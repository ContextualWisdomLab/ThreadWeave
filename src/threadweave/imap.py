"""RFC 5256 IMAP ``THREAD`` response projection and serialization.

The threading core deliberately returns transport-neutral :class:`Container`
trees. This module projects those trees onto a caller-selected search result and
renders the exact RFC 5256 parenthesized response grammar without recursion.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Literal, TypeAlias

from threadweave.container import Container
from threadweave.threading import Message

IdentifierResolver: TypeAlias = (
    Literal["sequence_number", "uid"] | Callable[[Message], int]
)
MessageFilter: TypeAlias = Callable[[Message], bool]

__all__ = [
    "IdentifierResolver",
    "MessageFilter",
    "ThreadSerializationError",
    "serialize_thread_data",
    "serialize_thread_response",
]


class ThreadSerializationError(ValueError):
    """Raised when a container graph cannot form a valid THREAD response."""


@dataclass(eq=False, slots=True)
class _ResponseNode:
    """A projected response node; ``None`` identifies a top-level dummy root."""

    identifier: int | None
    children: list[_ResponseNode] = field(default_factory=list)


def _identifier_resolver(identifier: IdentifierResolver) -> Callable[[Message], int]:
    """Return a validated built-in or caller-supplied identifier resolver."""
    if identifier == "sequence_number":
        return lambda message: message.sequence_number  # type: ignore[return-value]
    if identifier == "uid":
        return lambda message: message.uid  # type: ignore[return-value]
    if callable(identifier):
        return identifier
    raise ValueError("identifier must be 'sequence_number', 'uid', or a callable")


def _validated_identifier(value: object, used: set[int]) -> int:
    """Validate one RFC ``nz-number`` and reject duplicate emitted values."""
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 0 < value < 4_294_967_296
    ):
        raise ThreadSerializationError(
            "message identifier must be a positive integer in the unsigned 32-bit range"
        )
    if value in used:
        raise ThreadSerializationError(f"duplicate identifier in THREAD response: {value}")
    used.add(value)
    return value


def _project_roots(
    roots: Iterable[Container],
    resolver: Callable[[Message], int],
    include: MessageFilter | None,
) -> list[_ResponseNode]:
    """Project matching messages into response nodes without mutating the source.

    Excluded or dummy internal nodes are splice-promoted. At the top level, two
    or more promoted branches retain their common missing/excluded ancestor as a
    synthetic dummy root, matching RFC 5256's ``((3)(5))`` representation.
    """
    state: dict[int, int] = {}
    projected: dict[int, list[_ResponseNode]] = {}
    emitted: set[int] = set()
    used_identifiers: set[int] = set()
    response_roots: list[_ResponseNode] = []

    for root in roots:
        if not isinstance(root, Container):
            raise TypeError("THREAD roots must be Container instances")
        root_identity = id(root)
        if state.get(root_identity) == 2:
            raise ThreadSerializationError("container appears in multiple positions")

        stack: list[tuple[Container, bool]] = [(root, False)]
        while stack:
            node, exiting = stack.pop()
            node_identity = id(node)

            if not exiting:
                node_state = state.get(node_identity, 0)
                if node_state == 1:
                    raise ThreadSerializationError("container graph contains a cycle")
                if node_state == 2:
                    raise ThreadSerializationError(
                        "container appears in multiple positions"
                    )
                state[node_identity] = 1
                stack.append((node, True))
                for child in reversed(node.children):
                    if not isinstance(child, Container):
                        raise TypeError("THREAD children must be Container instances")
                    stack.append((child, False))
                continue

            child_branches: list[_ResponseNode] = []
            for child in node.children:
                child_branches.extend(projected[id(child)])

            message = node.message
            if message is not None:
                if not isinstance(message, Message):
                    raise TypeError("THREAD containers must wrap threadweave.Message")
                selected = True if include is None else bool(include(message))
                if selected:
                    value = _validated_identifier(resolver(message), used_identifiers)
                    projected[node_identity] = [_ResponseNode(value, child_branches)]
                    emitted.add(node_identity)
                else:
                    projected[node_identity] = child_branches
            else:
                projected[node_identity] = child_branches
            state[node_identity] = 2

        branches = projected[root_identity]
        if root_identity in emitted:
            response_roots.append(branches[0])
        elif len(branches) == 1:
            response_roots.append(branches[0])
        elif len(branches) > 1:
            response_roots.append(_ResponseNode(None, branches))

    return response_roots


def _render_thread_list(root: _ResponseNode) -> str:
    """Render one RFC ``thread-list`` iteratively with compact canonical spacing."""
    output: list[str] = []
    stack: list[tuple[str, _ResponseNode | None]] = [("node", root)]

    while stack:
        event, node = stack.pop()
        if event == "close":
            output.append(")")
            continue
        assert node is not None

        if node.identifier is None:
            if len(node.children) < 2:
                raise ThreadSerializationError(
                    "a dummy THREAD root must contain at least two branches"
                )
            output.append("(")
            stack.append(("close", None))
            for child in reversed(node.children):
                stack.append(("node", child))
            continue

        output.append("(")
        current = node
        output.append(str(current.identifier))
        while len(current.children) == 1:
            current = current.children[0]
            if current.identifier is None:
                raise ThreadSerializationError(
                    "dummy containers are only valid at the top level"
                )
            output.append(" ")
            output.append(str(current.identifier))

        if current.children:
            output.append(" ")
            stack.append(("close", None))
            for child in reversed(current.children):
                stack.append(("node", child))
        else:
            output.append(")")

    return "".join(output)


def serialize_thread_data(
    roots: Iterable[Container],
    *,
    identifier: IdentifierResolver = "sequence_number",
    include: MessageFilter | None = None,
) -> str:
    """Return the RFC 5256 ``thread-data`` value for ``roots``.

    Args:
        roots: Thread roots, normally returned by :func:`thread_messages`.
        identifier: ``"sequence_number"`` for THREAD, ``"uid"`` for UID THREAD,
            or a callable returning another positive mailbox identifier.
        include: Optional search-result predicate. Excluded ancestors are omitted
            while their matching descendants retain their thread relationships.

    Returns:
        ``"THREAD"`` for no matching messages, otherwise ``"THREAD "`` followed
        by one or more compact RFC ``thread-list`` values.
    """
    if include is not None and not callable(include):
        raise TypeError("include must be callable or None")
    resolver = _identifier_resolver(identifier)
    response_roots = _project_roots(roots, resolver, include)
    if not response_roots:
        return "THREAD"
    return "THREAD " + "".join(_render_thread_list(root) for root in response_roots)


def serialize_thread_response(
    roots: Iterable[Container],
    *,
    identifier: IdentifierResolver = "sequence_number",
    include: MessageFilter | None = None,
    line_ending: str = "\r\n",
) -> str:
    """Return one untagged IMAP THREAD response line.

    ``line_ending`` is restricted to the protocol CRLF or an empty string for a
    caller that owns framing. This prevents response-splitting through arbitrary
    suffix injection.
    """
    if line_ending not in {"", "\r\n"}:
        raise ValueError("line_ending must be CRLF or an empty string")
    return f"* {serialize_thread_data(roots, identifier=identifier, include=include)}{line_ending}"
