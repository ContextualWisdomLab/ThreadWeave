"""The canonical JWZ message-threading algorithm.

This is a fresh, faithful implementation of Jamie Zawinski's threading
algorithm (https://www.jwz.org/doc/threading.html): build an id-table of
containers, link ``References`` chains without creating loops or overriding good
existing parents, gather the root set, prune empty containers, and optionally
group the root set by base subject.

The RFC 5322 header primitives it consumes live in :mod:`threadweave.headers`.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from threadweave.container import Container
from threadweave.headers import extract_reference_ids, normalize_message_id
from threadweave.subject import is_reply_subject, normalize_subject

__all__ = ["Message", "thread_messages"]


@dataclass
class Message:
    """An input message for :func:`thread_messages`.

    Attributes:
        message_id: This message's ``Message-ID`` (brackets optional).
        in_reply_to: The raw ``In-Reply-To`` header or a sequence of message
            identifiers. Used only when ``references`` is empty.
        references: The raw ``References`` header or its message identifiers,
            oldest first. Angle brackets and duplicate IDs are normalized away.
        subject: The ``Subject`` header, used for optional subject grouping.
        payload: Arbitrary caller-supplied data carried through untouched.
    """

    message_id: str | None = None
    in_reply_to: str | Sequence[str] | None = None
    references: str | Sequence[str] = field(default_factory=list)
    subject: str | None = None
    payload: Any = None


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
    """Normalized, de-duplicated reference chain for ``message``.

    Falls back to ``In-Reply-To`` when ``References`` is absent, per JWZ. Both
    fields may be supplied as raw RFC 5322 header strings containing multiple
    message identifiers or as already-split sequences.
    """
    references = _reference_ids(message.references)
    return references or _reference_ids(message.in_reply_to)


def _subject_of(container: Container) -> str | None:
    """Best-effort subject for a container: its own, else its first child's.

    JWZ step 5.B: an empty container takes the subject of its *first* child
    message. Implemented as a first-child-first DFS (iterative + id()-guarded, so
    it is loop-safe and never recurses on deep trees).
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

    Mirrors JWZ step 1.B: skip when ``child`` already has a parent, and skip any
    link that would introduce a cycle.
    """
    if child.parent is not None:
        return
    if parent is child or child.has_descendant(parent):
        return
    child.parent = parent
    parent.children.append(child)


def _set_parent(child: Container, parent: Container) -> None:
    """JWZ step 1.C: (re)parent ``child`` to ``parent``, loop-safely.

    A definitive parent from the message's own ``References`` overrides a parent
    that was only presumed from another message's chain — unless doing so would
    create a loop.
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
    """JWZ step 4: prune empty containers under ``holder``.

    ``holder`` is a synthetic node whose ``children`` are the root set; an empty
    container with more than one child at that top level is preserved as a
    grouping root. Implemented iteratively (no recursion) so it stays safe on
    very deep trees such as long linear reply chains.
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


def _group_by_subject(root_set: list[Container]) -> list[Container]:
    """JWZ step 5: merge root-set threads that share a base subject."""
    subject_table: dict[str, Container] = {}

    for container in root_set:
        base = normalize_subject(_subject_of(container)).casefold()
        if not base:
            continue
        existing = subject_table.get(base)
        if existing is None:
            subject_table[base] = container
            continue
        replace = (existing.message is None and container.message is not None) or (
            is_reply_subject(_subject_of(existing))
            and not is_reply_subject(_subject_of(container))
        )
        if replace:
            subject_table[base] = container

    created: list[Container] = []
    for container in root_set:
        base = normalize_subject(_subject_of(container)).casefold()
        if not base:
            continue
        owner = subject_table.get(base)
        if owner is None or owner is container:
            continue

        # The first pass guarantees that an owner is concrete whenever any
        # concrete container exists for the base subject, and non-reply whenever
        # any non-reply exists. Only the cases below can therefore remain.
        if owner.message is None and container.message is None:
            for grandchild in list(container.children):
                owner.add_child(grandchild)
        elif container.message is None:
            container.add_child(owner)
            subject_table[base] = container
        elif is_reply_subject(_subject_of(container)) and not is_reply_subject(
            _subject_of(owner)
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


def thread_messages(
    messages: Iterable[Message], *, group_by_subject: bool = False
) -> list[Container]:
    """Thread ``messages`` into conversation trees via the JWZ algorithm.

    Args:
        messages: The messages to thread, consumed once in iteration order.
        group_by_subject: When true, also merge distinct root threads that share
            a base subject (a heuristic; off by default).

    Returns:
        The root :class:`Container` objects, one per thread, in a deterministic
        order derived from first appearance in ``messages``.
    """
    id_table: dict[str, Container] = {}
    container_order: list[Container] = []

    def new_container(message: Message | None = None) -> Container:
        container = Container(message=message)
        container_order.append(container)
        return container

    def container_for(message_id: str) -> Container:
        container = id_table.get(message_id)
        if container is None:
            container = new_container()
            id_table[message_id] = container
        return container

    for message in messages:
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

        references = _effective_references(message)

        previous: Container | None = None
        for ref_id in references:
            ref_container = container_for(ref_id)
            if previous is not None:
                _link(previous, ref_container)
            previous = ref_container

        if previous is not None and previous is not this:
            _set_parent(this, previous)

    root_set: list[Container] = [
        container for container in container_order if container.parent is None
    ]

    holder = Container()
    holder.children = root_set
    _prune(holder)
    root_set = holder.children

    if group_by_subject:
        root_set = _group_by_subject(root_set)

    return root_set
