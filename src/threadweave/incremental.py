"""Incremental, identity-aware mailbox threading over the batch RFC engine.

The batch :func:`threadweave.thread_messages` function remains the correctness
oracle.  This module adds an atomic state boundary that indexes caller-owned
message keys, recomputes only affected connectivity components, reports explicit
thread merge/split transitions, and snapshots JSON-safe metadata without caller
payloads.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from _thread import RLock
from typing import Literal, TypeVar

from threadweave.collation import unicode_casemap_key
from threadweave.container import Container
from threadweave.headers import extract_reference_ids, normalize_message_id
from threadweave.subject import normalize_subject
from threadweave.threading import Message, thread_messages

__all__ = [
    "ExternalIdentityError",
    "IncrementalThreadError",
    "IncrementalThreadIndex",
    "IndexedMessage",
    "MailboxChangeSet",
    "ThreadDelta",
    "ThreadProjection",
    "ThreadTransition",
    "VersionConflictError",
]

_batch_thread_messages = thread_messages
_MAX_MESSAGE_KEY_LENGTH = 512
_MAX_EXTERNAL_ID_LENGTH = 255
_OBJECT_ID_CHARACTERS = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"
)
_MAX_IMAP_NUMBER = 4_294_967_295
_DEFAULT_MAX_SNAPSHOT_RECORDS = 1_000_000
_DEFAULT_MAX_SNAPSHOT_BYTES = 256 * 1024 * 1024
_SNAPSHOT_SCHEMA_VERSION = 1

_KeyT = TypeVar("_KeyT")
_ValueT = TypeVar("_ValueT")


class _OverlayMapping(Mapping[_KeyT, _ValueT]):
    """Expose staged updates over a base mapping without copying unrelated entries."""

    def __init__(
        self,
        base: Mapping[_KeyT, _ValueT],
        updates: Mapping[_KeyT, _ValueT],
        removals: frozenset[_KeyT] = frozenset(),
    ) -> None:
        """Retain immutable transaction views of one base mapping and its delta."""
        self._base = base
        self._updates = updates
        self._removals = removals

    def __getitem__(self, key: _KeyT) -> _ValueT:
        """Return a staged value, excluding keys removed by the transaction."""
        if key in self._updates:
            return self._updates[key]
        if key in self._removals:
            raise KeyError(key)
        return self._base[key]

    def __iter__(self) -> Iterator[_KeyT]:
        """Iterate the logical mapping only when a global operation requires it."""
        for key in self._base:
            if key not in self._removals and key not in self._updates:
                yield key
        yield from self._updates

    def __len__(self) -> int:
        """Return logical size from the bounded transaction delta."""
        removed = sum(
            1
            for key in self._removals
            if key in self._base and key not in self._updates
        )
        added = sum(1 for key in self._updates if key not in self._base)
        return len(self._base) - removed + added

    def __contains__(self, key: object) -> bool:
        """Test logical membership without iterating the base mapping."""
        if key in self._updates:
            return True
        if key in self._removals:
            return False
        return key in self._base


class IncrementalThreadError(ValueError):
    """Raised when an incremental change or snapshot violates its contract."""


class VersionConflictError(IncrementalThreadError):
    """Raised when an optimistic change targets a stale index version."""


class ExternalIdentityError(IncrementalThreadError):
    """Raised when caller-owned EMAILID or THREADID metadata is inconsistent."""


def _validated_positive_limit(value: object, name: str) -> int:
    """Return a positive non-boolean integer denial-of-service limit."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise IncrementalThreadError(f"{name} must be a positive integer")
    return value


def _validated_nonnegative_integer(value: object, name: str) -> int:
    """Return a non-negative non-boolean integer revision value."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise IncrementalThreadError(f"{name} must be a non-negative integer")
    return value


def _validated_identifier(
    value: object,
    name: str,
    *,
    allow_none: bool,
    maximum_length: int,
) -> str | None:
    """Validate one bounded printable caller-owned identifier."""
    if value is None and allow_none:
        return None
    if not isinstance(value, str) or not value or len(value) > maximum_length:
        raise IncrementalThreadError(
            f"{name} must be a non-empty string of at most {maximum_length} characters"
        )
    if any(not character.isprintable() for character in value):
        raise IncrementalThreadError(f"{name} must contain only printable characters")
    return value


def _validated_message_key(value: object) -> str:
    """Return one safe immutable caller message key."""
    validated = _validated_identifier(
        value,
        "message_key",
        allow_none=False,
        maximum_length=_MAX_MESSAGE_KEY_LENGTH,
    )
    assert validated is not None
    return validated


def _validated_external_id(value: object, name: str) -> str | None:
    """Return one optional RFC 8474 ``objectid`` value."""
    validated = _validated_identifier(
        value,
        name,
        allow_none=True,
        maximum_length=_MAX_EXTERNAL_ID_LENGTH,
    )
    if validated is not None and any(
        character not in _OBJECT_ID_CHARACTERS for character in validated
    ):
        raise IncrementalThreadError(
            f"{name} must use only ASCII letters, digits, underscore, or hyphen"
        )
    return validated


def _tuple_without_duplicate_keys(
    values: Iterable[object],
    name: str,
    *,
    indexed: bool,
) -> tuple[object, ...]:
    """Materialize one request sequence and reject duplicate caller keys."""
    materialized = tuple(values)
    keys: list[str] = []
    for value in materialized:
        if indexed:
            if not isinstance(value, IndexedMessage):
                raise IncrementalThreadError(f"{name} must contain IndexedMessage values")
            key = value.message_key
        else:
            key = _validated_message_key(value)
        keys.append(key)
    if len(set(keys)) != len(keys):
        raise IncrementalThreadError(f"duplicate message keys in {name}")
    return materialized


@dataclass(frozen=True, slots=True)
class IndexedMessage:
    """One message plus immutable caller and optional external identities.

    Args:
        message_key: Caller-owned key that is stable across mailbox revisions.
        message: Structural email metadata and an arbitrary in-memory payload.
        email_id: Optional RFC 8474 immutable message-content identifier.
        thread_id: Optional RFC 8474 caller/server thread correlator.
    """

    message_key: str
    message: Message
    email_id: str | None = None
    thread_id: str | None = None

    def __post_init__(self) -> None:
        """Validate public identity values without copying message metadata yet."""
        object.__setattr__(self, "message_key", _validated_message_key(self.message_key))
        if not isinstance(self.message, Message):
            raise IncrementalThreadError("message must be a threadweave.Message")
        object.__setattr__(
            self,
            "email_id",
            _validated_external_id(self.email_id, "email_id"),
        )
        object.__setattr__(
            self,
            "thread_id",
            _validated_external_id(self.thread_id, "thread_id"),
        )


@dataclass(frozen=True, slots=True)
class MailboxChangeSet:
    """One optimistic and atomic mailbox mutation request."""

    expected_version: int
    additions: tuple[IndexedMessage, ...] = ()
    replacements: tuple[IndexedMessage, ...] = ()
    removals: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Normalize request sequences and require disjoint unique key sets."""
        object.__setattr__(
            self,
            "expected_version",
            _validated_nonnegative_integer(self.expected_version, "expected_version"),
        )
        additions = _tuple_without_duplicate_keys(
            self.additions,
            "additions",
            indexed=True,
        )
        replacements = _tuple_without_duplicate_keys(
            self.replacements,
            "replacements",
            indexed=True,
        )
        removals = _tuple_without_duplicate_keys(
            self.removals,
            "removals",
            indexed=False,
        )
        addition_keys = {item.message_key for item in additions}
        replacement_keys = {item.message_key for item in replacements}
        removal_keys = set(removals)
        if (
            addition_keys & replacement_keys
            or addition_keys & removal_keys
            or replacement_keys & removal_keys
        ):
            raise IncrementalThreadError(
                "addition, replacement, and removal message keys must be disjoint"
            )
        object.__setattr__(self, "additions", additions)
        object.__setattr__(self, "replacements", replacements)
        object.__setattr__(self, "removals", removals)


@dataclass(frozen=True, slots=True)
class ThreadProjection:
    """A deterministic caller-key view of one returned thread root."""

    message_keys: tuple[str, ...]
    thread_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ThreadTransition:
    """One explicit structural merge or split across caller thread IDs."""

    kind: Literal["merge", "split"]
    before: tuple[ThreadProjection, ...]
    after: tuple[ThreadProjection, ...]
    thread_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ThreadDelta:
    """Deterministic differences produced by one successful atomic change."""

    previous_version: int
    version: int
    affected_message_keys: tuple[str, ...]
    added_threads: tuple[ThreadProjection, ...]
    removed_threads: tuple[ThreadProjection, ...]
    updated_threads: tuple[ThreadProjection, ...]
    merges: tuple[ThreadTransition, ...]
    splits: tuple[ThreadTransition, ...]


def _validated_optional_number(
    value: object,
    name: str,
    *,
    maximum: int | None = None,
) -> int | None:
    """Validate optional positive integer mailbox metadata."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise IncrementalThreadError(f"{name} must be a positive integer or None")
    if maximum is not None and value > maximum:
        raise IncrementalThreadError(f"{name} exceeds the unsigned 32-bit range")
    return value


def _validated_optional_text(value: object, name: str) -> str | None:
    """Validate an optional textual email field."""
    if value is None or isinstance(value, str):
        return value
    raise IncrementalThreadError(f"{name} must be a string or None")


def _copied_reference_value(
    value: str | Sequence[str] | None,
    name: str,
) -> str | tuple[str, ...] | None:
    """Copy one raw or already-split identification header value."""
    if value is None or isinstance(value, str):
        return value
    try:
        copied = tuple(value)
    except TypeError as error:
        raise IncrementalThreadError(
            f"{name} must be a string, sequence of strings, or None"
        ) from error
    if not all(isinstance(item, str) for item in copied):
        raise IncrementalThreadError(f"{name} must contain only strings")
    return copied


def _copied_date_value(value: object, name: str) -> str | datetime | None:
    """Copy one supported date value after validating its runtime type."""
    if value is None or isinstance(value, (str, datetime)):
        return value
    raise IncrementalThreadError(f"{name} must be a datetime, string, or None")


def _copied_indexed_message(record: IndexedMessage) -> IndexedMessage:
    """Copy structural metadata while retaining the caller payload by reference."""
    message = record.message
    copied = Message(
        message_id=_validated_optional_text(message.message_id, "message_id"),
        in_reply_to=_copied_reference_value(message.in_reply_to, "in_reply_to"),
        references=_copied_reference_value(message.references, "references") or (),
        subject=_validated_optional_text(message.subject, "subject"),
        payload=message.payload,
        sent_date=_copied_date_value(message.sent_date, "sent_date"),
        internal_date=_copied_date_value(message.internal_date, "internal_date"),
        sequence_number=_validated_optional_number(
            message.sequence_number,
            "sequence_number",
        ),
        uid=_validated_optional_number(message.uid, "uid", maximum=_MAX_IMAP_NUMBER),
    )
    return IndexedMessage(
        message_key=record.message_key,
        message=copied,
        email_id=record.email_id,
        thread_id=record.thread_id,
    )


def _reference_ids(value: str | Sequence[str] | None) -> tuple[str, ...]:
    """Parse and de-duplicate one raw or split identification field."""
    if value is None:
        return ()
    values = (value,) if isinstance(value, str) else value
    result: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        for identifier in extract_reference_ids(raw_value):
            if identifier not in seen:
                seen.add(identifier)
                result.append(identifier)
    return tuple(result)


def _effective_reference_ids(message: Message) -> tuple[str, ...]:
    """Return the RFC 5256 ancestry identifiers used by the batch algorithm."""
    references = _reference_ids(message.references)
    if references:
        return references
    return _reference_ids(message.in_reply_to)[:1]


def _connectivity_tokens(
    record: IndexedMessage,
    *,
    group_by_subject: bool,
) -> frozenset[str]:
    """Return an over-approximating connectivity token set for one record."""
    tokens: set[str] = set()
    message_id = normalize_message_id(record.message.message_id)
    if message_id is not None:
        tokens.add(f"id\x00{message_id}")
    for reference_id in _effective_reference_ids(record.message):
        tokens.add(f"id\x00{reference_id}")
    if group_by_subject:
        subject_key = unicode_casemap_key(normalize_subject(record.message.subject))
        if subject_key:
            tokens.add(f"subject\x00{subject_key}")
    return frozenset(tokens)


def _writable_bucket(
    bucket_key: str,
    base_buckets: Mapping[str, set[str]],
    bucket_updates: dict[str, set[str]],
) -> set[str]:
    """Return one transaction-owned copy of a reverse-index bucket."""
    if bucket_key not in bucket_updates:
        bucket_updates[bucket_key] = set(base_buckets.get(bucket_key, set()))
    return bucket_updates[bucket_key]


def _remove_key_from_buckets(
    key: str,
    bucket_keys: Iterable[str],
    base_buckets: Mapping[str, set[str]],
    bucket_updates: dict[str, set[str]],
) -> None:
    """Stage removal of one record key from selected reverse-index buckets."""
    for bucket_key in bucket_keys:
        _writable_bucket(bucket_key, base_buckets, bucket_updates).discard(key)


def _add_key_to_buckets(
    key: str,
    bucket_keys: Iterable[str],
    base_buckets: Mapping[str, set[str]],
    bucket_updates: dict[str, set[str]],
) -> None:
    """Stage insertion of one record key into selected reverse-index buckets."""
    for bucket_key in bucket_keys:
        _writable_bucket(bucket_key, base_buckets, bucket_updates).add(key)


def _commit_bucket_updates(
    target: dict[str, set[str]],
    bucket_updates: Mapping[str, set[str]],
) -> None:
    """Publish touched reverse buckets and discard buckets that became empty."""
    for bucket_key, values in bucket_updates.items():
        if values:
            target[bucket_key] = values
        else:
            target.pop(bucket_key, None)


def _email_state_after(
    email_id: str,
    base_states: Mapping[str, tuple[str | None, int]],
    state_updates: Mapping[str, tuple[str | None, int] | None],
) -> tuple[str | None, int] | None:
    """Return one staged EMAILID association and reference count."""
    if email_id in state_updates:
        return state_updates[email_id]
    return base_states.get(email_id)


def _thread_count_after(
    thread_id: str,
    base_counts: Mapping[str, int],
    count_updates: Mapping[str, int],
) -> int:
    """Return one staged THREADID reference count."""
    return count_updates.get(thread_id, base_counts.get(thread_id, 0))


def _stage_external_identity(
    record: IndexedMessage,
    adjustment: Literal[-1, 1],
    base_email_states: Mapping[str, tuple[str | None, int]],
    email_state_updates: dict[str, tuple[str | None, int] | None],
    base_thread_counts: Mapping[str, int],
    thread_count_updates: dict[str, int],
    touched_values: set[str],
) -> None:
    """Stage one record's RFC 8474 identity contribution without a global scan."""
    email_id = record.email_id
    if email_id is not None:
        touched_values.add(email_id)
        current_state = _email_state_after(
            email_id,
            base_email_states,
            email_state_updates,
        )
        if adjustment < 0:
            if current_state is None or current_state[0] != record.thread_id:
                raise IncrementalThreadError("internal EMAILID index is inconsistent")
            next_count = current_state[1] - 1
            email_state_updates[email_id] = (
                None
                if next_count == 0
                else (current_state[0], next_count)
            )
        else:
            if current_state is not None and current_state[0] != record.thread_id:
                raise ExternalIdentityError(
                    f"messages with EMAILID {email_id!r} must expose the same THREADID"
                )
            email_state_updates[email_id] = (
                record.thread_id,
                1 if current_state is None else current_state[1] + 1,
            )

    thread_id = record.thread_id
    if thread_id is not None:
        touched_values.add(thread_id)
        next_count = (
            _thread_count_after(
                thread_id,
                base_thread_counts,
                thread_count_updates,
            )
            + adjustment
        )
        if next_count < 0:
            raise IncrementalThreadError("internal THREADID index is inconsistent")
        thread_count_updates[thread_id] = next_count


def _validate_touched_identity_namespaces(
    touched_values: Iterable[str],
    base_email_states: Mapping[str, tuple[str | None, int]],
    email_state_updates: Mapping[str, tuple[str | None, int] | None],
    base_thread_counts: Mapping[str, int],
    thread_count_updates: Mapping[str, int],
) -> None:
    """Reject touched ObjectID values present in both RFC 8474 namespaces."""
    reused_values = sorted(
        identity_value
        for identity_value in touched_values
        if _email_state_after(
            identity_value,
            base_email_states,
            email_state_updates,
        )
        is not None
        and _thread_count_after(
            identity_value,
            base_thread_counts,
            thread_count_updates,
        )
        > 0
    )
    if reused_values:
        raise ExternalIdentityError(
            "EMAILID and THREADID must use disjoint ObjectID values: "
            f"{reused_values!r}"
        )


def _commit_external_identity_updates(
    email_states: dict[str, tuple[str | None, int]],
    email_state_updates: Mapping[str, tuple[str | None, int] | None],
    thread_counts: dict[str, int],
    thread_count_updates: Mapping[str, int],
) -> None:
    """Publish touched compact RFC 8474 indexes after transaction validation."""
    for email_id, state in email_state_updates.items():
        if state is None:
            email_states.pop(email_id, None)
        else:
            email_states[email_id] = state
    for thread_id, count in thread_count_updates.items():
        if count == 0:
            thread_counts.pop(thread_id, None)
        else:
            thread_counts[thread_id] = count


def _ordered_keys(keys: Iterable[str], positions: Mapping[str, int]) -> tuple[str, ...]:
    """Return keys in stable insertion order with a lexical safety tie-breaker."""
    return tuple(sorted(keys, key=lambda key: (positions[key], key)))


def _current_ranks(positions: Mapping[str, int]) -> dict[str, int]:
    """Return compact one-based input positions for the current record order."""
    return {
        key: rank
        for rank, key in enumerate(_ordered_keys(positions, positions), start=1)
    }


def _validate_effective_sequence_numbers(
    records: Mapping[str, IndexedMessage],
    ranks: Mapping[str, int],
) -> None:
    """Reject global explicit/implicit sequence collisions before recomputation."""
    used: dict[int, str] = {}
    for key in _ordered_keys(records, ranks):
        explicit = records[key].message.sequence_number
        sequence_number = ranks[key] if explicit is None else explicit
        previous = used.get(sequence_number)
        if previous is not None:
            raise IncrementalThreadError(
                f"duplicate sequence number: {sequence_number} ({previous}, {key})"
            )
        used[sequence_number] = key


def _validate_replacement_identity(
    old_record: IndexedMessage,
    new_record: IndexedMessage,
) -> None:
    """Prevent removal or change of an already reported external identifier."""
    if old_record.email_id is not None and new_record.email_id != old_record.email_id:
        raise ExternalIdentityError("reported email_id is immutable on replacement")
    if old_record.thread_id is not None and new_record.thread_id != old_record.thread_id:
        raise ExternalIdentityError("reported thread_id is immutable on replacement")


def _expand_candidate_keys(
    seeds: set[str],
    tokens_by_key: Mapping[str, frozenset[str]],
    keys_by_token: Mapping[str, set[str]],
) -> set[str]:
    """Expand candidate keys through current token connectivity iteratively."""
    expanded = {key for key in seeds if key in tokens_by_key}
    queue = list(expanded)
    while queue:
        key = queue.pop()
        for token in tokens_by_key.get(key, frozenset()):
            for neighbor in keys_by_token.get(token, set()):
                if neighbor not in expanded:
                    expanded.add(neighbor)
                    queue.append(neighbor)
    return expanded


def _partition_components(
    keys: set[str],
    positions: Mapping[str, int],
    tokens_by_key: Mapping[str, frozenset[str]],
    keys_by_token: Mapping[str, set[str]],
) -> tuple[tuple[str, ...], ...]:
    """Partition candidate keys into deterministic current connectivity components."""
    remaining = set(keys)
    components: list[tuple[str, ...]] = []
    for seed in _ordered_keys(keys, positions):
        if seed not in remaining:
            continue
        component = {seed}
        queue = [seed]
        remaining.remove(seed)
        while queue:
            key = queue.pop()
            for token in tokens_by_key.get(key, frozenset()):
                for neighbor in keys_by_token.get(token, set()):
                    if neighbor in remaining:
                        remaining.remove(neighbor)
                        component.add(neighbor)
                        queue.append(neighbor)
        components.append(_ordered_keys(component, positions))
    return tuple(components)


def _message_for_batch(message: Message, sequence_number: int | None) -> Message:
    """Return a computation copy with an explicit global sequence when required."""
    if sequence_number is None or message.sequence_number is not None:
        return message
    return Message(
        message_id=message.message_id,
        in_reply_to=message.in_reply_to,
        references=message.references,
        subject=message.subject,
        payload=message.payload,
        sent_date=message.sent_date,
        internal_date=message.internal_date,
        sequence_number=sequence_number,
        uid=message.uid,
    )


def _public_message_copy(message: Message) -> Message:
    """Copy structural message metadata while retaining the caller payload."""
    return Message(
        message_id=message.message_id,
        in_reply_to=message.in_reply_to,
        references=message.references,
        subject=message.subject,
        payload=message.payload,
        sent_date=message.sent_date,
        internal_date=message.internal_date,
        sequence_number=message.sequence_number,
        uid=message.uid,
    )


def _public_forest_copy(roots: Iterable[Container]) -> tuple[Container, ...]:
    """Return a loop-safe defensive copy of the index's internal forest."""
    copied_roots: list[Container] = []
    seen: set[int] = set()
    for root in roots:
        root_identity = id(root)
        if root_identity in seen:
            raise IncrementalThreadError(
                "internal thread forest contains a shared or cyclic container"
            )
        root_copy = Container(
            message=None
            if root.message is None
            else _public_message_copy(root.message)
        )
        copied_roots.append(root_copy)
        seen.add(root_identity)
        stack: list[tuple[Container, Container]] = [(root, root_copy)]
        while stack:
            source, target = stack.pop()
            for child in source.children:
                child_identity = id(child)
                if child_identity in seen:
                    raise IncrementalThreadError(
                        "internal thread forest contains a shared or cyclic container"
                    )
                child_copy = Container(
                    message=None
                    if child.message is None
                    else _public_message_copy(child.message),
                    parent=target,
                )
                target.children.append(child_copy)
                seen.add(child_identity)
                stack.append((child, child_copy))
    return tuple(copied_roots)


def _projection_for_root(
    root: Container,
    key_by_message_identity: Mapping[int, str],
    records: Mapping[str, IndexedMessage],
) -> ThreadProjection:
    """Project one root into traversal-ordered caller keys and external IDs."""
    message_keys: list[str] = []
    seen: set[int] = set()
    stack = [root]
    while stack:
        node = stack.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        if node.message is not None:
            key = key_by_message_identity.get(id(node.message))
            if key is None:
                raise IncrementalThreadError(
                    "batch output contained a message outside its component"
                )
            message_keys.append(key)
        stack.extend(reversed(node.children))
    thread_ids = tuple(
        sorted(
            {
                records[key].thread_id
                for key in message_keys
                if records[key].thread_id is not None
            }
        )
    )
    return ThreadProjection(tuple(message_keys), thread_ids)


def _build_forest(
    keys: tuple[str, ...],
    records: Mapping[str, IndexedMessage],
    ranks: Mapping[str, int],
    *,
    group_by_subject: bool,
    sort_by_sent_date: bool,
) -> tuple[tuple[Container, ...], tuple[ThreadProjection, ...]]:
    """Run the canonical batch engine for one ordered record subset."""
    messages: list[Message] = []
    key_by_message_identity: dict[int, str] = {}
    for key in keys:
        message = _message_for_batch(
            records[key].message,
            ranks[key] if sort_by_sent_date else None,
        )
        messages.append(message)
        key_by_message_identity[id(message)] = key
    roots = tuple(
        _batch_thread_messages(
            messages,
            group_by_subject=group_by_subject,
            sort_by_sent_date=sort_by_sent_date,
        )
    )
    projections = tuple(
        _projection_for_root(root, key_by_message_identity, records) for root in roots
    )
    for key, message in zip(keys, messages):
        if records[key].message.sequence_number is None:
            message.sequence_number = None
    return roots, projections


def _transition_thread_ids(
    before: Iterable[ThreadProjection],
    after: Iterable[ThreadProjection],
) -> tuple[str, ...]:
    """Return every distinct caller THREADID represented by a transition."""
    return tuple(
        sorted(
            {
                thread_id
                for projection in (*tuple(before), *tuple(after))
                for thread_id in projection.thread_ids
            }
        )
    )


def _projection_membership(
    projections: Sequence[ThreadProjection],
    name: str,
) -> dict[str, int]:
    """Index each caller key once and reject overlapping root projections."""
    membership: dict[str, int] = {}
    for projection_index, projection in enumerate(projections):
        for message_key in projection.message_keys:
            if message_key in membership:
                raise IncrementalThreadError(
                    f"{name} projections contain duplicate message_key: {message_key}"
                )
            membership[message_key] = projection_index
    return membership


def _thread_delta(
    previous_version: int,
    version: int,
    affected_message_keys: tuple[str, ...],
    before: Sequence[ThreadProjection],
    after: Sequence[ThreadProjection],
) -> ThreadDelta:
    """Classify projection changes and transitions in linear message-key work."""
    before_tuple = tuple(before)
    after_tuple = tuple(after)
    before_membership = _projection_membership(before_tuple, "before")
    after_membership = _projection_membership(after_tuple, "after")

    before_by_after: list[set[int]] = [set() for _ in after_tuple]
    after_by_before: list[set[int]] = [set() for _ in before_tuple]
    for message_key, after_index in after_membership.items():
        before_index = before_membership.get(message_key)
        if before_index is not None:
            before_by_after[after_index].add(before_index)
            after_by_before[before_index].add(after_index)

    before_values = set(before_tuple)
    added = tuple(
        projection
        for projection, overlaps in zip(after_tuple, before_by_after)
        if not overlaps
    )
    removed = tuple(
        projection
        for projection, overlaps in zip(before_tuple, after_by_before)
        if not overlaps
    )
    updated = tuple(
        projection
        for projection, overlaps in zip(after_tuple, before_by_after)
        if overlaps and projection not in before_values
    )
    merges = tuple(
        ThreadTransition(
            "merge",
            tuple(before_tuple[index] for index in sorted(overlaps)),
            (projection,),
            _transition_thread_ids(
                tuple(before_tuple[index] for index in sorted(overlaps)),
                (projection,),
            ),
        )
        for projection, overlaps in zip(after_tuple, before_by_after)
        if len(overlaps) > 1
    )
    splits = tuple(
        ThreadTransition(
            "split",
            (projection,),
            tuple(after_tuple[index] for index in sorted(overlaps)),
            _transition_thread_ids(
                (projection,),
                tuple(after_tuple[index] for index in sorted(overlaps)),
            ),
        )
        for projection, overlaps in zip(before_tuple, after_by_before)
        if len(overlaps) > 1
    )
    return ThreadDelta(
        previous_version,
        version,
        affected_message_keys,
        added,
        removed,
        updated,
        merges,
        splits,
    )


def _encoded_date(value: str | datetime | None) -> object:
    """Encode one date value into a deterministic JSON-safe tagged form."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return {"kind": "datetime", "value": value.isoformat()}
    return {"kind": "text", "value": value}


def _decoded_date(value: object, name: str) -> str | datetime | None:
    """Decode one strict tagged date value from an untrusted snapshot."""
    if value is None:
        return None
    if not isinstance(value, Mapping) or set(value) != {"kind", "value"}:
        raise IncrementalThreadError(f"{name} date value is malformed")
    kind = value["kind"]
    encoded = value["value"]
    if not isinstance(encoded, str):
        raise IncrementalThreadError(f"{name} date value must be textual")
    if kind == "text":
        return encoded
    if kind == "datetime":
        try:
            return datetime.fromisoformat(encoded)
        except ValueError as error:
            raise IncrementalThreadError(f"{name} datetime is invalid") from error
    raise IncrementalThreadError(f"{name} date kind is unsupported")


def _require_plain_json_containers(
    value: object,
    *,
    maximum_nodes: int | None = None,
) -> None:
    """Reject executable, cyclic, aliased, or structurally oversized JSON trees.

    JSON decoding produces a tree of built-in dictionaries, lists, string
    keys, and scalar values. Requiring exact runtime types prevents attacker-
    controlled iteration, comparison, or scalar subclasses from executing,
    while rejecting repeated container identities prevents a compact Python
    object graph from expanding exponentially during JSON encoding. A node
    ceiling derived from the byte limit bounds validation before serialization.
    """
    pending = [(value, False)]
    active_containers: set[int] = set()
    seen_containers: set[int] = set()
    visited_nodes = 0
    while pending:
        current, exiting = pending.pop()
        if not exiting:
            visited_nodes += 1
            if maximum_nodes is not None and visited_nodes > maximum_nodes:
                raise IncrementalThreadError("snapshot exceeds max_snapshot_bytes")
        if type(current) in {dict, list}:
            identity = id(current)
            if exiting:
                active_containers.remove(identity)
                continue
            if identity in active_containers:
                raise IncrementalThreadError(
                    "snapshot must not contain cyclic JSON containers"
                )
            if identity in seen_containers:
                raise IncrementalThreadError(
                    "snapshot must not contain reused JSON container objects"
                )
            if type(current) is dict and any(
                type(key) is not str for key in dict.keys(current)
            ):
                raise IncrementalThreadError(
                    "snapshot object keys must be plain strings"
                )
            seen_containers.add(identity)
            active_containers.add(identity)
            pending.append((current, True))
            children = dict.values(current) if type(current) is dict else current
            pending.extend((child, False) for child in children)
        elif current is None or type(current) in {str, int, float, bool}:
            continue
        else:
            raise IncrementalThreadError(
                "snapshot must contain only plain JSON containers and scalar values"
            )


def _bounded_utf8_size(value: str, maximum_bytes: int) -> int:
    """Count UTF-8 bytes up to a limit without allocating an encoded copy."""
    if str.isascii(value):
        return str.__len__(value)

    encoded_bytes = 0
    for index in range(str.__len__(value)):
        code_point = ord(str.__getitem__(value, index))
        if code_point <= 0x7F:
            width = 1
        elif code_point <= 0x7FF:
            width = 2
        elif 0xD800 <= code_point <= 0xDFFF:
            raise UnicodeEncodeError(
                "utf-8",
                value,
                index,
                index + 1,
                "surrogates not allowed",
            )
        elif code_point <= 0xFFFF:
            width = 3
        else:
            width = 4
        encoded_bytes += width
        if encoded_bytes > maximum_bytes:
            break
    return encoded_bytes


def _bounded_snapshot_json_size(value: object, maximum_bytes: int) -> int:
    """Return canonical UTF-8 size while stopping at the configured byte limit."""
    encoder = json.JSONEncoder(
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    encoded_bytes = 0
    try:
        for chunk in encoder.iterencode(value):
            encoded_bytes += _bounded_utf8_size(
                chunk,
                maximum_bytes - encoded_bytes,
            )
            if encoded_bytes > maximum_bytes:
                raise IncrementalThreadError("snapshot exceeds max_snapshot_bytes")
    except IncrementalThreadError:
        raise
    except (RecursionError, TypeError, UnicodeError, ValueError) as error:
        raise IncrementalThreadError(
            "snapshot must contain only JSON-safe values"
        ) from error
    return encoded_bytes


def _required_plain_object(
    value: object,
    expected: set[str],
    name: str,
) -> dict[str, object]:
    """Return one exact built-in JSON object with the required plain-string keys."""
    if not isinstance(value, Mapping):
        raise IncrementalThreadError(f"{name} must be a mapping")
    if type(value) is not dict:
        raise IncrementalThreadError(
            "snapshot must contain only plain JSON containers and scalar values"
        )
    if dict.__len__(value) != len(expected):
        raise IncrementalThreadError(f"{name} fields do not match the schema")
    keys = dict.keys(value)
    if any(type(key) is not str for key in keys):
        raise IncrementalThreadError("snapshot object keys must be plain strings")
    if set(keys) != expected:
        raise IncrementalThreadError(f"{name} fields do not match the schema")
    return value


class IncrementalThreadIndex:
    """Maintain batch-equivalent thread roots across atomic mailbox changes."""

    def __init__(
        self,
        *,
        group_by_subject: bool = False,
        sort_by_sent_date: bool = False,
        max_snapshot_records: int = _DEFAULT_MAX_SNAPSHOT_RECORDS,
        max_snapshot_bytes: int = _DEFAULT_MAX_SNAPSHOT_BYTES,
    ) -> None:
        """Create an empty index with batch-compatible options and snapshot bounds."""
        if not isinstance(group_by_subject, bool):
            raise IncrementalThreadError("group_by_subject must be a boolean")
        if not isinstance(sort_by_sent_date, bool):
            raise IncrementalThreadError("sort_by_sent_date must be a boolean")
        self._state_lock = RLock()
        self._group_by_subject = group_by_subject
        self._sort_by_sent_date = sort_by_sent_date
        self._max_snapshot_records = _validated_positive_limit(
            max_snapshot_records,
            "max_snapshot_records",
        )
        self._max_snapshot_bytes = _validated_positive_limit(
            max_snapshot_bytes,
            "max_snapshot_bytes",
        )
        self._version = 0
        self._records: dict[str, IndexedMessage] = {}
        self._positions: dict[str, int] = {}
        self._next_position = 1
        self._tokens_by_key: dict[str, frozenset[str]] = {}
        self._keys_by_token: dict[str, set[str]] = {}
        self._email_id_states: dict[str, tuple[str | None, int]] = {}
        self._thread_id_counts: dict[str, int] = {}
        self._component_by_key: dict[str, str] = {}
        self._keys_by_component: dict[str, tuple[str, ...]] = {}
        self._roots: tuple[Container, ...] | None = ()
        self._projections: tuple[ThreadProjection, ...] | None = ()

    def __len__(self) -> int:
        """Return the number of indexed caller message keys."""
        with self._state_lock:
            return len(self._records)

    def _materialize_forest(self) -> None:
        """Build and cache the complete canonical forest only when requested."""
        if self._roots is not None and self._projections is not None:
            return
        ranks = (
            _current_ranks(self._positions)
            if self._sort_by_sent_date
            else self._positions
        )
        roots, projections = _build_forest(
            self.message_keys,
            self._records,
            ranks,
            group_by_subject=self._group_by_subject,
            sort_by_sent_date=self._sort_by_sent_date,
        )
        self._roots = roots
        self._projections = projections

    @property
    def version(self) -> int:
        """Return the optimistic mailbox-state version."""
        with self._state_lock:
            return self._version

    @property
    def message_keys(self) -> tuple[str, ...]:
        """Return current caller keys in stable batch input order."""
        with self._state_lock:
            return _ordered_keys(self._records, self._positions)

    @property
    def roots(self) -> tuple[Container, ...]:
        """Return defensive transport-neutral copies of current thread roots."""
        with self._state_lock:
            self._materialize_forest()
            assert self._roots is not None
            return _public_forest_copy(self._roots)

    @property
    def projections(self) -> tuple[ThreadProjection, ...]:
        """Return deterministic caller-key projections for current roots."""
        with self._state_lock:
            self._materialize_forest()
            assert self._projections is not None
            return self._projections

    def apply(self, change_set: MailboxChangeSet) -> ThreadDelta:
        """Atomically apply one optimistic mailbox change set.

        Concurrent callers are serialized. A second writer using the same
        ``expected_version`` observes the first commit and raises
        :class:`VersionConflictError` instead of interleaving copied state.

        Raises:
            VersionConflictError: ``expected_version`` is stale.
            IncrementalThreadError: Key ownership, metadata, or graph processing
                violates the public contract. The existing state remains unchanged.
            ExternalIdentityError: Reported EMAILID/THREADID metadata changes or
                conflicts across equal EMAILID values.
        """
        with self._state_lock:
            return self._apply_locked(change_set)

    def _apply_locked(self, change_set: MailboxChangeSet) -> ThreadDelta:
        """Apply one change while ``_state_lock`` protects every state field."""
        if not isinstance(change_set, MailboxChangeSet):
            raise IncrementalThreadError("change_set must be a MailboxChangeSet")
        if change_set.expected_version != self._version:
            raise VersionConflictError(
                f"expected version {change_set.expected_version}; "
                f"current version {self._version}"
            )
        if not (
            change_set.additions or change_set.replacements or change_set.removals
        ):
            return ThreadDelta(
                self._version,
                self._version,
                (),
                (),
                (),
                (),
                (),
                (),
            )

        addition_keys = {record.message_key for record in change_set.additions}
        replacement_keys = {record.message_key for record in change_set.replacements}
        removal_keys = set(change_set.removals)
        already_present = {key for key in addition_keys if key in self._records}
        missing_replacements = {
            key for key in replacement_keys if key not in self._records
        }
        missing_removals = {key for key in removal_keys if key not in self._records}
        if already_present:
            raise IncrementalThreadError(
                f"addition keys already exist: {sorted(already_present)!r}"
            )
        if missing_replacements:
            raise IncrementalThreadError(
                f"replacement keys do not exist: {sorted(missing_replacements)!r}"
            )
        if missing_removals:
            raise IncrementalThreadError(
                f"removal keys do not exist: {sorted(missing_removals)!r}"
            )

        copied_additions = tuple(
            _copied_indexed_message(record) for record in change_set.additions
        )
        copied_replacements = tuple(
            _copied_indexed_message(record) for record in change_set.replacements
        )
        for replacement in copied_replacements:
            _validate_replacement_identity(
                self._records[replacement.message_key],
                replacement,
            )

        record_updates = {
            record.message_key: record
            for record in (*copied_replacements, *copied_additions)
        }
        records = _OverlayMapping(
            self._records,
            record_updates,
            frozenset(removal_keys),
        )
        position_updates: dict[str, int] = {}
        next_position = self._next_position
        for addition in copied_additions:
            position_updates[addition.message_key] = next_position
            next_position += 1
        positions = _OverlayMapping(
            self._positions,
            position_updates,
            frozenset(removal_keys),
        )

        token_updates: dict[str, frozenset[str]] = {}
        token_bucket_updates: dict[str, set[str]] = {}
        email_state_updates: dict[str, tuple[str | None, int] | None] = {}
        thread_count_updates: dict[str, int] = {}
        changed_existing_keys = replacement_keys | removal_keys
        candidate_seeds: set[str] = set()
        touched_tokens: set[str] = set()
        touched_identity_values: set[str] = set()

        for key in changed_existing_keys:
            component_id = self._component_by_key.get(key)
            if component_id is not None:
                candidate_seeds.update(self._keys_by_component[component_id])
            old_tokens = self._tokens_by_key.get(key, frozenset())
            touched_tokens.update(old_tokens)
            _remove_key_from_buckets(
                key,
                old_tokens,
                self._keys_by_token,
                token_bucket_updates,
            )
            _stage_external_identity(
                self._records[key],
                -1,
                self._email_id_states,
                email_state_updates,
                self._thread_id_counts,
                thread_count_updates,
                touched_identity_values,
            )

        for record in (*copied_replacements, *copied_additions):
            tokens = _connectivity_tokens(
                record,
                group_by_subject=self._group_by_subject,
            )
            token_updates[record.message_key] = tokens
            touched_tokens.update(tokens)
            _add_key_to_buckets(
                record.message_key,
                tokens,
                self._keys_by_token,
                token_bucket_updates,
            )
            _stage_external_identity(
                record,
                1,
                self._email_id_states,
                email_state_updates,
                self._thread_id_counts,
                thread_count_updates,
                touched_identity_values,
            )
            candidate_seeds.add(record.message_key)

        tokens_by_key = _OverlayMapping(
            self._tokens_by_key,
            token_updates,
            frozenset(removal_keys),
        )
        keys_by_token = _OverlayMapping(self._keys_by_token, token_bucket_updates)

        for token in touched_tokens:
            candidate_seeds.update(keys_by_token.get(token, set()))
        for key in tuple(candidate_seeds):
            component_id = self._component_by_key.get(key)
            if component_id is not None:
                candidate_seeds.update(self._keys_by_component[component_id])

        old_component_ids = {
            self._component_by_key[key]
            for key in candidate_seeds
            if key in self._component_by_key
        }
        old_ranks = (
            _current_ranks(self._positions)
            if self._sort_by_sent_date
            else self._positions
        )
        before_affected_keys = _ordered_keys(
            {
                key
                for component_id in old_component_ids
                for key in self._keys_by_component[component_id]
            },
            self._positions,
        )
        _, before_affected_projections = _build_forest(
            before_affected_keys,
            self._records,
            old_ranks,
            group_by_subject=self._group_by_subject,
            sort_by_sent_date=self._sort_by_sent_date,
        )

        _validate_touched_identity_namespaces(
            touched_identity_values,
            self._email_id_states,
            email_state_updates,
            self._thread_id_counts,
            thread_count_updates,
        )
        ranks = (
            _current_ranks(positions)
            if self._sort_by_sent_date
            else positions
        )
        if self._sort_by_sent_date:
            _validate_effective_sequence_numbers(records, ranks)

        current_candidate_keys = _expand_candidate_keys(
            candidate_seeds,
            tokens_by_key,
            keys_by_token,
        )
        candidate_keys = current_candidate_keys | set(candidate_seeds)
        new_components = _partition_components(
            current_candidate_keys,
            positions,
            tokens_by_key,
            keys_by_token,
        )

        after_affected_keys = _ordered_keys(current_candidate_keys, positions)
        _, after_affected_projections = _build_forest(
            after_affected_keys,
            records,
            ranks,
            group_by_subject=self._group_by_subject,
            sort_by_sent_date=self._sort_by_sent_date,
        )
        affected_positions = {
            key: positions.get(key, self._positions.get(key, _MAX_IMAP_NUMBER))
            for key in candidate_keys
        }
        affected = tuple(
            sorted(candidate_keys, key=lambda key: (affected_positions[key], key))
        )
        previous_version = self._version
        version = previous_version + 1
        delta = _thread_delta(
            previous_version,
            version,
            affected,
            before_affected_projections,
            after_affected_projections,
        )

        for key in removal_keys:
            self._records.pop(key)
            self._positions.pop(key)
            self._tokens_by_key.pop(key, None)
        self._records.update(record_updates)
        self._positions.update(position_updates)
        self._tokens_by_key.update(token_updates)
        _commit_bucket_updates(self._keys_by_token, token_bucket_updates)
        _commit_external_identity_updates(
            self._email_id_states,
            email_state_updates,
            self._thread_id_counts,
            thread_count_updates,
        )

        for component_id in old_component_ids:
            self._keys_by_component.pop(component_id, None)
        for key in candidate_keys:
            self._component_by_key.pop(key, None)
        for keys in new_components:
            component_id = keys[0]
            self._keys_by_component[component_id] = keys
            for key in keys:
                self._component_by_key[key] = component_id

        self._next_position = next_position
        self._roots = None
        self._projections = None
        self._version = version
        return delta

    def snapshot(self) -> dict[str, object]:
        """Return deterministic versioned JSON-safe state without payload objects."""
        with self._state_lock:
            return self._snapshot_locked()

    def _snapshot_locked(self) -> dict[str, object]:
        """Build one snapshot while ``_state_lock`` protects current state."""
        if len(self._records) > self._max_snapshot_records:
            raise IncrementalThreadError(
                "snapshot exceeds max_snapshot_records"
            )
        records: list[dict[str, object]] = []
        for key in self.message_keys:
            record = self._records[key]
            message = record.message
            records.append(
                {
                    "message_key": key,
                    "email_id": record.email_id,
                    "thread_id": record.thread_id,
                    "message": {
                        "message_id": message.message_id,
                        "in_reply_to": list(_reference_ids(message.in_reply_to)),
                        "references": list(_reference_ids(message.references)),
                        "subject": message.subject,
                        "sent_date": _encoded_date(message.sent_date),
                        "internal_date": _encoded_date(message.internal_date),
                        "sequence_number": message.sequence_number,
                        "uid": message.uid,
                    },
                }
            )
        snapshot: dict[str, object] = {
            "schema_version": _SNAPSHOT_SCHEMA_VERSION,
            "version": self._version,
            "options": {
                "group_by_subject": self._group_by_subject,
                "sort_by_sent_date": self._sort_by_sent_date,
            },
            "records": records,
        }
        _bounded_snapshot_json_size(snapshot, self._max_snapshot_bytes)
        return snapshot

    @classmethod
    def restore(
        cls,
        snapshot: Mapping[str, object],
        *,
        max_snapshot_records: int = _DEFAULT_MAX_SNAPSHOT_RECORDS,
        max_snapshot_bytes: int = _DEFAULT_MAX_SNAPSHOT_BYTES,
    ) -> IncrementalThreadIndex:
        """Restore strict schema-version-1 state and rebuild all derived indexes."""
        max_records = _validated_positive_limit(
            max_snapshot_records,
            "max_snapshot_records",
        )
        max_bytes = _validated_positive_limit(
            max_snapshot_bytes,
            "max_snapshot_bytes",
        )
        snapshot_object = _required_plain_object(
            snapshot,
            {"schema_version", "version", "options", "records"},
            "snapshot",
        )
        raw_options = snapshot_object["options"]
        if not isinstance(raw_options, Mapping):
            raise IncrementalThreadError("snapshot options must be a mapping")
        options = _required_plain_object(
            raw_options,
            {"group_by_subject", "sort_by_sent_date"},
            "option",
        )
        encoded_records = snapshot_object["records"]
        if not isinstance(encoded_records, list):
            raise IncrementalThreadError("snapshot records must be a list")
        if type(encoded_records) is not list:
            raise IncrementalThreadError(
                "snapshot must contain only plain JSON containers and scalar values"
            )
        if len(encoded_records) > max_records:
            raise IncrementalThreadError("snapshot exceeds max_snapshot_records")
        _require_plain_json_containers(
            snapshot_object,
            maximum_nodes=max_bytes,
        )
        _bounded_snapshot_json_size(snapshot_object, max_bytes)
        schema_version = snapshot_object["schema_version"]
        if (
            isinstance(schema_version, bool)
            or not isinstance(schema_version, int)
            or schema_version != _SNAPSHOT_SCHEMA_VERSION
        ):
            raise IncrementalThreadError("unsupported snapshot schema_version")
        version = _validated_nonnegative_integer(
            snapshot_object["version"],
            "version",
        )
        group_by_subject = options["group_by_subject"]
        sort_by_sent_date = options["sort_by_sent_date"]
        if not isinstance(group_by_subject, bool):
            raise IncrementalThreadError("group_by_subject must be a boolean")
        if not isinstance(sort_by_sent_date, bool):
            raise IncrementalThreadError("sort_by_sent_date must be a boolean")
        records: list[IndexedMessage] = []
        seen_keys: set[str] = set()
        record_fields = {"message_key", "email_id", "thread_id", "message"}
        message_fields = {
            "message_id",
            "in_reply_to",
            "references",
            "subject",
            "sent_date",
            "internal_date",
            "sequence_number",
            "uid",
        }
        for encoded_record in encoded_records:
            encoded_record = _required_plain_object(
                encoded_record,
                record_fields,
                "record",
            )
            key = _validated_message_key(encoded_record["message_key"])
            if key in seen_keys:
                raise IncrementalThreadError(f"duplicate message_key in snapshot: {key}")
            seen_keys.add(key)
            encoded_message = encoded_record["message"]
            encoded_message = _required_plain_object(
                encoded_message,
                message_fields,
                "message",
            )
            in_reply_to = encoded_message["in_reply_to"]
            references = encoded_message["references"]
            if not isinstance(in_reply_to, list) or not all(
                isinstance(value, str) for value in in_reply_to
            ):
                raise IncrementalThreadError("in_reply_to must be a list of strings")
            if not isinstance(references, list) or not all(
                isinstance(value, str) for value in references
            ):
                raise IncrementalThreadError("references must be a list of strings")
            message = Message(
                message_id=_validated_optional_text(
                    encoded_message["message_id"],
                    "message_id",
                ),
                in_reply_to=tuple(in_reply_to),
                references=tuple(references),
                subject=_validated_optional_text(
                    encoded_message["subject"],
                    "subject",
                ),
                payload=None,
                sent_date=_decoded_date(encoded_message["sent_date"], "sent_date"),
                internal_date=_decoded_date(
                    encoded_message["internal_date"],
                    "internal_date",
                ),
                sequence_number=_validated_optional_number(
                    encoded_message["sequence_number"],
                    "sequence_number",
                ),
                uid=_validated_optional_number(
                    encoded_message["uid"],
                    "uid",
                    maximum=_MAX_IMAP_NUMBER,
                ),
            )
            records.append(
                IndexedMessage(
                    message_key=key,
                    message=message,
                    email_id=_validated_external_id(
                        encoded_record["email_id"],
                        "email_id",
                    ),
                    thread_id=_validated_external_id(
                        encoded_record["thread_id"],
                        "thread_id",
                    ),
                )
            )

        index = cls(
            group_by_subject=group_by_subject,
            sort_by_sent_date=sort_by_sent_date,
            max_snapshot_records=max_records,
            max_snapshot_bytes=max_bytes,
        )
        if records:
            index.apply(
                MailboxChangeSet(expected_version=0, additions=tuple(records))
            )
        index._version = version
        return index
