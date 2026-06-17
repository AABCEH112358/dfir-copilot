# Winning Strategy — Hackathon Podium Playbook

**Branch:** `david`  
**Track:** Band of Agents 2026, Track 3 (Regulated & High-Stakes Workflows)  
**Goal:** Move from competitive (~7.3/10) to podium by making four things undeniable in 5 minutes.

---

## Killer thesis (use everywhere)

> When Host and Network disagree, Band is the investigation room — agents challenge each other, the Captain forces correlation, and every action is hash-chained so a judge can verify chain of custody in the browser.

Every slide, video frame, and README paragraph should support this sentence.

---

## What judges score

| Criterion | What wins | What loses |
|-----------|-----------|------------|
| **Application of Technology** | Visible handoffs, debate, re-scope *in Band* | 5 agents that feel like one chatbot with @tags |
| **Presentation** | 30s hook → 2min wow → 30s proof | Long architecture monologue, broken demo |
| **Business Value** | Named user, named pain, named output | "Cyber is hard" without a workflow |
| **Originality** | "Only multi-agent could do this" moment | Linear intake → analyze → report |

**Rough current scores (idea + plan):** Application 8.0 · Business 7.5 · Originality 7.0 · Presentation 6.5 (unproven) · Track 3 fit 8.5

---

## Five moves that win

### 1. Own one unforgettable moment (Case 002)

**The moment:** Host says *no compromise on endpoint* while Network says *clear exfil* → Captain @mentions both with a **specific** correlation question → reconciliation → verdict.

**Execution:**
- Rehearse Case 002 until **3 clean runs in a row** before recording (Anes).
- Video devotes **60–90 seconds** to this debate uninterrupted.
- Add on-screen labels in edit: `HostForensics`, `NetworkForensics`, `Captain redirect`.
- If agents agree too easily: add prompt directive — *"Challenge anything the other specialist asserted that you have not personally confirmed from your own evidence."*

**Without this moment → top third. With it → podium.**

---

### 2. Make the audit chain the magic trick (David — B-4)

Most Track 3 projects *claim* traceability. We **prove** it.

- Viewer: vertical hash chain + **"Chain Verified ✓"** badge (SubtleCrypto SHA-256).
- Video: 20-second zoom on verified badge after Case 002.
- Optional demo: tamper one JSONL line → badge flips to **"Chain Broken at seq N"**.

---

### 3. Show Band as coordination, not chat decoration

| Stage | Judge should see in Band |
|-------|--------------------------|
| Intake | Liaison posts **collection plan table** + `case_brief.md` |
| Handoff | Classifier @mentions specialists with **different packets** |
| Investigation | Specialists post **StructuredFinding** JSON |
| Conflict | Captain **redirect** with targeted question |
| Re-scope | Captain → Liaison → human for round 2 collection (Case 003) |
| Close | CaptainVerdict → Liaison human report |

**Viewer add (B-3/B-4):** "What Happened" tab mirrors Band room as audit timeline.  
**Slides (B-7):** Slide 4 = **non-linear loop** — explicitly not a pipeline.

---

### 4. Nail presentation like a product launch (David — B-7, B-8)

**Video structure (strict, ~4 min):**

| Time | Content |
|------|---------|
| 0:00–0:20 | Hook: panicked office worker quote |
| 0:20–0:45 | Problem + persona (4-person cybercrime unit, 200 cases/year) |
| 0:45–1:00 | 5-agent diagram, Band in center |
| 1:00–2:30 | **Case 002 live recording (hero)** |
| 2:30–3:00 | Case 003 re-scope (10 sec) |
| 3:00–3:20 | Audit chain verified in viewer |
| 3:20–3:45 | Track 3: custody, MITRE, regulatory clocks |
| 3:45–4:00 | Demo URL + GitHub |

**Submission assets:**
- Cover image: dark theme, 5 agents + hash chain (not stock clip art)
- README: **"Try it"** judge steps
- `docs/DEMO_SCRIPT.md`: exact Band room messages + what to watch for
- Live demo URL loads in <3 seconds

**Business value numbers for slides:**
- Pain: first 4 hours = intake + "what do we collect?" not analysis
- Outcome: collection plan in minutes; MITRE-mapped case file with verified custody trail

---

### 5. Differentiate vs competition

| Competitor pattern | Our counter |
|--------------------|-------------|
| Compliance doc reviewer | Investigation with debate + re-scope |
| Linear approval workflow | Non-linear loop with human re-collection |
| "We have 5 agents" | Case 002 proves productive disagreement |
| Traceability claims | Browser-verified hash chain |
| Dev/coding agents | Native Track 3 — custody, escalation, regulated output |

**Do not add a 6th agent** unless Case 002 is already solid 3x in a row.

---

## Execution priority (drop everything else if tight)

| Priority | Task | Owner |
|----------|------|-------|
| **P0** | Case 002 debate works reliably (3 runs) | Anes |
| **P0** | Video with Case 002 as hero | David |
| **P0** | Live viewer + audit chain verify | David |
| **P0** | Live Band room / Fly.io agents | Both |
| **P1** | Case 003 re-scope (even once) | Anes |
| **P1** | 10-slide deck + cover image | David |
| **P1** | Judge demo script in README + DEMO_SCRIPT.md | David |
| **P2** | Case 001 polish | Anes |
| **P2** | SECURITY.md, CONTRIBUTING.md | David if early |
| **Skip** | 6th agent, real SIEM, dual US+CA framing | — |

---

## Podium checklist (Thursday night)

- [ ] Judge opens demo URL → Case 002 → real output + **Chain Verified ✓**
- [ ] Judge opens Band room → agents online → opening message → collection plan within 2 min
- [ ] Video shows **disagreement + Captain redirect** without narration needed
- [ ] README: agent roles + Band's role in one diagram
- [ ] Cover image looks intentional (dark theme, on-brand)
- [ ] Final smoke test on **hosted** infra (not localhost) for all 3 cases

---

## Outcome matrix

| Execution | Realistic result |
|-----------|------------------|
| Case 002 on video + verified audit chain + live URL | **Track 3 podium** (~top 3) |
| Above + Case 003 re-scope + judge script | **Overall winner** candidate |
| Agents work but debate weak / hosting breaks | Top third at best |
| Great slides, broken demo | Podium unlikely |

---

## 60-second pitch template (B-2)

1. **Problem:** Under-resourced cybercrime units; evidence collection is the bottleneck.
2. **Solution:** Five Band agents — Liaison talks to humans, Classifier routes, Host/Network analyze, Captain synthesizes with MITRE.
3. **Track 3 fit:** SHA-256 audit chain = chain of custody; structured findings; regulatory-aware reports.
4. **Demo:** Static viewer proves custody; live Band room for judge interaction.
5. **Wow:** Specialists disagree; Captain forces correlation — only possible with multi-agent coordination.

---

*See also: [B2_READING_CHECKLIST.md](B2_READING_CHECKLIST.md), [DEMO_SCRIPT.md](DEMO_SCRIPT.md), build playbook PART 2.*
