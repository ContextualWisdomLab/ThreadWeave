"""Contract tests for the repository's autonomous maintenance workflows."""

from pathlib import Path


WORKFLOW_DIRECTORY = Path(__file__).parents[1] / ".github" / "workflows"


def _workflow(name: str) -> str:
    """Return one workflow as text so tests require no YAML dependency."""
    return (WORKFLOW_DIRECTORY / name).read_text(encoding="utf-8")


def test_hourly_pr_maintenance_uses_central_cwl_workflows():
    """PR review, autofix, branch update, and merge stay centrally governed."""
    workflow = _workflow("hourly-pr-maintenance.yml")

    assert 'cron: "11 * * * *"' in workflow
    assert (
        "ContextualWisdomLab/.github/.github/workflows/"
        "pr-review-fix-scheduler.yml@main"
    ) in workflow
    assert (
        "ContextualWisdomLab/.github/.github/workflows/"
        "pr-review-merge-scheduler.yml@main"
    ) in workflow
    assert 'target_repository: "ContextualWisdomLab/ThreadWeave"' in workflow
    assert 'retry_hours: "1"' in workflow
    assert 'merge_mode: "direct_or_auto"' in workflow
    assert "secrets: inherit" in workflow


def test_product_development_uses_supported_agent_task_authentication():
    """Raw Agent Tasks REST calls use a supported fine-grained user token."""
    workflow = _workflow("hourly-product-development.yml")

    assert 'AGENT_TASK_TOKEN: ${{ secrets.COPILOT_GITHUB_TOKEN }}' in workflow
    assert 'REPOSITORY_TOKEN: ${{ github.token }}' in workflow
    assert 'reason=agent_task_token_unavailable' in workflow
    assert 'GH_TOKEN="$AGENT_TASK_TOKEN" gh api' in workflow
    assert 'GH_TOKEN="$REPOSITORY_TOKEN" gh pr list' in workflow
    assert 'X-GitHub-Api-Version: 2026-03-10' in workflow
    assert "copilot-requests: write" not in workflow
    assert "GH_TOKEN: ${{ github.token }}" not in workflow


def test_product_development_is_single_flight_and_fail_closed():
    """New work starts only when no PR or active/unknown task exists."""
    workflow = _workflow("hourly-product-development.yml")

    assert 'cron: "41 * * * *"' in workflow
    assert "cancel-in-progress: false" in workflow
    assert '--state open --limit 1 --json number,url' in workflow
    assert '"/agents/repos/${GITHUB_REPOSITORY}/tasks?per_page=100"' in workflow
    assert 'reason=task_inventory_unavailable' in workflow
    assert 'reason=active_agent_task' in workflow
    assert '$state != "completed"' in workflow
    assert '$state != "failed"' in workflow
    assert '$state != "timed_out"' in workflow
    assert '$state != "cancelled"' in workflow
    assert "// \"unknown\"" in workflow


def test_product_task_is_bounded_reviewable_and_commercially_focused():
    """Every autonomous cycle creates one tested PR and never self-merges."""
    workflow = _workflow("hourly-product-development.yml")

    assert "create_pull_request: true" in workflow
    assert "Maintain 100% production" in workflow
    assert "statement and branch coverage" in workflow
    assert "Update CHANGELOG.md" in workflow
    assert "Create exactly one bounded pull request" in workflow
    assert "buyer-visible" in workflow
    assert "security-sensitive edge cases" in workflow
    assert "Do not merge, publish, or bypass" in workflow
    assert "reviews. Create exactly one bounded pull request" in workflow
    assert "gh pr merge" not in workflow
