"""Deterministic mailbox-scale benchmark for the incremental threading layer.

The parent process runs incremental and full-rebuild workers separately so each
scenario reports its own peak resident-set size. Both workers hash the same
caller-key projection to prove structural parity without serializing a 100,000-
message forest between processes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import subprocess
import sys
from collections.abc import Iterable
from time import perf_counter

from threadweave import (
    Container,
    IncrementalThreadIndex,
    IndexedMessage,
    MailboxChangeSet,
    Message,
    thread_messages,
)


def _records(message_count: int, thread_size: int) -> tuple[IndexedMessage, ...]:
    """Create deterministic thread chains with caller keys retained as payloads."""
    records: list[IndexedMessage] = []
    for index in range(message_count):
        position = index % thread_size
        references = () if position == 0 else (f"message_{index - 1}",)
        records.append(
            IndexedMessage(
                f"key_{index}",
                Message(
                    message_id=f"message_{index}",
                    references=references,
                    payload=f"key_{index}",
                ),
            )
        )
    return tuple(records)


def _bridge_record(thread_size: int) -> IndexedMessage:
    """Return one message that joins the first two deterministic components."""
    return IndexedMessage(
        "bridge_key",
        Message(
            message_id="bridge_message",
            references=(
                f"message_{thread_size - 1}",
                f"message_{(thread_size * 2) - 1}",
            ),
            payload="bridge_key",
        ),
    )


def _projection_digest(projections: Iterable[tuple[str, ...]]) -> str:
    """Hash ordered root projections with unambiguous length framing."""
    digest = hashlib.sha256()
    for projection in projections:
        digest.update(len(projection).to_bytes(8, "big"))
        for message_key in projection:
            encoded = message_key.encode("utf-8")
            digest.update(len(encoded).to_bytes(8, "big"))
            digest.update(encoded)
    return digest.hexdigest()


def _forest_projection(roots: Iterable[Container]) -> tuple[tuple[str, ...], ...]:
    """Project a batch forest into iterative traversal-ordered payload keys."""
    result: list[tuple[str, ...]] = []
    for root in roots:
        keys: list[str] = []
        seen: set[int] = set()
        stack = [root]
        while stack:
            node = stack.pop()
            if id(node) in seen:
                continue
            seen.add(id(node))
            if node.message is not None:
                if not isinstance(node.message.payload, str):
                    raise RuntimeError("benchmark payload must be a caller key string")
                keys.append(node.message.payload)
            stack.extend(reversed(node.children))
        result.append(tuple(keys))
    return tuple(result)


def _peak_rss_bytes() -> int:
    """Return the process peak RSS in bytes on the Linux benchmark runner."""
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024


def _incremental_worker(message_count: int, thread_size: int) -> dict[str, object]:
    """Build an index, apply one bridge delta, and materialize its final view."""
    records = _records(message_count, thread_size)
    index = IncrementalThreadIndex()
    started = perf_counter()
    index.apply(MailboxChangeSet(expected_version=0, additions=records))
    initial_seconds = perf_counter() - started

    bridge = _bridge_record(thread_size)
    started = perf_counter()
    delta = index.apply(
        MailboxChangeSet(expected_version=1, additions=(bridge,))
    )
    delta_seconds = perf_counter() - started

    started = perf_counter()
    projections = tuple(
        projection.message_keys for projection in index.projections
    )
    materialize_seconds = perf_counter() - started
    return {
        "scenario": "incremental",
        "message_count": message_count + 1,
        "root_count": len(projections),
        "affected_message_count": len(delta.affected_message_keys),
        "initial_build_seconds": initial_seconds,
        "delta_apply_seconds": delta_seconds,
        "materialize_seconds": materialize_seconds,
        "peak_rss_bytes": _peak_rss_bytes(),
        "projection_sha256": _projection_digest(projections),
    }


def _full_worker(message_count: int, thread_size: int) -> dict[str, object]:
    """Build the same final mailbox through the canonical batch oracle."""
    records = _records(message_count, thread_size)
    messages = [record.message for record in records]
    messages.append(_bridge_record(thread_size).message)
    started = perf_counter()
    roots = thread_messages(messages)
    rebuild_seconds = perf_counter() - started
    projections = _forest_projection(roots)
    return {
        "scenario": "full_rebuild",
        "message_count": message_count + 1,
        "root_count": len(projections),
        "full_rebuild_seconds": rebuild_seconds,
        "peak_rss_bytes": _peak_rss_bytes(),
        "projection_sha256": _projection_digest(projections),
    }


def _run_worker(scenario: str, message_count: int, thread_size: int) -> dict[str, object]:
    """Execute one isolated worker and decode its single JSON result."""
    completed = subprocess.run(
        [
            sys.executable,
            __file__,
            "--worker",
            scenario,
            "--messages",
            str(message_count),
            "--thread-size",
            str(thread_size),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def _validated_positive(value: int, name: str) -> int:
    """Require one positive non-boolean benchmark integer."""
    if isinstance(value, bool) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def run_benchmark(message_count: int, thread_size: int) -> dict[str, object]:
    """Run isolated scenarios, require parity, and return one evidence record."""
    message_count = _validated_positive(message_count, "message_count")
    thread_size = _validated_positive(thread_size, "thread_size")
    if message_count < thread_size * 2:
        raise ValueError("message_count must contain at least two complete threads")
    incremental = _run_worker("incremental", message_count, thread_size)
    full_rebuild = _run_worker("full_rebuild", message_count, thread_size)
    if incremental["projection_sha256"] != full_rebuild["projection_sha256"]:
        raise RuntimeError("incremental and full-rebuild projections disagree")
    return {
        "schema_version": 1,
        "message_count": message_count + 1,
        "thread_size": thread_size,
        "incremental": incremental,
        "full_rebuild": full_rebuild,
    }


def _parser() -> argparse.ArgumentParser:
    """Build the command-line parser for parent and worker modes."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--messages", type=int, default=100_000)
    parser.add_argument("--thread-size", type=int, default=10)
    parser.add_argument(
        "--worker",
        choices=("incremental", "full_rebuild"),
    )
    parser.add_argument("--output")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run a worker or publish the combined deterministic benchmark JSON."""
    arguments = _parser().parse_args(argv)
    if arguments.worker == "incremental":
        result = _incremental_worker(arguments.messages, arguments.thread_size)
    elif arguments.worker == "full_rebuild":
        result = _full_worker(arguments.messages, arguments.thread_size)
    else:
        result = run_benchmark(arguments.messages, arguments.thread_size)
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        with open(arguments.output, "w", encoding="utf-8") as output_file:
            output_file.write(encoded)
    else:
        sys.stdout.write(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
