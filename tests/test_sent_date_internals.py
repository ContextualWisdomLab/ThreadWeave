"""Focused tests for loop-safe sent-date sorting helpers."""

from threadweave import Container
from threadweave.threading import (
    _EARLIEST_SORT_KEY,
    _container_sort_key,
    _sort_all_siblings,
)


def test_empty_dummy_uses_earliest_sort_key():
    """An unexpected childless dummy remains deterministically sortable."""
    assert _container_sort_key(Container(), {}) == _EARLIEST_SORT_KEY


def test_dummy_key_lookup_terminates_on_cycle():
    """Malformed first-child cycles cannot hang sort-key resolution."""
    first = Container()
    second = Container()
    first.children = [second]
    second.children = [first]
    assert _container_sort_key(first, {}) == _EARLIEST_SORT_KEY


def test_bottom_up_sort_walk_terminates_on_cycle():
    """The post-order traversal visits a malformed cyclic node only once."""
    first = Container()
    second = Container()
    first.children = [second]
    second.children = [first]
    roots = _sort_all_siblings([first], {})
    assert roots == [first]
