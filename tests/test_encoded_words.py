"""Tests for reusable RFC 2047 header-text decoding."""

from threadweave import decode_header_text


def test_returns_plain_text_unchanged():
    """Ordinary header text is already decoded."""
    assert decode_header_text("Plain subject") == "Plain subject"


def test_decodes_mixed_encoded_and_plain_parts():
    """Encoded words and surrounding ordinary text are joined as Unicode."""
    assert decode_header_text("Prefix =?utf-8?b?7JWI64WV?= suffix") == (
        "Prefix 안녕 suffix"
    )


def test_decodes_ascii_bytes_without_explicit_charset():
    """Encoded words lacking an explicit codec decode through ASCII."""
    assert decode_header_text("=?us-ascii?q?Hello?=") == "Hello"


def test_unknown_charset_falls_back_to_utf8_best_effort():
    """Unknown codec labels do not reject otherwise recoverable text."""
    assert decode_header_text("=?x-unknown?b?SGVsbG8=?=") == "Hello"


def test_malformed_encoded_word_is_returned_verbatim():
    """Malformed transport syntax is retained instead of aborting ingestion."""
    assert decode_header_text("=?utf-8?b?A?=") == "=?utf-8?b?A?="
