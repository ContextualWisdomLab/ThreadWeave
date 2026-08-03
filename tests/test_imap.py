"""Tests for RFC 5256 THREAD response serialization."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from threadweave import (
    Container,
    Message,
    ThreadSerializationError,
    serialize_thread_data,
    serialize_thread_response,
    thread_messages,
)


def _container(identifier: int, *children: Container, uid: int | None = None) -> Container:
    """Build a concrete response container with explicit mailbox identifiers."""
    message = Message(
        message_id=f"message-{identifier}",
        sequence_number=identifier,
        uid=uid,
    )
    node = Container(message=message)
    for child in children:
        node.add_child(child)
    return node


def test_empty_thread_data_and_response_match_rfc_shape():
    """An empty search result has no trailing SP or thread-list."""
    assert serialize_thread_data([]) == "THREAD"
    assert serialize_thread_response([]) == "* THREAD\r\n"


def test_serializes_rfc_5256_parent_child_and_split_example():
    """Successive parents form a chain and sibling splits form nested lists."""
    first_thread = _container(2)
    first_branch = _container(4, _container(23))
    second_branch = _container(44, _container(7, _container(96)))
    second_thread = _container(3, _container(6, first_branch, second_branch))

    assert serialize_thread_response([first_thread, second_thread]) == (
        "* THREAD (2)(3 6 (4 23)(44 7 96))\r\n"
    )


def test_serializes_dummy_root_as_nested_sibling_lists():
    """A missing or excluded parent groups its sibling branches without an ID."""
    dummy = Container()
    dummy.add_child(_container(3))
    dummy.add_child(_container(5))

    assert serialize_thread_data([dummy]) == "THREAD ((3)(5))"


def test_uid_mode_uses_unique_identifiers():
    """UID THREAD output selects the explicit UID metadata instead of sequence."""
    root = _container(1, _container(2, uid=202), uid=101)
    assert serialize_thread_data([root], identifier="uid") == "THREAD (101 202)"


def test_callable_identifier_supports_external_mailbox_metadata():
    """A caller can select an identifier stored outside the core Message fields."""
    root = Container(message=Message(payload={"mailbox_id": 41}))
    child = Container(message=Message(payload={"mailbox_id": 42}))
    root.add_child(child)

    resolver: Callable[[Message], int] = lambda message: message.payload["mailbox_id"]
    assert serialize_thread_data([root], identifier=resolver) == "THREAD (41 42)"


def test_search_projection_groups_children_of_excluded_root():
    """Two matching descendants retain one thread when their parent is excluded."""
    root = _container(1, _container(3), _container(5))
    include = lambda message: message.sequence_number in {3, 5}

    assert serialize_thread_data([root], include=include) == "THREAD ((3)(5))"


def test_search_projection_promotes_single_descendant_of_excluded_root():
    """A single matching descendant needs no synthetic grouping container."""
    root = _container(1, _container(3))
    include = lambda message: message.sequence_number == 3

    assert serialize_thread_data([root], include=include) == "THREAD (3)"


def test_search_projection_splices_excluded_internal_parent():
    """Matching grandchildren become siblings below the nearest included ancestor."""
    excluded = _container(2, _container(3), _container(5))
    root = _container(1, excluded)
    include = lambda message: message.sequence_number != 2

    assert serialize_thread_data([root], include=include) == "THREAD (1 (3)(5))"


def test_search_projection_drops_excluded_leaf_and_empty_thread():
    """An excluded branch with no matching descendants disappears completely."""
    root = _container(1, _container(2))
    include = lambda message: False

    assert serialize_thread_data([root], include=include) == "THREAD"


def test_serialization_does_not_mutate_source_tree():
    """Search projection and output generation leave parent/child state untouched."""
    child = _container(2)
    root = _container(1, child)
    original_children = list(root.children)

    serialize_thread_data([root], include=lambda message: message.sequence_number == 2)

    assert root.children == original_children
    assert child.parent is root


@pytest.mark.parametrize("identifier", [None, 0, -1, True, 1.5, "1"])
def test_invalid_emitted_identifiers_are_rejected(identifier):
    """RFC ``nz-number`` values must be positive non-boolean integers."""
    root = Container(message=Message(sequence_number=identifier))
    with pytest.raises(ThreadSerializationError, match="positive integer"):
        serialize_thread_data([root])


def test_duplicate_emitted_identifiers_are_rejected():
    """A response cannot identify two distinct messages with one mailbox number."""
    with pytest.raises(ThreadSerializationError, match="duplicate identifier"):
        serialize_thread_data([_container(1), _container(1)])


def test_missing_uid_is_rejected_in_uid_mode():
    """UID mode fails closed when a matching message has no UID metadata."""
    with pytest.raises(ThreadSerializationError, match="positive integer"):
        serialize_thread_data([_container(1)], identifier="uid")


def test_unknown_identifier_field_is_rejected():
    """Only supported built-in fields or a callable resolver are accepted."""
    with pytest.raises(ValueError, match="sequence_number.*uid"):
        serialize_thread_data([_container(1)], identifier="message_id")  # type: ignore[arg-type]


def test_cycle_is_rejected_instead_of_hanging_or_truncating():
    """Malformed container cycles are explicit serialization errors."""
    root = _container(1)
    root.children = [root]
    with pytest.raises(ThreadSerializationError, match="cycle"):
        serialize_thread_data([root])


def test_shared_container_is_rejected_instead_of_duplicated():
    """One container reachable through two parents is not a valid thread tree."""
    shared = _container(3)
    first = _container(1, shared)
    second = _container(2)
    second.children = [shared]
    with pytest.raises(ThreadSerializationError, match="multiple positions"):
        serialize_thread_data([first, second])


def test_non_container_root_is_rejected():
    """Invalid graph inputs fail at the public boundary with a useful message."""
    with pytest.raises(TypeError, match="Container"):
        serialize_thread_data([object()])  # type: ignore[list-item]


def test_deep_chain_serializes_without_recursion():
    """THREAD has unbounded nesting, so long chains must remain iterative."""
    root = _container(1)
    current = root
    depth = 5000
    for identifier in range(2, depth + 1):
        child = _container(identifier)
        current.add_child(child)
        current = child

    rendered = serialize_thread_data([root])

    assert rendered.startswith("THREAD (1 2 3 4 5 ")
    assert rendered.endswith(f" {depth})")
    assert rendered.count("(") == 1


def test_deep_split_tree_serializes_without_recursion():
    """Nested sibling lists also avoid Python's recursion limit."""
    root = _container(1)
    current = root
    for identifier in range(2, 1500):
        branch = _container(identifier)
        sibling = _container(identifier + 10_000)
        current.add_child(branch)
        current.add_child(sibling)
        current = branch

    rendered = serialize_thread_data([root])
    assert rendered.startswith("THREAD (1 (2 ")
    assert "(10002)" in rendered


def test_line_ending_is_configurable_but_must_be_protocol_safe():
    """Servers can omit CRLF for framing layers while injection remains blocked."""
    root = _container(1)
    assert serialize_thread_response([root], line_ending="") == "* THREAD (1)"
    with pytest.raises(ValueError, match="line_ending"):
        serialize_thread_response([root], line_ending="\r\n* BAD")


def test_real_thread_messages_output_serializes_directly():
    """The public serializer consumes trees returned by the threading core."""
    roots = thread_messages(
        [
            Message(message_id="root", sequence_number=2),
            Message(message_id="child", references=["root"], sequence_number=4),
        ]
    )
    assert serialize_thread_response(roots) == "* THREAD (2 4)\r\n"


def test_same_root_object_cannot_be_emitted_twice():
    """Repeated top-level references are rejected as an invalid shared graph."""
    root = _container(1)
    with pytest.raises(ThreadSerializationError, match="multiple positions"):
        serialize_thread_data([root, root])


def test_non_container_child_is_rejected():
    """Every child edge must point to another Container."""
    root = _container(1)
    root.children = [object()]  # type: ignore[list-item]
    with pytest.raises(TypeError, match="children must be Container"):
        serialize_thread_data([root])


def test_non_message_payload_in_concrete_container_is_rejected():
    """Protocol output requires the mailbox metadata contract on Message."""
    root = Container(message="not-a-message")
    with pytest.raises(TypeError, match="threadweave.Message"):
        serialize_thread_data([root])


def test_non_callable_include_is_rejected():
    """Search projection must be supplied as a message predicate."""
    with pytest.raises(TypeError, match="include must be callable"):
        serialize_thread_data([_container(1)], include=True)  # type: ignore[arg-type]


def test_invalid_private_dummy_shapes_fail_closed():
    """Internal response nodes cannot bypass the RFC dummy-root arity rule."""
    from threadweave.imap import _ResponseNode, _render_thread_list

    with pytest.raises(ThreadSerializationError, match="at least two branches"):
        _render_thread_list(_ResponseNode(None, []))


def test_private_dummy_cannot_appear_inside_concrete_chain():
    """Only a top-level thread-list can encode an identifier-less dummy."""
    from threadweave.imap import _ResponseNode, _render_thread_list

    invalid = _ResponseNode(1, [_ResponseNode(None, [_ResponseNode(2), _ResponseNode(3)])])
    with pytest.raises(ThreadSerializationError, match="only valid at the top level"):
        _render_thread_list(invalid)
