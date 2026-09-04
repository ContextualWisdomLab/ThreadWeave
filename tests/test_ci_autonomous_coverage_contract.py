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


def test_ci_cancels_only_superseded_heads_for_the_same_pull_request() -> None:
    """PR runs share one group while non-PR runs remain isolated."""

    workflow = _workflow("ci.yml")

    assert (
        "group: ${{ github.workflow }}-${{ github.repository }}-"
        "${{ github.event.pull_request.number || github.run_id }}" in workflow
    )
    assert "cancel-in-progress: true" in workflow
