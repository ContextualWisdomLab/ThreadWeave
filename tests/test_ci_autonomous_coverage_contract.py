"""Coverage contracts for security-sensitive autonomous CI helpers."""

from pathlib import Path


WORKFLOW_DIRECTORY = Path(__file__).parents[1] / ".github" / "workflows"
SECRET_GUARD_TEST = "tests/test_hourly_product_secret_fingerprint.py"
SECRET_GUARD_SOURCE = "scripts/ci/secret_fingerprint_guard.py"


def _workflow(name: str) -> str:
    """Return one workflow as UTF-8 text for dependency-free contract checks."""

    return (WORKFLOW_DIRECTORY / name).read_text(encoding="utf-8")


def test_ci_and_release_cover_secret_guard_in_focused_boundary_suite() -> None:
    """CI and release gates must execute and report the secret guard at 100%."""

    for workflow_name in ("ci.yml", "release.yml"):
        workflow = _workflow(workflow_name)
        assert "coverage run --branch --source=scripts/ci -m pytest -q" in workflow
        assert SECRET_GUARD_TEST in workflow, workflow_name
        assert SECRET_GUARD_SOURCE in workflow, workflow_name
        assert "--fail-under=100" in workflow
