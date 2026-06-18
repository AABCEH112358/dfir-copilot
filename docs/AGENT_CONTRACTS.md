# Agent Data Contracts

> **These contracts are LOCKED after this commit. Any change requires both tracks to sync.**
>
> This document is the shared source of truth across both tracks. The investigator
> track (`lib/`) produces these structures; David's viewer track consumes them.
> A copy of this file is mirrored at `docs/AGENT_CONTRACTS.md` in David's repo and
> the two must be kept byte-identical. Do not change a field name, type, or
> enum value on one side without updating the other in the same coordinated change.

These five contracts define every cross-track payload:

| # | Contract | Produced by | Consumed by |
|---|----------|-------------|-------------|
| 1 | `AuditChainEvent` | `lib/audit_trail.py` (`AuditChain.append`) | Anyone verifying the chain; `CaseFile.audit_chain_path` |
| 2 | `StructuredFinding` | Specialists | Captain, Liaison report, `CaseFile.all_findings` |
| 3 | `CaptainVerdict` | Captain | Liaison report, `CaseFile.captain_verdict` |
| 4 | `LiaisonReport` | Liaison | Human investigator, `CaseFile.liaison_report_md` |
| 5 | `CaseFile` | Liaison (on case close) | David's viewer |

---

## 1. AuditChainEvent

One line in the JSON Lines audit chain. Defined and produced by
[`lib/audit_trail.py`](../lib/audit_trail.py) via `AuditChain.append()`. The chain
is tamper-evident: each event's `hash` is `sha256(json.dumps(<all fields except
hash>, sort_keys=True))`, and `prev_hash` links to the previous event's `hash`.
The `prev_hash` of `seq` 0 is 64 zero characters (`AuditChain` genesis value).

**Fields**

- `seq` (int) — 0-based sequence number, contiguous and increasing.
- `timestamp` (str) — ISO 8601, UTC (`datetime.now(timezone.utc).isoformat()`).
- `event_type` (str) — one of the canonical `EVENT_TYPES` (not enforced by the lib).
- `agent_id` (str) — which agent appended the event.
- `payload` (object) — event-specific body.
- `prev_hash` (str) — sha256 hex of the previous event (64 zeros for `seq` 0).
- `hash` (str) — sha256 hex of all other fields with sorted keys.

**Canonical `event_type` values** (from `audit_trail.EVENT_TYPES`):
`CASE_OPENED`, `COLLECTION_PLAN_ISSUED`, `EVIDENCE_RECEIVED`,
`EVIDENCE_CLASSIFIED`, `SPECIALIST_FINDING`, `SPECIALIST_CHALLENGE`,
`CAPTAIN_REDIRECT`, `CAPTAIN_VERDICT`, `REPORT_DRAFTED`, `CASE_SEALED`.

**Example**

```json
{
  "seq": 4,
  "timestamp": "2026-06-17T16:42:11.084213+00:00",
  "event_type": "SPECIALIST_FINDING",
  "agent_id": "DFIR-HostForensics",
  "payload": {
    "finding_summary": "LockB1D ransomware confirmed on FS-CORE-01",
    "confidence": "high"
  },
  "prev_hash": "9f2c4a1b6d8e0f3a5c7b9d1e2f4a6c8b0d2e4f6a8c0b2d4e6f8a0c2e4b6d8f0a",
  "hash": "1a3c5e7b9d0f2a4c6e8b0d2f4a6c8e0b1d3f5a7c9e1b3d5f7a9c1e3b5d7f9a0c"
}
```

---

## 2. StructuredFinding

What a specialist posts to the room when they have a verdict-quality finding.
`evidence_refs` use the `category/key` addressing scheme into the case's
`evidence_bundle` (e.g. `encrypted_sample/0`, `ransom_note/text_content`).
`confidence` is one of `low | medium | high`.

```json
{
  "kind": "structured_finding",
  "specialist": "DFIR-HostForensics",
  "case_id": "DFIR-2026-001",
  "findings": [
    {
      "summary": "Files were encrypted by the LockB1D ransomware variant, renaming targets with a .lock_b1d extension.",
      "evidence_refs": ["encrypted_sample/0", "ransom_note/text_content"],
      "mitre_techniques": ["T1486"],
      "confidence": "high"
    },
    {
      "summary": "A malicious svchost.exe ran from C:\\Windows\\Temp with an unexpected parent process on FS-CORE-01.",
      "evidence_refs": ["memory_artifacts/FS-CORE-01"],
      "mitre_techniques": ["T1036.005"],
      "confidence": "medium"
    }
  ],
  "open_questions": [
    "Was the svc_backup NTLM hash used for lateral movement before encryption?"
  ]
}
```

**Field reference**

- `kind` (str) — always `"structured_finding"`.
- `specialist` (str) — the posting specialist's agent id.
- `case_id` (str) — the case this finding belongs to.
- `findings` (array) — one or more finding objects:
  - `summary` (str) — one sentence.
  - `evidence_refs` (array<str>) — `category/key` references into the evidence bundle.
  - `mitre_techniques` (array<str>) — MITRE ATT&CK technique IDs.
  - `confidence` (str) — `low | medium | high`.
- `open_questions` (array<str>) — what would change the specialist's confidence.

---

## 3. CaptainVerdict

The Captain's final structured verdict consolidating all specialist findings.

```json
{
  "kind": "captain_verdict",
  "case_id": "DFIR-2026-001",
  "classification": "Double-extortion ransomware incident",
  "subtype": "LockB1D (LockBit-affiliated variant)",
  "threat_actor_attribution": {
    "group": "LockB1D affiliate (unattributed operator)",
    "confidence": "medium"
  },
  "initial_access_vector": "Spearphishing attachment with malicious Office macro to a finance user on 2026-06-01.",
  "mitre_techniques": [
    {
      "id": "T1566.001",
      "name": "Phishing: Spearphishing Attachment",
      "evidence": "edr_alerts/0 — WINWORD.EXE spawning encoded PowerShell on WS-FIN-014."
    },
    {
      "id": "T1486",
      "name": "Data Encrypted for Impact",
      "evidence": "encrypted_sample/0-2 — .lock_b1d files with LOCKB1D header."
    },
    {
      "id": "T1567.002",
      "name": "Exfiltration Over Web Service",
      "evidence": "network_traffic — 89.4 GB outbound to files.cdn-cache-prod-447.com on 2026-06-13."
    }
  ],
  "immediate_actions": [
    "Keep the network isolated at the edge; do not reboot acquired hosts.",
    "Rotate the svc_backup service account and all domain admin credentials."
  ],
  "evidence_preserved": [
    "encrypted_sample/0",
    "encrypted_sample/1",
    "memory_artifacts/FS-CORE-01",
    "ransom_note/text_content"
  ],
  "regulatory_obligations": [
    "Ohio Data Protection Act breach-notification assessment (customer data exfiltrated)."
  ],
  "human_followup_recommended": [
    "Engage breach counsel before any ransom-payment discussion with the board."
  ],
  "audit_chain_head": "1a3c5e7b9d0f2a4c6e8b0d2f4a6c8e0b1d3f5a7c9e1b3d5f7a9c1e3b5d7f9a0c"
}
```

**Field reference**

- `kind` (str) — always `"captain_verdict"`.
- `case_id` (str).
- `classification` (str) — one-line incident type.
- `subtype` (str).
- `threat_actor_attribution` (object) — `{ "group": str, "confidence": str }`.
- `initial_access_vector` (str).
- `mitre_techniques` (array) — each `{ "id": str, "name": str, "evidence": str }`.
- `immediate_actions` (array<str>).
- `evidence_preserved` (array<str>) — `category/key` references.
- `regulatory_obligations` (array<str>).
- `human_followup_recommended` (array<str>).
- `audit_chain_head` (str) — sha256 hex from `AuditChain.head_hash()` at verdict time.

---

## 4. LiaisonReport

The human-facing final report, authored as **Markdown** (stored as a string in
`CaseFile.liaison_report_md`). It is plain-language and written for the
investigator in the room, not for other agents. The document MUST contain these
sections, in this order:

1. `## Summary for the Investigator`
2. `## What Happened (plain language)`
3. `## MITRE Mapping with Explanations`
4. `## Evidence Catalog`
5. `## Recommended Next Steps`
6. `## Regulatory Clocks`
7. `## Chain of Custody`

**Example**

```markdown
# Incident Report: DFIR-2026-001 — Meridian Logistics Ransomware

## Summary for the Investigator
Your network was hit by LockB1D ransomware. Before encrypting your files the
attackers stole roughly 84 GB of customer data, so this is a "double-extortion"
case: paying the ransom would not undo the data theft. The clock on Ohio breach
notification is already running.

## What Happened (plain language)
On June 1 a finance employee opened a malicious email attachment. That gave the
attackers a foothold. They quietly stayed for two weeks, stole data on June 13,
and triggered the encryption on the morning of June 15.

## MITRE Mapping with Explanations
- **T1566.001 — Spearphishing Attachment**: The intrusion started with a booby-trapped
  document opened in Word.
- **T1486 — Data Encrypted for Impact**: Your files were encrypted and renamed `.lock_b1d`.
- **T1567.002 — Exfiltration Over Web Service**: 89.4 GB left your network before encryption.

## Evidence Catalog
| Reference | What it is |
|-----------|------------|
| `ransom_note/text_content` | The ransom note left on desktops |
| `encrypted_sample/0` | Encrypted Q2 freight invoices file |
| `memory_artifacts/FS-CORE-01` | Memory image showing the malicious process |

## Recommended Next Steps
1. Keep the network isolated; do not reboot the acquired servers.
2. Rotate the `svc_backup` service account and domain admin credentials.
3. Engage breach counsel before any payment discussion.

## Regulatory Clocks
- **Ohio Data Protection Act**: Notification assessment required now that customer
  data exfiltration is confirmed.

## Chain of Custody
All actions in this case are recorded in a tamper-evident SHA-256 hash chain.
- Audit chain file: `data/outputs/DFIR-2026-001.audit.jsonl`
- Audit chain head: `1a3c5e7b9d0f2a4c6e8b0d2f4a6c8e0b1d3f5a7c9e1b3d5f7a9c1e3b5d7f9a0c`
```

---

## 5. CaseFile

The JSON dropped into `data/outputs/` after a case completes. **This is the file
David's viewer reads to render the case pages.** The filename convention is
`data/outputs/{case_id}.json`.

**Top-level keys**

- `case_id` (str)
- `opened_at` (str) — ISO 8601 UTC.
- `closed_at` (str) — ISO 8601 UTC.
- `case_brief_md` (str) — the rendered global case brief Markdown.
- `all_findings` (array<StructuredFinding>) — every finding posted during the case.
- `captain_verdict` (CaptainVerdict) — the final verdict object.
- `liaison_report_md` (str) — the human-facing report Markdown.
- `audit_chain_path` (str) — path to the JSON Lines audit chain for this case.

**Example**

```json
{
  "case_id": "DFIR-2026-001",
  "opened_at": "2026-06-15T11:00:03+00:00",
  "closed_at": "2026-06-15T14:22:47+00:00",
  "case_brief_md": "# Case Brief: DFIR-2026-001\n\n## Incident Summary\n...",
  "all_findings": [
    {
      "kind": "structured_finding",
      "specialist": "DFIR-HostForensics",
      "case_id": "DFIR-2026-001",
      "findings": [
        {
          "summary": "Files were encrypted by the LockB1D ransomware variant.",
          "evidence_refs": ["encrypted_sample/0", "ransom_note/text_content"],
          "mitre_techniques": ["T1486"],
          "confidence": "high"
        }
      ],
      "open_questions": []
    }
  ],
  "captain_verdict": {
    "kind": "captain_verdict",
    "case_id": "DFIR-2026-001",
    "classification": "Double-extortion ransomware incident",
    "subtype": "LockB1D (LockBit-affiliated variant)",
    "threat_actor_attribution": { "group": "LockB1D affiliate", "confidence": "medium" },
    "initial_access_vector": "Spearphishing attachment with malicious Office macro.",
    "mitre_techniques": [
      { "id": "T1486", "name": "Data Encrypted for Impact", "evidence": "encrypted_sample/0-2" }
    ],
    "immediate_actions": ["Keep the network isolated; do not reboot acquired hosts."],
    "evidence_preserved": ["encrypted_sample/0", "memory_artifacts/FS-CORE-01"],
    "regulatory_obligations": ["Ohio Data Protection Act breach-notification assessment."],
    "human_followup_recommended": ["Engage breach counsel before ransom discussion."],
    "audit_chain_head": "1a3c5e7b9d0f2a4c6e8b0d2f4a6c8e0b1d3f5a7c9e1b3d5f7a9c1e3b5d7f9a0c"
  },
  "liaison_report_md": "# Incident Report: DFIR-2026-001 ...",
  "audit_chain_path": "data/outputs/DFIR-2026-001.audit.jsonl"
}
```
