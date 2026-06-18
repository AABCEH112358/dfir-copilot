# DFIR Investigator

A multi-agent digital-forensics-and-incident-response (DFIR) system built on the Band platform. Five specialist AI agents collaborate in a shared room to investigate a real incident — coordinated by a human-facing Liaison, routed by a Classifier, analyzed by Host and Network specialists, and synthesized by a Captain — with every action recorded in a tamper-evident SHA-256 hash chain.

**Hackathon track:** Track 3 — Regulated & High-Stakes Workflows.

## What this system does, end to end

A human reports an incident in plain language to the **Liaison**. The Liaison conducts a structured intake, issues a collection plan, and acknowledges what arrives — pushing back gracefully on what can't be collected. When evidence is in hand, it hands the case to the **Classifier**, which routes each evidence category to the right specialist. **HostForensics** examines endpoint artifacts; **NetworkForensics** examines traffic, DNS, and exfiltration patterns. Each posts structured findings citing specific evidence and MITRE ATT&CK techniques. The **Captain** (running on Gemini Pro for stronger synthesis) watches the room, challenges any technique a specialist claims without evidence to back it, and only then issues a final verdict. The Liaison takes that verdict and translates it back to the human as a plain-language report. The case is sealed with a terminal audit event.

Every action — case opened, evidence received, evidence classified, finding posted, technique challenged, finding retracted, verdict issued, case sealed — is recorded in a single per-case JSONL hash chain where every entry's hash includes the previous entry's hash. Tamper with any earlier entry and the chain breaks at that point.

## The Track 3 differentiator: chain-of-custody on every action

The audit chain is the headline feature. Open `data/outputs/{case_id}/audit_chain.jsonl` and you can verify, with a 4-line Python check, that:

- No event has been edited since it was written
- No event has been inserted or removed between any two entries
- The verdict's `audit_chain_head` field matches the actual head of the chain — meaning the verdict can be cryptographically tied to the exact set of events the Captain reasoned over

This is the property a regulator, auditor, or opposing counsel asks for. It's also the property that lets the system be honest about its own limits: when the Captain refuses to rubber-stamp a claim, both the redirect AND the retraction are sealed into the chain.

### The demo's hero moment

In the case_001 run, the Captain challenged HostForensics's MITRE T1547.001 (registry-based persistence) claim. Reason: the specialist had inferred persistence from the ransom note rather than from direct execution evidence. HostForensics agreed and retracted. The final verdict contains 5 MITRE techniques — every one backed by specialist-cited evidence — and the audit chain preserves both the challenge (`CAPTAIN_REDIRECT` at seq 20) and the retraction (`SPECIALIST_CHALLENGE` at seq 21) before the verdict at seq 22. That sequence, in three audit events, is the system's value proposition.

## Architecture

```
                            ┌─────────────────────┐
                            │  Human investigator │
                            └──────────┬──────────┘
                                       │ (plain language, Band room)
                            ┌──────────▼──────────┐
                            │   DFIR-Liaison      │  Gemini Flash
                            │   intake, plan,     │
                            │   handoff, report   │
                            └──────────┬──────────┘
                                       │ @mentions
                            ┌──────────▼──────────┐
                            │   DFIR-Classifier   │  Gemini Flash
                            │   routes evidence   │
                            └─────┬──────────┬────┘
                                  │          │
                  ┌───────────────▼──┐   ┌───▼────────────────┐
                  │ DFIR-HostForensics│   │ DFIR-NetworkForensics│
                  │ Gemini Flash      │   │ Gemini Flash         │
                  │ endpoint, memory  │   │ traffic, DNS, exfil  │
                  └───────────────┬──┘   └───┬──────────────────┘
                                  │          │
                                  │  StructuredFindings
                                  │          │
                            ┌─────▼──────────▼────┐
                            │   DFIR-Captain      │  Gemini Pro
                            │   challenge, verdict│
                            └──────────┬──────────┘
                                       │ CaptainVerdict
                                       │
              ┌────────────────────────▼────────────────────────┐
              │   SHA-256 audit chain                            │
              │   (sealed across all 5 agents, CASE_SEALED)      │
              └──────────────────────────────────────────────────┘
```

## Five agents, five roles

| Agent | Model | Job |
|-------|-------|-----|
| DFIR-Liaison | gemini-2.5-flash | Single point of contact with the human. Intake, collection plan, push-back handling, final report. |
| DFIR-Classifier | gemini-2.5-flash | Routes evidence to the right specialist; flags cross-cutting categories to both. |
| DFIR-HostForensics | gemini-2.5-flash | Endpoint artifacts: event logs, registry, filesystem, memory, processes, persistence. |
| DFIR-NetworkForensics | gemini-2.5-flash | Wire-side evidence: traffic, DNS, firewall and VPN logs, C2 callbacks, exfil. |
| DFIR-Captain | **gemini-2.5-pro** | Synthesis and final authority. Challenges unsupported claims. Issues the sealed verdict. |

## Quick start

```bash
# 1. Clone, create venv, install
cd dfir-investigator
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Configure credentials in .env (see .env.example)
#    - One per-agent API key from the Band UI (5 keys)
#    - One Gemini API key
cp .env.example .env
# edit .env

# 3. Launch all five agents
python scripts/run_all.py

# 4. Open the Band room, add all 5 agents, and post your incident as the human:
#    @DFIR-Liaison <your message>
```

Three sample cases ship in `data/cases/`:

- `case_001_ransomware.json` — LockB1D ransomware with confirmed pre-encryption data exfiltration
- `case_002_insider_threat.json` — Departing senior engineer suspected of trade-secret theft (designed to force Host vs. Network correlation)
- `case_003_supply_chain.json` — Customer data on the dark web — initial web-app-compromise hypothesis is wrong, real vector is a compromised npm dependency (forces the Captain to re-scope)

## Output structure

For each investigated case, everything ends up under `data/outputs/{case_id}/`:

```
data/outputs/DFIR-2026-001/
├── case_brief.md              # global case briefing
├── packets/                   # per-specialist packets from the Classifier
│   ├── dfir-hostforensics.md
│   └── dfir-networkforensics.md
├── findings/                  # StructuredFindings posted by specialists
│   ├── dfir-hostforensics-{timestamp}.json
│   └── dfir-networkforensics-{timestamp}.json
├── captain_verdict.json       # the sealed verdict
├── liaison_report.md          # human-facing report
├── audit_chain.jsonl          # tamper-evident chain across all 5 agents
└── case_file.json             # consolidated record for the viewer
```

## How to verify the audit chain

```python
from pathlib import Path
from lib.audit_trail import AuditChain
chain = AuditChain("DFIR-2026-001", Path("data/outputs/DFIR-2026-001/audit_chain.jsonl"))
ok, broken_at = chain.verify()
print("verify:", ok, broken_at)
print("head_hash:", chain.head_hash())
print("event_count:", len(chain.events()))
```

The final event's hash should match the `audit_chain_head` field in `captain_verdict.json`.

## Tech stack

- **Band SDK** 1.0.0 (multi-agent platform, WebSocket + REST)
- **Google Gemini** API (gemini-2.5-flash for routing/intake/specialist work, gemini-2.5-pro for Captain synthesis)
- **Python 3.13**, stdlib for the audit chain (`hashlib`, `json`, `pathlib`) — zero external deps for the chain-of-custody library
- **PyYAML** for agent configuration
- **python-dotenv** for credential loading
- **pytest** for the test suite (23+ tests covering the audit chain, evidence tools, and case-brief renderer)

## Cross-track contracts

The agents on this repo collaborate with a viewer on a separate codebase via stable JSON / Markdown contracts documented in `docs/AGENT_CONTRACTS.md`:

- `AuditChainEvent` — every event written to the chain
- `StructuredFinding` — what specialists post
- `CaptainVerdict` — the sealed verdict
- `LiaisonReport` — the human-facing markdown report
- `CaseFile` — the consolidated record the viewer reads

These contracts were locked before either side wrote agent or viewer code, and any change requires both tracks to sync.

## Project structure

```
dfir-investigator/
├── agents/                 # the five agent modules
│   ├── liaison.py
│   ├── classifier.py
│   ├── host_forensics.py
│   ├── network_forensics.py
│   ├── captain.py
│   └── specialist_base.py  # shared engine for the two specialists
├── lib/                    # supporting libraries
│   ├── audit_trail.py      # SHA-256 hash chain
│   ├── evidence_tools.py   # case data loader, search, ground-truth stripping
│   ├── case_brief.py       # case briefing + report renderers
│   └── agent_credentials.py# per-agent credential loader
├── data/
│   ├── cases/              # the 3 case JSONs
│   └── outputs/            # per-case investigation artifacts
├── scripts/run_all.py      # launches all 5 agents in parallel
├── tests/                  # pytest suite
├── docs/AGENT_CONTRACTS.md # cross-track contracts (locked)
├── agent_config.yaml       # per-agent Band IDs + env var names
├── requirements.txt
└── .env.example
```

## Authors and credits

Built for the Band hackathon by [your team names]. Cases and agent prompts authored from scratch; Band SDK by Band Inc.; investigation domain expertise informed by public MITRE ATT&CK documentation and common DFIR practice.
