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
    assert "secrets: inherit" in workflow


def test_hourly_product_development_is_single_flight_and_pr_first():
    """New product work starts only when no PR or cloud-agent task is active."""
    workflow = _workflow("hourly-product-development.yml")

    assert 'cron: "41 * * * *"' in workflow
    assert "copilot-requests: write" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "gh pr list" in workflow
    assert '--repo "$GITHUB_REPOSITORY" --state open' in workflow
    assert '"/agents/repos/${GITHUB_REPOSITORY}/tasks"' in workflow
    assert "create_pull_request: true" in workflow
    assert "100% production statement and branch coverage" in workflow
    assert "Update CHANGELOG.md" in workflow
    assert "Create exactly one bounded pull request" in workflow


def test_agent_task_api_uses_supported_user_token_and_all_active_states():
    """The preview API never receives an unsupported Actions installation token."""
    workflow = _workflow("hourly-product-development.yml")

    assert "COPILOT_AGENT_TOKEN" in workflow
    assert "COPILOT_GITHUB_TOKEN" in workflow
    assert "PR_REVIEW_MERGE_TOKEN" in workflow
    assert 'if [ -z "${AGENT_TASK_TOKEN:-}" ]; then' in workflow
    assert 'GH_TOKEN="$AGENT_TASK_TOKEN" gh api' in workflow
    assert 'X-GitHub-Api-Version: 2026-03-10' in workflow
    assert '"idle"' in workflow
    assert '"waiting_for_user"' in workflow
