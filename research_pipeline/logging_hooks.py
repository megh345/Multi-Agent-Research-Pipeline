"""
logging_hooks.py - observability layer: log every subagent spawn/completion.

WHAT: A PreToolUse hook (matcher="Agent") that logs, with a real
monotonic timestamp, which subagent is being spawned and the (truncated)
prompt it's being given. A SubagentStop hook that logs when a subagent
finishes.

WHY hooks rather than logging inside the coordinator's own message loop:
a hook fires from inside the SDK itself, at the moment the event actually
happens, regardless of how the coordinator's message stream happens to be
consumed. That makes hook timestamps trustworthy evidence for
benchmark.py's parallel-vs-sequential comparison - two PreToolUse firings
a few milliseconds apart is proof the SDK issued both tool calls in the
same turn, not just that our own code printed two lines close together.

EXAM TASK: Task 3 (hooks) - PreToolUse / SubagentStop registered via
`HookMatcher` in `ClaudeAgentOptions.hooks`, using the CONFIRMED dict-in/
dict-out callback signature `async def hook(input_data, tool_use_id,
context) -> dict`. (An earlier draft of this file used a dataclass-based
`HookContext`/`PreToolUseResult` API - that turned out to be fabricated
by a documentation-fetch summarizer, not the real SDK. Verified against
the actual hooks.md page before writing this version.)

ANTI-PATTERN: printing spawn/completion info only from inside
coordinator.py's own message-parsing loop. That conflates "what the
orchestrating script chose to log after the fact" with "what the SDK
guarantees happened" - a hook is a more faithful record of execution
because it can't be skipped by a bug in how we iterate messages.
"""
from __future__ import annotations

import time
from typing import Any

from claude_agent_sdk import HookMatcher

# Populated by pre_tool_use_agent_logger; read back by coordinator.py after
# a run to build the ResearchRun.spawn_log_snapshot, and by benchmark.py to
# compute wall-clock overlap between spawns. A plain module-level list is
# enough here since each demo scenario runs exactly one query() at a time -
# a concurrent-queries setup would need this scoped per-run instead.
SPAWN_LOG: list[dict[str, Any]] = []


def _truncate(text: str, limit: int) -> str:
    text = text.strip().replace("\n", " ")
    return text if len(text) <= limit else text[: limit] + "..."


async def pre_tool_use_agent_logger(
    input_data: dict[str, Any], tool_use_id: str | None, context: Any
) -> dict[str, Any]:
    """Fires before EVERY tool call; the matcher="Agent" on the
    HookMatcher that registers this (see build_logging_hooks below)
    means the SDK only invokes it for Agent tool calls - but we still
    guard on tool_name here too, defensively, in case this callback is
    ever reused under a broader matcher."""
    if input_data.get("tool_name") != "Agent":
        return {}

    tool_input = input_data.get("tool_input", {}) or {}
    subagent_type = tool_input.get("subagent_type", "<unknown>")
    prompt = tool_input.get("prompt", "")
    ts = time.monotonic()

    SPAWN_LOG.append(
        {
            "subagent_type": subagent_type,
            "tool_use_id": tool_use_id,
            "spawned_at": ts,
            "prompt_preview": _truncate(prompt, 500),
        }
    )

    print(f"[SPAWN  t={ts:.3f}] {subagent_type:<18} <- prompt: {_truncate(prompt, 160)}")

    # {} = allow the call, unchanged. A logging hook must never block or
    # mutate the operation it's observing - see PreToolUseResult's
    # "return {} to allow without changes" contract in hooks.md.
    return {}


async def subagent_stop_logger(
    input_data: dict[str, Any], tool_use_id: str | None, context: Any
) -> dict[str, Any]:
    agent_id = input_data.get("agent_id", "<unknown>")
    ts = time.monotonic()
    print(f"[DONE   t={ts:.3f}] agent_id={agent_id}")
    return {}


def build_logging_hooks() -> dict[str, list[HookMatcher]]:
    """Registers both hooks. matcher="Agent" on PreToolUse means the SDK
    filters to Agent tool calls for us before the callback even runs -
    the tool_name guard inside the callback is belt-and-suspenders, not
    load-bearing filtering."""
    return {
        "PreToolUse": [HookMatcher(matcher="Agent", hooks=[pre_tool_use_agent_logger])],
        "SubagentStop": [HookMatcher(hooks=[subagent_stop_logger])],
    }
