"""Tests for RFC 5256 base-subject extraction."""

from threadweave import (
    is_reply_or_forward_subject,
    is_reply_subject,
    normalize_subject,
)


def test_strips_single_reply_prefix():
    """A standard reply prefix is removed."""
    assert normalize_subject("Re: Hello") == "Hello"


def test_strips_repeated_reply_and_forward_prefixes():
    """Repeated RFC 5256 reply/forward leaders are removed."""
    assert normalize_subject("Re: Fwd: FW: Hello") == "Hello"


def test_prefix_tokens_are_case_insensitive():
    """RFC literals are matched case-insensitively."""
    assert normalize_subject("RE: hello") == "hello"
    assert normalize_subject("fwd: hi") == "hi"
    assert normalize_subject("FW: hi") == "hi"


def test_decodes_encoded_words_before_extracting_base_subject():
    """RFC 2047 encoded reply prefixes are normalized before matching."""
    assert normalize_subject("=?utf-8?q?Re=3A_=EC=95=88=EB=85=95?=") == "안녕"


def test_normalizes_tabs_continuations_and_multiple_spaces():
    """Tabs, folded lines, and repeated ASCII spaces collapse to one space."""
    assert normalize_subject("\tRe:\r\n\tHello   World  ") == "Hello World"


def test_strips_blob_before_reply_leader():
    """A mailing-list blob preceding a reply leader is an artifact."""
    assert normalize_subject("[project] Re: Topic") == "Topic"


def test_strips_blob_inside_reply_leader():
    """The optional blob between a reply token and colon is removed."""
    assert normalize_subject("Re [project]: Topic") == "Topic"


def test_strips_repeated_leading_blobs_while_base_remains():
    """Leading blobs are removed until the last blob would be the whole base."""
    assert normalize_subject("[outer] [inner] Topic") == "Topic"
    assert normalize_subject("[outer] [inner]") == "[inner]"


def test_keeps_blob_when_it_is_the_entire_base_subject():
    """RFC 5256 permits a final blob to be the base subject."""
    assert normalize_subject("[project]") == "[project]"


def test_strips_repeated_forward_trailers():
    """Every trailing ``(fwd)`` artifact and surrounding WSP is removed."""
    assert normalize_subject("Topic (fwd)  (FWD) ") == "Topic"


def test_unwraps_nested_forward_subjects_and_restarts_algorithm():
    """Forward wrappers are peeled and their inner subject is normalized anew."""
    assert normalize_subject("[Fwd: Re: [project] Topic (fwd)]") == "Topic"


def test_empty_and_none_subjects_have_empty_base():
    """Missing and empty subjects normalize to the empty base subject."""
    assert normalize_subject(None) == ""
    assert normalize_subject("") == ""


def test_plain_subject_is_unchanged_except_rfc_whitespace():
    """Meaningful subject text is preserved."""
    assert normalize_subject("  Hello   World ") == "Hello World"


def test_reply_or_forward_detection_matches_removed_artifacts():
    """Every RFC 5256 reply/forward artifact classifies the message."""
    assert is_reply_or_forward_subject("Re: Topic")
    assert is_reply_or_forward_subject("Fwd: Topic")
    assert is_reply_or_forward_subject("Topic (fwd)")
    assert is_reply_or_forward_subject("[fwd: Topic]")


def test_blob_removal_alone_does_not_mark_reply_or_forward():
    """Mailing-list blobs alone do not make a message a reply or forward."""
    assert not is_reply_or_forward_subject("[project] Topic")


def test_missing_plain_and_blob_only_subjects_are_not_replies():
    """Subjects without removed reply/forward artifacts classify as originals."""
    assert not is_reply_or_forward_subject(None)
    assert not is_reply_or_forward_subject("")
    assert not is_reply_or_forward_subject("Topic")
    assert not is_reply_or_forward_subject("[project]")


def test_historical_reply_predicate_uses_rfc_reply_or_forward_semantics():
    """The compatibility predicate delegates to the RFC 5256 classification."""
    assert is_reply_subject("Re: Topic")
    assert is_reply_subject("Fwd: Topic")
    assert not is_reply_subject("Topic")


def test_malformed_encoded_word_is_preserved_without_crashing():
    """Malformed transport syntax remains usable as ordinary subject text."""
    assert normalize_subject("=?utf-8?b?A?=") == "=?utf-8?b?A?="
