"""Adapters for Python's standard-library :mod:`email` message objects.

The core API intentionally stays transport-agnostic. These helpers remove the
boilerplate required to thread parsed RFC email messages while preserving each
source object as the default payload.
"""

from __future__ import annotations

from collections.abc import Iterable
from email.message import Message as EmailMessage
from typing import Any

from threadweave.container import Container
from threadweave.headers import extract_reference_ids, normalize_message_id
from threadweave.threading import Message, thread_messages

__all__ = ["message_from_email", "thread_email_messages"]

_PAYLOAD_MISSING = object()


def _header_text(message: EmailMessage, name: str) -> str | None:
    """Return one decoded header value as text, or ``None`` when absent."""
    value = message.get(name)
    return None if value is None else str(value)


def message_from_email(
    message: EmailMessage, *, payload: Any = _PAYLOAD_MISSING
) -> Message:
    """Convert a standard-library email message into a threadable message.

    Args:
        message: A parsed :class:`email.message.Message` or ``EmailMessage``.
        payload: Caller payload to carry through the resulting thread tree. When
            omitted, the source email message itself is retained. Passing
            ``None`` explicitly is therefore distinct from omitting the value.

    Returns:
        A normalized :class:`threadweave.Message` ready for
        :func:`threadweave.thread_messages`.
    """
    references = _header_text(message, "References")
    in_reply_to = _header_text(message, "In-Reply-To")
    return Message(
        message_id=normalize_message_id(_header_text(message, "Message-ID")),
        in_reply_to=extract_reference_ids(in_reply_to),
        references=extract_reference_ids(references),
        subject=_header_text(message, "Subject"),
        payload=message if payload is _PAYLOAD_MISSING else payload,
    )


def thread_email_messages(
    messages: Iterable[EmailMessage], *, group_by_subject: bool = False
) -> list[Container]:
    """Thread standard-library email messages without manual header mapping.

    The iterable is consumed once and every source message is retained as the
    corresponding ``Message.payload``.
    """
    converted = (message_from_email(message) for message in messages)
    return thread_messages(converted, group_by_subject=group_by_subject)
