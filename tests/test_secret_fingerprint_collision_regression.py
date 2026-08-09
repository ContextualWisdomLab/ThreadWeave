"""Regression coverage for rolling-hash collisions in the credential leak guard."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "scripts" / "ci" / "secret_fingerprint_guard.py"
SPEC = importlib.util.spec_from_file_location("secret_fingerprint_guard_collision", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


def test_rolling_collision_before_secret_does_not_abort_scan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A prefilter collision must not hide an exact protected token later in the payload."""
    token = b"abcX"
    salt = b"s" * guard.SCRYPT_SALT_BYTES

    # A base of one makes equal-byte-sum windows collide deterministically.  The
    # first window (``Xabc``) is not the secret, while the second (``abcX``) is.
    # Production keeps its 64-bit base; this fixture isolates collision behavior
    # without relying on probabilistic brute force.
    monkeypatch.setattr(guard, "ROLLING_BASE", 1)
    record = (
        len(token),
        guard.rolling_hash(token),
        salt,
        guard.scrypt_confirmation(token, salt),
    )
    payload = b"X" + token
    first_window = payload[: len(token)]

    assert first_window != token
    assert guard.rolling_hash(first_window) == record[1]
    assert guard.contains_fingerprint(payload, record)
