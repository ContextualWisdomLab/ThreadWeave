"""RFC 5051 ``i;unicode-casemap`` preparation for subject comparison.

RFC 5256 requires subject-table comparisons to use the Unicode casemap
collation. The preparation algorithm applies each code point's *simple* Unicode
titlecase mapping from ``UnicodeData.txt`` and then recursively applies canonical
and compatibility decomposition before comparison.
"""

from __future__ import annotations

import unicodedata

__all__ = ["unicode_casemap_key"]


def _simple_titlecase(character: str) -> str:
    """Return one code point's simple Unicode titlecase mapping.

    Python's ``str.title`` exposes the full titlecase mapping and can expand one
    code point into several characters through ``SpecialCasing.txt``. RFC 5051
    instead uses the single-code-point mapping in ``UnicodeData.txt``. Across
    the supported Unicode databases, an expanding full mapping has no simple
    mapping and therefore leaves the original code point unchanged.
    """
    mapped = character.title()
    return mapped if len(mapped) == 1 else character


def unicode_casemap_key(value: str) -> str:
    """Return the RFC 5051 ``i;unicode-casemap`` preparation key for ``value``.

    Preparation is performed independently for every input code point: apply
    its simple Unicode titlecase mapping, then recursively apply canonical and
    compatibility decomposition. The implementation uses Python's bundled
    Unicode Character Database, so newly assigned code points can acquire newer
    mappings as the supported Python runtime advances.

        >>> unicode_casemap_key("Ｔｏｐｉｃ") == unicode_casemap_key("Topic")
        True
        >>> unicode_casemap_key("é") == unicode_casemap_key("e\\u0301")
        True
        >>> unicode_casemap_key("\\u01c4")
        'Dž'
        >>> unicode_casemap_key("ß")
        'ß'
    """
    return "".join(
        unicodedata.normalize("NFKD", _simple_titlecase(character))
        for character in value
    )
