"""The canonical JWZ/RFC 5256 message-threading algorithm.

This module builds reference-linked container trees, prunes missing-message
placeholders, optionally groups disconnected roots by standardized base subject,
and can apply the sent-date ordering required by RFC 5256. All graph traversals
are iterative and identity-guarded so malformed or hostile cycles terminate.

The RFC 5322 identification-field primitives it consumes live in
:mod:`threadweave.headers`; subject-table keys use RFC 5051
``i;unicode-casemap`` preparation, and sent dates use
:func:`threadweave.dates.normalize_sent_date`.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from threadweave.collation import unicode_casemap_key
from threadweave.container import Container
from threadweave.dates import DateValue, normalize_sent_date
from threadweave.headers import extract_reference_ids, normalize_message_id
from threadweave.subject import is_reply_or_forward_subject, normalize_subject

__all__ = ["Message", "thread_messages"]

_SortKey = tuple[datetime, int, int]
_EARLIEST_SORT_KEY: _SortKey = (normalize_sent_date(None), 0, 0)


@dataclass
class Message:
    """An input message for :func:`thread_messages`.

    Attributes:
        message_id: This message's ``Message-ID`` (brackets optional).
        in_reply_to: The raw ``In-Reply-To`` header or a sequence of message
            identifiers. When ``references`` is empty, only its first valid
            identifier is used as the parent, as required by RFC 5256.
        references: The raw ``References`` header or its message identifiers,
            oldest first. Angle brackets and duplicate IDs are normalized away.
        subject: The ``Subject`` header, used for optional subject grouping.
        payload: Arbitrary caller-supplied data carried through untouched.
        sent_date: The RFC 5322 ``Date`` header or a :class:`datetime` used for
            optional RFC 5256 sibling ordering.
        internal_date: Mailbox ``INTERNALDATE`` fallback when ``sent_date`` is
            absent or unusable.
        sequence_number: Positive mailbox sequence number used to break exact
            sent-date ties. Input position is used when omitted.
    """

    message_id: str | None = None
    in_reply_to: str | Sequence[str] | None = None
    references: str | Sequence[str] = field(default_factory=list)
    subject: str | None = None
    payload: Any = None
    sent_date: DateValue = None
    internal_date: DateValue = None
    sequence_number: int | None = None


def _reference_ids(value: str | Sequence[str] | None) -> list[str]:
    """Parse one raw identification header or a sequence of header values."""
    if value is None:
        return []

    values = [value] if isinstance(value, str) else value
    references: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        for reference in extract_reference_ids(str(raw_value)):
            if reference not in seen:
                seen.add(reference)
                references.append(reference)
    return references


def _effective_references(message: Message) -> list[str]:
    """Return the normalized ancestry references used for ``message``.

    A valid ``References`` chain is used in full. When that field is absent or
    contains no valid identifiers, RFC 5256 requires the first valid identifier
    in ``In-Reply-To`` to be used as the only reference. Limiting the fallback
    prevents trailing addresses or identifiers from becoming fabricated ancestry.
    """
    references = _reference_ids(message.references)
    if references:
        return references
    return _reference_ids(message.in_reply_to)[:1]


def _subject_of(container: Container) -> str | None:
    """Return a container's subject, falling back to its first child message.

    RFC 5256 gives a dummy container the subject of its first child. This
    first-child-first traversal is iterative and visits each object identity once.
    """
    stack: list[Container] = [container]
    seen: set[int] = set()
    while stack:
        node = stack.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        if node.message is not None:
            return node.message.subject
        stack.extend(reversed(node.children))
    return None


def _link(parent: Container, child: Container) -> None:
    """Link ``child`` under ``parent`` if it neither loops nor steals a parent.

    Presumed edges created while walking another message's reference chain never
    replace an existing parent. Self-links and descendant-to-ancestor links are
    discarded because either would create a cycle.
    """
    if child.parent is not None:
        return
    if parent is child or child.has_descendant(parent):
        return
    child.parent = parent
    parent.children.append(child)


def _set_parent(child: Container, parent: Container) -> None:
    """Replace a presumed parent with the message's definitive parent safely.

    The current message's own effective reference chain is authoritative, but it
    may reparent the container only when the new edge remains acyclic. Inconsistent
    historical parent lists are tolerated and repaired.
    """
    if parent is child or child.has_descendant(parent):
        return
    if child.parent is not None:
        try:
            child.parent.children.remove(child)
        except ValueError:
            pass
    child.parent = parent
    parent.children.append(child)


def _prune(holder: Container) -> None:
    """Prune RFC 5256 dummy containers iteratively under ``holder``.

    Empty leaves are removed. Empty internal containers are splice-promoted,
    except that a multi-child dummy at the root remains as the grouping node for
    a missing thread root. Descendants are processed before ancestors.
    """
    order: list[Container] = []
    seen: set[int] = set()
    stack: list[Container] = [holder]
    while stack:
        node = stack.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        order.append(node)
        stack.extend(node.children)

    for node in reversed(order):
        is_root = node is holder
        kept: list[Container] = []
        for child in node.children:
            if child.message is None:
                if not child.children:
                    continue
                if is_root and len(child.children) > 1:
                    child.parent = None
                    kept.append(child)
                else:
                    for grandchild in child.children:
                        grandchild.parent = None if is_root else node
                        kept.append(grandchild)
            else:
                child.parent = None if is_root else node
                kept.append(child)
        node.children = kept


def _subject_key(container: Container) -> str:
    """Return the RFC 5256/5051 subject-table key for ``container``."""
    return unicode_casemap_key(normalize_subject(_subject_of(container)))


def _group_by_subject(root_set: list[Container]) -> list[Container]:
    """Merge root threads that share an RFC 5256 base subject.

    Dummy owners are retained whenever present. Otherwise a concrete original is
    preferred over a reply or forward, and the remaining roots are attached or
    wrapped exactly once while preserving deterministic first appearance.
    """
    subject_table: dict[str, Container] = {}

    for container in root_set:
        base = _subject_key(container)
        if not base:
            continue
        existing = subject_table.get(base)
        if existing is None:
            subject_table[base] = container
            continue
        replace = existing.message is not None and (
            container.message is None
            or (
                is_reply_or_forward_subject(_subject_of(existing))
                and not is_reply_or_forward_subject(_subject_of(container))
            )
        )
        if replace:
            subject_table[base] = container

    created: list[Container] = []
    for container in root_set:
        base = _subject_key(container)
        if not base:
            continue
        owner = subject_table.get(base)
        if owner is None or owner is container:
            continue

        if owner.message is None and container.message is None:
            for grandchild in list(container.children):
                owner.add_child(grandchild)
        elif owner.message is None:
            owner.add_child(container)
        elif (
            is_reply_or_forward_subject(_subject_of(container))
            and not is_reply_or_forward_subject(_subject_of(owner))
        ):
            owner.add_child(container)
        else:
            merged = Container()
            merged.add_child(owner)
            merged.add_child(container)
            subject_table[base] = merged
            created.append(merged)

    final: list[Container] = []
    seen: set[int] = set()
    for container in list(root_set) + created:
        root = container
        ancestors: set[int] = set()
        while root.parent is not None and id(root) not in ancestors:
            ancestors.add(id(root))
            root = root.parent

        if id(root) in seen:
            continue
        if root.message is None and not root.children:
            continue
        seen.add(id(root))
        final.append(root)
    return final


def _validated_sequence_number(message: Message, input_position: int) -> int:
    """Return a positive explicit sequence number or the one-based input position."""
    sequence_number = message.sequence_number
    if sequence_number is None:
        return input_position
    if (
        isinstance(sequence_number, bool)
        or not isinstance(sequence_number, int)
        or sequence_number <= 0
    ):
        raise ValueError("sequence_number must be a positive integer")
    return sequence_number


def _container_sort_key(
    container: Container,
    sort_keys: dict[int, _SortKey],
) -> _SortKey:
    """Return a concrete key or a loop-safe dummy key from its first child.

    RFC 5256 assigns a dummy container the sent date of its first child after that
    child set has been sorted. Malformed first-child cycles terminate at the
    earliest fallback key instead of hanging.
    """
    current = container
    seen: set[int] = set()
    while id(current) not in seen:
        seen.add(id(current))
        concrete_key = sort_keys.get(id(current))
        if concrete_key is not None:
            return concrete_key
        if not current.children:
            break
        current = current.children[0]
    return _EARLIEST_SORT_KEY


def _sort_top_level(
    root_set: list[Container],
    sort_keys: dict[int, _SortKey],
) -> None:
    """Apply RFC 5256 step 4 before subject-table construction.

    Children of every top-level dummy are sorted first; the resulting first child
    supplies the dummy's key when the root set itself is sorted.
    """
    for root in root_set:
        if root.message is None:
            root.children.sort(key=lambda child: _container_sort_key(child, sort_keys))
    root_set.sort(key=lambda root: _container_sort_key(root, sort_keys))


def _sort_all_siblings(
    root_set: list[Container],
    sort_keys: dict[int, _SortKey],
) -> list[Container]:
    """Apply RFC 5256 step 6, sorting descendants before ancestors.

    A synthetic holder makes the final root set another sibling set. Reverse
    pre-order yields the required bottom-up processing without recursion, while
    an identity set prevents malformed cycles from being revisited.
    """
    holder = Container(children=root_set)
    order: list[Container] = []
    seen: set[int] = set()
    stack: list[Container] = [holder]
    while stack:
        node = stack.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        order.append(node)
        stack.extend(node.children)

    for node in reversed(order):
        node.children.sort(key=lambda child: _container_sort_key(child, sort_keys))
    return holder.children


def thread_messages(
    messages: Iterable[Message],
    *,
    group_by_subject: bool = False,
    sort_by_sent_date: bool = False,
) -> list[Container]:
    """Thread ``messages`` into deterministic conversation trees.

    Args:
        messages: Messages consumed once in iteration order.
        group_by_subject: Merge disconnected roots sharing a standardized base
            subject. This caller-selected heuristic is disabled by default.
        sort_by_sent_date: Apply RFC 5256 steps 4 and 6. When disabled, the
            existing first-appearance and child-insertion ordering is preserved.

    Returns:
        Root :class:`Container` objects in deterministic order.

    Raises:
        ValueError: An effective sequence number is invalid or duplicated.
        TypeError: Date metadata has an unsupported runtime type.
    """
    id_table: dict[str, Container] = {}
    container_order: list[Container] = []
    sort_keys: dict[int, _SortKey] = {}
    used_sequence_numbers: set[int] = set()

    def new_container(message: Message | None = None) -> Container:
        """Create and remember a container in first-creation order."""
        container = Container(message=message)
        container_order.append(container)
        return container

    def container_for(message_id: str) -> Container:
        """Return the existing ID container or create a dummy placeholder."""
        container = id_table.get(message_id)
        if container is None:
            container = new_container()
            id_table[message_id] = container
        return container

    for input_position, message in enumerate(messages, start=1):
        message_id = normalize_message_id(message.message_id)

        if message_id is None:
            this = new_container(message)
        else:
            existing = id_table.get(message_id)
            if existing is not None and existing.message is None:
                existing.message = message
                this = existing
            elif existing is not None:
                this = new_container(message)
            else:
                this = new_container(message)
                id_table[message_id] = this

        if sort_by_sent_date:
            sequence_number = _validated_sequence_number(message, input_position)
            if sequence_number in used_sequence_numbers:
                raise ValueError(f"duplicate sequence number: {sequence_number}")
            used_sequence_numbers.add(sequence_number)
            sort_keys[id(this)] = (
                normalize_sent_date(message.sent_date, message.internal_date),
                sequence_number,
                input_position,
            )

        previous: Container | None = None
        for ref_id in _effective_references(message):
            ref_container = container_for(ref_id)
            if previous is not None:
                _link(previous, ref_container)
            previous = ref_container

        if previous is not None and previous is not this:
            _set_parent(this, previous)

    root_set: list[Container] = [
        container for container in container_order if container.parent is None
    ]

    holder = Container(children=root_set)
    _prune(holder)
    root_set = holder.children

    if sort_by_sent_date:
        _sort_top_level(root_set, sort_keys)
    if group_by_subject:
        root_set = _group_by_subject(root_set)
    if sort_by_sent_date:
        root_set = _sort_all_siblings(root_set, sort_keys)

    return root_set
