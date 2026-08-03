"""Tests for standard-library email message integration."""

from email import policy
from email.message import EmailMessage
from email.parser import BytesParser

from threadweave import message_from_email, thread_email_messages


def _message(
    message_id: str,
    *,
    references: str | None = None,
    in_reply_to: str | None = None,
    subject: str | None = None,
) -> EmailMessage:
    """Build an ``EmailMessage`` with the threading headers under test."""
    message = EmailMessage()
    message["Message-ID"] = message_id
    if references is not None:
        message["References"] = references
    if in_reply_to is not None:
        message["In-Reply-To"] = in_reply_to
    if subject is not None:
        message["Subject"] = subject
    return message


def test_message_from_email_normalizes_threading_headers_and_preserves_payload():
    source = _message(
        "<child@example.com>",
        references="<root@example.com> <parent@example.com>",
        in_reply_to="<parent@example.com>",
        subject="Re: 안녕하세요",
    )

    converted = message_from_email(source)

    assert converted.message_id == "child@example.com"
    assert converted.references == ["root@example.com", "parent@example.com"]
    assert converted.in_reply_to == ["parent@example.com"]
    assert converted.subject == "Re: 안녕하세요"
    assert converted.payload is source


def test_message_from_email_decodes_encoded_words_under_compat32_policy():
    """Legacy parser policies still produce decoded Unicode header text."""
    source = BytesParser(policy=policy.compat32).parsebytes(
        b"Message-ID: <message@example.com>\r\n"
        b"Subject: =?utf-8?b?UmU6IOyViOuFle2VmOyEuOyalA==?=\r\n"
        b"\r\n"
    )

    converted = message_from_email(source)

    assert converted.subject == "Re: 안녕하세요"


def test_message_from_email_decodes_unknown_charset_best_effort():
    """Unknown encoded-word charsets do not leak transport syntax to callers."""
    source = BytesParser(policy=policy.compat32).parsebytes(
        b"Message-ID: <message@example.com>\r\n"
        b"Subject: =?x-unknown?b?SGVsbG8=?=\r\n"
        b"\r\n"
    )

    converted = message_from_email(source)

    assert converted.subject == "Hello"


def test_message_from_email_allows_explicit_none_payload():
    source = _message("<message@example.com>")

    converted = message_from_email(source, payload=None)

    assert converted.payload is None


def test_message_from_email_handles_missing_headers():
    source = EmailMessage()

    converted = message_from_email(source)

    assert converted.message_id is None
    assert converted.references == []
    assert converted.in_reply_to == []
    assert converted.subject is None
    assert converted.payload is source


def test_thread_email_messages_accepts_one_shot_iterables():
    source_messages = [
        _message("<root@example.com>", subject="Topic"),
        _message(
            "<child@example.com>",
            references="<root@example.com>",
            in_reply_to="<root@example.com>",
            subject="Re: Topic",
        ),
    ]

    roots = thread_email_messages(message for message in source_messages)

    assert len(roots) == 1
    assert roots[0].message.payload is source_messages[0]
    descendants = list(roots[0].iter_descendants())
    assert len(descendants) == 1
    assert descendants[0].message.payload is source_messages[1]
