"""
Deterministic mock tools for web search and document retrieval.

The custom SDK tools in this module read from research_pipeline.fixtures
instead of external APIs or local document stores. They are exposed
through an in-process MCP server so subagents can exercise realistic tool
calls while keeping results repeatable across demos and benchmarks.
"""
from __future__ import annotations

import asyncio
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

from research_pipeline.fixtures import ARTICLES, DOCUMENTS, KNOWN_TOPIC_IDS, TIMEOUT_TOPICS


def _topic_enum_schema(description: str) -> dict[str, Any]:
    """
    Build a JSON Schema that restricts topic_id to known fixture IDs.

    The enum keeps LLM-generated tool calls aligned with the fixture
    registry, preventing paraphrased topic names from bypassing the
    deterministic scenarios.
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
        # Simulate a timeout deterministically by topic_id instead of
        # using randomness or a real network race. Returning is_error=True
        # gives the subagent a structured tool failure to report while
        # preserving a stable, readable error message.
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


# Both tools share the same fixture-backed data domain, so a single
# in-process MCP server keeps registration and lifecycle management simple.
research_tools_server = create_sdk_mcp_server(
    name="research_tools",
    version="1.0.0",
    tools=[search_web, fetch_documents],
)

# Fully-qualified tool names used by allowed_tools and AgentDefinition.tools.
# Centralizing them prevents drift if the MCP server or tool names change.
SEARCH_WEB_TOOL = "mcp__research_tools__search_web"
FETCH_DOCUMENTS_TOOL = "mcp__research_tools__fetch_documents"
