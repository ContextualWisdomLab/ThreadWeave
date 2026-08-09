"""Regression contracts for Hourly Product Development network policy."""

from pathlib import Path

import pytest


WORKFLOW = (
    Path(__file__).parents[1] / ".github" / "workflows" / "hourly-product-development.yml"
)

EXPECTED_ENDPOINTS = {
    "develop-product-gap": {
        "api.github.com:443",
        "cafe.github.com:443",
        "codeload.github.com:443",
        "files.pythonhosted.org:443",
        "github.com:443",
        "integrate.api.nvidia.com:443",
        "objects.githubusercontent.com:443",
        "pypi.org:443",
        "registry.npmjs.org:443",
        "release-assets.githubusercontent.com:443",
        "results-receiver.actions.githubusercontent.com:443",
        "*.actions.githubusercontent.com:443",
        "*.blob.core.windows.net:443",
    },
    "reverify-product-gap": {
        "api.github.com:443",
        "cafe.github.com:443",
        "files.pythonhosted.org:443",
        "github.com:443",
        "objects.githubusercontent.com:443",
        "pypi.org:443",
        "release-assets.githubusercontent.com:443",
        "results-receiver.actions.githubusercontent.com:443",
        "*.actions.githubusercontent.com:443",
        "*.blob.core.windows.net:443",
    },
    "publish-product-gap": {
        "api.github.com:443",
        "cafe.github.com:443",
        "github.com:443",
        "objects.githubusercontent.com:443",
        "results-receiver.actions.githubusercontent.com:443",
        "*.actions.githubusercontent.com:443",
        "*.blob.core.windows.net:443",
    },
}


def _job_block(workflow: str, job_name: str, next_job_name: str | None = None) -> str:
    """Return exactly one named workflow job block for contract assertions."""
    block = workflow.split(f"  {job_name}:\n", 1)[1]
    if next_job_name is not None:
        block = block.split(f"  {next_job_name}:\n", 1)[0]
    return block


def _hardened_endpoint_lines(job: str) -> set[str]:
    """Return exact endpoint entries from the runtime-safe folded YAML scalar."""
    marker = "          allowed-endpoints: >-\n"
    assert marker in job, "Harden Runner endpoints must be folded to space delimiters"
    endpoints = job.split(marker, 1)[1].split("\n\n", 1)[0]
    return {line.strip() for line in endpoints.splitlines() if line.strip()}


def _contains_repository_gh_api_command(job: str) -> bool:
    """Return whether a job executes GitHub CLI API access against this repository."""
    return any(
        line.strip().startswith('gh api "repos/${GITHUB_REPOSITORY}/')
        for line in job.splitlines()
    )


def _assert_named_job_network_contract(
    workflow: str, job_name: str, next_job_name: str | None
) -> None:
    """Assert one named job has the exact reviewed fail-closed network contract."""
    job = _job_block(workflow, job_name, next_job_name)
    assert "egress-policy: block" in job, job_name
    assert _hardened_endpoint_lines(job) == EXPECTED_ENDPOINTS[job_name], job_name
    assert _contains_repository_gh_api_command(job), job_name


def _develop_gate(workflow: str) -> str:
    """Return only the credential-free deterministic gate from the develop job."""
    develop = _job_block(workflow, "develop-product-gap", "reverify-product-gap")
    return develop.split(
        "      - name: Enforce the pull-request-first deterministic gate", 1
    )[1].split(
        "      - name: Check out the protected default branch without persisted credentials", 1
    )[0]


def _stop_gate_block(gate: str, reason: str) -> tuple[str, int, int]:
    """Return one deterministic stop branch and its location inside the gate."""
    reason_position = gate.index(f'echo "reason={reason}"')
    block_start = gate.rfind("          if [", 0, reason_position)
    assert block_start >= 0, reason
    block_end = gate.index("          fi", reason_position) + len("          fi")
    return gate[block_start:block_end], block_start, block_end


def _assert_deterministic_gate_contract(workflow: str) -> None:
    """Assert model-independent stop branches terminate before the ready decision."""
    gate = _develop_gate(workflow)
    ready_position = gate.index('echo "reason=ready"')
    assert "secrets.NVIDIA_NIM_API_KEY" not in gate
    assert "NIM_UPSTREAM_API_KEY" not in gate

    for reason in ("open_pull_request", "release_blocker", "dry_run"):
        block, block_start, block_end = _stop_gate_block(gate, reason)
        assert f'reason={reason}' in block
        assert "exit 0" in block
        assert block_start < block_end <= ready_position


def test_each_named_hardened_product_phase_has_exact_github_api_egress_contract():
    """Every named GitHub-API phase keeps its exact reviewed fail-closed allowlist."""
    workflow = WORKFLOW.read_text(encoding="utf-8")
    for job_name, next_job_name in (
        ("develop-product-gap", "reverify-product-gap"),
        ("reverify-product-gap", "publish-product-gap"),
        ("publish-product-gap", None),
    ):
        _assert_named_job_network_contract(workflow, job_name, next_job_name)

    assert "egress-policy: audit" not in workflow


def test_endpoint_contract_rejects_literal_block_runtime_delimiters():
    """Literal newlines must not regress the agent's space-delimited endpoint input."""
    workflow = WORKFLOW.read_text(encoding="utf-8")
    mutated = workflow.replace("          allowed-endpoints: >-\n", "          allowed-endpoints: |\n", 1)
    assert mutated != workflow

    with pytest.raises(AssertionError):
        _assert_named_job_network_contract(
            mutated, "develop-product-gap", "reverify-product-gap"
        )


def test_endpoint_contract_rejects_hostname_suffix_injection():
    """A lookalike endpoint cannot satisfy the exact Harden Runner allowlist contract."""
    workflow = WORKFLOW.read_text(encoding="utf-8")
    mutated = workflow.replace(
        "            api.github.com:443\n",
        "            api.github.com:443.evil\n",
        1,
    )

    with pytest.raises(AssertionError):
        _assert_named_job_network_contract(
            mutated, "develop-product-gap", "reverify-product-gap"
        )


def test_develop_job_runs_terminating_deterministic_gates_before_model_credential():
    """Model-independent stop gates terminate before optional model credentials matter."""
    _assert_deterministic_gate_contract(WORKFLOW.read_text(encoding="utf-8"))


def test_deterministic_gate_contract_rejects_missing_stop_exit():
    """Removing any deterministic stop exit must break the workflow contract."""
    workflow = WORKFLOW.read_text(encoding="utf-8")
    gate = _develop_gate(workflow)

    for reason in ("open_pull_request", "release_blocker", "dry_run"):
        block, block_start, block_end = _stop_gate_block(gate, reason)
        mutated_block = block.replace("            exit 0\n", "", 1)
        assert mutated_block != block, reason
        mutated_gate = gate[:block_start] + mutated_block + gate[block_end:]
        mutated_workflow = workflow.replace(gate, mutated_gate, 1)
        with pytest.raises(AssertionError):
            _assert_deterministic_gate_contract(mutated_workflow)


def test_reverification_and_publication_keep_github_api_checks_in_named_jobs():
    """Credential-free downstream jobs retain their own hardened GitHub API gates."""
    workflow = WORKFLOW.read_text(encoding="utf-8")
    for job_name, next_job_name in (
        ("reverify-product-gap", "publish-product-gap"),
        ("publish-product-gap", None),
    ):
        job = _job_block(workflow, job_name, next_job_name)
        assert job.index("Check out a fresh protected branch") < job.index("gh api "), job_name
        assert "NIM_UPSTREAM_API_KEY" not in job, job_name


def test_model_secret_is_materialized_only_after_deterministic_gate_selects_model_path():
    """Only the broker may receive the raw model secret after a model path is chosen."""
    workflow = WORKFLOW.read_text(encoding="utf-8")
    develop = _job_block(workflow, "develop-product-gap", "reverify-product-gap")
    gate = _develop_gate(workflow)

    assert "secrets.NVIDIA_NIM_API_KEY" not in gate
    assert "NIM_UPSTREAM_API_KEY" not in gate
    assert develop.count("NIM_UPSTREAM_API_KEY: ${{ secrets.NVIDIA_NIM_API_KEY }}") == 1

    broker = develop.split(
        "      - name: Start the loopback-only NIM credential broker", 1
    )[1].split("      - name: Run the NVIDIA NIM development agent", 1)[0]
    assert "if: steps.gate.outputs.develop == 'true'" in broker
    assert "NIM_UPSTREAM_API_KEY: ${{ secrets.NVIDIA_NIM_API_KEY }}" in broker
    assert 'if [ -z "${NIM_UPSTREAM_API_KEY:-}" ]; then' in broker
    assert "secret_fingerprint_guard.py fingerprint" in broker
    assert "exit 1" in broker


def test_model_fallback_budget_fits_outer_job_timeout():
    """Every sequential model fallback plus orchestration reserve must be schedulable."""
    workflow = WORKFLOW.read_text(encoding="utf-8")
    develop = _job_block(workflow, "develop-product-gap", "reverify-product-gap")
    job_timeout_minutes = int(
        develop.split("    timeout-minutes: ", 1)[1].splitlines()[0].strip()
    )
    model_timeout_seconds = int(
        workflow.split('  OPENCODE_RUN_TIMEOUT_SECONDS: "', 1)[1].split('"', 1)[0]
    )
    candidates = [
        line.strip()
        for line in workflow.split("  OPENCODE_MODEL_CANDIDATES: >-\n", 1)[1]
        .split("  OPENCODE_RUN_TIMEOUT_SECONDS:", 1)[0]
        .splitlines()
        if line.strip()
    ]
    orchestration_reserve_seconds = 30 * 60
    required_seconds = (
        len(candidates) * model_timeout_seconds + orchestration_reserve_seconds
    )

    assert len(candidates) > 1
    assert job_timeout_minutes * 60 >= required_seconds, (
        f"job timeout {job_timeout_minutes * 60}s cannot cover {len(candidates)} "
        f"sequential model attempts at {model_timeout_seconds}s plus "
        f"{orchestration_reserve_seconds}s orchestration reserve"
    )
