# QRESCE-0001 R0 Prerequisite Certificate — DRAFT

**Status**: DRAFT — partial agent execution + operator action required
**Date**: 2026-05-17
**Codename**: QRESCE-0001 v0.3 (QorSense rename migration)
**Plan reference**: `C:\Users\Contr\.claude\plans\qresce-0001-v0.3.md`
**Brand etymology lock**: Qor (Qorvo precedent) + esence (presence) = core + presence → KOR-ess-ense

---

## Status Summary

| # | Prerequisite | Agent-executable | Operator action required | Current state |
|---|---|---|---|---|
| 1 | Trademark clearance (USPTO/EUIPO/CIPO) | ❌ requires attorney | ✓ attorney engagement | NOT STARTED |
| 2 | Domain registration | partial (DNS check only) | ✓ purchase + DNS configure | **DNS PRE-CHECK: 8/8 NXDOMAIN — likely available** |
| 3 | Pronunciation documentation | ✓ doc authored | ✓ audio sample recording | **DOC COMPLETE; audio pending** |
| 4 | GitHub slot reservation | ✓ availability check | ✓ reserve under operator account | **CHECK: 4/4 SLOTS AVAILABLE** |

**Overall**: R0 is **40% complete** — agent-executable portions done; operator-side actions (attorney engagement, domain purchase, audio recording, GitHub reservation) pending.

---

## Prerequisite #1: Trademark Clearance (REQUIRES ATTORNEY)

**Action items for operator**:
- [ ] Engage USPTO trademark attorney for formal TESS clearance opinion ($250-500)
- [ ] Request opinion across Nice classes 9 (software) / 38 (telecommunications) / 42 (SaaS)
- [ ] Request sound-alike scan against Qorvo (chip semiconductor, DIFFERENT industry — likely no conflict per v0.3 brand etymology rationale), Coresense, Quintessence, Co-Essence
- [ ] Optional but recommended for global grant context: EUIPO (`euipo.europa.eu/eSearch`) + CIPO (`ic.gc.ca/app/opic-cipo/trdmrks`) parallel filings
- [ ] If conflict surfaces: ABORT QRESCE-0001 before any R-stage commits

**Pre-attorney self-search query strings** (operator can run before attorney engagement to flag obvious conflicts):

USPTO TESS Basic Word Search:
```
SEARCH: QorSense
FIELD: Full Text (FT)
CLASSES: 9, 38, 42
URL: https://tmsearch.uspto.gov/search/search-information
```

Qorvo-precedent verification (confirms chip-industry holder, not software-protocol scope):
```
SEARCH: Qor*
FIELD: Live + Dead Trademarks (LD)
EXPECTED FINDING: Qorvo Inc. (Greensboro NC) registered marks in classes 9, 40, 42
  for "semiconductor", "RF systems", "chip integrated circuits" —
  NOT for software protocols / DePIN / anti-cheat / blockchain SaaS
```

Sound-alike phonetic scans (operator should ask attorney to extend automated scan):
```
Cor*sense*    — verify no software-class hit
Co*resence    — verify no telecommunications-class hit
Quint*essence — Latin etymology cousin; verify distinct
```

---

## Prerequisite #2: Domain Registration

### Agent-executed DNS pre-check (2026-05-17 17:35)

All 8 candidate domains returned NXDOMAIN from Google's 8.8.8.8 resolver — strong positive signal that no DNS records exist. Does NOT prove un-registered (a domain can be registered without DNS pointed), but combined with WHOIS confirmation below it's the gating signal.

| Domain | DNS check | Action |
|---|---|---|
| **qorsense.com** | NXDOMAIN ✓ | **Operator must register (priority 1 — primary brand)** |
| **qorsense.io** | NXDOMAIN ✓ | **Operator must register (priority 1 — tech convention)** |
| **qorsense.xyz** | NXDOMAIN ✓ | **Operator must register (priority 2 — Web3 convention)** |
| **qorsense.network** | NXDOMAIN ✓ | **Operator must register (priority 2 — DePIN convention)** |
| qorsense.app | NXDOMAIN | Recommended add (app store association) |
| qorsense.dev | NXDOMAIN | Recommended add (developer-facing) |
| qorsense.tech | NXDOMAIN | Optional |
| qorsense.ai | NXDOMAIN | **HIGH PRIORITY** — vapi.ai conflict context makes .ai TLD strategically important |

**Action items for operator**:
- [ ] Run WHOIS confirmation (sandbox lacks whois CLI; operator run on dev machine):
  ```bash
  for d in qorsense.com qorsense.io qorsense.xyz qorsense.network qorsense.app qorsense.ai; do
    echo "=== $d ==="
    whois "$d" 2>&1 | grep -iE "registrar|status|creation|registrant|no match|not found" | head -3
  done
  ```
- [ ] Register confirmed-available domains via Namecheap / Cloudflare Registrar / Google Domains (estimated cost: $50-200/year total for 4-8 domains)
- [ ] Configure DNS pointing to operator-controlled hosting (placeholder OK during R0; production DNS at R4)
- [ ] **CRITICAL TIMING**: register domains BEFORE any rename commit lands on origin/main (commit metadata could leak via private collaborators per v0.3 §4 risk #2)

---

## Prerequisite #3: Pronunciation Documentation

**Status**: documentation COMPLETE (see `pronunciation_guide.md` companion artifact). Audio sample recording pending operator action.

**Locked decision** (per v0.3 §3 + Qorvo precedent):
- **Pronunciation**: KOR-ess-ense
- **IPA**: /ˈkɔːrəsɛns/
- **Stress**: First syllable primary (KOR), second unstressed (ess), third secondary (ense)
- **Etymology**: Qor (intentional, Qorvo NASDAQ:QRVO precedent) + esence (presence) = core + presence

**Action items for operator**:
- [ ] Record 30-second WAV/MP3 audio sample saying "QorSense" 3 times slowly + 3 times at conversational pace
- [ ] Save at `docs/audio/qorsense_pronunciation.mp3` (path TBD finalized at R4)
- [ ] Add link in README + brand-guidelines.md draft (R4 scope)
- [ ] Include in IoTeX grant application materials (audio appendix or transcript footnote)

---

## Prerequisite #4: GitHub Slot Reservation

### Agent-executed availability check (2026-05-17 17:35)

All 4 candidate GitHub slots returned HTTP 404 (= AVAILABLE):

| Slot | HTTP code | Status | Recommended use |
|---|---|---|---|
| **github.com/qorsense** | 404 | **AVAILABLE** | **Reserve as primary org name** |
| github.com/QorSense | 404 | AVAILABLE | Case-variant; reserve OR redirect |
| github.com/qorsense-protocol | 404 | AVAILABLE | Reserve as fallback brand-protocol org |
| **github.com/ConWan30/qorsense-pebble-prototype** | 404 | **AVAILABLE** | **Reserve as repo destination** for R4 GitHub rename |

**Action items for operator**:
- [ ] Reserve `github.com/qorsense` org name under operator's GitHub account (requires GitHub login; create org via Settings → Organizations → New)
- [ ] Confirm `qorsense-pebble-prototype` repo slot is reservable under existing ConWan30 account OR newly-created qorsense org
- [ ] Optionally reserve `github.com/QorSense` case-variant to prevent typosquatting
- [ ] Optionally reserve `github.com/qorsense-protocol` as fallback if org name later transfers
- [ ] R4 rename operation: `gh repo rename qorsense-pebble-prototype` (one-shot; GitHub auto-redirects old URL for 90 days)

---

## Open Risks Pre-R0-Complete

| Risk | Mitigation |
|---|---|
| Attorney clearance reveals trademark conflict in any class | ABORT QRESCE-0001 before R-stage commits; choose alternative brand |
| Operator delays domain registration; squatter sees rename commit metadata leak | Register domains FIRST per v0.3 §4 timing constraint |
| GitHub slot taken between this pre-check and operator reservation (race condition) | Operator reserves immediately upon R0 work authorization; back-up names (qorsense-protocol) staged |
| Pronunciation audio sample never recorded; pronunciation inconsistent in spoken contexts | Author at least operator's own 30s recording; expand at R4 |

---

## R0 Certification — Operator Signature Required

**To certify R0 complete, operator confirms each row below**:

```
[ ] Trademark attorney clearance opinion received (or self-search confirms no conflict, accepting risk)
[ ] Domain registrations confirmed for at least: qorsense.com + qorsense.io + qorsense.network + qorsense.ai
[ ] Pronunciation guide documented + 30s audio sample recorded
[ ] GitHub slots reserved: qorsense org name + qorsense-pebble-prototype repo slot

Operator signature: ______________________
Date:               ______________________
Wallet address:     0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
```

Upon all 4 checkboxes confirmed + signature, R0 is COMPLETE. R1 plan-doc commit unlocks **subject to STABILITY-9 terminal state** (per QRESCE-0001 v0.3 §6 dependency note).

---

*End R0_PREREQ_CERTIFICATE DRAFT. Promotion to vsd-vault/proposals/drafts/QRESCE-0001-R0-CERTIFICATE.md upon operator signature.*
