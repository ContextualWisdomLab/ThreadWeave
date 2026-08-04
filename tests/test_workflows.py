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


def test_product_development_uses_nim_in_a_credential_isolated_workspace():
    """The model receives NIM only and never shares a runner with publication."""
    workflow = _workflow("hourly-product-development.yml")

    assert 'cron: "41 * * * *"' in workflow
    assert "cancel-in-progress: false" in workflow
    assert "NVIDIA_API_KEY: ${{ secrets.NVIDIA_NIM_API_KEY }}" in workflow
    assert "sudo -u '#65532' -g '#65532' env -i" in workflow
    assert "git archive HEAD | tar -x" in workflow
    assert "persist-credentials: false" in workflow
    assert '"webfetch": "deny"' in workflow
    assert '"websearch": "deny"' in workflow
    assert "COPILOT_GITHUB_TOKEN" not in workflow
    assert "/agents/repos" not in workflow


def test_product_development_packages_and_reverifies_a_bounded_patch():
    """Model output crosses jobs only as a validated immutable text patch."""
    workflow = _workflow("hourly-product-development.yml")

    assert "scripts/ci/hourly_product_guard.py capture" in workflow
    assert "scripts/ci/hourly_product_guard.py apply" in workflow
    assert "THREADWEAVE_FORBIDDEN_SECRET" in workflow
    assert "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a" in workflow
    assert "actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c" in workflow
    assert "reverify-product-gap:" in workflow
    assert "publish-product-gap:" in workflow
    assert workflow.count("pulls?state=open&per_page=1") >= 3
    assert 'git add -A -- src/threadweave tests docs README.md CHANGELOG.md' in workflow
    assert "pyproject.toml" in workflow
    assert "Do not edit .github/**, scripts/**, AGENTS.md" in workflow


def test_publication_uses_external_automation_token_without_write_token_permissions():
    """A fresh trusted job opens the PR so required workflows start automatically."""
    workflow = _workflow("hourly-product-development.yml")

    assert "contents: write" not in workflow
    assert "pull-requests: write" not in workflow
    assert (
        "AUTOMATION_TOKEN: ${{ secrets.PR_REVIEW_MERGE_TOKEN || "
        "secrets.OPENCODE_APPROVE_TOKEN }}"
    ) in workflow
    assert "GH_TOKEN=\"$AUTOMATION_TOKEN\" gh pr create" in workflow
    assert "https://x-access-token:${AUTOMATION_TOKEN}@github.com/" in workflow
    assert "gh pr merge" not in workflow


def test_product_task_is_test_first_documented_and_never_self_releases():
    """Every autonomous increment remains reviewable and commercially focused."""
    workflow = _workflow("hourly-product-development.yml")

    assert "Use test-driven development" in workflow
    assert "Maintain 100% production statement and branch coverage" in workflow
    assert "Record user-visible changes under CHANGELOG.md [Unreleased]" in workflow
    assert "highest-value buyer-visible" in workflow
    assert "Do not stage, commit, push, open a pull request, tag, or publish" in workflow
    assert "PR_MESSAGE.md" in workflow
