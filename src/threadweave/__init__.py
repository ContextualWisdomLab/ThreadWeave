"""threadweave — the canonical JWZ message-threading algorithm for Python.

Assemble flat lists of email messages into conversation trees using Jamie
Zawinski's threading algorithm (https://www.jwz.org/doc/threading.html), on top
of RFC 5322 §3.6.4 identification-field parsing.

    from threadweave import Message, thread_messages

    threads = thread_messages([
        Message(message_id="a"),
        Message(message_id="b", references=["a"]),
        Message(message_id="c", references=["a", "b"]),
    ])
    # -> one root Container; a is an ancestor of b, b of c.

The RFC 5322 header primitives (:mod:`threadweave.headers`) are extracted
behaviour-preserving from the naruon control plane; the JWZ assembly
(:mod:`threadweave.threading`) is a fresh canonical implementation.
"""

from threadweave.container import Container
from threadweave.headers import (
    extract_reference_ids,
    generate_email_fingerprint,
    normalize_message_id,
)
from threadweave.subject import is_reply_subject, normalize_subject
from threadweave.threading import Message, thread_messages

__version__ = "0.1.0"

# REFERENCE_PATTERN is an implementation detail of `threadweave.headers`; use
# `extract_reference_ids`. It stays importable as `threadweave.headers.REFERENCE_PATTERN`.
__all__ = [
    "Container",
    "Message",
    "extract_reference_ids",
    "generate_email_fingerprint",
    "is_reply_subject",
    "normalize_message_id",
    "normalize_subject",
    "thread_messages",
]
