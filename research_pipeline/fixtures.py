"""
fixtures.py - mock data sources for the research pipeline demo.

WHAT: Fake articles and internal documents, grouped by a fixed set of
`topic_id`s, plus a registry of which topic_ids should simulate a search
timeout. This is the only place "the internet" and "the document store"
exist in this project - everything downstream (mock_tools.py, the
subagents, the demo scripts) reads from here.

WHY: the exercise requires "deterministic, repeatable behaviour... to
trigger timeouts and conflicts on demand." A real web search tool returns
different results every run and can't be told to fail on command.
Centralizing fixed, hand-authored data means the same topic_id always
produces the same articles/documents (or the same simulated failure),
every run, with zero network calls - and fixing a typo in one place
updates every consumer.

EXAM TASK: this file is the "mock data sources, not real web search"
requirement, and the setup for Tasks 5.1 (error propagation) and 5.2
(conflicting sources).

ANTI-PATTERN: scattering literal source strings ("EVs hit 18% in
2024...") inside subagent prompts or inline in mock_tools.py instead of
here. That would make it impossible to point at "the fixture" as a
single reviewable source of truth, and any future addition (a fourth
topic, a second timeout case) would mean hunting through unrelated
files.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Topic 1: ai_regulation_eu
# Clean, well-covered topic: multiple corroborating sources, no conflicts,
# no failures. Used for the parallel-spawning benchmark and the baseline
# structured-output/verification demo (Tasks 1 and 3).
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Topic 2: grid_battery_storage_2026
# TIMEOUT DEMO topic (Task 5.1). search_web() always simulates a timeout
# for this topic_id; fetch_documents() still succeeds, so the coordinator
# has to proceed on partial (document-only) coverage and say so in the
# final report instead of silently dropping the gap.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Topic 3: global_ev_adoption_rate
# CONFLICTING SOURCES demo topic (Task 5.2). Two real-looking articles give
# different EV market-share numbers for the same year, from different
# publishers on different dates. Both must survive into the final report
# with attribution - never merged or averaged into a single number.
# ---------------------------------------------------------------------------

ARTICLES: dict[str, list[dict[str, str]]] = {
    "ai_regulation_eu": [
        {
            "title": "EU AI Act Enters Into Force",
            "source_name": "TechPolicy Daily",
            "source_url": "https://techpolicydaily.example/eu-ai-act-force",
            "published_date": "2024-08-01",
            "excerpt": (
                "The EU AI Act formally entered into force on August 1, 2024, "
                "establishing a risk-based framework for regulating artificial "
                "intelligence systems across the European Union."
            ),
        },
        {
            "title": "High-Risk AI Systems Face Strict Compliance Deadlines",
            "source_name": "Brussels Tech Wire",
            "source_url": "https://brusselstechwire.example/compliance-deadlines",
            "published_date": "2025-02-15",
            "excerpt": (
                "Providers of high-risk AI systems under the EU AI Act must "
                "complete conformity assessments by August 2026, according to "
                "the phased implementation timeline."
            ),
        },
    ],
    "grid_battery_storage_2026": [
        {
            "title": "Battery Storage Investment Surges",
            "source_name": "GridTech Weekly",
            "source_url": "https://gridtechweekly.example/storage-investment-surge",
            "published_date": "2026-02-01",
            # NOTE: this article exists in the fixture set to establish that
            # data *existed* and was simply unreachable due to the simulated
            # timeout below - search_web() never actually returns it. Kept
            # here so the demo can show "attempted but failed" rather than
            # "nothing existed to find".
            "excerpt": (
                "Utility-scale battery storage investment reached a record "
                "$41 billion in the past twelve months, per preliminary "
                "industry tracking data."
            ),
        },
    ],
    "global_ev_adoption_rate": [
        {
            "title": "IEA: EVs Reached 18% of Global Car Sales in 2024",
            "source_name": "International Energy Agency - Global EV Outlook",
            "source_url": "https://iea.example/global-ev-outlook-2025",
            "published_date": "2025-04-22",
            "excerpt": (
                "Electric vehicles accounted for 18% of new car sales "
                "worldwide in 2024, according to the IEA's Global EV Outlook "
                "2025 report, up from 14% the prior year."
            ),
        },
        {
            "title": "Industry Group: EV Share Hit 22% Last Year",
            "source_name": "Global Battery & Energy Vehicle Alliance (BEVA)",
            "source_url": "https://beva.example/2025-market-review",
            "published_date": "2025-06-10",
            "excerpt": (
                "The Global Battery & Energy Vehicle Alliance's 2025 market "
                "review put electric vehicles at 22% of worldwide new car "
                "sales in 2024, citing a broader definition of 'electric' "
                "that includes plug-in hybrids with over 50km electric range."
            ),
        },
    ],
}

DOCUMENTS: dict[str, list[dict[str, str]]] = {
    "ai_regulation_eu": [
        {
            "doc_id": "eu-ai-act-summary-2024",
            "title": "Regulation (EU) 2024/1689 - Executive Summary",
            "source_name": "European Commission (internal briefing)",
            "published_date": "2024-07-12",
            "body": (
                "This regulation classifies AI systems into four risk tiers: "
                "unacceptable, high, limited, and minimal risk. "
                "Unacceptable-risk systems, including social scoring by "
                "public authorities, are prohibited outright."
            ),
        },
    ],
    "grid_battery_storage_2026": [
        {
            "doc_id": "battery-storage-outlook-2026",
            "title": "Grid-Scale Battery Storage Capacity Outlook",
            "source_name": "Internal Energy Research Archive",
            "published_date": "2026-01-10",
            "body": (
                "Global grid-scale battery storage capacity is projected to "
                "exceed 520 GWh by the end of 2026, driven primarily by "
                "utility-scale lithium-iron-phosphate deployments in China "
                "and the United States."
            ),
        },
        {
            "doc_id": "storage-safety-standards-2025",
            "title": "Battery Storage Safety Standards Review",
            "source_name": "Internal Energy Research Archive",
            "published_date": "2025-11-03",
            "body": (
                "Revised UL 9540A thermal runaway testing standards, adopted "
                "industry-wide in late 2025, have reduced reported "
                "grid-storage fire incidents by an estimated 40% "
                "year-over-year."
            ),
        },
    ],
    "global_ev_adoption_rate": [
        {
            "doc_id": "ev-stat-methodology-note",
            "title": "Note on EV Market Share Methodology Differences",
            "source_name": "Internal Energy Research Archive",
            "published_date": "2025-07-01",
            "body": (
                "Discrepancies between IEA and industry-alliance EV adoption "
                "figures typically stem from differing definitions of "
                "'electric vehicle' (BEV-only vs. BEV+PHEV) and differing "
                "base datasets (national registration data vs. "
                "manufacturer-reported sales)."
            ),
        },
    ],
}

# Task 5.1: topic_ids for which search_web() deterministically simulates a
# timeout, regardless of how many times or in what order it's called.
TIMEOUT_TOPICS: frozenset[str] = frozenset({"grid_battery_storage_2026"})

# The fixed vocabulary mock_tools.py constrains the `topic_id` tool argument
# to (see mock_tools.py's _topic_enum_schema). A subagent literally cannot
# pass a topic_id we haven't defined data for.
KNOWN_TOPIC_IDS: frozenset[str] = frozenset(ARTICLES) | frozenset(DOCUMENTS)
