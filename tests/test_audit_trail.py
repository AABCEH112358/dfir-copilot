"""Unit tests for the DFIR audit trail hash chain library."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.audit_trail import GENESIS_PREV_HASH, AuditChain


@pytest.fixture
def chain_path(tmp_path: Path) -> Path:
    return tmp_path / "case.jsonl"


def test_append_and_verify_happy_path(chain_path: Path) -> None:
    chain = AuditChain("CASE-001", chain_path)
    h0 = chain.append("CASE_OPENED", "captain", {"summary": "case opened"})
    h1 = chain.append("EVIDENCE_RECEIVED", "collector", {"item": "disk.img"})
    h2 = chain.append("CAPTAIN_VERDICT", "captain", {"verdict": "compromised"})

    assert h0 != h1 != h2
    events = chain.events()
    assert len(events) == 3
    assert events[0]["prev_hash"] == GENESIS_PREV_HASH
    assert events[1]["prev_hash"] == h0
    assert events[2]["prev_hash"] == h1

    ok, err = chain.verify()
    assert ok is True
    assert err is None


def test_tamper_detection(chain_path: Path) -> None:
    chain = AuditChain("CASE-002", chain_path)
    chain.append("CASE_OPENED", "captain", {"summary": "open"})
    chain.append("SPECIALIST_FINDING", "analyst", {"finding": "malware"})
    chain.append("CASE_SEALED", "captain", {"sealed": True})

    lines = chain_path.read_text(encoding="utf-8").splitlines()
    tampered = json.loads(lines[1])
    tampered["payload"]["finding"] = "nothing suspicious"
    lines[1] = json.dumps(tampered)
    chain_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    ok, err = chain.verify()
    assert ok is False
    assert err == "broken at seq 1"


def test_head_hash_matches_last_event(chain_path: Path) -> None:
    chain = AuditChain("CASE-003", chain_path)
    assert chain.head_hash() == GENESIS_PREV_HASH

    chain.append("CASE_OPENED", "captain", {"n": 1})
    last = chain.append("REPORT_DRAFTED", "writer", {"n": 2})

    assert chain.head_hash() == last
    assert chain.head_hash() == chain.events()[-1]["hash"]


def test_events_returns_in_order(chain_path: Path) -> None:
    chain = AuditChain("CASE-004", chain_path)
    types = [
        "CASE_OPENED",
        "COLLECTION_PLAN_ISSUED",
        "EVIDENCE_RECEIVED",
        "EVIDENCE_CLASSIFIED",
        "CASE_SEALED",
    ]
    for t in types:
        chain.append(t, "agent", {"t": t})

    events = chain.events()
    assert [e["seq"] for e in events] == [0, 1, 2, 3, 4]
    assert [e["event_type"] for e in events] == types


def test_chain_persists_across_reopen(chain_path: Path) -> None:
    first = AuditChain("CASE-005", chain_path)
    first.append("CASE_OPENED", "captain", {"step": 1})
    head_after_first = first.append("EVIDENCE_RECEIVED", "collector", {"step": 2})

    # Reopen the same file with a fresh instance.
    second = AuditChain("CASE-005", chain_path)
    assert second.head_hash() == head_after_first
    assert len(second.events()) == 2

    third_hash = second.append("CAPTAIN_VERDICT", "captain", {"step": 3})
    assert second.events()[-1]["prev_hash"] == head_after_first

    ok, err = second.verify()
    assert ok is True
    assert err is None

    # A third instance still sees a fully intact, ordered chain.
    third = AuditChain("CASE-005", chain_path)
    assert third.head_hash() == third_hash
    assert [e["seq"] for e in third.events()] == [0, 1, 2]
    assert third.verify() == (True, None)
