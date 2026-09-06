"""
Deterministic verification utilities for subagent output.

verify_findings_have_sources() parses a subagent's raw JSON result and
asserts that every finding includes the required attribution fields.
classify_coverage() provides a simple code-level coverage label based on
finding count and retrieval failures.

Keeping these checks deterministic makes attribution failures suitable
for automated tests rather than relying on manual review of a generated
Markdown report.
"""
from __future__ import annotations

import json
from typing import Any

from research_pipeline.schemas import REQUIRED_FINDING_FIELDS, CoverageLevel, Finding


class MissingSourceError(AssertionError):
    """Raised when a subagent result is invalid or missing attribution."""


def verify_findings_have_sources(raw_json_result: str, *, subagent_name: str) -> list[Finding]:
    """
    Parse a subagent result and validate all available findings.

    Successful results validate `findings`; error results validate
    `failure.partial_results` so partial evidence can still be used
    downstream. The first missing field raises MissingSourceError with
    the subagent name, claim text, and field name.
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
    Classify evidence coverage using deterministic pipeline metadata.

    A topic with no findings is not covered. A topic with one finding or
    a retrieval failure has limited coverage. Multiple corroborating
    findings without a failure are treated as well supported.
    """
    if corroborating_finding_count == 0:
        return "NOT COVERED"
    if failure_present or corroborating_finding_count == 1:
        return "LIMITED COVERAGE"
    return "WELL-SUPPORTED"
