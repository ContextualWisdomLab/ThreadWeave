"""The :class:`Container` node used to assemble JWZ thread trees.

A ``Container`` wraps an optional message and holds parent/children links. Empty
containers (``message is None``) are placeholders for messages referenced but
not yet seen (or pruned away). All traversal is **loop-safe**: even if a
malformed reference graph produces a cycle, iteration terminates.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

__all__ = ["Container"]


@dataclass
class Container:
    """A node in a thread tree.

    Attributes:
        message: The wrapped message, or ``None`` for an empty placeholder.
        parent: The parent container, or ``None`` for a root.
        children: Direct child containers, in insertion order.
    """

    message: Any | None = None
    parent: Container | None = None
    children: list[Container] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        """Whether this container holds no message (a placeholder node)."""
        return self.message is None

    def has_descendant(self, other: Container) -> bool:
        """Return whether ``other`` is this container or one of its descendants.

        Used for loop checks before linking. Loop-safe: visits each node once.
        """
        seen: set[int] = set()
        stack: list[Container] = [self]
        while stack:
            node = stack.pop()
            if id(node) in seen:
                continue
            seen.add(id(node))
            if node is other:
                return True
            stack.extend(node.children)
        return False

    def add_child(self, child: Container) -> None:
        """Attach ``child`` under this container, re-parenting it if needed.

        No-op when the link would be a self-loop or when ``child`` is already an
        ancestor of this container (which would create a cycle).
        """
        if child is self or child.has_descendant(self):
            return
        if child.parent is not None:
            try:
                child.parent.children.remove(child)
            except ValueError:
                pass
        child.parent = self
        self.children.append(child)

    def iter_descendants(self) -> Iterator[Container]:
        """Yield every descendant (depth-first). Loop-safe; each node once."""
        seen: set[int] = set()
        stack: list[Container] = list(self.children)
        while stack:
            node = stack.pop()
            if id(node) in seen:
                continue
            seen.add(id(node))
            yield node
            stack.extend(node.children)
