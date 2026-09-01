"""Contract tests for the production release workflow."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
HARDEN_RUNNER = "step-security/harden-runner@bf7454d06d71f1098171f2acdf0cd4708d7b5920"
PYPI_PUBLISH = "pypa/gh-action-pypi-publish@cef221092ed1bacb1cc03d23a2d87d1d172e277b"
EXPECTED_RELEASE_ENDPOINTS = {
    "release-readiness": {
        "api.github.com:443",
        "github.com:443",
        "objects.githubusercontent.com:443",
        "pypi.org:443",
        "results-receiver.actions.githubusercontent.com:443",
        "*.actions.githubusercontent.com:443",
        "*.blob.core.windows.net:443",
    },
    "build-release": {
        "api.github.com:443",
        "files.pythonhosted.org:443",
        "github.com:443",
        "objects.githubusercontent.com:443",
        "pypi.org:443",
        "release-assets.githubusercontent.com:443",
        "results-receiver.actions.githubusercontent.com:443",
        "*.actions.githubusercontent.com:443",
        "*.blob.core.windows.net:443",
    },
    "publication-plan": {
        "pypi.org:443",
        "results-receiver.actions.githubusercontent.com:443",
        "*.actions.githubusercontent.com:443",
        "*.blob.core.windows.net:443",
    },
    "attest-release": {
        "api.github.com:443",
        "fulcio.sigstore.dev:443",
        "github.com:443",
        "oauth2.sigstore.dev:443",
        "rekor.sigstore.dev:443",
        "results-receiver.actions.githubusercontent.com:443",
        "token.actions.githubusercontent.com:443",
        "tuf-repo-cdn.sigstore.dev:443",
        "*.actions.githubusercontent.com:443",
        "*.blob.core.windows.net:443",
    },
    "tag-release": {
        "api.github.com:443",
        "github.com:443",
        "results-receiver.actions.githubusercontent.com:443",
        "*.actions.githubusercontent.com:443",
        "*.blob.core.windows.net:443",
    },
    "github-release": {
        "api.github.com:443",
        "github.com:443",
        "objects.githubusercontent.com:443",
        "release-assets.githubusercontent.com:443",
        "results-receiver.actions.githubusercontent.com:443",
        "uploads.github.com:443",
        "*.actions.githubusercontent.com:443",
        "*.blob.core.windows.net:443",
    },
    "publish-pypi": {
        "pypi.org:443",
        "results-receiver.actions.githubusercontent.com:443",
        "upload.pypi.org:443",
        "*.actions.githubusercontent.com:443",
        "*.blob.core.windows.net:443",
    },
    "verify-publication": {
        "files.pythonhosted.org:443",
        "pypi.org:443",
        "results-receiver.actions.githubusercontent.com:443",
        "*.actions.githubusercontent.com:443",
        "*.blob.core.windows.net:443",
    },
}


def _workflow() -> str:
    """Return the release workflow without adding a YAML parser dependency."""

    return WORKFLOW.read_text(encoding="utf-8")


def _job_block(workflow: str, job_name: str, next_job_name: str | None) -> str:
    """Return exactly one release job for fail-closed contract assertions."""

    block = workflow.split(f"  {job_name}:\n", 1)[1]
    if next_job_name is not None:
        block = block.split(f"  {next_job_name}:\n", 1)[0]
    return block


def _hardened_endpoints(job: str) -> set[str]:
    """Return the exact Harden Runner endpoint allowlist for one job."""

    marker = "          allowed-endpoints: >-\n"
    assert marker in job
    endpoint_block = job.split(marker, 1)[1].split("\n      - name:", 1)[0]
    return {line.strip() for line in endpoint_block.splitlines() if line.strip()}


def test_release_waits_for_completed_main_ci_and_keeps_manual_recovery() -> None:
    """Automatic release authority starts from completed main CI, not raw push."""

    workflow = _workflow()
    trigger = workflow.split("permissions:", 1)[0]
    assert "workflow_dispatch:" in trigger
    assert "required: false" in trigger
    assert "workflow_run:" in trigger
    assert 'workflows: ["ci"]' in trigger
    assert "types: [completed]" in trigger
    assert "branches: [main]" in trigger
    assert "\n  push:\n" not in trigger
    assert "pull_request_target" not in trigger
    assert "github.event.workflow_run.head_sha" in workflow
    assert "github.repository == 'ContextualWisdomLab/ThreadWeave'" in workflow
    assert "group: release-${{" in workflow
    assert "cancel-in-progress: false" in workflow


def test_readiness_derives_version_and_exposes_only_boolean_publisher_state() -> None:
    """Version/public presence/publisher availability are facts, never secret material."""

    workflow = _workflow()
    assert workflow.index("  release-readiness:\n") < workflow.index("  build-release:\n")
    readiness = _job_block(workflow, "release-readiness", "build-release")
    assert "PIPY_TOKEN_AVAILABLE: ${{ secrets.PIPY_TOKEN != '' }}" in readiness
    assert "SOURCE_SHA:" in readiness
    assert "tomllib.load" in readiness
    assert 'project["version"]' in readiness
    assert "GITHUB_REF_PROTECTED" in readiness
    assert "https://pypi.org/pypi/threadweave/$release_version/json" in readiness
    assert "publisher_available" in readiness
    assert "public_version_exists" in readiness
    assert "run_release" in readiness
    assert "source_sha" in readiness
    assert "release_required" not in readiness
    assert "environments/pypi" not in readiness
    build = _job_block(workflow, "build-release", "publication-plan")
    assert "needs: release-readiness" in build
    assert "needs.release-readiness.outputs.run_release == 'true'" in build
    assert "ref: ${{ needs.release-readiness.outputs.source_sha }}" in build


def test_release_authority_is_bound_to_integrated_and_pr_security_evidence() -> None:
    """Automatic or manual release work proves the exact accepted source boundary."""

    readiness = _job_block(_workflow(), "release-readiness", "build-release")
    assert "actions: read" in readiness
    assert "pull-requests: read" in readiness
    assert "require_workflow_success" in readiness
    assert 'require_workflow_success "ci" "push" "$SOURCE_SHA"' in readiness
    assert 'require_workflow_success "SAST Semgrep" "push" "$SOURCE_SHA"' in readiness
    assert 'require_workflow_success "ci" "pull_request" "$source_pr_head"' in readiness
    assert 'require_workflow_success "SAST Semgrep" "pull_request" "$source_pr_head"' in readiness
    assert 'require_workflow_success "Security Scan" "pull_request" "$source_pr_head"' in readiness
    assert '"repos/$GITHUB_REPOSITORY/commits/$SOURCE_SHA/pulls"' in readiness
    assert "merge_commit_sha" in readiness
    assert "associated merged pull request" in readiness


def test_partial_publication_is_planned_before_attestation_or_release_side_effects() -> None:
    """Existing files must match the rebuilt bundle and only missing files may upload."""

    workflow = _workflow()
    assert workflow.index("  build-release:\n") < workflow.index("  publication-plan:\n")
    assert workflow.index("  publication-plan:\n") < workflow.index("  attest-release:\n")
    plan = _job_block(workflow, "publication-plan", "attest-release")
    assert "needs: [release-readiness, build-release]" in plan
    assert "SHA256SUMS.txt" in plan
    assert "https://pypi.org/pypi/threadweave/$RELEASE_VERSION/json" in plan
    assert "unexpected public artifact" in plan
    assert "public artifact digest mismatch" in plan
    assert "missing_filenames" in plan
    assert "publication_required=true" in plan
    assert "publication_required=false" in plan
    assert "publisher_available" in plan
    assert "publication-missing-${{ github.run_id }}-${{ github.run_attempt }}" in plan
    assert "if-no-files-found: error" in plan


def test_automatic_existing_version_noops_while_manual_recovery_can_verify() -> None:
    """Routine main CI does not re-tag an existing version; manual recovery may rebuild it."""

    workflow = _workflow()
    readiness = _job_block(workflow, "release-readiness", "build-release")
    assert 'if [ "$GITHUB_EVENT_NAME" = "workflow_run" ] && [ "$public_version_exists" = "true" ]; then' in readiness
    assert "run_release=false" in readiness
    assert 'if [ "$GITHUB_EVENT_NAME" = "workflow_dispatch" ]; then' in readiness
    assert "run_release=true" in readiness
    publish = _job_block(workflow, "publish-pypi", "verify-publication")
    assert "needs.publication-plan.outputs.publication_required == 'true'" in publish
    verify = _job_block(workflow, "verify-publication", None)
    assert "always()" in verify
    assert "needs.publish-pypi.result == 'success' ||" in verify
    assert "needs.publish-pypi.result == 'skipped'" in verify


def test_release_separates_build_attestation_release_and_registry_credentials() -> None:
    """Only the registry publisher can materialize the approved PyPI API token."""

    workflow = _workflow()
    assert workflow.count("id-token: write") == 1
    assert workflow.count("attestations: write") == 1
    assert workflow.count("artifact-metadata: write") == 1
    assert workflow.count("contents: write") == 2
    assert "environment:\n      name: pypi" not in workflow
    assert "PIPY_USERNAME" not in workflow
    assert workflow.count("${{ secrets.PIPY_TOKEN }}") == 1
    assert workflow.count("secrets.PIPY_TOKEN") == 2
    publish = _job_block(workflow, "publish-pypi", "verify-publication")
    assert PYPI_PUBLISH in publish
    assert "password: ${{ secrets.PIPY_TOKEN }}" in publish
    assert "attestations: false" in publish
    assert "print-hash: true" in publish
    assert "id-token: write" not in publish
    assert "skip-existing" not in publish
    assert "publication-missing-${{ github.run_id }}-${{ github.run_attempt }}" in publish


def test_release_uses_full_sha_actions_and_reviewed_artifact_handoffs() -> None:
    """External actions are immutable and artifact handoffs are explicit."""

    workflow = _workflow()
    required_actions = {
        "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
        "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97",
        "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
        "actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c",
        "actions/attest@59d89421af93a897026c735860bf21b6eb4f7b26",
        PYPI_PUBLISH,
        HARDEN_RUNNER,
    }
    assert required_actions <= {
        line.strip().removeprefix("uses: ").split(" #", 1)[0]
        for line in workflow.splitlines()
        if line.strip().startswith("uses: ")
    }
    assert "release-bundle-${{ github.run_id }}-${{ github.run_attempt }}" in workflow
    assert "publication-missing-${{ github.run_id }}-${{ github.run_attempt }}" in workflow
    assert workflow.count("retention-days: 7") >= 2


def test_release_harden_runner_endpoints_are_exact_and_folded() -> None:
    """Every release job gets only its reviewed outbound network surface."""

    workflow = _workflow()
    jobs = (
        ("release-readiness", "build-release"),
        ("build-release", "publication-plan"),
        ("publication-plan", "attest-release"),
        ("attest-release", "tag-release"),
        ("tag-release", "github-release"),
        ("github-release", "publish-pypi"),
        ("publish-pypi", "verify-publication"),
        ("verify-publication", None),
    )
    assert "          allowed-endpoints: |\n" not in workflow
    for job_name, next_job_name in jobs:
        job = _job_block(workflow, job_name, next_job_name)
        assert job.count(HARDEN_RUNNER) == 1, job_name
        assert job.count("          egress-policy: block\n") == 1, job_name
        assert job.count("          allowed-endpoints: >-\n") == 1, job_name
        assert _hardened_endpoints(job) == EXPECTED_RELEASE_ENDPOINTS[job_name], job_name


def test_build_repeats_quality_gates_and_prepares_release_evidence() -> None:
    """The published files are rebuilt from reviewed hash-locked source."""

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


def test_attestation_tag_and_github_release_keep_immutable_evidence() -> None:
    """Attestation and retries never rewrite an existing release identity."""

    workflow = _workflow()
    assert workflow.count(
        "actions/attest@59d89421af93a897026c735860bf21b6eb4f7b26"
    ) == 2
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


def test_publication_is_verified_with_bounded_registry_retry_and_clean_install() -> None:
    """Release completion tolerates propagation only for matching incomplete public state."""

    workflow = _workflow()
    verify = _job_block(workflow, "verify-publication", None)
    assert "SHA256SUMS.txt" in verify
    assert "https://pypi.org/pypi/threadweave/$RELEASE_VERSION/json" in verify
    assert "for attempt in $(seq 1 12); do" in verify
    assert "sleep 10" in verify
    assert "exit 10" in verify
    assert "exit 20" in verify
    assert "PyPI artifact set did not converge" in verify
    assert "python3 -m venv" in verify
    assert 'threadweave==${RELEASE_VERSION}' in verify
    assert "serialize_thread_response" in verify


def test_manual_input_never_becomes_an_unquoted_shell_fragment() -> None:
    """A requested recovery version is compared as data before downstream use."""

    workflow = _workflow()
    assert "REQUESTED_VERSION: ${{ inputs.version || '' }}" in workflow
    run_blocks = workflow.split("run: |")
    assert all(
        "${{ inputs.version }}" not in block.split("\n      - name:", 1)[0]
        for block in run_blocks[1:]
    )
