"""
Observability hooks for subagent lifecycle events.

The PreToolUse hook records when the coordinator invokes the Agent tool
and captures a short prompt preview for each subagent. The SubagentStop
hook records completion events. These SDK-level timestamps support the
benchmark script by showing whether independent subagents were spawned
in the same coordinator turn.
"""
from __future__ import annotations

import time
from typing import Any

from claude_agent_sdk import HookMatcher

# Populated by pre_tool_use_agent_logger and copied into ResearchRun after
# each run. The demo executes one query at a time; a multi-request service
# should scope this state per run instead of using a module-level list.
SPAWN_LOG: list[dict[str, Any]] = []


def _truncate(text: str, limit: int) -> str:
    text = text.strip().replace("\n", " ")
    return text if len(text) <= limit else text[: limit] + "..."


async def pre_tool_use_agent_logger(
    input_data: dict[str, Any], tool_use_id: str | None, context: Any
) -> dict[str, Any]:
    """Log Agent tool invocations before the SDK dispatches the subagent."""
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

    # Returning an empty dict allows the observed tool call to proceed
    # unchanged.
    return {}


async def subagent_stop_logger(
    input_data: dict[str, Any], tool_use_id: str | None, context: Any
) -> dict[str, Any]:
    agent_id = input_data.get("agent_id", "<unknown>")
    ts = time.monotonic()
    print(f"[DONE   t={ts:.3f}] agent_id={agent_id}")
    return {}


def build_logging_hooks() -> dict[str, list[HookMatcher]]:
    """Build the hook configuration passed into ClaudeAgentOptions."""
    return {
        "PreToolUse": [HookMatcher(matcher="Agent", hooks=[pre_tool_use_agent_logger])],
        "SubagentStop": [HookMatcher(hooks=[subagent_stop_logger])],
    }
