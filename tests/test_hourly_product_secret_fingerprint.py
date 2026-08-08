"""Contracts for credential-free post-model product packaging."""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "hourly-product-development.yml"
MODULE_PATH = ROOT / "scripts" / "ci" / "hourly_product_guard.py"
SPEC = importlib.util.spec_from_file_location("hourly_product_guard_fingerprint", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


def _rolling_hash(payload: bytes) -> int:
    """Return the reviewed 64-bit rolling prefilter for one protected token."""
    value = 0
    for byte in payload:
        value = ((value * 257) + byte) & ((1 << 64) - 1)
    return value


def _fingerprints(secret: bytes) -> dict[str, object]:
    """Return fingerprint-only metadata for raw and common encoded secret forms."""
    variants = {
        secret,
        base64.b64encode(secret),
        base64.urlsafe_b64encode(secret),
        secret.hex().encode("ascii"),
    }
    return {
        "version": 1,
        "records": sorted(
            (
                {
                    "length": len(token),
                    "rolling_hash": _rolling_hash(token),
                    "sha256": hashlib.sha256(token).hexdigest(),
                }
                for token in variants
            ),
            key=lambda record: (record["length"], record["sha256"]),
        ),
    }


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
    assert "THREADWEAVE_FORBIDDEN_FINGERPRINT_FILE" in capture
    assert "forbidden_fingerprint_file=" in credential
    assert "secret_sha256" in credential
    assert "rolling_hash" in credential


def test_fingerprint_only_scan_rejects_raw_and_encoded_secret_forms(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Fingerprint metadata preserves existing raw/base64/url-safe/hex leak rejection."""
    secret = b"nvapi-commercial-secret_+/"
    fingerprint_file = tmp_path / "fingerprints.json"
    fingerprint_file.write_text(json.dumps(_fingerprints(secret)), encoding="utf-8")
    monkeypatch.delenv("THREADWEAVE_FORBIDDEN_SECRET", raising=False)
    monkeypatch.setenv(
        "THREADWEAVE_FORBIDDEN_FINGERPRINT_FILE", str(fingerprint_file)
    )

    variants = {
        secret,
        base64.b64encode(secret),
        base64.urlsafe_b64encode(secret),
        secret.hex().encode("ascii"),
    }
    for variant in variants:
        with pytest.raises(guard.BoundaryError, match="protected credential"):
            guard._reject_forbidden_tokens(b"prefix:" + variant + b":suffix", label="test")

    guard._reject_forbidden_tokens(b"ordinary bounded product text", label="test")
