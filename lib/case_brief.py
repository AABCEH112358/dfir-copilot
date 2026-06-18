"""Markdown document builders for DFIR agent context sharing.

Two structured documents flow between agents:

* The global ``case_brief.md`` produced by the Liaison on case open
  (``render_case_brief``), optionally re-scoped later by the Captain
  (``append_to_case_brief``).
* A per-specialist handoff packet produced by the Classifier
  (``render_specialist_packet``).

No external dependencies beyond the standard library.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

VALID_PHASES = ["INTAKE", "COLLECTION", "INVESTIGATION", "VERDICT", "REPORT"]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def render_case_brief(
    case_id: str,
    scenario_dict: dict,
    intake_summary: str,
    phase: str = "INTAKE",
    audit_chain_head: str | None = None,
    last_updated: str | None = None,
) -> str:
    """Render the global case brief Markdown written by the Liaison on open.

    ``phase``, ``audit_chain_head`` (e.g. from ``AuditChain.head_hash()``), and
    ``last_updated`` are optional so the brief can be produced without an audit
    chain yet and so tests can inject deterministic values.
    """
    victim = scenario_dict.get("victim_organization", {})
    human = scenario_dict.get("human_in_room", {})
    timestamp = last_updated or _utc_now_iso()
    audit_head = audit_chain_head or "(no audit chain yet)"

    compliance = victim.get("compliance_context") or []
    compliance_text = ", ".join(compliance) if compliance else "None recorded"

    technical_skill = human.get("technical_skill") or human.get(
        "experience_level", "Unknown"
    )

    lines = [
        f"# Case Brief: {case_id}",
        "",
        "## Incident Summary",
        scenario_dict.get("incident_summary", ""),
        "",
        "## Victim Organization",
        f"- Name: {victim.get('name', 'Unknown')}",
        f"- Industry: {victim.get('industry', 'Unknown')}",
        f"- Size: {victim.get('size', 'Unknown')} people",
        f"- Location: {victim.get('location', 'Unknown')}",
        f"- Compliance context: {compliance_text}",
        "",
        "## Human Contact",
        f"- Name: {human.get('name', 'Unknown')}",
        f"- Role: {human.get('role', 'Unknown')}",
        f"- Technical skill: {technical_skill}",
        f"- Context: {human.get('context', '')}",
        "",
        "## Initial Report",
        f"> {scenario_dict.get('human_opening_message', '')}",
        "",
        "## Liaison's Intake Summary",
        intake_summary,
        "",
        "## Status",
        f"- Phase: {phase}",
        f"- Last updated: {timestamp}",
        f"- Audit chain head: {audit_head}",
        "",
    ]
    return "\n".join(lines)


def render_specialist_packet(
    specialist_name: str,
    case_id: str,
    assigned_artifacts: list[dict],
    co_specialists: list[dict],
    focus_directive: str,
) -> str:
    """Render a per-specialist handoff packet written by the Classifier.

    ``assigned_artifacts`` items are dicts with a category name and a brief
    description. ``co_specialists`` items are dicts with a name and the
    evidence categories they own.
    """
    lines = [
        f"# Specialist Handoff: {specialist_name} on {case_id}",
        "",
        "## Your Assignment",
        focus_directive,
        "",
        "## Your Evidence Package",
    ]

    if assigned_artifacts:
        for artifact in assigned_artifacts:
            category = artifact.get("category", "unknown")
            description = artifact.get("description", "")
            lines.append(f"- **{category}**: {description}")
    else:
        lines.append("- (no artifacts assigned)")

    lines += [
        "",
        "## Other Specialists Working This Case",
    ]

    if co_specialists:
        for peer in co_specialists:
            name = peer.get("name", "unknown")
            owned = peer.get("evidence_categories_owned") or []
            owned_text = ", ".join(owned) if owned else "none"
            lines.append(f"- **{name}**: {owned_text}")
    else:
        lines.append("- (you are the only specialist on this case)")

    lines += [
        "",
        "## How to Coordinate",
        "- If you need to correlate findings with another specialist's evidence, "
        "@mention them AND the Captain in the same message.",
        "- Post findings to the room. The Captain is watching.",
        "- If you reach a verdict you're confident in, post it as a STRUCTURED "
        "FINDING (see docs/AGENT_CONTRACTS.md).",
        "",
        "## MITRE ATT&CK Reference",
        "You may map findings to MITRE technique IDs. The Captain will consolidate.",
        "",
    ]
    return "\n".join(lines)


def append_to_case_brief(
    case_brief_path: Path,
    update_section: str,
    update_content: str,
) -> None:
    """Append a timestamped update section to an existing case_brief.md.

    Used when the Captain re-scopes mid-investigation. The new section is added
    as ``## Update at {timestamp}: {update_section}`` followed by the content.
    """
    path = Path(case_brief_path)
    timestamp = _utc_now_iso()
    block = (
        f"\n## Update at {timestamp}: {update_section}\n\n"
        f"{update_content}\n"
    )
    with path.open("a", encoding="utf-8") as fh:
        fh.write(block)
