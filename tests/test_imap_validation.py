"""Validation tests for RFC 5256 THREAD serialization."""

import pytest

from threadweave import (
    Container,
    Message,
    ThreadSerializationError,
    serialize_thread_data,
    serialize_thread_response,
)


def _container(identifier: int, *children: Container) -> Container:
    """Build one concrete response container with a sequence number."""
    node = Container(message=Message(sequence_number=identifier))
    for child in children:
        node.add_child(child)
    return node


@pytest.mark.parametrize("identifier", [None, 0, -1, True, 1.5, "1"])
def test_invalid_emitted_identifiers_are_rejected(identifier):
    """RFC ``nz-number`` values must be positive non-boolean integers."""
    root = Container(message=Message(sequence_number=identifier))
    with pytest.raises(ThreadSerializationError, match="positive integer"):
        serialize_thread_data([root])


def test_maximum_imap_identifier_is_accepted():
    """The largest unsigned 32-bit non-zero value is valid."""
    root = Container(message=Message(sequence_number=4_294_967_295))
    assert serialize_thread_data([root]) == "THREAD (4294967295)"


def test_identifier_above_imap_nz_number_range_is_rejected():
    """IMAP numeric syntax caps identifiers below two to the power of 32."""
    root = Container(message=Message(sequence_number=4_294_967_296))
    with pytest.raises(ThreadSerializationError, match="unsigned 32-bit range"):
        serialize_thread_data([root])


def test_duplicate_emitted_identifiers_are_rejected():
    """Two messages cannot share one emitted mailbox identifier."""
    with pytest.raises(ThreadSerializationError, match="duplicate identifier"):
        serialize_thread_data([_container(1), _container(1)])


def test_missing_uid_is_rejected_in_uid_mode():
    """UID mode fails closed when a matching message has no UID."""
    with pytest.raises(ThreadSerializationError, match="positive integer"):
        serialize_thread_data([_container(1)], identifier="uid")


def test_unknown_identifier_field_is_rejected():
    """Only supported built-ins or a callable resolver are accepted."""
    with pytest.raises(ValueError, match="sequence_number.*uid"):
        serialize_thread_data(
            [_container(1)],
            identifier="message_id",  # type: ignore[arg-type]
        )


def test_non_callable_identifier_is_rejected():
    """A non-string non-callable selector is invalid."""
    with pytest.raises(ValueError, match="sequence_number.*uid"):
        serialize_thread_data(
            [_container(1)],
            identifier=object(),  # type: ignore[arg-type]
        )


def test_cycle_is_rejected_instead_of_hanging():
    """Malformed container cycles are explicit errors."""
    root = _container(1)
    root.children = [root]
    with pytest.raises(ThreadSerializationError, match="cycle"):
        serialize_thread_data([root])


def test_shared_container_is_rejected_instead_of_duplicated():
    """One container reachable through two parents is not a tree."""
    shared = _container(3)
    first = _container(1, shared)
    second = _container(2)
    second.children = [shared]
    with pytest.raises(ThreadSerializationError, match="multiple positions"):
        serialize_thread_data([first, second])


def test_same_root_object_cannot_be_emitted_twice():
    """Repeated top-level references are rejected."""
    root = _container(1)
    with pytest.raises(ThreadSerializationError, match="multiple positions"):
        serialize_thread_data([root, root])


def test_non_container_root_is_rejected():
    """Invalid graph roots fail at the public boundary."""
    with pytest.raises(TypeError, match="Container"):
        serialize_thread_data([object()])  # type: ignore[list-item]


def test_non_container_child_is_rejected():
    """Every child edge must point to another Container."""
    root = _container(1)
    root.children = [object()]  # type: ignore[list-item]
    with pytest.raises(TypeError, match="children must be Container"):
        serialize_thread_data([root])


def test_non_message_payload_in_concrete_container_is_rejected():
    """Protocol output requires the Message metadata contract."""
    root = Container(message="not-a-message")
    with pytest.raises(TypeError, match="threadweave.Message"):
        serialize_thread_data([root])


def test_non_callable_include_is_rejected():
    """Search projection must be a message predicate."""
    with pytest.raises(TypeError, match="include must be callable"):
        serialize_thread_data(
            [_container(1)],
            include=True,  # type: ignore[arg-type]
        )


def test_line_ending_is_configurable_but_protocol_safe():
    """A framing layer may omit CRLF, but arbitrary suffixes are rejected."""
    root = _container(1)
    assert serialize_thread_response([root], line_ending="") == "* THREAD (1)"
    unsafe_ending = "\r\n" + "* BAD"
    with pytest.raises(ValueError, match="line_ending"):
        serialize_thread_response([root], line_ending=unsafe_ending)


def test_invalid_private_dummy_shapes_fail_closed():
    """Internal nodes cannot bypass the dummy-root arity rule."""
    from threadweave.imap import _ResponseNode, _render_thread_list

    with pytest.raises(ThreadSerializationError, match="at least two branches"):
        _render_thread_list(_ResponseNode(None, []))


def test_private_dummy_cannot_appear_inside_concrete_chain():
    """Only a top-level thread-list can encode an identifier-less dummy."""
    from threadweave.imap import _ResponseNode, _render_thread_list

    invalid = _ResponseNode(
        1,
        [_ResponseNode(None, [_ResponseNode(2), _ResponseNode(3)])],
    )
    with pytest.raises(ThreadSerializationError, match="only valid at the top level"):
        _render_thread_list(invalid)
