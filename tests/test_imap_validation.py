"""Additional selector validation for RFC 5256 THREAD serialization."""

import pytest

from threadweave import Container, Message, serialize_thread_data


def test_non_callable_identifier_is_rejected():
    """A non-string non-callable selector is invalid."""
    root = Container(message=Message(sequence_number=1))
    with pytest.raises(ValueError, match="sequence_number.*uid"):
        serialize_thread_data(
            [root],
            identifier=object(),  # type: ignore[arg-type]
        )
