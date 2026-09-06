"""
agents_config.py - AgentDefinitions for the three research subagents.

WHAT: Defines web_researcher, document_analyst, and synthesizer as real
`AgentDefinition` instances, each scoped to exactly the tools it needs,
plus `build_agent_options()` which assembles the full `ClaudeAgentOptions`
the coordinator passes to `query()`.

WHY: `AgentDefinition.tools` restricts a subagent's toolset (tool
restriction is a first-class SDK feature, not something we bolt on).
web_researcher gets only search_web; document_analyst gets only
fetch_documents; synthesizer gets NO tools at all, because its entire job
is reasoning over findings the coordinator hands it explicitly - it
should never be able to go fetch its own data and quietly bypass the
context-passing contract this project exists to demonstrate.

EXAM TASK: Task 2.1/2.2 - real `AgentDefinition` fields (description,
prompt, tools, model), registered via `ClaudeAgentOptions.agents` and
gated by `allowed_tools` containing "Agent" (the current name of what
the exam guide calls the Task tool - see the note in coordinator.py).

ANTI-PATTERN: giving every subagent every tool "just in case". A
synthesizer with `search_web` access could silently go find its own
extra sources instead of working only from what the coordinator passed
it - defeating the "subagents inherit nothing, context must be explicit"
requirement (Task 2) in a way that's very hard to notice just by reading
the final report.
"""
from __future__ import annotations

from claude_agent_sdk import AgentDefinition, ClaudeAgentOptions, HookMatcher

from research_pipeline.mock_tools import (
    FETCH_DOCUMENTS_TOOL,
    SEARCH_WEB_TOOL,
    research_tools_server,
)

# Every subagent is told the exact JSON contract it must return.
# coordinator.py does `json.loads()` on the Agent tool's result text with
# no fallback parsing, so if a subagent wraps its answer in prose or a
# markdown fence, parsing breaks loudly rather than silently producing a
# malformed report - Task 4.2 (verification) depends on catching that
# early rather than downstream in the synthesized Markdown.
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
    WHAT: Assembles the ClaudeAgentOptions the coordinator's query() call
    needs: the three subagents, the mock-tools MCP server, the allow-list
    that lets Claude invoke them without a manual permission prompt, and
    (optionally) the observability hooks from logging_hooks.py.

    WHY "Agent" must be in allowed_tools: without it, every subagent
    invocation stops the session for manual approval - dead on arrival in
    an unattended demo/benchmark script. The two mcp__research_tools__*
    names must ALSO be allow-listed at this top level even though only
    the subagents call them directly, because permission approval in the
    SDK happens at the session level, not scoped per-subagent.

    EXAM TASK: Task 2.1 - ClaudeAgentOptions wiring: agents + mcp_servers
    + allowed_tools + hooks together in one options object.
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
