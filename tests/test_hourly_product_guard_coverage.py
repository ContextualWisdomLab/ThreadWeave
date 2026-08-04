"""Coverage-completion tests for the autonomous product patch boundary."""

from __future__ import annotations

import argparse
import base64
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

BASE_TEST = Path(__file__).with_name("test_hourly_product_guard.py")
SPEC = importlib.util.spec_from_file_location("hourly_product_guard_base_tests", BASE_TEST)
assert SPEC is not None and SPEC.loader is not None
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)

guard = base.guard
MODULE_PATH = base.MODULE_PATH
_fixture = base._fixture
_capture = base._capture
_run = base._run


def test_proposal_metadata_size_and_default_branches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Metadata limits and empty proposal defaults fail or recover deterministically."""

    oversized_root = tmp_path / "oversized"
    oversized_root.mkdir()
    _, baseline, workspace, base_file = _fixture(oversized_root)
    (workspace / "README.md").write_text("changed\n")
    (workspace / guard.PROPOSAL_FILENAME).write_bytes(
        b"x" * (guard.MAX_BODY_BYTES + 1_025)
    )
    with pytest.raises(guard.BoundaryError, match="metadata byte limit"):
        _capture(oversized_root, baseline, workspace, base_file)

    body_root = tmp_path / "body"
    body_root.mkdir()
    _, baseline, workspace, base_file = _fixture(body_root)
    (workspace / "README.md").write_text("changed\n")
    (workspace / guard.PROPOSAL_FILENAME).write_text("Title\nlong body\n")
    monkeypatch.setattr(guard, "MAX_BODY_BYTES", 3)
    with pytest.raises(guard.BoundaryError, match="body exceeded"):
        _capture(body_root, baseline, workspace, base_file)
    monkeypatch.undo()

    empty_root = tmp_path / "empty"
    empty_root.mkdir()
    _, baseline, workspace, base_file = _fixture(empty_root)
    (workspace / "README.md").write_text("changed\n")
    (workspace / guard.PROPOSAL_FILENAME).write_text("")
    _, _, _, proposal_file = _capture(empty_root, baseline, workspace, base_file)
    proposal = json.loads(proposal_file.read_text())
    assert proposal["title"] == "ThreadWeave autonomous product increment"
    assert "bounded diff" in proposal["body"]


def test_validate_worktree_diff_handles_empty_mode_and_binary_summaries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Unexpected Git summaries cannot bypass the textual-diff boundary."""

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "README.md").write_text("changed\n")
    git = ["git"]
    env: dict[str, str] = {}

    monkeypatch.setattr(guard, "_changed_paths", lambda *_args, **_kwargs: ([], []))
    with pytest.raises(guard.BoundaryError, match="no reviewable"):
        guard.validate_worktree_diff(workspace=workspace, git=git, env=env)

    monkeypatch.setattr(
        guard, "_changed_paths", lambda *_args, **_kwargs: (["README.md"], [])
    )

    def mode_run(args, **_kwargs):
        text = " mode change 100644 => 100755 README.md\n" if "--summary" in args else b""
        return subprocess.CompletedProcess(args, 0, stdout=text, stderr="")

    monkeypatch.setattr(guard, "_run", mode_run)
    with pytest.raises(guard.BoundaryError, match="change file modes"):
        guard.validate_worktree_diff(workspace=workspace, git=git, env=env)

    def binary_run(args, **_kwargs):
        stdout: str | bytes = "" if "--summary" in args else b"-\t1\tREADME.md\0"
        return subprocess.CompletedProcess(args, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(guard, "_run", binary_run)
    with pytest.raises(guard.BoundaryError, match="binary diff"):
        guard.validate_worktree_diff(workspace=workspace, git=git, env=env)


def test_patch_text_size_encoding_count_marker_and_mode_guards(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Every patch-metadata rejection branch fails before materialization."""

    patch = tmp_path / "patch"
    patch.write_bytes(b"xx")
    monkeypatch.setattr(guard, "MAX_PATCH_BYTES", 1)
    with pytest.raises(guard.BoundaryError, match="byte limit"):
        guard.validate_patch_text(patch)
    monkeypatch.undo()

    patch.write_bytes(b"\xff")
    with pytest.raises(guard.BoundaryError, match="strict UTF-8"):
        guard.validate_patch_text(patch)

    patch.write_text(
        "diff --git a/README.md b/README.md\n"
        "--- x/README.md\n+++ b/README.md\n@@ -1 +1 @@\n-a\n+b\n"
    )
    with pytest.raises(guard.BoundaryError, match="unsafe file marker"):
        guard.validate_patch_text(patch)

    patch.write_text(
        "diff --git a/README.md b/README.md\n"
        "new file mode 100755\n--- /dev/null\n+++ b/README.md\n"
        "@@ -0,0 +1 @@\n+x\n"
    )
    with pytest.raises(guard.BoundaryError, match="new-file mode"):
        guard.validate_patch_text(patch)

    patch.write_text(
        "diff --git a/README.md b/README.md\n--- a/README.md\n+++ b/README.md\n"
        "@@ -1 +1 @@\n-a\n+b\n"
        "diff --git a/CHANGELOG.md b/CHANGELOG.md\n"
        "--- a/CHANGELOG.md\n+++ b/CHANGELOG.md\n@@ -1 +1 @@\n-a\n+b\n"
    )
    monkeypatch.setattr(guard, "MAX_FILES", 1)
    with pytest.raises(guard.BoundaryError, match="too many files"):
        guard.validate_patch_text(patch)


def test_capture_rejects_invalid_base_moved_baseline_and_git_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """The immutable base and Git return-code contracts are fail-closed."""

    _, baseline, workspace, base_file = _fixture(tmp_path)
    (workspace / "README.md").write_text("changed\n")
    base_file.write_text("not-a-sha\n")
    with pytest.raises(guard.BoundaryError, match="Base SHA"):
        _capture(tmp_path, baseline, workspace, base_file)

    source_sha = _run("git", "rev-parse", "HEAD", cwd=baseline)
    base_file.write_text("0" * 40 + "\n")
    assert source_sha != "0" * 40
    with pytest.raises(guard.BoundaryError, match="baseline changed"):
        _capture(tmp_path, baseline, workspace, base_file)

    base_file.write_text(source_sha + "\n")
    original_run = guard._run

    def bad_quiet(args, **kwargs):
        if "--quiet" in args:
            return subprocess.CompletedProcess(args, 2, stdout=b"", stderr=b"bad")
        return original_run(args, **kwargs)

    monkeypatch.setattr(guard, "_run", bad_quiet)
    with pytest.raises(guard.BoundaryError, match="could not determine"):
        _capture(tmp_path, baseline, workspace, base_file)


def test_capture_rejects_patch_byte_budget_after_diff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """A textual diff can still be rejected by the final serialized patch budget."""

    _, baseline, workspace, base_file = _fixture(tmp_path)
    (workspace / "README.md").write_text("changed\n")
    monkeypatch.setattr(guard, "MAX_PATCH_BYTES", 1)
    with pytest.raises(guard.BoundaryError, match="patch byte limit"):
        _capture(tmp_path, baseline, workspace, base_file)


def test_proposal_envelope_schema_and_field_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Every receipt field is type-, size-, path-, and credential-validated."""

    valid = {
        "base_sha": "a" * 40,
        "body": "body",
        "changed_paths": ["README.md"],
        "patch_sha256": "b" * 64,
        "title": "title",
    }

    def reject(name: str, value, match: str) -> None:
        proposal = tmp_path / f"{name}.json"
        data = dict(valid)
        if name == "schema":
            data["extra"] = value
        else:
            data[name] = value
        proposal.write_text(json.dumps(data))
        with pytest.raises(guard.BoundaryError, match=match):
            guard._load_proposal(proposal)

    malformed = tmp_path / "malformed.json"
    malformed.write_text("{")
    with pytest.raises(guard.BoundaryError, match="strict UTF-8 JSON"):
        guard._load_proposal(malformed)

    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b"x" * (guard.MAX_BODY_BYTES + 4_097))
    with pytest.raises(guard.BoundaryError, match="byte limit"):
        guard._load_proposal(oversized)

    reject("schema", True, "unexpected schema")
    reject("base_sha", "bad", "base SHA")
    reject("patch_sha256", "bad", "patch digest")
    reject("title", "", "title")
    reject("body", 3, "body")
    reject("changed_paths", ["README.md", "README.md"], "path inventory")
    reject("changed_paths", ["pyproject.toml"], "path inventory")

    monkeypatch.setenv("THREADWEAVE_FORBIDDEN_SECRET", "secret")
    reject("title", "secret", "protected credential")
    reject("body", base64.b64encode(b"secret").decode(), "protected credential")


def test_apply_rejects_materialized_path_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Fresh-checkout application must reproduce the exact sealed path inventory."""

    source, baseline, workspace, base_file = _fixture(tmp_path)
    (workspace / "README.md").write_text("after\n")
    _, patch, _, proposal_file = _capture(tmp_path, baseline, workspace, base_file)
    target = tmp_path / "target"
    _run(
        "git", "clone", "-q", "--local", "--no-hardlinks",
        str(source), str(target), cwd=tmp_path,
    )
    monkeypatch.setattr(guard, "validate_worktree_diff", lambda **_kwargs: ["CHANGELOG.md"])
    with pytest.raises(guard.BoundaryError, match="Materialized paths"):
        guard.apply_patch(
            argparse.Namespace(
                workspace=target,
                patch_file=patch,
                proposal_file=proposal_file,
            )
        )


def test_self_test_parser_and_module_entrypoint(capsys: pytest.CaptureFixture[str]):
    """The trusted CLI's success paths and module entry point remain executable."""

    assert guard.self_test() == 0
    assert guard.main(["self-test"]) == 0
    assert "hourly product guard self-test passed" in capsys.readouterr().out

    import runpy

    previous = list(__import__("sys").argv)
    __import__("sys").argv = [str(MODULE_PATH), "self-test"]
    try:
        with pytest.raises(SystemExit, match="0"):
            runpy.run_path(str(MODULE_PATH), run_name="__main__")
    finally:
        __import__("sys").argv = previous


def test_patch_without_diff_headers_is_rejected(tmp_path: Path):
    """Arbitrary text is never treated as a reviewable Git patch."""

    patch = tmp_path / "plain.patch"
    patch.write_text("not a patch\n")
    with pytest.raises(guard.BoundaryError, match="no reviewable diff headers"):
        guard.validate_patch_text(patch)


def test_self_test_detects_a_guard_that_stops_rejecting_unsafe_paths(
    monkeypatch: pytest.MonkeyPatch,
):
    """The built-in self-test fails loudly if its negative control is accepted."""

    original = guard.validate_patch_text

    def accept_only_negative_control(path: Path):
        if path.name == "unsafe.patch":
            return ["README.md"]
        return original(path)

    monkeypatch.setattr(guard, "validate_patch_text", accept_only_negative_control)
    with pytest.raises(AssertionError, match="Unsafe build-configuration"):
        guard.self_test()
