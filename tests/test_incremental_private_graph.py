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
    overlay = dict(original)
    tokens_by_key = {"a": frozenset({"token"})}
    copied_tokens: set[str] = set()

    incremental._remove_key_from_buckets(
        "a",
        tokens_by_key,
        overlay,
        copied_tokens,
    )
    incremental._add_key_to_buckets(
        "c",
        frozenset({"token"}),
        tokens_by_key,
        overlay,
        copied_tokens,
    )

    assert original == {"token": {"a", "b"}}
    assert overlay == {"token": {"b", "c"}}
    assert copied_tokens == {"token"}


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
