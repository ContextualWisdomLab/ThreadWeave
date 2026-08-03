"""RFC 5256 base-subject extraction and reply/forward classification.

The REFERENCES threading algorithm compares exact RFC 5256 base subjects when
reference headers alone do not connect two root threads. Extraction removes
standard reply/forward artifacts, mailing-list blobs, forward trailers, and
forward wrappers after decoding RFC 2047 encoded words.
"""

from __future__ import annotations

import re

from threadweave.encoded_words import decode_header_text

__all__ = [
    "is_reply_or_forward_subject",
    "is_reply_subject",
    "normalize_subject",
]

# RFC 5256 section 5 ABNF, applied after step 1 has normalized WSP to spaces.
_BLOB_PATTERN = r"\[[^\[\]]*\] *"
_REFWD_PATTERN = rf"(?:re|fw(?:d)?) *(?:{_BLOB_PATTERN})?:"
_LEADER_RE = re.compile(
    rf"^(?:{_BLOB_PATTERN})*{_REFWD_PATTERN}",
    re.IGNORECASE,
)
_BLOB_RE = re.compile(rf"^{_BLOB_PATTERN}")
_FORWARD_TRAILER_RE = re.compile(r"\(fwd\)$", re.IGNORECASE)
_RFC_WSP_RE = re.compile(r"[ \t\r\n]+")
_FORWARD_WRAPPER_PREFIX = "[fwd:"


def _normalize_subject(subject: str | None) -> tuple[str, bool]:
    """Return the RFC 5256 base subject and reply/forward-artifact flag."""
    if not subject:
        return "", False

    text = _RFC_WSP_RE.sub(" ", decode_header_text(subject))
    removed_reply_or_forward = False

    while True:
        # Step 2: remove trailing WSP and ``(fwd)`` artifacts repeatedly.
        while True:
            before_trailer = text
            text = text.rstrip(" ")
            trailer = _FORWARD_TRAILER_RE.search(text)
            if trailer is not None:
                text = text[: trailer.start()]
                removed_reply_or_forward = True
            if text == before_trailer:
                break

        # Steps 3-5: remove leaders and removable blobs until stable.
        while True:
            before_leader = text
            leader = _LEADER_RE.match(text)
            if leader is not None:
                text = text[leader.end() :]
                removed_reply_or_forward = True
            elif text.startswith(" "):
                text = text[1:]

            blob = _BLOB_RE.match(text)
            if blob is not None and text[blob.end() :]:
                text = text[blob.end() :]

            if text == before_leader:
                break

        # Step 6: unwrap ``[fwd: ...]`` and restart at trailer removal.
        if text[: len(_FORWARD_WRAPPER_PREFIX)].casefold() == (
            _FORWARD_WRAPPER_PREFIX
        ) and text.endswith("]"):
            text = text[len(_FORWARD_WRAPPER_PREFIX) : -1]
            removed_reply_or_forward = True
            continue

        return text, removed_reply_or_forward


def normalize_subject(subject: str | None) -> str:
    """Return the exact RFC 5256 base subject for ``subject``.

    RFC 2047 encoded words are decoded first. The extraction then normalizes
    RFC whitespace and removes reply/forward leaders, removable mailing-list
    blobs, ``(fwd)`` trailers, and ``[fwd: ...]`` wrappers.

        >>> normalize_subject("[list] Re: Fwd: Hello   World (fwd)")
        'Hello World'
        >>> normalize_subject("[only-a-blob]")
        '[only-a-blob]'
        >>> normalize_subject(None)
        ''
    """
    return _normalize_subject(subject)[0]


def is_reply_or_forward_subject(subject: str | None) -> bool:
    """Return whether RFC 5256 classifies ``subject`` as reply or forward.

    Classification is true only when extraction removes a ``subj-refwd``
    leader, a trailing ``(fwd)``, or a ``[fwd: ...]`` wrapper. Removing a
    mailing-list blob alone does not classify a message as a reply or forward.
    """
    return _normalize_subject(subject)[1]


def is_reply_subject(subject: str | None) -> bool:
    """Return RFC 5256 reply-or-forward classification for compatibility.

    This historical public name is retained for source compatibility. New code
    should prefer :func:`is_reply_or_forward_subject`, which states the RFC
    semantics explicitly.
    """
    return is_reply_or_forward_subject(subject)
