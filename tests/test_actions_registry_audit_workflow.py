"""Contract tests for the Actions Registry Audit workflow's source."""

from pathlib import Path


WORKFLOW_DIRECTORY = Path(__file__).parents[1] / ".github" / "workflows"


def _workflow() -> str:
    """Return the Actions Registry Audit workflow as text."""

    return (WORKFLOW_DIRECTORY / "actions-registry-audit.yml").read_text(encoding="utf-8")


def test_permissions_are_read_only_with_no_mutation_authority() -> None:
    """The detector must never hold actions/pull-requests write authority."""

    workflow = _workflow()
    job_permissions = workflow.split("    permissions:\n", 1)[1].split("    steps:\n", 1)[0]
    assert "actions: read" in job_permissions
    assert "contents: read" in job_permissions
    assert "pull-requests: read" in job_permissions
    assert "write" not in job_permissions


def test_runs_on_the_hourly_heartbeat_distinct_from_other_schedules() -> None:
    """Minute 53 must not contend with PR maintenance (11) or product dev (41)."""

    workflow = _workflow()
    assert 'cron: "53 * * * *"' in workflow


def test_does_not_trigger_on_pull_request() -> None:
    """A live audit that fails on a genuine live orphan must not block unrelated PRs.

    tests/test_actions_registry_audit.py already provides exact 100% PR-time
    contract coverage for the detector's own correctness through ci.yml; this
    workflow is the separate, deliberately visible incident signal.
    """

    workflow = _workflow()
    trigger_block = workflow.split("\non:\n", 1)[1].split("\nconcurrency:\n", 1)[0]
    assert "pull_request:" not in trigger_block
    assert "push:" in trigger_block


def test_non_pr_audit_runs_are_serialized_without_cancellation() -> None:
    """A new heartbeat must not terminate an in-flight audit."""

    workflow = _workflow()
    assert "group: actions-registry-audit-${{ github.repository }}" in workflow
    assert "cancel-in-progress: false" in workflow


def test_runs_on_push_to_main_only_for_the_detector_source() -> None:
    """Only changes to the detector itself should re-trigger a live audit on push."""

    workflow = _workflow()
    assert "branches: [main]" in workflow
    assert '"scripts/ci/actions_registry_audit.py"' in workflow


def test_supports_manual_dispatch() -> None:
    """An operator can trigger an out-of-cycle audit on demand."""

    workflow = _workflow()
    assert "workflow_dispatch: {}" in workflow


def test_uses_pinned_actions_and_python_314() -> None:
    """Supply-chain pins must match the rest of the repository's workflows."""

    workflow = _workflow()
    assert "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1" in workflow
    assert "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97" in workflow
    assert "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a" in workflow
    assert 'python-version: "3.14"' in workflow


def test_checkout_does_not_pin_a_ref() -> None:
    """Every remaining trigger already resolves to the default branch tip."""

    workflow = _workflow()
    checkout_step = workflow.split("uses: actions/checkout@", 1)[1]
    next_step = checkout_step.split("\n      - name:", 1)[0]
    assert "ref:" not in next_step


def test_uploads_evidence_even_when_the_audit_step_fails() -> None:
    """A found orphan/unresolved record must still leave the report attached."""

    workflow = _workflow()
    assert "if: always() && steps.audit.outputs.report_path != ''" in workflow
    assert "if-no-files-found: warn" in workflow
    assert 'exit "$audit_exit_code"' in workflow


def test_persists_no_checkout_credentials() -> None:
    """The read-only detector must never carry a reusable Git credential."""

    workflow = _workflow()
    assert "persist-credentials: false" in workflow
