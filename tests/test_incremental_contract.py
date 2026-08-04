"""Public and atomicity contracts for incremental mailbox threading."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from threadweave import (
    ExternalIdentityError,
    IncrementalThreadError,
    IncrementalThreadIndex,
    IndexedMessage,
    MailboxChangeSet,
    Message,
    VersionConflictError,
)


def _record(
    key: str,
    *,
    message_id: str | None = None,
    references: tuple[str, ...] = (),
    subject: str | None = None,
    payload: object | None = None,
    sequence_number: int | None = None,
    uid: int | None = None,
    email_id: str | None = None,
    thread_id: str | None = None,
) -> IndexedMessage:
    """Build one indexed message with explicit caller identity."""
    return IndexedMessage(
        message_key=key,
        message=Message(
            message_id=message_id or key,
            references=references,
            subject=subject,
            payload=key if payload is None else payload,
            sequence_number=sequence_number,
            uid=uid,
        ),
        email_id=email_id,
        thread_id=thread_id,
    )


def test_empty_index_exposes_immutable_empty_state():
    """A new index starts at version zero with no roots or projections."""
    index = IncrementalThreadIndex()

    assert index.version == 0
    assert index.message_keys == ()
    assert index.roots == ()
    assert index.projections == ()
    assert len(index) == 0


def test_public_records_are_frozen_and_sequences_are_normalized():
    """Change records cannot be mutated after validation or retain caller lists."""
    additions = [_record("a")]
    changes = MailboxChangeSet(expected_version=0, additions=additions)

    assert changes.additions == tuple(additions)
    assert changes.replacements == ()
    assert changes.removals == ()
    with pytest.raises(FrozenInstanceError):
        changes.expected_version = 1  # type: ignore[misc]


def test_indexed_message_rejects_unsafe_keys_and_external_identifiers():
    """Caller identity values remain bounded, printable, and non-empty."""
    for key in ("", "bad\nkey", "x" * 513):
        with pytest.raises(IncrementalThreadError, match="message_key"):
            _record(key)

    with pytest.raises(IncrementalThreadError, match="email_id"):
        _record("a", email_id="bad\x00id")
    with pytest.raises(IncrementalThreadError, match="thread_id"):
        _record("a", thread_id="")


def test_change_set_rejects_invalid_versions_duplicate_and_overlapping_keys():
    """An atomic request has one non-negative version and disjoint unique keys."""
    with pytest.raises(IncrementalThreadError, match="expected_version"):
        MailboxChangeSet(expected_version=True)
    with pytest.raises(IncrementalThreadError, match="expected_version"):
        MailboxChangeSet(expected_version=-1)
    with pytest.raises(IncrementalThreadError, match="duplicate.*additions"):
        MailboxChangeSet(expected_version=0, additions=(_record("a"), _record("a")))
    with pytest.raises(IncrementalThreadError, match="disjoint"):
        MailboxChangeSet(
            expected_version=0,
            additions=(_record("a"),),
            removals=("a",),
        )
    with pytest.raises(IncrementalThreadError, match="removals"):
        MailboxChangeSet(expected_version=0, removals=("a", "a"))


def test_add_replace_remove_are_atomic_and_optimistically_versioned():
    """Successful changes advance once while rejected requests preserve state."""
    original_payload = object()
    original = _record("a", subject="Original", payload=original_payload)
    index = IncrementalThreadIndex()

    added = index.apply(MailboxChangeSet(expected_version=0, additions=(original,)))
    assert (added.previous_version, added.version) == (0, 1)
    assert added.affected_message_keys == ("a",)
    assert index.message_keys == ("a",)
    assert index.roots[0].message.payload is original_payload

    replacement = _record("a", subject="Replacement", payload=original_payload)
    replaced = index.apply(
        MailboxChangeSet(expected_version=1, replacements=(replacement,))
    )
    assert (replaced.previous_version, replaced.version) == (1, 2)
    assert index.roots[0].message.subject == "Replacement"

    before = index.snapshot()
    with pytest.raises(VersionConflictError, match="expected version 1.*current version 2"):
        index.apply(MailboxChangeSet(expected_version=1, removals=("a",)))
    assert index.snapshot() == before

    removed = index.apply(MailboxChangeSet(expected_version=2, removals=("a",)))
    assert (removed.previous_version, removed.version) == (2, 3)
    assert index.message_keys == ()
    assert index.roots == ()


def test_invalid_ownership_requests_leave_the_index_unchanged():
    """Add/replace/remove ownership errors fail before committing copied state."""
    index = IncrementalThreadIndex()
    index.apply(MailboxChangeSet(expected_version=0, additions=(_record("a"),)))
    before = index.snapshot()

    invalid_changes = (
        MailboxChangeSet(expected_version=1, additions=(_record("a"),)),
        MailboxChangeSet(expected_version=1, replacements=(_record("missing"),)),
        MailboxChangeSet(expected_version=1, removals=("missing",)),
    )
    for changes in invalid_changes:
        with pytest.raises(IncrementalThreadError):
            index.apply(changes)
        assert index.snapshot() == before


def test_structural_metadata_is_copied_while_payload_remains_caller_owned():
    """Later caller mutation cannot rewrite indexed references or subject data."""
    references = ["root"]
    message = Message(
        message_id="child",
        references=references,
        subject="Original",
        payload={"caller": "owned"},
    )
    index = IncrementalThreadIndex()
    index.apply(
        MailboxChangeSet(
            expected_version=0,
            additions=(IndexedMessage("child_key", message),),
        )
    )

    references.append("other")
    message.subject = "Mutated"

    indexed = index.roots[0].message
    assert indexed.references == ("root",)
    assert indexed.subject == "Original"
    assert indexed.payload is message.payload


def test_reported_external_identity_is_immutable_on_replacement():
    """RFC 8474 identity metadata cannot disappear or change after exposure."""
    index = IncrementalThreadIndex()
    index.apply(
        MailboxChangeSet(
            expected_version=0,
            additions=(
                _record("a", email_id="M1", thread_id="T1"),
            ),
        )
    )
    before = index.snapshot()

    for replacement in (
        _record("a", email_id=None, thread_id="T1"),
        _record("a", email_id="M2", thread_id="T1"),
        _record("a", email_id="M1", thread_id=None),
        _record("a", email_id="M1", thread_id="T2"),
    ):
        with pytest.raises(ExternalIdentityError, match="immutable"):
            index.apply(
                MailboxChangeSet(expected_version=1, replacements=(replacement,))
            )
        assert index.snapshot() == before


def test_same_email_id_requires_one_consistent_thread_id():
    """Messages sharing immutable content identity cannot disagree on THREADID."""
    index = IncrementalThreadIndex()

    with pytest.raises(ExternalIdentityError, match="EMAILID.*THREADID"):
        index.apply(
            MailboxChangeSet(
                expected_version=0,
                additions=(
                    _record("a", email_id="M1", thread_id="T1"),
                    _record("b", email_id="M1", thread_id="T2"),
                ),
            )
        )
    assert index.version == 0

    with pytest.raises(ExternalIdentityError, match="EMAILID.*THREADID"):
        index.apply(
            MailboxChangeSet(
                expected_version=0,
                additions=(
                    _record("a", email_id="M1", thread_id="T1"),
                    _record("b", email_id="M1", thread_id=None),
                ),
            )
        )


def test_constructor_rejects_boolean_and_nonpositive_snapshot_limits():
    """Snapshot denial-of-service limits are explicit positive integers."""
    for keyword in ("max_snapshot_records", "max_snapshot_bytes"):
        with pytest.raises(IncrementalThreadError, match=keyword):
            IncrementalThreadIndex(**{keyword: True})
        with pytest.raises(IncrementalThreadError, match=keyword):
            IncrementalThreadIndex(**{keyword: 0})
