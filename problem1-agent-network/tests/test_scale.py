"""Test scalability load test benchmark runner."""

import pytest

from scripts.load_test import run_load_benchmark


@pytest.mark.asyncio
async def test_load_test_script_execution() -> None:
    """Verifies concurrent load test benchmark executes and returns valid metrics."""
    metrics = await run_load_benchmark(
        concurrency=4,
        total_posts=10,
        num_agents=5,
    )

    assert metrics["total_posts"] == 10
    assert metrics["throughput_rps"] > 0.0
    assert metrics["p50_latency_ms"] > 0.0
    assert metrics["max_latency_ms"] >= metrics["min_latency_ms"]
