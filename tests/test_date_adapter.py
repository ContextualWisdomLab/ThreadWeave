"""Tests for Date metadata in the standard-library email adapter."""

from email.message import EmailMessage

from threadweave import message_from_email, thread_email_messages


def test_message_from_email_carries_date_and_mailbox_metadata():
    """Ordering and protocol identifiers reach the transport-neutral model."""
    source = EmailMessage()
    source["Message-ID"] = "<message@example.com>"
    source["Date"] = "Tue, 06 Jun 2017 07:39:33 +0600"

    converted = message_from_email(
        source,
        internal_date="06-Jun-2017 02:00:00 +0000",
        sequence_number=7,
        uid=70,
    )

    assert converted.sent_date == "Tue, 06 Jun 2017 07:39:33 +0600"
    assert converted.internal_date == "06-Jun-2017 02:00:00 +0000"
    assert converted.sequence_number == 7
    assert converted.uid == 70


def test_thread_email_messages_uses_iterable_order_as_sequence_number():
    """Direct mailbox ingestion gets deterministic RFC tie-breaking for free."""
    later = EmailMessage()
    later["Message-ID"] = "<later@example.com>"
    later["Date"] = "2 Jan 2026 00:00:00 +0000"
    earlier = EmailMessage()
    earlier["Message-ID"] = "<earlier@example.com>"
    earlier["Date"] = "1 Jan 2026 00:00:00 +0000"

    roots = thread_email_messages(
        [later, earlier],
        sort_by_sent_date=True,
    )

    assert [root.message.message_id for root in roots] == [
        "earlier@example.com",
        "later@example.com",
    ]
    assert [root.message.sequence_number for root in roots] == [2, 1]
