"""Tests for RFC 5256 sent-date normalization."""

from datetime import datetime, timedelta, timezone

import pytest

from threadweave import normalize_sent_date

UTC = timezone.utc


def test_normalizes_valid_numeric_zone_to_utc():
    """A valid Date header is shifted from its zone into UTC."""
    assert normalize_sent_date("31 Dec 2000 16:01:33 -0800") == datetime(
        2001, 1, 1, 0, 1, 33, tzinfo=UTC
    )


def test_naive_datetime_is_treated_as_utc():
    """A datetime without zone information follows the RFC invalid-zone rule."""
    value = datetime(2026, 8, 3, 12, 30)
    assert normalize_sent_date(value) == value.replace(tzinfo=UTC)


def test_invalid_numeric_zone_is_treated_as_utc():
    """An impossible numeric offset does not discard an otherwise valid date."""
    assert normalize_sent_date("Tue, 06 Jun 2017 07:39:33 +2600") == datetime(
        2017, 6, 6, 7, 39, 33, tzinfo=UTC
    )


def test_invalid_time_becomes_midnight_in_the_valid_zone():
    """An invalid time becomes local midnight before UTC normalization."""
    assert normalize_sent_date("Tue, 06 Jun 2017 27:39:33 +0600") == datetime(
        2017, 6, 5, 18, 0, 0, tzinfo=UTC
    )


def test_date_without_time_uses_midnight_utc():
    """A valid date with no usable time or zone falls back to midnight UTC."""
    assert normalize_sent_date("Tue, 06 Jun 2017") == datetime(
        2017, 6, 6, 0, 0, 0, tzinfo=UTC
    )


def test_missing_or_unparseable_date_uses_internal_date():
    """INTERNALDATE is the fallback when Date is missing or cannot be parsed."""
    internal = "17-Jul-1996 02:44:25 -0700"
    expected = datetime(1996, 7, 17, 9, 44, 25, tzinfo=UTC)
    assert normalize_sent_date(None, internal) == expected
    assert normalize_sent_date("not a date", internal) == expected


def test_no_valid_date_uses_earliest_representable_utc_datetime():
    """Missing Date and INTERNALDATE sort at the earliest possible instant."""
    assert normalize_sent_date(None, None) == datetime.min.replace(tzinfo=UTC)
    assert normalize_sent_date("not a date", "also invalid") == datetime.min.replace(
        tzinfo=UTC
    )


def test_leap_second_sorts_after_ordinary_final_second_before_midnight():
    """RFC 5322's leap second is represented immediately before next midnight."""
    result = normalize_sent_date("Sat, 31 Dec 2016 23:59:60 +0000")
    assert result == datetime(2016, 12, 31, 23, 59, 59, 999999, tzinfo=UTC)
    assert result > datetime(2016, 12, 31, 23, 59, 59, tzinfo=UTC)
    assert result < datetime(2017, 1, 1, 0, 0, 0, tzinfo=UTC)


def test_aware_datetime_is_normalized_to_utc():
    """Caller-supplied aware datetimes retain their instant."""
    value = datetime(2026, 8, 3, 9, 0, tzinfo=timezone(timedelta(hours=9)))
    assert normalize_sent_date(value) == datetime(2026, 8, 3, 0, 0, tzinfo=UTC)


def test_unsupported_date_value_type_is_rejected():
    """Unexpected metadata types fail explicitly instead of sorting arbitrarily."""
    with pytest.raises(TypeError, match="datetime, str, or None"):
        normalize_sent_date(123)  # type: ignore[arg-type]


def test_unparseable_time_recovers_calendar_date_and_valid_zone():
    """A malformed time token still preserves a valid date and numeric zone."""
    assert normalize_sent_date("Tue, 06 Jun 2017 broken +0600") == datetime(
        2017, 6, 5, 18, 0, 0, tzinfo=UTC
    )


def test_unparseable_time_recovers_named_zone():
    """A known obsolete zone remains usable when the time itself is invalid."""
    assert normalize_sent_date("Tue, 06 Jun 2017 broken EST") == datetime(
        2017, 6, 6, 5, 0, 0, tzinfo=UTC
    )


def test_invalid_calendar_date_uses_internal_date():
    """An impossible calendar date cannot outrank a valid INTERNALDATE."""
    internal = datetime(2026, 1, 1, tzinfo=UTC)
    assert normalize_sent_date("30 Feb 2026 12:00:00 +0000", internal) == internal


def test_text_conversion_overflow_uses_internal_date():
    """A UTC conversion outside datetime's range is treated as unusable."""
    internal = datetime(2026, 1, 1, tzinfo=UTC)
    assert normalize_sent_date("31 Dec 9999 23:59:59 -2300", internal) == internal


def test_datetime_conversion_overflow_uses_internal_date():
    """Caller datetime overflow also falls back to INTERNALDATE."""
    value = datetime(1, 1, 1, tzinfo=timezone(timedelta(hours=23)))
    internal = datetime(2026, 1, 1, tzinfo=UTC)
    assert normalize_sent_date(value, internal) == internal


def test_blank_date_string_is_unusable():
    """Whitespace-only Date metadata follows the normal fallback path."""
    internal = datetime(2026, 1, 1, tzinfo=UTC)
    assert normalize_sent_date("   ", internal) == internal
