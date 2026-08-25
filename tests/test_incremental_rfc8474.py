"""RFC 8474 identity grammar and namespace tests for incremental threading."""

import pytest

from threadweave import (
    ExternalIdentityError,
    IncrementalThreadError,
    IncrementalThreadIndex,
    IndexedMessage,
    MailboxChangeSet,
    Message,
)


def _record(
    key: str,
    *,
    email_id: str | None = None,
    thread_id: str | None = None,
) -> IndexedMessage:
    """Build one message carrying optional RFC 8474 identity metadata."""
    return IndexedMessage(
        message_key=key,
        message=Message(message_id=key),
        email_id=email_id,
        thread_id=thread_id,
    )


def test_object_ids_use_exact_ascii_grammar_and_length():
    """EMAILID and THREADID accept only 1-255 RFC ``objectid`` characters."""
    valid = "Abc_012-Z"
    record = _record("a", email_id=valid, thread_id="Thread_1")
    assert record.email_id == valid
    assert record.thread_id == "Thread_1"

    for field in ("email_id", "thread_id"):
        for invalid in ("contains space", "é", "x" * 256, "slash/value"):
            with pytest.raises(IncrementalThreadError, match=field):
                _record("a", **{field: invalid})


def test_email_id_and_thread_id_namespaces_are_disjoint():
    """One ObjectID value cannot be reused across EMAILID and THREADID data items."""
    index = IncrementalThreadIndex()
    with pytest.raises(ExternalIdentityError, match="disjoint ObjectID"):
        index.apply(
            MailboxChangeSet(
                expected_version=0,
                additions=(
                    _record("a", email_id="Shared1", thread_id="Thread1"),
                    _record("b", email_id="Mail2", thread_id="Shared1"),
                ),
            )
        )
    assert index.version == 0


def test_message_keys_reject_nonprintable_unicode_without_encoding_failure():
    """Caller keys fail during validation instead of later UTF-8 serialization."""
    for invalid in ("bad\ud800key", "line\u2028separator"):
        with pytest.raises(IncrementalThreadError, match="message_key.*printable"):
            _record(invalid)
