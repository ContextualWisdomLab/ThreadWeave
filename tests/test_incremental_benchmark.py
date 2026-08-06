"""Contract tests for the mailbox-scale incremental benchmark."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
BENCHMARK_PATH = ROOT / "benchmarks" / "incremental_mailbox.py"
SPEC = importlib.util.spec_from_file_location(
    "threadweave_incremental_benchmark",
    BENCHMARK_PATH,
)
assert SPEC is not None and SPEC.loader is not None
benchmark = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = benchmark
SPEC.loader.exec_module(benchmark)


def test_small_benchmark_proves_projection_parity_and_reports_resources():
    """The CI-sized run emits matching digests and complete evidence fields."""
    result = benchmark.run_benchmark(1_000, 10)

    assert result["schema_version"] == 1
    assert result["message_count"] == 1_001
    assert result["incremental"]["projection_sha256"] == (
        result["full_rebuild"]["projection_sha256"]
    )
    assert result["incremental"]["affected_message_count"] == 21
    assert result["incremental"]["delta_apply_seconds"] >= 0
    assert result["incremental"]["delta_retained_bytes"] >= 0
    assert result["incremental"]["delta_transient_peak_bytes"] >= 0
    assert result["incremental"]["peak_rss_bytes"] > 0
    assert result["full_rebuild"]["full_rebuild_seconds"] >= 0
    assert result["full_rebuild"]["peak_rss_bytes"] > 0


def test_benchmark_validates_size_contracts():
    """Invalid or undersized workloads fail before spawning workers."""
    with pytest.raises(ValueError, match="message_count"):
        benchmark.run_benchmark(0, 10)
    with pytest.raises(ValueError, match="thread_size"):
        benchmark.run_benchmark(100, 0)
    with pytest.raises(ValueError, match="two complete threads"):
        benchmark.run_benchmark(10, 10)


def test_main_writes_deterministic_json_shape(tmp_path: Path):
    """The command-line entry point writes one parseable evidence document."""
    output = tmp_path / "benchmark.json"
    assert benchmark.main(
        [
            "--messages",
            "1000",
            "--thread-size",
            "10",
            "--output",
            str(output),
        ]
    ) == 0
    parsed = json.loads(output.read_text(encoding="utf-8"))
    assert parsed["schema_version"] == 1
    assert parsed["message_count"] == 1_001
