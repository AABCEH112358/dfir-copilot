#!/usr/bin/env python3
"""Generate viewer demo data for cases 002 and 003 with valid SHA-256 audit chains."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.audit_trail import GENESIS_PREV_HASH, _compute_hash  # noqa: E402

VIEWER_DATA = ROOT / "viewer" / "data"
ZERO = GENESIS_PREV_HASH


def build_chain(events_spec: list[tuple], base: datetime) -> list[dict]:
    lines: list[dict] = []
    prev = ZERO
    for i, (etype, agent, payload) in enumerate(events_spec):
        ts = (base + timedelta(minutes=i * 4)).isoformat().replace("+00:00", "Z")
        event = {
            "seq": i,
            "timestamp": ts,
            "event_type": etype,
            "agent_id": agent,
            "payload": payload,
            "prev_hash": prev,
        }
        event["hash"] = _compute_hash(event)
        lines.append(event)
        prev = event["hash"]
    return lines


def write_case(num: str, output: dict, chain: list[dict]) -> None:
    verdict_hash = next(
        e["hash"] for e in chain if e["event_type"] == "CAPTAIN_VERDICT"
    )
    output["captain_verdict"]["audit_chain_head"] = verdict_hash
    output["audit_chain_head"] = chain[-1]["hash"]
    out_path = VIEWER_DATA / f"case_{num}_output.json"
    audit_path = VIEWER_DATA / f"case_{num}_audit.jsonl"
    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    audit_path.write_text(
        "\n".join(json.dumps(e) for e in chain) + "\n", encoding="utf-8"
    )
    ok = all(
        _compute_hash(e) == e["hash"] and e["prev_hash"] == (chain[i - 1]["hash"] if i else ZERO)
        for i, e in enumerate(chain)
    )
    print(f"case_{num}: {len(chain)} events, verify={ok}, head={chain[-1]['hash'][:16]}...")


def case_002() -> None:
    base = datetime(2026, 6, 12, 14, 0, 0, tzinfo=timezone.utc)
    chain = build_chain(
        [
            ("CASE_OPENED", "DFIR-Liaison", {"incident_type": "Insider Threat"}),
            (
                "COLLECTION_PLAN_ISSUED",
                "DFIR-Liaison",
                {
                    "plan_items": [
                        "Workstation Access Logs",
                        "USB Device History",
                        "Print Logs",
                        "Email Metadata",
                        "Cloud Egress Logs",
                        "DNS Queries",
                        "VPN Session Logs",
                        "Memory Image",
                        "HR Records",
                    ]
                },
            ),
            ("EVIDENCE_RECEIVED", "DFIR-Liaison", {"artifact": "workstation_access_logs"}),
            ("EVIDENCE_RECEIVED", "DFIR-Liaison", {"artifact": "usb_device_history"}),
            ("EVIDENCE_RECEIVED", "DFIR-Liaison", {"artifact": "cloud_egress_logs"}),
            ("EVIDENCE_RECEIVED", "DFIR-Liaison", {"artifact": "memory_artifacts"}),
            (
                "EVIDENCE_CLASSIFIED",
                "DFIR-Classifier",
                {"routed_to": ["DFIR-HostForensics"], "category": "workstation_access_logs"},
            ),
            (
                "SPECIALIST_FINDING",
                "DFIR-HostForensics",
                {"finding_path": "data/outputs/DFIR-2026-002/findings/host-initial.json", "num_findings": 1},
            ),
            (
                "EVIDENCE_CLASSIFIED",
                "DFIR-Classifier",
                {"routed_to": ["DFIR-NetworkForensics"], "category": "cloud_egress_logs"},
            ),
            (
                "SPECIALIST_FINDING",
                "DFIR-NetworkForensics",
                {"finding_path": "data/outputs/DFIR-2026-002/findings/network-initial.json", "num_findings": 1},
            ),
            (
                "EVIDENCE_CLASSIFIED",
                "DFIR-Classifier",
                {"routed_to": ["DFIR-HostForensics"], "category": "memory_artifacts"},
            ),
            (
                "SPECIALIST_FINDING",
                "DFIR-HostForensics",
                {"finding_path": "data/outputs/DFIR-2026-002/findings/host-memory.json", "num_findings": 1},
            ),
            (
                "CAPTAIN_REDIRECT",
                "DFIR-Captain",
                {
                    "audience": "DFIR-HostForensics",
                    "directive": "Correlate your after-hours access windows with NetworkForensics cloud upload sessions on 2026-05-28 through 2026-06-06. Examine PowerShell history in the memory image for staged compression before upload.",
                    "reason": "Host reports no bulk exfiltration; Network confirms ~13.4 GB to personal Google Drive. The staging mechanism must be on the endpoint.",
                },
            ),
            (
                "SPECIALIST_CHALLENGE",
                "DFIR-HostForensics",
                {
                    "challenged_specialist": "DFIR-HostForensics",
                    "challenge": "Revised assessment: PowerShell history shows scripted enumeration of IP_drafts, assay raw data (BGX-119/122/141), and vendor contracts, 7-Zip encryption, and staging file deletion. File-access telemetry alone undercounted exfil volume.",
                    "evidence_refs": ["memory_artifacts", "workstation_access_logs"],
                },
            ),
            (
                "CAPTAIN_VERDICT",
                "DFIR-Captain",
                {
                    "verdict_path": "data/outputs/DFIR-2026-002/captain_verdict.json",
                    "classification": "Confirmed Insider Data Theft",
                    "num_techniques": 6,
                },
            ),
            (
                "REPORT_DRAFTED",
                "DFIR-Liaison",
                {"report_path": "data/outputs/DFIR-2026-002/liaison_report.md"},
            ),
            (
                "CASE_SEALED",
                "DFIR-Liaison",
                {"final": True, "report_path": "data/outputs/DFIR-2026-002/liaison_report.md"},
            ),
        ],
        base,
    )

    brief = """# Case Brief: DFIR-2026-002

## Incident Summary
Dr. Lena Voss, Principal Scientist, left BioGenix Therapeutics on June 10, 2026 after a four-week notice period. She is joining Helion Biopharma, a direct competitor. Leadership suspects proprietary research may have been taken during the notice window (May 13–June 10).

## Victim Organization
- Name: BioGenix Therapeutics, Inc.
- Industry: Pre-clinical biotech (oncology immunomodulators)
- Size: 247 employees
- Location: Cambridge, Massachusetts, USA

## Human Contact
- Name: Dr. Marcus Chen
- Role: Co-founder and CEO

## Initial Report
> Lena Voss left last Friday. She's joining Helion. Badge logs show late nights; IT saw cloud sync traffic. We have 14 days under Massachusetts law to file if she took trade secrets.

## Status
- Phase: INVESTIGATION COMPLETE
"""

    report = """# Incident Report: DFIR-2026-002 — BioGenix Insider Data Theft

## Summary for the Investigator
Marcus, the investigation confirms intentional data theft by Dr. Lena Voss during her notice period. Approximately 13.4 GB was uploaded to a personal Google Drive account across five after-hours sessions. Host-side PowerShell history reveals scripted staging of patent drafts, lead-compound assay data, and vendor contracts.

## What Happened (plain language)
On the endpoint, file-access logs alone looked ambiguous — Voss accessed files within her normal role. Network telemetry told a different story: large encrypted uploads to lena.voss.research@gmail.com on five late-night sessions. Once memory artifacts were correlated, PowerShell history showed directory enumeration, 7-Zip password archives, manual browser upload, and deletion of staging files.

## MITRE Mapping
- **T1078 — Valid Accounts**: Insider used legitimate credentials on VOSS-WS-12.
- **T1059.001 — PowerShell**: Scripted collection of R&D directories before compression.
- **T1560.001 — Archive via Utility**: 7-Zip with header encryption before upload.
- **T1567.002 — Exfiltration to Cloud Storage**: ~13.4 GB to personal Google Drive.
- **T1029 — Scheduled Transfer**: After-hours windows May 28–June 6.
- **T1070.004 — File Deletion**: Staging archives deleted June 6.

## Recommended Next Steps
1. Legal hold on VOSS-WS-12 memory image and disk (pre-wipe).
2. Preservation order to Google for lena.voss.research@gmail.com.
3. File MUTSA trade-secrets claim within the remaining 14-day window.
4. Notify Series C diligence counsel if material IP loss is confirmed.

## Chain of Custody
Tamper-evident SHA-256 hash chain — verify in the Audit Chain tab.
"""

    output = {
        "case_id": "DFIR-2026-002",
        "opened_at": chain[0]["timestamp"],
        "closed_at": chain[-1]["timestamp"],
        "case_brief_md": brief,
        "all_findings": [
            {
                "kind": "structured_finding",
                "specialist": "DFIR-HostForensics",
                "case_id": "DFIR-2026-002",
                "findings": [
                    {
                        "summary": "File access on VOSS-WS-12 during the notice period is within normal range (~84 files/day vs 91 baseline). No USB mass storage connected. Print volume elevated but documents are handoff-related. Initial assessment: no clear on-host exfiltration from file telemetry alone.",
                        "evidence_refs": ["workstation_access_logs", "usb_device_history"],
                        "mitre_techniques": ["T1078"],
                        "confidence": "medium",
                    }
                ],
                "open_questions": [
                    "Correlate after-hours sessions with network egress volume.",
                ],
            },
            {
                "kind": "structured_finding",
                "specialist": "DFIR-NetworkForensics",
                "case_id": "DFIR-2026-002",
                "findings": [
                    {
                        "summary": "~13.4 GB egressed to personal Google Drive (lena.voss.research@gmail.com) across five after-hours sessions on May 28, May 29, June 2, June 4, and June 6. Encrypted archive uploads; contents not visible from network telemetry alone.",
                        "evidence_refs": ["cloud_egress_logs", "dns_queries"],
                        "mitre_techniques": ["T1567.002", "T1029"],
                        "confidence": "high",
                    }
                ],
                "open_questions": [
                    "Identify what was inside the encrypted archives.",
                ],
            },
            {
                "kind": "structured_finding",
                "specialist": "DFIR-HostForensics",
                "case_id": "DFIR-2026-002",
                "findings": [
                    {
                        "summary": "PowerShell history shows Get-ChildItem on IP_drafts, BGX-119/122/141 assay data, and vendor contracts; Compress-Archive and 7-Zip with password; staging files deleted June 6. Explains network egress without matching file-read bursts.",
                        "evidence_refs": ["memory_artifacts"],
                        "mitre_techniques": ["T1059.001", "T1560.001", "T1070.004"],
                        "confidence": "high",
                    }
                ],
                "open_questions": [],
            },
        ],
        "captain_verdict": {
            "kind": "captain_verdict",
            "case_id": "DFIR-2026-002",
            "classification": "Confirmed Insider Data Theft",
            "subtype": "Dr. Lena Voss — notice-period exfiltration",
            "threat_actor_attribution": {"group": "Insider (departing employee)", "confidence": "high"},
            "initial_access_vector": "Valid Accounts (insider)",
            "mitre_techniques": [
                {"id": "T1078", "name": "Valid Accounts", "evidence": "Legitimate BIOGENIX\\lvoss credentials on VOSS-WS-12."},
                {"id": "T1059.001", "name": "PowerShell", "evidence": "Scripted directory enumeration in memory_artifacts."},
                {"id": "T1560.001", "name": "Archive via Utility", "evidence": "7-Zip password archives before upload."},
                {"id": "T1567.002", "name": "Exfiltration to Cloud Storage", "evidence": "~13.4 GB to personal Google Drive."},
                {"id": "T1029", "name": "Scheduled Transfer", "evidence": "Five after-hours upload sessions."},
                {"id": "T1070.004", "name": "File Deletion", "evidence": "Staging archives removed June 6."},
            ],
            "immediate_actions": [
                "Legal hold on VOSS-WS-12 forensic image.",
                "Preservation order to Google for personal Drive account.",
                "File MUTSA claim within remaining statutory window.",
            ],
            "evidence_preserved": [
                "workstation_access_logs",
                "cloud_egress_logs",
                "memory_artifacts",
                "dns_queries",
            ],
            "regulatory_obligations": [
                "Massachusetts Uniform Trade Secrets Act — 14-day pre-suit investigation window.",
                "Series C diligence disclosure if material IP loss confirmed.",
            ],
            "human_followup_recommended": [
                "Engage outside counsel for civil injunctive relief against Helion Biopharma.",
            ],
            "audit_chain_head": "",
        },
        "liaison_report_md": report,
        "audit_chain_path": "data/outputs/DFIR-2026-002/audit_chain.jsonl",
        "audit_chain_head": "",
    }
    write_case("002", output, chain)


def case_003() -> None:
    base = datetime(2026, 5, 3, 9, 0, 0, tzinfo=timezone.utc)
    chain = build_chain(
        [
            ("CASE_OPENED", "DFIR-Liaison", {"incident_type": "Data Breach"}),
            (
                "COLLECTION_PLAN_ISSUED",
                "DFIR-Liaison",
                {
                    "plan_items": [
                        "Web App Access Logs",
                        "Database Audit Logs",
                        "Admin Authentication Logs",
                        "WAF Logs",
                        "Customer Impact Summary",
                    ]
                },
            ),
            ("EVIDENCE_RECEIVED", "DFIR-Liaison", {"artifact": "web_app_access_logs"}),
            ("EVIDENCE_RECEIVED", "DFIR-Liaison", {"artifact": "database_audit_logs"}),
            ("EVIDENCE_RECEIVED", "DFIR-Liaison", {"artifact": "admin_authentication_logs"}),
            ("EVIDENCE_RECEIVED", "DFIR-Liaison", {"artifact": "waf_logs"}),
            ("EVIDENCE_RECEIVED", "DFIR-Liaison", {"artifact": "customer_impact_summary"}),
            (
                "EVIDENCE_CLASSIFIED",
                "DFIR-Classifier",
                {"routed_to": ["DFIR-HostForensics"], "category": "web_app_access_logs"},
            ),
            (
                "SPECIALIST_FINDING",
                "DFIR-HostForensics",
                {"finding_path": "data/outputs/DFIR-2026-003/findings/host-round1.json", "num_findings": 1},
            ),
            (
                "EVIDENCE_CLASSIFIED",
                "DFIR-Classifier",
                {"routed_to": ["DFIR-NetworkForensics"], "category": "database_audit_logs"},
            ),
            (
                "SPECIALIST_FINDING",
                "DFIR-NetworkForensics",
                {"finding_path": "data/outputs/DFIR-2026-003/findings/network-round1.json", "num_findings": 1},
            ),
            (
                "CAPTAIN_REDIRECT",
                "DFIR-Captain",
                {
                    "audience": "DFIR-Liaison",
                    "directive": "This is not a web application compromise. Database access used svc_deploy_prod from external AWS IP — those credentials live in the CI/build pipeline. Request round-2 collection: CI build logs, npm manifests, install logs, build-server outbound traffic, and env-var inventory for 60 days before April 7.",
                    "reason": "Round-1 evidence contradicts web-app hypothesis. Service-account direct PostgreSQL access points to compromised build environment.",
                },
            ),
            ("EVIDENCE_RECEIVED", "DFIR-Liaison", {"artifact": "ci_build_logs"}),
            ("EVIDENCE_RECEIVED", "DFIR-Liaison", {"artifact": "npm_dependency_manifest"}),
            ("EVIDENCE_RECEIVED", "DFIR-Liaison", {"artifact": "npm_install_audit"}),
            ("EVIDENCE_RECEIVED", "DFIR-Liaison", {"artifact": "build_server_outbound"}),
            ("EVIDENCE_RECEIVED", "DFIR-Liaison", {"artifact": "environment_variables_inventory"}),
            (
                "EVIDENCE_CLASSIFIED",
                "DFIR-Classifier",
                {"routed_to": ["DFIR-HostForensics"], "category": "npm_install_audit"},
            ),
            (
                "SPECIALIST_FINDING",
                "DFIR-HostForensics",
                {"finding_path": "data/outputs/DFIR-2026-003/findings/host-round2.json", "num_findings": 1},
            ),
            (
                "EVIDENCE_CLASSIFIED",
                "DFIR-Classifier",
                {"routed_to": ["DFIR-NetworkForensics"], "category": "build_server_outbound"},
            ),
            (
                "SPECIALIST_FINDING",
                "DFIR-NetworkForensics",
                {"finding_path": "data/outputs/DFIR-2026-003/findings/network-round2.json", "num_findings": 1},
            ),
            (
                "CAPTAIN_VERDICT",
                "DFIR-Captain",
                {
                    "verdict_path": "data/outputs/DFIR-2026-003/captain_verdict.json",
                    "classification": "Supply Chain Compromise — Customer Data Breach",
                    "num_techniques": 6,
                },
            ),
            (
                "REPORT_DRAFTED",
                "DFIR-Liaison",
                {"report_path": "data/outputs/DFIR-2026-003/liaison_report.md"},
            ),
            (
                "CASE_SEALED",
                "DFIR-Liaison",
                {"final": True, "report_path": "data/outputs/DFIR-2026-003/liaison_report.md"},
            ),
        ],
        base,
    )

    brief = """# Case Brief: DFIR-2026-003

## Incident Summary
On May 2, 2026, a Confluxe Systems customer reported CRM contact data on a dark-web forum (posted ~April 18). Internal review found bulk database reads April 1–14 from service account svc_deploy_prod via direct PostgreSQL connection from an external AWS IP — not through the web application.

## Victim Organization
- Name: Confluxe Systems, Inc.
- Industry: B2B SaaS — customer success management platform
- Size: 153 employees
- Location: Denver, Colorado, USA

## Human Contact
- Name: Avery Tomlinson
- Role: VP of Engineering and acting CISO

## Initial Report
> We assumed web-app compromise or stolen admin creds. WAF is clean. DB access is from svc_deploy_prod from an AWS IP. I need an outside view without our assumptions baked in.

## Status
- Phase: INVESTIGATION COMPLETE (after Captain re-scope)
"""

    report = """# Incident Report: DFIR-2026-003 — Confluxe Supply Chain Breach

## Summary for the Investigator
Avery, this was a supply-chain attack, not a web application intrusion. Malicious npm package form-validator-plus@2.4.7 exfiltrated build-server environment variables on March 19, including production database credentials. The attacker used those credentials on April 7 to bulk-read 1.24M customer contact records. Confluxe is one of ~1,200 downstream victims of the same upstream maintainer compromise.

## What Happened (plain language)
Round 1 pointed away from your initial hypothesis: web logs, admin auth, and WAF were clean. Database audit logs showed the real signal — svc_deploy_prod querying customer_contacts from an external IP. The Captain re-scoped collection to the CI/CD pipeline. Round 2 revealed a malicious post-install script in form-validator-plus@2.4.7 that POSTed env vars to telemetry.form-validator.dev during build B-2026-03-19-04.

## MITRE Mapping
- **T1195.002 — Supply Chain Compromise**: Malicious npm dependency in CI build.
- **T1059.007 — JavaScript**: postinstall.js exfiltration script.
- **T1552.001 — Credentials in Files**: DATABASE_URL_PROD in build env vars.
- **T1078.004 — Cloud Accounts**: Stolen svc_deploy_prod used from AWS EC2.
- **T1530 — Data from Cloud Storage**: 1.24M records from production PostgreSQL.

## Recommended Next Steps
1. Rotate ALL build-environment secrets immediately.
2. Audit npm dependencies published March 12–April 14, 2026.
3. Notify SOC 2 auditor and begin breach notifications (287 customers; GDPR for 14% EU).
4. Engage npm security on NSWA-2026-0341 broader campaign.

## Chain of Custody
Tamper-evident SHA-256 hash chain — verify in the Audit Chain tab.
"""

    output = {
        "case_id": "DFIR-2026-003",
        "opened_at": chain[0]["timestamp"],
        "closed_at": chain[-1]["timestamp"],
        "case_brief_md": brief,
        "all_findings": [
            {
                "kind": "structured_finding",
                "specialist": "DFIR-HostForensics",
                "case_id": "DFIR-2026-003",
                "findings": [
                    {
                        "summary": "Web application access logs April 1–14 show no webshell indicators, no anomalous admin sessions, and traffic consistent with baseline. Stolen-admin-credentials hypothesis not supported.",
                        "evidence_refs": ["web_app_access_logs", "admin_authentication_logs"],
                        "mitre_techniques": [],
                        "confidence": "high",
                    }
                ],
                "open_questions": ["If not web app, where did svc_deploy_prod credentials leak?"],
            },
            {
                "kind": "structured_finding",
                "specialist": "DFIR-NetworkForensics",
                "case_id": "DFIR-2026-003",
                "findings": [
                    {
                        "summary": "Database audit logs show bulk reads of customer_contacts in 50k batches on April 7 from svc_deploy_prod via direct PostgreSQL connection from AWS IP 54.218.119.40 — not through the application pool. WAF logs show no successful injection during the window.",
                        "evidence_refs": ["database_audit_logs", "waf_logs"],
                        "mitre_techniques": ["T1078.004"],
                        "confidence": "high",
                    }
                ],
                "open_questions": ["Trace origin of svc_deploy_prod credential exposure."],
            },
            {
                "kind": "structured_finding",
                "specialist": "DFIR-HostForensics",
                "case_id": "DFIR-2026-003",
                "findings": [
                    {
                        "summary": "Build B-2026-03-19-04 had 13x normal post-install duration. form-validator-plus@2.4.7 postinstall.js exfiltrated env vars to telemetry.form-validator.dev. Malicious version published after maintainer phishing March 11.",
                        "evidence_refs": ["npm_install_audit", "ci_build_logs", "npm_dependency_manifest"],
                        "mitre_techniques": ["T1195.002", "T1059.007", "T1552.001"],
                        "confidence": "high",
                    }
                ],
                "open_questions": [],
            },
            {
                "kind": "structured_finding",
                "specialist": "DFIR-NetworkForensics",
                "case_id": "DFIR-2026-003",
                "findings": [
                    {
                        "summary": "Single HTTPS POST (~18 KB) from build server to telemetry.form-validator.dev during anomalous build — consistent with serialized env-var dump. No persistence channel afterward.",
                        "evidence_refs": ["build_server_outbound", "environment_variables_inventory"],
                        "mitre_techniques": ["T1567"],
                        "confidence": "high",
                    }
                ],
                "open_questions": [],
            },
        ],
        "captain_verdict": {
            "kind": "captain_verdict",
            "case_id": "DFIR-2026-003",
            "classification": "Supply Chain Compromise — Customer Data Breach",
            "subtype": "form-validator-plus@2.4.7 npm supply chain",
            "threat_actor_attribution": {"group": "Unknown (npm maintainer compromise)", "confidence": "medium"},
            "initial_access_vector": "Supply Chain Compromise: Software Dependencies",
            "mitre_techniques": [
                {"id": "T1195.002", "name": "Supply Chain Compromise", "evidence": "Malicious form-validator-plus@2.4.7 in CI build."},
                {"id": "T1059.007", "name": "JavaScript", "evidence": "postinstall.js exfiltration script."},
                {"id": "T1552.001", "name": "Credentials in Files", "evidence": "DATABASE_URL_PROD in build env."},
                {"id": "T1078.004", "name": "Cloud Accounts", "evidence": "svc_deploy_prod used from AWS EC2."},
                {"id": "T1530", "name": "Data from Cloud Storage", "evidence": "1.24M customer_contacts records."},
                {"id": "T1567", "name": "Exfiltration Over Web Service", "evidence": "Env vars POSTed during npm install."},
            ],
            "immediate_actions": [
                "Rotate all build-environment secrets.",
                "Audit npm dependencies from March 12–April 14, 2026.",
                "Notify SOC 2 auditor and begin customer breach notifications.",
            ],
            "evidence_preserved": [
                "database_audit_logs",
                "ci_build_logs",
                "npm_install_audit",
                "build_server_outbound",
            ],
            "regulatory_obligations": [
                "Multi-state breach notification (CO, CA, TX, NY).",
                "GDPR notification for ~14% EU customer records.",
                "SOC 2 auditor notification.",
            ],
            "human_followup_recommended": [
                "Retain customer facing 21-day termination notice — provide remediation timeline.",
            ],
            "audit_chain_head": "",
        },
        "liaison_report_md": report,
        "audit_chain_path": "data/outputs/DFIR-2026-003/audit_chain.jsonl",
        "audit_chain_head": "",
    }
    write_case("003", output, chain)


def main() -> None:
    VIEWER_DATA.mkdir(parents=True, exist_ok=True)
    case_002()
    case_003()
    print("Done.")


if __name__ == "__main__":
    main()
