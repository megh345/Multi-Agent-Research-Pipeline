# Multi-Agent Research Pipeline

Exercise 4 from the Claude Certified Architect - Foundations exam guide,
built on the real Claude Agent SDK (Python). See `ARCHITECTURE.md` for
the flow diagram and a file-to-task-statement map.

## Setup

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
```

This is a real SDK application - `run_demo.py` and `benchmark.py` make
real Claude API calls (the coordinator and all three subagents are real
Sonnet sessions). Only the *data sources* (`search_web`, `fetch_documents`)
are mocked, via `research_pipeline/fixtures.py` - see
`ARCHITECTURE.md`'s "Where determinism lives" section for what that
does and doesn't guarantee.

## Run

```bash
# All five required behaviours, in order, with printed headers:
python run_demo.py

# Sequential vs. parallel spawning, wall-clock comparison:
python -m research_pipeline.benchmark
```

## Project layout

```
research_pipeline/
  fixtures.py        mock articles/documents, keyed by topic_id
  schemas.py         Finding / FailureReport structured-output contracts
  mock_tools.py      search_web / fetch_documents custom SDK tools
  agents_config.py   AgentDefinitions + ClaudeAgentOptions wiring
  logging_hooks.py   PreToolUse / SubagentStop observability hooks
  coordinator.py     orchestration: prompts, query(), message parsing
  verification.py    deterministic checks on structured output
  benchmark.py       sequential vs. parallel timing
run_demo.py          runs all five scenarios
ARCHITECTURE.md      flow diagram + task-statement map
```
