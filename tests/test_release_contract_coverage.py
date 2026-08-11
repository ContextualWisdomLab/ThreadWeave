"""Compatibility and operating-system boundary tests for release preparation."""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "scripts" / "ci" / "release_contract.py"
SPEC = importlib.util.spec_from_file_location(
    "threadweave_release_contract_compatibility", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
release = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = release
SPEC.loader.exec_module(release)


def _project(root: Path) -> None:
    """Write a minimal synchronized 0.2.0 project for boundary tests."""

    (root / "src/threadweave").mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        '[project]\nname = "threadweave"\nversion = "0.2.0"\n',
        encoding="utf-8",
    )
    (root / "src/threadweave/__init__.py").write_text(
        '__version__ = "0.2.0"\n', encoding="utf-8"
    )
    (root / "CHANGELOG.md").write_text(
        "# Changelog\n\n"
        "## Unreleased\n\n"
        "## [0.2.0] - 2026-08-04\n\n"
        "- Material release.\n",
        encoding="utf-8",
    )


def _distributions(root: Path) -> Path:
    """Write one wheel and one source archive for the reviewed version."""

    dist = root / "dist"
    dist.mkdir()
    (dist / "threadweave-0.2.0-py3-none-any.whl").write_bytes(b"wheel")
    (dist / "threadweave-0.2.0.tar.gz").write_bytes(b"sdist")
    return dist


def test_release_contract_source_is_valid_python_310() -> None:
    """The release boundary must remain importable on the package's version floor."""

    source = MODULE_PATH.read_text(encoding="utf-8")
    ast.parse(source, filename=str(MODULE_PATH), feature_version=(3, 10))


def test_validate_release_rejects_material_unreleased_notes(tmp_path: Path) -> None:
    """A final release cannot silently omit reviewed Unreleased changes from its notes."""

    _project(tmp_path)
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        changelog.read_text(encoding="utf-8").replace(
            "## Unreleased\n\n",
            "## Unreleased\n\n- Not represented in the final section.\n\n",
        ),
        encoding="utf-8",
    )

    with pytest.raises(release.ReleaseContractError, match="material Unreleased"):
        release.validate_release(tmp_path, "0.2.0")


def test_main_converts_unwritable_github_output_to_exit_two(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A downstream-output failure is reported without partial workflow success."""

    _project(tmp_path)
    dist = _distributions(tmp_path)
    result = release.main(
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
            "--github-output",
            str(tmp_path / "missing" / "github-output"),
        ]
    )

    assert result == 2
    assert "release contract:" in capsys.readouterr().err


def test_validate_release_rejects_symlinked_source_metadata(tmp_path: Path) -> None:
    """Release metadata must not escape the reviewed source tree through a link."""

    repository = tmp_path / "repository"
    _project(repository)
    outside_changelog = tmp_path / "outside-changelog.md"
    outside_changelog.write_text(
        "# Changelog\n\n"
        "## Unreleased\n\n"
        "## [0.2.0] - 2026-08-04\n\n"
        "- Unreviewed external release notes.\n",
        encoding="utf-8",
    )
    changelog = repository / "CHANGELOG.md"
    changelog.unlink()
    changelog.symlink_to(outside_changelog)

    with pytest.raises(release.ReleaseContractError, match="regular file inside release root"):
        release.validate_release(repository, "0.2.0")
