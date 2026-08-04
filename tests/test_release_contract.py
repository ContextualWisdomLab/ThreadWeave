"""Tests for the fail-closed ThreadWeave release contract."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import runpy
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


def _project(
    root: Path,
    *,
    version: str = "0.2.0",
    package_version: str | None = None,
) -> None:
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


def _main_args(root: Path, dist: Path, output: Path) -> list[str]:
    """Return canonical CLI arguments for one test release."""

    return [
        "prepare",
        "--root",
        str(root),
        "--version",
        "0.2.0",
        "--dist-dir",
        str(dist),
        "--output-dir",
        str(output),
    ]


def test_validate_release_requires_synchronized_versions_and_notes(
    tmp_path: Path,
) -> None:
    """Project, package, tag, and changelog metadata resolve to one release."""

    _project(tmp_path)

    contract = release.validate_release(tmp_path, "0.2.0")

    assert contract.version == "0.2.0"
    assert contract.tag == "v0.2.0"
    assert contract.release_date == "2026-08-04"
    assert contract.notes == "### Added\n\n- Release capability."


@pytest.mark.parametrize("requested", ["v0.2.0", "0.2", "01.2.0", "0.2.0rc1"])
def test_validate_release_rejects_noncanonical_requested_versions(
    tmp_path: Path,
    requested: str,
) -> None:
    """The release input is a strict PEP 440-compatible SemVer final version."""

    _project(tmp_path)
    with pytest.raises(release.ReleaseContractError, match="canonical three-part"):
        release.validate_release(tmp_path, requested)


def test_validate_release_rejects_version_drift(tmp_path: Path) -> None:
    """Package and project metadata cannot describe different artifacts."""

    _project(tmp_path, package_version="0.1.0")
    with pytest.raises(release.ReleaseContractError, match="version metadata disagrees"):
        release.validate_release(tmp_path, "0.2.0")


def test_validate_release_rejects_requested_project_mismatch(tmp_path: Path) -> None:
    """A workflow input cannot publish a version other than reviewed source."""

    _project(tmp_path, version="0.3.0")
    with pytest.raises(release.ReleaseContractError, match="requested version"):
        release.validate_release(tmp_path, "0.2.0")


@pytest.mark.parametrize(
    ("changelog", "match"),
    [
        ("# Changelog\n\n## Unreleased\n", "release section"),
        (
            "# Changelog\n\n"
            "## [0.2.0] - 2026-08-04\n\n"
            "## [0.2.0] - 2026-08-04\n\n"
            "- duplicate\n",
            "exactly one",
        ),
        (
            "# Changelog\n\n"
            "## [0.2.0] - 2026-08-04\n\n"
            "## [0.1.0] - 2026-07-12\n",
            "release notes are empty",
        ),
        ("# Changelog\n\n## [0.2.0] - 2026-08-04\n\n- TODO\n", "placeholder"),
    ],
)
def test_validate_release_rejects_invalid_release_notes(
    tmp_path: Path,
    changelog: str,
    match: str,
) -> None:
    """Published release notes must be unique, material, and final."""

    _project(tmp_path)
    (tmp_path / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
    with pytest.raises(release.ReleaseContractError, match=match):
        release.validate_release(tmp_path, "0.2.0")


def test_package_version_reader_rejects_missing_or_dynamic_assignment(
    tmp_path: Path,
) -> None:
    """The public runtime version must be one unambiguous string literal."""

    _project(tmp_path)
    init_path = tmp_path / "src/threadweave/__init__.py"

    init_path.write_text("value = 1\n", encoding="utf-8")
    with pytest.raises(release.ReleaseContractError, match="__version__ assignment"):
        release.validate_release(tmp_path, "0.2.0")

    init_path.write_text('__version__ = make_version()\n', encoding="utf-8")
    with pytest.raises(release.ReleaseContractError, match="string literal"):
        release.validate_release(tmp_path, "0.2.0")

    init_path.write_text(
        '__version__ = "0.2.0"\n__version__ = "0.2.0"\n',
        encoding="utf-8",
    )
    with pytest.raises(release.ReleaseContractError, match="exactly one"):
        release.validate_release(tmp_path, "0.2.0")


def test_prepare_release_writes_deterministic_checksums_notes_and_spdx(
    tmp_path: Path,
) -> None:
    """Release evidence binds both artifacts to conformant SPDX metadata."""

    _project(tmp_path)
    dist = _distributions(tmp_path)
    evidence = release.prepare_release(tmp_path, "0.2.0", dist, tmp_path / "release")

    assert evidence.contract.tag == "v0.2.0"
    assert evidence.notes_path.read_text(encoding="utf-8") == (
        "### Added\n\n- Release capability.\n"
    )
    checksum_lines = evidence.checksums_path.read_text(encoding="utf-8").splitlines()
    assert checksum_lines == sorted(
        checksum_lines,
        key=lambda line: line.split("  ", 1)[1],
    )
    assert all(len(line.split("  ", 1)[0]) == 64 for line in checksum_lines)

    sbom = json.loads(evidence.sbom_path.read_text(encoding="utf-8"))
    assert sbom["spdxVersion"] == "SPDX-2.3"
    assert sbom["dataLicense"] == "CC0-1.0"
    assert sbom["name"] == "threadweave-0.2.0-release"
    assert sbom["creationInfo"]["created"] == "2026-08-04T00:00:00Z"
    assert sbom["documentDescribes"] == ["SPDXRef-Package-ThreadWeave"]
    assert "#" not in sbom["documentNamespace"]

    package = sbom["packages"][0]
    assert package["versionInfo"] == "0.2.0"
    assert package["licenseDeclared"] == "Apache-2.0"
    assert package["filesAnalyzed"] is True
    assert package["primaryPackagePurpose"] == "LIBRARY"
    assert package["externalRefs"][0]["referenceLocator"] == (
        "pkg:pypi/threadweave@0.2.0"
    )

    files = sbom["files"]
    assert package["hasFiles"] == [item["SPDXID"] for item in files]
    assert {item["fileName"] for item in files} == {
        "dist/threadweave-0.2.0-py3-none-any.whl",
        "dist/threadweave-0.2.0.tar.gz",
    }
    wheel = next(item for item in files if item["fileName"].endswith(".whl"))
    assert wheel["checksums"] == [
        {"algorithm": "SHA1", "checksumValue": hashlib.sha1(b"wheel").hexdigest()},
        {
            "algorithm": "SHA256",
            "checksumValue": hashlib.sha256(b"wheel").hexdigest(),
        },
    ]
    sha1_values = sorted(
        hashlib.sha1(content).hexdigest() for content in (b"wheel", b"sdist")
    )
    expected_verification = hashlib.sha1(
        "".join(sha1_values).encode("ascii")
    ).hexdigest()
    assert package["packageVerificationCode"] == {
        "packageVerificationCodeValue": expected_verification
    }


def test_prepare_release_rejects_duplicate_or_wrong_version_artifacts(
    tmp_path: Path,
) -> None:
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


def test_prepare_release_refuses_nonempty_or_linked_output(tmp_path: Path) -> None:
    """Stale evidence and symbolic-link output locations fail closed."""

    _project(tmp_path)
    dist = _distributions(tmp_path)
    output = tmp_path / "release"
    output.mkdir()
    (output / "stale").write_text("old", encoding="utf-8")
    with pytest.raises(release.ReleaseContractError, match="absent or empty"):
        release.prepare_release(tmp_path, "0.2.0", dist, output)

    linked_output = tmp_path / "linked-release"
    linked_output.symlink_to(output, target_is_directory=True)
    with pytest.raises(release.ReleaseContractError, match="symbolic link"):
        release.prepare_release(tmp_path, "0.2.0", dist, linked_output)


def test_main_writes_bounded_outputs_and_converts_contract_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The workflow CLI emits scalar outputs and returns 2 for invalid input."""

    _project(tmp_path)
    dist = _distributions(tmp_path)
    output = tmp_path / "release"
    github_output = tmp_path / "github-output"
    args = [*_main_args(tmp_path, dist, output), "--github-output", str(github_output)]

    assert release.main(args) == 0
    assert github_output.read_text(encoding="utf-8").splitlines() == [
        "version=0.2.0",
        "tag=v0.2.0",
        "release_date=2026-08-04",
    ]

    def reject_release(*_args: object) -> None:
        raise release.ReleaseContractError("invalid release")

    monkeypatch.setattr(release, "prepare_release", reject_release)
    assert release.main(_main_args(tmp_path, dist, output)) == 2
    assert "release contract: invalid release" in capsys.readouterr().err


def test_project_reader_handles_sections_and_rejects_version_ambiguity(
    tmp_path: Path,
) -> None:
    """Only one literal version inside the project table is accepted."""

    _project(tmp_path)
    project = tmp_path / "pyproject.toml"
    project.write_text(
        "[build-system]\n"
        "requires = []\n\n"
        "[project]\n"
        "name = 'threadweave'\n"
        "version = '0.2.0'\n\n"
        "[tool.demo]\n"
        "value = 1\n",
        encoding="utf-8",
    )
    assert release.validate_release(tmp_path, "0.2.0").version == "0.2.0"

    project.write_text("[project]\nname = 'threadweave'\n", encoding="utf-8")
    with pytest.raises(release.ReleaseContractError, match="exactly one literal"):
        release.validate_release(tmp_path, "0.2.0")

    project.write_text(
        "[project]\nversion = '0.2.0'\nversion = '0.2.0'\n",
        encoding="utf-8",
    )
    with pytest.raises(release.ReleaseContractError, match="exactly one literal"):
        release.validate_release(tmp_path, "0.2.0")


def test_read_failures_invalid_python_annotated_version_and_invalid_date(
    tmp_path: Path,
) -> None:
    """Malformed or unreadable source metadata cannot reach artifact creation."""

    _project(tmp_path)
    project = tmp_path / "pyproject.toml"
    project.unlink()
    with pytest.raises(
        release.ReleaseContractError,
        match="could not read project metadata",
    ):
        release.validate_release(tmp_path, "0.2.0")

    project.write_text(
        "[project]\nname = 'threadweave'\nversion = '0.2.0'\n",
        encoding="utf-8",
    )
    init_path = tmp_path / "src/threadweave/__init__.py"
    init_path.write_text("__version__ = (\n", encoding="utf-8")
    with pytest.raises(release.ReleaseContractError, match="not valid Python"):
        release.validate_release(tmp_path, "0.2.0")

    init_path.write_text("value: str\n__version__: str = '0.2.0'\n", encoding="utf-8")
    assert release.validate_release(tmp_path, "0.2.0").version == "0.2.0"

    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [0.2.0] - 2026-99-99\n\n- release\n",
        encoding="utf-8",
    )
    with pytest.raises(release.ReleaseContractError, match="valid ISO date"):
        release.validate_release(tmp_path, "0.2.0")


def test_distribution_directory_and_file_type_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing, linked, unreadable, incomplete, and wrong-name artifacts fail."""

    _project(tmp_path)
    missing = tmp_path / "missing"
    with pytest.raises(release.ReleaseContractError, match="one real directory"):
        release.prepare_release(tmp_path, "0.2.0", missing, tmp_path / "release")

    real_dist = _distributions(tmp_path)
    linked_dist = tmp_path / "linked-dist"
    linked_dist.symlink_to(real_dist, target_is_directory=True)
    with pytest.raises(release.ReleaseContractError, match="one real directory"):
        release.prepare_release(tmp_path, "0.2.0", linked_dist, tmp_path / "release")

    original_iterdir = Path.iterdir

    def failing_iterdir(path: Path):
        if path == real_dist:
            raise OSError("unreadable")
        return original_iterdir(path)

    monkeypatch.setattr(Path, "iterdir", failing_iterdir)
    with pytest.raises(release.ReleaseContractError, match="inspect distribution"):
        release.prepare_release(tmp_path, "0.2.0", real_dist, tmp_path / "release")
    monkeypatch.setattr(Path, "iterdir", original_iterdir)

    (real_dist / "threadweave-0.2.0.tar.gz").unlink()
    with pytest.raises(release.ReleaseContractError, match="source archive"):
        release.prepare_release(tmp_path, "0.2.0", real_dist, tmp_path / "release")

    (real_dist / "threadweave-0.2.0.tar.gz").write_bytes(b"sdist")
    wheel = real_dist / "threadweave-0.2.0-py3-none-any.whl"
    wrong_wheel = real_dist / "other-0.2.0-py3-none-any.whl"
    wheel.rename(wrong_wheel)
    with pytest.raises(release.ReleaseContractError, match="reviewed version"):
        release.prepare_release(tmp_path, "0.2.0", real_dist, tmp_path / "release")

    wrong_wheel.rename(wheel)
    original_lstat = Path.lstat

    def failing_lstat(path: Path):
        if path.name.endswith(".whl"):
            raise OSError("gone")
        return original_lstat(path)

    monkeypatch.setattr(Path, "lstat", failing_lstat)
    with pytest.raises(release.ReleaseContractError, match="inspect release artifact"):
        release.prepare_release(tmp_path, "0.2.0", real_dist, tmp_path / "release")


def test_linked_artifact_empty_output_and_no_github_output(tmp_path: Path) -> None:
    """Linked artifacts fail, while an empty evidence directory is reusable."""

    _project(tmp_path)
    dist = _distributions(tmp_path)
    wheel = dist / "threadweave-0.2.0-py3-none-any.whl"
    target = dist / "wheel-target"
    wheel.rename(target)
    wheel.symlink_to(target.name)
    with pytest.raises(release.ReleaseContractError, match="regular non-linked"):
        release.prepare_release(tmp_path, "0.2.0", dist, tmp_path / "release")

    wheel.unlink()
    target.rename(wheel)
    output = tmp_path / "release"
    output.mkdir()
    evidence = release.prepare_release(tmp_path, "0.2.0", dist, output)
    release._write_github_outputs(None, evidence)
    assert evidence.sbom_path.exists()


def test_module_entrypoint_and_main_oserror(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The executable entry point succeeds and converts operating-system errors."""

    _project(tmp_path)
    dist = _distributions(tmp_path)
    previous_argv = list(sys.argv)
    sys.argv = [str(MODULE_PATH), *_main_args(tmp_path, dist, tmp_path / "release")]
    try:
        with pytest.raises(SystemExit, match="0"):
            runpy.run_path(str(MODULE_PATH), run_name="__main__")
    finally:
        sys.argv = previous_argv

    def raise_oserror(*_args: object) -> None:
        raise OSError("disk")

    monkeypatch.setattr(release, "prepare_release", raise_oserror)
    assert release.main(_main_args(tmp_path, dist, tmp_path / "other")) == 2
    assert "release contract: disk" in capsys.readouterr().err
