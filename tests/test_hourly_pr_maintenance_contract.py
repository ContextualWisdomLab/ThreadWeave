"""Contract tests for ThreadWeave's hourly PR-maintenance caller."""

from pathlib import Path


WORKFLOW = (
    Path(__file__).parents[1]
    / ".github"
    / "workflows"
    / "hourly-pr-maintenance.yml"
)
CENTRAL_MERGE_REVISION = "3f65dbee6672b78802e7d71d49c390f3817bb03b"


def _workflow() -> str:
    """Return the hourly PR-maintenance workflow as UTF-8 text."""

    return WORKFLOW.read_text(encoding="utf-8")


def test_hourly_pr_maintenance_uses_one_immutable_secretless_scheduler() -> None:
    """The caller must not duplicate repair dispatch or forward repository secrets."""

    workflow = _workflow()
    review_merge = workflow.split("  review-merge:\n", 1)[1]

    assert 'cron: "11 * * * *"' in workflow
    assert "pr-review-fix-scheduler.yml" not in workflow
    assert "secrets: inherit" not in workflow
    assert "\n    secrets:" not in review_merge
    assert "@main" not in workflow
    assert (
        "ContextualWisdomLab/.github/.github/workflows/"
        f"pr-review-merge-scheduler.yml@{CENTRAL_MERGE_REVISION}"
    ) in workflow
    assert 'base_branch: "main"' in workflow
    assert 'review_dispatch_limit: "1"' in workflow
    assert 'branch_update_limit: "1"' in workflow
    assert 'merge_mode: "direct_or_auto"' in workflow
    assert "trigger_reviews: true" in workflow
    assert "update_branches: true" in workflow
    assert "enable_auto_merge: true" in workflow
    assert "issues: write" not in workflow
    assert (
        "permissions:\n"
        "  contents: read\n\n"
        "jobs:\n"
        "  review-merge:\n"
    ) in workflow
    assert (
        "    permissions:\n"
        "      actions: write\n"
        "      checks: read\n"
        "      contents: write\n"
        "      id-token: write\n"
        "      pull-requests: write\n"
        "      statuses: read\n"
    ) in workflow
