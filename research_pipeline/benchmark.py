"""
Benchmark sequential and parallel subagent orchestration.

The same research task is executed twice through run_research(): once
with sequential Agent calls and once with parallel fan-out for the web
researcher and document analyst. Comparing wall-clock time highlights the
latency benefit of letting independent subagents run in the same
coordinator turn.
"""
from __future__ import annotations

import asyncio

from research_pipeline.coordinator import run_research


async def run_benchmark(topic_id: str = "ai_regulation_eu") -> None:
    print(f"\n=== BENCHMARK: sequential vs. parallel spawning (topic={topic_id}) ===\n")

    print("--- Sequential run (one Agent call per turn, Task 1's anti-pattern) ---")
    sequential_run = await run_research(topic_id, parallel=False)

    print("\n--- Parallel run (two Agent calls in one turn, Task 1's target behaviour) ---")
    parallel_run = await run_research(topic_id, parallel=True)

    print("\n=== RESULTS ===")
    print(f"{'Mode':<12}{'Wall-clock (s)':>18}")
    print(f"{'Sequential':<12}{sequential_run.wall_clock_seconds:>18.2f}")
    print(f"{'Parallel':<12}{parallel_run.wall_clock_seconds:>18.2f}")

    if parallel_run.wall_clock_seconds > 0:
        speedup = sequential_run.wall_clock_seconds / parallel_run.wall_clock_seconds
        print(f"\nSpeedup: {speedup:.2f}x")

    print(
        "\nNote: speedup here reflects real API round-trip latency, so it "
        "will vary run to run - the point is that parallel is reliably "
        "faster, not that it hits an exact ratio."
    )


if __name__ == "__main__":
    asyncio.run(run_benchmark())
