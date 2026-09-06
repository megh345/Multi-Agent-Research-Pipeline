"""
benchmark.py - sequential vs. parallel wall-clock comparison (Task 1.3).

WHAT: Runs the SAME research task twice through coordinator.run_research()
- once with parallel=False (one Agent tool call per coordinator turn,
waiting for each result before issuing the next) and once with
parallel=True (web_researcher and document_analyst issued as two Agent
tool_use blocks in the same coordinator turn) - and prints both
wall-clock times side by side.

WHY the comparison is meaningful even though both runs invoke the same
two subagents: the dominant cost here is real Claude API round-trip
latency per turn, not local compute. The sequential arm pays for three
full round trips end to end (web_researcher turn, document_analyst turn,
synthesizer turn); the parallel arm pays for two (the fan-out turn, where
both subagent calls overlap in-flight, then the fan-in/synthesizer
turn). The gap you see is the SDK's own subagent concurrency at work,
not anything this script does - see the ANTI-PATTERN note in
coordinator.py about why this isn't implemented with asyncio.gather.

EXAM TASK: Task 1.3 - parallel spawning benchmark with wall-clock
evidence, run against a real coordinator session (not a simulation).

ANTI-PATTERN: benchmarking by counting API calls instead of wall-clock
time. Two subagent calls issued in parallel and two issued sequentially
cost the same NUMBER of calls - the only observable difference is
elapsed time, which is exactly why this script measures
time.monotonic() around the whole run (in coordinator.py) rather than
counting tool_use blocks.
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
