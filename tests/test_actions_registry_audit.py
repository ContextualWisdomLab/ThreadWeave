"""Fail-first contract for the read-only Actions registry lifecycle auditor."""

from pathlib import Path


ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "scripts" / "ci" / "actions_registry_audit.py"


def test_actions_registry_audit_production_module_exists() -> None:
    """The fleet incident needs an executable repository-owned detector."""

    assert MODULE_PATH.is_file(), "scripts/ci/actions_registry_audit.py is not implemented"
