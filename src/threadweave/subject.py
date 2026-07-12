"""Base-subject normalization for JWZ subject-based thread grouping.

Subject grouping is a **heuristic** fallback used only when ``References`` and
``In-Reply-To`` are unavailable: two messages whose subjects share the same base
(after stripping reply/forward prefixes) may belong to the same conversation.
"""

from __future__ import annotations

import re

__all__ = ["is_reply_subject", "normalize_subject"]

# Leading "Re:", "Fwd:", "Fw:" prefixes (case-insensitive), each optionally
# repeated, e.g. "Re: Fwd: Re: Hello". Stripped one prefix at a time.
_PREFIX_RE = re.compile(r"^\s*(?:re|fwd|fw)\s*:\s*", re.IGNORECASE)

# A subject is a "reply" (for JWZ 5C parent preference) iff it starts with "Re:".
_REPLY_RE = re.compile(r"^\s*re\s*:", re.IGNORECASE)


def normalize_subject(subject: str | None) -> str:
    """Return the base subject: reply/forward prefixes stripped, space-collapsed.

    Strips leading ``Re:`` / ``Fwd:`` / ``Fw:`` prefixes (case-insensitive,
    repeated) and collapses internal whitespace runs to single spaces.

        >>> normalize_subject("Re: Fwd: Hello   World")
        'Hello World'
        >>> normalize_subject("hello")
        'hello'
        >>> normalize_subject(None)
        ''
    """
    if not subject:
        return ""

    text = str(subject)
    while True:
        stripped = _PREFIX_RE.sub("", text, count=1)
        if stripped == text:
            break
        text = stripped

    return " ".join(text.split())


def is_reply_subject(subject: str | None) -> bool:
    """Return whether ``subject`` begins with a ``Re:`` reply prefix."""
    if not subject:
        return False
    return bool(_REPLY_RE.match(str(subject)))
