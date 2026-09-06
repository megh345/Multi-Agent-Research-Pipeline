"""
mock_tools.py - deterministic fake "web search" and "document store" tools.

WHAT: Two custom SDK tools - search_web and fetch_documents - wired to
research_pipeline.fixtures instead of a real search API or filesystem.
Wrapped in an in-process MCP server (`create_sdk_mcp_server`) and handed
to the web_researcher and document_analyst subagents respectively.

WHY: the exercise requires "deterministic, repeatable behaviour... to
trigger timeouts and conflicts on demand." A real web search tool returns
different results every run and can't be told to fail on command. Custom
SDK tools built on an in-process MCP server give us a function we fully
control: same topic_id in, same (or deliberately-broken) result out,
every time, with zero network calls.

EXAM TASK: Task 2.4 - custom tools via the in-process MCP server
(`@tool` decorator + `create_sdk_mcp_server`), registered through
`ClaudeAgentOptions.mcp_servers` and gated by `allowed_tools` using the
`mcp__{server_name}__{tool_name}` fully-qualified naming convention
confirmed in the SDK's custom-tools reference.

ANTI-PATTERN: calling a real search API from inside a study/demo
environment. Findings would differ across runs, you could never reliably
reproduce the timeout or conflicting-sources scenarios on demand, and the
demo would be flaky in front of whoever you're showing it to.
"""
from __future__ import annotations

import asyncio
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

from research_pipeline.fixtures import ARTICLES, DOCUMENTS, KNOWN_TOPIC_IDS, TIMEOUT_TOPICS


def _topic_enum_schema(description: str) -> dict[str, Any]:
    """
    WHAT: A JSON Schema (not the `{"name": type}` shorthand) that
    constrains the `topic_id` argument to the fixed set of topic IDs
    fixtures.py actually knows about, via an `enum`. The Python `@tool`
    decorator's dict shorthand has no enum support - the SDK docs are
    explicit that an enum requires the full JSON Schema dict form.

    WHY: this is what makes "trigger a timeout on demand" reliable
    despite the tool being called by an LLM rather than by our own code:
    the LLM can only pass one of a fixed set of strings, so the same
    subagent prompt reliably lands on the same fixture data (or the same
    simulated failure) every run. Without the enum, the subagent could
    paraphrase the topic ("EV adoption stats" vs. "electric vehicle
    market share") and the mock tool would have nothing to match against.

    EXAM TASK: Task 2.4 - JSON Schema tool input definitions.
    """
    return {
        "type": "object",
        "properties": {
            "topic_id": {
                "type": "string",
                "enum": sorted(KNOWN_TOPIC_IDS),
                "description": description,
            }
        },
        "required": ["topic_id"],
    }


@tool(
    "search_web",
    "Search mock news/article sources for a research topic. "
    f"topic_id must be exactly one of: {', '.join(sorted(KNOWN_TOPIC_IDS))}.",
    _topic_enum_schema("The fixed topic identifier to search for."),
)
async def search_web(args: dict[str, Any]) -> dict[str, Any]:
    topic_id = args["topic_id"]

    if topic_id in TIMEOUT_TOPICS:
        # WHAT: simulate a network timeout deterministically, keyed off
        # topic_id rather than randomness or a real clock race.
        # WHY (Task 5.1): the exercise asks for a fixture that makes
        # web_researcher time out "on demand" - this topic_id reliably
        # reproduces the failure every single run.
        # is_error=True (not a raised exception) lets us compose the
        # exact message web_researcher's prompt tells it to expect,
        # instead of leaving it to whatever string a raw exception
        # would produce - see custom-tools.md's "Handle errors" section.
        await asyncio.sleep(2)
        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"TIMEOUT: search_web(topic_id='{topic_id}') did not respond "
                        "within the configured window (simulated 2s deterministic "
                        "timeout fixture). No articles were retrieved for this topic."
                    ),
                }
            ],
            "is_error": True,
        }

    articles = ARTICLES.get(topic_id, [])
    if not articles:
        return {
            "content": [
                {"type": "text", "text": f"No articles found for topic_id='{topic_id}'."}
            ]
        }

    lines = [f"Found {len(articles)} article(s) for topic_id='{topic_id}':", ""]
    for a in articles:
        lines.append(
            f"- title: {a['title']}\n"
            f"  source_name: {a['source_name']}\n"
            f"  source_url: {a['source_url']}\n"
            f"  published_date: {a['published_date']}\n"
            f"  excerpt: {a['excerpt']}"
        )
    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


@tool(
    "fetch_documents",
    "Fetch mock internal documents relevant to a research topic. "
    f"topic_id must be exactly one of: {', '.join(sorted(KNOWN_TOPIC_IDS))}.",
    _topic_enum_schema("The fixed topic identifier to fetch documents for."),
)
async def fetch_documents(args: dict[str, Any]) -> dict[str, Any]:
    topic_id = args["topic_id"]
    docs = DOCUMENTS.get(topic_id, [])
    if not docs:
        return {
            "content": [
                {"type": "text", "text": f"No internal documents found for topic_id='{topic_id}'."}
            ]
        }

    lines = [f"Found {len(docs)} document(s) for topic_id='{topic_id}':", ""]
    for d in docs:
        lines.append(
            f"- doc_id: {d['doc_id']}\n"
            f"  title: {d['title']}\n"
            f"  source_name: {d['source_name']}\n"
            f"  published_date: {d['published_date']}\n"
            f"  body: {d['body']}"
        )
    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


# WHAT: wraps both tools in a single in-process MCP server named
# "research_tools". WHY one server for both: they share one data domain
# (this project's mock fixtures) and one lifecycle - there is no reason
# to pay for two separate server registrations here.
research_tools_server = create_sdk_mcp_server(
    name="research_tools",
    version="1.0.0",
    tools=[search_web, fetch_documents],
)

# Fully-qualified tool names, in the mcp__{server_name}__{tool_name} form
# the SDK requires in allowed_tools / AgentDefinition.tools. Named
# constants here (rather than the literal string repeated in
# agents_config.py) so a future rename of the server can't silently
# desync one call site from another.
SEARCH_WEB_TOOL = "mcp__research_tools__search_web"
FETCH_DOCUMENTS_TOOL = "mcp__research_tools__fetch_documents"
