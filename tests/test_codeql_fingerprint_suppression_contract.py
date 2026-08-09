"""Contracts for the query-scoped CodeQL credential-fingerprint disposition."""

from pathlib import Path


ROOT = Path(__file__).parents[1]
FINGERPRINT_GUARD = ROOT / "scripts" / "ci" / "secret_fingerprint_guard.py"


def test_sha256_fingerprint_has_narrow_non_password_codeql_disposition() -> None:
    """Keep the SHA-256 equality fingerprint documented and query-scoped."""
    source = FINGERPRINT_GUARD.read_text(encoding="utf-8")
    expected = (
        "            # SHA-256 is an exact-equality confirmation for a high-entropy credential;\n"
        "            # it is not password hashing. CodeQL recommends SHA-2 for non-password data.\n"
        "            # codeql[py/weak-sensitive-data-hashing]\n"
        '            "sha256": hashlib.sha256(token).hexdigest(),'
    )

    assert expected in source
    assert source.count("codeql[py/weak-sensitive-data-hashing]") == 1
