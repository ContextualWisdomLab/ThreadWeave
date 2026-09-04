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


def test_release_readiness_requires_protected_ref_and_canonical_semver() -> None:
    """Reject unprotected refs and non-canonical numeric project versions."""

    readiness = _readiness_block()
    assert "GITHUB_REF_PROTECTED" in readiness
    assert 'if [ "$GITHUB_REF_PROTECTED" != "true" ]; then' in readiness
    assert "import re" in readiness
    assert (
        're.fullmatch(r"(?:0|[1-9][0-9]*)\\.(?:0|[1-9][0-9]*)\\.'
        '(?:0|[1-9][0-9]*)", version)'
        in readiness
    )
    assert "project version must be canonical MAJOR.MINOR.PATCH" in readiness
    assert 'if [ -n "$REQUESTED_VERSION" ] && [ "$REQUESTED_VERSION" != "$release_version" ]; then' in readiness


def test_pull_request_gate_binds_workflow_evidence_to_authorizing_pr() -> None:
    """Reject successful PR checks from another PR that shares the same head SHA."""

    readiness = _readiness_block()
    assert 'pull_request_number="${4:-}"' in readiness
    assert '--argjson pr "$pull_request_number"' in readiness
    assert 'any(.pull_requests[]?; .number == $pr)' in readiness
    assert (
        'require_workflow_success "ci" "pull_request" "$source_pr_head" '
        '"$source_pr_number"'
        in readiness
    )
    assert (
        'require_workflow_success "SAST Semgrep" "pull_request" "$source_pr_head" '
        '"$source_pr_number"'
        in readiness
    )
    assert (
        'require_workflow_success "Security Scan" "pull_request" "$source_pr_head" '
        '"$source_pr_number"'
        in readiness
    )
