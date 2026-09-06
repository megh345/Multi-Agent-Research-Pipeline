# Multi-Agent Research Pipeline

A Python research orchestration project that uses the Claude Agent SDK to
coordinate specialized subagents for evidence gathering, document review,
and final report synthesis.

The pipeline accepts a research topic, sends work to a web researcher and
document analyst, validates that extracted findings include source
metadata, and produces an attributed Markdown report. Mock data sources
keep the workflow deterministic so parallel execution, retrieval
failures, and conflicting claims can be demonstrated reliably.

## What this project demonstrates

- Multi-agent coordination with specialized subagents.
- Parallel fan-out for independent evidence gathering.
- Explicit context passing between coordinator and subagents.
- Structured findings with required source attribution.
- Deterministic handling of timeouts, partial results, and conflicting
  sources.
- Hook-based observability for subagent spawn and completion events.

For the full orchestration diagram and module-level architecture, see
`ARCHITECTURE.md`.

## Tech stack

- Python 3.10+
- Claude Agent SDK
- In-process MCP tools for deterministic mock research sources

## Setup

Create and activate a virtual environment if desired, then install the
project dependency:

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
```

`run_demo.py` and `benchmark.py` make real Claude API calls. The
coordinator and subagents run through the SDK; only the research data
sources are mocked through `research_pipeline/fixtures.py`.

## Run

```bash
# Run all demonstration scenarios:
python run_demo.py

# Compare sequential and parallel subagent execution:
python -m research_pipeline.benchmark
```

## Repository structure

The main implementation lives in `research_pipeline/`. This README keeps
the layout concise; `ARCHITECTURE.md` provides the deeper flow and design
rationale.

```text
research_pipeline/
  fixtures.py        deterministic mock articles and documents
  schemas.py         shared Finding and FailureReport contracts
  mock_tools.py      SDK tools for mock search and document retrieval
  agents_config.py   subagent definitions and SDK option wiring
  logging_hooks.py   subagent lifecycle observability hooks
  coordinator.py     top-level orchestration and stream parsing
  verification.py    deterministic attribution checks
  benchmark.py       sequential vs. parallel timing comparison
run_demo.py          runnable scenario demo
ARCHITECTURE.md      detailed architecture and data-flow notes
```

## Notes

This project was designed as a deterministic multi-agent demo, not a live
web research product. It uses fixed fixtures so results are repeatable
while still exercising realistic agent coordination patterns.
