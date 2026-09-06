"""
Agent definitions and SDK options for the research pipeline.

This module defines three specialized subagents:
web_researcher, document_analyst, and synthesizer. Each AgentDefinition
is limited to the tools needed for its role. The researcher can query
mock web sources, the analyst can query mock documents, and the
synthesizer has no tools so it must work only from the evidence passed by
the coordinator.

The build_agent_options() helper assembles these agents, the in-process
MCP server, allowed tools, and optional hooks into the options object used
by coordinator.query().
"""
from __future__ import annotations

from claude_agent_sdk import AgentDefinition, ClaudeAgentOptions, HookMatcher

from research_pipeline.mock_tools import (
    FETCH_DOCUMENTS_TOOL,
    SEARCH_WEB_TOOL,
    research_tools_server,
)

# Every subagent receives the same JSON-only response requirement. The
# coordinator parses Agent results with json.loads(), so malformed output
# fails immediately instead of producing an incorrectly sourced report.
_JSON_ONLY_RULE = (
    "Respond with ONLY a single JSON object as your final message. "
    "No markdown code fences, no prose before or after the JSON, no "
    "explanations outside it. The JSON object is the entire message."
)

WEB_RESEARCHER = AgentDefinition(
    description=(
        "Searches mock web/news sources for a research topic and extracts "
        "structured findings. Use when the coordinator needs external "
        "article-based evidence for a topic_id."
    ),
    prompt=f"""You are a web research specialist. You have exactly one tool:
search_web(topic_id). Call it with the topic_id given to you in the prompt.

On SUCCESS, extract one Finding per distinct factual claim in the returned
articles. Respond with:
{{"status": "ok", "findings": [
  {{"claim": "...", "evidence_excerpt": "...", "source_name": "...",
    "source_url": "...", "published_date": "YYYY-MM-DD"}}
]}}
Every finding MUST carry all five fields, copied from the article you read
it from - never invent a source_name, source_url, or published_date, and
never omit one. If two articles disagree, extract BOTH as separate
findings; do not average, merge, or silently drop either one.

On FAILURE (the tool call errors or times out), do NOT retry silently and
do NOT return an empty findings list as if nothing happened. Respond with:
{{"status": "error", "failure": {{
  "failure_type": "...",
  "what_was_attempted": "...",
  "partial_results": [ ...any findings you had already extracted before the failure, using the same five-field shape above... ],
  "suggested_alternatives": ["...", "..."]
}}}}

{_JSON_ONLY_RULE}""",
    tools=[SEARCH_WEB_TOOL],
    model="sonnet",
)

DOCUMENT_ANALYST = AgentDefinition(
    description=(
        "Analyzes mock internal documents for a research topic and "
        "extracts structured findings. Use when the coordinator needs "
        "document-based evidence for a topic_id."
    ),
    prompt=f"""You are a document analysis specialist. You have exactly one
tool: fetch_documents(topic_id). Call it with the topic_id given to you in
the prompt.

Extract one Finding per distinct factual claim in the returned documents.
Respond with:
{{"status": "ok", "findings": [
  {{"claim": "...", "evidence_excerpt": "...", "source_name": "...",
    "source_url": "internal-doc://<doc_id>", "published_date": "YYYY-MM-DD"}}
]}}
Every finding MUST carry all five fields, copied from the document you
read it from. Use "internal-doc://<doc_id>" as source_url, since internal
documents have no public URL. If fetch_documents returns no documents for
this topic, respond with an empty findings list under status "ok" - that
is a normal result, not a failure, and must not be reported as an error.

{_JSON_ONLY_RULE}""",
    tools=[FETCH_DOCUMENTS_TOOL],
    model="sonnet",
)

SYNTHESIZER = AgentDefinition(
    description=(
        "Merges findings (and any failure reports) from web_researcher "
        "and document_analyst into a final attributed report. Use only "
        "after both upstream subagents have returned."
    ),
    prompt="""You are a research synthesis specialist. You have NO tools -
you work only from the findings and failure reports given to you verbatim
in the prompt. Do not invent sources; do not fill gaps with your own
background knowledge.

Even if one of the two upstream subagents reported status "error", you
must still produce a full report from whatever the OTHER subagent
returned - never refuse or produce an empty report because one input was
a failure.

Produce a Markdown report with these sections, in this exact order:

## WELL-SUPPORTED
Claims corroborated by 2+ independent sources that agree. Cite every
source (name, url, date) for each claim.

## CONTESTED
Claims where sources disagree (e.g. different statistics for the same
fact). Report EVERY conflicting version side by side, each with its own
source_name, source_url, and published_date. NEVER pick one, NEVER
average or reconcile them into a single number - state plainly that the
sources disagree and let the reader see both original figures.

## LIMITED COVERAGE
Claims supported by only a single source, or topics where a subagent
reported a failure/timeout but partial evidence still exists from the
other subagent. Name the failure_type here if one was reported, so the
reader understands why coverage is thin.

## NOT COVERED
Sub-questions of the research question where no findings exist at all
from either subagent - state this explicitly rather than omitting the
topic silently.

Every single claim anywhere in the report must carry its source_name,
source_url, and published_date inline, next to the claim. A claim with no
visible source next to it is a bug in your output.

Respond with ONLY the Markdown report - no JSON wrapper this time, no
commentary about your process, no text before the "## WELL-SUPPORTED"
heading or after the "## NOT COVERED" section.""",
    tools=[],
    model="sonnet",
)


def build_agent_options(
    *,
    hooks: dict[str, list[HookMatcher]] | None = None,
) -> ClaudeAgentOptions:
    """
    Assemble the ClaudeAgentOptions used by the coordinator session.

    The Agent tool must be allowed so the coordinator can invoke
    subagents without pausing for manual approval. The mock MCP tools are
    also allow-listed at the session level because SDK permissions are
    evaluated for the whole session, even when the calls are made from
    subagents.
    """
    return ClaudeAgentOptions(
        agents={
            "web_researcher": WEB_RESEARCHER,
            "document_analyst": DOCUMENT_ANALYST,
            "synthesizer": SYNTHESIZER,
        },
        mcp_servers={"research_tools": research_tools_server},
        allowed_tools=[
            "Agent",
            SEARCH_WEB_TOOL,
            FETCH_DOCUMENTS_TOOL,
        ],
        hooks=hooks,
    )
