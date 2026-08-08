"""Contracts for credential-free post-model product packaging."""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import runpy
import stat
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "hourly-product-development.yml"
MODULE_PATH = ROOT / "scripts" / "ci" / "secret_fingerprint_guard.py"
SPEC = importlib.util.spec_from_file_location("secret_fingerprint_guard", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


def _fingerprints(secret: bytes) -> dict[str, object]:
    """Return the production fingerprint schema for one synthetic secret."""
    return guard.build_fingerprint(secret)


def test_post_model_capture_step_receives_fingerprints_not_the_raw_nim_secret():
    """Packaging must preserve leak detection without rematerializing the API key."""
    workflow = WORKFLOW.read_text(encoding="utf-8")
    capture = workflow.split("      - name: Capture the bounded credential-free patch", 1)[1].split(
        "      - name: Upload the bounded proposal for credential-free reverification", 1
    )[0]
    credential = workflow.split(
        "      - name: Require the NVIDIA credential for model-backed development", 1
    )[1].split("      - name: Check out the protected default branch", 1)[0]

    assert "THREADWEAVE_FORBIDDEN_SECRET" not in capture
    assert "secrets.NVIDIA_NIM_API_KEY" not in capture
    assert "secret_fingerprint_guard.py scan" in capture
    assert "forbidden_fingerprint_file=" in credential
    assert "secret_fingerprint_guard.py fingerprint" in credential


def test_fingerprint_only_scan_rejects_raw_and_encoded_secret_forms(tmp_path: Path):
    """Fingerprint metadata preserves raw/base64/url-safe/hex leak rejection."""
    secret = b"nvapi-commercial-secret_+/"
    fingerprint_file = tmp_path / "fingerprints.json"
    guard.write_fingerprint(fingerprint_file, secret)
    records = guard.load_fingerprint(fingerprint_file)

    variants = {
        secret,
        base64.b64encode(secret),
        base64.urlsafe_b64encode(secret),
        secret.hex().encode("ascii"),
    }
    for index, variant in enumerate(variants):
        artifact = tmp_path / f"artifact-{index}"
        artifact.write_bytes(b"prefix:" + variant + b":suffix")
        with pytest.raises(guard.FingerprintError, match="protected credential"):
            guard.reject_protected_material([artifact], records)

    clean = tmp_path / "clean"
    clean.write_bytes(b"ordinary bounded product text")
    guard.reject_protected_material([clean], records)


def test_fingerprint_builder_and_writer_fail_closed(tmp_path: Path):
    """Fingerprint generation requires a nonempty secret and persists no raw value."""
    secret = b"nvapi-high-entropy-secret"
    with pytest.raises(guard.FingerprintError, match="unavailable"):
        guard.build_fingerprint(b"")

    path = tmp_path / "fingerprint.json"
    guard.write_fingerprint(path, secret)
    payload = path.read_bytes()
    assert secret not in payload
    assert stat.S_IMODE(path.stat().st_mode) == 0o400
    loaded = guard.load_fingerprint(path)
    assert loaded
    assert all(length > 0 for length, _, _ in loaded)


def test_fingerprint_loader_rejects_missing_nonregular_oversized_and_bad_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Fingerprint evidence itself is a strict, bounded trusted input."""
    missing = tmp_path / "missing.json"
    with pytest.raises(guard.FingerprintError, match="missing"):
        guard.load_fingerprint(missing)

    target = tmp_path / "target.json"
    target.write_text("{}", encoding="utf-8")
    link = tmp_path / "link.json"
    link.symlink_to(target)
    with pytest.raises(guard.FingerprintError, match="regular"):
        guard.load_fingerprint(link)

    monkeypatch.setattr(guard, "MAX_FINGERPRINT_BYTES", 2)
    with pytest.raises(guard.FingerprintError, match="too large"):
        guard.load_fingerprint(target)
    monkeypatch.undo()

    bad = tmp_path / "bad.json"
    bad.write_bytes(b"\xff")
    with pytest.raises(guard.FingerprintError, match="UTF-8 JSON"):
        guard.load_fingerprint(bad)
    bad.write_text("{", encoding="utf-8")
    with pytest.raises(guard.FingerprintError, match="UTF-8 JSON"):
        guard.load_fingerprint(bad)


@pytest.mark.parametrize(
    ("payload", "match"),
    [
        ({"records": []}, "schema mismatch"),
        ({"version": 2, "records": [{}]}, "version or records"),
        ({"version": 1, "records": []}, "version or records"),
        ({"version": 1, "records": ["bad"]}, "record schema"),
        (
            {"version": 1, "records": [{"length": 0, "rolling_hash": 0, "sha256": "0" * 64}]},
            "length",
        ),
        (
            {"version": 1, "records": [{"length": 1, "rolling_hash": -1, "sha256": "0" * 64}]},
            "rolling hash",
        ),
        (
            {"version": 1, "records": [{"length": 1, "rolling_hash": 0, "sha256": "x"}]},
            "SHA-256",
        ),
    ],
)
def test_fingerprint_loader_rejects_malformed_schema(
    tmp_path: Path, payload: dict[str, object], match: str
):
    """Every malformed fingerprint schema or value fails closed."""
    path = tmp_path / "bad-schema.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(guard.FingerprintError, match=match):
        guard.load_fingerprint(path)


def test_fingerprint_loader_rejects_duplicate_records(tmp_path: Path):
    """Duplicate fingerprint evidence cannot create ambiguous matching semantics."""
    payload = _fingerprints(b"secret")
    record = payload["records"][0]
    payload["records"] = [record, record]
    path = tmp_path / "duplicate.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(guard.FingerprintError, match="duplicate"):
        guard.load_fingerprint(path)


def test_contains_fingerprint_covers_short_offset_collision_and_miss():
    """Rolling matches require exact SHA confirmation at any payload offset."""
    token = b"credential"
    record = (
        len(token),
        guard.rolling_hash(token),
        hashlib.sha256(token).hexdigest(),
    )
    assert not guard.contains_fingerprint(b"short", record)
    assert guard.contains_fingerprint(token, record)
    assert guard.contains_fingerprint(b"prefix-" + token + b"-suffix", record)

    collision_without_digest = (len(token), guard.rolling_hash(token), "0" * 64)
    assert not guard.contains_fingerprint(token, collision_without_digest)
    rolling_miss = (len(token), (guard.rolling_hash(token) + 1) & guard.ROLLING_MASK, record[2])
    assert not guard.contains_fingerprint(token, rolling_miss)


def test_artifact_scanner_rejects_nonregular_artifact(tmp_path: Path):
    """Only regular single-link artifact files may cross the fingerprint scan."""
    directory = tmp_path / "artifact-dir"
    directory.mkdir()
    with pytest.raises(guard.FingerprintError, match="regular file"):
        guard.reject_protected_material([directory], ((1, 1, "0" * 64),))


def test_command_handlers_and_main_cover_success_and_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """CLI generation and scanning preserve fail-closed exit semantics."""
    fingerprint = tmp_path / "fingerprint.json"
    artifact = tmp_path / "artifact.txt"
    artifact.write_text("safe", encoding="utf-8")
    monkeypatch.setenv("NIM_UPSTREAM_API_KEY", "synthetic-secret")

    assert guard.main(["fingerprint", "--output-file", str(fingerprint)]) == 0
    assert guard.main(
        ["scan", "--fingerprint-file", str(fingerprint), "--file", str(artifact)]
    ) == 0

    monkeypatch.delenv("NIM_UPSTREAM_API_KEY")
    assert guard.main(["fingerprint", "--output-file", str(tmp_path / "empty.json")]) == 2
    assert "unavailable" in capsys.readouterr().err

    assert guard.main(
        ["scan", "--fingerprint-file", str(tmp_path / "missing.json"), "--file", str(artifact)]
    ) == 2
    assert "missing" in capsys.readouterr().err


def test_module_main_entrypoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """The executable module exits successfully for a valid fingerprint command."""
    output = tmp_path / "entrypoint.json"
    monkeypatch.setenv("NIM_UPSTREAM_API_KEY", "entrypoint-secret")
    monkeypatch.setattr(
        sys,
        "argv",
        [str(MODULE_PATH), "fingerprint", "--output-file", str(output)],
    )
    with pytest.raises(SystemExit, match="0"):
        runpy.run_path(str(MODULE_PATH), run_name="__main__")
    assert output.exists()
