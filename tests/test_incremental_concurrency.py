"""Concurrency contracts for the incremental mailbox index."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path

import threadweave.incremental as incremental_module
from threadweave import (
    IncrementalThreadIndex,
    IndexedMessage,
    MailboxChangeSet,
    Message,
    VersionConflictError,
)


def _record(message_key: str) -> IndexedMessage:
    """Return one independent indexed message for a concurrent update."""
    return IndexedMessage(message_key, Message(message_id=message_key))


def test_concurrent_writers_are_serialized_by_optimistic_version(monkeypatch):
    """Two writers targeting one version yield one commit and one conflict."""
    index = IncrementalThreadIndex()
    real_copy = incremental_module._copied_indexed_message
    first_entered = threading.Event()
    second_entered = threading.Event()
    release_first = threading.Event()
    activity_lock = threading.Lock()
    active_calls = 0
    maximum_active_calls = 0

    def controlled_copy(record: IndexedMessage) -> IndexedMessage:
        """Expose whether two transactions copy records at the same time."""
        nonlocal active_calls, maximum_active_calls
        with activity_lock:
            active_calls += 1
            maximum_active_calls = max(maximum_active_calls, active_calls)
            is_first_call = active_calls == 1
            if is_first_call:
                first_entered.set()
            else:
                second_entered.set()
                release_first.set()
        if is_first_call:
            release_first.wait(timeout=1)
        try:
            return real_copy(record)
        finally:
            with activity_lock:
                active_calls -= 1

    monkeypatch.setattr(
        incremental_module,
        "_copied_indexed_message",
        controlled_copy,
    )

    outcomes: list[tuple[str, object]] = []

    def apply_record(message_key: str) -> None:
        """Apply one expected-version-zero transaction and capture its outcome."""
        try:
            delta = index.apply(
                MailboxChangeSet(
                    expected_version=0,
                    additions=(_record(message_key),),
                )
            )
        except VersionConflictError as error:
            outcomes.append(("conflict", error))
        else:
            outcomes.append(("committed", delta))

    first = threading.Thread(target=apply_record, args=("first",))
    second = threading.Thread(target=apply_record, args=("second",))
    first.start()
    assert first_entered.wait(timeout=1)
    second.start()
    if not second_entered.wait(timeout=0.1):
        release_first.set()
    first.join(timeout=2)
    second.join(timeout=2)

    assert not first.is_alive()
    assert not second.is_alive()
    assert maximum_active_calls == 1
    assert sorted(kind for kind, _ in outcomes) == ["committed", "conflict"]
    assert index.version == 1
    assert len(index.message_keys) == 1


def test_readers_observe_only_committed_versions(monkeypatch):
    """A reader blocks behind a writer and never observes partial transaction state."""
    index = IncrementalThreadIndex()
    real_copy = incremental_module._copied_indexed_message
    writer_entered = threading.Event()
    release_writer = threading.Event()
    reader_started = threading.Event()
    reader_finished = threading.Event()
    observed: list[dict[str, object]] = []

    def controlled_copy(record: IndexedMessage) -> IndexedMessage:
        """Pause one writer after it owns the state lock but before commit."""
        writer_entered.set()
        assert release_writer.wait(timeout=2)
        return real_copy(record)

    monkeypatch.setattr(
        incremental_module,
        "_copied_indexed_message",
        controlled_copy,
    )

    def write() -> None:
        """Apply one transaction while the test controls its commit point."""
        index.apply(
            MailboxChangeSet(
                expected_version=0,
                additions=(_record("message"),),
            )
        )

    def read() -> None:
        """Capture one snapshot after acquiring the same state lock."""
        reader_started.set()
        observed.append(index.snapshot())
        reader_finished.set()

    writer = threading.Thread(target=write)
    reader = threading.Thread(target=read)
    writer.start()
    assert writer_entered.wait(timeout=1)
    reader.start()
    assert reader_started.wait(timeout=1)
    assert not reader_finished.wait(timeout=0.05)

    release_writer.set()
    writer.join(timeout=2)
    reader.join(timeout=2)

    assert not writer.is_alive()
    assert not reader.is_alive()
    assert reader_finished.is_set()
    assert observed[0]["version"] == 1
    records = observed[0]["records"]
    assert isinstance(records, list)
    assert [record["message_key"] for record in records] == ["message"]


def test_package_import_survives_a_top_level_threading_name_collision():
    """The built-in lock remains importable beside ``threadweave/threading.py``."""
    repository_root = Path(__file__).resolve().parents[1]
    import_script = (
        "import sys; "
        "sys.path.insert(0, 'src/threadweave'); "
        "sys.path.insert(1, 'src'); "
        "import subject"
    )

    result = subprocess.run(
        [sys.executable, "-S", "-c", import_script],
        cwd=repository_root,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
