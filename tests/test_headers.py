"""Tests for the RFC 5322 identification-field primitives."""

from threadweave import (
    extract_reference_ids,
    generate_email_fingerprint,
    normalize_message_id,
)


def test_normalize_message_id_strips_brackets():
    assert normalize_message_id("<x@y>") == "x@y"


def test_normalize_message_id_strips_surrounding_whitespace():
    assert normalize_message_id("  <a@b>  ") == "a@b"


def test_normalize_message_id_none_and_empty():
    assert normalize_message_id(None) is None
    assert normalize_message_id("") is None
    assert normalize_message_id("<>") is None
    assert normalize_message_id("   ") is None


def test_extract_reference_ids_bracketed():
    assert extract_reference_ids("<a@x> <b@y>") == ["a@x", "b@y"]


def test_extract_reference_ids_dedup_preserves_order():
    assert extract_reference_ids("<a@x> <b@y> <a@x>") == ["a@x", "b@y"]


def test_extract_reference_ids_whitespace_fallback():
    # No angle brackets: fall back to whitespace splitting.
    assert extract_reference_ids("a@x b@y") == ["a@x", "b@y"]


def test_extract_reference_ids_empty():
    assert extract_reference_ids("") == []
    assert extract_reference_ids(None) == []


def test_generate_email_fingerprint_deterministic():
    a = generate_email_fingerprint("Hi", "2026-07-12", "s@x", "r@y")
    b = generate_email_fingerprint("Hi", "2026-07-12", "s@x", "r@y")
    assert a == b
    assert len(a) == 64  # SHA-256 hex digest


def test_generate_email_fingerprint_case_insensitive():
    a = generate_email_fingerprint("Hello", "d", "SENDER", "R")
    b = generate_email_fingerprint("hello", "d", "sender", "r")
    assert a == b


def test_generate_email_fingerprint_distinguishes_content():
    a = generate_email_fingerprint("Hello", "d", "s", "r")
    b = generate_email_fingerprint("Goodbye", "d", "s", "r")
    assert a != b
