"""Defensive validation coverage for incremental mailbox boundaries."""

from __future__ import annotations

from copy import deepcopy

import pytest

from threadweave import (
    IncrementalThreadError,
    IncrementalThreadIndex,
    IndexedMessage,
    MailboxChangeSet,
    Message,
)


def _record(key: str, message: Message | None = None, **identity: str) -> IndexedMessage:
    """Build one record for focused validation tests."""
    return IndexedMessage(
        key,
        Message(message_id=key) if message is None else message,
        **identity,
    )


def test_public_containers_reject_wrong_element_and_message_types():
    """Runtime boundaries reject values hidden behind static annotations."""
    with pytest.raises(IncrementalThreadError, match="IndexedMessage"):
        MailboxChangeSet(
            expected_version=0,
            additions=(object(),),  # type: ignore[arg-type]
        )
    with pytest.raises(IncrementalThreadError, match="threadweave.Message"):
        IndexedMessage("a", object())  # type: ignore[arg-type]


def test_apply_rejects_invalid_message_metadata_before_mutation():
    """Malformed text, references, dates, and IMAP numbers fail atomically."""
    bad_messages = (
        Message(message_id=object()),  # type: ignore[arg-type]
        Message(subject=object()),  # type: ignore[arg-type]
        Message(references=1),  # type: ignore[arg-type]
        Message(references=("ok", 1)),  # type: ignore[arg-type]
        Message(sent_date=object()),  # type: ignore[arg-type]
        Message(uid=4_294_967_296),
    )
    for position, message in enumerate(bad_messages):
        index = IncrementalThreadIndex()
        with pytest.raises(IncrementalThreadError):
            index.apply(
                MailboxChangeSet(
                    expected_version=0,
                    additions=(_record(f"bad_{position}", message),),
                )
            )
        assert index.version == 0


def test_constructor_and_apply_reject_wrong_runtime_boundary_types():
    """Boolean options and arbitrary change objects never enter mutable state."""
    with pytest.raises(IncrementalThreadError, match="group_by_subject"):
        IncrementalThreadIndex(group_by_subject=1)  # type: ignore[arg-type]
    with pytest.raises(IncrementalThreadError, match="sort_by_sent_date"):
        IncrementalThreadIndex(sort_by_sent_date=1)  # type: ignore[arg-type]
    with pytest.raises(IncrementalThreadError, match="MailboxChangeSet"):
        IncrementalThreadIndex().apply(object())  # type: ignore[arg-type]


def test_snapshot_record_limit_is_enforced_at_publication_time():
    """A lowered publication bound cannot emit an oversized state document."""
    index = IncrementalThreadIndex(max_snapshot_records=1)
    index.apply(
        MailboxChangeSet(
            expected_version=0,
            additions=(_record("a"), _record("b")),
        )
    )
    with pytest.raises(IncrementalThreadError, match="max_snapshot_records"):
        index.snapshot()


def test_restore_rejects_remaining_shape_and_scalar_ambiguities():
    """Nested snapshot fields use exact mapping, list, and scalar types."""
    source = IncrementalThreadIndex()
    source.apply(MailboxChangeSet(expected_version=0, additions=(_record("a"),)))
    snapshot = source.snapshot()

    invalid_values: list[tuple[dict[str, object], str]] = []
    options_not_mapping = deepcopy(snapshot)
    options_not_mapping["options"] = []
    invalid_values.append((options_not_mapping, "options"))

    invalid_group_option = deepcopy(snapshot)
    invalid_group_option["options"]["group_by_subject"] = 1  # type: ignore[index]
    invalid_values.append((invalid_group_option, "group_by_subject"))

    invalid_sort_option = deepcopy(snapshot)
    invalid_sort_option["options"]["sort_by_sent_date"] = 1  # type: ignore[index]
    invalid_values.append((invalid_sort_option, "sort_by_sent_date"))

    record_not_mapping = deepcopy(snapshot)
    record_not_mapping["records"] = [1]
    invalid_values.append((record_not_mapping, "record"))

    invalid_reply = deepcopy(snapshot)
    invalid_reply["records"][0]["message"]["in_reply_to"] = [1]  # type: ignore[index]
    invalid_values.append((invalid_reply, "in_reply_to"))

    invalid_references = deepcopy(snapshot)
    invalid_references["records"][0]["message"]["references"] = [1]  # type: ignore[index]
    invalid_values.append((invalid_references, "references"))

    malformed_date = deepcopy(snapshot)
    malformed_date["records"][0]["message"]["sent_date"] = []  # type: ignore[index]
    invalid_values.append((malformed_date, "date"))

    nontext_date = deepcopy(snapshot)
    nontext_date["records"][0]["message"]["sent_date"] = {  # type: ignore[index]
        "kind": "text",
        "value": 1,
    }
    invalid_values.append((nontext_date, "textual"))

    for invalid, pattern in invalid_values:
        with pytest.raises(IncrementalThreadError, match=pattern):
            IncrementalThreadIndex.restore(invalid)


def test_empty_snapshot_restore_skips_initial_rebuild():
    """A versioned empty mailbox restores without a fabricated change."""
    restored = IncrementalThreadIndex.restore(
        {
            "schema_version": 1,
            "version": 7,
            "options": {
                "group_by_subject": False,
                "sort_by_sent_date": False,
            },
            "records": [],
        }
    )
    assert restored.version == 7
    assert restored.message_keys == ()
