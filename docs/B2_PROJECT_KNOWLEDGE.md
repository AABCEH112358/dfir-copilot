# B-2 Project Knowledge — Everything David Needs to Know

**Purpose:** Single reference for Phase 1 reading. Read this first; use linked sources for depth.  
**Goal when done:** Explain the project in 60 seconds and know what you're building Wednesday onward.

---

## 1. What we are building

**DFIR Co-pilot** is an AI-powered digital forensics assistant for under-resourced cybercrime units, regional CERTs, and small IR teams who cannot afford enterprise DFIR platforms (CrowdStrike-scale).

A panicked office worker messages: *"Our computers are locked, red text, they want bitcoin."* Five agents in a **Band room** turn that into a complete forensic case file — collection plan, specialist analysis, MITRE ATT&CK mapping, human-readable report, and a **SHA-256 hash-chained audit trail** (chain of custody). The human never needs to know what an event log is.

| Detail | Value |
|--------|-------|
| Hackathon | [Band of Agents 2026](https://lablab.ai/ai-hackathons/band-of-agents-hackathon) |
| Track | **Track 3 — Regulated & High-Stakes Workflows** |
| Deadline | June 19, 2026 EOD |
| Prize pool | $10,000+ (top 3: $3,500 / $2,500 / $1,500) |
| Our repo | `dfir-copilot` (viewer, hosting, slides, video, submission) |
| Anes's repo | `dfir-investigator` (agents, prompts, audit library, case JSONs) |

---

## 2. The problem (why judges should care)

**Who hurts:** 4-person regional cybercrime units handling 200+ cases/year; one-person SecOps at SaaS startups; municipal IT with no DFIR bench.

**The bottleneck is not analysis — it is evidence collection and coordination.** When an incident hits, the first hours are spent figuring out *what to preserve, where to find it, and how to hand it off* without breaking chain of custody. Non-technical staff on scene make mistakes. Investigators repeat intake interviews. Specialists cannot start until artifacts arrive in the right shape.

**What we deliver:** Minutes-to-plan collection guidance; automated routing to host/network specialists; debate and synthesis; a tamper-evident custody trail; a case file a human investigator can act on and a regulator can trace.

**Slide-ready numbers:** First ~4 hours of many incidents = intake + collection coordination, not deep analysis. We compress that coordination phase dramatically.

---

## 3. The five agents

All agents run through **Band** (shared coordination layer). Humans only talk to the Liaison.

| Agent | Job | Model | Key behavior |
|-------|-----|-------|--------------|
| **DFIR-Liaison** | Single human-facing contact | Gemini 2.5 Flash | Intake interview → 4-part collection plan → acknowledges uploads → drafts final report. **Never speculates** on in-flight findings before Captain verdict. |
| **DFIR-Classifier** | Evidence router | Gemini 2.5 Flash | Reads evidence categories, assigns host/network/both, writes **per-specialist handoff packets**. Does not investigate. |
| **DFIR-HostForensics** | Endpoint specialist | Gemini 2.5 Flash | Logs, registry, AV, persistence, lateral movement *on the machine*. Cites evidence; maps MITRE; posts StructuredFinding. |
| **DFIR-NetworkForensics** | Network specialist | Gemini 2.5 Flash | Firewall, DNS, VPN, C2, exfil *on the wire*. Same discipline as Host. |
| **DFIR-Captain** | Synthesizer & judge | Gemini 2.5 **Pro** | Watches debate, redirects loops, **re-scopes** investigation when evidence shape is wrong, issues CaptainVerdict with MITRE. Only Pro user (50 req/day free tier — enough). |

**Why five, not one:** Real DFIR splits host vs network expertise; they **disagree** in real cases; a captain must force correlation; the human must re-collect when scope changes. That requires distinct agents coordinating through Band — not a single chatbot.

---

## 4. End-to-end workflow (what happens in a case)

```
Human (panicked) → Liaison (intake + collection plan + case_brief.md)
       ↓
Human ("uploaded server_logs, firewall_logs…") → Liaison acknowledges
       ↓
Liaison @Classifier → Classifier routes evidence → specialist packets
       ↓
Host + Network analyze → StructuredFinding JSON → @Captain
       ↓
Captain: agree? → verdict  |  disagree? → redirect both with specific question
       ↓
Captain: wrong scope? → @Liaison → human collects more (Case 003 pattern)
       ↓
CaptainVerdict → Liaison drafts human report → CaseFile.json + audit.jsonl
       ↓
David's viewer renders case file + verified hash chain
```

**This is intentionally non-linear.** Not: prompt → one agent → done. The loop back to the human for more evidence is load-bearing for both Band and Track 3.

---

## 5. Two-document context model

Agents stay within context limits while sharing case understanding:

| Document | Author | When | Purpose |
|----------|--------|------|---------|
| `case_brief.md` | Liaison | Case open (once) | Global "what is this case" — incident, victim org, human contact, intake summary, phase status |
| Per-specialist packet | Classifier | Each evidence routing | "Your slice, your artifacts, who else has what, how to coordinate" |

---

## 6. The three demo cases

Case JSONs live in `data/cases/` on Anes's side. **Get copies from Anes** — read them when available; they explain the system better than prose.

### Case 001 — Acme Ransomware (easy)

| Field | Detail |
|-------|--------|
| Org | Acme Accounting, Calgary, ~35 people |
| Scenario | LockBit-style ransomware, black screen, red text, bitcoin demand |
| Demo purpose | **Happy path** — clean end-to-end: intake → collection → classify → findings → verdict → report |
| MITRE anchor | **T1486** — Data Encrypted for Impact |
| Human opening | *"Our office computers are all locked… IT isn't picking up… insurance told me to contact you…"* |

### Case 002 — Vector Insider Threat (medium) — **THE HERO CASE**

| Field | Detail |
|-------|--------|
| Org | Vector Aerospace, Mississauga, defense supplier |
| Scenario | Departing engineer stealing IP |
| Demo purpose | **Non-linear debate** — Host: "no compromise indicators on endpoint." Network: "clear exfil to personal Gmail." Captain forces correlation. **This is the video money shot.** |
| MITRE anchors | **T1078** Valid Accounts · **T1052.001** Exfiltration Over USB · **T1567** Exfiltration to Cloud Storage |
| Why it wins | Proves Band is an investigation room, not a pipeline. Judges must *see* disagreement + Captain redirect. |

### Case 003 — TrueLedger Supply Chain (hard)

| Field | Detail |
|-------|--------|
| Org | TrueLedger SaaS, Vancouver |
| Scenario | Compromised npm dependency exfiltrating customer data |
| Demo purpose | **Mid-investigation re-scope** — initial intrusion hypothesis is wrong; Captain expands scope; Liaison runs **multiple collection rounds**. Blast radius: 14 → 1,247 customers. |
| MITRE anchor | **T1195.002** Supply Chain Compromise |
| Why it wins | Shows Captain authority to change investigation direction — another Band-native pattern. |

**Dev note:** Each case JSON has a `ground_truth` block for QA. Agents and viewer **never** expose it.

---

## 7. Track 3 fit (regulated & high-stakes)

Track 3 is for workflows where **review, traceability, escalation, and careful decisions** matter. Examples on the hackathon page include healthcare, finance, legal, insurance — and **cybersecurity investigation**.

| Real-world concept | Our implementation |
|--------------------|--------------------|
| Chain of custody | SHA-256 hash chain (`audit.jsonl`) — each event links to previous hash |
| Tamper evidence | Modify any past entry → chain breaks → viewer shows "Broken at seq N" |
| Escalation | Captain redirects debate; Liaison escalates to human for collection |
| Regulatory awareness | Liaison report includes regulatory clocks (PIPEDA, breach notification) |
| MITRE ATT&CK | Structured technique mapping with evidence citations |
| Human gate | Liaison won't speculate pre-verdict; human approves re-collection |

**Your killer differentiator:** Browser-side hash verification in the viewer (SubtleCrypto) — most teams *claim* traceability; you **prove** it.

---

## 8. Data contracts (what your viewer consumes)

Locked **Wednesday morning SYNC 1** with Anes. After lock, neither side changes schemas without syncing.

| Artifact | Producer | Your viewer uses it for |
|----------|----------|-------------------------|
| **CaseFile.json** | Liaison at case close | **Primary input** — all case pages load this from `viewer/data/` |
| **audit.jsonl** | All agents (append-only) | Audit Chain tab + "What Happened" timeline |
| **LiaisonReport.md** | Liaison | Summary tab (Markdown) |
| **CaptainVerdict** | Captain | MITRE mapping, classification, immediate actions |
| **StructuredFinding** | Host / Network | Evidence catalog, specialist sections |
| **AuditChainEvent** | audit library | One line in JSONL: seq, timestamp, event_type, agent_id, payload, prev_hash, hash |

### CaseFile top-level keys (viewer schema)

```
case_id, opened_at, closed_at, case_brief_md,
all_findings[], captain_verdict, liaison_report_md, audit_chain_path
```

### LiaisonReport sections (Markdown)

Summary for the Investigator · What Happened · MITRE Mapping with Explanations · Evidence Catalog · Recommended Next Steps · Regulatory Clocks · Chain of Custody

### Audit chain event types

`CASE_OPENED` · `COLLECTION_PLAN_ISSUED` · `EVIDENCE_RECEIVED` · `EVIDENCE_CLASSIFIED` · `SPECIALIST_FINDING` · `SPECIALIST_CHALLENGE` · `CAPTAIN_REDIRECT` · `CAPTAIN_VERDICT` · `REPORT_DRAFTED` · `CASE_SEALED`

---

## 9. Division of labor

### Anes owns (backend track)

- 5 Band agent implementations + prompts
- `lib/audit_trail.py`, `evidence_tools.py`, `case_brief.py`
- `scripts/run_all.py` (launches all agents)
- Case JSONs in `data/cases/`
- Demo recordings (OBS) → copies `case_*_output.json` + `audit.jsonl` to your `viewer/data/`
- Fly.io backend (you deploy B-6, he confirms agents work first)

### David owns (your track)

- **GitHub repo** (`dfir-copilot`) — public face for judges
- **Static viewer** (`viewer/`) — HTML/CSS/JS, Tailwind CDN, no build step
- **Hosting** — GitHub Pages or Netlify (viewer); Fly.io (agents, B-6)
- **Slides** (10 max, PDF) · **Video** (3–5 min, YouTube unlisted)
- **Submission** — cover image, demo URL, video URL, slides URL

### Three sync points

| When | What |
|------|------|
| **Wed AM — SYNC 1** | Lock `AGENT_CONTRACTS.md`; you copy to repo; reply "contracts locked" |
| **Wed PM — SYNC 2** | Watch Anes smoke test Case 001 in Band; flag schema mismatches immediately |
| **Fri AM — SYNC 3** | Joint final smoke test + lablab.ai submission |

---

## 10. Your build timeline (PART 2)

| Step | When | What |
|------|------|------|
| B-1 | Tue eve | Repo scaffold — **done** on `david` |
| B-2 | Tue eve | Read this doc + case JSONs when Anes sends |
| B-3 | Wed AM (~3h) | Viewer scaffold: index + 3 case pages + placeholder JSON |
| B-4 | Wed PM (~3h) | Audit chain visualization + SubtleCrypto verify + polish |
| B-5 | Thu AM (~1h) | Deploy viewer → demo URL in README |
| B-6 | Thu AM (~2h) | Deploy agents to Fly.io (after Wed smoke test passes) |
| B-7 | Thu PM (~2h) | 10-slide deck + PDF |
| B-8 | Thu night (~2–3h) | Video — Case 002 hero segment |

**Viewer pages:** Landing with 3 case cards + 5-agent diagram. Each case page: Summary · What Happened · MITRE · Evidence Catalog · Audit Chain · Recommended Actions. Dark theme; monospace for hashes.

---

## 11. MITRE ATT&CK — case cheat sheet

You do not need to memorize the matrix. Know these five for slides and video:

| ID | Name | Plain English | Case |
|----|------|---------------|------|
| **T1486** | Data Encrypted for Impact | Ransomware encrypts files for ransom | 001 |
| **T1078** | Valid Accounts | Attacker uses legitimate creds (insider / stolen account) | 002 |
| **T1052.001** | Exfiltration Over USB | Data copied out via USB device | 002 |
| **T1567** | Exfiltration to Cloud Storage | Data sent to personal Gmail, Dropbox, etc. | 002 |
| **T1195.002** | Supply Chain Compromise | Malicious code in a software dependency | 003 |

Reference: https://attack.mitre.org/matrices/enterprise/

---

## 12. How judges score us

Four criteria from the [hackathon page](https://lablab.ai/ai-hackathons/band-of-agents-hackathon):

| Criterion | Strong submission | Our answer |
|-----------|-------------------|------------|
| **Application of Technology** | Band is the coordination layer; visible handoffs & shared context | 5 agents, @mentions, packets, debate, re-scope — **must show on video** |
| **Presentation** | Problem, roles, Band flow, value — easy to grasp | Your video + viewer + judge demo script |
| **Business Value** | Real enterprise workflow; less manual coordination | Under-resourced units; collection bottleneck → case file |
| **Originality** | Beyond single chatbot / linear automation | Case 002 disagreement; Case 003 re-scope; verified hash chain |

**Minimum requirements:** ≥3 agents on Band (we have 5); Band is core to workflow, not a notification wrapper.

**Rough idea scores:** Application 8 · Business 7.5 · Originality 7 · Presentation TBD · Track 3 fit 8.5

Full podium playbook: [WINNING_STRATEGY.md](WINNING_STRATEGY.md)

---

## 13. Stack (what to name-drop)

| Layer | Tech |
|-------|------|
| Agent platform | [Band SDK](https://www.band.ai/) 1.0.0 |
| Models | Google Gemini 2.5 Flash (4 agents) + 2.5 Pro (Captain) |
| Backend | Python 3.13 |
| Audit chain | SHA-256 hash chain, JSON Lines |
| Viewer | Vanilla HTML/CSS/JS, Tailwind CDN |
| Agent hosting | Fly.io (~256MB, persistent process for WebSockets) |
| Viewer hosting | GitHub Pages or Netlify |
| Cost | ~$0–20 total; Gemini free tier; Band Pro free 1 month via `BANDHACK26` |

**Band import gotcha:** Docs may say `from thenvoi import …` — wrong. Use `from band import Agent`, `from band.adapters.gemini import GeminiAdapter`.

---

## 14. Your 60-second pitch (memorize this)

> Cybercrime units with four investigators and two hundred cases a year don't fail at analysis — they fail at **evidence collection**. Non-technical staff don't know what to preserve or how to maintain chain of custody.
>
> **DFIR Co-pilot** puts five AI agents in a Band room with the human investigator. The Liaison speaks plain English and produces a collection plan. The Classifier routes evidence. Host and Network specialists analyze and **debate** — in our insider-threat demo, Host sees no compromise while Network sees clear exfil, and the Captain forces them to correlate.
>
> Every action appends to a **SHA-256 audit chain** — real chain of custody. The completed case file renders in our viewer, where a judge can **verify the chain in the browser**.
>
> We built this for Track 3: regulated, high-stakes workflows where traceability and careful decisions matter. Live demo and GitHub in the submission.

---

## 15. What still needs to land from Anes

- [ ] Three case JSONs → copy to `data/cases/` (read before B-3 if possible)
- [ ] Final `docs/AGENT_CONTRACTS.md` → Wed SYNC 1
- [ ] Real `viewer/data/case_*_output.json` + `audit.jsonl` → Thu after demo runs
- [ ] Band room URL for "Play case" button
- [ ] `GEMINI_API_KEY` + `BAND_API_KEY` for Fly.io deploy (B-6)

---

## 16. Open decisions (not blocking you yet)

| Question | Options | Notes |
|----------|---------|-------|
| US vs Canadian framing | PIPEDA/RCMP vs FTC/CISA/state breach laws | Quick swap for video if judges skew US |
| Sixth agent (ThreatIntel) | Add only if Case 002 solid | Anes's call on day 3 |
| Hosting | GitHub Pages vs Netlify for viewer | Both fine; pick Thursday AM |

---

## 17. Key links

| Resource | URL |
|----------|-----|
| Hackathon | https://lablab.ai/ai-hackathons/band-of-agents-hackathon |
| Band app (register agents) | https://app.band.ai/agents |
| Band hacker guide | https://www.band.ai/hacker-guide |
| MITRE ATT&CK Enterprise | https://attack.mitre.org/matrices/enterprise/ |
| Hackathon Discord | https://discord.gg/lablabai |
| Anes's brief (local) | `~/Downloads/project_brief_for_david.md` |
| Build playbook (local) | `~/Downloads/build_playbook.md` — PART 2 = your steps |

---

## 18. B-2 done when

- [ ] You can deliver the 60-second pitch without notes
- [ ] You can draw the 5-agent workflow and where Band sits
- [ ] You can explain why Case 002 and Case 003 exist (debate vs re-scope)
- [ ] You know what CaseFile.json contains and which viewer tabs use which fields
- [ ] You know your Wed/Thu deliverables (B-3 through B-8)
- [ ] You've skimmed case JSONs once Anes shares them

---

*Next step: Phase 2 — [B-3 viewer scaffold](../viewer/) Wednesday morning. See [WINNING_STRATEGY.md](WINNING_STRATEGY.md) for what judges must see.*
