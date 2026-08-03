"""Adapters for Python's standard-library :mod:`email` message objects.

The core API intentionally stays transport-agnostic. These helpers remove the
boilerplate required to thread parsed RFC email messages while preserving each
source object as the default payload. Optional mailbox metadata supplies the
``INTERNALDATE`` and sequence-number values required for RFC 5256 sent-date
ordering.
"""

from __future__ import annotations

from collections.abc import Iterable
from email.message import Message as EmailMessage
from typing import Any

from threadweave.container import Container
from threadweave.dates import DateValue
from threadweave.encoded_words import decode_header_text
from threadweave.headers import extract_reference_ids, normalize_message_id
from threadweave.threading import Message, thread_messages

__all__ = ["message_from_email", "thread_email_messages"]

_PAYLOAD_MISSING = object()


def _header_text(message: EmailMessage, name: str) -> str | None:
    """Return one decoded header value as text, or ``None`` when absent."""
    value = message.get(name)
    return None if value is None else decode_header_text(value)


def message_from_email(
    message: EmailMessage,
    *,
    payload: Any = _PAYLOAD_MISSING,
    internal_date: DateValue = None,
    sequence_number: int | None = None,
) -> Message:
    """Convert a standard-library email message into a threadable message.

    Args:
        message: A parsed :class:`email.message.Message` or ``EmailMessage``.
        payload: Caller payload to carry through the resulting tree. When
            omitted, the source email message itself is retained; explicitly
            passing ``None`` is therefore distinct from omitting the value.
        internal_date: Optional mailbox ``INTERNALDATE`` used when the message's
            ``Date`` header is absent or unusable during sent-date sorting.
        sequence_number: Optional positive mailbox sequence number used to break
            exact sent-date ties.

    Returns:
        A normalized :class:`threadweave.Message`. The decoded ``Date`` header,
        ``internal_date``, and ``sequence_number`` are retained as ordering
        metadata without changing the transport-agnostic threading core.
    """
    references = _header_text(message, "References")
    in_reply_to = _header_text(message, "In-Reply-To")
    return Message(
        message_id=normalize_message_id(_header_text(message, "Message-ID")),
        in_reply_to=extract_reference_ids(in_reply_to),
        references=extract_reference_ids(references),
        subject=_header_text(message, "Subject"),
        payload=message if payload is _PAYLOAD_MISSING else payload,
        sent_date=_header_text(message, "Date"),
        internal_date=internal_date,
        sequence_number=sequence_number,
    )


def thread_email_messages(
    messages: Iterable[EmailMessage],
    *,
    group_by_subject: bool = False,
    sort_by_sent_date: bool = False,
) -> list[Container]:
    """Thread standard-library email messages without manual header mapping.

    The iterable is consumed once and each source message is retained as its
    ``Message.payload``. Its one-based iteration order becomes the mailbox
    sequence number, giving direct mailbox ingestion a deterministic RFC 5256
    tie-breaker when ``sort_by_sent_date`` is enabled.
    """
    converted = (
        message_from_email(message, sequence_number=sequence_number)
        for sequence_number, message in enumerate(messages, start=1)
    )
    return thread_messages(
        converted,
        group_by_subject=group_by_subject,
        sort_by_sent_date=sort_by_sent_date,
    )
