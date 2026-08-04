"""Contract tests for the production release workflow."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"


def _workflow() -> str:
    """Return the release workflow without adding a YAML parser dependency."""

    return WORKFLOW.read_text(encoding="utf-8")


def test_release_is_manual_main_only_and_single_flight() -> None:
    """A release requires an explicit version and one protected main invocation."""

    workflow = _workflow()
    assert "workflow_dispatch:" in workflow
    assert "version:" in workflow
    assert "required: true" in workflow
    assert "pull_request_target" not in workflow
    assert "push:" not in workflow.split("jobs:", 1)[0]
    assert "github.ref == 'refs/heads/main'" in workflow
    assert "github.repository == 'ContextualWisdomLab/ThreadWeave'" in workflow
    assert "group: release-${{ inputs.version }}" in workflow
    assert "cancel-in-progress: false" in workflow


def test_release_separates_build_attestation_tag_release_and_publish_privileges() -> None:
    """Build code never shares a job with publish, tag, or release credentials."""

    workflow = _workflow()
    assert "build-release:" in workflow
    assert "attest-release:" in workflow
    assert "tag-release:" in workflow
    assert "github-release:" in workflow
    assert "publish-pypi:" in workflow
    assert workflow.count("id-token: write") == 2
    assert workflow.count("attestations: write") == 1
    assert workflow.count("artifact-metadata: write") == 1
    assert workflow.count("contents: write") == 2
    assert "environment:\n      name: pypi" in workflow
    assert "username:" not in workflow
    assert "password:" not in workflow
    assert "PYPI_API_TOKEN" not in workflow


def test_release_uses_full_sha_actions_and_reviewed_artifact_handoff() -> None:
    """Every external action is immutable and jobs exchange one named bundle."""

    workflow = _workflow()
    required_actions = {
        "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
        "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97",
        "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
        "actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c",
        "actions/attest@59d89421af93a897026c735860bf21b6eb4f7b26",
        "pypa/gh-action-pypi-publish@cef221092ed1bacb1cc03d23a2d87d1d172e277b",
        "step-security/harden-runner@bf7454d06d71f1098171f2acdf0cd4708d7b5920",
    }
    assert required_actions <= {
        line.strip().removeprefix("uses: ").split(" #", 1)[0]
        for line in workflow.splitlines()
        if line.strip().startswith("uses: ")
    }
    assert "release-bundle-${{ github.run_id }}-${{ github.run_attempt }}" in workflow
    assert workflow.count("actions/download-artifact@") == 4
    assert "retention-days: 7" in workflow


def test_build_repeats_quality_gates_and_prepares_release_evidence() -> None:
    """The released files are rebuilt from reviewed, hash-locked source."""

    workflow = _workflow()
    assert "python -m pip install --require-hashes -r requirements/ci.lock" in workflow
    assert "ruff check ." in workflow
    assert "python -m compileall -q src tests scripts" in workflow
    assert "coverage run -m pytest -q" in workflow
    assert "coverage report" in workflow
    assert "python -m build --no-isolation" in workflow
    assert "python -m pip check" in workflow
    assert "scripts/ci/release_contract.py prepare" in workflow
    assert "SHA256SUMS.txt" in workflow
    assert ".spdx.json" in workflow
    assert "git diff --exit-code" in workflow


def test_attestation_covers_distributions_and_spdx_sbom() -> None:
    """GitHub records both SLSA provenance and the release SBOM."""

    workflow = _workflow()
    assert workflow.count(
        "actions/attest@59d89421af93a897026c735860bf21b6eb4f7b26"
    ) == 2
    assert "subject-path: ${{ runner.temp }}/release-bundle/dist/*" in workflow
    assert "sbom-path: ${{ runner.temp }}/release-bundle/release/" in workflow
    assert "threadweave-${{ needs.build-release.outputs.version }}.spdx.json" in workflow


def test_tag_and_github_release_are_idempotent_and_pypi_publish_is_final() -> None:
    """Retries preserve immutable evidence while PyPI remains fail-closed."""

    workflow = _workflow()
    assert "git ls-remote --tags origin" in workflow
    assert "git tag -a" in workflow
    assert "git push origin" in workflow
    assert "gh release view" in workflow
    assert "gh release create" in workflow
    assert "--verify-tag" in workflow
    assert "expected-release-assets.txt" in workflow
    assert "gh release edit" not in workflow
    assert "--clobber" not in workflow
    assert "skip-existing" not in workflow
    assert "needs: [build-release, attest-release, tag-release, github-release]" in workflow
    assert "attestations: true" in workflow
    assert "print-hash: true" in workflow
    publish_job = workflow.split("publish-pypi:", 1)[1]
    assert publish_job.count("Verify distributions immediately before publication") == 1
    assert "sha256sum --check ../release/SHA256SUMS.txt" in publish_job


def test_workflow_passes_user_input_via_environment_not_shell_interpolation() -> None:
    """The manually supplied version never becomes an unquoted command fragment."""

    workflow = _workflow()
    assert "RELEASE_VERSION: ${{ inputs.version }}" in workflow
    assert "--version \"$RELEASE_VERSION\"" in workflow
    assert 'os.environ["RELEASE_VERSION"]' in workflow
    assert 'threadweave.__version__ == "0.2.0"' not in workflow
    run_blocks = workflow.split("run: |")
    assert all(
        "${{ inputs.version }}" not in block.split("\n      - name:", 1)[0]
        for block in run_blocks[1:]
    )
