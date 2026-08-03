"""The canonical JWZ message-threading algorithm.

This is a fresh, faithful implementation of Jamie Zawinski's threading
algorithm (https://www.jwz.org/doc/threading.html): build an id-table of
containers, link ``References`` chains without creating loops or overriding good
existing parents, gather the root set, prune empty containers, and optionally
group the root set by base subject.

The RFC 5322 header primitives it consumes live in :mod:`threadweave.headers`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from threadweave.container import Container
from threadweave.headers import normalize_message_id
from threadweave.subject import is_reply_subject, normalize_subject

__all__ = ["Message", "thread_messages"]


@dataclass
class Message:
    """An input message for :func:`thread_messages`.

    Attributes:
        message_id: This message's ``Message-ID`` (brackets optional).
        in_reply_to: The ``In-Reply-To`` header (used only when ``references``
            is empty), brackets optional.
        references: The ``References`` chain, oldest first. Each entry may carry
            angle brackets; they are normalized away.
        subject: The ``Subject`` header, used for optional subject grouping.
        payload: Arbitrary caller-supplied data carried through untouched.
    """

    message_id: str | None = None
    in_reply_to: str | None = None
    references: list[str] = field(default_factory=list)
    subject: str | None = None
    payload: Any = None


def _effective_references(message: Message) -> list[str]:
    """Normalized, de-duplicated reference chain for ``message``.

    Falls back to ``In-Reply-To`` when ``References`` is absent, per JWZ.
    """
    refs: list[str] = []
    seen: set[str] = set()
    for ref in message.references or []:
        normalized = normalize_message_id(ref)
        if normalized and normalized not in seen:
            seen.add(normalized)
            refs.append(normalized)
    if not refs:
        fallback = normalize_message_id(message.in_reply_to)
        if fallback:
            refs.append(fallback)
    return refs


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
        # Push in reverse so the first child is examined first.
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
    # Reverse pre-order gives every node AFTER all of its descendants, i.e. the
    # post-order property the splice logic needs; the id()-visited set keeps it
    # loop-safe even against a malformed graph.
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
                    # Empty leaf: nuke it.
                    continue
                if is_root and len(child.children) > 1:
                    # Empty root with several children: keep as a grouping root.
                    child.parent = None
                    kept.append(child)
                else:
                    # Splice the already-pruned children up into this level.
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

    # 5.B — choose one owner per base subject, preferring non-empty non-replies.
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

    # 5.C — merge every other root into (or with) its base-subject owner.
    created: list[Container] = []
    for container in root_set:
        base = normalize_subject(_subject_of(container)).casefold()
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
        elif container.message is None:
            container.add_child(owner)
            subject_table[base] = container
        elif is_reply_subject(_subject_of(container)) and not is_reply_subject(
            _subject_of(owner)
        ):
            owner.add_child(container)
        elif is_reply_subject(_subject_of(owner)) and not is_reply_subject(
            _subject_of(container)
        ):
            container.add_child(owner)
            subject_table[base] = container
        else:
            merged = Container()
            merged.add_child(owner)
            merged.add_child(container)
            subject_table[base] = merged
            created.append(merged)

    # Final roots: resolve the top-level parent from each original root so a
    # newly-created synthetic root keeps the position of its first appearance.
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
    messages: list[Message], *, group_by_subject: bool = False
) -> list[Container]:
    """Thread ``messages`` into conversation trees via the JWZ algorithm.

    Args:
        messages: The messages to thread.
        group_by_subject: When true, also merge distinct root threads that share
            a base subject (a heuristic; off by default).

    Returns:
        The root :class:`Container` objects, one per thread, in a deterministic
        order derived from first appearance in ``messages``.
    """
    id_table: dict[str, Container] = {}
    # Containers for messages without a usable / unique Message-ID: they are
    # never referenced, so they are always their own roots.
    standalone: list[Container] = []

    def container_for(message_id: str) -> Container:
        container = id_table.get(message_id)
        if container is None:
            container = Container()
            id_table[message_id] = container
        return container

    # Step 1 — build the id-table and link reference chains.
    for message in messages:
        message_id = normalize_message_id(message.message_id)

        # 1.A — find or create this message's container.
        if message_id is None:
            this = Container(message=message)
            standalone.append(this)
        else:
            existing = id_table.get(message_id)
            if existing is not None and existing.message is None:
                existing.message = message
                this = existing
            elif existing is not None:
                # Duplicate Message-ID on a distinct message: keep it as its own
                # container so nothing collides destructively.
                this = Container(message=message)
                standalone.append(this)
            else:
                this = Container(message=message)
                id_table[message_id] = this

        references = _effective_references(message)

        # 1.B — link the referenced containers into a parent chain.
        previous: Container | None = None
        for ref_id in references:
            ref_container = container_for(ref_id)
            if previous is not None:
                _link(previous, ref_container)
            previous = ref_container

        # 1.C — the last reference is this message's definitive parent.
        if previous is not None and previous is not this:
            _set_parent(this, previous)

    # Step 2 — the root set is every parentless container.
    root_set: list[Container] = [c for c in id_table.values() if c.parent is None]
    root_set.extend(c for c in standalone if c.parent is None)

    # Step 3 — id_table is no longer needed.

    # Step 4 — prune empty containers.
    holder = Container()
    holder.children = root_set
    _prune(holder)
    root_set = holder.children

    # Step 5 — optional subject grouping.
    if group_by_subject:
        root_set = _group_by_subject(root_set)

    return root_set
