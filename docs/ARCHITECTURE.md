# Architecture

> Placeholder — to be filled during the build week.

## Overview

DFIR Co-pilot is a multi-agent digital forensics assistant:

- **Backend:** Five Band agents (Python, Band SDK, Gemini) run via `scripts/run_all.py`
- **Evidence:** Pre-built case JSON bundles in `data/cases/`
- **Audit:** SHA-256 hash chain (`lib/audit_trail.py`) — append-only, tamper-evident
- **Frontend:** Static HTML viewer in `viewer/` — reads completed case output JSON

## Data flow

1. Human enters Band room → Liaison conducts intake and collection planning
2. Classifier routes evidence → specialists analyze and post structured findings
3. Captain synthesizes debate → issues verdict with MITRE mapping
4. Liaison drafts human-facing report → case file written to `data/outputs/`
5. Viewer renders case file + audit chain for investigators and judges

See [AGENT_CONTRACTS.md](AGENT_CONTRACTS.md) for cross-track schemas (locked Wednesday morning).
