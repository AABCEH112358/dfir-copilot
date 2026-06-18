"""Shared foundation for the DFIR specialist agents (Host & Network Forensics).

Both specialists do the same job — receive a packet from the Classifier, read
their assigned evidence, produce a ``StructuredFinding`` (see
``docs/AGENT_CONTRACTS.md``), post it for the Captain, and answer follow-ups —
differing only in domain identity. Keeping the tools, audit discipline, output
layout, and run wiring here guarantees the two agents stay at parity.

Per-case output layout (mirrors liaison.py / classifier.py):
    data/outputs/{case_id}/audit_chain.jsonl   shared tamper-evident chain
    data/outputs/{case_id}/findings/{specialist}-{timestamp}.json
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from band import Agent, AdapterFeatures, Emit
from band.adapters.gemini import GeminiAdapter
from band.runtime.custom_tools import CustomToolDef

from . import audit_trail, evidence_tools
from .agent_credentials import load_credentials

logger = logging.getLogger("dfir.specialist")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = PROJECT_ROOT / "data" / "outputs"
CAPTAIN_HANDLE = "DFIR-Captain"

VALID_CONFIDENCE = {"low", "medium", "high"}


# ---------------------------------------------------------------------------
# Shared system prompt (identity is injected per-agent via compose_prompt)
# ---------------------------------------------------------------------------

# {DOMAIN} is replaced with "host" or "network" so the honesty directive reads
# naturally for each specialist while staying otherwise identical.
SPECIALIST_COMMON_PROMPT = """\
# Your Shared Job
1. You begin when the Classifier @mentions you with a specialist packet describing the \
evidence categories assigned to you.
2. Read your assigned evidence with your get-evidence tool (use search-evidence to find \
specific items). Read only the categories you were assigned.
3. Analyze the evidence and produce a StructuredFinding (schema below). Post it in the \
room and include @DFIR-Captain in the mention list so the Captain can synthesize.
4. Respond to @mentions from the other specialist or the Captain asking follow-ups.
5. NEVER finalize a verdict alone — the Captain owns final synthesis. You report what \
your evidence shows; you do not declare the case's conclusion.

# Method
- Walk your findings in chronological order.
- Cite specific event IDs and timestamps when they are present in the evidence.
- Map observed behaviors to MITRE ATT&CK technique IDs.
- Clearly distinguish what you can CONFIRM from the evidence versus what you SUSPECT, \
and encode that as your confidence level (low | medium | high).

# Honesty About Limits (load-bearing)
If your evidence shows no compromise on the {DOMAIN} side, SAY SO — even when the user \
expects you to find something. The truth in this work often emerges from correlation \
across specialists. Your job is to report what your evidence actually shows, not what \
the narrative wants.

# When Challenged
When the other specialist or the Captain challenges your finding, respond with specific \
evidence references — exact category/key, event IDs, timestamps — not just a restatement \
of your conclusion. If YOU challenge the other specialist, use your challenge tool (it \
records a SPECIALIST_CHALLENGE audit event) and @mention both that specialist and \
@DFIR-Captain.

# StructuredFinding Schema (match docs/AGENT_CONTRACTS.md exactly)
Produce findings via your post-finding tool, which builds and persists this exact shape \
and records a SPECIALIST_FINDING audit event:
{
  "kind": "structured_finding",
  "specialist": "<your handle>",
  "case_id": "<case id>",
  "findings": [
    {
      "summary": "one sentence",
      "evidence_refs": ["category/key from the evidence bundle"],
      "mitre_techniques": ["T1486"],
      "confidence": "low|medium|high"
    }
  ],
  "open_questions": ["what would change your confidence"]
}
evidence_refs use the category/key convention: for list categories use the index (e.g. \
"encrypted_sample/0"), and for keyed categories use the key (e.g. \
"memory_artifacts/FS-CORE-01"). Only reference evidence you were assigned and actually \
read.

# Audit Discipline (mandatory)
Every finding you post is logged as SPECIALIST_FINDING; every challenge you raise is \
logged as SPECIALIST_CHALLENGE. These tool calls maintain the case's tamper-evident \
chain of custody.

# Coordination
Talk in the room. @mention only when you need someone to act: @DFIR-Captain when you \
post a finding, and the other specialist (plus @DFIR-Captain) when you need to correlate \
or challenge.
"""


def compose_prompt(identity: str, domain_word: str) -> str:
    """Combine a specialist's identity block with the shared prompt body."""
    return identity.rstrip() + "\n\n" + SPECIALIST_COMMON_PROMPT.replace(
        "{DOMAIN}", domain_word
    )


# ---------------------------------------------------------------------------
# Per-case helpers
# ---------------------------------------------------------------------------

def _case_dir(case_id: str) -> Path:
    path = OUTPUTS_DIR / case_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _findings_dir(case_id: str) -> Path:
    path = _case_dir(case_id) / "findings"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _audit_chain(case_id: str) -> audit_trail.AuditChain:
    """Open (or create) the per-case tamper-evident audit chain (shared file)."""
    return audit_trail.AuditChain(case_id, _case_dir(case_id) / "audit_chain.jsonl")


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _normalize_finding(raw: dict[str, Any]) -> dict[str, Any]:
    """Coerce one finding dict into the exact StructuredFinding finding shape."""
    refs = raw.get("evidence_refs") or []
    techniques = raw.get("mitre_techniques") or []
    confidence = str(raw.get("confidence", "")).lower().strip()
    if confidence not in VALID_CONFIDENCE:
        confidence = "low"
    return {
        "summary": str(raw.get("summary", "")).strip(),
        "evidence_refs": [str(r) for r in refs],
        "mitre_techniques": [str(t) for t in techniques],
        "confidence": confidence,
    }


# ---------------------------------------------------------------------------
# Tool input models (shared across both specialists)
#
# Band derives each tool name from the class name minus "Input", lowercased
# (e.g. PostStructuredFindingInput -> "poststructuredfinding"). The docstring
# becomes the tool description the LLM reads.
# ---------------------------------------------------------------------------

class GetEvidenceInput(BaseModel):
    """Read one evidence category's contents from the case bundle. Use this to read the categories assigned to you."""

    case_id: str = Field(
        ..., description="Case identifier, e.g. 'DFIR-2026-001' or 'case_001_ransomware'."
    )
    category: str = Field(..., description="Evidence category name to fetch.")


class SearchEvidenceInput(BaseModel):
    """Case-insensitive keyword search within one evidence category. Returns matching items."""

    case_id: str = Field(..., description="Case identifier.")
    category: str = Field(..., description="Evidence category to search within.")
    query: str = Field(..., description="Keyword/substring to search for.")


class PostStructuredFindingInput(BaseModel):
    """Build, persist, and audit a StructuredFinding (kind='structured_finding'), then return the JSON so you can post it in the room with @DFIR-Captain. Records a SPECIALIST_FINDING audit event."""

    case_id: str = Field(..., description="Case identifier.")
    findings: list[dict[str, Any]] = Field(
        ...,
        description=(
            "One or more finding objects, each "
            "{'summary': str, 'evidence_refs': [category/key, ...], "
            "'mitre_techniques': [str, ...], 'confidence': 'low|medium|high'}."
        ),
    )
    open_questions: list[str] = Field(
        default_factory=list,
        description="What would change your confidence (may be empty).",
    )


class RecordChallengeInput(BaseModel):
    """Record a challenge to another specialist's finding (SPECIALIST_CHALLENGE audit event). Then post the challenge in the room, @mentioning the other specialist and @DFIR-Captain. Back your challenge with specific evidence references."""

    case_id: str = Field(..., description="Case identifier.")
    target_specialist: str = Field(
        ..., description="The specialist whose finding you are challenging."
    )
    challenge: str = Field(
        ..., description="The substance of your challenge, grounded in evidence."
    )
    evidence_refs: list[str] = Field(
        default_factory=list,
        description="category/key references that support your challenge.",
    )


# ---------------------------------------------------------------------------
# Tool factory (handlers close over the specialist's display name)
# ---------------------------------------------------------------------------

def build_specialist_tools(display_name: str) -> list[CustomToolDef]:
    """Return the custom-tool list for a specialist, bound to its handle.

    Handlers are closures over ``display_name`` so audit events and finding
    documents are stamped with the correct specialist id.
    """

    def get_evidence(args: GetEvidenceInput) -> dict | list:
        return evidence_tools.get_evidence(args.case_id, args.category)

    def search_evidence(args: SearchEvidenceInput) -> list:
        return evidence_tools.search_evidence(args.case_id, args.category, args.query)

    def post_structured_finding(args: PostStructuredFindingInput) -> dict:
        finding = {
            "kind": "structured_finding",
            "specialist": display_name,
            "case_id": args.case_id,
            "findings": [_normalize_finding(f) for f in args.findings],
            "open_questions": [str(q) for q in (args.open_questions or [])],
        }
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        path = _findings_dir(args.case_id) / f"{_slug(display_name)}-{stamp}.json"
        path.write_text(json.dumps(finding, indent=2), encoding="utf-8")

        chain = _audit_chain(args.case_id)
        event_hash = chain.append(
            "SPECIALIST_FINDING",
            display_name,
            {"finding_path": str(path), "num_findings": len(finding["findings"])},
        )
        return {
            "structured_finding": finding,
            "path": str(path),
            "hash": event_hash,
            "head": chain.head_hash(),
        }

    def record_challenge(args: RecordChallengeInput) -> dict:
        payload = {
            "challenged_specialist": args.target_specialist,
            "challenge": args.challenge,
            "evidence_refs": [str(r) for r in (args.evidence_refs or [])],
        }
        chain = _audit_chain(args.case_id)
        event_hash = chain.append("SPECIALIST_CHALLENGE", display_name, payload)
        return {"payload": payload, "hash": event_hash, "head": chain.head_hash()}

    return [
        (GetEvidenceInput, get_evidence),
        (SearchEvidenceInput, search_evidence),
        (PostStructuredFindingInput, post_structured_finding),
        (RecordChallengeInput, record_challenge),
    ]


# ---------------------------------------------------------------------------
# Adapter + run wiring
# ---------------------------------------------------------------------------

def build_adapter(display_name: str, system_prompt: str) -> GeminiAdapter:
    """Construct the Gemini adapter for a specialist (no network I/O)."""
    return GeminiAdapter(
        model="gemini-2.5-flash",
        provider_key=os.environ.get("GEMINI_API_KEY"),
        prompt=system_prompt,
        temperature=0.3,
        max_output_tokens=2048,
        additional_tools=build_specialist_tools(display_name),
        # Surface tool calls/results into the room as execution events.
        features=AdapterFeatures(emit=frozenset({Emit.EXECUTION})),
    )


async def run_agent(agent_key: str, display_name: str, system_prompt: str) -> None:
    """Wire up a specialist agent and run until interrupted."""
    load_dotenv(PROJECT_ROOT / ".env")
    logging.basicConfig(level=logging.INFO)

    adapter = build_adapter(display_name, system_prompt)
    agent_id, api_key = load_credentials(
        agent_key, config_path=PROJECT_ROOT / "agent_config.yaml"
    )
    agent = Agent.create(adapter=adapter, agent_id=agent_id, api_key=api_key)

    logger.info("%s is running. Press Ctrl+C to stop.", display_name)
    await agent.run()
