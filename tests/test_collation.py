"""Tests for RFC 5051 ``i;unicode-casemap`` comparison keys."""

from threadweave import unicode_casemap_key


def test_ascii_case_maps_to_one_key():
    """ASCII case differences compare equal under Unicode casemap."""
    assert unicode_casemap_key("Topic") == unicode_casemap_key("TOPIC")


def test_compatibility_characters_map_to_ascii_equivalents():
    """Compatibility decomposition collapses full-width forms."""
    assert unicode_casemap_key("Ｔｏｐｉｃ") == unicode_casemap_key("Topic")


def test_canonical_equivalents_map_to_one_key():
    """Precomposed and decomposed accents compare identically."""
    assert unicode_casemap_key("é") == unicode_casemap_key("e\u0301")


def test_rfc_5051_dz_caron_example_maps_all_case_forms_identically():
    """RFC 5051's U+01C4/U+01C5/U+01C6 example produces one key."""
    expected = "Dz\u030c"

    assert unicode_casemap_key("\u01c4") == expected
    assert unicode_casemap_key("\u01c5") == expected
    assert unicode_casemap_key("\u01c6") == expected


def test_visually_similar_scripts_remain_distinct():
    """Casemap does not collapse unrelated Latin and Greek characters."""
    assert unicode_casemap_key("A") != unicode_casemap_key("Α")


def test_simple_titlecase_does_not_apply_multi_character_expansions():
    """RFC 5051 uses UnicodeData simple titlecase, not full SpecialCasing."""
    assert unicode_casemap_key("ß") == "ß"
    assert unicode_casemap_key("ß") != unicode_casemap_key("SS")
    assert unicode_casemap_key("ﬀ") == "ff"
    assert unicode_casemap_key("ﬀ") != unicode_casemap_key("FF")
