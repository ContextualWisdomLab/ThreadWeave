"""Docstring coverage for the autonomous and release workflow trust boundaries."""

from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).parents[1]


def _load(name: str, relative_path: str) -> ModuleType:
    """Load one repository script as a stable module for documentation checks."""

    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MODULES = (
    _load("threadweave_actions_registry_audit", "scripts/ci/actions_registry_audit.py"),
    _load("threadweave_hourly_product_guard", "scripts/ci/hourly_product_guard.py"),
    _load("threadweave_nim_proxy", "scripts/ci/nim_proxy.py"),
    _load("threadweave_release_contract", "scripts/ci/release_contract.py"),
)


def _defined_callables(module: ModuleType):
    """Yield authored functions, classes, methods, and properties in ``module``."""

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


def test_every_autonomous_module_and_callable_has_a_docstring():
    """Every trusted boundary remains understandable without reading its body."""

    for module in MODULES:
        assert inspect.getdoc(module), f"missing module docstring: {module.__name__}"
        for callable_object in _defined_callables(module):
            qualified_name = (
                f"{callable_object.__module__}.{callable_object.__qualname__}"
            )
            assert inspect.getdoc(callable_object), (
                f"missing callable docstring: {qualified_name}"
            )
