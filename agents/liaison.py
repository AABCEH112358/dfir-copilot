"""DFIR-Liaison agent — the single human-facing point of contact in a DFIR room.

Built on the Band SDK 1.0.0 (import name ``band``, NOT ``thenvoi``). The Liaison
runs a three-phase workflow: INTAKE (diagnose + issue a collection plan),
COLLECTION COORDINATION (acknowledge artifacts, handle pushback, hand off to the
Classifier), and REPORT-OUT (draft the human-readable report after the Captain's
verdict).

Run it with::

    python agents/liaison.py

Reference architecture: https://www.band.ai/hacker-guide
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from band import Agent, AdapterFeatures, Emit
from band.adapters.gemini import GeminiAdapter

# Make the project root importable so ``lib`` resolves when this file is run
# directly as ``python agents/liaison.py``.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lib import audit_trail, case_brief, evidence_tools  # noqa: E402
from lib.agent_credentials import load_credentials  # noqa: E402

logger = logging.getLogger("dfir.liaison")

AGENT_KEY = "liaison"
AGENT_DISPLAY_NAME = "DFIR-Liaison"
OUTPUTS_DIR = PROJECT_ROOT / "data" / "outputs"


# ---------------------------------------------------------------------------
# System prompt (full, load-bearing — do not abbreviate)
# ---------------------------------------------------------------------------

LIAISON_SYSTEM_PROMPT = """\
# Identity
You are DFIR-Liaison, the single point of contact between human investigators and \
the specialist forensic agents in this room. The human is your only conversational \
partner from outside the agent team.

# Tone
Professional, calm, plainspoken. Never patronizing — the human may not be technical \
but is intelligent. Use plain English over jargon; when a technical term is \
unavoidable, define it parenthetically (for example, "EDR (the endpoint security \
tool that flags suspicious activity)").

# Load-Bearing Guardrail
You answer questions about procedure, definitions, MITRE codes, and regulatory \
implications in general terms. You DO NOT speculate about in-flight findings. If the \
human asks "what did the attacker do" before the Captain has issued a verdict, \
respond: "The specialists are still working on the determination. I will return to \
you with their verdict, not speculate ahead of it."

# Your Three Phases

## PHASE 1 — INTAKE
The human arrives with a panicked, plain-language description of an incident. You must:
1. Read the scenario for context (use your scenario-brief tool with the case_id).
2. Produce an INTAKE SUMMARY: a short, calm diagnosis of the likely incident type in \
plain language.
3. Produce a FOUR-PART COLLECTION PLAN. Every artifact you need must list four things:
   - plain_language: what this is, in words the human understands
   - where_to_find_it: which system, log, or location it lives in
   - how_to_retrieve: the concrete steps to pull it safely
   - where_to_drop: where to upload/hand off the artifact
4. Post the collection plan to the room as a Markdown table with EXACTLY these columns:

   | Plain-Language | Where | How | Drop Location |

5. Write and post the case_brief.md (use your write-case-brief tool), then record the \
audit events CASE_OPENED and COLLECTION_PLAN_ISSUED (use your audit tool).

## PHASE 2 — COLLECTION COORDINATION
The human reports artifacts as they upload them (in the demo they type things like \
"uploaded ransom_note"). For each one:
- Acknowledge it warmly and briefly.
- Record an EVIDENCE_RECEIVED audit event for that item (one per artifact).
- Handle pushback gracefully (see examples below).
When collection is complete, append an update to the case_brief and then @mention the \
Classifier with the case_id to begin the investigation.

### Pushback handling — three worked examples
1. Human: "We don't have firewall logs, we never set up central logging."
   You: "Understood — that's common. Let's substitute: pull the EDR network-connection \
records and any DNS resolver logs instead; together they cover most of what firewall \
logs would have shown. I'll mark firewall_logs as PENDING and flag the visibility gap \
to the Captain so it's accounted for in the verdict."
2. Human: "I can't image memory, the servers are already back in production."
   You: "Okay — memory captures aren't possible once a host is rebooted, so we won't \
chase that. I'll mark memory_artifacts as UNAVAILABLE, note the limitation, and lean \
harder on disk and log evidence. I'll let the Captain know this narrows what we can \
say about in-memory credential theft."
3. Human: "The ransom note is gone, IT already wiped the desktops."
   You: "No problem — if anyone screenshotted it or it's quarantined in the EDR \
console, that works just as well. I'll mark ransom_note as PENDING pending those \
sources, propose the EDR quarantine as the alternate location, and flag to the \
Captain that family attribution may rest on other indicators."
In every case: propose an alternative, mark the item PENDING or UNAVAILABLE, and flag \
the scope limitation to the Captain.

## PHASE 3 — REPORT-OUT
Only AFTER the Captain posts a CaptainVerdict (see docs/AGENT_CONTRACTS.md) do you \
draft the LiaisonReport — a human-readable Markdown document with these sections:
Summary for the Investigator | What Happened (plain language) | MITRE Mapping with \
Explanations | Evidence Catalog | Recommended Next Steps | Regulatory Clocks | \
Chain of Custody.
Post it in the room, save it with your save-report tool (which records a \
REPORT_DRAFTED audit event), and then answer the human's follow-up questions about \
MITRE codes, regulatory timelines, and procedure — strictly within what the Captain \
verified. Never invent findings.

# Audit Discipline (mandatory)
You MUST record audit events for: CASE_OPENED (on open), COLLECTION_PLAN_ISSUED \
(after issuing the plan), EVIDENCE_RECEIVED (once per artifact reported), and \
REPORT_DRAFTED (when you save the report). The audit chain is tamper-evident and is \
the case's chain of custody.

# Coordination
Use the room's messaging tools to talk to the human and to @mention other agents. \
Only @mention an agent when you need them to act (e.g., the Classifier to start the \
investigation). Keep the human informed in plain language at every step.
"""


# ---------------------------------------------------------------------------
# Per-case helpers
# ---------------------------------------------------------------------------

def _case_dir(case_id: str) -> Path:
    path = OUTPUTS_DIR / case_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _audit_chain(case_id: str) -> audit_trail.AuditChain:
    """Open (or create) the per-case tamper-evident audit chain."""
    return audit_trail.AuditChain(case_id, _case_dir(case_id) / "audit_chain.jsonl")


def _case_brief_path(case_id: str) -> Path:
    return _case_dir(case_id) / "case_brief.md"


# ---------------------------------------------------------------------------
# Tool input models + handlers
#
# Band derives each tool name from the model class name minus the "Input"
# suffix, lowercased (e.g. GetScenarioBriefInput -> "getscenariobrief"). The
# model docstring becomes the tool description the LLM reads.
# ---------------------------------------------------------------------------

class GetScenarioBriefInput(BaseModel):
    """Read the case scenario (incident summary, victim organization, human contact, opening message) for context. Call this first when a case opens."""

    case_id: str = Field(
        ..., description="Case identifier, e.g. 'DFIR-2026-001' or 'case_001_ransomware'."
    )


def get_scenario_brief(args: GetScenarioBriefInput) -> dict:
    return evidence_tools.get_scenario_brief(args.case_id)


class WriteCaseBriefInput(BaseModel):
    """Render and save the global case_brief.md from the scenario plus your intake summary, stamped with the current audit-chain head. Returns the Markdown so you can post it in the room."""

    case_id: str = Field(..., description="Case identifier.")
    intake_summary: str = Field(
        ..., description="Your plain-language diagnosis of the likely incident type."
    )
    phase: str = Field(
        "INTAKE",
        description="Case phase: INTAKE | COLLECTION | INVESTIGATION | VERDICT | REPORT.",
    )


def write_case_brief(args: WriteCaseBriefInput) -> dict:
    scenario = evidence_tools.get_scenario_brief(args.case_id)
    head = _audit_chain(args.case_id).head_hash()
    markdown = case_brief.render_case_brief(
        args.case_id,
        scenario,
        intake_summary=args.intake_summary,
        phase=args.phase,
        audit_chain_head=head,
    )
    path = _case_brief_path(args.case_id)
    path.write_text(markdown, encoding="utf-8")
    return {"case_brief_md": markdown, "path": str(path)}


class AppendCaseBriefUpdateInput(BaseModel):
    """Append a timestamped update section to the existing case_brief.md. Use when collection completes or when the Captain re-scopes the investigation."""

    case_id: str = Field(..., description="Case identifier.")
    update_section: str = Field(..., description="Short title for the update.")
    update_content: str = Field(..., description="The update body, in plain language.")


def append_case_brief_update(args: AppendCaseBriefUpdateInput) -> dict:
    path = _case_brief_path(args.case_id)
    case_brief.append_to_case_brief(path, args.update_section, args.update_content)
    return {"status": "appended", "path": str(path)}


class RecordAuditEventInput(BaseModel):
    """Append an event to this case's tamper-evident audit chain and return the new head hash. You MUST call this for CASE_OPENED, COLLECTION_PLAN_ISSUED, EVIDENCE_RECEIVED (once per artifact), and REPORT_DRAFTED."""

    case_id: str = Field(..., description="Case identifier.")
    event_type: str = Field(
        ...,
        description=(
            "One of: CASE_OPENED, COLLECTION_PLAN_ISSUED, EVIDENCE_RECEIVED, "
            "EVIDENCE_CLASSIFIED, SPECIALIST_FINDING, SPECIALIST_CHALLENGE, "
            "CAPTAIN_REDIRECT, CAPTAIN_VERDICT, REPORT_DRAFTED, CASE_SEALED."
        ),
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Event-specific details (e.g. {'artifact': 'ransom_note'}).",
    )


def record_audit_event(args: RecordAuditEventInput) -> dict:
    chain = _audit_chain(args.case_id)
    event_hash = chain.append(args.event_type, AGENT_DISPLAY_NAME, args.payload)
    return {"event_type": args.event_type, "hash": event_hash, "head": chain.head_hash()}


class SaveLiaisonReportInput(BaseModel):
    """Save the final human-readable LiaisonReport Markdown to data/outputs/{case_id}/liaison_report.md and record a REPORT_DRAFTED audit event. Call only AFTER the Captain has posted a verdict."""

    case_id: str = Field(..., description="Case identifier.")
    report_md: str = Field(..., description="The full LiaisonReport Markdown document.")


def save_liaison_report(args: SaveLiaisonReportInput) -> dict:
    path = _case_dir(args.case_id) / "liaison_report.md"
    path.write_text(args.report_md, encoding="utf-8")
    chain = _audit_chain(args.case_id)
    event_hash = chain.append(
        "REPORT_DRAFTED", AGENT_DISPLAY_NAME, {"report_path": str(path)}
    )
    return {"path": str(path), "hash": event_hash, "head": chain.head_hash()}


LIAISON_TOOLS = [
    (GetScenarioBriefInput, get_scenario_brief),
    (WriteCaseBriefInput, write_case_brief),
    (AppendCaseBriefUpdateInput, append_case_brief_update),
    (RecordAuditEventInput, record_audit_event),
    (SaveLiaisonReportInput, save_liaison_report),
]


# ---------------------------------------------------------------------------
# Credentials + agent wiring
# ---------------------------------------------------------------------------

def _load_liaison_credentials() -> tuple[str, str]:
    """Resolve (agent_id, api_key) for the Liaison.

    Reads the agent_id from ``agent_config.yaml['agents']['liaison']`` and the API
    key from the env var named by that block's ``api_key_env`` (``LIAISON_API_KEY``),
    falling back to ``BAND_API_KEY`` with a warning. Delegates to the shared
    ``lib.agent_credentials.load_credentials`` helper used by all DFIR agents.
    """
    return load_credentials(AGENT_KEY, config_path=PROJECT_ROOT / "agent_config.yaml")


def build_adapter() -> GeminiAdapter:
    """Construct the Gemini adapter for the Liaison (no network I/O)."""
    return GeminiAdapter(
        model="gemini-2.5-flash",
        provider_key=os.environ.get("GEMINI_API_KEY"),
        prompt=LIAISON_SYSTEM_PROMPT,
        temperature=0.4,
        max_output_tokens=2048,
        additional_tools=LIAISON_TOOLS,
        # Surface tool calls/results into the room as execution events.
        features=AdapterFeatures(emit=frozenset({Emit.EXECUTION})),
    )


async def run_agent() -> None:
    """Wire up the Liaison and run until interrupted."""
    load_dotenv(PROJECT_ROOT / ".env")
    logging.basicConfig(level=logging.INFO)

    adapter = build_adapter()
    agent_id, api_key = _load_liaison_credentials()
    agent = Agent.create(adapter=adapter, agent_id=agent_id, api_key=api_key)

    logger.info("%s is running. Press Ctrl+C to stop.", AGENT_DISPLAY_NAME)
    await agent.run()


if __name__ == "__main__":
    asyncio.run(run_agent())
