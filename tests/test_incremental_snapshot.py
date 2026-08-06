"""Versioned JSON-safe snapshot tests for the incremental index."""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from datetime import datetime, timezone

import pytest
import threadweave.incremental as incremental_module

from threadweave import (
    IncrementalThreadError,
    IncrementalThreadIndex,
    IndexedMessage,
    MailboxChangeSet,
    Message,
)


def _index() -> IncrementalThreadIndex:
    """Return a representative index containing every serializable field."""
    index = IncrementalThreadIndex(
        group_by_subject=True,
        sort_by_sent_date=True,
        max_snapshot_records=100,
        max_snapshot_bytes=100_000,
    )
    index.apply(
        MailboxChangeSet(
            expected_version=0,
            additions=(
                IndexedMessage(
                    message_key="root_key",
                    message=Message(
                        message_id="<root@example.test>",
                        subject="Topic",
                        payload={"must": "not persist"},
                        sent_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
                        internal_date="1 Jan 2026 00:00:00 +0000",
                        sequence_number=1,
                        uid=101,
                    ),
                    email_id="M1",
                    thread_id="T1",
                ),
                IndexedMessage(
                    message_key="child_key",
                    message=Message(
                        message_id="<child@example.test>",
                        references="<root@example.test>",
                        in_reply_to="<root@example.test>",
                        subject="Re: Topic",
                        payload=object(),
                        sent_date=datetime(2026, 1, 2),
                        sequence_number=2,
                        uid=102,
                    ),
                    email_id="M2",
                    thread_id="T1",
                ),
            ),
        )
    )
    return index


def test_snapshot_is_deterministic_json_safe_and_omits_payloads():
    """State serializes reproducibly without arbitrary caller objects."""
    index = _index()

    first = index.snapshot()
    second = index.snapshot()

    assert first == second
    encoded = json.dumps(first, sort_keys=True, separators=(",", ":"))
    assert "must not persist" not in encoded
    assert "payload" not in encoded
    assert first["schema_version"] == 1
    assert first["version"] == 1
    assert first["options"] == {
        "group_by_subject": True,
        "sort_by_sent_date": True,
    }
    assert [record["message_key"] for record in first["records"]] == [
        "root_key",
        "child_key",
    ]


def test_snapshot_restore_round_trip_preserves_structure_and_version():
    """Restored derived state matches the source while payloads become None."""
    source = _index()
    snapshot = source.snapshot()

    restored = IncrementalThreadIndex.restore(
        snapshot,
        max_snapshot_records=100,
        max_snapshot_bytes=100_000,
    )

    assert restored.version == source.version
    assert restored.message_keys == source.message_keys
    assert restored.projections == source.projections
    assert restored.snapshot() == snapshot
    assert all(
        node.message.payload is None
        for root in restored.roots
        for node in (root, *tuple(root.iter_descendants()))
        if node.message is not None
    )


def test_restored_index_continues_with_optimistic_versioning():
    """A restored revision accepts the next atomic change exactly once."""
    restored = IncrementalThreadIndex.restore(_index().snapshot())
    delta = restored.apply(
        MailboxChangeSet(
            expected_version=1,
            additions=(
                IndexedMessage(
                    "new_key",
                    Message(message_id="new", payload="not persisted"),
                ),
            ),
        )
    )

    assert (delta.previous_version, delta.version) == (1, 2)
    assert restored.version == 2


def test_restore_rejects_unknown_root_fields_and_schema_versions():
    """Untrusted snapshots use an exact schema rather than permissive decoding."""
    snapshot = _index().snapshot()

    unknown = deepcopy(snapshot)
    unknown["unexpected"] = True
    with pytest.raises(IncrementalThreadError, match="snapshot fields"):
        IncrementalThreadIndex.restore(unknown)

    unsupported = deepcopy(snapshot)
    unsupported["schema_version"] = 2
    with pytest.raises(IncrementalThreadError, match="schema_version"):
        IncrementalThreadIndex.restore(unsupported)

    missing = deepcopy(snapshot)
    del missing["records"]
    with pytest.raises(IncrementalThreadError, match="snapshot fields"):
        IncrementalThreadIndex.restore(missing)


@pytest.mark.parametrize("invalid_schema_version", [True, 1.0])
def test_restore_requires_an_exact_integer_schema_version(
    invalid_schema_version: object,
):
    """Boolean and floating-point lookalikes cannot select a snapshot schema."""
    snapshot = _index().snapshot()
    snapshot["schema_version"] = invalid_schema_version

    with pytest.raises(IncrementalThreadError, match="schema_version"):
        IncrementalThreadIndex.restore(snapshot)


def test_snapshot_reports_unencodable_unicode_as_a_domain_error():
    """Lone surrogates fail closed instead of leaking a codec exception."""
    index = IncrementalThreadIndex()
    index.apply(
        MailboxChangeSet(
            expected_version=0,
            additions=(
                IndexedMessage(
                    "surrogate_key",
                    Message(message_id="surrogate", subject="bad\ud800subject"),
                ),
            ),
        )
    )

    with pytest.raises(IncrementalThreadError, match="JSON-safe"):
        index.snapshot()


def test_restore_reports_excessive_json_nesting_as_a_domain_error():
    """Hostile nesting cannot escape the snapshot boundary as RecursionError."""
    nested: object = []
    for _ in range(sys.getrecursionlimit() * 20):
        nested = [nested]
    snapshot = {
        "schema_version": 1,
        "version": 0,
        "options": {
            "group_by_subject": False,
            "sort_by_sent_date": False,
        },
        "records": [],
        "unexpected": nested,
    }

    with pytest.raises(IncrementalThreadError, match="JSON-safe"):
        IncrementalThreadIndex.restore(snapshot)


def test_restore_rejects_malformed_record_fields_and_duplicate_keys():
    """Record decoding rejects ambiguity before constructing any graph state."""
    snapshot = _index().snapshot()

    duplicate = deepcopy(snapshot)
    duplicate["records"].append(deepcopy(duplicate["records"][0]))
    with pytest.raises(IncrementalThreadError, match="duplicate.*message_key"):
        IncrementalThreadIndex.restore(duplicate)

    extra = deepcopy(snapshot)
    extra["records"][0]["unexpected"] = "value"
    with pytest.raises(IncrementalThreadError, match="record fields"):
        IncrementalThreadIndex.restore(extra)

    invalid_records = deepcopy(snapshot)
    invalid_records["records"] = "not-a-list"
    with pytest.raises(IncrementalThreadError, match="records"):
        IncrementalThreadIndex.restore(invalid_records)

    invalid_message = deepcopy(snapshot)
    invalid_message["records"][0]["message"] = []
    with pytest.raises(IncrementalThreadError, match="message"):
        IncrementalThreadIndex.restore(invalid_message)


def test_restore_rejects_invalid_date_tags_and_numeric_metadata():
    """Date and IMAP metadata preserve strict tagged and integer contracts."""
    snapshot = _index().snapshot()

    invalid_date = deepcopy(snapshot)
    invalid_date["records"][0]["message"]["sent_date"] = {
        "kind": "unknown",
        "value": "2026-01-01",
    }
    with pytest.raises(IncrementalThreadError, match="date"):
        IncrementalThreadIndex.restore(invalid_date)

    invalid_datetime = deepcopy(snapshot)
    invalid_datetime["records"][0]["message"]["sent_date"] = {
        "kind": "datetime",
        "value": "not-a-date",
    }
    with pytest.raises(IncrementalThreadError, match="datetime"):
        IncrementalThreadIndex.restore(invalid_datetime)

    invalid_sequence = deepcopy(snapshot)
    invalid_sequence["records"][0]["message"]["sequence_number"] = True
    with pytest.raises(IncrementalThreadError, match="sequence_number"):
        IncrementalThreadIndex.restore(invalid_sequence)


def test_restore_and_snapshot_enforce_record_and_byte_limits():
    """Configured bounds stop oversized state before allocation or publication."""
    snapshot = _index().snapshot()

    with pytest.raises(IncrementalThreadError, match="max_snapshot_records"):
        IncrementalThreadIndex.restore(snapshot, max_snapshot_records=1)
    with pytest.raises(IncrementalThreadError, match="max_snapshot_bytes"):
        IncrementalThreadIndex.restore(snapshot, max_snapshot_bytes=10)

    index = IncrementalThreadIndex(max_snapshot_bytes=10)
    index.apply(
        MailboxChangeSet(
            expected_version=0,
            additions=(IndexedMessage("a", Message(message_id="a")),),
        )
    )
    with pytest.raises(IncrementalThreadError, match="max_snapshot_bytes"):
        index.snapshot()


def test_restore_rejects_non_mapping_and_non_json_safe_values():
    """The public boundary converts encoder failures into domain errors."""
    with pytest.raises(IncrementalThreadError, match="mapping"):
        IncrementalThreadIndex.restore([])  # type: ignore[arg-type]

    snapshot = _index().snapshot()
    invalid = deepcopy(snapshot)
    invalid["records"][0]["email_id"] = object()
    with pytest.raises(IncrementalThreadError, match="JSON"):
        IncrementalThreadIndex.restore(invalid)


class _HostileDictionary(dict):
    """Dictionary subclass whose iteration must never cross the snapshot boundary."""

    def items(self):
        """Raise if generic JSON encoding invokes subclass behavior."""
        raise RuntimeError("hostile dictionary iteration")


class _HostileList(list):
    """List subclass whose iteration must never cross the snapshot boundary."""

    def __iter__(self):
        """Raise if generic JSON encoding invokes subclass behavior."""
        raise RuntimeError("hostile list iteration")


class _HostileString(str):
    """String subclass whose comparisons must not run during sorted encoding."""

    def __lt__(self, _other: object) -> bool:
        """Reject less-than comparison if sorted encoding reaches this key."""
        raise TypeError("hostile string comparison")

    def __le__(self, _other: object) -> bool:
        """Reject less-than-or-equal comparison if encoding reaches this key."""
        raise TypeError("hostile string comparison")

    def __gt__(self, _other: object) -> bool:
        """Reject greater-than comparison if sorted encoding reaches this key."""
        raise TypeError("hostile string comparison")

    def __ge__(self, _other: object) -> bool:
        """Reject greater-than-or-equal comparison if encoding reaches this key."""
        raise TypeError("hostile string comparison")


def test_restore_rejects_container_subclasses_before_they_execute():
    """Only plain JSON containers may enter the untrusted snapshot decoder."""
    root = _HostileDictionary(
        {
            "schema_version": 1,
            "version": 0,
            "options": {
                "group_by_subject": False,
                "sort_by_sent_date": False,
            },
            "records": [],
        }
    )
    with pytest.raises(IncrementalThreadError, match="plain JSON containers"):
        IncrementalThreadIndex.restore(root)

    nested = {
        "schema_version": 1,
        "version": 0,
        "options": {
            "group_by_subject": False,
            "sort_by_sent_date": False,
        },
        "records": _HostileList(),
    }
    with pytest.raises(IncrementalThreadError, match="plain JSON containers"):
        IncrementalThreadIndex.restore(nested)


def test_plain_json_guard_rejects_executable_key_and_scalar_subclasses():
    """Sorted JSON encoding cannot invoke attacker-controlled scalar methods."""
    hostile_key = _HostileString("unexpected")
    with pytest.raises(IncrementalThreadError, match="plain strings"):
        incremental_module._require_plain_json_containers(
            {hostile_key: "value", "schema_version": 1}
        )

    with pytest.raises(IncrementalThreadError, match="scalar values"):
        incremental_module._require_plain_json_containers(
            {"value": _HostileString("hostile")}
        )


def test_plain_container_guard_rejects_cycles_and_reused_containers():
    """JSON snapshots are trees: cycles and shared container identities fail closed."""
    mapping_cycle: dict[str, object] = {}
    mapping_cycle["self"] = mapping_cycle
    with pytest.raises(IncrementalThreadError, match="cyclic"):
        IncrementalThreadIndex.restore(mapping_cycle)

    list_cycle: list[object] = []
    list_cycle.append(list_cycle)
    nested_cycle = {
        "schema_version": 1,
        "version": 0,
        "options": {
            "group_by_subject": False,
            "sort_by_sent_date": False,
        },
        "records": list_cycle,
    }
    with pytest.raises(IncrementalThreadError, match="cyclic"):
        IncrementalThreadIndex.restore(nested_cycle)

    shared: list[object] = [{"value": 1}]
    with pytest.raises(IncrementalThreadError, match="reused"):
        incremental_module._require_plain_json_containers(
            {"first": shared, "second": shared}
        )

    compact_graph: object = []
    for _ in range(28):
        compact_graph = [compact_graph, compact_graph]
    hostile_snapshot = {
        "schema_version": 1,
        "version": 0,
        "options": {
            "group_by_subject": False,
            "sort_by_sent_date": False,
        },
        "records": compact_graph,
    }
    with pytest.raises(IncrementalThreadError, match="reused"):
        IncrementalThreadIndex.restore(hostile_snapshot)


def test_snapshot_size_validation_stops_at_the_utf8_limit(monkeypatch):
    """Byte-limit enforcement stops the incremental encoder before later chunks."""
    later_chunks_requested: list[bool] = []

    class _ChunkedEncoder:
        """Yield one oversized UTF-8 chunk, then fail if iteration continues."""

        def __init__(self, **_options: object) -> None:
            """Accept the production encoder options used by the helper."""

        def iterencode(self, _value: object):
            """Yield one four-byte chunk and record any forbidden second request."""
            yield '"é"'
            later_chunks_requested.append(True)
            raise AssertionError("encoder continued after the configured byte limit")

    monkeypatch.setattr(incremental_module.json, "JSONEncoder", _ChunkedEncoder)

    with pytest.raises(IncrementalThreadError, match="max_snapshot_bytes"):
        incremental_module._bounded_snapshot_json_size({}, 3)
    assert later_chunks_requested == []
