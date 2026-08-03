"""Tests for loop-safe, deterministic container operations."""

from threadweave import Container


def test_iter_descendants_uses_depth_first_insertion_order():
    root = Container(message="root")
    first = Container(message="first")
    first_child = Container(message="first-child")
    second = Container(message="second")

    root.add_child(first)
    first.add_child(first_child)
    root.add_child(second)

    assert [node.message for node in root.iter_descendants()] == [
        "first",
        "first-child",
        "second",
    ]


def test_iter_descendants_never_yields_root_from_cycle():
    root = Container(message="root")
    child = Container(message="child")
    root.children = [child]
    child.children = [root]

    assert [node.message for node in root.iter_descendants()] == ["child"]


def test_add_child_is_idempotent_for_existing_parent():
    root = Container(message="root")
    first = Container(message="first")
    second = Container(message="second")

    root.add_child(first)
    root.add_child(second)
    root.add_child(first)

    assert [node.message for node in root.children] == ["first", "second"]


def test_add_child_repairs_missing_child_entry():
    root = Container(message="root")
    child = Container(message="child", parent=root)

    root.add_child(child)

    assert len(root.children) == 1
    assert root.children[0] is child


def test_container_equality_is_identity_based_and_cycle_safe():
    first = Container(message="same")
    second = Container(message="same")
    first.children = [first]
    second.children = [second]

    assert first != second
    assert first == first


def test_add_child_reparents_the_exact_structurally_equal_child():
    old_parent = Container(message="old-parent")
    first = Container(message="same", parent=old_parent)
    second = Container(message="same", parent=old_parent)
    old_parent.children = [first, second]
    new_parent = Container(message="new-parent")

    new_parent.add_child(second)

    assert len(old_parent.children) == 1
    assert old_parent.children[0] is first
    assert new_parent.children == [second]
    assert second.parent is new_parent
