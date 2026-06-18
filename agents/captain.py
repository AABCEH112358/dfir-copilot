"""DFIR-Captain agent — the synthesis and final-authority layer in a DFIR room.

Built on the Band SDK 1.0.0 (import name ``band``, NOT ``thenvoi``). The Captain
observes the Classifier's routing and the specialists' findings, drives the room
toward resolution (redirecting on disagreement, re-scoping on scope creep), and
issues the final CaptainVerdict (see ``docs/AGENT_CONTRACTS.md``). It synthesizes
what specialists report — it does not investigate evidence directly.

NOTE: this agent uses gemini-2.5-pro (NOT Flash) for stronger synthesis.

Run it with::

    python agents/captain.py

Reference architecture: https://www.band.ai/hacker-guide
"""

from __future__ import annotations

import asyncio
import json
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
# directly as ``python agents/captain.py``.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lib import audit_trail  # noqa: E402
from lib.agent_credentials import load_credentials  # noqa: E402

logger = logging.getLogger("dfir.captain")

AGENT_KEY = "captain"
AGENT_DISPLAY_NAME = "DFIR-Captain"
OUTPUTS_DIR = PROJECT_ROOT / "data" / "outputs"


# ---------------------------------------------------------------------------
# System prompt (full, load-bearing — do not abbreviate)
# ---------------------------------------------------------------------------

CAPTAIN_SYSTEM_PROMPT = """\
# Identity
You are DFIR-Captain. You do not investigate evidence directly — you synthesize what \
the specialists report. Your authority comes from connecting their views, not \
overriding them.

# MITRE Expertise
You are fluent in the MITRE ATT&CK Enterprise matrix. When you consolidate the \
specialists' technique mappings, ensure each technique is supported by evidence cited \
by at least one specialist.

# Loop Prevention
If the same disagreement persists across two rounds, force a verdict by asking each \
specialist to commit to a confidence level. Do not let the debate run more than 3 rounds.

# Re-Scope Authority
You alone can re-scope the investigation. Trust your judgment here — if the evidence \
shape doesn't match the original hypothesis, say so.

# Token Economy
Be concise. Specialists do the detail work. You synthesize.

# Your Four Phases

## PHASE 1 — OBSERVE
Watch the room as the Classifier routes evidence and the specialists post findings. \
Maintain an internal model of what each specialist has concluded. Use your read-findings \
tool to review the StructuredFindings posted so far. Do NOT speak until BOTH specialists \
(DFIR-HostForensics and DFIR-NetworkForensics) have posted at least one StructuredFinding.

## PHASE 2 — DETECT DISAGREEMENT OR GAPS
- If the specialists agree on the interpretation, move toward a verdict (Phase 4).
- If they disagree, @mention BOTH with a SPECIFIC question that could resolve the \
disagreement — not a vague "please clarify". For example: "@DFIR-HostForensics \
@DFIR-NetworkForensics — Host reports no compromise indicators, Network reports \
anomalous outbound to personal Gmail. Host — can you verify whether the attachment \
file types match engineering formats? Network — can you confirm the exact bytes sent?" \
Record this with your redirect tool (event_type CAPTAIN_REDIRECT).

## PHASE 3 — DETECT SCOPE CREEP
If a finding suggests the investigation scope is wrong (e.g., the specialists are \
chasing a direct intrusion when the evidence points at a supply-chain compromise), \
@mention the Liaison with a re-scope directive, for example: "@DFIR-Liaison — this is \
not direct intrusion. We need a fleet-wide dependency audit. Please go back to the human \
for additional collection." Record this with your redirect tool as well (CAPTAIN_REDIRECT, \
audience DFIR-Liaison). The Liaison will run another round of collection.

## PHASE 4 — VERDICT
When you are confident, post a CaptainVerdict as a structured message with @DFIR-Liaison \
in the mentions. Build it with your post-verdict tool, which persists it and records a \
CAPTAIN_VERDICT audit event and stamps the final audit-chain head into the verdict. Every \
MITRE technique in the verdict must carry evidence cited by a specialist.

# CaptainVerdict Schema (match docs/AGENT_CONTRACTS.md exactly)
Your post-verdict tool builds and persists this exact shape (you supply every field \
except audit_chain_head, which the tool computes):
{
  "kind": "captain_verdict",
  "case_id": "<case id>",
  "classification": "one-line type of incident",
  "subtype": "string",
  "threat_actor_attribution": {"group": "...", "confidence": "..."},
  "initial_access_vector": "string",
  "mitre_techniques": [{"id": "T1486", "name": "...", "evidence": "..."}],
  "immediate_actions": ["string"],
  "evidence_preserved": ["category/key"],
  "regulatory_obligations": ["string"],
  "human_followup_recommended": ["string"],
  "audit_chain_head": "sha256-hex"
}

# Audit Discipline (mandatory)
Redirects (to specialists or the Liaison) are logged as CAPTAIN_REDIRECT; the final \
verdict is logged as CAPTAIN_VERDICT. The audit chain is the case's chain of custody.
"""


# ---------------------------------------------------------------------------
# Per-case helpers (mirrors the other agents' output layout)
# ---------------------------------------------------------------------------

def _case_dir(case_id: str) -> Path:
    path = OUTPUTS_DIR / case_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _findings_dir(case_id: str) -> Path:
    return _case_dir(case_id) / "findings"


def _audit_chain(case_id: str) -> audit_trail.AuditChain:
    """Open (or create) the per-case tamper-evident audit chain (shared file)."""
    return audit_trail.AuditChain(case_id, _case_dir(case_id) / "audit_chain.jsonl")


# ---------------------------------------------------------------------------
# Tool input models + handlers
#
# Band derives each tool name from the class name minus "Input", lowercased
# (e.g. PostVerdictInput -> "postverdict"). The docstring becomes the tool
# description the LLM reads.
# ---------------------------------------------------------------------------

class ReadFindingsInput(BaseModel):
    """Read every StructuredFinding the specialists have posted for this case so far. Use this to maintain your internal model and to confirm each MITRE technique is backed by cited evidence."""

    case_id: str = Field(
        ..., description="Case identifier, e.g. 'DFIR-2026-001' or 'case_001_ransomware'."
    )


def read_findings(args: ReadFindingsInput) -> list[dict]:
    findings_dir = _findings_dir(args.case_id)
    if not findings_dir.is_dir():
        return []
    out: list[dict] = []
    for path in sorted(findings_dir.glob("*.json")):
        try:
            out.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return out


class RecordRedirectInput(BaseModel):
    """Record a CAPTAIN_REDIRECT audit event for a disagreement-resolving question (to both specialists) OR a re-scope directive (to the Liaison). Then post the actual @mention message in the room yourself."""

    case_id: str = Field(..., description="Case identifier.")
    audience: str = Field(
        ...,
        description=(
            "Who the redirect targets, e.g. 'DFIR-HostForensics,DFIR-NetworkForensics' "
            "or 'DFIR-Liaison'."
        ),
    )
    directive: str = Field(
        ...,
        description="The specific question or re-scope directive you are issuing.",
    )
    reason: str = Field(
        "",
        description="Brief reason / what triggered this redirect (optional).",
    )


def record_redirect(args: RecordRedirectInput) -> dict:
    chain = _audit_chain(args.case_id)
    payload = {
        "audience": args.audience,
        "directive": args.directive,
        "reason": args.reason,
    }
    event_hash = chain.append("CAPTAIN_REDIRECT", AGENT_DISPLAY_NAME, payload)
    return {"payload": payload, "hash": event_hash, "head": chain.head_hash()}


class PostVerdictInput(BaseModel):
    """Build, persist, and audit the final CaptainVerdict (kind='captain_verdict'), then return the JSON so you can post it in the room with @DFIR-Liaison. The tool records a CAPTAIN_VERDICT event and stamps the final audit-chain head into the verdict."""

    case_id: str = Field(..., description="Case identifier.")
    classification: str = Field(..., description="One-line type of incident.")
    subtype: str = Field("", description="More specific subtype/variant.")
    threat_actor_attribution: dict[str, Any] = Field(
        default_factory=dict,
        description="{'group': str, 'confidence': str}.",
    )
    initial_access_vector: str = Field(
        "", description="How the attacker first got in."
    )
    mitre_techniques: list[dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "Consolidated techniques; each {'id': str, 'name': str, 'evidence': str}. "
            "Every entry must cite evidence reported by a specialist."
        ),
    )
    immediate_actions: list[str] = Field(default_factory=list)
    evidence_preserved: list[str] = Field(
        default_factory=list,
        description="category/key references to preserved evidence.",
    )
    regulatory_obligations: list[str] = Field(default_factory=list)
    human_followup_recommended: list[str] = Field(default_factory=list)


def _normalize_technique(raw: dict[str, Any]) -> dict[str, str]:
    return {
        "id": str(raw.get("id", "")).strip(),
        "name": str(raw.get("name", "")).strip(),
        "evidence": str(raw.get("evidence", "")).strip(),
    }


def post_verdict(args: PostVerdictInput) -> dict:
    attribution = {
        "group": str(args.threat_actor_attribution.get("group", "")).strip(),
        "confidence": str(args.threat_actor_attribution.get("confidence", "")).strip(),
    }
    verdict: dict[str, Any] = {
        "kind": "captain_verdict",
        "case_id": args.case_id,
        "classification": args.classification,
        "subtype": args.subtype,
        "threat_actor_attribution": attribution,
        "initial_access_vector": args.initial_access_vector,
        "mitre_techniques": [_normalize_technique(t) for t in args.mitre_techniques],
        "immediate_actions": [str(a) for a in args.immediate_actions],
        "evidence_preserved": [str(e) for e in args.evidence_preserved],
        "regulatory_obligations": [str(r) for r in args.regulatory_obligations],
        "human_followup_recommended": [str(h) for h in args.human_followup_recommended],
    }

    path = _case_dir(args.case_id) / "captain_verdict.json"

    # Log the verdict event first, then seal the verdict with the resulting head
    # so audit_chain_head reflects the chain *including* this verdict.
    chain = _audit_chain(args.case_id)
    event_hash = chain.append(
        "CAPTAIN_VERDICT",
        AGENT_DISPLAY_NAME,
        {
            "verdict_path": str(path),
            "classification": args.classification,
            "num_techniques": len(verdict["mitre_techniques"]),
        },
    )
    verdict["audit_chain_head"] = chain.head_hash()
    path.write_text(json.dumps(verdict, indent=2), encoding="utf-8")

    return {
        "captain_verdict": verdict,
        "path": str(path),
        "hash": event_hash,
        "audit_chain_head": verdict["audit_chain_head"],
    }


CAPTAIN_TOOLS = [
    (ReadFindingsInput, read_findings),
    (RecordRedirectInput, record_redirect),
    (PostVerdictInput, post_verdict),
]


# ---------------------------------------------------------------------------
# Credentials + agent wiring
# ---------------------------------------------------------------------------

def _load_captain_credentials() -> tuple[str, str]:
    """Resolve (agent_id, api_key) for the Captain.

    Reads the agent_id from ``agent_config.yaml['agents']['captain']`` and the API
    key from the env var named by that block's ``api_key_env`` (``CAPTAIN_API_KEY``),
    via the shared ``lib.agent_credentials`` helper.
    """
    return load_credentials(AGENT_KEY, config_path=PROJECT_ROOT / "agent_config.yaml")


def build_adapter() -> GeminiAdapter:
    """Construct the Gemini adapter for the Captain (no network I/O).

    Uses gemini-2.5-pro (NOT Flash) for stronger synthesis.
    """
    return GeminiAdapter(
        model="gemini-2.5-pro",
        provider_key=os.environ.get("GEMINI_API_KEY"),
        prompt=CAPTAIN_SYSTEM_PROMPT,
        temperature=0.3,
        max_output_tokens=4096,
        additional_tools=CAPTAIN_TOOLS,
        # Surface tool calls/results into the room as execution events.
        features=AdapterFeatures(emit=frozenset({Emit.EXECUTION})),
    )


async def run_agent() -> None:
    """Wire up the Captain and run until interrupted."""
    load_dotenv(PROJECT_ROOT / ".env")
    logging.basicConfig(level=logging.INFO)

    adapter = build_adapter()
    agent_id, api_key = _load_captain_credentials()
    agent = Agent.create(adapter=adapter, agent_id=agent_id, api_key=api_key)

    logger.info("%s is running. Press Ctrl+C to stop.", AGENT_DISPLAY_NAME)
    await agent.run()


if __name__ == "__main__":
    asyncio.run(run_agent())
