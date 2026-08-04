"""Contract tests for the reviewable hash-locked CI dependency set."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path


ROOT = Path(__file__).parents[1]
PYPROJECT = ROOT / "pyproject.toml"
LOCK_INPUT = ROOT / "requirements" / "ci.in"
LOCK_FILE = ROOT / "requirements" / "ci.lock"
LOCK_COMPILER = ROOT / "scripts" / "ci" / "compile_ci_lock.sh"
SUPPLY_CHAIN_DOC = ROOT / "docs" / "supply-chain.md"

EXPECTED_DIRECT_PINS = {
    "build==1.5.0",
    "coverage[toml]==7.15.3",
    "hatchling==1.31.0",
    "pytest==9.1.1",
    "ruff==0.15.20",
}


def _active_lines(path: Path) -> list[str]:
    """Return non-empty, non-comment lines from one policy file."""

    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def test_pyproject_and_direct_lock_input_use_exact_synchronized_pins():
    """Package metadata and CI intent cannot silently select different tools."""

    project = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    assert project["project"]["dependencies"] == []
    assert project["build-system"]["requires"] == ["hatchling==1.31.0"]
    assert project["project"]["optional-dependencies"]["test"] == [
        "coverage[toml]==7.15.3",
        "pytest==9.1.1",
    ]
    assert set(_active_lines(LOCK_INPUT)) == EXPECTED_DIRECT_PINS


def test_lock_compiler_is_versioned_universal_and_time_bounded():
    """One deterministic command owns every lock refresh."""

    script = LOCK_COMPILER.read_text(encoding="utf-8")
    assert 'UV_REQUIRED_VERSION="0.11.29"' in script
    assert 'EXCLUDE_NEWER="2026-08-04T00:00:00Z"' in script
    assert "--universal" in script
    assert "--python-version 3.10" in script
    assert "--generate-hashes" in script
    assert "--exclude-newer \"$EXCLUDE_NEWER\"" in script
    assert "--no-header" in script
    assert 'output_path="${1:-requirements/ci.lock}"' in script


def test_generated_lock_is_complete_hash_checking_input():
    """Every locked distribution is exact and carries one or more SHA-256 hashes."""

    text = LOCK_FILE.read_text(encoding="utf-8")
    assert "--hash=sha256:" in text
    assert "==" in text
    assert "-e " not in text
    assert "git+" not in text
    assert "http://" not in text

    requirement_blocks = re.split(r"\n(?=[A-Za-z0-9_.-]+==)", text.strip())
    assert requirement_blocks
    for block in requirement_blocks:
        first_line = block.splitlines()[0]
        assert "==" in first_line, block
        assert re.search(r"--hash=sha256:[0-9a-f]{64}", block), block


def test_supply_chain_documentation_is_operational_and_auditable():
    """A new maintainer can refresh and review the lock without source archaeology."""

    text = SUPPLY_CHAIN_DOC.read_text(encoding="utf-8").lower()
    required_phrases = {
        "uv 0.11.29",
        "2026-08-04t00:00:00z",
        "scripts/ci/compile_ci_lock.sh",
        "python -m pip install --require-hashes -r requirements/ci.lock",
        "python -m build --no-isolation",
        "byte-for-byte",
        "autonomous model",
        "rollback",
    }
    assert all(phrase in text for phrase in required_phrases)
