"""threadweave — standards-grounded email message threading for Python.

Assemble flat iterables of email messages into conversation trees using Jamie
Zawinski's container algorithm and RFC 5256 REFERENCES semantics, on top of RFC
5322 identification-field parsing, RFC 5051 Unicode casemap comparison, exact
RFC 5256 base-subject extraction, and optional RFC 5256 sent-date ordering.

    from threadweave import Message, thread_messages

    threads = thread_messages([
        Message(message_id="a"),
        Message(message_id="b", references=["a"]),
        Message(message_id="c", references=["a", "b"]),
    ])
    # -> one root Container; a is an ancestor of b, b of c.

The RFC 5322 header primitives (:mod:`threadweave.headers`) are extracted
behaviour-preserving from the naruon control plane; the threading, subject,
collation, and date layers are standalone implementations grounded in published
standards.
"""

from threadweave.adapters import message_from_email, thread_email_messages
from threadweave.collation import unicode_casemap_key
from threadweave.container import Container
from threadweave.dates import DateValue, normalize_sent_date
from threadweave.encoded_words import decode_header_text
from threadweave.headers import (
    extract_reference_ids,
    generate_email_fingerprint,
    normalize_message_id,
)
from threadweave.subject import (
    is_reply_or_forward_subject,
    is_reply_subject,
    normalize_subject,
)
from threadweave.threading import Message, thread_messages

__version__ = "0.1.0"

# REFERENCE_PATTERN is an implementation detail of `threadweave.headers`; use
# `extract_reference_ids`. It stays importable as `threadweave.headers.REFERENCE_PATTERN`.
__all__ = [
    "Container",
    "DateValue",
    "Message",
    "decode_header_text",
    "extract_reference_ids",
    "generate_email_fingerprint",
    "is_reply_or_forward_subject",
    "is_reply_subject",
    "message_from_email",
    "normalize_message_id",
    "normalize_sent_date",
    "normalize_subject",
    "thread_email_messages",
    "thread_messages",
    "unicode_casemap_key",
]
