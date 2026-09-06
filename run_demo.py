"""
run_demo.py - runs all five required behaviours in sequence, with clear
printed headers, so each one can be watched happening independently.

WHAT: five async scenario functions, one per exercise requirement, each
calling into research_pipeline.coordinator.run_research() with the
topic_id fixture chosen specifically to exercise that behaviour (see the
per-topic comments in research_pipeline/fixtures.py for why each topic_id
was picked).

WHY one script instead of five separate ad hoc runs: the point of this
file is to be the thing you actually run and watch, in order, once per
study session - not a test suite. Keeping it as one script makes it
visible that all five behaviours are facets of the SAME coordinator/
subagent architecture (agents_config.py + coordinator.py), not five
unrelated features bolted on separately.

EXAM TASK: demonstrates Tasks 1 through 5 end to end, in the order the
exercise lists them. Requires ANTHROPIC_API_KEY to be set - see README.md.
"""
from __future__ import annotations

import asyncio
import json

from research_pipeline.coordinator import run_research
from research_pipeline.verification import MissingSourceError, verify_findings_have_sources


def _header(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


async def scenario_1_parallel_spawning() -> None:
    _header("SCENARIO 1 - Parallel spawning (Task 1)")
    run = await run_research("ai_regulation_eu", parallel=True)

    print("\nSpawn log (from the PreToolUse hook - real timestamps, not estimates):")
    for entry in run.spawn_log_snapshot:
        print(f"  t={entry['spawned_at']:.3f}  {entry['subagent_type']}")

    if len(run.spawn_log_snapshot) >= 2:
        gap = abs(run.spawn_log_snapshot[1]["spawned_at"] - run.spawn_log_snapshot[0]["spawned_at"])
        print(
            f"\nGap between the first two spawns: {gap:.3f}s "
            "(near-zero confirms they were emitted in the SAME coordinator "
            "turn, not one after the other - see coordinator.py's fan-out "
            "instruction)."
        )

    print(f"\nTotal wall-clock for this run: {run.wall_clock_seconds:.2f}s")


async def scenario_2_explicit_context_passing() -> None:
    _header("SCENARIO 2 - Explicit context passing (Task 2)")
    run = await run_research("ai_regulation_eu", parallel=True)

    print(
        "\nEach subagent's actual prompt, as captured by the PreToolUse hook.\n"
        "This is ALL the context that subagent received - nothing else from\n"
        "this conversation reached it. See the 'what would break if removed'\n"
        "comments above each prompt-builder function in coordinator.py.\n"
    )
    for entry in run.spawn_log_snapshot:
        print(f"--- {entry['subagent_type']} ---")
        print(entry.get("prompt_preview", "<not captured>"))
        print()


async def scenario_3_structured_output() -> None:
    _header("SCENARIO 3 - Structured output with metadata (Task 3)")
    run = await run_research("ai_regulation_eu", parallel=True)

    for subagent_name in ("web_researcher", "document_analyst"):
        raw = run.raw_agent_results.get(subagent_name, "")
        try:
            findings = verify_findings_have_sources(raw, subagent_name=subagent_name)
            print(f"[PASS] {subagent_name}: {len(findings)} finding(s), all fully sourced.")
            for f in findings:
                print(f"   - {f.claim!r} <- {f.source_name} ({f.published_date})")
        except MissingSourceError as e:
            print(f"[FAIL] {subagent_name}: {e}")

    print("\n--- Final synthesized report ---\n")
    print(run.final_report)


async def scenario_4_error_propagation() -> None:
    _header("SCENARIO 4 - Error propagation with partial results (Task 5.1)")
    run = await run_research("grid_battery_storage_2026", parallel=True)

    web_raw = run.raw_agent_results.get("web_researcher", "")
    try:
        payload = json.loads(web_raw)
        print(f"web_researcher status: {payload.get('status')}")
        if payload.get("status") == "error":
            failure = payload["failure"]
            print(f"  failure_type: {failure.get('failure_type')}")
            print(f"  what_was_attempted: {failure.get('what_was_attempted')}")
            print(f"  partial_results: {len(failure.get('partial_results', []))} finding(s)")
            print(f"  suggested_alternatives: {failure.get('suggested_alternatives')}")
    except json.JSONDecodeError:
        print("web_researcher did not return valid JSON.")

    print("\n--- Final report (should show LIMITED COVERAGE, not a crash) ---\n")
    print(run.final_report)


async def scenario_5_conflicting_sources() -> None:
    _header("SCENARIO 5 - Conflicting sources, never averaged (Task 5.2)")
    run = await run_research("global_ev_adoption_rate", parallel=True)

    print(run.final_report)

    has_18 = "18%" in run.final_report
    has_22 = "22%" in run.final_report
    verdict = "PASS" if (has_18 and has_22) else "FAIL"
    print(
        f"\n[CHECK] Report preserves BOTH conflicting figures (18% AND 22%, "
        f"not a merged/averaged 20%): {verdict}"
    )


async def main() -> None:
    await scenario_1_parallel_spawning()
    await scenario_2_explicit_context_passing()
    await scenario_3_structured_output()
    await scenario_4_error_propagation()
    await scenario_5_conflicting_sources()


if __name__ == "__main__":
    asyncio.run(main())
