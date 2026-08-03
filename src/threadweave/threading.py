"""The canonical JWZ message-threading algorithm.

This is a fresh, faithful implementation of Jamie Zawinski's threading
algorithm (https://www.jwz.org/doc/threading.html), aligned with the
``REFERENCES`` algorithm standardized by RFC 5256: build an id-table of
containers, link ``References`` chains without creating loops or overriding good
existing parents, gather the root set, prune empty containers, and optionally
group the root set by base subject.

The RFC 5322 identification-field primitives it consumes live in
:mod:`threadweave.headers`; subject-table keys use RFC 5051
``i;unicode-casemap`` preparation.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from threadweave.collation import unicode_casemap_key
from threadweave.container import Container
from threadweave.headers import extract_reference_ids, normalize_message_id
from threadweave.subject import is_reply_or_forward_subject, normalize_subject

__all__ = ["Message", "thread_messages"]


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
    """Return the normalized ancestry references used for ``message``.

    A valid ``References`` chain is used in full. When that field is absent or
    contains no valid identifiers, RFC 5256 requires the first valid identifier
    in ``In-Reply-To`` to be used as the *only* reference. Limiting the fallback
    prevents addresses or additional identifiers found in malformed historical
    ``In-Reply-To`` fields from becoming a fabricated ancestry chain.
    """
    references = _reference_ids(message.references)
    if references:
        return references
    return _reference_ids(message.in_reply_to)[:1]


def _subject_of(container: Container) -> str | None:
    """Best-effort subject for a container: its own, else its first child's.

    RFC 5256 step 5.B: an empty container takes the subject of its *first* child
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

    Mirrors RFC 5256 step 1.A: skip when ``child`` already has a parent, and skip any
    link that would introduce a cycle.
    """
    if child.parent is not None:
        return
    if parent is child or child.has_descendant(parent):
        return
    child.parent = parent
    parent.children.append(child)


def _set_parent(child: Container, parent: Container) -> None:
    """RFC 5256 step 1.B: (re)parent ``child`` to ``parent``, loop-safely.

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
    """RFC 5256 step 3: prune empty containers under ``holder``.

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


def _subject_key(container: Container) -> str:
    """Return the RFC 5256/5051 subject-table key for ``container``."""
    return unicode_casemap_key(normalize_subject(_subject_of(container)))


def _group_by_subject(root_set: list[Container]) -> list[Container]:
    """RFC 5256 step 5: merge root threads that share a base subject."""
    subject_table: dict[str, Container] = {}

    # RFC 5256 5.B keeps a dummy owner whenever one exists. Otherwise it prefers
    # a non-reply/non-forward concrete owner over a reply/forward owner.
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


def thread_messages(
    messages: Iterable[Message], *, group_by_subject: bool = False
) -> list[Container]:
    """Thread ``messages`` into conversation trees via the JWZ/RFC 5256 algorithm.

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
