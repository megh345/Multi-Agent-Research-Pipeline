# Architecture

Exercise 4 from the Claude Certified Architect - Foundations exam guide:
a multi-agent research pipeline built on the real Claude Agent SDK
(Python), with mock data sources for deterministic, repeatable behaviour.

## Flow

```
                         +---------------------------+
                         |   Coordinator              |
                         |   (main query() session)   |
                         |   - directive prompt        |
                         |   - agents={web_researcher, |
                         |     document_analyst,       |
                         |     synthesizer}             |
                         |   - allowed_tools has        |
                         |     "Agent"                  |
                         +--------------+---------------+
                                        |
                     Turn 1: FAN-OUT (parallel, Task 1)
                                        |
                +-----------------------+-----------------------+
                | Agent tool_use                                 | Agent tool_use
                v                                                 v
    +------------------------+                       +---------------------------+
    | web_researcher          |                       | document_analyst           |
    | tool: search_web         |                       | tool: fetch_documents       |
    | (mock_tools.py ->         |                       | (mock_tools.py ->            |
    |  fixtures.ARTICLES)        |                       |  fixtures.DOCUMENTS)          |
    +-----------+--------------+                       +--------------+--------------+
                | JSON {status, findings|failure}                       | JSON {status, findings}
                +-----------------------+-----------------------------+
                                        |
                     Turn 2: FAN-IN (necessarily sequential -
                     synthesizer depends on BOTH prior outputs)
                                        |
                                        v
                         +---------------------------+
                         | synthesizer                 |
                         | tools: none - reasons        |
                         | only over what the           |
                         | coordinator passed it         |
                         | verbatim (Task 2)              |
                         +--------------+----------------+
                                        | Markdown report
                                        v
                         +---------------------------+
                         | Coordinator's final message |
                         | == the report, unmodified   |
                         +---------------------------+
```

Two things worth noticing about this shape:

1. **Fan-out / fan-in, not full 3-way parallelism.** web_researcher and
   document_analyst are independent, so both `Agent` tool calls land in
   the coordinator's *same* assistant turn (Task 1). synthesizer depends
   on both of their outputs, so it necessarily runs in a *second* turn.
   Claiming all three run in parallel would misrepresent the dependency
   graph - see `coordinator.py`'s `_build_coordinator_directive`.

2. **Subagents inherit nothing.** Per the SDK's own docs, a non-fork
   subagent's context contains only its `AgentDefinition.prompt` plus the
   `Agent` tool's `prompt` string for that call - not the coordinator's
   conversation history, not its tool results, not its system prompt.
   Every arrow carrying "JSON {...}" or a prompt string in the diagram
   above is content someone had to *explicitly* put into a prompt; none
   of it is inherited. `coordinator.py` has a "what would break if this
   were removed" comment above each prompt-builder function.

## File -> task statement map

| File | Role | Task statement(s) it demonstrates |
|---|---|---|
| `research_pipeline/fixtures.py` | Mock articles/documents keyed by `topic_id`; the one place fake "data" lives | Mock data sources requirement; setup for 5.1 and 5.2 |
| `research_pipeline/schemas.py` | `Finding` / `FailureReport` dataclasses - the shared structured-output contract | Task 3/4.2 - structured output with metadata |
| `research_pipeline/mock_tools.py` | `search_web` / `fetch_documents` custom SDK tools (`@tool` + `create_sdk_mcp_server`), deterministic timeout injection | Task 2.4 - custom tools; Task 5.1 - deterministic failure fixture |
| `research_pipeline/agents_config.py` | `AgentDefinition`s for web_researcher, document_analyst, synthesizer; tool restriction per subagent; `ClaudeAgentOptions` wiring | Task 2.1/2.2/2.3 - AgentDefinition, tool restriction |
| `research_pipeline/logging_hooks.py` | `PreToolUse`/`SubagentStop` hooks logging every spawn/completion with real timestamps | Task 3 (hooks) - observability |
| `research_pipeline/coordinator.py` | Builds subagent prompts (with context-passing comments), runs the coordinator `query()`, parses the message stream | Task 1 - parallel spawning; Task 2 - explicit context passing; Task 5.1 - proceeding on partial results |
| `research_pipeline/verification.py` | `verify_findings_have_sources()`, `classify_coverage()` - deterministic checks, not LLM judgment | Task 4.2 - verification function |
| `research_pipeline/benchmark.py` | Sequential vs. parallel wall-clock comparison, run against a real coordinator session | Task 1.3 - parallel spawning benchmark |
| `run_demo.py` | Runs all five scenarios in sequence with headers | All five behaviours, end to end |

## The three mock topics and what each exercises

| `topic_id` | Exercises | Why |
|---|---|---|
| `ai_regulation_eu` | Task 1 (parallel spawning), Task 3 (structured output + verification) | Clean, multi-source, no failures - a baseline where nothing goes wrong |
| `grid_battery_storage_2026` | Task 5.1 (error propagation) | `search_web` always simulates a timeout for this `topic_id`; `fetch_documents` still succeeds, forcing the coordinator to proceed on partial (document-only) coverage |
| `global_ev_adoption_rate` | Task 5.2 (conflicting sources) | Two real-looking articles give different EV market-share figures for the same year, from different publishers, different dates - both must survive into the report, never merged |

## Where determinism lives, and where it doesn't

The fixtures and mock tools are fully deterministic: the same `topic_id`
always returns the same articles/documents, or deterministically times
out. What is *not* code-guaranteed is the coordinator's exact phrasing
turn to turn, since it's a real Claude session following the directive
in `coordinator.py` rather than a hardcoded script. In practice Sonnet
follows the strict JSON-only and fan-out/fan-in instructions reliably,
and `verification.py` exists precisely so that reliability is checked
automatically rather than assumed.
