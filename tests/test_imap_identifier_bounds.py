"""Tests for IMAP ``nz-number`` identifier limits."""

import pytest

from threadweave import (
    Container,
    Message,
    ThreadSerializationError,
    serialize_thread_data,
)


def test_maximum_imap_identifier_is_accepted():
    """The largest unsigned 32-bit non-zero value is a valid ``nz-number``."""
    root = Container(message=Message(sequence_number=4_294_967_295))
    assert serialize_thread_data([root]) == "THREAD (4294967295)"


def test_identifier_above_imap_nz_number_range_is_rejected():
    """RFC 5256 and RFC 9051 cap ``nz-number`` below 2**32."""
    root = Container(message=Message(sequence_number=4_294_967_296))
    with pytest.raises(ThreadSerializationError, match="unsigned 32-bit range"):
        serialize_thread_data([root])
