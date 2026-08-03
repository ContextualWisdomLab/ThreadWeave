"""Tests that keep every production API understandable through docstrings."""

from __future__ import annotations

import inspect

import threadweave.adapters
import threadweave.collation
import threadweave.container
import threadweave.encoded_words
import threadweave.headers
import threadweave.subject
import threadweave.threading

MODULES = (
    threadweave.adapters,
    threadweave.collation,
    threadweave.container,
    threadweave.encoded_words,
    threadweave.headers,
    threadweave.subject,
    threadweave.threading,
)


def _defined_callables(module):
    """Yield functions, classes, methods, and properties defined by ``module``."""
    for _, member in inspect.getmembers(module):
        if getattr(member, "__module__", None) != module.__name__:
            continue
        if inspect.isfunction(member):
            yield member
            continue
        if not inspect.isclass(member):
            continue

        yield member
        for name, attribute in member.__dict__.items():
            if name.startswith("__"):
                continue
            if inspect.isfunction(attribute):
                if getattr(attribute, "__module__", None) == module.__name__:
                    yield attribute
            elif isinstance(attribute, property) and attribute.fget is not None:
                yield attribute.fget


def test_every_production_module_and_callable_has_a_docstring():
    """Production modules and their authored callables remain self-documenting."""
    for module in MODULES:
        assert inspect.getdoc(module), f"missing module docstring: {module.__name__}"
        for callable_object in _defined_callables(module):
            qualified_name = (
                f"{callable_object.__module__}.{callable_object.__qualname__}"
            )
            assert inspect.getdoc(callable_object), (
                f"missing callable docstring: {qualified_name}"
            )
