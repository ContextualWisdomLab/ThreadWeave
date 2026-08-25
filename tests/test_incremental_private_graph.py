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




def test_thread_delta_scans_projection_sequences_a_bounded_number_of_times():
    """Large independent forests avoid pairwise projection comparisons."""

    class CountingSequence:
        """Wrap projections and record full-sequence operations."""

        def __init__(self, values: tuple[ThreadProjection, ...]) -> None:
            """Store values with zeroed iteration and membership counters."""
            self.values = values
            self.iterations = 0
            self.membership_checks = 0

        def __iter__(self):
            """Iterate while recording one full-sequence pass."""
            self.iterations += 1
            return iter(self.values)

        def __len__(self) -> int:
            """Return the wrapped projection count."""
            return len(self.values)

        def __getitem__(self, index: int) -> ThreadProjection:
            """Return one wrapped projection by position."""
            return self.values[index]

        def __contains__(self, value: object) -> bool:
            """Record whole-sequence membership checks."""
            self.membership_checks += 1
            return value in self.values

    projection_count = 128
    values = tuple(
        ThreadProjection((f"message_{index}",))
        for index in range(projection_count)
    )
    before = CountingSequence(values)
    after = CountingSequence(values + (ThreadProjection(("new_message",)),))

    delta = incremental._thread_delta(0, 1, ("new_message",), before, after)

    assert delta.added_threads == (ThreadProjection(("new_message",)),)
    assert before.iterations <= 2
    assert after.iterations <= 2
    assert before.membership_checks == 0
    assert after.membership_checks == 0


def test_projection_membership_rejects_duplicate_keys_between_roots():
    """Malformed projections cannot make merge/split classification ambiguous."""
    with pytest.raises(IncrementalThreadError, match="duplicate message_key"):
        incremental._thread_delta(
            0,
            1,
            (),
            (
                ThreadProjection(("shared",)),
                ThreadProjection(("shared",)),
            ),
            (),
        )


def test_reverse_token_buckets_are_copied_only_when_mutated():
    """Atomic changes preserve every shared pre-transaction bucket."""
    original = {"token": {"a", "b"}}
    updates: dict[str, set[str]] = {}

    incremental._remove_key_from_buckets(
        "a",
        ("token",),
        original,
        updates,
    )
    incremental._add_key_to_buckets(
        "c",
        ("token",),
        original,
        updates,
    )

    assert original == {"token": {"a", "b"}}
    assert updates == {"token": {"b", "c"}}
    incremental._commit_bucket_updates(original, updates)
    assert original == {"token": {"b", "c"}}
    incremental._commit_bucket_updates(original, {"token": set()})
    assert original == {}


def test_component_partition_reads_positions_linearly_for_disconnected_keys():
    """Disconnected mailboxes avoid a repeated-minimum quadratic scan."""

    class CountingPositions(dict[str, int]):
        """Count position lookups performed by the partitioner."""

        def __init__(self, values: dict[str, int]) -> None:
            """Create the mapping with a zeroed lookup counter."""
            super().__init__(values)
            self.lookups = 0

        def __getitem__(self, key: str) -> int:
            """Return one position while recording algorithmic work."""
            self.lookups += 1
            return super().__getitem__(key)

    key_count = 128
    keys = {f"message_{index}" for index in range(key_count)}
    positions = CountingPositions(
        {key: index for index, key in enumerate(sorted(keys), start=1)}
    )
    components = incremental._partition_components(
        keys,
        positions,
        {key: frozenset() for key in keys},
        {},
    )

    assert len(components) == key_count
    assert positions.lookups <= key_count * 2


def test_public_forest_copy_rejects_shared_and_cyclic_internal_nodes():
    """Defensive copies fail closed if derived graph invariants are corrupted."""
    index = IncrementalThreadIndex()
    shared = Container(message=Message(message_id="shared"))
    index._roots = (shared, shared)
    with pytest.raises(IncrementalThreadError, match="shared or cyclic"):
        _ = index.roots

    cyclic = Container(message=Message(message_id="cyclic"))
    cyclic.children = [cyclic]
    index._roots = (cyclic,)
    with pytest.raises(IncrementalThreadError, match="shared or cyclic"):
        _ = index.roots

    root = Container(message=Message(message_id="root"))
    root.children = [Container(parent=root)]
    index._roots = (root,)
    copied = index.roots
    assert copied[0].children[0].message is None
    assert copied[0].children[0].parent is copied[0]


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


def test_default_delta_does_not_copy_or_iterate_unrelated_state_maps():
    """A small default-mode update touches bounded state instead of the whole mailbox."""

    class NoFullIterationDict(dict[str, object]):
        """Permit keyed access and mutation while rejecting whole-map scans."""

        def __iter__(self):
            """Reject direct iteration over unrelated state."""
            raise AssertionError("unexpected full-state iteration")

        def keys(self):
            """Reject key-view scans over unrelated state."""
            raise AssertionError("unexpected full-state key scan")

        def items(self):
            """Reject item-view scans over unrelated state."""
            raise AssertionError("unexpected full-state item scan")

        def values(self):
            """Reject value-view scans over unrelated state."""
            raise AssertionError("unexpected full-state value scan")

    records = tuple(
        _record(
            f"message_{index}",
            Message(message_id=f"message_{index}"),
            email_id=f"Email_{index}",
            thread_id=f"Thread_{index}",
        )
        for index in range(128)
    )
    index = IncrementalThreadIndex()
    index.apply(MailboxChangeSet(expected_version=0, additions=records))

    state_names = (
        "_records",
        "_positions",
        "_tokens_by_key",
        "_keys_by_token",
        "_email_id_states",
        "_thread_id_counts",
        "_component_by_key",
        "_keys_by_component",
    )
    for name in state_names:
        setattr(index, name, NoFullIterationDict(getattr(index, name)))
    state_identities = {name: id(getattr(index, name)) for name in state_names}

    delta = index.apply(
        MailboxChangeSet(
            expected_version=1,
            replacements=(
                _record(
                    "message_0",
                    Message(message_id="message_0", subject="updated"),
                    email_id="Email_0",
                    thread_id="Thread_0",
                ),
            ),
        )
    )

    assert delta.affected_message_keys == ("message_0",)
    assert index.version == 2
    assert {name: id(getattr(index, name)) for name in state_names} == state_identities


def test_external_identity_indexes_update_only_touched_namespaces():
    """Identity removals and additions remain atomic without a mailbox-wide scan."""
    index = IncrementalThreadIndex()
    index.apply(
        MailboxChangeSet(
            expected_version=0,
            additions=(
                _record("a", email_id="Mail_A", thread_id="Thread_A"),
                _record("b", email_id="Mail_B", thread_id="Thread_B"),
            ),
        )
    )

    index.apply(
        MailboxChangeSet(
            expected_version=1,
            removals=("a",),
            additions=(
                _record("c", email_id="Thread_A", thread_id="Mail_A"),
            ),
        )
    )

    assert index._email_id_states == {
        "Mail_B": ("Thread_B", 1),
        "Thread_A": ("Mail_A", 1),
    }
    assert index._thread_id_counts == {"Thread_B": 1, "Mail_A": 1}

    before = index.snapshot()
    with pytest.raises(IncrementalThreadError, match="disjoint ObjectID"):
        index.apply(
            MailboxChangeSet(
                expected_version=2,
                additions=(
                    _record("d", email_id="Thread_B", thread_id="Thread_D"),
                ),
            )
        )
    assert index.snapshot() == before


def test_external_identity_index_corruption_fails_before_commit():
    """Broken private identity indexes cannot be published by a transaction."""
    index = IncrementalThreadIndex()
    index.apply(
        MailboxChangeSet(
            expected_version=0,
            additions=(
                _record("a", email_id="Mail_A", thread_id="Thread_A"),
            ),
        )
    )
    index._email_id_states.clear()
    with pytest.raises(IncrementalThreadError, match="EMAILID index"):
        index.apply(MailboxChangeSet(expected_version=1, removals=("a",)))

    index._email_id_states["Mail_A"] = ("Thread_A", 1)
    index._thread_id_counts.clear()
    with pytest.raises(IncrementalThreadError, match="THREADID index"):
        index.apply(MailboxChangeSet(expected_version=1, removals=("a",)))
