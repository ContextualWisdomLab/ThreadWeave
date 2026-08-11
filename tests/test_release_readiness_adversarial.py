"""Adversarial contracts for the release-readiness workflow boundary."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"


def _readiness_block() -> str:
    """Return the release-readiness job without parsing workflow YAML."""

    workflow = WORKFLOW.read_text(encoding="utf-8")
    return workflow.split("  release-readiness:\n", 1)[1].split(
        "  build-release:\n", 1
    )[0]


def test_release_readiness_requires_protected_ref_and_semver_without_leading_zero() -> None:
    """Reject unprotected refs and non-canonical numeric version identifiers."""

    readiness = _readiness_block()
    assert "GITHUB_REF_PROTECTED" in readiness
    assert 'if [ "$GITHUB_REF_PROTECTED" != "true" ]; then' in readiness
    assert (
        '^((0|[1-9][0-9]*)\\.){2}(0|[1-9][0-9]*)$'
        in readiness
    )
    assert "Release version must be canonical MAJOR.MINOR.PATCH." in readiness
