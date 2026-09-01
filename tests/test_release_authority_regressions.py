"""Regression contracts for exact-head release authority and recovery semantics."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"


def _workflow() -> str:
    """Return the reviewed release workflow as UTF-8 text."""

    return WORKFLOW.read_text(encoding="utf-8")


def _job(workflow: str, name: str, next_name: str | None) -> str:
    """Return one job block without adding a YAML parser dependency."""

    block = workflow.split(f"  {name}:\n", 1)[1]
    if next_name is not None:
        block = block.split(f"  {next_name}:\n", 1)[0]
    return block


def test_automatic_release_starts_only_after_main_ci_completes() -> None:
    """A watched push must not race the exact integrated CI run."""

    workflow = _workflow()
    trigger = workflow.split("permissions:", 1)[0]
    assert "workflow_run:" in trigger
    assert 'workflows: ["ci"]' in trigger
    assert "types: [completed]" in trigger
    assert "branches: [main]" in trigger
    assert "\n  push:\n" not in trigger
    readiness = _job(workflow, "release-readiness", "build-release")
    assert "github.event.workflow_run.conclusion == 'success'" in readiness
    assert "github.event.workflow_run.head_sha" in readiness


def test_release_authority_checks_integrated_ci_sast_and_source_pr_security() -> None:
    """Irreversible release work waits for reviewed terminal-success evidence."""

    readiness = _job(_workflow(), "release-readiness", "build-release")
    assert "actions: read" in readiness
    assert "pull-requests: read" in readiness
    assert "require_workflow_success" in readiness
    assert 'require_workflow_success "ci" "push" "$SOURCE_SHA"' in readiness
    assert 'require_workflow_success "SAST Semgrep" "push" "$SOURCE_SHA"' in readiness
    assert 'require_workflow_success "Security Scan" "pull_request" "$source_pr_head"' in readiness
    assert '"repos/$GITHUB_REPOSITORY/commits/$SOURCE_SHA/pulls"' in readiness
    assert "merge_commit_sha" in readiness
    assert "associated merged pull request" in readiness


def test_release_runs_are_serialized_across_source_shas() -> None:
    """Two consecutive main commits must never publish the same version concurrently."""

    workflow = _workflow()
    concurrency = workflow.split("concurrency:\n", 1)[1].split("\nenv:\n", 1)[0]
    assert "group: release-${{ github.repository }}" in concurrency
    assert "head_sha" not in concurrency
    assert "github.sha" not in concurrency
    assert "cancel-in-progress: false" in concurrency


def test_tag_revalidates_main_before_first_immutable_side_effect() -> None:
    """A superseded candidate exits unless its matching release tag already exists."""

    workflow = _workflow()
    tag = _job(workflow, "tag-release", "github-release")
    assert "actions: read" not in tag
    assert "current_main_sha" in tag
    assert '"repos/$GITHUB_REPOSITORY/branches/main"' in tag
    assert 'if [ "$current_main_sha" != "$SOURCE_SHA" ] && [ -z "$tag_object" ]; then' in tag
    assert "release_authorized=false" in tag
    assert "release_authorized=true" in tag
    assert "release_authorized: ${{ steps.tag.outputs.release_authorized }}" in tag
    assert "Existing release tag is not an annotated tag for this exact release source" in tag
    github_release = _job(workflow, "github-release", "publish-pypi")
    assert "needs.tag-release.outputs.release_authorized == 'true'" in github_release


def test_stale_or_already_public_automatic_runs_are_successful_noops() -> None:
    """Automatic recovery must not rebuild an old or already released version."""

    workflow = _workflow()
    readiness = _job(workflow, "release-readiness", "build-release")
    assert "run_release" in readiness
    assert "github.event_name == 'workflow_run'" in readiness
    assert "current_main_sha" in readiness
    assert "public_version_exists" in readiness
    assert "run_release=false" in readiness
    build = _job(workflow, "build-release", "publication-plan")
    assert "needs.release-readiness.outputs.run_release == 'true'" in build
    assert "needs.release-readiness.outputs.source_sha" in build


def test_manual_recovery_can_rebuild_an_existing_or_partial_publication() -> None:
    """Manual recovery remains explicit and exact-main-bound after automatic no-op."""

    readiness = _job(_workflow(), "release-readiness", "build-release")
    assert "workflow_dispatch" in _workflow().split("permissions:", 1)[0]
    assert "REQUESTED_VERSION: ${{ inputs.version || '' }}" in readiness
    assert 'if [ "$GITHUB_EVENT_NAME" = "workflow_dispatch" ]; then' in readiness
    assert "run_release=true" in readiness


def test_public_registry_verification_retries_only_matching_incomplete_sets() -> None:
    """Normal PyPI propagation delay is retried without tolerating immutable mismatch."""

    verify = _job(_workflow(), "verify-publication", None)
    assert "for attempt in $(seq 1 12); do" in verify
    assert "sleep 10" in verify
    assert "exit 10" in verify
    assert "exit 20" in verify
    assert "PyPI artifact set did not converge" in verify
    assert "public artifact digest mismatch" in verify
    assert "unexpected public artifact" in verify


def test_api_token_publisher_stays_isolated_without_environment_dependency() -> None:
    """Deployment safety comes from exact release authority, not an absent OIDC environment."""

    workflow = _workflow()
    publish = _job(workflow, "publish-pypi", "verify-publication")
    assert "password: ${{ secrets.PIPY_TOKEN }}" in publish
    assert "environment:\n      name: pypi" not in publish
    assert "id-token: write" not in publish
    readiness = _job(workflow, "release-readiness", "build-release")
    assert "required_reviewers" not in readiness
    assert "prevent_self_review" not in readiness
