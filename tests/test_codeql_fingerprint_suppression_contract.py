"""Contracts for password-grade credential fingerprint confirmation."""

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
FINGERPRINT_GUARD = ROOT / "scripts" / "ci" / "secret_fingerprint_guard.py"
SPEC = importlib.util.spec_from_file_location("secret_fingerprint_guard_contract", FINGERPRINT_GUARD)
assert SPEC is not None and SPEC.loader is not None
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


def test_fingerprint_confirmation_uses_salted_scrypt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sensitive values must use a salted, computationally expensive confirmation."""
    calls: list[tuple[bytes, bytes, int, int, int, int]] = []

    def fake_scrypt(
        password: bytes, *, salt: bytes, n: int, r: int, p: int, dklen: int
    ) -> bytes:
        calls.append((password, salt, n, r, p, dklen))
        return bytes([len(calls)]) * dklen

    monkeypatch.setattr(guard.hashlib, "scrypt", fake_scrypt)
    payload = guard.build_fingerprint(b"nvapi-synthetic-high-entropy-secret")

    assert payload["version"] == 2
    records = payload["records"]
    assert isinstance(records, list)
    assert len(calls) == len(records)
    assert len({call[1] for call in calls}) == len(calls)
    assert all(call[2:] == (guard.SCRYPT_N, guard.SCRYPT_R, guard.SCRYPT_P, 32) for call in calls)
    assert all(set(record) == {"length", "rolling_hash", "salt", "scrypt"} for record in records)
