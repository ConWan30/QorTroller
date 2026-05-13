# VAPI Whitepaper Versioning

This file is the canonical lineage record for VAPI whitepaper drafts.

## Active

| Version | Path | Status | Anchor commits | Citation |
|---|---|---|---|---|
| **v4** | `docs/vapi-whitepaper-v4.md` | **CANONICAL SUCCESSOR** | Architecture anchor: `e81e04aa` (Phase O4-VPM-INT close, 2026-05-13). Documentation revamp commit: `9f8581cd` (README + Whitepaper v4 successor landing, 2026-05-13). | DOI assignment pending Zenodo release. Until v4 minting: cite v3 + reference `docs/vapi-whitepaper-v4.md` at architecture anchor `e81e04aa` (documentation revamp commit `9f8581cd`). |

## Superseded (preserved for historical continuity)

| Version | Path | Status | Reason | Citation |
|---|---|---|---|---|
| v3 | `docs/vapi-whitepaper-v3.md` | **SUPERSEDED by v4** (preserved for DOI continuity) | Captures Phase 68–70 baseline (Ruling Registry + MPC ceremony). 168 phases out of date as of Phase O4 close. | Zenodo DOI **10.5281/zenodo.18966169** preserved. Cite v3 only for historical reference; cite v4 for current-state architectural claims. |
| v2 | `docs/vapi-whitepaper-v2.md` (if present) | SUPERSEDED | Intermediate draft. | Not citable. |
| v5 draft | `docs/vapi-whitepaper-v5.md` (if present) | INTERMEDIATE DRAFT — NOT CANONICAL | Was an in-progress draft between v3 and v4. v4 is the canonical successor; v5 fragments may be folded into v4 retroactively as appendix material. | Not citable. |
| paper/ | `paper/vapi-whitepaper.md` (if present) | EARLY DRAFT (Phase 1–17 era) | Preserved as the protocol's initial public articulation. | Not citable. |

## Lineage

```
paper/vapi-whitepaper.md  (Phase 1–17 era — earliest public draft)
       ↓
docs/vapi-whitepaper-v2.md  (intermediate)
       ↓
docs/vapi-whitepaper-v3.md  (Phase 68–70; Zenodo DOI 10.5281/zenodo.18966169)
       ↓
docs/vapi-whitepaper-v4.md  ← CANONICAL (Phase O4 close, commit e81e04aa, 2026-05-13)
```

## Citation guidance for external readers

- **For current-state architectural claims** (49 substantive live testnet contracts / 7-of-7 ZKBA classes / Operator Initiative fleet / VPM compiler discipline / Anti-Hype Visual Grammar / 77 PV-CI invariants / PATTERN-017 primitive family): cite `docs/vapi-whitepaper-v4.md` at architecture anchor commit `e81e04aa` (documentation revamp commit `9f8581cd`).
- **For historical DOI continuity** (Phase 68–70 baseline; Ruling Registry; MPC ceremony): cite Zenodo DOI `10.5281/zenodo.18966169` (v3).
- **For protocol invariants that are FROZEN and unchanged across versions** (228-byte PoAC wire format; SHA-256 chain hash; 9-level PITL stack; 13-feature L4 Mahalanobis space; cheat code taxonomy): either version is citable — v4 supersedes v3 in detail but does not modify the FROZEN regions.

## v4 Zenodo release plan

v4 receives a new Zenodo DOI at release. The DOI is allocated through the operator's Zenodo upload workflow (`docs/vapi-whitepaper-v4.md` zipped + `wiki/assessments/whitepaper_v4_revamp_provenance_2026-05-13.md` + `contracts/deployed-addresses.json` snapshot + `CLAUDE.md` snapshot, all at architecture anchor commit `e81e04aa` / documentation revamp commit `9f8581cd`). When the v4 DOI is minted, this file is updated to reflect the canonical citation path; the v3 DOI is preserved as historical.

---

*— VAPI Principal Architect, 2026-05-13*
