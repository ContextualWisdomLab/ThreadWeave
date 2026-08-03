"""Resilient RFC 2047 encoded-word decoding for email header text.

Python's modern email policies usually expose decoded header objects, while the
legacy ``compat32`` policy and caller-supplied raw values can still contain MIME
encoded words. This module provides one transport-tolerant decoder shared by the
stdlib adapter and RFC 5256 base-subject extraction.
"""

from __future__ import annotations

from email.errors import HeaderParseError
from email.header import decode_header

__all__ = ["decode_header_text"]


def decode_header_text(value: object) -> str:
    """Return ``value`` as decoded Unicode RFC 2047 header text.

    Unknown character-set labels fall back to best-effort UTF-8 decoding. A
    malformed encoded word is returned verbatim so one damaged header cannot
    abort mailbox ingestion.
    """
    text = str(value)
    try:
        decoded_header = decode_header(text)
    except HeaderParseError:
        return text

    decoded_parts: list[str] = []
    for part, charset in decoded_header:
        if isinstance(part, str):
            decoded_parts.append(part)
            continue

        encoding = charset or "ascii"
        try:
            decoded_parts.append(part.decode(encoding, errors="replace"))
        except LookupError:
            decoded_parts.append(part.decode("utf-8", errors="replace"))
    return "".join(decoded_parts)
