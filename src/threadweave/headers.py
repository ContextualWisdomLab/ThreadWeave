"""RFC 5322 §3.6.4 identification-field primitives.

These helpers parse and normalize ``Message-ID`` / ``References`` /
``In-Reply-To`` header values and compute a content fingerprint for messages
that lack a usable ``Message-ID``.

They are extracted **behaviour-preserving** from the naruon control plane
(``backend/services/threading_service.py``); the JWZ assembly in
:mod:`threadweave.threading` is a fresh canonical implementation built on top of
them. See the package README for the "one source, multi use" provenance note.
"""

from __future__ import annotations

import hashlib
import re

# Message-IDs inside a ``References``/``In-Reply-To`` header are angle-bracketed
# per RFC 5322 §3.6.4 (``msg-id = "<" id-left "@" id-right ">"``). Pre-compiled
# once so repeated header processing does not re-compile the pattern.
REFERENCE_PATTERN = re.compile(r"<([^>]+)>")

__all__ = [
    "REFERENCE_PATTERN",
    "extract_reference_ids",
    "generate_email_fingerprint",
    "normalize_message_id",
]


def normalize_message_id(value: str | None) -> str | None:
    """Return the canonical persisted form for a ``Message-ID``-like header.

    Strips surrounding whitespace and a single pair of angle brackets, returning
    ``None`` for input that is empty once normalized.

        >>> normalize_message_id("<x@y>")
        'x@y'
        >>> normalize_message_id("  <a@b>  ")
        'a@b'
        >>> normalize_message_id(None) is None
        True
    """
    if value is None:
        return None

    normalized = str(value).strip().strip("<>").strip()
    return normalized or None


def extract_reference_ids(value: str | None) -> list[str]:
    """Extract canonical message IDs from a ``References`` header, in order.

    Bracketed IDs are preferred; if none are present the value is split on
    whitespace as a fallback. Duplicates are dropped while preserving first-seen
    order.

        >>> extract_reference_ids("<a@x> <b@y>")
        ['a@x', 'b@y']
        >>> extract_reference_ids("<a@x> <a@x> <b@y>")
        ['a@x', 'b@y']
    """
    if not value:
        return []

    refs = REFERENCE_PATTERN.findall(str(value))
    if not refs:
        refs = str(value).split()

    normalized_refs: list[str] = []
    # Use a set for O(1) membership so long reference chains stay linear.
    seen: set[str] = set()
    for ref in refs:
        normalized = normalize_message_id(ref)
        if normalized and normalized not in seen:
            seen.add(normalized)
            normalized_refs.append(normalized)
    return normalized_refs


def generate_email_fingerprint(
    subject: str | None,
    date_str: str | None,
    sender: str | None,
    recipient: str | None,
) -> str:
    """Generate a deterministic fingerprint for an email from its key fields.

    Useful as a fallback identity for messages that carry no usable
    ``Message-ID``. The fingerprint is a SHA-256 hex digest over the
    lower-cased, ``|``-joined ``subject``, ``date``, ``sender`` and
    ``recipient`` components.
    """
    components = [
        str(subject or "").strip(),
        str(date_str or "").strip(),
        str(sender or "").strip(),
        str(recipient or "").strip(),
    ]
    raw = "|".join(components).lower()
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
