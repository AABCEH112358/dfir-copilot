"""Unit tests for the DFIR evidence access tools, using case_001 as fixture."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib import evidence_tools as ET

# Filename-stem resolution (rule 1): data/cases/case_001_ransomware.json
CASE_ID = "case_001_ransomware"
# Canonical internal id resolution (rule 2): the "case_id" field in the JSON
CANONICAL_ID = "DFIR-2026-001"


def _assert_no_ground_truth(obj: object) -> None:
    """Recursively assert no 'ground_truth' key appears anywhere in output."""
    if isinstance(obj, dict):
        assert "ground_truth" not in obj
        for v in obj.values():
            _assert_no_ground_truth(v)
    elif isinstance(obj, list):
        for v in obj:
            _assert_no_ground_truth(v)


def test_load_case_strips_ground_truth() -> None:
    case = ET.load_case(CASE_ID)
    assert case["case_id"] == "DFIR-2026-001"
    assert "ground_truth" not in case
    _assert_no_ground_truth(case)


def test_load_case_by_canonical_id() -> None:
    case = ET.load_case(CANONICAL_ID)
    assert isinstance(case, dict)
    assert case["case_id"] == "DFIR-2026-001"
    assert "ground_truth" not in case
    _assert_no_ground_truth(case)


def test_load_case_by_filename_stem() -> None:
    # Rule 1 resolution by exact filename stem must still work.
    case = ET.load_case(CASE_ID)
    assert case["case_id"] == "DFIR-2026-001"
    assert "ground_truth" not in case


def test_load_case_raises_for_fake_case() -> None:
    with pytest.raises(FileNotFoundError) as exc_info:
        ET.load_case("case_999_does_not_exist")
    # Rule 3: error message lists the available case_ids for debugging.
    assert "DFIR-2026-001" in str(exc_info.value)


def test_get_scenario_brief() -> None:
    brief = ET.get_scenario_brief(CASE_ID)
    assert set(brief.keys()) >= {
        "incident_summary",
        "victim_organization",
        "human_in_room",
        "human_opening_message",
    }
    _assert_no_ground_truth(brief)


def test_list_evidence_categories() -> None:
    cats = ET.list_evidence_categories(CASE_ID)
    assert "encrypted_sample" in cats
    assert "ransom_note" in cats
    assert "edr_alerts" in cats
    assert "ground_truth" not in cats


def test_get_evidence_returns_right_shape() -> None:
    samples = ET.get_evidence(CASE_ID, "encrypted_sample")
    assert isinstance(samples, list)
    assert len(samples) == 3
    first = samples[0]
    assert first["encryption_marker"] == "lock_b1d"
    assert {"original_filename", "encrypted_filename", "host"} <= set(first.keys())

    ransom = ET.get_evidence(CASE_ID, "ransom_note")
    assert isinstance(ransom, dict)
    assert "text_content" in ransom


def test_get_evidence_unknown_category_raises() -> None:
    with pytest.raises(KeyError):
        ET.get_evidence(CASE_ID, "not_a_real_category")


def test_search_evidence_finds_lock_b1d() -> None:
    results = ET.search_evidence(CASE_ID, "encrypted_sample", "lock_b1d")
    assert len(results) == 3
    assert all("lock_b1d" in r["encrypted_filename"] for r in results)


def test_search_evidence_case_insensitive_and_filters() -> None:
    # Case-insensitive match on a host present in only one sample.
    results = ET.search_evidence(CASE_ID, "encrypted_sample", "ws-fin-014")
    assert len(results) == 1
    assert results[0]["host"] == "WS-FIN-014"

    # A query that matches nothing returns an empty list.
    assert ET.search_evidence(CASE_ID, "encrypted_sample", "zzz_no_match") == []


def test_get_collection_plan() -> None:
    plan = ET.get_collection_plan(CASE_ID)
    assert isinstance(plan, list)
    assert len(plan) == 6
    assert plan[0]["step"] == 1
    assert plan[0]["evidence_category"] == "ransom_note"


def test_ground_truth_never_in_any_output() -> None:
    _assert_no_ground_truth(ET.load_case(CASE_ID))
    _assert_no_ground_truth(ET.get_scenario_brief(CASE_ID))
    _assert_no_ground_truth(ET.get_collection_plan(CASE_ID))
    for cat in ET.list_evidence_categories(CASE_ID):
        _assert_no_ground_truth(ET.get_evidence(CASE_ID, cat))
