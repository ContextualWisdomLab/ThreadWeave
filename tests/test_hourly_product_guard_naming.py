"""Naming-contract regression for the autonomous product guard."""

from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "ci" / "hourly_product_guard.py"


def _load_product_guard():
    """Load the repository-owned guard without changing package structure."""
    module_spec = importlib.util.spec_from_file_location(
        "threadweave_hourly_product_guard_naming", MODULE_PATH
    )
    assert module_spec is not None and module_spec.loader is not None
    guard_module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(guard_module)
    return guard_module


def test_guard_uses_semantic_command_execution_helper_name() -> None:
    """Trusted command execution must not use a generic one-word helper name."""
    guard_module = _load_product_guard()

    assert hasattr(guard_module, "_run_command")
    assert not hasattr(guard_module, "_run")
