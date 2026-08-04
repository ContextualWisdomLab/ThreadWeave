"""Tests for RFC 5256 THREAD response serialization."""

from __future__ import annotations

from collections.abc import Callable

from threadweave import (
    Container,
    Message,
    serialize_thread_data,
    serialize_thread_response,
    thread_messages,
)


def _container(
    identifier: int,
    *children: Container,
    uid: int | None = None,
) -> Container:
    """Build a concrete response container with explicit mailbox identifiers."""
    node = Container(
        message=Message(
            message_id=f"message-{identifier}",
            sequence_number=identifier,
            uid=uid,
        )
    )
    for child in children:
        node.add_child(child)
    return node


def test_empty_thread_data_and_response_match_rfc_shape():
    """An empty search result has no trailing space or thread-list."""
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
    """A missing parent groups sibling branches without an identifier."""
    dummy = Container()
    dummy.add_child(_container(3))
    dummy.add_child(_container(5))

    assert serialize_thread_data([dummy]) == "THREAD ((3)(5))"


def test_uid_mode_uses_unique_identifiers():
    """UID THREAD output selects UID metadata instead of sequence numbers."""
    root = _container(1, _container(2, uid=202), uid=101)
    assert serialize_thread_data([root], identifier="uid") == "THREAD (101 202)"


def test_callable_identifier_supports_external_mailbox_metadata():
    """A caller can resolve identifiers stored outside Message fields."""
    root = Container(message=Message(payload={"mailbox_id": 41}))
    child = Container(message=Message(payload={"mailbox_id": 42}))
    root.add_child(child)

    resolver: Callable[[Message], int] = lambda message: message.payload["mailbox_id"]
    assert serialize_thread_data([root], identifier=resolver) == "THREAD (41 42)"


def test_real_thread_messages_output_serializes_directly():
    """The serializer consumes trees returned by the threading core."""
    roots = thread_messages(
        [
            Message(message_id="root", sequence_number=2),
            Message(message_id="child", references=["root"], sequence_number=4),
        ]
    )
    assert serialize_thread_response(roots) == "* THREAD (2 4)\r\n"
