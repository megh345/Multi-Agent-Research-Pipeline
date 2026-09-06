"""
verification.py - automated, deterministic checks on subagent output.

WHAT: verify_findings_have_sources() parses a subagent's raw JSON result
and asserts every finding carries all five required fields, non-empty,
returning typed Finding objects. classify_coverage() applies a simple,
code-level (not LLM-judged) rule for whether a topic ended up
WELL-SUPPORTED / LIMITED COVERAGE / NOT COVERED.

WHY this has to be code, not another LLM call grading the first LLM's
output: Task 4.2 explicitly asks for "a verification function that
asserts no claim in the output is missing its source." An assertion
implies a deterministic pass/fail a test suite could run on every commit
- an LLM judge is itself non-deterministic and would just move the "did
this actually happen" question one level up without answering it.

EXAM TASK: Task 4.2 - deterministic verification of structured output.

ANTI-PATTERN: eyeballing the synthesizer's Markdown report to see if
attribution "looks present". Markdown is exactly the free-form format
Task 4.2 says not to trust for this - a missing source_url on one claim
in a 40-line report is easy to miss by reading, trivial to catch by
asserting against the structured JSON before synthesis ever happens.
"""
from __future__ import annotations

import json
from typing import Any

from research_pipeline.schemas import REQUIRED_FINDING_FIELDS, CoverageLevel, Finding


class MissingSourceError(AssertionError):
    """Raised when a finding is missing one or more required attribution
    fields, or when a subagent's output isn't valid JSON at all (which
    itself violates the JSON-only contract every subagent prompt states
    in agents_config.py)."""


def verify_findings_have_sources(raw_json_result: str, *, subagent_name: str) -> list[Finding]:
    """
    Parses a subagent's raw JSON text - the
    `{"status": "ok", "findings": [...]}` or
    `{"status": "error", "failure": {...}}` contract defined in
    agents_config.py - and asserts every finding present has all
    REQUIRED_FINDING_FIELDS, non-empty.

    Returns the findings that passed as typed Finding objects: for
    status="ok" these are `findings`; for status="error" these are
    `failure.partial_results`, so partial coverage can still be verified
    and used downstream even when the primary call failed.

    Raises MissingSourceError on the first violation found, naming
    exactly which field, on which claim, from which subagent - because
    "verification failed" alone isn't actionable inside study material
    you're trying to read and learn from.
    """
    try:
        payload = json.loads(raw_json_result)
    except json.JSONDecodeError as e:
        raise MissingSourceError(
            f"{subagent_name} did not return valid JSON (violates the "
            f"JSON-only contract in agents_config.py): {e}"
        ) from e

    if payload.get("status") == "error":
        raw_findings = payload.get("failure", {}).get("partial_results", [])
    else:
        raw_findings = payload.get("findings", [])

    findings: list[Finding] = []
    for i, raw in enumerate(raw_findings):
        for field_name in REQUIRED_FINDING_FIELDS:
            value = raw.get(field_name)
            if not value or not str(value).strip():
                raise MissingSourceError(
                    f"{subagent_name} finding #{i} "
                    f"({raw.get('claim', '<no claim text>')!r}) is missing "
                    f"required field '{field_name}'."
                )
        findings.append(Finding(**{k: raw[k] for k in REQUIRED_FINDING_FIELDS}))
    return findings


def classify_coverage(
    *, corroborating_finding_count: int, failure_present: bool
) -> CoverageLevel:
    """
    WHAT: A deliberately simple, deterministic rule - not an LLM
    judgment - for how confident a report section should be about a
    given claim/topic, based only on how many independent findings
    support it.

    WHY code, not the synthesizer's own say-so: Task 5.1 requires the
    pipeline (not the LLM being studied) to annotate coverage gaps, so
    this classification stays independently checkable even if a future
    prompt change made the synthesizer sound more confident than the
    underlying evidence supports.
    """
    if corroborating_finding_count == 0:
        return "NOT COVERED"
    if failure_present or corroborating_finding_count == 1:
        return "LIMITED COVERAGE"
    return "WELL-SUPPORTED"
