"""
coordinator.py - the top-level orchestration logic (Tasks 1, 2 and 5 hub).

WHAT: run_research() drives one end-to-end pipeline run. It builds the
exact prompt text each subagent will receive, wires up a coordinator
directive that controls whether the fan-out phase runs in parallel or
sequentially, runs the coordinator as a real Claude Agent SDK `query()`
session with the three subagents registered, and parses the resulting
message stream into a ResearchRun the demo/benchmark scripts can print
or assert against.

WHY this is one coordinator query() session rather than three manual
query() calls we sequence ourselves in Python: the entire point of
Task 1 (parallel spawning) is that a SINGLE Claude session, given the
Agent tool and multiple registered subagents, can emit more than one
Agent tool_use block in the same assistant turn, and have the SDK run
them concurrently - "multiple subagents can run concurrently... finish
in the time of the slowest one rather than the sum of all of them," per
the SDK's own subagents documentation. If we instead called query()
three times ourselves and wrapped them in asyncio.gather, we would be
reimplementing scheduling in OUR code and would never actually exercise
the SDK's own subagent concurrency - we'd be demonstrating asyncio, not
the Agent SDK.

A NOTE ON NAMING: the exam guide (and most people's mental model) calls
this the "Task tool". The SDK renamed it "Agent" in Claude Code v2.1.63;
current SDK releases emit "Agent" in tool_use blocks, but permission
denials and the system:init tools list can still say "Task". This file
checks both names wherever it inspects tool_use blocks, and the
allow-list in agents_config.py lists "Agent" (the current name) -
matching the SDK's own documented compatibility guidance rather than
picking one name from memory.

EXAM TASK: this file ties together Task 1 (parallel spawning), Task 2
(explicit context passing - see the prompt-builder functions below,
each with a "what would break if removed" comment), and Task 5 (error
propagation continuing the pipeline instead of aborting it).

ANTI-PATTERN: hardcoding three separate query() calls under
asyncio.gather. That produces a similar-looking wall-clock speedup for
the WRONG reason - our code parallelized, not the coordinator agent -
and none of the "coordinator sees both results and decides how to
synthesize them" reasoning this exercise is actually about would happen
at all.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from claude_agent_sdk import ToolResultBlock, ToolUseBlock, query

from research_pipeline.agents_config import build_agent_options
from research_pipeline.logging_hooks import SPAWN_LOG, build_logging_hooks

DEFAULT_QUESTIONS: dict[str, str] = {
    "ai_regulation_eu": "What is the current status of AI regulation in the EU?",
    "grid_battery_storage_2026": "What is the outlook for grid-scale battery storage in 2026?",
    "global_ev_adoption_rate": "What share of global new car sales were electric vehicles in 2024?",
}


@dataclass
class ResearchRun:
    """Everything a demo/benchmark script needs after one pipeline run."""

    topic_id: str
    research_question: str
    parallel: bool
    final_report: str
    raw_agent_results: dict[str, str] = field(default_factory=dict)  # subagent_type -> raw text
    wall_clock_seconds: float = 0.0
    spawn_log_snapshot: list[dict[str, Any]] = field(default_factory=list)


def _build_web_researcher_prompt(research_question: str, topic_id: str) -> str:
    # ------------------------------------------------------------------
    # TASK 2 (explicit context passing): web_researcher's process starts
    # completely empty except for AgentDefinition.prompt (its own system
    # prompt) plus this exact string - confirmed by the SDK's own docs:
    # a non-fork subagent receives "its own system prompt and the Agent
    # tool's prompt" and explicitly does NOT receive "the parent's
    # conversation history or tool results". Nothing said anywhere else
    # in this coordinator run reaches web_researcher unless it's in here.
    #
    # WHAT WOULD BREAK IF `research_question` WERE REMOVED: web_researcher
    # would still successfully call search_web and return well-formed
    # Findings - the tool call itself doesn't need the question, only
    # topic_id. But the synthesizer later has no way to judge whether a
    # given finding actually answers what was asked, and the final
    # report's NOT COVERED section becomes impossible to compute
    # correctly, because nothing downstream knows what "coverage" was
    # being measured against. The failure is silent: everything still
    # runs without error, the output just becomes subtly wrong.
    # ------------------------------------------------------------------
    return (
        f"Original research question (verbatim, for your context only - "
        f"you do not need to restate it): {research_question}\n\n"
        f'Use topic_id="{topic_id}" when calling search_web.'
    )


def _build_document_analyst_prompt(research_question: str, topic_id: str) -> str:
    # ------------------------------------------------------------------
    # TASK 2: same isolation contract as web_researcher's prompt above -
    # document_analyst also starts with nothing but its own system prompt
    # and this string.
    #
    # WHAT WOULD BREAK IF `topic_id` WERE REMOVED: unlike the question
    # above, this is not a subtle downstream failure. document_analyst
    # would have no valid value to pass into fetch_documents(topic_id),
    # and the tool's JSON Schema `enum` constraint (mock_tools.py) would
    # reject anything it guessed instead - an immediate, loud tool-call
    # error. That's exactly why topic_id is treated as load-bearing here,
    # unlike the question text, which is contextual.
    # ------------------------------------------------------------------
    return (
        f"Original research question (verbatim, for your context only): "
        f"{research_question}\n\n"
        f'Use topic_id="{topic_id}" when calling fetch_documents.'
    )


def _build_synthesizer_instruction() -> str:
    # ------------------------------------------------------------------
    # TASK 2: this is an instruction TO THE COORDINATOR about how to
    # build the synthesizer's prompt, not the synthesizer's prompt
    # itself - the coordinator can only assemble it after seeing both
    # upstream results, so (unlike the two functions above) it can't be
    # a plain string template computed up front.
    #
    # WHAT WOULD BREAK IF THIS RULE WERE REMOVED: if the coordinator
    # forwarded only a paraphrased summary of web_researcher's and
    # document_analyst's JSON instead of the raw JSON verbatim,
    # source_url/published_date fields could be dropped or reworded in
    # the retelling - and the synthesizer has no way to detect that,
    # since (per Task 2) it never sees the original tool results, only
    # what the coordinator chooses to relay. Attribution would silently
    # degrade one hop downstream of where the actual bug is, which is
    # exactly the failure mode "explicit context passing" exists to rule
    # out.
    # ------------------------------------------------------------------
    return (
        'When you call the Agent tool for subagent_type="synthesizer", '
        "the prompt you send it MUST contain, verbatim and in full: "
        "(1) the original research question, "
        "(2) the COMPLETE raw JSON text that web_researcher returned, "
        "(3) the COMPLETE raw JSON text that document_analyst returned. "
        "Do not summarize, paraphrase, or truncate either JSON result - "
        "copy them exactly as you received them, even if one of them has "
        'status "error".'
    )


def _build_coordinator_directive(research_question: str, topic_id: str, *, parallel: bool) -> str:
    """Builds the single prompt string passed to the coordinator's own
    query(). This is the ONE place in the whole pipeline that has to
    reason about both subagents' eventual outputs, which is why it's
    also where the fan-out (parallel vs. sequential) instruction lives."""
    web_prompt = _build_web_researcher_prompt(research_question, topic_id)
    doc_prompt = _build_document_analyst_prompt(research_question, topic_id)
    synth_rule = _build_synthesizer_instruction()

    if parallel:
        # TASK 1 (parallel spawning): web_researcher and document_analyst
        # are independent of each other - neither needs the other's
        # output - so both Agent tool calls belong in the SAME assistant
        # turn. synthesizer is necessarily a SECOND turn (fan-in) since
        # it depends on both of their results: true 3-way single-turn
        # parallelism isn't possible here, and claiming otherwise would
        # misrepresent the dependency graph. This fan-out/fan-in shape -
        # not full parallelism - is the honest, exam-accurate pattern.
        fanout_rule = (
            "Call the Agent tool TWICE - once for web_researcher, once for "
            "document_analyst - in the SAME response. Do not wait for one "
            "to return before issuing the other. This is the parallel "
            "fan-out phase."
        )
    else:
        # ANTI-PATTERN, demonstrated on purpose: one Agent call per turn,
        # waiting for the full result before issuing the next. This is
        # what benchmark.py's "sequential" arm exercises, specifically so
        # the parallel speedup in scenario 1 is visible by contrast
        # rather than asserted.
        fanout_rule = (
            "Call the Agent tool for web_researcher FIRST. Wait for its "
            "complete result. THEN call the Agent tool for "
            "document_analyst. Wait for its complete result. Do not call "
            "more than one Agent tool in a single response at any point "
            "in this run."
        )

    return f"""You are the research coordinator. Research question: {research_question}
Topic ID for all subagent tool calls: {topic_id}

Step 1 - gather evidence.
{fanout_rule}
Even if one of the two subagents returns status "error", still proceed to
Step 2 - do not abort the pipeline because one source failed.

Send this exact prompt to web_researcher:
---
{web_prompt}
---

Send this exact prompt to document_analyst:
---
{doc_prompt}
---

Step 2 - synthesize.
{synth_rule}

Step 3 - final answer.
Once synthesizer returns its Markdown report, your own final message must
be EXACTLY that report, character for character, with nothing added,
removed, or summarized."""


def _extract_text(content: Any) -> str:
    """
    Normalizes a ToolResultBlock's `content` into one string. The SDK's
    own documented examples show `content` can be either a plain string
    or a list of dict-shaped parts with a "text" key (see the
    `extract_agent_id` pattern in the subagents.md "Resume subagents"
    example) - this handles both, defensively, rather than assuming one.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict):
                parts.append(part.get("text", ""))
            else:
                parts.append(str(part))
        return "".join(parts)
    return str(content)


async def run_research(
    topic_id: str,
    *,
    parallel: bool = True,
    research_question: str | None = None,
) -> ResearchRun:
    """Runs one full coordinator session end to end and returns a
    ResearchRun with the final report, each subagent's raw JSON result,
    wall-clock time, and the hook-captured spawn log."""
    question = research_question or DEFAULT_QUESTIONS[topic_id]
    directive = _build_coordinator_directive(question, topic_id, parallel=parallel)

    SPAWN_LOG.clear()
    options = build_agent_options(hooks=build_logging_hooks())

    raw_results: dict[str, str] = {}
    # Maps a ToolUseBlock's id to the subagent_type it invoked, so that
    # when the matching ToolResultBlock arrives later in the stream we
    # know which subagent's output we're looking at - the SDK correlates
    # tool_use/tool_result by id, the same way the wider Anthropic
    # Messages API always has.
    pending_tool_names: dict[str, str] = {}
    final_report = ""

    start = time.monotonic()
    async for message in query(prompt=directive, options=options):
        content = getattr(message, "content", None)
        if content:
            for block in content:
                if isinstance(block, ToolUseBlock) and block.name in ("Task", "Agent"):
                    subagent_type = block.input.get("subagent_type", "<unknown>")
                    pending_tool_names[block.id] = subagent_type
                elif isinstance(block, ToolResultBlock):
                    subagent_type = pending_tool_names.get(block.tool_use_id, "<unknown>")
                    text = _extract_text(block.content)
                    raw_results[subagent_type] = text
                    elapsed = time.monotonic() - start
                    preview = text.strip().replace("\n", " ")[:160]
                    print(f"[RESULT t={elapsed:.3f}] {subagent_type:<18} -> {preview}...")

        if hasattr(message, "result") and message.result:
            final_report = message.result

    wall_clock_seconds = time.monotonic() - start

    return ResearchRun(
        topic_id=topic_id,
        research_question=question,
        parallel=parallel,
        final_report=final_report,
        raw_agent_results=raw_results,
        wall_clock_seconds=wall_clock_seconds,
        spawn_log_snapshot=list(SPAWN_LOG),
    )
