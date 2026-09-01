"""Regression contract for the approved GitHub-secret PyPI publisher."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"


def _workflow() -> str:
    """Return the production release workflow as reviewed source text."""

    return WORKFLOW.read_text(encoding="utf-8")


def _job(workflow: str, name: str, next_name: str | None) -> str:
    """Return exactly one job block from the dependency-free workflow fixture."""

    block = workflow.split(f"  {name}:\n", 1)[1]
    if next_name is not None:
        block = block.split(f"  {next_name}:\n", 1)[0]
    return block


def test_readiness_checks_token_availability_without_materializing_the_secret() -> None:
    """Publisher availability is decided before tags without exposing token bytes."""

    workflow = _workflow()
    readiness = _job(workflow, "release-readiness", "build-release")
    assert "PIPY_TOKEN_AVAILABLE: ${{ secrets.PIPY_TOKEN != '' }}" in readiness
    assert 'if [ "$PIPY_TOKEN_AVAILABLE" != "true" ]; then' in readiness
    assert "secrets.PIPY_TOKEN }}" not in readiness
    assert "environments/pypi" not in readiness
    assert "required_reviewers" not in readiness
    assert "prevent_self_review" not in readiness


def test_publish_job_uses_only_the_existing_api_token_secret() -> None:
    """The pinned PyPA publisher receives the token only in the publish job."""

    workflow = _workflow()
    publish = _job(workflow, "publish-pypi", None)
    assert "pypa/gh-action-pypi-publish@cef221092ed1bacb1cc03d23a2d87d1d172e277b" in publish
    assert "password: ${{ secrets.PIPY_TOKEN }}" in publish
    assert "PIPY_USERNAME" not in workflow
    assert "environment:\n      name: pypi" not in publish
    assert "id-token: write" not in publish
    assert "token.actions.githubusercontent.com:443" not in publish


def test_token_secret_is_never_materialized_in_shell_or_release_evidence() -> None:
    """No shell, cache, output, or receipt receives the publisher secret value."""

    workflow = _workflow()
    assert workflow.count("${{ secrets.PIPY_TOKEN }}") == 1
    for block in workflow.split("run: |")[1:]:
        shell = block.split("\n      - name:", 1)[0]
        assert "secrets.PIPY_TOKEN" not in shell
    assert "PIPY_TOKEN" not in workflow.split("  publish-pypi:\n", 1)[0].replace(
        "PIPY_TOKEN_AVAILABLE", ""
    )
