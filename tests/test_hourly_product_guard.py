"""Tests for the fail-closed autonomous product patch boundary."""

from __future__ import annotations

import argparse
import base64
import importlib.util
import json
import os
import subprocess
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[1] / "scripts" / "ci" / "hourly_product_guard.py"
SPEC = importlib.util.spec_from_file_location("hourly_product_guard", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


def _run(*args: str, cwd: Path) -> str:
    """Run one local Git command and return stripped text output."""

    return subprocess.run(
        list(args), cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    """Create source, immutable baseline, agent workspace, and base-SHA file."""

    source = tmp_path / "source"
    source.mkdir()
    _run("git", "init", "-q", cwd=source)
    _run("git", "config", "user.name", "Guard Test", cwd=source)
    _run("git", "config", "user.email", "guard@example.invalid", cwd=source)
    (source / "README.md").write_text("before\n", encoding="utf-8")
    (source / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
    (source / "src/threadweave").mkdir(parents=True)
    (source / "src/threadweave/__init__.py").write_text(
        '"""Package."""\n', encoding="utf-8"
    )
    (source / "tests").mkdir()
    (source / "tests/test_base.py").write_text("def test_base():\n    assert True\n")
    _run("git", "add", ".", cwd=source)
    _run("git", "commit", "-qm", "base", cwd=source)

    baseline = tmp_path / "baseline"
    workspace = tmp_path / "workspace"
    _run(
        "git", "clone", "-q", "--local", "--no-hardlinks",
        str(source), str(baseline), cwd=tmp_path,
    )
    _run(
        "git", "clone", "-q", "--local", "--no-hardlinks",
        str(source), str(workspace), cwd=tmp_path,
    )
    (workspace / ".git").rename(tmp_path / "workspace-git")
    base_file = tmp_path / "base-sha"
    base_file.write_text(_run("git", "rev-parse", "HEAD", cwd=source) + "\n")
    return source, baseline, workspace, base_file


def _capture(tmp_path: Path, baseline: Path, workspace: Path, base_file: Path):
    """Capture a proposal and return its three artifact paths."""

    patch = tmp_path / "change.patch"
    stat_file = tmp_path / "change.stat"
    proposal = tmp_path / "proposal.json"
    result = guard.capture(
        argparse.Namespace(
            workspace=workspace,
            baseline=baseline,
            base_sha_file=base_file,
            patch_file=patch,
            stat_file=stat_file,
            proposal_file=proposal,
        )
    )
    return result, patch, stat_file, proposal


def test_capture_and_apply_round_trip_with_sanitized_metadata(tmp_path: Path):
    """A bounded textual change survives capture and fresh-checkout application."""

    source, baseline, workspace, base_file = _fixture(tmp_path)
    (workspace / "README.md").write_text("after\n", encoding="utf-8")
    (workspace / "tests/test_new.py").write_text("def test_new():\n    assert 2 + 2 == 4\n")
    (workspace / guard.PROPOSAL_FILENAME).write_text(
        "# Improve deterministic docs\r\n\r\nEvidence and residual risk.\r\n",
        encoding="utf-8",
    )

    result, patch, stat_file, proposal_file = _capture(
        tmp_path, baseline, workspace, base_file
    )

    assert result == 0
    assert stat_file.read_text(encoding="utf-8")
    proposal = json.loads(proposal_file.read_text(encoding="utf-8"))
    assert proposal["title"] == "Improve deterministic docs"
    assert proposal["body"] == "Evidence and residual risk."
    assert proposal["changed_paths"] == ["README.md", "tests/test_new.py"]
    assert not (workspace / guard.PROPOSAL_FILENAME).exists()

    apply_target = tmp_path / "apply-target"
    _run(
        "git", "clone", "-q", "--local", "--no-hardlinks",
        str(source), str(apply_target), cwd=tmp_path,
    )
    assert guard.apply_patch(
        argparse.Namespace(
            workspace=apply_target,
            patch_file=patch,
            proposal_file=proposal_file,
        )
    ) == 0
    assert (apply_target / "README.md").read_text(encoding="utf-8") == "after\n"
    assert (apply_target / "tests/test_new.py").exists()


def test_proposal_only_is_not_a_product_change(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Metadata without source changes produces no patch or pull request."""

    _, baseline, workspace, base_file = _fixture(tmp_path)
    (workspace / guard.PROPOSAL_FILENAME).write_text("Title\nBody\n", encoding="utf-8")
    output = tmp_path / "github-output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))

    result, patch, _, proposal = _capture(tmp_path, baseline, workspace, base_file)

    assert result == 0
    assert not patch.exists()
    assert not proposal.exists()
    assert "changed=false" in output.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "path",
    ["pyproject.toml", ".github/workflows/ci.yml", "AGENTS.md", "scripts/x.py"],
)
def test_capture_rejects_paths_outside_product_boundary(tmp_path: Path, path: str):
    """The model cannot edit build, workflow, policy, or automation files."""

    _, baseline, workspace, base_file = _fixture(tmp_path)
    target = workspace / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("unsafe\n", encoding="utf-8")

    with pytest.raises(guard.BoundaryError, match="path boundary"):
        _capture(tmp_path, baseline, workspace, base_file)


def test_capture_rejects_deletion_symlink_hardlink_executable_and_binary(tmp_path: Path):
    """File-system tricks and destructive patches fail closed."""

    for case in ("delete", "symlink", "hardlink", "executable", "binary"):
        case_root = tmp_path / case
        case_root.mkdir()
        _, baseline, workspace, base_file = _fixture(case_root)
        if case == "delete":
            (workspace / "README.md").unlink()
            match = "delete files"
        elif case == "symlink":
            (workspace / "tests/link.py").symlink_to("../README.md")
            match = "non-regular"
        elif case == "hardlink":
            os.link(workspace / "README.md", workspace / "tests/hardlink.py")
            match = "hard link"
        elif case == "executable":
            path = workspace / "tests/executable.py"
            path.write_text("print('x')\n")
            path.chmod(0o755)
            match = "executable"
        else:
            (workspace / "tests/binary.py").write_bytes(b"a\x00b")
            match = "binary"
        with pytest.raises(guard.BoundaryError, match=match):
            _capture(case_root, baseline, workspace, base_file)


def test_capture_enforces_file_line_and_byte_budgets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Oversized autonomous increments are rejected before artifact upload."""

    for case in ("files", "file-bytes", "total-bytes", "lines"):
        case_root = tmp_path / case
        case_root.mkdir()
        _, baseline, workspace, base_file = _fixture(case_root)
        if case == "files":
            monkeypatch.setattr(guard, "MAX_FILES", 1)
            (workspace / "README.md").write_text("changed\n")
            (workspace / "CHANGELOG.md").write_text("changed\n")
            match = "too many files"
        elif case == "file-bytes":
            monkeypatch.setattr(guard, "MAX_FILE_BYTES", 3)
            (workspace / "README.md").write_text("changed\n")
            match = "per-file"
        elif case == "total-bytes":
            monkeypatch.setattr(guard, "MAX_TOTAL_BYTES", 5)
            (workspace / "README.md").write_text("changed\n")
            match = "changed-file byte"
        else:
            monkeypatch.setattr(guard, "MAX_CHANGED_LINES", 1)
            (workspace / "README.md").write_text("one\ntwo\n")
            match = "changed-line"
        with pytest.raises(guard.BoundaryError, match=match):
            _capture(case_root, baseline, workspace, base_file)
        monkeypatch.undo()


def test_capture_rejects_raw_and_encoded_secret_material(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """The NIM credential cannot cross into the patch or PR metadata."""

    secret = "nvapi-commercial-secret"
    monkeypatch.setenv("THREADWEAVE_FORBIDDEN_SECRET", secret)
    variants = [secret, base64.b64encode(secret.encode()).decode(), secret.encode().hex()]
    for index, variant in enumerate(variants):
        case_root = tmp_path / str(index)
        case_root.mkdir()
        _, baseline, workspace, base_file = _fixture(case_root)
        (workspace / "README.md").write_text(variant + "\n")
        with pytest.raises(guard.BoundaryError, match="protected credential"):
            _capture(case_root, baseline, workspace, base_file)


def test_proposal_validation_rejects_unsafe_metadata(tmp_path: Path):
    """PR metadata must be one bounded UTF-8 regular file without controls."""

    cases = {
        "symlink": None,
        "invalid-utf8": b"\xff",
        "long-title": ("x" * (guard.MAX_TITLE_CHARACTERS + 1)).encode(),
        "control-title": b"bad\x07title\nbody",
        "control-body": b"title\nbad\x01body",
    }
    for name, data in cases.items():
        case_root = tmp_path / name
        case_root.mkdir()
        _, baseline, workspace, base_file = _fixture(case_root)
        (workspace / "README.md").write_text("changed\n")
        proposal = workspace / guard.PROPOSAL_FILENAME
        if name == "symlink":
            proposal.symlink_to("README.md")
        else:
            assert data is not None
            proposal.write_bytes(data)
        with pytest.raises(guard.BoundaryError):
            _capture(case_root, baseline, workspace, base_file)


def test_validate_patch_text_rejects_unsafe_metadata(tmp_path: Path):
    """Patch headers cannot escape paths or introduce links, binaries, or duplicates."""

    patches = [
        (
            "diff --git a/pyproject.toml b/pyproject.toml\n"
            "--- a/pyproject.toml\n+++ b/pyproject.toml\n"
            "@@ -1 +1 @@\n-a\n+b\n"
        ),
        (
            "diff --git a/README.md b/README.md\nnew file mode 120000\n"
            "--- /dev/null\n+++ b/README.md\n@@ -0,0 +1 @@\n+x\n"
        ),
        "diff --git a/README.md b/README.md\nGIT binary patch\n",
        (
            "diff --git a/README.md b/README.md\n"
            "--- a/README.md\n+++ b/README.md\n@@ -1 +1 @@\n-a\n+b\n"
            "diff --git a/README.md b/README.md\n"
            "--- a/README.md\n+++ b/README.md\n@@ -1 +1 @@\n-b\n+c\n"
        ),
    ]
    for index, content in enumerate(patches):
        patch = tmp_path / f"unsafe-{index}.patch"
        patch.write_text(content, encoding="utf-8")
        with pytest.raises(guard.BoundaryError):
            guard.validate_patch_text(patch)


def test_apply_rejects_tampered_digest_base_and_path_inventory(tmp_path: Path):
    """Every cross-job receipt must match the fresh checkout and sealed patch."""

    source, baseline, workspace, base_file = _fixture(tmp_path)
    (workspace / "README.md").write_text("after\n")
    _, patch, _, proposal_file = _capture(tmp_path, baseline, workspace, base_file)

    tampered = json.loads(proposal_file.read_text())
    tampered["patch_sha256"] = "0" * 64
    proposal_file.write_text(json.dumps(tampered))
    target = tmp_path / "target-digest"
    _run("git", "clone", "-q", "--local", "--no-hardlinks", str(source), str(target), cwd=tmp_path)
    with pytest.raises(guard.BoundaryError, match="digest"):
        guard.apply_patch(
            argparse.Namespace(
                workspace=target, patch_file=patch, proposal_file=proposal_file
            )
        )

    _, patch, _, proposal_file = _capture(tmp_path, baseline, workspace, base_file)
    target = tmp_path / "target-base"
    _run("git", "clone", "-q", "--local", "--no-hardlinks", str(source), str(target), cwd=tmp_path)
    (target / "README.md").write_text("advance\n")
    _run("git", "add", ".", cwd=target)
    _run("git", "config", "user.name", "Guard Test", cwd=target)
    _run("git", "config", "user.email", "guard@example.invalid", cwd=target)
    _run("git", "commit", "-qm", "advance", cwd=target)
    with pytest.raises(guard.BoundaryError, match="moved"):
        guard.apply_patch(
            argparse.Namespace(
                workspace=target, patch_file=patch, proposal_file=proposal_file
            )
        )

    proposal = json.loads(proposal_file.read_text())
    proposal["changed_paths"] = ["CHANGELOG.md"]
    proposal_file.write_text(json.dumps(proposal))
    target = tmp_path / "target-paths"
    _run("git", "clone", "-q", "--local", "--no-hardlinks", str(source), str(target), cwd=tmp_path)
    with pytest.raises(guard.BoundaryError, match="paths"):
        guard.apply_patch(
            argparse.Namespace(
                workspace=target, patch_file=patch, proposal_file=proposal_file
            )
        )


def test_default_metadata_and_cli_boundary_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """Missing metadata gets a safe default and CLI failures return exit status two."""

    _, baseline, workspace, base_file = _fixture(tmp_path)
    (workspace / "README.md").write_text("after\n")
    _, _, _, proposal_file = _capture(tmp_path, baseline, workspace, base_file)
    proposal = json.loads(proposal_file.read_text())
    assert proposal["title"] == "ThreadWeave autonomous product increment"

    unsafe = tmp_path / "unsafe.patch"
    unsafe.write_text("not a patch\n")
    arguments = [
        "apply",
        "--workspace",
        str(tmp_path),
        "--patch-file",
        str(unsafe),
        "--proposal-file",
        str(proposal_file),
    ]
    assert guard.main(arguments) == 2
    assert "hourly product guard:" in capsys.readouterr().err
