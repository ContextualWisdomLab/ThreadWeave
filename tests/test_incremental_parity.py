"""RFC, ordering, protocol, and depth parity for the incremental index."""

from __future__ import annotations

import pytest

from threadweave import (
    IncrementalThreadIndex,
    IncrementalThreadError,
    IndexedMessage,
    MailboxChangeSet,
    Message,
    serialize_thread_response,
    thread_messages,
)


def _record(key: str, **message_fields) -> IndexedMessage:
    """Build one record whose payload remains its caller key."""
    return IndexedMessage(
        message_key=key,
        message=Message(payload=key, **message_fields),
    )


def _preorder(roots) -> tuple[tuple[str | None, ...], ...]:
    """Return root-by-root preorder payload keys without recursion."""
    forest: list[tuple[str | None, ...]] = []
    for root in roots:
        keys: list[str | None] = []
        stack = [root]
        seen: set[int] = set()
        while stack:
            node = stack.pop()
            if id(node) in seen:
                continue
            seen.add(id(node))
            keys.append(None if node.message is None else node.message.payload)
            stack.extend(reversed(node.children))
        forest.append(tuple(keys))
    return tuple(forest)


def test_subject_grouping_uses_rfc_5051_and_replacement_updates_bucket():
    """Compatibility-width and reply variants merge and later split by replacement."""
    first = _record("a", message_id="a", subject="Ｔｏｐｉｃ")
    second = _record("b", message_id="b", subject="Re: Topic")
    index = IncrementalThreadIndex(group_by_subject=True)
    index.apply(MailboxChangeSet(expected_version=0, additions=(first, second)))

    batch = thread_messages(
        (first.message, second.message),
        group_by_subject=True,
    )
    assert _preorder(index.roots) == _preorder(batch)
    assert len(index.roots) == 1

    replacement = _record("b", message_id="b", subject="Different")
    delta = index.apply(
        MailboxChangeSet(expected_version=1, replacements=(replacement,))
    )
    batch_after = thread_messages(
        (first.message, replacement.message),
        group_by_subject=True,
    )
    assert _preorder(index.roots) == _preorder(batch_after)
    assert len(index.roots) == 2
    assert len(delta.splits) == 1


def test_sent_date_order_matches_batch_across_unrelated_components():
    """Global root ordering uses RFC date recovery and sequence tie-breaking."""
    records = (
        _record(
            "later",
            message_id="later",
            sent_date="2 Jan 2026 00:00:00 +0000",
            sequence_number=2,
        ),
        _record(
            "earlier",
            message_id="earlier",
            sent_date="1 Jan 2026 09:00:00 +0900",
            sequence_number=1,
        ),
        _record(
            "same_time",
            message_id="same-time",
            sent_date="1 Jan 2026 00:00:00 +0000",
            sequence_number=3,
        ),
    )
    index = IncrementalThreadIndex(sort_by_sent_date=True)
    index.apply(MailboxChangeSet(expected_version=0, additions=records))

    batch = thread_messages(
        (record.message for record in records),
        sort_by_sent_date=True,
    )
    assert _preorder(index.roots) == _preorder(batch)
    assert tuple(projection.message_keys for projection in index.projections) == (
        ("earlier",),
        ("same_time",),
        ("later",),
    )


def test_global_sequence_number_collision_fails_atomically():
    """Separate components cannot hide duplicate RFC ordering tie-breakers."""
    index = IncrementalThreadIndex(sort_by_sent_date=True)
    index.apply(
        MailboxChangeSet(
            expected_version=0,
            additions=(
                _record("a", message_id="a", sequence_number=1),
            ),
        )
    )
    before = index.snapshot()

    with pytest.raises(IncrementalThreadError, match="duplicate sequence number"):
        index.apply(
            MailboxChangeSet(
                expected_version=1,
                additions=(
                    _record("b", message_id="b", sequence_number=1),
                ),
            )
        )
    assert index.snapshot() == before


def test_raw_reference_headers_and_uid_thread_output_match_batch():
    """The index preserves raw RFC input and feeds the installed IMAP projector."""
    records = (
        _record(
            "root",
            message_id="<root@example.test>",
            sequence_number=1,
            uid=101,
        ),
        _record(
            "child",
            message_id="<child@example.test>",
            references="<root@example.test>",
            in_reply_to="<root@example.test> <ignored@example.test>",
            sequence_number=2,
            uid=102,
        ),
    )
    index = IncrementalThreadIndex()
    index.apply(MailboxChangeSet(expected_version=0, additions=records))

    batch = thread_messages(record.message for record in records)
    assert _preorder(index.roots) == _preorder(batch)
    assert serialize_thread_response(index.roots) == "* THREAD (1 2)\r\n"
    assert serialize_thread_response(index.roots, identifier="uid") == (
        "* THREAD (101 102)\r\n"
    )


def test_deep_delayed_ancestry_update_remains_iterative():
    """A deep component can be indexed and extended without recursion limits."""
    depth = 1500
    records = tuple(
        _record(
            f"message_{index}",
            message_id=f"message_{index}",
            references=() if index == 0 else (f"message_{index - 1}",),
        )
        for index in range(depth)
    )
    index = IncrementalThreadIndex()
    index.apply(MailboxChangeSet(expected_version=0, additions=records))

    tail = _record(
        "tail",
        message_id="tail",
        references=(f"message_{depth - 1}",),
    )
    delta = index.apply(
        MailboxChangeSet(expected_version=1, additions=(tail,))
    )

    assert len(index.projections) == 1
    assert len(index.projections[0].message_keys) == depth + 1
    assert index.projections[0].message_keys[-1] == "tail"
    assert len(delta.affected_message_keys) == depth + 1


def test_implicit_sequence_positions_remain_stable_after_replacement():
    """Replacing metadata does not move a caller key to the end of input order."""
    first = _record("a", message_id="a", sent_date="1 Jan 2026 00:00:00 +0000")
    second = _record("b", message_id="b", sent_date="1 Jan 2026 00:00:00 +0000")
    index = IncrementalThreadIndex(sort_by_sent_date=True)
    index.apply(MailboxChangeSet(expected_version=0, additions=(first, second)))

    replacement = _record(
        "a",
        message_id="a",
        sent_date="1 Jan 2026 00:00:00 +0000",
        subject="updated",
    )
    index.apply(
        MailboxChangeSet(expected_version=1, replacements=(replacement,))
    )

    assert tuple(projection.message_keys for projection in index.projections) == (
        ("a",),
        ("b",),
    )
