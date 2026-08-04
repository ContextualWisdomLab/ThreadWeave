"""Coverage tests for release-contract error and compatibility paths."""

from __future__ import annotations

import importlib.util
import runpy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "scripts" / "ci" / "release_contract.py"
SPEC = importlib.util.spec_from_file_location(
    "threadweave_release_contract_coverage", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
release = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = release
SPEC.loader.exec_module(release)


def _project(root: Path, version: str = "0.2.0") -> None:
    """Write one minimal synchronized project and release section."""
    (root / "src/threadweave").mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "threadweave"\nversion = "{version}"\n',
        encoding="utf-8",
    )
    (root / "src/threadweave/__init__.py").write_text(
        f'__version__ = "{version}"\n', encoding="utf-8"
    )
    (root / "CHANGELOG.md").write_text(
        f"# Changelog\n\n## [{version}] - 2026-08-04\n\n- Material release.\n",
        encoding="utf-8",
    )


def _distributions(root: Path, version: str = "0.2.0") -> Path:
    """Write one wheel and one source distribution."""
    dist = root / "dist"
    dist.mkdir()
    (dist / f"threadweave-{version}-py3-none-any.whl").write_bytes(b"wheel")
    (dist / f"threadweave-{version}.tar.gz").write_bytes(b"sdist")
    return dist


def test_project_metadata_read_and_type_failures(tmp_path: Path):
    """Missing, malformed, non-text, and noncanonical project versions fail."""
    with pytest.raises(release.ReleaseContractError, match="project version"):
        release.validate_release(tmp_path, "0.2.0")

    (tmp_path / "pyproject.toml").write_text("not toml =", encoding="utf-8")
    with pytest.raises(release.ReleaseContractError, match="project version"):
        release.validate_release(tmp_path, "0.2.0")

    (tmp_path / "pyproject.toml").write_text(
        "[project]\nversion = 2\n", encoding="utf-8"
    )
    with pytest.raises(release.ReleaseContractError, match="must be text"):
        release.validate_release(tmp_path, "0.2.0")

    _project(tmp_path, "0.2")
    with pytest.raises(release.ReleaseContractError, match="canonical three-part"):
        release.validate_release(tmp_path, "0.2.0")


def test_package_source_read_parse_and_annotated_assignment_paths(tmp_path: Path):
    """Package version extraction supports a literal annotation and rejects damage."""
    _project(tmp_path)
    init_path = tmp_path / "src/threadweave/__init__.py"

    init_path.unlink()
    with pytest.raises(release.ReleaseContractError, match="readable Python"):
        release.validate_release(tmp_path, "0.2.0")

    init_path.write_text("this is not Python !", encoding="utf-8")
    with pytest.raises(release.ReleaseContractError, match="readable Python"):
        release.validate_release(tmp_path, "0.2.0")

    init_path.write_text('__version__: str = "0.2.0"\n', encoding="utf-8")
    assert release.validate_release(tmp_path, "0.2.0").version == "0.2.0"

    init_path.write_text('__version__: str\n', encoding="utf-8")
    with pytest.raises(release.ReleaseContractError, match="exactly one"):
        release.validate_release(tmp_path, "0.2.0")

    init_path.write_text(
        'other = "ignored"\nother: str = "ignored"\n__version__ = "0.2.0"\n',
        encoding="utf-8",
    )
    assert release.validate_release(tmp_path, "0.2.0").tag == "v0.2.0"


def test_changelog_read_failure_and_terminal_section(tmp_path: Path):
    """Unreadable notes fail while a material final section needs no successor."""
    _project(tmp_path)
    changelog = tmp_path / "CHANGELOG.md"
    changelog.unlink()
    with pytest.raises(release.ReleaseContractError, match="not readable"):
        release.validate_release(tmp_path, "0.2.0")

    changelog.write_text(
        "# Changelog\n\n## [0.2.0] - 2026-08-04\n\n- Final section.\n",
        encoding="utf-8",
    )
    assert release.validate_release(tmp_path, "0.2.0").notes == "- Final section."


def test_distribution_directory_and_duplicate_sdist_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """Unreadable directories and ambiguous source archives fail closed."""
    _project(tmp_path)
    with pytest.raises(release.ReleaseContractError, match="not readable"):
        release.prepare_release(
            tmp_path,
            "0.2.0",
            tmp_path / "missing-dist",
            tmp_path / "release",
        )

    dist = _distributions(tmp_path)
    wheel = dist / "threadweave-0.2.0-py3-none-any.whl"
    sdist = dist / "threadweave-0.2.0.tar.gz"
    original_iterdir = Path.iterdir

    def duplicated(path: Path):
        """Return a duplicated sdist only for the test distribution directory."""
        if path == dist:
            return iter((wheel, sdist, sdist))
        return original_iterdir(path)

    monkeypatch.setattr(Path, "iterdir", duplicated)
    with pytest.raises(release.ReleaseContractError, match="source distribution"):
        release.prepare_release(tmp_path, "0.2.0", dist, tmp_path / "release")


def test_artifact_read_and_evidence_write_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """Unreadable artifacts and unwritable evidence never produce partial success."""
    _project(tmp_path)
    dist = _distributions(tmp_path)
    wheel = dist / "threadweave-0.2.0-py3-none-any.whl"
    original_open = Path.open

    def fail_artifact(path: Path, *args, **kwargs):
        """Reject only the representative wheel read."""
        if path == wheel:
            raise OSError("unreadable")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fail_artifact)
    with pytest.raises(release.ReleaseContractError, match="cannot read"):
        release.prepare_release(tmp_path, "0.2.0", dist, tmp_path / "release")

    monkeypatch.setattr(Path, "open", original_open)
    original_write_text = Path.write_text

    def fail_evidence(path: Path, *args, **kwargs):
        """Reject release evidence while preserving source reads."""
        if path.parent.name == "release":
            raise OSError("unwritable")
        return original_write_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_evidence)
    with pytest.raises(release.ReleaseContractError, match="could not be written"):
        release.prepare_release(tmp_path, "0.2.0", dist, tmp_path / "release")


def test_output_directory_shape_and_os_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """An empty directory is reusable; files and OS failures are rejected."""
    empty = tmp_path / "empty"
    empty.mkdir()
    release._require_empty_output(empty)

    output_file = tmp_path / "output-file"
    output_file.write_text("not a directory", encoding="utf-8")
    with pytest.raises(release.ReleaseContractError, match="must be empty"):
        release._require_empty_output(output_file)

    original_exists = Path.exists

    def fail_exists(path: Path) -> bool:
        """Simulate an operating-system error at the output boundary."""
        if path.name == "broken-output":
            raise OSError("broken")
        return original_exists(path)

    monkeypatch.setattr(Path, "exists", fail_exists)
    with pytest.raises(release.ReleaseContractError, match="not usable"):
        release._require_empty_output(tmp_path / "broken-output")


def test_github_output_optional_and_unwritable_paths(tmp_path: Path):
    """Output emission is optional and converts filesystem errors to contract errors."""
    _project(tmp_path)
    dist = _distributions(tmp_path)
    evidence = release.prepare_release(tmp_path, "0.2.0", dist, tmp_path / "release")

    assert release._write_outputs(None, evidence) is None
    with pytest.raises(release.ReleaseContractError, match="not writable"):
        release._write_outputs(tmp_path / "missing" / "github-output", evidence)


def test_main_success_without_github_output_and_module_entrypoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """Both CLI success and executable-module failure paths are deterministic."""
    _project(tmp_path)
    dist = _distributions(tmp_path)
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
            str(tmp_path / "release"),
        ]
    ) == 0

    previous = list(sys.argv)
    sys.argv = [
        str(MODULE_PATH),
        "prepare",
        "--root",
        str(tmp_path),
        "--version",
        "invalid",
        "--dist-dir",
        str(dist),
        "--output-dir",
        str(tmp_path / "other"),
    ]
    try:
        with pytest.raises(SystemExit, match="2"):
            runpy.run_path(str(MODULE_PATH), run_name="__main__")
    finally:
        sys.argv = previous
