"""Focused tests for the loop guards and JWZ internal transformations."""

from threadweave import Container, Message
from threadweave.threading import (
    _group_by_subject,
    _link,
    _prune,
    _reference_ids,
    _set_parent,
    _subject_of,
)


def test_reference_ids_deduplicates_across_header_fragments():
    """Repeated identifiers across sequence entries keep first-seen order."""
    assert _reference_ids(
        ["<a@example.com> <b@example.com>", "<b@example.com> <c@example.com>"]
    ) == ["a@example.com", "b@example.com", "c@example.com"]


def test_subject_of_returns_none_for_an_empty_cycle():
    """Subject lookup terminates when every node in a cycle is empty."""
    first = Container()
    second = Container()
    first.children = [second]
    second.children = [first]

    assert _subject_of(first) is None


def test_link_rejects_self_links_and_descendant_cycles():
    """Reference-chain linking refuses either form of graph cycle."""
    node = Container(message="node")
    _link(node, node)
    assert node.parent is None
    assert node.children == []

    parent = Container(message="parent")
    child = Container(message="child", children=[parent])
    _link(parent, child)
    assert child.parent is None
    assert parent.children == []


def test_set_parent_detaches_child_from_consistent_old_parent():
    """Definitive references move the exact child between parent lists."""
    old_parent = Container(message="old")
    child = Container(message="child", parent=old_parent)
    old_parent.children = [child]
    new_parent = Container(message="new")

    _set_parent(child, new_parent)

    assert old_parent.children == []
    assert child.parent is new_parent
    assert new_parent.children == [child]


def test_set_parent_repairs_inconsistent_old_parent_pointer():
    """Reparenting tolerates a parent pointer whose child list is incomplete."""
    old_parent = Container(message="old")
    child = Container(message="child", parent=old_parent)
    new_parent = Container(message="new")

    _set_parent(child, new_parent)

    assert child.parent is new_parent
    assert new_parent.children == [child]


def test_prune_removes_empty_leaf():
    """An empty root-set leaf carries no thread information and is removed."""
    holder = Container()
    leaf = Container(parent=holder)
    holder.children = [leaf]

    _prune(holder)

    assert holder.children == []


def test_prune_preserves_empty_root_with_multiple_children():
    """A missing root remains as the grouping node for a forked thread."""
    holder = Container()
    grouping = Container(parent=holder)
    first = Container(message=Message(message_id="first"), parent=grouping)
    second = Container(message=Message(message_id="second"), parent=grouping)
    grouping.children = [first, second]
    holder.children = [grouping]

    _prune(holder)

    assert holder.children == [grouping]
    assert grouping.parent is None
    assert grouping.children == [first, second]


def test_prune_terminates_on_a_malformed_child_cycle():
    """The post-order walk visits a cyclic node only once."""
    holder = Container()
    node = Container(message=Message(message_id="node"))
    node.children = [node]
    holder.children = [node]

    _prune(holder)

    assert holder.children == [node]
    assert node.parent is None
    assert node.children == [node]


def test_group_by_subject_drops_empty_subjectless_root():
    """A subjectless empty node cannot contribute a usable thread root."""
    assert _group_by_subject([Container()]) == []


def test_group_by_subject_prefers_non_reply_owner_seen_later():
    """A non-reply root replaces an earlier reply as the subject owner."""
    reply = Container(message=Message(message_id="reply", subject="Re: Topic"))
    original = Container(message=Message(message_id="original", subject="Topic"))

    grouped = _group_by_subject([reply, original])

    assert grouped == [original]
    assert original.children == [reply]
    assert reply.parent is original


def test_group_by_subject_combines_two_empty_roots():
    """Missing roots with the same subject merge their concrete descendants."""
    first_child = Container(message=Message(message_id="first", subject="Topic"))
    first_root = Container(children=[first_child])
    first_child.parent = first_root
    second_child = Container(
        message=Message(message_id="second", subject="Re: Topic")
    )
    second_root = Container(children=[second_child])
    second_child.parent = second_root

    grouped = _group_by_subject([first_root, second_root])

    assert grouped == [first_root]
    assert first_root.children == [first_child, second_child]
    assert second_child.parent is first_root
    assert second_root.children == []


def test_group_by_subject_promotes_empty_container_over_concrete_owner():
    """An empty grouping root absorbs a concrete root sharing its base subject."""
    original = Container(
        message=Message(message_id="original", subject="Topic")
    )
    reply = Container(message=Message(message_id="reply", subject="Re: Topic"))
    grouping = Container(children=[reply])
    reply.parent = grouping

    grouped = _group_by_subject([original, grouping])

    assert grouped == [grouping]
    assert grouping.children == [reply, original]
    assert original.parent is grouping
