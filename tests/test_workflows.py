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


def test_product_development_brokers_nim_outside_the_model_process():
    """The model gets a placeholder key while a loopback broker owns the secret."""
    workflow = _workflow("hourly-product-development.yml")

    assert 'cron: "41 * * * *"' in workflow
    assert "cancel-in-progress: false" in workflow
    assert "NIM_UPSTREAM_API_KEY: ${{ secrets.NVIDIA_NIM_API_KEY }}" in workflow
    assert "python scripts/ci/nim_proxy.py" in workflow
    assert '"baseURL": "http://127.0.0.1:8765/v1"' in workflow
    assert "NVIDIA_API_KEY=threadweave-local-broker" in workflow
    assert "NVIDIA_API_KEY=\"$NIM_UPSTREAM_API_KEY\"" not in workflow
    assert "sudo -u '#65532' -g '#65532' env -i" in workflow
    assert "sudo pkill -KILL -u 65532" in workflow
    assert "git archive HEAD | tar -x" in workflow
    assert "persist-credentials: false" in workflow
    assert '"webfetch": "deny"' in workflow
    assert '"websearch": "deny"' in workflow
    assert "COPILOT_GITHUB_TOKEN" not in workflow
    assert "/agents/repos" not in workflow


def test_model_job_blocks_undeclared_network_egress():
    """The provider process cannot use DNS or arbitrary endpoints for exfiltration."""
    workflow = _workflow("hourly-product-development.yml")

    assert workflow.count("egress-policy: block") == 3
    assert workflow.count("disable-telemetry: true") == 3
    assert "integrate.api.nvidia.com:443" in workflow
    assert "registry.npmjs.org:443" in workflow
    assert "*.blob.core.windows.net:443" in workflow
    assert "egress-policy: audit" not in workflow


def test_product_development_packages_and_reverifies_a_bounded_patch():
    """Model output crosses jobs only as a validated immutable text patch."""
    workflow = _workflow("hourly-product-development.yml")

    assert "scripts/ci/hourly_product_guard.py capture" in workflow
    assert workflow.count("scripts/ci/hourly_product_guard.py apply") == 2
    assert "THREADWEAVE_FORBIDDEN_SECRET" in workflow
    assert "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a" in workflow
    assert "actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c" in workflow
    assert "reverify-product-gap:" in workflow
    assert "publish-product-gap:" in workflow
    assert workflow.count("pulls?state=open&per_page=1") >= 3
    assert 'git add -A -- src/threadweave tests docs README.md CHANGELOG.md' in workflow
    assert "pyproject.toml" in workflow
    assert "Do not edit .github/**, scripts/**, AGENTS.md" in workflow


def test_reverification_runs_the_complete_product_quality_gate():
    """A fresh credential-free job proves the patch before publication."""
    workflow = _workflow("hourly-product-development.yml")

    assert "Set up independent Python verification" in workflow
    assert 'python -m pip install -e ".[test]" "ruff==0.15.20" build' in workflow
    assert "ruff check ." in workflow
    assert "coverage run -m pytest -q" in workflow
    assert "coverage report" in workflow
    assert "python -m build" in workflow
    assert "python -m pip check" in workflow
    assert "python -m pip install --force-reinstall dist/*.whl" in workflow
    assert "git diff --check" in workflow


def test_ci_overrides_package_only_coverage_source_for_autonomous_scripts():
    """The focused script run must override pyproject's `source = threadweave`."""
    workflow = _workflow("ci.yml")

    assert "coverage run --branch --source=scripts/ci -m pytest -q" in workflow
    assert (
        "--include=scripts/ci/hourly_product_guard.py,scripts/ci/nim_proxy.py"
        in workflow
    )
    assert "--fail-under=100" in workflow


def test_ci_cancels_stale_runs_per_pull_request_or_protected_ref():
    """Only the newest PR head or protected-ref push may consume CI runners."""
    workflow = _workflow("ci.yml")

    assert "concurrency:" in workflow
    assert (
        "group: ci-${{ github.workflow }}-${{ "
        "github.event.pull_request.number || github.ref }}"
    ) in workflow
    assert "cancel-in-progress: true" in workflow


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
