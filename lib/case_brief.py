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

import json
from datetime import datetime, timezone
from pathlib import Path

VALID_PHASES = ["INTAKE", "COLLECTION", "INVESTIGATION", "VERDICT", "REPORT"]

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = PROJECT_ROOT / "data" / "outputs"
GROUND_TRUTH_KEY = "ground_truth"


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


# Plain-language descriptions for evidence categories, keyed by the category part
# of a ``category/key`` reference. Used to populate the Evidence Catalog.
_EVIDENCE_DESCRIPTIONS = {
    "ransom_note": "The ransom note the attackers left on affected systems.",
    "encrypted_sample": "A sample of one of your encrypted (.lock_b1d) files.",
    "edr_alerts": "An alert from your endpoint security (EDR) tool.",
    "network_traffic": "Network records showing outbound data transfers.",
    "dns_queries": "DNS lookup records (which domains your machines contacted).",
    "memory_artifacts": "A memory capture taken from an affected machine.",
    "firewall_proxy_logs": "Firewall and web-proxy logs.",
    "internal_dns_query_logs": "Internal DNS resolver query logs.",
}


def _evidence_description(ref: str) -> str:
    """Plain-language description for a ``category/key`` evidence reference."""
    category = ref.split("/", 1)[0]
    return _EVIDENCE_DESCRIPTIONS.get(category, "Collected case evidence.")


def render_liaison_report(
    case_id: str,
    verdict: dict,
    scenario_dict: dict | None = None,
    audit_chain_path: str | None = None,
    audit_chain_head: str | None = None,
    audit_event_count: int | None = None,
) -> str:
    """Render the human-facing Phase 3 LiaisonReport Markdown.

    Conforms to the LiaisonReport contract in docs/AGENT_CONTRACTS.md: seven
    sections, in order, in plain language for the human investigator in the room.
    Built from the Captain's ``verdict`` (a CaptainVerdict dict) plus optional
    ``scenario_dict`` (for the victim/contact context) and audit-chain details.
    """
    scenario = scenario_dict or {}
    victim = scenario.get("victim_organization", {})
    human = scenario.get("human_in_room", {})
    org_name = victim.get("name", "your organization")
    contact_name = human.get("name", "")
    first_name = contact_name.split()[0] if contact_name else "there"

    classification = verdict.get("classification", "security incident")
    subtype = verdict.get("subtype", "")
    techniques = verdict.get("mitre_techniques", [])
    immediate = verdict.get("immediate_actions", [])
    followups = verdict.get("human_followup_recommended", [])
    obligations = verdict.get("regulatory_obligations", [])
    preserved = verdict.get("evidence_preserved", [])
    initial_access = verdict.get("initial_access_vector", "")
    head = audit_chain_head or verdict.get("audit_chain_head", "")

    title = f"# Incident Report: {case_id} — {org_name} {classification}"

    # 1. Summary for the Investigator
    summary_lines = [
        "## Summary for the Investigator",
        (
            f"{first_name}, here is the bottom line. This was a "
            f"{classification.lower()}"
            + (f" (the {subtype} ransomware variant)" if subtype else "")
            + ". Before any files were locked, the attackers had already copied "
            "data out of your network — so this is a \"double-extortion\" situation: "
            "paying a ransom would not undo the data theft. Treat the regulatory "
            "notification clock as already running, and keep the network isolated "
            "while you work through the steps below."
        ),
    ]

    # 2. What Happened (plain language)
    happened_lines = [
        "## What Happened (plain language)",
        (
            "In plain terms: the attackers first got in through "
            + (initial_access.lower() if initial_access else "an initial intrusion")
            + " on a workstation. They stayed quietly for a while, talking to a "
            "server they controlled on the internet, then used that foothold to "
            "reach your file servers. Before locking anything, they copied a large "
            "amount of your data out of the network. Finally they encrypted files "
            "and renamed them with a `.lock_b1d` extension, which is what triggered "
            "your morning alerts."
        ),
    ]

    # 3. MITRE Mapping with Explanations
    mitre_lines = ["## MITRE Mapping with Explanations"]
    if techniques:
        for tech in techniques:
            tid = tech.get("id", "")
            name = tech.get("name", "")
            evidence = tech.get("evidence", "")
            mitre_lines.append(
                f"- **{tid} — {name}**: {evidence}"
                if evidence
                else f"- **{tid} — {name}**"
            )
    else:
        mitre_lines.append("- (No techniques were consolidated for this case.)")

    # 4. Evidence Catalog
    catalog_lines = [
        "## Evidence Catalog",
        "| Reference | What it is |",
        "|-----------|------------|",
    ]
    if preserved:
        for ref in preserved:
            catalog_lines.append(f"| `{ref}` | {_evidence_description(ref)} |")
    else:
        catalog_lines.append("| (none recorded) | |")

    # 5. Recommended Next Steps
    steps_lines = ["## Recommended Next Steps"]
    step_items = list(immediate) + list(followups)
    if step_items:
        for i, step in enumerate(step_items, start=1):
            steps_lines.append(f"{i}. {step}")
    else:
        steps_lines.append("1. (No specific actions were recorded.)")

    # 6. Regulatory Clocks
    reg_lines = ["## Regulatory Clocks"]
    compliance = victim.get("compliance_context") or []
    if obligations:
        for ob in obligations:
            reg_lines.append(f"- {ob}")
    if compliance:
        reg_lines.append(
            "- Applicable compliance context for "
            f"{org_name}: " + ", ".join(compliance) + "."
        )
    if not obligations and not compliance:
        reg_lines.append("- No specific regulatory obligations were recorded.")

    # 7. Chain of Custody
    custody_lines = ["## Chain of Custody"]
    custody_lines.append(
        "Every action in this case is recorded in a tamper-evident SHA-256 hash "
        "chain — each entry is cryptographically linked to the one before it, so "
        "any later edit to the record is detectable."
    )
    if audit_chain_path:
        custody_lines.append(f"- Audit chain file: `{audit_chain_path}`")
    if audit_event_count is not None:
        custody_lines.append(f"- Total recorded events: {audit_event_count}")
    if head:
        custody_lines.append(f"- Audit chain head: `{head}`")
    custody_lines.append(
        "- This report is logged as `REPORT_DRAFTED`, and the case is then closed "
        "with a terminal `CASE_SEALED` entry."
    )

    sections = [
        title,
        "\n".join(summary_lines),
        "\n".join(happened_lines),
        "\n".join(mitre_lines),
        "\n".join(catalog_lines),
        "\n".join(steps_lines),
        "\n".join(reg_lines),
        "\n".join(custody_lines),
    ]
    return "\n\n".join(sections) + "\n"


def _strip_ground_truth(obj: object) -> object:
    """Recursively remove any ``ground_truth`` keys from nested dict/list data.

    The CaseFile is the public-facing record David's viewer reads, so any
    eval-only ground_truth must be stripped at this boundary.
    """
    if isinstance(obj, dict):
        return {
            k: _strip_ground_truth(v)
            for k, v in obj.items()
            if k != GROUND_TRUTH_KEY
        }
    if isinstance(obj, list):
        return [_strip_ground_truth(v) for v in obj]
    return obj


def _read_audit_events(path: Path) -> list[dict]:
    """Read all JSON Lines events from an audit chain file (in order)."""
    events: list[dict] = []
    if not path.is_file():
        return events
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def build_case_file(case_id: str, *, outputs_dir: str | Path | None = None) -> dict:
    """Aggregate a case's artifacts into the public CaseFile record.

    Conforms to the CaseFile schema in docs/AGENT_CONTRACTS.md (case_id,
    opened_at, closed_at, case_brief_md, all_findings, captain_verdict,
    liaison_report_md, audit_chain_path) plus an ``audit_chain_head`` set to the
    final (CASE_SEALED) hash. ``opened_at``/``closed_at`` come from the first and
    last audit events. Any ground_truth is stripped at this boundary so the
    record is safe for David's viewer.
    """
    base = Path(outputs_dir) if outputs_dir is not None else OUTPUTS_DIR
    case_dir = base / case_id

    events = _read_audit_events(case_dir / "audit_chain.jsonl")
    opened_at = events[0]["timestamp"] if events else ""
    closed_at = events[-1]["timestamp"] if events else ""
    audit_chain_head = events[-1]["hash"] if events else ""

    all_findings: list[dict] = []
    findings_dir = case_dir / "findings"
    if findings_dir.is_dir():
        for path in sorted(findings_dir.glob("*.json")):
            all_findings.append(json.loads(path.read_text(encoding="utf-8")))

    captain_verdict: dict = {}
    verdict_path = case_dir / "captain_verdict.json"
    if verdict_path.is_file():
        captain_verdict = json.loads(verdict_path.read_text(encoding="utf-8"))

    def _read_text(name: str) -> str:
        p = case_dir / name
        return p.read_text(encoding="utf-8") if p.is_file() else ""

    case_file = {
        "case_id": case_id,
        "opened_at": opened_at,
        "closed_at": closed_at,
        "case_brief_md": _read_text("case_brief.md"),
        "all_findings": all_findings,
        "captain_verdict": captain_verdict,
        "liaison_report_md": _read_text("liaison_report.md"),
        "audit_chain_path": f"data/outputs/{case_id}/audit_chain.jsonl",
        "audit_chain_head": audit_chain_head,
    }
    # Strip ground_truth at the boundary (defensive — none should be present).
    return _strip_ground_truth(case_file)  # type: ignore[return-value]
