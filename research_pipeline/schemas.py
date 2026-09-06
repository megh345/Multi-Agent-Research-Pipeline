"""
schemas.py - shared data contracts for the research pipeline.

WHAT: Defines the `Finding` structure every subagent must emit, and the
`FailureReport` structure web_researcher must emit when a source is
unreachable (e.g. a simulated timeout).

WHY: Task 3 (structured output) requires every claim to carry
{claim, evidence_excerpt, source_name, source_url, published_date} and
never bare prose. A single shared definition - rather than each agent
prompt independently describing "please return JSON with these fields"
in its own words - means the coordinator, the synthesizer instructions,
and verification.py are all checking the exact same contract. If the
schema only existed as prose inside prompt text, a typo in one prompt
could silently diverge from what verification.py actually checks for.

EXAM TASK: Task 4.2/3 - structured output with mandatory metadata fields.

ANTI-PATTERN: returning findings as free-form prose ("Sources suggest EV
adoption is climbing, per IEA and industry data...") is exactly what this
schema rules out. Prose collapses attribution: a reader can no longer
tell which sentence came from which source, dated when - contested
claims quietly get merged into a false consensus.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

REQUIRED_FINDING_FIELDS: tuple[str, ...] = (
    "claim",
    "evidence_excerpt",
    "source_name",
    "source_url",
    "published_date",
)


@dataclass(frozen=True)
class Finding:
    """One attributed claim. Every field is required - there is no
    optional/nullable variant, on purpose, so a missing field is always
    a bug rather than a valid "unknown source" state."""

    claim: str
    evidence_excerpt: str
    source_name: str
    source_url: str
    published_date: str  # ISO 8601 (YYYY-MM-DD), kept as str so subagent
    # JSON round-trips without needing a date parser in the hot path.

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class FailureReport:
    """
    WHAT: Structured error contract a subagent returns instead of
    crashing, retrying silently, or quietly returning an empty findings
    list when a tool call fails (e.g. a simulated search timeout).

    WHY: Task 5.1 (error propagation) requires the coordinator to receive
    enough structured detail to know coverage is incomplete AND to decide
    whether to proceed, retry, or substitute another subagent. A bare
    exception string can't support that decision - it doesn't say what
    was already gathered before the failure, or what to try next.

    EXAM TASK: Task 5.1 - structured error propagation with partial
    results and suggested alternatives.

    ANTI-PATTERN: catching the tool error and returning
    {"status": "ok", "findings": []}. The coordinator (and the final
    report) would then have no way to distinguish "we searched and found
    nothing" from "the search never completed" - those require very
    different report language (NOT COVERED vs. LIMITED COVERAGE with a
    named cause).
    """

    failure_type: str
    what_was_attempted: str
    partial_results: list[Finding] = field(default_factory=list)
    suggested_alternatives: list[str] = field(default_factory=list)


CoverageLevel = Literal["WELL-SUPPORTED", "LIMITED COVERAGE", "NOT COVERED"]
