"""Regression contracts for Hourly Product Development network policy."""

from pathlib import Path


WORKFLOW = (
    Path(__file__).parents[1] / ".github" / "workflows" / "hourly-product-development.yml"
)


def test_each_hardened_product_phase_allows_the_observed_github_api_alias():
    """Every hardened phase using GitHub API must permit its observed DNS alias."""
    workflow = WORKFLOW.read_text(encoding="utf-8")
    phases = workflow.split("      - name: Harden runner and block undeclared egress")[1:]

    assert len(phases) == 3
    for phase in phases:
        endpoint_block = phase.split("\n\n", 1)[0]
        assert "egress-policy: block" in endpoint_block
        assert "api.github.com:443" in endpoint_block
        assert "cafe.github.com:443" in endpoint_block

    assert "egress-policy: audit" not in workflow


def test_deterministic_gates_run_before_the_optional_model_credential_gate():
    """A model credential is required only after deterministic stop gates clear."""
    workflow = WORKFLOW.read_text(encoding="utf-8")
    gate = workflow.split("      - name: Enforce the credential and pull-request-first gate", 1)[
        1
    ].split("      - name: Check out the protected default branch", 1)[0]

    credential_gate = 'if [ -z "${NIM_UPSTREAM_API_KEY:-}" ]; then'
    assert gate.index("reason=open_pull_request") < gate.index(credential_gate)
    assert gate.index("reason=release_blocker") < gate.index(credential_gate)
    assert gate.index("reason=dry_run") < gate.index(credential_gate)
    assert gate.index(credential_gate) < gate.index("reason=ready")
