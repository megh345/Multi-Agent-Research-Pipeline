"""
Top-level orchestration for the multi-agent research pipeline.

run_research() builds each subagent prompt, configures whether evidence
gathering runs in parallel or sequentially, starts one Claude Agent SDK
coordinator session, and parses the streamed results into a ResearchRun.

The coordinator uses the SDK's Agent tool rather than manually launching
separate query() calls in Python. That keeps scheduling, subagent
execution, and fan-in/fan-out behavior inside the same agent session the
pipeline is designed to demonstrate.

The SDK has used both "Task" and "Agent" names for subagent tool blocks
across releases, so stream parsing accepts either name while the current
allowed_tools configuration lists "Agent".
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
    """Captured output and metadata for one completed pipeline run."""

    topic_id: str
    research_question: str
    parallel: bool
    final_report: str
    raw_agent_results: dict[str, str] = field(default_factory=dict)  # subagent_type -> raw text
    wall_clock_seconds: float = 0.0
    spawn_log_snapshot: list[dict[str, Any]] = field(default_factory=list)


def _build_web_researcher_prompt(research_question: str, topic_id: str) -> str:
    # Subagents only receive their own system prompt plus the explicit
    # Agent-tool prompt. Include the original question so retrieved
    # findings can later be evaluated against the user's actual request,
    # not only against the fixture topic ID. Without this context,
    # downstream coverage checks cannot reliably identify unanswered
    # parts of the user's question.
    return (
        f"Original research question (verbatim, for your context only - "
        f"you do not need to restate it): {research_question}\n\n"
        f'Use topic_id="{topic_id}" when calling search_web.'
    )


def _build_document_analyst_prompt(research_question: str, topic_id: str) -> str:
    # The document analyst needs both the natural-language question for
    # context and the exact fixture topic ID required by fetch_documents().
    # Without the topic ID, the tool call cannot satisfy the schema enum
    # enforced by the mock document retrieval tool.
    return (
        f"Original research question (verbatim, for your context only): "
        f"{research_question}\n\n"
        f'Use topic_id="{topic_id}" when calling fetch_documents.'
    )


def _build_synthesizer_instruction() -> str:
    # This rule tells the coordinator how to construct the synthesizer
    # prompt after both upstream agents return. Passing raw JSON verbatim
    # preserves source URLs, dates, failure details, and partial results.
    # Summarizing those results before synthesis can drop attribution
    # fields that the final report is expected to expose.
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
    """Build the prompt passed to the coordinator's query() session."""
    web_prompt = _build_web_researcher_prompt(research_question, topic_id)
    doc_prompt = _build_document_analyst_prompt(research_question, topic_id)
    synth_rule = _build_synthesizer_instruction()

    if parallel:
        # web_researcher and document_analyst are independent, so they can
        # be spawned in the same coordinator turn. The synthesizer runs
        # afterward because it depends on both upstream results.
        fanout_rule = (
            "Call the Agent tool TWICE - once for web_researcher, once for "
            "document_analyst - in the SAME response. Do not wait for one "
            "to return before issuing the other. This is the parallel "
            "fan-out phase."
        )
    else:
        # Sequential mode is retained for benchmarking against the
        # parallel fan-out path.
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
    Normalize a ToolResultBlock content payload into one string.

    The SDK can provide tool results as a plain string or as a list of
    content parts. This helper handles both shapes before storing raw
    subagent results.
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
    """Run one full coordinator session and return its report metadata."""
    question = research_question or DEFAULT_QUESTIONS[topic_id]
    directive = _build_coordinator_directive(question, topic_id, parallel=parallel)

    SPAWN_LOG.clear()
    options = build_agent_options(hooks=build_logging_hooks())

    raw_results: dict[str, str] = {}
    # Map each tool_use id to the subagent_type it invoked so the
    # matching ToolResultBlock can be stored under the correct agent name.
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
