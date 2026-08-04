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


def test_product_development_authenticates_with_nvidia_nim():
    """The in-workflow agent uses NVIDIA NIM only; Copilot is never assumed."""
    workflow = _workflow("hourly-product-development.yml")

    assert 'NVIDIA_API_KEY: ${{ secrets.NVIDIA_NIM_API_KEY }}' in workflow
    assert 'REPOSITORY_TOKEN: ${{ github.token }}' in workflow
    assert 'reason=nim_api_key_unavailable' in workflow
    assert 'GH_TOKEN="$REPOSITORY_TOKEN" gh pr list' in workflow
    assert '"baseURL": "https://integrate.api.nvidia.com/v1"' in workflow
    assert '"apiKey": "{env:NVIDIA_API_KEY}"' in workflow
    assert "COPILOT_GITHUB_TOKEN" not in workflow
    assert "/agents/repos" not in workflow
    assert "copilot-requests: write" not in workflow


def test_product_development_is_single_flight_and_fail_closed():
    """New work starts only when no PR exists, with credentials kept from the agent."""
    workflow = _workflow("hourly-product-development.yml")

    assert 'cron: "41 * * * *"' in workflow
    assert "cancel-in-progress: false" in workflow
    assert "group: hourly-product-development-${{ github.repository }}" in workflow
    assert '--state open --limit 1 --json number,url' in workflow
    assert 'reason=open_pull_request' in workflow
    assert "persist-credentials: false" in workflow
    assert "env -u GH_TOKEN -u GITHUB_TOKEN -u REPOSITORY_TOKEN" in workflow
    assert "sha256sum -c -" in workflow
    assert 'OPENCODE_VERSION: "1.17.13"' in workflow


def test_product_task_is_bounded_reviewable_and_commercially_focused():
    """Every autonomous cycle proposes one tested PR and never self-merges."""
    workflow = _workflow("hourly-product-development.yml")

    assert "Maintain 100% production" in workflow
    assert "statement and branch coverage" in workflow
    assert "Update CHANGELOG.md" in workflow
    assert "exactly one bounded pull request" in workflow
    assert "buyer-visible" in workflow
    assert "security-sensitive edge cases" in workflow
    assert "Do not merge, publish, or bypass" in workflow
    assert "gh pr create" in workflow
    assert '--base "$DEFAULT_BRANCH"' in workflow
    assert "gh pr merge" not in workflow
