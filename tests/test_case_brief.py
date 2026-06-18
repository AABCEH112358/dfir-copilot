"""Unit tests for the case brief / specialist packet Markdown builders."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib import case_brief as CB


@pytest.fixture
def scenario() -> dict:
    return {
        "incident_summary": "Ransomware encrypted 40% of shares.",
        "victim_organization": {
            "name": "Meridian Logistics Inc.",
            "industry": "Logistics",
            "size": 380,
            "location": "Columbus, Ohio, USA",
            "compliance_context": ["Ohio Data Protection Act", "DOT Hazmat"],
        },
        "human_in_room": {
            "name": "Priya Achterberg",
            "role": "Director of IT Security",
            "technical_skill": "intermediate",
            "context": "First major incident.",
        },
        "human_opening_message": "We're in trouble. Files are encrypted.",
    }


def test_render_case_brief_structure(scenario: dict) -> None:
    out = CB.render_case_brief(
        "DFIR-2026-001",
        scenario,
        intake_summary="Likely double-extortion ransomware.",
        phase="INTAKE",
        audit_chain_head="abc123",
        last_updated="2026-06-17T12:00:00+00:00",
    )

    assert out.startswith("# Case Brief: DFIR-2026-001")
    # Required section headers, in order.
    for header in [
        "## Incident Summary",
        "## Victim Organization",
        "## Human Contact",
        "## Initial Report",
        "## Liaison's Intake Summary",
        "## Status",
    ]:
        assert header in out
    positions = [out.index(h) for h in [
        "## Incident Summary",
        "## Victim Organization",
        "## Human Contact",
        "## Initial Report",
        "## Liaison's Intake Summary",
        "## Status",
    ]]
    assert positions == sorted(positions)

    assert "Ransomware encrypted 40% of shares." in out
    assert "- Name: Meridian Logistics Inc." in out
    assert "- Size: 380 people" in out
    assert "- Compliance context: Ohio Data Protection Act, DOT Hazmat" in out
    assert "- Name: Priya Achterberg" in out
    assert "- Technical skill: intermediate" in out
    assert "- Context: First major incident." in out
    # Initial report rendered as a blockquote.
    assert "> We're in trouble. Files are encrypted." in out
    assert "Likely double-extortion ransomware." in out
    assert "- Phase: INTAKE" in out
    assert "- Last updated: 2026-06-17T12:00:00+00:00" in out
    assert "- Audit chain head: abc123" in out


def test_render_case_brief_defaults_and_fallbacks() -> None:
    # Minimal scenario exercises fallbacks (no compliance, experience_level).
    minimal = {
        "incident_summary": "Something happened.",
        "victim_organization": {"name": "Acme"},
        "human_in_room": {"name": "Sam", "experience_level": "8 years"},
        "human_opening_message": "Help.",
    }
    out = CB.render_case_brief("C1", minimal, "summary")
    assert "- Compliance context: None recorded" in out
    # technical_skill falls back to experience_level.
    assert "- Technical skill: 8 years" in out
    # Default phase and audit head placeholder.
    assert "- Phase: INTAKE" in out
    assert "- Audit chain head: (no audit chain yet)" in out


def test_render_specialist_packet_structure() -> None:
    out = CB.render_specialist_packet(
        specialist_name="MalwareAnalyst",
        case_id="DFIR-2026-001",
        assigned_artifacts=[
            {"category": "encrypted_sample", "description": "Three .lock_b1d files"},
            {"category": "memory_artifacts", "description": "Process dumps"},
        ],
        co_specialists=[
            {"name": "NetworkAnalyst", "evidence_categories_owned": ["network_traffic", "dns_queries"]},
            {"name": "EndpointAnalyst", "evidence_categories_owned": ["edr_alerts"]},
        ],
        focus_directive="Identify the ransomware family and encryption scheme.",
    )

    assert out.startswith("# Specialist Handoff: MalwareAnalyst on DFIR-2026-001")
    for header in [
        "## Your Assignment",
        "## Your Evidence Package",
        "## Other Specialists Working This Case",
        "## How to Coordinate",
        "## MITRE ATT&CK Reference",
    ]:
        assert header in out

    assert "Identify the ransomware family and encryption scheme." in out
    assert "- **encrypted_sample**: Three .lock_b1d files" in out
    assert "- **memory_artifacts**: Process dumps" in out
    assert "- **NetworkAnalyst**: network_traffic, dns_queries" in out
    assert "- **EndpointAnalyst**: edr_alerts" in out
    assert "@mention them AND the Captain" in out
    assert "docs/AGENT_CONTRACTS.md" in out
    assert "MITRE technique IDs" in out


def test_render_specialist_packet_empty_collections() -> None:
    out = CB.render_specialist_packet(
        specialist_name="Solo",
        case_id="C2",
        assigned_artifacts=[],
        co_specialists=[],
        focus_directive="Look at everything.",
    )
    assert "- (no artifacts assigned)" in out
    assert "- (you are the only specialist on this case)" in out


def test_append_to_case_brief(tmp_path: Path, scenario: dict) -> None:
    path = tmp_path / "case_brief.md"
    original = CB.render_case_brief("DFIR-2026-001", scenario, "intake")
    path.write_text(original, encoding="utf-8")

    CB.append_to_case_brief(path, "Captain re-scope", "Focus shifted to exfiltration.")

    result = path.read_text(encoding="utf-8")
    # Original content preserved.
    assert result.startswith("# Case Brief: DFIR-2026-001")
    assert original in result
    # New timestamped update section appended.
    assert "## Update at " in result
    assert ": Captain re-scope" in result
    assert "Focus shifted to exfiltration." in result
    # The update comes after the original brief.
    assert result.index("## Update at ") > result.index("## Status")


def test_append_to_case_brief_multiple_updates(tmp_path: Path) -> None:
    path = tmp_path / "case_brief.md"
    path.write_text("# Case Brief: C3\n", encoding="utf-8")

    CB.append_to_case_brief(path, "first", "content one")
    CB.append_to_case_brief(path, "second", "content two")

    result = path.read_text(encoding="utf-8")
    assert result.count("## Update at ") == 2
    assert result.index(": first") < result.index(": second")


def _seed_sealed_case(outputs_dir: Path, case_id: str) -> str:
    """Create a minimal sealed case under outputs_dir; return the seal hash."""
    case_dir = outputs_dir / case_id
    (case_dir / "findings").mkdir(parents=True)

    seal_hash = "d0d8bdc7seal"
    events = [
        {"seq": 0, "timestamp": "2026-06-18T00:00:00+00:00", "event_type": "CASE_OPENED",
         "agent_id": "DFIR-Liaison", "payload": {}, "prev_hash": "0" * 64, "hash": "h0"},
        {"seq": 1, "timestamp": "2026-06-18T03:30:00+00:00", "event_type": "CASE_SEALED",
         "agent_id": "DFIR-Liaison", "payload": {"final": True}, "prev_hash": "h0",
         "hash": seal_hash},
    ]
    (case_dir / "audit_chain.jsonl").write_text(
        "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8"
    )
    (case_dir / "case_brief.md").write_text("# Case Brief: T\n", encoding="utf-8")
    (case_dir / "liaison_report.md").write_text("# Report\n", encoding="utf-8")
    # Embed ground_truth inside the verdict and a finding to prove it is stripped.
    (case_dir / "captain_verdict.json").write_text(
        json.dumps({"kind": "captain_verdict", "case_id": case_id, "ground_truth": "SECRET"}),
        encoding="utf-8",
    )
    (case_dir / "findings" / "f1.json").write_text(
        json.dumps({"kind": "structured_finding", "findings": [], "ground_truth": "LEAK"}),
        encoding="utf-8",
    )
    return seal_hash


def test_build_case_file_contract_head_and_no_ground_truth(tmp_path: Path) -> None:
    case_id = "DFIR-TEST-001"
    seal_hash = _seed_sealed_case(tmp_path, case_id)

    case_file = CB.build_case_file(case_id, outputs_dir=tmp_path)

    # Structure: all 8 contract keys present.
    contract_keys = {
        "case_id", "opened_at", "closed_at", "case_brief_md", "all_findings",
        "captain_verdict", "liaison_report_md", "audit_chain_path",
    }
    assert contract_keys <= set(case_file.keys())
    assert case_file["case_id"] == case_id
    assert case_file["opened_at"] == "2026-06-18T00:00:00+00:00"
    assert case_file["closed_at"] == "2026-06-18T03:30:00+00:00"
    assert len(case_file["all_findings"]) == 1

    # audit head matches the final (CASE_SEALED) hash.
    assert case_file["audit_chain_head"] == seal_hash

    # No ground_truth anywhere in the serialized output.
    assert "ground_truth" not in json.dumps(case_file)
