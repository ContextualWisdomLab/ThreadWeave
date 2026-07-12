"""Tests for base-subject normalization."""

from threadweave import is_reply_subject, normalize_subject


def test_strip_single_re():
    assert normalize_subject("Re: Hello") == "Hello"


def test_strip_repeated_prefixes():
    assert normalize_subject("Re: Fwd: Re: Hello") == "Hello"


def test_case_insensitive():
    assert normalize_subject("RE: hello") == "hello"
    assert normalize_subject("fwd: hi") == "hi"
    assert normalize_subject("FW: hi") == "hi"


def test_collapse_whitespace():
    assert normalize_subject("Re:   Hello   World") == "Hello World"


def test_no_prefix_unchanged():
    assert normalize_subject("Hello") == "Hello"


def test_none_and_empty():
    assert normalize_subject(None) == ""
    assert normalize_subject("") == ""


def test_base_subjects_match_across_reply():
    assert normalize_subject("Hello") == normalize_subject("Re: Hello")


def test_is_reply_subject():
    assert is_reply_subject("Re: Hello")
    assert is_reply_subject("RE: Hello")
    assert not is_reply_subject("Hello")
    assert not is_reply_subject("Fwd: Hello")
    assert not is_reply_subject(None)
