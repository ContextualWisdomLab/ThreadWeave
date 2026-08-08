"""Regression contracts for Hourly Product Development network policy."""

from pathlib import Path


WORKFLOW = (
    Path(__file__).parents[1] / ".github" / "workflows" / "hourly-product-development.yml"
)


def _job_block(workflow: str, job_name: str, next_job_name: str | None = None) -> str:
    """Return exactly one named workflow job block for contract assertions."""
    block = workflow.split(f"  {job_name}:\n", 1)[1]
    if next_job_name is not None:
        block = block.split(f"  {next_job_name}:\n", 1)[0]
    return block


def _hardened_endpoint_lines(job: str) -> set[str]:
    """Return exact Harden Runner configuration lines from one workflow job."""
    hardening = job.split(
        "      - name: Harden runner and block undeclared egress", 1
    )[1].split("\n\n", 1)[0]
    return {line.strip() for line in hardening.splitlines()}


def test_each_named_hardened_product_phase_allows_the_observed_github_api_alias():
    """Every named GitHub-API phase permits the observed alias while fail-closed."""
    workflow = WORKFLOW.read_text(encoding="utf-8")
    jobs = {
        "develop-product-gap": _job_block(
            workflow, "develop-product-gap", "reverify-product-gap"
        ),
        "reverify-product-gap": _job_block(
            workflow, "reverify-product-gap", "publish-product-gap"
        ),
        "publish-product-gap": _job_block(workflow, "publish-product-gap"),
    }

    for job_name, job in jobs.items():
        endpoint_lines = _hardened_endpoint_lines(job)
        assert "egress-policy: block" in endpoint_lines, job_name
        assert {"api.github.com:443", "cafe.github.com:443"} <= endpoint_lines, job_name
        assert "gh api " in job, job_name

    assert "egress-policy: audit" not in workflow


def test_develop_job_runs_deterministic_gates_before_optional_model_credential():
    """The develop job requires a model credential only after stop gates clear."""
    workflow = WORKFLOW.read_text(encoding="utf-8")
    develop = _job_block(workflow, "develop-product-gap", "reverify-product-gap")
    gate = develop.split(
        "      - name: Enforce the credential and pull-request-first gate", 1
    )[1].split("      - name: Check out the protected default branch", 1)[0]

    credential_gate = 'if [ -z "${NIM_UPSTREAM_API_KEY:-}" ]; then'
    assert gate.index("reason=open_pull_request") < gate.index(credential_gate)
    assert gate.index("reason=release_blocker") < gate.index(credential_gate)
    assert gate.index("reason=dry_run") < gate.index(credential_gate)
    assert gate.index(credential_gate) < gate.index("reason=ready")


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
