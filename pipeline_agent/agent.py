"""
Pipeline Agent — 3-stage SequentialAgent: fetch → analyze → report.

Demonstrates:
  F10 — SequentialAgent: deterministic assembly-line orchestration
  F13 — Session state: each stage reads and writes shared state keys

Stage 1 (fetch_agent):   Fetches raw information on a topic.
Stage 2 (analyze_agent): Analyses the raw information for key insights.
Stage 3 (report_agent):  Formats insights into a structured report.

The ``root_agent`` is the SequentialAgent itself.  Each stage is an
LlmAgent that reads previous-stage output from ``context.state``.

Usage::

    adk run ./pipeline_agent/
    adk web ./pipeline_agent/
"""

from __future__ import annotations

from dotenv import load_dotenv
from google.adk.agents import LlmAgent, SequentialAgent

from shared.config import settings

load_dotenv()

# ── Stage 1: Fetch ────────────────────────────────────────────────────────────

_FETCH_INSTRUCTION = """
You are the Fetch stage of a research pipeline.

Your job: Given a topic from the user, write a comprehensive summary of
background information on that topic. Include key facts, definitions, and
relevant context.

Store your output in state key: "raw_data"

Format your response as:
TOPIC: <topic>
RAW_DATA: <your comprehensive summary>
"""

fetch_agent = LlmAgent(
    model=settings.GEMINI_MODEL,
    name="fetch_agent",
    description="Stage 1: Fetches and summarises raw information on a topic.",
    instruction=_FETCH_INSTRUCTION,
    output_key="raw_data",  # Store output in session state under this key
)

# ── Stage 2: Analyze ──────────────────────────────────────────────────────────

_ANALYZE_INSTRUCTION = """
You are the Analyze stage of a research pipeline.

Your job: Take the raw_data from the previous stage (available in context)
and identify:
1. The 3-5 most important insights.
2. Any surprising or counterintuitive findings.
3. Key relationships and patterns.

Store your analysis in state key: "analysis"

Format your response as:
INSIGHTS:
1. ...
2. ...
PATTERNS: ...
"""

analyze_agent = LlmAgent(
    model=settings.GEMINI_MODEL,
    name="analyze_agent",
    description="Stage 2: Analyses raw data to extract key insights.",
    instruction=_ANALYZE_INSTRUCTION,
    output_key="analysis",
)

# ── Stage 3: Report ───────────────────────────────────────────────────────────

_REPORT_INSTRUCTION = """
You are the Report stage of a research pipeline.

Your job: Take the analysis from the previous stage and produce a polished,
professional research report.

The report must include:
- Executive Summary (2-3 sentences)
- Key Findings (bullet points)
- Analysis Section (prose)
- Conclusion

Format as proper markdown with headings.
"""

report_agent = LlmAgent(
    model=settings.GEMINI_MODEL,
    name="report_agent",
    description="Stage 3: Formats analysis into a structured markdown report.",
    instruction=_REPORT_INSTRUCTION,
    output_key="final_report",
)

# ── Sequential Pipeline ───────────────────────────────────────────────────────

root_agent = SequentialAgent(
    name="pipeline_agent",
    description=(
        "3-stage research pipeline: (1) Fetch → (2) Analyze → (3) Report. "
        "Run with: adk run ./pipeline_agent/"
    ),
    sub_agents=[fetch_agent, analyze_agent, report_agent],
)
