"""Adapters for Python's standard-library :mod:`email` message objects.

The core API intentionally stays transport-agnostic. These helpers remove the
boilerplate required to thread parsed RFC email messages while preserving each
source object as the default payload. Optional mailbox metadata supplied to
``message_from_email`` carries ``INTERNALDATE``, sequence-number, and UID values
used by RFC 5256 ordering and THREAD response serialization; the bulk adapter
does not invent public mailbox identifiers from iterable position.
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
    uid: int | None = None,
) -> Message:
    """Convert a standard-library email message into a threadable message.

    Args:
        message: A parsed :class:`email.message.Message` or ``EmailMessage``.
        payload: Caller payload to carry through the resulting tree. When
            omitted, the source email message itself is retained; explicitly
            passing ``None`` is therefore distinct from omitting the value.
        internal_date: Optional mailbox ``INTERNALDATE`` used when the message's
            ``Date`` header is absent or unusable during sent-date sorting.
        sequence_number: Optional positive mailbox sequence number used for
            ordering and THREAD responses.
        uid: Optional positive IMAP unique identifier for UID THREAD output.

    Returns:
        A normalized :class:`threadweave.Message`. The decoded ``Date`` header,
        ``internal_date``, ``sequence_number``, and ``uid`` are retained as
        mailbox metadata without changing the transport-agnostic core.
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
        uid=uid,
    )


def thread_email_messages(
    messages: Iterable[EmailMessage],
    *,
    group_by_subject: bool = False,
    sort_by_sent_date: bool = False,
) -> list[Container]:
    """Thread standard-library email messages without inventing mailbox IDs.

    The iterable is consumed once and each source message is retained as its
    ``Message.payload``. When sent-date ordering is enabled, ``thread_messages``
    may use one-based input position as an internal deterministic ordering
    fallback, but this adapter does not store that position in
    ``Message.sequence_number``. Callers that own real mailbox sequence numbers
    or UIDs can supply them explicitly through ``message_from_email`` before
    calling the canonical threader.
    """
    converted = (message_from_email(message) for message in messages)
    return thread_messages(
        converted,
        group_by_subject=group_by_subject,
        sort_by_sent_date=sort_by_sent_date,
    )
