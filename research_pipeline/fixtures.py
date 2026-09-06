"""
Deterministic source fixtures used by the research pipeline.

The pipeline uses fixed article and document collections instead of live
network calls so demos, benchmarks, and verification checks are
repeatable. Each topic ID maps to known evidence, and selected topics can
simulate predictable failure modes such as search timeouts or conflicting
source claims.

Keeping fixture data centralized gives the mock tools, subagents, and
demo scripts a single source of truth. New topics or failure scenarios
can be added here without changing orchestration logic.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Topic 1: ai_regulation_eu
# Well-covered topic with corroborating sources and no simulated failures.
# Used by the parallel benchmark and structured-output verification flow.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Topic 2: grid_battery_storage_2026
# Timeout scenario. search_web() always returns a simulated timeout for
# this topic_id, while fetch_documents() still succeeds. The coordinator
# should continue with document-only evidence and preserve that limitation
# in the final report.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Topic 3: global_ev_adoption_rate
# Conflicting-source scenario. Independent sources report different EV
# market-share figures for the same year. Both claims should remain
# attributed separately in the final report.
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
            # This article documents that relevant web evidence exists, even
            # though search_web() intentionally withholds it for the timeout
            # scenario. That distinction lets the final report distinguish a
            # retrieval failure from an empty result set.
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

# Topic IDs for which search_web() deterministically simulates a timeout.
TIMEOUT_TOPICS: frozenset[str] = frozenset({"grid_battery_storage_2026"})

# The mock tool schema constrains `topic_id` to this fixed vocabulary, so
# subagents can only request fixture-backed topics.
KNOWN_TOPIC_IDS: frozenset[str] = frozenset(ARTICLES) | frozenset(DOCUMENTS)
