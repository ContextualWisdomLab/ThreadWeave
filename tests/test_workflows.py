"""Contract tests for the repository's autonomous maintenance workflows."""

from pathlib import Path


WORKFLOW_DIRECTORY = Path(__file__).parents[1] / ".github" / "workflows"
CENTRAL_MERGE_REVISION = "3f65dbee6672b78802e7d71d49c390f3817bb03b"


def _workflow(name: str) -> str:
    """Return one workflow as text so tests require no YAML dependency."""
    return (WORKFLOW_DIRECTORY / name).read_text(encoding="utf-8")


def test_hourly_pr_maintenance_uses_central_cwl_workflows():
    """PR review, branch update, and merge stay centrally governed."""
    workflow = _workflow("hourly-pr-maintenance.yml")
    review_merge = workflow.split("  review-merge:\n", 1)[1]

    assert 'cron: "11 * * * *"' in workflow
    assert "pr-review-fix-scheduler.yml" not in workflow
    assert (
        "ContextualWisdomLab/.github/.github/workflows/"
        f"pr-review-merge-scheduler.yml@{CENTRAL_MERGE_REVISION}"
    ) in workflow
    assert "@main" not in workflow
    assert 'base_branch: "main"' in workflow
    assert 'review_dispatch_limit: "1"' in workflow
    assert 'branch_update_limit: "1"' in workflow
    assert 'merge_mode: "direct_or_auto"' in workflow
    assert "trigger_reviews: true" in workflow
    assert "update_branches: true" in workflow
    assert "enable_auto_merge: true" in workflow
    assert "secrets: inherit" not in workflow
    assert "\n    secrets:" not in review_merge
    assert "issues: write" not in workflow


def test_product_development_brokers_nim_outside_the_model_process():
    """The model gets a placeholder key while a loopback broker owns the secret."""
    workflow = _workflow("hourly-product-development.yml")
    develop = workflow.split("  develop-product-gap:\n", 1)[1].split(
        "  reverify-product-gap:\n", 1
    )[0]
    job_header = develop.split("    steps:\n", 1)[0]
    gate = develop.split(
        "      - name: Enforce the pull-request-first deterministic gate", 1
    )[1].split(
        "      - name: Check out the protected default branch without persisted credentials", 1
    )[0]
    broker = develop.split(
        "      - name: Start the loopback-only NIM credential broker", 1
    )[1].split("      - name: Run the NVIDIA NIM development agent", 1)[0]
    capture = develop.split("      - name: Capture the bounded credential-free patch", 1)[
        1
    ].split("      - name: Upload the bounded proposal", 1)[0]
    secret_binding = "NIM_UPSTREAM_API_KEY: ${{ secrets.NVIDIA_NIM_API_KEY }}"

    assert 'cron: "41 * * * *"' in workflow
    assert "cancel-in-progress: false" in workflow
    assert workflow.count(secret_binding) == 1
    assert secret_binding not in job_header
    assert "NIM_UPSTREAM_API_KEY" not in job_header
    assert "secrets.NVIDIA_NIM_API_KEY" not in gate
    assert "NIM_UPSTREAM_API_KEY" not in gate
    assert "if: steps.gate.outputs.develop == 'true'" in broker
    assert secret_binding in broker
    assert "python scripts/ci/nim_proxy.py" in broker
    assert "secret_fingerprint_guard.py fingerprint" in broker
    assert 'forbidden_fingerprint_file="${RUNNER_TEMP}/threadweave-secret-fingerprint.json"' in broker
    assert "set -euo pipefail" in capture
    assert "secret_fingerprint_guard.py scan" in capture
    assert '--fingerprint-file "$forbidden_fingerprint_file"' in capture
    assert "continue-on-error: true" not in capture
    assert develop.index("secret_fingerprint_guard.py scan") < develop.index(
        "actions/upload-artifact@"
    )
    assert workflow.index("secret_fingerprint_guard.py scan") < workflow.index(
        "scripts/ci/hourly_product_guard.py apply"
    )
    assert "THREADWEAVE_FORBIDDEN_SECRET" not in workflow
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


def test_product_development_pauses_while_a_release_blocker_is_open():
    """A release freeze prevents autonomous product drift before publication."""
    workflow = _workflow("hourly-product-development.yml")
    gate = workflow.split("      - name: Enforce the pull-request-first deterministic gate", 1)[
        1
    ].split(
        "      - name: Check out the protected default branch without persisted credentials", 1
    )[0]

    assert "issues?state=open&labels=release-blocker&per_page=1" in gate
    assert "select(.pull_request == null)" in gate
    assert "reason=release_blocker" in gate
    assert "A release-blocker issue is open" in gate
    assert gate.index("reason=open_pull_request") < gate.index("reason=release_blocker")
    assert gate.index("reason=release_blocker") < gate.index("reason=dry_run")
    assert "NVIDIA_NIM_API_KEY" not in gate


def test_model_job_blocks_undeclared_network_egress():
    """The provider process cannot use DNS or arbitrary endpoints for exfiltration."""
    workflow = _workflow("hourly-product-development.yml")
    workflow_lines = {line.strip() for line in workflow.splitlines()}
    required_endpoints = {
        "integrate.api.nvidia.com:443",
        "registry.npmjs.org:443",
        "*.blob.core.windows.net:443",
    }

    assert workflow.count("egress-policy: block") == 3
    assert workflow.count("disable-telemetry: true") == 3
    assert required_endpoints <= workflow_lines
    assert "egress-policy: audit" not in workflow_lines


def test_product_development_packages_and_reverifies_a_bounded_patch():
    """Model output crosses jobs only as a validated immutable text patch."""
    workflow = _workflow("hourly-product-development.yml")

    assert "scripts/ci/hourly_product_guard.py capture" in workflow
    assert workflow.count("scripts/ci/hourly_product_guard.py apply") == 2
    assert "THREADWEAVE_FORBIDDEN_SECRET" not in workflow
    assert "secret_fingerprint_guard.py fingerprint" in workflow
    assert "secret_fingerprint_guard.py scan" in workflow
    assert "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a" in workflow
    assert "actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c" in workflow
    assert "reverify-product-gap:" in workflow
    assert "publish-product-gap:" in workflow
    assert workflow.count("pulls?state=open&per_page=1") >= 3
    assert 'git add -A -- src/threadweave tests docs README.md CHANGELOG.md' in workflow
    assert "pyproject.toml" in workflow
    assert "Do not edit .github/**, scripts/**, AGENTS.md" in workflow


def test_reverification_runs_the_complete_product_quality_gate():
    """A fresh credential-free job proves the locked patch before publication."""
    workflow = _workflow("hourly-product-development.yml")

    assert "Set up independent Python verification" in workflow
    reverify = workflow.split("  reverify-product-gap:", 1)[1].split(
        "  publish-product-gap:", 1
    )[0]
    assert "PYTHONPATH: src" in reverify
    assert workflow.count("--require-hashes") >= 3
    assert workflow.count("-r requirements/ci.lock") >= 2
    assert "python -m build --no-isolation" in workflow
    assert "wheel_requirements=" in workflow
    assert "--no-index" in workflow
    assert "PIP_NO_INDEX=1" in workflow
    assert "ruff check ." in workflow
    assert "coverage run -m pytest -q" in workflow
    assert "coverage report" in workflow
    assert "python -m pip check" in workflow
    assert "git diff --check" in workflow
    assert "pip install --upgrade pip" not in workflow
    assert "pip install -e" not in workflow


def test_ci_regenerates_and_installs_only_the_reviewed_hash_lock():
    """Repository CI rejects stale locks and unhashed package installations."""
    workflow = _workflow("ci.yml")

    assert "lock-integrity:" in workflow
    assert (
        "astral-sh/setup-uv@11f9893b081a58869d3b5fccaea48c9e9e46f990"
        in workflow
    )
    assert 'version: "0.11.29"' in workflow
    assert "bash scripts/ci/compile_ci_lock.sh" in workflow
    assert "cmp --silent requirements/ci.lock" in workflow
    assert workflow.count(
        "python -m pip install --require-hashes -r requirements/ci.lock"
    ) == 2
    assert "python -m build --no-isolation" in workflow
    assert "wheel_sha=" in workflow
    assert "--no-index" in workflow
    assert "pip install --upgrade pip" not in workflow
    assert "pip install -e" not in workflow


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


def test_product_prompt_is_work_conserving_inside_the_bounded_slice():
    """The model must continue safe sub-steps instead of stopping after one success."""
    workflow = _workflow("hourly-product-development.yml")

    assert "Do not stop after completing one useful sub-step" in workflow
    assert "two fresh internal exit sweeps" in workflow
    assert "If either sweep finds another safe action" in workflow
    assert "within the same coherent product gap and allowed file scope" in workflow
    assert "one bounded proposal" in workflow
    assert "Do not open or publish a second pull request" in workflow


def test_product_workflow_keeps_hash_requirement_inside_the_yaml_block():
    """The multiline requirement must remain valid YAML and pip input."""
    workflow = _workflow("hourly-product-development.yml")
    expected = (
        "          printf 'threadweave @ file://%s \\\n"
        "            --hash=sha256:%s\\n' \\\n"
    )

    assert expected in workflow
    assert "\n    --hash=sha256:%s\\n' \\\n" not in workflow


def test_product_workflow_documents_intentional_nested_shell_expansion():
    """ShellCheck must not flag positional parameters expanded by the inner shell."""
    workflow = _workflow("hourly-product-development.yml")
    expected = (
        "            # shellcheck disable=SC2016\n"
        '            if timeout --kill-after=30s "${OPENCODE_RUN_TIMEOUT_SECONDS}s"'
    )

    assert expected in workflow


def test_ci_lints_every_workflow_with_a_pinned_actionlint_release():
    """A malformed scheduled workflow must fail ordinary pull-request CI."""
    workflow = _workflow("ci.yml")

    assert 'ACTIONLINT_VERSION: "1.7.12"' in workflow
    assert (
        "ACTIONLINT_SHA256: "
        "8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8"
        in workflow
    )
    assert "actionlint_${ACTIONLINT_VERSION}_linux_amd64.tar.gz" in workflow
    assert '"${RUNNER_TEMP}/actionlint" -color=false .github/workflows/*.yml' in workflow
