"""Governance contract for the mailbox-scale benchmark workflow."""

from pathlib import Path

WORKFLOW = (
    Path(__file__).parents[1]
    / ".github"
    / "workflows"
    / "incremental-benchmark.yml"
)


def _workflow() -> str:
    """Return the workflow source without adding a YAML parser dependency."""
    return WORKFLOW.read_text(encoding="utf-8")


def test_benchmark_is_manual_and_scheduled_with_a_100k_default():
    """Operators can reproduce evidence while a weekly run catches regressions."""
    workflow = _workflow()
    assert "workflow_dispatch:" in workflow
    assert 'default: "100000"' in workflow
    assert 'cron: "17 3 * * 1"' in workflow
    assert "cancel-in-progress: true" in workflow


def test_benchmark_uses_immutable_actions_and_the_reviewed_dependency_lock():
    """Performance evidence runs through the same pinned supply-chain boundary."""
    workflow = _workflow()
    required_actions = {
        "step-security/harden-runner@bf7454d06d71f1098171f2acdf0cd4708d7b5920",
        "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
        "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97",
        "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
    }
    observed_actions = {
        line.strip().removeprefix("uses: ").split(" #", 1)[0]
        for line in workflow.splitlines()
        if line.strip().startswith("uses: ")
    }
    assert required_actions <= observed_actions
    assert "pip install --require-hashes -r requirements/ci.lock" in workflow
    assert "persist-credentials: false" in workflow


def test_benchmark_requires_parity_bounded_impact_and_evidence_upload():
    """The workflow fails closed on incorrect output or a regressed 100k delta."""
    workflow = _workflow()
    assert "incremental_mailbox.py" in workflow
    assert 'incremental["projection_sha256"] == full_rebuild["projection_sha256"]' in workflow
    assert 'incremental["affected_message_count"] == 21' in workflow
    assert 'incremental["delta_apply_seconds"] < full_rebuild[' in workflow
    assert "incremental-mailbox-benchmark-${{ github.run_id }}" in workflow
    assert "retention-days: 90" in workflow
    assert "NVIDIA_NIM_API_KEY" not in workflow
    assert "COPILOT_GITHUB_TOKEN" not in workflow
