"""
Shared data contracts for the research pipeline.

Subagents exchange structured findings instead of free-form summaries.
Each finding carries the claim, evidence excerpt, source name, source URL,
and publication date required for downstream attribution checks. The
failure contract preserves partial results and suggested recovery paths
when a source cannot be reached.

Defining these shapes in one module keeps the coordinator, prompts, and
verification logic aligned around the same contract.
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
    """One attributed claim with mandatory source metadata."""

    claim: str
    evidence_excerpt: str
    source_name: str
    source_url: str
    published_date: str  # ISO 8601 (YYYY-MM-DD), kept as str for JSON round-trips.

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class FailureReport:
    """
    Structured failure details returned by a subagent when retrieval
    fails but the pipeline should continue.

    The coordinator uses this payload to distinguish an empty result set
    from an incomplete search, retain any partial findings, and surface
    suggested follow-up actions in the final report.
    """

    failure_type: str
    what_was_attempted: str
    partial_results: list[Finding] = field(default_factory=list)
    suggested_alternatives: list[str] = field(default_factory=list)


CoverageLevel = Literal["WELL-SUPPORTED", "LIMITED COVERAGE", "NOT COVERED"]
