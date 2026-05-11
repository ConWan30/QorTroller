# VBDIP-0002A — Verified Projection Media (VPM) & Stakeholder Utility Layer

**Proposal type:** VBDIP Sidecar / Amendment Candidate
**Parent proposal:** VBDIP-0002 — Autonomous Visual Projections & ZKBA
**Dependency:** VBDIP-0001 must be FROZEN before operational activation
**Status:** DRAFT / PARALLEL DEVELOPMENT
**Scope:** Documentation-only expansion. No new runtime authority granted.
**Activation:** Not active until reconciled into VBDIP-0002 and approved through governance.

---

## 1. The VPM Definition & Protocol Purpose
VAPI does not merely output "HTML." VAPI produces **Verified Projection Media (VPM)**.

A VPM is defined as: *A deterministic, human-operable artifact compiled from canonical VAPI state to communicate proof, eligibility, consent, hardware status, marketplace integrity, or agent accountability without ever becoming the source of truth.*

The core protocol equation for this layer is:
**Canonical Cryptographic Truth → Deterministic Proof Media → Audience-Specific Trust**

HTML is the first medium (via VBDIP-0002), but the VPM framework governs any future media (QR codes, broadcast overlays, PDF dispute packets). The VPM layer inherits the strict epistemic discipline of the evidence design: it may explain proof state, but it must never strengthen or alter proof state.

## 2. Non-Authority Clause
This sidecar does not grant Operator agents new runtime authority.
It explicitly **does not authorize**:
- IPFS pinning
- On-chain anchoring
- Marketplace listing mutation
- Endpoint writes
- Git commits
- FROZEN-v1 primitive changes
- Proof-weight escalation
- Consent override

All operational use remains gated by VBDIP-0001, VBDIP-0002, AgentScope/Cedar policy roots, and explicit governance ceremonies.

## 3. Visual Honesty & Anti-Hype Grammar (VED-INV-10 Extension)
All VPM artifacts must obey a strict, protocol-native visual grammar to make overclaiming visually impossible.
- `live` = saturated colors
- `dry-run` = striped patterns
- `emulated` = desaturated/greyscale
- `frozen-disabled` = locked iconography
- `revoked` = crossed out / redacted
- `unverified` = high-contrast warning bands

Every VPM must include an "Integrity Nutrition Label" detailing: Proof Type, Capture Mode, Raw Biometrics Exposed (Yes/No), Consent Active, ZK Verified, and On-Chain Anchor status.

## 4. Stakeholder Utility Layer
One canonical truth generates multiple audience-specific projections:
* **Gamers:** Receive local "Proof Wallets" holding VHP credentials, practice streaks, and hardware certificates without exposing raw 13-dimensional biometric telemetry.
* **Developers:** Receive "Trust SDK Pages" and verified-human matchmaking sandboxes, reducing integration friction without requiring biometric custody.
* **Manufacturers:** Receive Hardware Lineage Certificates showing DualSense Edge module epochs, firmware provenance, and how specific sensors map to proof-weight tiers.
* **Tournament Organizers:** Receive QR Eligibility Passes and Dispute Packets for rapid, cryptographically backed check-ins and appeals.

## 5. Curator Marketplace Lane
Curator is the Operator Agent responsible for VPM marketplace and artifact coherence. Curator monitors ZKBA manifest completeness, proof-weight classification, consent validity, and compiler hash matching.
**In O1_SHADOW:** Curator may observe and draft review VPM artifacts only.
**Future authority:** Any listing mutation, tier update, or IPFS pinning of a VPM requires explicit Cedar/AgentScope expansion through governance.

## 6. AI Role Constraint
AI agents do not create protocol truth. Under VBDIP-0002A, AI agents may:
- Detect inconsistency and compile deterministic VPMs
- Flag visual misrepresentation and summarize verification outcomes
AI agents **may not**:
- Fabricate proof claims or bypass Cedar policy
- Convert demo artifacts into production VPMs

## 7. VPM Projection Registry
This sidecar reserves the following VPM identifiers to prevent derived-artifact sprawl. All future artifacts must map to one of these registered identifiers:

| VPM ID | Name | Core Audience | Status |
|---|---|---|---|
| `PROOF-TRAILER-v1` | Tournament Broadcast Overlay | Esports Viewers | Reserved |
| `PROOF-WALLET-v1` | Player-Side Competitive Record | Gamers | Reserved |
| `QR-ELIGIBILITY-v1` | Tournament Check-in Pass | Organizers | Reserved |
| `HARDWARE-LINEAGE-v1` | Hardware Lifecycle Cert | Manufacturers | Reserved |
| `CONSENT-CAPSULE-v1` | Data Contribution Receipt | Gamers / Data Buyers | Reserved |
| `DISPUTE-PACKET-v1` | Integrity Replay / Appeals | Referees / Ops | Reserved |
| `MARKET-LISTING-v1` | ZKBA Market Card | Buyers / Curator | Reserved |
| `DEV-SANDBOX-v1` | Live Proof SDK Example | Developers | Reserved |
| `HONESTY-BOARD-v1` | Public Protocol State Board | Ecosystem Partners | Reserved |
| `AGENT-REVIEW-v1` | Operator Accountability Card | Governance / Deployer | Reserved |

## 8. Activation Gates
| Gate | Requirement | Status |
|---|---|---|
| G1 | VBDIP-0001 FROZEN | Required |
| G2 | VBDIP-0002 reconciled with VBDIP-0002A | Required |
| G3 | `vsd_ui_compiler.py` deterministic harness passing | Required |
| G4 | VPM manifest schema & Integrity Label implemented | Required |
| G5 | Anti-Hype Visual Grammar tests passing | Required |

## 9. Decision Blocks
**Decision L1 — VPMs as Human-Operable Surfaces**
*Resolved:* VPMs are approved as deterministic human-operable surfaces for cryptographic state, not as protocol source of truth.
**Decision L2 — Anti-Hype Visual Grammar**
*Resolved:* Visual honesty is protocol law. VPMs must utilize mandatory visual states (striped, desaturated, etc.) to reflect technical limitations.
**Decision L3 — VPM Registry Discipline**
*Resolved:* All projections must use registered VPM identifiers to prevent un-auditable artifact sprawl.
**Decision L4 — AI Stewardship Boundary**
*Resolved:* AI agents compile VPMs to explain verified state, but may never create or escalate protocol truth.
