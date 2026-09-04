"""Fingerprint-only leak guard for autonomous product artifacts.

The trusted gateway step may derive one-way fingerprints while it holds a
provider credential. Post-model packaging receives only those fingerprints and
uses a rolling-hash prefilter plus salted scrypt confirmation to reject the raw
key and its common encoded forms without rematerializing the credential.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import secrets
import stat
import sys
from collections.abc import Sequence
from pathlib import Path

ROLLING_BASE = 257
ROLLING_MASK = (1 << 64) - 1
MAX_FINGERPRINT_BYTES = 16_384
MAX_TOKEN_LENGTH = 16_384
MAX_RECORDS = 4
SCRYPT_N = 1 << 14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32
SCRYPT_SALT_BYTES = 16
SCRYPT_SALT = re.compile(r"[0-9a-f]{32}")
SCRYPT_DIGEST = re.compile(r"[0-9a-f]{64}")


class FingerprintError(RuntimeError):
    """Raised when credential fingerprint evidence is malformed or matched."""


def rolling_hash(payload: bytes) -> int:
    """Return the bounded 64-bit rolling hash used as a fast match prefilter."""
    value = 0
    for byte in payload:
        value = ((value * ROLLING_BASE) + byte) & ROLLING_MASK
    return value


def scrypt_confirmation(payload: bytes, salt: bytes) -> bytes:
    """Return a memory-hard, per-record-salted equality confirmation."""
    return hashlib.scrypt(
        payload,
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_DKLEN,
    )


def build_fingerprint(secret: bytes) -> dict[str, object]:
    """Build fingerprint-only records for raw and common encoded secret forms."""
    if not secret:
        raise FingerprintError("provider credential is unavailable")
    variants = {
        secret,
        base64.b64encode(secret),
        base64.urlsafe_b64encode(secret),
        secret.hex().encode("ascii"),
    }
    records = []
    for token in variants:
        salt = secrets.token_bytes(SCRYPT_SALT_BYTES)
        records.append(
            {
                "length": len(token),
                "rolling_hash": rolling_hash(token),
                "salt": salt.hex(),
                "scrypt": scrypt_confirmation(token, salt).hex(),
            }
        )
    records.sort(key=lambda record: (record["length"], record["salt"]))
    return {"version": 2, "records": records}


def write_fingerprint(path: Path, secret: bytes) -> None:
    """Write mode-0400 fingerprint metadata without persisting the raw secret."""
    path.write_text(
        json.dumps(build_fingerprint(secret), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    path.chmod(0o400)


def _validate_record(value: object) -> tuple[int, int, bytes, bytes]:
    """Validate one fingerprint record and return its immutable tuple form."""
    if not isinstance(value, dict) or set(value) != {
        "length",
        "rolling_hash",
        "salt",
        "scrypt",
    }:
        raise FingerprintError("credential fingerprint record schema mismatch")
    length = value["length"]
    rolling = value["rolling_hash"]
    salt = value["salt"]
    digest = value["scrypt"]
    if type(length) is not int or not 1 <= length <= MAX_TOKEN_LENGTH:
        raise FingerprintError("credential fingerprint length is invalid")
    if type(rolling) is not int or not 0 <= rolling <= ROLLING_MASK:
        raise FingerprintError("credential rolling hash is invalid")
    if not isinstance(salt, str) or SCRYPT_SALT.fullmatch(salt) is None:
        raise FingerprintError("credential scrypt salt is invalid")
    if not isinstance(digest, str) or SCRYPT_DIGEST.fullmatch(digest) is None:
        raise FingerprintError("credential scrypt fingerprint is invalid")
    return length, rolling, bytes.fromhex(salt), bytes.fromhex(digest)


def load_fingerprint(path: Path) -> tuple[tuple[int, int, bytes, bytes], ...]:
    """Load one regular, bounded, strict-schema fingerprint evidence file."""
    try:
        file_stat = path.lstat()
    except FileNotFoundError as exc:
        raise FingerprintError("credential fingerprint file is missing") from exc
    if not stat.S_ISREG(file_stat.st_mode) or file_stat.st_nlink != 1:
        raise FingerprintError("credential fingerprint must be one regular file")
    if file_stat.st_size > MAX_FINGERPRINT_BYTES:
        raise FingerprintError("credential fingerprint file is too large")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FingerprintError("credential fingerprint must be strict UTF-8 JSON") from exc
    if not isinstance(payload, dict) or set(payload) != {"version", "records"}:
        raise FingerprintError("credential fingerprint schema mismatch")
    if (
        payload["version"] != 2
        or not isinstance(payload["records"], list)
        or not payload["records"]
        or len(payload["records"]) > MAX_RECORDS
    ):
        raise FingerprintError("credential fingerprint version or records are invalid")
    records = tuple(_validate_record(record) for record in payload["records"])
    if len(records) != len(set(records)):
        raise FingerprintError("credential fingerprint contains duplicate records")
    return records


def contains_fingerprint(payload: bytes, record: tuple[int, int, bytes, bytes]) -> bool:
    """Return whether ``payload`` contains the exact token represented by ``record``."""
    length, target_rolling, salt, target_scrypt = record
    if len(payload) < length:
        return False
    highest_power = pow(ROLLING_BASE, length - 1, 1 << 64)
    current = rolling_hash(payload[:length])
    for offset in range(len(payload) - length + 1):
        if offset:
            removed = payload[offset - 1]
            added = payload[offset + length - 1]
            current = (current - ((removed * highest_power) & ROLLING_MASK)) & ROLLING_MASK
            current = ((current * ROLLING_BASE) + added) & ROLLING_MASK
        if current != target_rolling:
            continue
        candidate = payload[offset : offset + length]
        if secrets.compare_digest(scrypt_confirmation(candidate, salt), target_scrypt):
            return True
        # The rolling value is only a prefilter. A non-matching scrypt digest is
        # a collision, not proof that the remaining windows are safe to skip.
    return False


def reject_protected_material(
    paths: Sequence[Path], records: Sequence[tuple[int, int, bytes, bytes]]
) -> None:
    """Reject any bounded artifact containing a protected credential representation."""
    for path in paths:
        file_stat = path.lstat()
        if not stat.S_ISREG(file_stat.st_mode) or file_stat.st_nlink != 1:
            raise FingerprintError(f"artifact is not one regular file: {path}")
        payload = path.read_bytes()
        if any(contains_fingerprint(payload, record) for record in records):
            raise FingerprintError(f"protected credential detected in artifact: {path.name}")


def _fingerprint_command(args: argparse.Namespace) -> int:
    """Create fingerprint evidence while the selected credential path is authorized."""
    secret = os.environ.get("PROVIDER_API_KEY", "").encode("utf-8")
    write_fingerprint(args.output_file, secret)
    return 0


def _scan_command(args: argparse.Namespace) -> int:
    """Scan post-model artifact files using fingerprint-only evidence."""
    records = load_fingerprint(args.fingerprint_file)
    reject_protected_material(args.files, records)
    return 0


def _parser() -> argparse.ArgumentParser:
    """Build the command-line parser for trusted workflow entry points."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    fingerprint_parser = subparsers.add_parser("fingerprint")
    fingerprint_parser.add_argument("--output-file", type=Path, required=True)
    fingerprint_parser.set_defaults(handler=_fingerprint_command)

    scan_parser = subparsers.add_parser("scan")
    scan_parser.add_argument("--fingerprint-file", type=Path, required=True)
    scan_parser.add_argument("--file", dest="files", type=Path, action="append", required=True)
    scan_parser.set_defaults(handler=_scan_command)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run a fingerprint command and convert boundary failures to exit status two."""
    args = _parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except (FingerprintError, OSError) as exc:
        print(f"secret fingerprint guard: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
