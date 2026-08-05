"""Incremental, identity-aware mailbox threading over the batch RFC engine.

The batch :func:`threadweave.thread_messages` function remains the correctness
oracle.  This module adds an atomic state boundary that indexes caller-owned
message keys, recomputes only affected connectivity components, reports explicit
thread merge/split transitions, and snapshots JSON-safe metadata without caller
payloads.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from _thread import RLock
from typing import Literal

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


def _writable_token_bucket(
    token: str,
    keys_by_token: dict[str, set[str]],
    copied_tokens: set[str],
) -> set[str]:
    """Return one copy-on-write reverse bucket owned by the transaction."""
    if token not in copied_tokens:
        keys_by_token[token] = set(keys_by_token.get(token, set()))
        copied_tokens.add(token)
    elif token not in keys_by_token:
        keys_by_token[token] = set()
    return keys_by_token[token]


def _remove_key_from_buckets(
    key: str,
    tokens_by_key: dict[str, frozenset[str]],
    keys_by_token: dict[str, set[str]],
    copied_tokens: set[str],
) -> frozenset[str]:
    """Remove one key from transaction-owned token buckets."""
    old_tokens = tokens_by_key.pop(key, frozenset())
    for token in old_tokens:
        bucket = _writable_token_bucket(token, keys_by_token, copied_tokens)
        bucket.discard(key)
        if not bucket:
            del keys_by_token[token]
    return old_tokens


def _add_key_to_buckets(
    key: str,
    tokens: frozenset[str],
    tokens_by_key: dict[str, frozenset[str]],
    keys_by_token: dict[str, set[str]],
    copied_tokens: set[str],
) -> None:
    """Insert one key through transaction-owned copy-on-write buckets."""
    tokens_by_key[key] = tokens
    for token in tokens:
        _writable_token_bucket(token, keys_by_token, copied_tokens).add(key)


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


def _validate_external_identities(records: Mapping[str, IndexedMessage]) -> None:
    """Enforce RFC 8474 EMAILID/THREADID consistency and namespace separation."""
    thread_id_by_email_id: dict[str, str | None] = {}
    email_ids: set[str] = set()
    thread_ids: set[str] = set()
    for record in records.values():
        email_id = record.email_id
        thread_id = record.thread_id
        if email_id is not None:
            email_ids.add(email_id)
            if email_id not in thread_id_by_email_id:
                thread_id_by_email_id[email_id] = thread_id
            elif thread_id_by_email_id[email_id] != thread_id:
                raise ExternalIdentityError(
                    f"messages with EMAILID {email_id!r} must expose the same THREADID"
                )
        if thread_id is not None:
            thread_ids.add(thread_id)
    reused_values = email_ids & thread_ids
    if reused_values:
        raise ExternalIdentityError(
            "EMAILID and THREADID must use disjoint ObjectID values: "
            f"{sorted(reused_values)!r}"
        )


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


def _snapshot_json_bytes(value: object) -> bytes:
    """Serialize a snapshot canonically or raise a bounded domain error."""
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as error:
        raise IncrementalThreadError("snapshot must contain only JSON-safe values") from error
    return encoded.encode("utf-8")


def _required_fields(value: Mapping[str, object], expected: set[str], name: str) -> None:
    """Require an exact untrusted mapping field set."""
    if set(value) != expected:
        raise IncrementalThreadError(f"{name} fields do not match the schema")


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
        existing_keys = set(self._records)
        already_present = addition_keys & existing_keys
        missing_replacements = replacement_keys - existing_keys
        missing_removals = removal_keys - existing_keys
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

        records = dict(self._records)
        positions = dict(self._positions)
        tokens_by_key = dict(self._tokens_by_key)
        keys_by_token = dict(self._keys_by_token)
        copied_tokens: set[str] = set()
        next_position = self._next_position
        changed_existing_keys = replacement_keys | removal_keys
        candidate_seeds: set[str] = set()
        touched_tokens: set[str] = set()

        for key in changed_existing_keys:
            component_id = self._component_by_key.get(key)
            if component_id is not None:
                candidate_seeds.update(self._keys_by_component[component_id])
            touched_tokens.update(
                _remove_key_from_buckets(
                    key,
                    tokens_by_key,
                    keys_by_token,
                    copied_tokens,
                )
            )

        for key in removal_keys:
            records.pop(key)
            positions.pop(key)
        for replacement in copied_replacements:
            records[replacement.message_key] = replacement
            tokens = _connectivity_tokens(
                replacement,
                group_by_subject=self._group_by_subject,
            )
            touched_tokens.update(tokens)
            _add_key_to_buckets(
                replacement.message_key,
                tokens,
                tokens_by_key,
                keys_by_token,
                copied_tokens,
            )
            candidate_seeds.add(replacement.message_key)
        for addition in copied_additions:
            records[addition.message_key] = addition
            positions[addition.message_key] = next_position
            next_position += 1
            tokens = _connectivity_tokens(
                addition,
                group_by_subject=self._group_by_subject,
            )
            touched_tokens.update(tokens)
            _add_key_to_buckets(
                addition.message_key,
                tokens,
                tokens_by_key,
                keys_by_token,
                copied_tokens,
            )
            candidate_seeds.add(addition.message_key)

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

        _validate_external_identities(records)
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
        old_candidate_keys = set(candidate_seeds)
        candidate_keys = current_candidate_keys | old_candidate_keys

        component_by_key = {
            key: component_id
            for key, component_id in self._component_by_key.items()
            if key not in candidate_keys and key in records
        }
        unaffected_component_ids = set(component_by_key.values())
        keys_by_component = {
            component_id: keys
            for component_id, keys in self._keys_by_component.items()
            if component_id in unaffected_component_ids
        }
        for keys in _partition_components(
            current_candidate_keys,
            positions,
            tokens_by_key,
            keys_by_token,
        ):
            component_id = keys[0]
            keys_by_component[component_id] = keys
            for key in keys:
                component_by_key[key] = component_id

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

        self._records = records
        self._positions = positions
        self._next_position = next_position
        self._tokens_by_key = tokens_by_key
        self._keys_by_token = keys_by_token
        self._component_by_key = component_by_key
        self._keys_by_component = keys_by_component
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
        if len(_snapshot_json_bytes(snapshot)) > self._max_snapshot_bytes:
            raise IncrementalThreadError("snapshot exceeds max_snapshot_bytes")
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
        if not isinstance(snapshot, Mapping):
            raise IncrementalThreadError("snapshot must be a mapping")
        if len(_snapshot_json_bytes(snapshot)) > max_bytes:
            raise IncrementalThreadError("snapshot exceeds max_snapshot_bytes")
        _required_fields(
            snapshot,
            {"schema_version", "version", "options", "records"},
            "snapshot",
        )
        if snapshot["schema_version"] != _SNAPSHOT_SCHEMA_VERSION:
            raise IncrementalThreadError("unsupported snapshot schema_version")
        version = _validated_nonnegative_integer(snapshot["version"], "version")
        options = snapshot["options"]
        if not isinstance(options, Mapping):
            raise IncrementalThreadError("snapshot options must be a mapping")
        _required_fields(
            options,
            {"group_by_subject", "sort_by_sent_date"},
            "option",
        )
        group_by_subject = options["group_by_subject"]
        sort_by_sent_date = options["sort_by_sent_date"]
        if not isinstance(group_by_subject, bool):
            raise IncrementalThreadError("group_by_subject must be a boolean")
        if not isinstance(sort_by_sent_date, bool):
            raise IncrementalThreadError("sort_by_sent_date must be a boolean")
        encoded_records = snapshot["records"]
        if not isinstance(encoded_records, list):
            raise IncrementalThreadError("snapshot records must be a list")
        if len(encoded_records) > max_records:
            raise IncrementalThreadError("snapshot exceeds max_snapshot_records")

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
            if not isinstance(encoded_record, Mapping):
                raise IncrementalThreadError("snapshot record must be a mapping")
            _required_fields(encoded_record, record_fields, "record")
            key = _validated_message_key(encoded_record["message_key"])
            if key in seen_keys:
                raise IncrementalThreadError(f"duplicate message_key in snapshot: {key}")
            seen_keys.add(key)
            encoded_message = encoded_record["message"]
            if not isinstance(encoded_message, Mapping):
                raise IncrementalThreadError("snapshot message must be a mapping")
            _required_fields(encoded_message, message_fields, "message")
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
