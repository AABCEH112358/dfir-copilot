"""SHA-256 hash chain library for DFIR case audit trails.

Provides a tamper-evident, append-only log of case events. Each event is
linked to the previous one via a SHA-256 hash chain, so any modification to a
past event invalidates every subsequent hash and is detectable by `verify()`.

The chain is persisted as JSON Lines (one JSON object per line), making it
easy to inspect, stream, and append to without rewriting the whole file.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

GENESIS_PREV_HASH = "0" * 64

# Canonical event types used throughout a DFIR case lifecycle. Documented for
# callers; intentionally not enforced by `append()` so the library stays
# flexible for custom event types.
EVENT_TYPES = [
    "CASE_OPENED",
    "COLLECTION_PLAN_ISSUED",
    "EVIDENCE_RECEIVED",
    "EVIDENCE_CLASSIFIED",
    "SPECIALIST_FINDING",
    "SPECIALIST_CHALLENGE",
    "CAPTAIN_REDIRECT",
    "CAPTAIN_VERDICT",
    "REPORT_DRAFTED",
    "CASE_SEALED",
]


def _compute_hash(event: dict) -> str:
    """Return the SHA-256 hash of an event, excluding its own `hash` field.

    The hash covers every field except `hash` itself, serialized as JSON with
    sorted keys to guarantee a stable, reproducible byte representation.
    """
    unhashed = {k: v for k, v in event.items() if k != "hash"}
    encoded = json.dumps(unhashed, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class AuditChain:
    """An append-only, hash-chained audit log for a single DFIR case."""

    def __init__(self, case_id: str, storage_path: Path) -> None:
        self.case_id = case_id
        self.storage_path = Path(storage_path)
        if not self.storage_path.exists():
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            self.storage_path.touch()

    def events(self) -> list[dict]:
        """Return all events in chain order."""
        if not self.storage_path.exists():
            return []
        events: list[dict] = []
        with self.storage_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
        return events

    def append(self, event_type: str, agent_id: str, payload: dict) -> str:
        """Append a new event to the chain and return its hash."""
        existing = self.events()
        if existing:
            seq = existing[-1]["seq"] + 1
            prev_hash = existing[-1]["hash"]
        else:
            seq = 0
            prev_hash = GENESIS_PREV_HASH

        event = {
            "seq": seq,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "agent_id": agent_id,
            "payload": payload,
            "prev_hash": prev_hash,
        }
        event["hash"] = _compute_hash(event)

        with self.storage_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event) + "\n")

        return event["hash"]

    def verify(self) -> tuple[bool, str | None]:
        """Walk the chain and confirm every hash and link is intact.

        Returns (True, None) when the chain is valid, otherwise
        (False, "broken at seq N") for the first event that fails.
        """
        prev_hash = GENESIS_PREV_HASH
        for idx, event in enumerate(self.events()):
            if event.get("seq") != idx:
                return False, f"broken at seq {idx}"
            if event.get("prev_hash") != prev_hash:
                return False, f"broken at seq {event.get('seq', idx)}"
            if _compute_hash(event) != event.get("hash"):
                return False, f"broken at seq {event.get('seq', idx)}"
            prev_hash = event["hash"]
        return True, None

    def head_hash(self) -> str:
        """Return the hash of the most recent event.

        Returns the genesis prev-hash (64 zeros) when the chain is empty.
        """
        events = self.events()
        if not events:
            return GENESIS_PREV_HASH
        return events[-1]["hash"]
