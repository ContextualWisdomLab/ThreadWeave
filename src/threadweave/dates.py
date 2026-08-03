"""RFC 5256 sent-date normalization for deterministic message ordering."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_tz
from typing import TypeAlias

DateValue: TypeAlias = datetime | str | None

__all__ = ["DateValue", "normalize_sent_date"]

_UTC = timezone.utc
_EARLIEST_SENT_DATE = datetime.min.replace(tzinfo=_UTC)
_NUMERIC_ZONE_RE = re.compile(r"(?P<sign>[+-])(?P<hour>\d{2})(?P<minute>\d{2})")
_DATE_RE = re.compile(
    r"(?P<day>\d{1,2})[\s-]+"
    r"(?P<month>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[\s-]+"
    r"(?P<year>\d{2,4})",
    re.IGNORECASE,
)
_NAMED_ZONE_RE = re.compile(
    r"\b(?:UT|GMT|EST|EDT|CST|CDT|MST|MDT|PST|PDT)\b",
    re.IGNORECASE,
)


def _numeric_zone_is_valid(text: str) -> bool:
    """Return whether the last numeric zone in ``text`` is semantically valid."""
    matches = list(_NUMERIC_ZONE_RE.finditer(text))
    if not matches:
        return True
    match = matches[-1]
    return int(match.group("hour")) <= 23 and int(match.group("minute")) <= 59


def _fallback_date_tuple(text: str) -> tuple[int, ...] | None:
    """Recover a valid calendar date when the Date header time is unparseable."""
    match = _DATE_RE.search(text)
    if match is None:
        return None

    zone_match = list(_NUMERIC_ZONE_RE.finditer(text))
    if zone_match and _numeric_zone_is_valid(text):
        zone = zone_match[-1].group(0)
    else:
        named_zone = _NAMED_ZONE_RE.search(text)
        zone = named_zone.group(0) if named_zone is not None else "+0000"

    synthetic = (
        f"{match.group('day')} {match.group('month')} {match.group('year')} "
        f"00:00:00 {zone}"
    )
    return parsedate_tz(synthetic)


def _parse_date_text(text: str) -> datetime | None:
    """Parse one RFC-style date string with RFC 5256 recovery semantics."""
    parsed = parsedate_tz(text)
    if parsed is None:
        parsed = _fallback_date_tuple(text)
    if parsed is None:
        return None

    year, month, day, hour, minute, second, *_ignored, offset = parsed
    try:
        datetime(year, month, day)
    except (OverflowError, ValueError):
        return None

    valid_time = 0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 60
    leap_second = valid_time and second == 60
    if not valid_time:
        hour = minute = second = 0
    elif leap_second:
        second = 59

    if offset is None or abs(offset) >= 24 * 60 * 60 or not _numeric_zone_is_valid(text):
        offset = 0

    try:
        local = datetime(
            year,
            month,
            day,
            hour,
            minute,
            second,
            tzinfo=timezone(timedelta(seconds=offset)),
        )
        normalized = local.astimezone(_UTC)
    except (OverflowError, ValueError):
        return None

    if leap_second:
        normalized += timedelta(microseconds=999_999)
    return normalized


def _normalize_one(value: DateValue) -> datetime | None:
    """Normalize one explicit date value, returning ``None`` when unusable."""
    if value is None:
        return None
    if isinstance(value, datetime):
        try:
            if value.tzinfo is None or value.utcoffset() is None:
                return value.replace(tzinfo=_UTC)
            return value.astimezone(_UTC)
        except (OverflowError, ValueError):
            return None
    if not isinstance(value, str):
        raise TypeError("date values must be datetime, str, or None")
    text = value.strip()
    return None if not text else _parse_date_text(text)


def normalize_sent_date(
    sent_date: DateValue,
    internal_date: DateValue = None,
) -> datetime:
    """Return an RFC 5256 sent date as an aware UTC :class:`datetime`.

    ``Date`` is preferred. Missing or unparseable values fall back to
    ``INTERNALDATE``. Invalid zones are treated as UTC, invalid times as local
    midnight, and a message with neither usable value sorts at the earliest
    representable UTC datetime. RFC 5322 leap seconds are represented as the
    final microsecond before the following midnight.
    """
    normalized = _normalize_one(sent_date)
    if normalized is not None:
        return normalized
    normalized = _normalize_one(internal_date)
    return _EARLIEST_SENT_DATE if normalized is None else normalized
