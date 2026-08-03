"""RFC 5051 ``i;unicode-casemap`` preparation for subject comparison.

RFC 5256 requires subject-table comparisons to use the Unicode casemap
collation. The preparation algorithm titlecases each Unicode code point and
recursively applies canonical and compatibility decomposition before comparison.
Python strings are already Unicode scalar sequences, so the resulting string can
serve directly as a deterministic comparison key.
"""

from __future__ import annotations

import unicodedata

__all__ = ["unicode_casemap_key"]


def unicode_casemap_key(value: str) -> str:
    """Return the RFC 5051 ``i;unicode-casemap`` preparation key for ``value``.

    Preparation is performed independently for every input code point: apply
    its Unicode titlecase mapping, then recursively apply canonical and
    compatibility decomposition. The implementation uses Python's bundled
    Unicode Character Database, so newly assigned code points can acquire newer
    mappings as the supported Python runtime advances.

        >>> unicode_casemap_key("Ｔｏｐｉｃ") == unicode_casemap_key("Topic")
        True
        >>> unicode_casemap_key("é") == unicode_casemap_key("e\\u0301")
        True
        >>> unicode_casemap_key("\\u01c4")
        'Dž'
    """
    return "".join(
        unicodedata.normalize("NFKD", character.title()) for character in value
    )
