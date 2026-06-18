"""DFIR-Classifier agent — the evidence routing layer in a DFIR room.

Built on the Band SDK 1.0.0 (import name ``band``, NOT ``thenvoi``). The
Classifier waits for the Liaison to hand off a case, inspects every evidence
category in the bundle, decides which specialist(s) own each category, and posts
a per-specialist briefing packet (via ``case_brief.render_specialist_packet``).
It routes — it does not investigate or interpret evidence beyond what routing
requires.

Run it with::

    python agents/classifier.py

Reference architecture: https://www.band.ai/hacker-guide
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from band import Agent, AdapterFeatures, Emit
from band.adapters.gemini import GeminiAdapter

# Make the project root importable so ``lib`` resolves when this file is run
# directly as ``python agents/classifier.py``.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lib import audit_trail, case_brief, evidence_tools  # noqa: E402
from lib.agent_credentials import load_credentials  # noqa: E402

logger = logging.getLogger("dfir.classifier")

AGENT_KEY = "classifier"
AGENT_DISPLAY_NAME = "DFIR-Classifier"
HOST_SPECIALIST = "DFIR-HostForensics"
NETWORK_SPECIALIST = "DFIR-NetworkForensics"
OUTPUTS_DIR = PROJECT_ROOT / "data" / "outputs"


# ---------------------------------------------------------------------------
# System prompt (full, load-bearing — do not abbreviate)
# ---------------------------------------------------------------------------

CLASSIFIER_SYSTEM_PROMPT = """\
# Identity
You are DFIR-Classifier, the routing layer for evidence. You do not investigate or \
interpret evidence beyond what's needed to route it. You produce briefings for the \
specialists, not findings.

# When You Act
You wait for the Liaison to hand off a case with a message like \
"@DFIR-Classifier begin investigation for {case_id}". When you see it, start routing.

# Your Routing Procedure
1. Call your list-categories tool with the case_id to see every evidence category in \
the bundle.
2. For each category, call your get-evidence tool to glance at its shape — only enough \
to confirm routing, never to interpret findings.
3. Decide ownership using the routing rules below.
4. For each specialist, produce ONE briefing packet with your write-packet tool, which \
renders a structured Markdown handoff via render_specialist_packet. Post each packet to \
the room as an @mention to that specialist (@DFIR-HostForensics or @DFIR-NetworkForensics).
5. Record an EVIDENCE_CLASSIFIED audit event for EVERY category you route (use your \
audit tool), noting which specialist(s) received it.

# Routing Rules (deterministic — follow exactly)
- Host-related categories go to DFIR-HostForensics:
  server_logs, av_alerts, encrypted_sample, usb_logs, file_access, print_logs,
  db_audit, deployments, dependencies, ci_builds, binary_hash
  (also treat host/endpoint/memory/disk artifacts like edr_alerts and memory_artifacts
  as host-related when present).
- Network-related categories go to DFIR-NetworkForensics:
  firewall_logs, vpn_logs, network_egress, and customer_reports that describe network
  behavior (also dns_queries and network_traffic when present).
- Cross-cutting categories go to BOTH specialists, each from their own angle:
  hr_records, physical_access, email_metadata, ransom_note, affected_systems,
  customer_impact, fleet_audit, upstream_source.
- If a category is not listed above, route by best fit: clearly host/endpoint evidence
  → HostForensics; clearly network/traffic evidence → NetworkForensics; ambiguous or
  organizational/contextual → both.

# Cross-Reference Requirement (load-bearing)
When a single category is routed to BOTH specialists, the packet to each specialist \
MUST note that the other specialist also has that evidence, so they coordinate instead \
of duplicating work. Populate the "co_specialists" field of each packet with the other \
specialist and the categories they own, and call out shared categories explicitly in \
the focus directive.

# Output Discipline
Always structured. Every briefing goes through your write-packet tool \
(render_specialist_packet) — never freehand a briefing. Your focus_directive should \
tell the specialist what angle to take, not what conclusion to reach. You never post \
findings or interpretations of your own.

# Re-Scoping / Updates
If new evidence arrives mid-investigation (the Liaison collects more, or the Captain \
re-scopes), produce an UPDATE packet for ONLY the affected specialist(s): set is_update \
to true, list only the newly-added or changed categories as the assigned artifacts, and \
record an EVIDENCE_CLASSIFIED audit event for each new/changed category. Do not re-send \
unchanged assignments.

# Audit Discipline (mandatory)
Record an EVIDENCE_CLASSIFIED audit event for every category you route, on both the \
initial pass and any update. The audit chain is the case's chain of custody.
"""


# ---------------------------------------------------------------------------
# Per-case helpers (mirrors liaison.py output layout)
# ---------------------------------------------------------------------------

def _case_dir(case_id: str) -> Path:
    path = OUTPUTS_DIR / case_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _packets_dir(case_id: str) -> Path:
    path = _case_dir(case_id) / "packets"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _audit_chain(case_id: str) -> audit_trail.AuditChain:
    """Open (or create) the per-case tamper-evident audit chain."""
    return audit_trail.AuditChain(case_id, _case_dir(case_id) / "audit_chain.jsonl")


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


# ---------------------------------------------------------------------------
# Tool input models + handlers
#
# Band derives each tool name from the model class name minus the "Input"
# suffix, lowercased (e.g. ListEvidenceCategoriesInput -> "listevidencecategories").
# The model docstring becomes the tool description the LLM reads.
# ---------------------------------------------------------------------------

class ListEvidenceCategoriesInput(BaseModel):
    """List the top-level evidence categories in a case's evidence bundle. Call this first when you begin routing a case."""

    case_id: str = Field(
        ..., description="Case identifier, e.g. 'DFIR-2026-001' or 'case_001_ransomware'."
    )


def list_evidence_categories(args: ListEvidenceCategoriesInput) -> list[str]:
    return evidence_tools.list_evidence_categories(args.case_id)


class GetEvidenceInput(BaseModel):
    """Read one evidence category's contents — only to confirm routing, never to interpret findings."""

    case_id: str = Field(..., description="Case identifier.")
    category: str = Field(..., description="Evidence category name to fetch.")


def get_evidence(args: GetEvidenceInput) -> dict | list:
    return evidence_tools.get_evidence(args.case_id, args.category)


class WriteSpecialistPacketInput(BaseModel):
    """Render and save a structured specialist briefing packet (via render_specialist_packet), and return the Markdown so you can post it as an @mention to the specialist. Use this for both initial routing and updates."""

    case_id: str = Field(..., description="Case identifier.")
    specialist_name: str = Field(
        ...,
        description="Target specialist handle: 'DFIR-HostForensics' or 'DFIR-NetworkForensics'.",
    )
    focus_directive: str = Field(
        ...,
        description="What angle this specialist should take (not a conclusion to reach).",
    )
    assigned_artifacts: list[dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "Categories assigned to this specialist; each item "
            "{'category': str, 'description': str}."
        ),
    )
    co_specialists: list[dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "Other specialists on the case; each item "
            "{'name': str, 'evidence_categories_owned': [str, ...]}. "
            "Required when evidence is shared, so the packet notes who else has it."
        ),
    )
    is_update: bool = Field(
        False,
        description="True for a mid-investigation UPDATE packet (re-scope / new evidence).",
    )


def write_specialist_packet(args: WriteSpecialistPacketInput) -> dict:
    focus = args.focus_directive
    if args.is_update:
        focus = f"[UPDATE — newly added or re-scoped evidence] {focus}"

    markdown = case_brief.render_specialist_packet(
        specialist_name=args.specialist_name,
        case_id=args.case_id,
        assigned_artifacts=args.assigned_artifacts,
        co_specialists=args.co_specialists,
        focus_directive=focus,
    )

    slug = _slug(args.specialist_name)
    if args.is_update:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        filename = f"{slug}_update_{stamp}.md"
    else:
        filename = f"{slug}.md"
    path = _packets_dir(args.case_id) / filename
    path.write_text(markdown, encoding="utf-8")

    return {"packet_md": markdown, "path": str(path), "is_update": args.is_update}


class RecordAuditEventInput(BaseModel):
    """Append an event to this case's tamper-evident audit chain and return the new head hash. You MUST call this with event_type EVIDENCE_CLASSIFIED for every category you route (initial pass and updates)."""

    case_id: str = Field(..., description="Case identifier.")
    event_type: str = Field(
        "EVIDENCE_CLASSIFIED",
        description=(
            "Normally EVIDENCE_CLASSIFIED. One of: CASE_OPENED, "
            "COLLECTION_PLAN_ISSUED, EVIDENCE_RECEIVED, EVIDENCE_CLASSIFIED, "
            "SPECIALIST_FINDING, SPECIALIST_CHALLENGE, CAPTAIN_REDIRECT, "
            "CAPTAIN_VERDICT, REPORT_DRAFTED, CASE_SEALED."
        ),
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Routing details, e.g. "
            "{'category': 'ransom_note', 'routed_to': ['DFIR-HostForensics', "
            "'DFIR-NetworkForensics']}."
        ),
    )


def record_audit_event(args: RecordAuditEventInput) -> dict:
    chain = _audit_chain(args.case_id)
    event_hash = chain.append(args.event_type, AGENT_DISPLAY_NAME, args.payload)
    return {"event_type": args.event_type, "hash": event_hash, "head": chain.head_hash()}


CLASSIFIER_TOOLS = [
    (ListEvidenceCategoriesInput, list_evidence_categories),
    (GetEvidenceInput, get_evidence),
    (WriteSpecialistPacketInput, write_specialist_packet),
    (RecordAuditEventInput, record_audit_event),
]


# ---------------------------------------------------------------------------
# Credentials + agent wiring
# ---------------------------------------------------------------------------

def _load_classifier_credentials() -> tuple[str, str]:
    """Resolve (agent_id, api_key) for the Classifier.

    Reads the agent_id from ``agent_config.yaml['agents']['classifier']`` and the
    API key from the env var named by that block's ``api_key_env``
    (``CLASSIFIER_API_KEY``), via the shared ``lib.agent_credentials`` helper.
    """
    return load_credentials(AGENT_KEY, config_path=PROJECT_ROOT / "agent_config.yaml")


def build_adapter() -> GeminiAdapter:
    """Construct the Gemini adapter for the Classifier (no network I/O)."""
    return GeminiAdapter(
        model="gemini-2.5-flash",
        provider_key=os.environ.get("GEMINI_API_KEY"),
        prompt=CLASSIFIER_SYSTEM_PROMPT,
        temperature=0.2,
        max_output_tokens=1024,
        additional_tools=CLASSIFIER_TOOLS,
        # Surface tool calls/results into the room as execution events.
        features=AdapterFeatures(emit=frozenset({Emit.EXECUTION})),
    )


async def run_agent() -> None:
    """Wire up the Classifier and run until interrupted."""
    load_dotenv(PROJECT_ROOT / ".env")
    logging.basicConfig(level=logging.INFO)

    adapter = build_adapter()
    agent_id, api_key = _load_classifier_credentials()
    agent = Agent.create(adapter=adapter, agent_id=agent_id, api_key=api_key)

    logger.info("%s is running. Press Ctrl+C to stop.", AGENT_DISPLAY_NAME)
    await agent.run()


if __name__ == "__main__":
    asyncio.run(run_agent())
