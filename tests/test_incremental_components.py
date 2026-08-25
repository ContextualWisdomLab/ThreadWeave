"""Component and delta tests for incremental mailbox threading."""

from __future__ import annotations

import pytest

from collections.abc import Iterable

import threadweave.incremental as incremental_module
from threadweave import (
    Container,
    IncrementalThreadIndex,
    IndexedMessage,
    MailboxChangeSet,
    Message,
    thread_messages,
)


def _record(
    key: str,
    *,
    message_id: str | None = None,
    references: tuple[str, ...] = (),
    in_reply_to: tuple[str, ...] = (),
    subject: str | None = None,
    sent_date: str | None = None,
    sequence_number: int | None = None,
    uid: int | None = None,
    email_id: str | None = None,
    thread_id: str | None = None,
) -> IndexedMessage:
    """Build one record whose payload exposes the caller key to tests."""
    return IndexedMessage(
        message_key=key,
        message=Message(
            message_id=message_id if message_id is not None else key,
            references=references,
            in_reply_to=in_reply_to,
            subject=subject,
            payload=key,
            sent_date=sent_date,
            sequence_number=sequence_number,
            uid=uid,
        ),
        email_id=email_id,
        thread_id=thread_id,
    )


def _shape(roots: Iterable[Container]) -> tuple[object, ...]:
    """Return one deterministic, iterative forest representation."""
    rendered: list[object] = []
    for root in roots:
        output: list[object] = []
        stack: list[tuple[Container, bool]] = [(root, False)]
        built: dict[int, object] = {}
        while stack:
            node, exiting = stack.pop()
            if not exiting:
                stack.append((node, True))
                for child in reversed(node.children):
                    stack.append((child, False))
                continue
            children = tuple(built[id(child)] for child in node.children)
            key = None if node.message is None else node.message.payload
            built[id(node)] = (key, children)
        output.append(built[id(root)])
        rendered.extend(output)
    return tuple(rendered)


def _batch(
    records: Iterable[IndexedMessage],
    *,
    group_by_subject: bool = False,
    sort_by_sent_date: bool = False,
) -> tuple[object, ...]:
    """Return the canonical batch shape for indexed records."""
    return _shape(
        thread_messages(
            (record.message for record in records),
            group_by_subject=group_by_subject,
            sort_by_sent_date=sort_by_sent_date,
        )
    )


def test_additions_match_batch_and_preserve_independent_root_order():
    """Initial component construction is exactly equivalent to one batch call."""
    records = (
        _record("a"),
        _record("b", references=("a",)),
        _record("x"),
        _record("y", references=("x",)),
    )
    index = IncrementalThreadIndex()
    delta = index.apply(MailboxChangeSet(expected_version=0, additions=records))

    assert _shape(index.roots) == _batch(records)
    assert index.message_keys == ("a", "b", "x", "y")
    assert delta.affected_message_keys == ("a", "b", "x", "y")
    assert tuple(projection.message_keys for projection in index.projections) == (
        ("a", "b"),
        ("x", "y"),
    )
    assert len(delta.added_threads) == 2
    assert delta.removed_threads == ()


def test_delayed_missing_ancestor_recomputes_only_the_affected_component():
    """A late parent replaces a dummy without touching an unrelated thread."""
    child = _record("child", references=("root",))
    other = _record("other")
    index = IncrementalThreadIndex()
    index.apply(
        MailboxChangeSet(expected_version=0, additions=(child, other))
    )

    root = _record("root")
    delta = index.apply(
        MailboxChangeSet(expected_version=1, additions=(root,))
    )

    assert _shape(index.roots) == _batch((child, other, root))
    assert delta.affected_message_keys == ("child", "root")
    assert tuple(projection.message_keys for projection in index.projections) == (
        ("root", "child"),
        ("other",),
    )


def test_bridge_message_emits_an_explicit_external_identity_merge():
    """Joining two exposed groups reports both caller THREADIDs."""
    first = _record("a", thread_id="T1")
    second = _record("b", thread_id="T2")
    index = IncrementalThreadIndex()
    index.apply(
        MailboxChangeSet(expected_version=0, additions=(first, second))
    )

    bridge = _record("bridge", references=("a", "b"), thread_id="T3")
    delta = index.apply(
        MailboxChangeSet(expected_version=1, additions=(bridge,))
    )

    assert _shape(index.roots) == _batch((first, second, bridge))
    assert len(delta.merges) == 1
    merge = delta.merges[0]
    assert merge.kind == "merge"
    assert merge.thread_ids == ("T1", "T2", "T3")
    assert tuple(item.message_keys for item in merge.before) == (("a",), ("b",))
    assert tuple(item.message_keys for item in merge.after) == (("a", "b", "bridge"),)


def test_replacing_bridge_references_emits_a_split_and_matches_batch():
    """Removing a structural bridge rediscovers both resulting components."""
    first = _record("a", thread_id="T1")
    second = _record("b", thread_id="T2")
    bridge = _record("bridge", references=("a", "b"), thread_id="T3")
    index = IncrementalThreadIndex()
    index.apply(
        MailboxChangeSet(expected_version=0, additions=(first, second, bridge))
    )

    replacement = _record("bridge", references=("a",), thread_id="T3")
    delta = index.apply(
        MailboxChangeSet(expected_version=1, replacements=(replacement,))
    )

    assert _shape(index.roots) == _batch((first, second, replacement))
    assert len(delta.splits) == 1
    split = delta.splits[0]
    assert split.kind == "split"
    assert split.thread_ids == ("T1", "T2", "T3")
    assert tuple(item.message_keys for item in split.before) == (
        ("a", "b", "bridge"),
    )
    assert {item.message_keys for item in split.after} == {
        ("a", "bridge"),
        ("b",),
    }


def test_removing_root_internal_leaf_and_duplicate_id_matches_batch():
    """Every removal location follows canonical dummy pruning and promotion."""
    records = (
        _record("root"),
        _record("middle", references=("root",)),
        _record("leaf", references=("root", "middle")),
        _record("duplicate", message_id="middle"),
        _record("missing", message_id=None),
    )

    for removed_key in ("root", "middle", "leaf", "duplicate", "missing"):
        index = IncrementalThreadIndex()
        index.apply(MailboxChangeSet(expected_version=0, additions=records))
        index.apply(
            MailboxChangeSet(expected_version=1, removals=(removed_key,))
        )
        remaining = tuple(record for record in records if record.message_key != removed_key)
        assert _shape(index.roots) == _batch(remaining)


def test_unrelated_components_are_not_passed_to_the_batch_delegate(monkeypatch):
    """A bounded update avoids rescanning a structurally unrelated component."""
    records = (
        _record("a"),
        _record("b", references=("a",)),
        _record("x"),
        _record("y", references=("x",)),
    )
    index = IncrementalThreadIndex()
    index.apply(MailboxChangeSet(expected_version=0, additions=records))

    calls: list[tuple[str, ...]] = []
    real_delegate = incremental_module._batch_thread_messages

    def recording_delegate(messages, **options):
        """Record component payload keys before invoking the canonical batcher."""
        materialized = tuple(messages)
        calls.append(tuple(message.payload for message in materialized))
        return real_delegate(materialized, **options)

    monkeypatch.setattr(incremental_module, "_batch_thread_messages", recording_delegate)
    replacement = _record("b", references=("a",), subject="changed")
    index.apply(
        MailboxChangeSet(expected_version=1, replacements=(replacement,))
    )

    assert calls == [("a", "b"), ("a", "b")]
    assert all("x" not in call and "y" not in call for call in calls)


def test_noop_change_set_advances_no_version_and_returns_empty_delta():
    """An empty request is idempotent and does not fabricate a new revision."""
    index = IncrementalThreadIndex()
    delta = index.apply(MailboxChangeSet(expected_version=0))

    assert delta.previous_version == 0
    assert delta.version == 0
    assert delta.affected_message_keys == ()
    assert delta.added_threads == ()
    assert delta.removed_threads == ()
    assert delta.updated_threads == ()
    assert delta.merges == ()
    assert delta.splits == ()


def test_delta_classification_receives_only_affected_component_projections(
    monkeypatch: pytest.MonkeyPatch,
):
    """Unrelated roots never enter one small change's delta classifier."""
    records = tuple(
        _record(f"key_{index}", message_id=f"message_{index}")
        for index in range(128)
    )
    index = IncrementalThreadIndex()
    index.apply(MailboxChangeSet(expected_version=0, additions=records))

    original = incremental_module._thread_delta
    observed_sizes: list[tuple[int, int]] = []

    def recording_delta(*args):
        """Record old/new projection counts before delegating."""
        observed_sizes.append((len(args[3]), len(args[4])))
        return original(*args)

    monkeypatch.setattr(incremental_module, "_thread_delta", recording_delta)
    index.apply(
        MailboxChangeSet(
            expected_version=1,
            additions=(
                _record(
                    "new_key",
                    message_id="new_message",
                    references=("message_0",),
                ),
            ),
        )
    )

    assert observed_sizes == [(1, 1)]



def test_small_delta_defers_the_complete_canonical_batch_view(
    monkeypatch: pytest.MonkeyPatch,
):
    """Apply batches only affected records until a full view is requested."""
    records = tuple(
        _record(f"key_{index}", message_id=f"message_{index}")
        for index in range(128)
    )
    index = IncrementalThreadIndex()
    index.apply(MailboxChangeSet(expected_version=0, additions=records))

    original = incremental_module._batch_thread_messages
    observed_message_counts: list[int] = []

    def recording_batch(messages, **options):
        """Record each canonical batch size before delegating."""
        materialized = tuple(messages)
        observed_message_counts.append(len(materialized))
        return original(materialized, **options)

    monkeypatch.setattr(
        incremental_module,
        "_batch_thread_messages",
        recording_batch,
    )
    index.apply(
        MailboxChangeSet(
            expected_version=1,
            additions=(
                _record(
                    "new_key",
                    message_id="new_message",
                    references=("message_0",),
                ),
            ),
        )
    )

    assert observed_message_counts == [1, 2]
    assert len(index.projections) == 128
    assert observed_message_counts == [1, 2, 129]
    assert len(index.projections) == 128
    assert len(index.roots) == 128
    assert observed_message_counts == [1, 2, 129]
