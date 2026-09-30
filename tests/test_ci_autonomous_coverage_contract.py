"""Coverage contracts for security-sensitive autonomous CI helpers."""

from pathlib import Path


WORKFLOW_DIRECTORY = Path(__file__).parents[1] / ".github" / "workflows"
SECRET_GUARD_TEST = "tests/test_hourly_product_secret_fingerprint.py"
SECRET_GUARD_SOURCE = "scripts/ci/secret_fingerprint_guard.py"


def _workflow(name: str) -> str:
    """Return one workflow as UTF-8 text for dependency-free contract checks."""

    return (WORKFLOW_DIRECTORY / name).read_text(encoding="utf-8")


def test_ci_covers_secret_guard_in_focused_boundary_suite() -> None:
    """CI must execute and report the hourly secret guard at exact 100% coverage."""

    workflow = _workflow("ci.yml")
    focused_step = workflow.split(
        "      - name: Require complete autonomous and release boundary coverage\n", 1
    )[1].split("      - run: coverage run -m pytest -q\n", 1)[0]
    focused_run, focused_report = focused_step.split("          coverage report \\\n", 1)

    assert "coverage run --branch --source=scripts/ci -m pytest -q" in focused_run
    assert SECRET_GUARD_TEST in focused_run
    assert f"--include={SECRET_GUARD_SOURCE}" in focused_report or (
        f",{SECRET_GUARD_SOURCE}" in focused_report
    )
    assert "--fail-under=100" in focused_report


def test_ci_cancels_stale_runs_per_pull_request_or_protected_ref() -> None:
    """PR and protected-ref runs must use stable concurrency identities."""

    workflow = _workflow("ci.yml")
    concurrency = workflow.split("concurrency:\n", 1)[1].split("\nenv:\n", 1)[0]

    assert (
        "group: ci-${{ github.workflow }}-"
        "${{ github.event.pull_request.number || github.ref }}" in concurrency
    )
    assert "github.run_id" not in concurrency
    assert "cancel-in-progress: true" in concurrency
