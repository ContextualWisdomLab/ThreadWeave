"""Tests for the fail-closed ThreadWeave release contract."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "scripts" / "ci" / "release_contract.py"
SPEC = importlib.util.spec_from_file_location("threadweave_release_contract", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
release = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = release
SPEC.loader.exec_module(release)


def _project(root: Path, *, version: str = "0.2.0", package_version: str | None = None) -> None:
    """Create one minimal release source tree for contract tests."""
    (root / "src/threadweave").mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        "[project]\n"
        'name = "threadweave"\n'
        f'version = "{version}"\n',
        encoding="utf-8",
    )
    actual_package_version = version if package_version is None else package_version
    (root / "src/threadweave/__init__.py").write_text(
        f'__version__ = "{actual_package_version}"\n',
        encoding="utf-8",
    )
    (root / "CHANGELOG.md").write_text(
        "# Changelog\n\n"
        "## Unreleased\n\n"
        f"## [{version}] - 2026-08-04\n\n"
        "### Added\n\n"
        "- Release capability.\n\n"
        "## [0.1.0] - 2026-07-12\n",
        encoding="utf-8",
    )


def _distributions(root: Path, version: str = "0.2.0") -> Path:
    """Create representative wheel and source distributions."""
    dist = root / "dist"
    dist.mkdir()
    (dist / f"threadweave-{version}-py3-none-any.whl").write_bytes(b"wheel")
    (dist / f"threadweave-{version}.tar.gz").write_bytes(b"sdist")
    return dist


def test_validate_release_requires_synchronized_versions_and_notes(tmp_path: Path):
    """Project, package, tag, and changelog metadata resolve to one release."""
    _project(tmp_path)

    contract = release.validate_release(tmp_path, "0.2.0")

    assert contract.version == "0.2.0"
    assert contract.tag == "v0.2.0"
    assert contract.release_date == "2026-08-04"
    assert contract.notes == "### Added\n\n- Release capability."


@pytest.mark.parametrize(
    ("requested", "match"),
    [
        ("v0.2.0", "canonical three-part"),
        ("0.2", "canonical three-part"),
        ("01.2.0", "canonical three-part"),
        ("0.2.0rc1", "canonical three-part"),
    ],
)
def test_validate_release_rejects_noncanonical_requested_versions(
    tmp_path: Path,
    requested: str,
    match: str,
):
    """The release input is a strict PEP 440-compatible SemVer final version."""
    _project(tmp_path)
    with pytest.raises(release.ReleaseContractError, match=match):
        release.validate_release(tmp_path, requested)


def test_validate_release_rejects_version_drift(tmp_path: Path):
    """Package and project metadata cannot describe different artifacts."""
    _project(tmp_path, package_version="0.1.0")
    with pytest.raises(release.ReleaseContractError, match="version metadata disagrees"):
        release.validate_release(tmp_path, "0.2.0")


def test_validate_release_rejects_requested_project_mismatch(tmp_path: Path):
    """A workflow input cannot publish a version other than the reviewed source."""
    _project(tmp_path, version="0.3.0")
    with pytest.raises(release.ReleaseContractError, match="requested version"):
        release.validate_release(tmp_path, "0.2.0")


@pytest.mark.parametrize(
    ("changelog", "match"),
    [
        ("# Changelog\n\n## Unreleased\n", "release section"),
        (
            "# Changelog\n\n## [0.2.0] - 2026-08-04\n\n"
            "## [0.2.0] - 2026-08-04\n\n- duplicate\n",
            "exactly one",
        ),
        (
            "# Changelog\n\n## [0.2.0] - 2026-08-04\n\n"
            "## [0.1.0] - 2026-07-12\n",
            "release notes are empty",
        ),
        (
            "# Changelog\n\n## [0.2.0] - 2026-08-04\n\n- TODO\n",
            "placeholder",
        ),
    ],
)
def test_validate_release_rejects_missing_duplicate_empty_or_placeholder_notes(
    tmp_path: Path,
    changelog: str,
    match: str,
):
    """Published release notes must be unique, material, and final."""
    _project(tmp_path)
    (tmp_path / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
    with pytest.raises(release.ReleaseContractError, match=match):
        release.validate_release(tmp_path, "0.2.0")


def test_package_version_reader_rejects_missing_or_dynamic_assignment(tmp_path: Path):
    """The public runtime version must be one unambiguous string literal."""
    _project(tmp_path)
    init_path = tmp_path / "src/threadweave/__init__.py"

    init_path.write_text("value = 1\n", encoding="utf-8")
    with pytest.raises(release.ReleaseContractError, match="__version__ assignment"):
        release.validate_release(tmp_path, "0.2.0")

    init_path.write_text('__version__ = make_version()\n', encoding="utf-8")
    with pytest.raises(release.ReleaseContractError, match="string literal"):
        release.validate_release(tmp_path, "0.2.0")

    init_path.write_text('__version__ = "0.2.0"\n__version__ = "0.2.0"\n', encoding="utf-8")
    with pytest.raises(release.ReleaseContractError, match="exactly one"):
        release.validate_release(tmp_path, "0.2.0")


def test_prepare_release_writes_deterministic_checksums_notes_and_spdx(tmp_path: Path):
    """Release evidence binds both artifacts to deterministic SPDX metadata."""
    _project(tmp_path)
    dist = _distributions(tmp_path)
    output = tmp_path / "release"

    evidence = release.prepare_release(tmp_path, "0.2.0", dist, output)

    assert evidence.contract.tag == "v0.2.0"
    assert evidence.notes_path.read_text(encoding="utf-8") == (
        "### Added\n\n- Release capability.\n"
    )
    checksum_lines = evidence.checksums_path.read_text(encoding="utf-8").splitlines()
    assert checksum_lines == sorted(checksum_lines, key=lambda line: line.split("  ", 1)[1])
    assert all(len(line.split("  ", 1)[0]) == 64 for line in checksum_lines)

    sbom = json.loads(evidence.sbom_path.read_text(encoding="utf-8"))
    assert sbom["spdxVersion"] == "SPDX-2.3"
    assert sbom["dataLicense"] == "CC0-1.0"
    assert sbom["name"] == "threadweave-0.2.0-release"
    assert sbom["creationInfo"]["created"] == "2026-08-04T00:00:00Z"
    package = sbom["packages"][0]
    assert package["versionInfo"] == "0.2.0"
    assert package["licenseDeclared"] == "Apache-2.0"
    assert package["externalRefs"][0]["referenceLocator"] == (
        "pkg:pypi/threadweave@0.2.0"
    )
    assert {item["fileName"] for item in sbom["files"]} == {
        "dist/threadweave-0.2.0-py3-none-any.whl",
        "dist/threadweave-0.2.0.tar.gz",
    }
    expected_digest = hashlib.sha256(b"wheel").hexdigest()
    wheel = next(item for item in sbom["files"] if item["fileName"].endswith(".whl"))
    assert wheel["checksums"] == [
        {"algorithm": "SHA256", "checksumValue": expected_digest}
    ]


def test_prepare_release_rejects_missing_duplicate_or_wrong_version_artifacts(
    tmp_path: Path,
):
    """Exactly one wheel and one sdist for the reviewed version are publishable."""
    _project(tmp_path)
    dist = _distributions(tmp_path)
    (dist / "threadweave-0.2.0-extra.whl").write_bytes(b"duplicate")
    with pytest.raises(release.ReleaseContractError, match="exactly one wheel"):
        release.prepare_release(tmp_path, "0.2.0", dist, tmp_path / "release")

    (dist / "threadweave-0.2.0-extra.whl").unlink()
    (dist / "threadweave-0.2.0.tar.gz").rename(dist / "threadweave-0.3.0.tar.gz")
    with pytest.raises(release.ReleaseContractError, match="reviewed version"):
        release.prepare_release(tmp_path, "0.2.0", dist, tmp_path / "release")


def test_prepare_release_refuses_nonempty_output_directory(tmp_path: Path):
    """Stale evidence cannot be mixed into a new release bundle."""
    _project(tmp_path)
    dist = _distributions(tmp_path)
    output = tmp_path / "release"
    output.mkdir()
    (output / "stale").write_text("old", encoding="utf-8")
    with pytest.raises(release.ReleaseContractError, match="output directory"):
        release.prepare_release(tmp_path, "0.2.0", dist, output)


def test_main_prepare_writes_github_outputs_and_converts_contract_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    """The workflow CLI emits bounded outputs and returns 2 for invalid input."""
    _project(tmp_path)
    dist = _distributions(tmp_path)
    output = tmp_path / "release"
    github_output = tmp_path / "github-output"

    assert release.main(
        [
            "prepare",
            "--root",
            str(tmp_path),
            "--version",
            "0.2.0",
            "--dist-dir",
            str(dist),
            "--output-dir",
            str(output),
            "--github-output",
            str(github_output),
        ]
    ) == 0
    emitted = github_output.read_text(encoding="utf-8")
    assert "version=0.2.0\n" in emitted
    assert "tag=v0.2.0\n" in emitted
    assert "release_date=2026-08-04\n" in emitted

    monkeypatch.setattr(release, "prepare_release", lambda *_args: (_ for _ in ()).throw(
        release.ReleaseContractError("invalid release")
    ))
    assert release.main(
        [
            "prepare",
            "--root",
            str(tmp_path),
            "--version",
            "0.2.0",
            "--dist-dir",
            str(dist),
            "--output-dir",
            str(output),
        ]
    ) == 2
    assert "release contract: invalid release" in capsys.readouterr().err
