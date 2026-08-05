"""Defensive graph-branch coverage for the incremental index."""

from __future__ import annotations

import pytest

import threadweave.incremental as incremental
from threadweave import (
    Container,
    IncrementalThreadError,
    IncrementalThreadIndex,
    IndexedMessage,
    MailboxChangeSet,
    Message,
    ThreadProjection,
)


def _record(key: str, message: Message | None = None, **identity: str) -> IndexedMessage:
    """Build one record for focused graph tests."""
    return IndexedMessage(
        key,
        Message(message_id=key) if message is None else message,
        **identity,
    )


def test_duplicate_references_missing_id_and_consistent_email_id_are_supported():
    """Deduplication and optional ID branches preserve valid historical mail."""
    index = IncrementalThreadIndex()
    index.apply(
        MailboxChangeSet(
            expected_version=0,
            additions=(
                _record(
                    "a",
                    Message(message_id=None, references=("<root>", "<root>")),
                    email_id="M1",
                    thread_id="T1",
                ),
                _record(
                    "b",
                    Message(message_id="b"),
                    email_id="M1",
                    thread_id="T1",
                ),
            ),
        )
    )
    assert index.message_keys == ("a", "b")


def test_candidate_expansion_adds_neighbors_reached_through_tokens():
    """The iterative candidate queue crosses every current reverse bucket."""
    assert incremental._expand_candidate_keys(
        {"a"},
        {"a": frozenset({"token"}), "b": frozenset({"token"})},
        {"token": {"a", "b"}},
    ) == {"a", "b"}


def test_projection_defenses_cover_dummy_cycle_and_foreign_messages():
    """Private batch-output validation remains loop-safe and fail-closed."""
    message = Message(message_id="a")
    record = _record("a", message)
    concrete = Container(message=message)
    concrete.children = [concrete]
    projection = incremental._projection_for_root(
        concrete,
        {id(message): "a"},
        {"a": record},
    )
    assert projection.message_keys == ("a",)

    dummy = Container()
    child = Container(message=message)
    dummy.children = [child]
    assert incremental._projection_for_root(
        dummy,
        {id(message): "a"},
        {"a": record},
    ).message_keys == ("a",)

    with pytest.raises(IncrementalThreadError, match="outside its component"):
        incremental._projection_for_root(child, {}, {"a": record})


def test_empty_projection_has_an_earliest_safe_sent_date_key():
    """A malformed empty projection remains deterministically sortable."""
    key = incremental._root_order_key(
        Container(),
        ThreadProjection(()),
        {},
        {},
        sort_by_sent_date=True,
    )
    assert key == (incremental.normalize_sent_date(None), 0, 0)


def test_replacement_recovers_when_derived_component_mapping_is_missing():
    """A defensive update rebuilds a record after derived-state loss."""
    index = IncrementalThreadIndex()
    index.apply(MailboxChangeSet(expected_version=0, additions=(_record("a"),)))
    index._component_by_key.pop("a")

    index.apply(
        MailboxChangeSet(
            expected_version=1,
            replacements=(
                _record("a", Message(message_id="a", subject="updated")),
            ),
        )
    )
    assert index.projections[0].message_keys == ("a",)
