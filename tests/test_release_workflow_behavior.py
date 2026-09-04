"""Behavioral tests for executable state logic embedded in the release workflow."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap


ROOT = Path(__file__).parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"


def _workflow() -> str:
    """Return the production release workflow text used by the behavioral tests."""

    return WORKFLOW.read_text(encoding="utf-8")


def _embedded_python(step_name: str, *, invocation: str = "python3 - <<'PY'") -> str:
    """Extract the executable Python heredoc from one named production workflow step."""

    workflow = _workflow()
    step = workflow.split(f"      - name: {step_name}\n", 1)[1]
    step = step.split("\n      - name:", 1)[0]
    body = step.split(invocation + "\n", 1)[1].split("\n          PY", 1)[0]
    return textwrap.dedent(body)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _release_bundle(tmp_path: Path) -> tuple[dict[str, bytes], dict[str, str]]:
    """Create the reviewed two-distribution bundle consumed by production workflow code."""

    files = {
        "threadweave-0.2.0-py3-none-any.whl": b"reviewed-wheel",
        "threadweave-0.2.0.tar.gz": b"reviewed-sdist",
    }
    digests = {name: _sha256(data) for name, data in files.items()}
    bundle = tmp_path / "release-bundle"
    (bundle / "dist").mkdir(parents=True)
    (bundle / "release").mkdir()
    for name, data in files.items():
        (bundle / "dist" / name).write_bytes(data)
    manifest = "".join(f"{digests[name]}  {name}\n" for name in sorted(files))
    (bundle / "release" / "SHA256SUMS.txt").write_text(manifest, encoding="utf-8")
    return files, digests


def _run_embedded(code: str, tmp_path: Path, **env_overrides: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update({"RUNNER_TEMP": str(tmp_path), **env_overrides})
    return subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def test_publication_plan_emits_real_outputs_and_materializes_only_missing_files(
    tmp_path: Path,
) -> None:
    """Execute the shipped planner and prove its outputs reflect the observed registry set."""

    files, digests = _release_bundle(tmp_path)
    wheel = "threadweave-0.2.0-py3-none-any.whl"
    sdist = "threadweave-0.2.0.tar.gz"
    (tmp_path / "pypi-version.json").write_text(
        json.dumps(
            {
                "urls": [
                    {"filename": wheel, "digests": {"sha256": digests[wheel]}},
                ]
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "github-output.txt"
    code = _embedded_python(
        "Compare public artifacts and prepare only missing distributions",
        invocation="PYPI_STATUS=\"$status\" python3 - <<'PY'",
    )

    result = _run_embedded(
        code,
        tmp_path,
        PYPI_STATUS="200",
        PUBLISHER_AVAILABLE="true",
        GITHUB_OUTPUT=str(output),
    )

    assert result.returncode == 0, result.stderr
    assert output.read_text(encoding="utf-8").splitlines() == [
        "publication_required=true",
        f'missing_filenames=["{sdist}"]',
    ]
    publish_dir = tmp_path / "publication-missing"
    assert sorted(path.name for path in publish_dir.iterdir()) == [sdist]
    assert (publish_dir / sdist).read_bytes() == files[sdist]


def test_publication_plan_emits_false_only_for_complete_matching_publication(
    tmp_path: Path,
) -> None:
    """A complete matching registry set executes the production false/no-upload transition."""

    _, digests = _release_bundle(tmp_path)
    (tmp_path / "pypi-version.json").write_text(
        json.dumps(
            {
                "urls": [
                    {"filename": name, "digests": {"sha256": digest}}
                    for name, digest in sorted(digests.items())
                ]
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "github-output.txt"
    code = _embedded_python(
        "Compare public artifacts and prepare only missing distributions",
        invocation="PYPI_STATUS=\"$status\" python3 - <<'PY'",
    )

    result = _run_embedded(
        code,
        tmp_path,
        PYPI_STATUS="200",
        PUBLISHER_AVAILABLE="false",
        GITHUB_OUTPUT=str(output),
    )

    assert result.returncode == 0, result.stderr
    assert output.read_text(encoding="utf-8").splitlines() == [
        "publication_required=false",
        "missing_filenames=[]",
    ]
    assert not (tmp_path / "publication-missing").exists()


def test_publication_plan_fails_closed_on_public_digest_mismatch(tmp_path: Path) -> None:
    """The executed planner rejects an immutable public file whose digest is not reviewed."""

    _, digests = _release_bundle(tmp_path)
    wheel = "threadweave-0.2.0-py3-none-any.whl"
    (tmp_path / "pypi-version.json").write_text(
        json.dumps(
            {
                "urls": [
                    {"filename": wheel, "digests": {"sha256": "0" * 64}},
                ]
            }
        ),
        encoding="utf-8",
    )
    code = _embedded_python(
        "Compare public artifacts and prepare only missing distributions",
        invocation="PYPI_STATUS=\"$status\" python3 - <<'PY'",
    )

    result = _run_embedded(
        code,
        tmp_path,
        PYPI_STATUS="200",
        PUBLISHER_AVAILABLE="true",
        GITHUB_OUTPUT=str(tmp_path / "github-output.txt"),
    )

    assert result.returncode != 0
    assert "public artifact digest mismatch" in result.stderr
    assert digests[wheel] not in result.stdout


def test_public_verifier_exits_10_for_matching_incomplete_registry_state(tmp_path: Path) -> None:
    """Execute the shipped verifier and prove retryable incomplete state uses exit code 10."""

    _, digests = _release_bundle(tmp_path)
    wheel = "threadweave-0.2.0-py3-none-any.whl"
    (tmp_path / "threadweave-pypi.json").write_text(
        json.dumps(
            {
                "urls": [
                    {"filename": wheel, "digests": {"sha256": digests[wheel]}},
                ]
            }
        ),
        encoding="utf-8",
    )
    code = _embedded_python("Verify PyPI filenames and SHA-256 digests with propagation retry")

    result = _run_embedded(code, tmp_path)

    assert result.returncode == 10


def test_public_verifier_exits_20_for_immutable_mismatch(tmp_path: Path) -> None:
    """Execute the shipped verifier and prove digest corruption is terminal, not retryable."""

    _release_bundle(tmp_path)
    wheel = "threadweave-0.2.0-py3-none-any.whl"
    (tmp_path / "threadweave-pypi.json").write_text(
        json.dumps(
            {
                "urls": [
                    {"filename": wheel, "digests": {"sha256": "f" * 64}},
                ]
            }
        ),
        encoding="utf-8",
    )
    code = _embedded_python("Verify PyPI filenames and SHA-256 digests with propagation retry")

    result = _run_embedded(code, tmp_path)

    assert result.returncode == 20
    assert "public artifact digest mismatch" in result.stderr


def test_public_verifier_succeeds_only_for_exact_reviewed_artifact_set(tmp_path: Path) -> None:
    """Execute the shipped verifier and prove the exact reviewed filename/digest set is GREEN."""

    _, digests = _release_bundle(tmp_path)
    (tmp_path / "threadweave-pypi.json").write_text(
        json.dumps(
            {
                "urls": [
                    {"filename": name, "digests": {"sha256": digest}}
                    for name, digest in sorted(digests.items())
                ]
            }
        ),
        encoding="utf-8",
    )
    code = _embedded_python("Verify PyPI filenames and SHA-256 digests with propagation retry")

    result = _run_embedded(code, tmp_path)

    assert result.returncode == 0, result.stderr
