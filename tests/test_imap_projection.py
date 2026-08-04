"""Projection and depth tests for RFC 5256 THREAD serialization."""

from threadweave import Container, Message, serialize_thread_data


def _container(identifier: int, *children: Container) -> Container:
    """Build one concrete response container with a sequence number."""
    node = Container(
        message=Message(
            message_id=f"message-{identifier}",
            sequence_number=identifier,
        )
    )
    for child in children:
        node.add_child(child)
    return node


def test_callable_identifier_is_not_compared_to_builtin_names():
    """A callable with hostile equality remains a valid resolver boundary."""

    class Resolver:
        def __eq__(self, _other: object) -> bool:
            raise AssertionError("resolver equality must not be invoked")

        def __call__(self, _message: Message) -> int:
            return 41

    root = Container(message=Message())
    assert serialize_thread_data([root], identifier=Resolver()) == "THREAD (41)"


def test_search_projection_groups_children_of_excluded_root():
    """Two matching descendants retain one thread when their parent is excluded."""
    root = _container(1, _container(3), _container(5))

    def include(message: Message) -> bool:
        return message.sequence_number in {3, 5}

    assert serialize_thread_data([root], include=include) == "THREAD ((3)(5))"


def test_search_projection_promotes_single_descendant_of_excluded_root():
    """A single matching descendant needs no synthetic grouping container."""
    root = _container(1, _container(3))

    def include(message: Message) -> bool:
        return message.sequence_number == 3

    assert serialize_thread_data([root], include=include) == "THREAD (3)"


def test_search_projection_splices_excluded_internal_parent():
    """Matching grandchildren become siblings below the nearest included ancestor."""
    excluded = _container(2, _container(3), _container(5))
    root = _container(1, excluded)

    def include(message: Message) -> bool:
        return message.sequence_number != 2

    assert serialize_thread_data([root], include=include) == "THREAD (1 (3)(5))"


def test_search_projection_drops_excluded_leaf_and_empty_thread():
    """A branch with no matching messages disappears completely."""
    root = _container(1, _container(2))

    assert serialize_thread_data([root], include=lambda _message: False) == "THREAD"


def test_serialization_does_not_mutate_source_tree():
    """Search projection and rendering leave source parent/child state untouched."""
    child = _container(2)
    root = _container(1, child)
    original_children = list(root.children)

    serialize_thread_data(
        [root],
        include=lambda message: message.sequence_number == 2,
    )

    assert root.children == original_children
    assert child.parent is root


def test_deep_chain_serializes_without_recursion():
    """Long parent-child chains remain iterative."""
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
