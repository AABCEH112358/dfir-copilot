# DFIR Co-pilot

**AI-powered digital forensics co-pilot for under-resourced cybercrime units.**

Built for the [Band of Agents Hackathon 2026](https://lablab.ai/ai-hackathons/band-of-agents-hackathon), Track 3 (Regulated & High-Stakes Workflows).

**Live demo:** [TBD — will update Thursday]

---

## The problem

Cybercrime units and small security teams are chronically understaffed. When an incident hits, the bottleneck is rarely analysis alone — it is **evidence collection**. Non-technical staff on the scene do not know what to preserve, where to find it, or how to hand it off without breaking chain of custody. Investigators spend hours on intake interviews and collection coordination before specialist work can begin.

DFIR Co-pilot puts a team of forensic agents in the room with the human investigator. One agent speaks human; the rest examine evidence, debate findings, and produce a verified audit trail — so under-resourced units can move from panic to structured response in minutes, not days.

---

## How it works

Five agents collaborate through [Band](https://www.band.ai/), orchestrated with the Band SDK and Google Gemini:

| Agent | Role |
|-------|------|
| **DFIR-Liaison** | Single point of contact for the human; intake, collection plans, final reports |
| **DFIR-Classifier** | Routes incoming evidence to the right specialists with targeted briefings |
| **DFIR-HostForensics** | Endpoint artifacts — IOCs, persistence, lateral movement |
| **DFIR-NetworkForensics** | Traffic, DNS, C2 callbacks, exfiltration patterns |
| **DFIR-Captain** | Watches specialist debate, redirects loops, issues verdict with MITRE mapping |

Every agent action appends to a **SHA-256 hash chain** — tamper-evident chain of custody for regulated workflows. Completed cases export to a static viewer for judges and investigators.

---

## Built for

- **Event:** Band of Agents Hackathon 2026
- **Track:** Track 3 — Regulated & High-Stakes Workflows
- **Platform:** [lablab.ai](https://lablab.ai/ai-hackathons/band-of-agents-hackathon)

---

## Repo structure

```
dfir-copilot/
├── agents/          # Band agent implementations (teammate track)
├── lib/             # Shared libraries — audit chain, evidence tools
├── data/
│   └── cases/       # Pre-built case scenario JSON bundles
├── viewer/          # Static case viewer (HTML/CSS/JS) — demo URL
├── docs/            # Architecture, agent contracts, demo script
└── deploy/          # Fly.io and hosting configs
```

---

## Built with

- Python 3.13
- [Band SDK](https://www.band.ai/) 1.0.0
- Google Gemini (2.5 Flash + 2.5 Pro)
- SHA-256 audit chains
- Vanilla HTML/CSS/JS viewer (Tailwind CDN)

---

## License

MIT — see [LICENSE](LICENSE).
