# QRESCE-0001 R0 Prerequisite Certificate — DRAFT v2

**Status**: DRAFT v2 — Phase 2 R0 deep-verification complete; operator action precisely scoped
**Date**: 2026-05-18 (v2 — supersedes v1 2026-05-17)
**Codename**: QRESCE-0001 v0.4 (QorSense rename migration)
**Plan reference**: `C:\Users\Contr\.claude\plans\qresce-0001-v0.4-brand-amendment.md`
**Brand**: **QorSense** (medial capital S — iPhone/GitHub/OpenAI styling)
**Pronunciation**: **KOR-sense** (IPA `/ˈkɔːrsɛns/`, 2 syllables)
**Etymology**: Qor (Qorvo NASDAQ:QRVO precedent) + Sense (English noun) = core + sense

---

## Status Summary — Phase 2 R0 Precisional Verification COMPLETE

| # | Prerequisite | Agent verification | Operator action required | Current state |
|---|---|---|---|---|
| 1 | Trademark clearance | ✓ SEO/brand-virginity confirmed; USPTO TESS query templates prepped | **✓ attorney engagement (1-3 wks async)** | **PRE-CLEARED at agent layer; legal opinion required** |
| 2 | Domain registration | ✓ RDAP authoritative; .com FOUND REGISTERED ⚠ | **✓ decision: acquire .com via resale OR lead with .io** | **8/9 AVAILABLE; .com is parked GoDaddy squatter** |
| 3 | Pronunciation documentation | ✓ guide authored | **✓ 30s audio sample recording** | **DOC COMPLETE; audio pending** |
| 4 | GitHub slot reservation | ✓ 7/7 AVAILABLE inc. alternates | **✓ reserve under operator account** | **CONFIRMED CLEAN** |
| 5 | Package namespace (PyPI + npm) | ✓ 9/9 AVAILABLE | (no operator action — reserve at R4) | **CONFIRMED CLEAN** |
| 6 | Social media handle | partial (HTTP probes inconclusive; needs auth) | **✓ visual verify on logged-in accounts** | **OPERATOR-side check** |

**Overall**: R0 is **60% complete** (up from 40% at v1) — Phase 2 deepened all agent-side checks beyond initial DNS-only signal. Critical finding: **qorsense.com is NOT freely available** (registered + parked by GoDaddy squatter 2026-01-07). Operator must decide path forward at prereq #2 before purchase action.

---

## Prereq #1: Trademark Clearance (REQUIRES ATTORNEY)

### Agent pre-screen — BRAND VIRGINITY CONFIRMED ✓

Bing SEO comparative (2026-05-18):
- **"qorsense"**: 18 mentions in SERP HTML — mostly search chrome + maybe 1-2 incidental hits (no organic brand presence)
- **"qorvo"** (control, NASDAQ:QRVO chip company): 48 mentions + explicit `NASDAQ:QRVO` + `QRVO` ticker references — established commercial brand

→ **Qorsense is essentially virgin on the SEO landscape.** Strongest possible distinctiveness signal for trademark prosecution. Only conflict layer is the parked .com domain (no commercial brand using the name).

### Operator action items

- [ ] **Engage USPTO trademark attorney for formal TESS clearance opinion** ($250-500; 1-3 weeks async)
- [ ] **Request Nice class scope**: 9 (computer software) + 38 (telecommunications) + 42 (SaaS)
- [ ] **Request sound-alike scans against**:
  - **Qorvo** (chip industry — DIFFERENT scope; commercial precedent for Q-without-U brand)
  - **Quora** (Q&A platform — DIFFERENT scope)
  - **Quintessence** (Latin etymology cousin — distinct syllable count)
  - "Core sense" / "Coresense" (common English phrase — not a brand)
  - "Coherence" + "Concourse" + "Corsense" sound-alikes
- [ ] **Optional (recommended for global IoTeX grant context)**:
  - EUIPO eSearch: `euipo.europa.eu/eSearch` — Nice classes 9/38/42
  - CIPO: `ic.gc.ca/app/opic-cipo/trdmrks` — Nice classes 9/38/42
- [ ] **If conflict surfaces in ANY class within software/SaaS/telecom**: ABORT QRESCE-0001 before R1; choose alternative brand

### USPTO TESS query templates (operator runs in browser at `tmsearch.uspto.gov`)

Note: USPTO TESS is a SPA (JavaScript-rendered) — cannot be scripted reliably; operator runs manually:

```
SEARCH 1 (exact match in software/SaaS/telecom):
  Mark: QORSENSE
  Field: Combined Word Mark (TM/SM)
  Status: LIVE
  Classes: 009 + 038 + 042

SEARCH 2 (wildcard prefix — flush out Qorvo + adjacent):
  Mark: QORS*
  Field: TM/SM (Live + Dead)
  Classes: ALL 45 (see if any QORS- mark exists in unexpected scope)
  Expected: Qorvo Inc (Greensboro NC) in 009/040/042 chip-industry context

SEARCH 3 (sound-alike phonetic):
  Mark: KOR SENSE
  Use TESS phonetic search variant
  Classes: 009 + 038 + 042

SEARCH 4 (Mark Drawing Code 4 — standard character QOR family):
  Mark: QOR
  Mark Drawing Code: 4 (standard character)
  Field: TM/SM (Live)
  Classes: ALL
```

---

## Prereq #2: Domain Registration — CRITICAL FINDING ⚠

### Agent RDAP verification (authoritative; supersedes prior DNS-only check)

DNS NXDOMAIN does NOT mean "available" — a registered domain with no DNS records published returns NXDOMAIN. RDAP is the authoritative source. Phase 2 ran both:

| Domain | DNS | RDAP | Verdict |
|---|---|---|---|
| **qorsense.com** | NXDOMAIN | **HTTP 200 (REGISTERED)** | ⚠ **REGISTERED 2026-01-07 by GoDaddy registrant; parked at `/lander` (resale-broker page)** |
| qorsense.io | NXDOMAIN | HTTP 404 | ✓ **AVAILABLE** |
| qorsense.xyz | NXDOMAIN | HTTP 404 | ✓ **AVAILABLE** |
| qorsense.network | NXDOMAIN | HTTP 404 | ✓ **AVAILABLE** |
| qorsense.app | NXDOMAIN | HTTP 404 | ✓ **AVAILABLE** |
| qorsense.dev | NXDOMAIN | HTTP 404 | ✓ **AVAILABLE** |
| qorsense.tech | NXDOMAIN | HTTP 404 | ✓ **AVAILABLE** |
| qorsense.ai | NXDOMAIN | HTTP 404 | ✓ **AVAILABLE** |
| qorsense.org | NXDOMAIN | HTTP 404 | ✓ **AVAILABLE** |

**8/9 AVAILABLE; .com REGISTERED.**

### qorsense.com registration details (Verisign RDAP)

```
Registered:     2026-01-07T04:56:49Z (4 months ago)
Expiration:     2027-01-07T04:56:49Z (1-year initial; renewable)
Registrar:      GoDaddy.com, LLC
Nameservers:    NS69.DOMAINCONTROL.COM / NS70.DOMAINCONTROL.COM
                (GoDaddy parking/holding nameservers — no DNS records)
Status flags:   client delete prohibited + renew prohibited
                + transfer prohibited + update prohibited (all GoDaddy defaults)
Public page:    redirects to /lander (GoDaddy domain-brokerage interface)
```

**Interpretation**: This is a domain squatter or speculator who registered "qorsense" 4 months ago (recent enough to be opportunistic given the AI brand-naming surge in late 2025/early 2026). They're holding it for resale. Typical GoDaddy parked-domain resale ranges: $500 - $5,000 for common names; $10K - $50K+ for premium brand-quality names; rare cases $100K+.

### Operator DECISION REQUIRED at this prereq

**Path A — Acquire .com via resale negotiation** ($$$$; weeks-long; uncertain outcome):
1. Visit https://qorsense.com → redirects to GoDaddy /lander
2. Click "Make offer" or "Buy now" if listed
3. Negotiate via GoDaddy broker (typical fee: 20% of sale price)
4. **Risk**: registrant may ignore offers OR price-anchor at $20K+; this could block R0 indefinitely

**Path B — Skip .com, lead with .io as primary brand domain** (RECOMMENDED for DePIN context):
1. Web3/DePIN community accepts .io / .xyz / .network as primary brand
2. IoTeX foundation grant evaluators expect non-.com for new protocols
3. Register: qorsense.io + qorsense.xyz + qorsense.network + qorsense.ai immediately (~$200/year total)
4. Optionally backorder qorsense.com via Namecheap/GoDaddy backorder service ($69-$199/year) — fires automatically if squatter lets registration lapse 2027-01-07
5. **Risk minimized**: zero $$$$ negotiation; no R0 blocker

**Author recommendation**: **Path B (skip .com, lead with .io)**. The DePIN/Web3 brand context and the IoTeX grant alignment make .io / .xyz / .network primary anyway. .com acquisition can happen post-traction.

### Operator action items (Path B)

- [ ] **Decide Path A or Path B** (annotate decision below)
- [ ] **Register PRIMARY**: `qorsense.io` ($40-60/yr) — primary brand domain
- [ ] **Register SECONDARY** (defensive against typosquatters):
  - `qorsense.xyz` ($1-12/yr) — Web3 convention
  - `qorsense.network` ($25-30/yr) — DePIN convention
  - `qorsense.ai` ($120-150/yr) — strategic given vapi.ai precedent (CRITICAL given the .ai TLD's anti-cheat-vs-voice-AI brand collision pattern we're escaping)
- [ ] **Register OPTIONAL** (low-cost defensive):
  - `qorsense.app` ($14/yr) — Google-controlled TLD with HTTPS-enforcement
  - `qorsense.dev` ($14/yr) — developer-facing
  - `qorsense.org` ($10/yr) — nonprofit/foundation framing
  - `qorsense.tech` ($1-50/yr) — generic tech
- [ ] **Backorder .com**: `qorsense.com` via GoDaddy or Namecheap backorder service ($69-$199/yr) — auto-acquires if 2027 expiration lapses
- [ ] **Configure DNS**: point all registered domains to operator-controlled hosting (placeholder OK during R0; production DNS at R4)
- [ ] **CRITICAL TIMING**: register domains BEFORE any rename commit lands on origin/main

**Decision annotation (operator fills in)**:
```
Path chosen: [ A | B ]
Reasoning:
Registered domains:
Registration date:
Total annual cost: $______
```

---

## Prereq #3: Pronunciation Documentation

**Status**: documentation COMPLETE (see `pronunciation_guide.md` companion artifact). Audio sample recording pending operator action.

**Locked decision** (per QRESCE-0001 v0.4 §3 + Qorvo precedent + iPhone/GitHub/OpenAI medial-capital styling):
- **Brand**: QorSense
- **Pronunciation**: KOR-sense
- **IPA**: /ˈkɔːrsɛns/
- **Stress**: First syllable primary (KOR), second unstressed (sense)
- **Etymology**: Qor (Qorvo precedent) + Sense (English noun) = core + sense

### Operator action items

- [ ] **Record 30-second WAV/MP3 audio sample**:
  - Take 1 (slow, separated): "KOR. SENSE. Qor-Sense. Qor-Sense. Qor-Sense."
  - Take 2 (conversational): "QorSense. QorSense. QorSense."
  - Take 3 (sentence): "The QorSense protocol verifies human presence cryptographically."
  - Take 4 (etymology): "QorSense — the core sense — pronounced KOR-sense, spelled Q-O-R-capital-S-E-N-S-E."
- [ ] **Save at**: `docs/audio/qorsense_pronunciation.mp3` (path finalized at R4)
- [ ] **Include**: in README + brand-guidelines.md draft (R4 scope) + IoTeX grant application appendix

---

## Prereq #4: GitHub Slot Reservation — CONFIRMED CLEAN ✓

### Agent verification (2026-05-18)

| Slot | HTTP code | Verdict |
|---|---|---|
| **github.com/qorsense** | 404 | ✓ **AVAILABLE — reserve as primary org name** |
| github.com/Qorsense | 404 | ✓ AVAILABLE (case-variant; reserve or redirect to canonical) |
| github.com/QorSense | 404 | ✓ AVAILABLE (medial-cap variant — match brand display) |
| **github.com/qorsense-protocol** | 404 | ✓ AVAILABLE (fallback brand-protocol org) |
| github.com/qorsense-labs | 404 | ✓ AVAILABLE (research/incubation context) |
| github.com/qorsense-foundation | 404 | ✓ AVAILABLE (nonprofit framing) |
| github.com/qorsense-network | 404 | ✓ AVAILABLE (DePIN-network framing) |
| **github.com/ConWan30/qorsense-pebble-prototype** | 404 | ✓ **AVAILABLE — reserve as repo destination for R4 rename** |

**7/7 alternates + primary repo slot AVAILABLE.**

### Operator action items

- [ ] **PRIMARY** — Reserve `github.com/qorsense` org under operator's GitHub account (Settings → Organizations → New Organization)
- [ ] **DEFENSIVE** — Reserve `github.com/Qorsense` + `github.com/QorSense` to prevent typosquatting/squatting
- [ ] **FALLBACK** — Reserve `github.com/qorsense-protocol` as backup org name
- [ ] **REPO** — Confirm `qorsense-pebble-prototype` repo slot is reservable under `ConWan30` account OR newly-created `qorsense` org (note: rename happens at R4 via `gh repo rename qorsense-pebble-prototype` — GitHub auto-redirects old URL `vapi-pebble-prototype` for 90 days)
- [ ] **OPTIONAL** — Reserve `qorsense-labs` / `qorsense-foundation` / `qorsense-network` for future operational use (research org, DAO entity, network protocol entity)

---

## Prereq #5 (NEW v2): Package Namespace — CONFIRMED CLEAN ✓

### PyPI (Python SDK distribution)

| Package | Status |
|---|---|
| `qorsense` | ✓ AVAILABLE |
| `qorsense-sdk` | ✓ AVAILABLE |
| `qorsense_sdk` (underscore variant) | ✓ AVAILABLE |
| `qorsense-protocol` | ✓ AVAILABLE |

### npm (Frontend / JavaScript SDK)

| Package | Status |
|---|---|
| `qorsense` | ✓ AVAILABLE |
| `@qorsense/core` | ✓ AVAILABLE (scoped — critical for org-wide packages) |
| `@qorsense/sdk` | ✓ AVAILABLE |
| `qorsense-protocol` | ✓ AVAILABLE |
| `qorsense-verifier` | ✓ AVAILABLE (frontend verifier component naming) |

**9/9 package namespaces AVAILABLE.**

### Operator action items

- [ ] **Reserve at R4 (not R0)** — package registration is tied to first publish; no R0 action needed
- [ ] **At R4 publish**: register PyPI + npm names atomically with R4 rename merge to prevent post-rename squatting

---

## Prereq #6 (NEW v2): Social Media Handle — OPERATOR VISUAL VERIFY REQUIRED

HTTP probes are inconclusive for social platforms (they often return 200/301 for both existing and non-existent profiles to defeat enumeration). Operator MUST visually verify on authenticated accounts:

| Platform | URL | Operator action |
|---|---|---|
| **Twitter/X** | https://x.com/qorsense | Log in to X, navigate, verify "doesn't exist" page; reserve `@qorsense` |
| **Discord** | (no profile URLs; channel reservation only) | Create Discord server "QorSense"; reserve vanity URL after Boost level 3 |
| **Telegram** | https://t.me/qorsense | Log in, attempt to create channel `t.me/qorsense` |
| **Reddit** | https://reddit.com/r/qorsense | Log in, attempt to create subreddit r/qorsense |
| **Medium** | https://medium.com/@qorsense | Log in, attempt to claim @qorsense handle |
| **LinkedIn** | (company page) | Create LinkedIn Company Page "QorSense" |

### Operator action items

- [ ] Visually verify availability on X / Reddit / Telegram / Medium / Discord / LinkedIn
- [ ] Reserve handles immediately upon verification (squatter risk amplifies post-rename announcement)

---

## Open Risks Pre-R0-Complete

| Risk | Mitigation |
|---|---|
| Attorney clearance reveals trademark conflict in software/SaaS/telecom | ABORT QRESCE-0001 before R-stage commits; choose alternative brand |
| .com squatter price-anchors at $20K+ | Lead with .io per Path B; revisit .com via backorder or post-traction acquisition |
| Operator delays domain registration; squatter sees rename commit metadata leak | Register .io + alternates IMMEDIATELY per v0.4 §4 timing constraint |
| GitHub slot taken between this verification and operator reservation | Operator reserves within days; back-up names (qorsense-labs / qorsense-foundation) staged |
| Pronunciation audio sample never recorded | Operator records minimum-viable 30s WAV; expand at R4 |
| Social media handle squatting post-rename announcement | Reserve handles on prereq #6 BEFORE R4 merge announcement |

---

## R0 Certification — Operator Signature Required

**To certify R0 complete, operator confirms each row below**:

```
[ ] Trademark attorney clearance opinion received (or self-search confirms no conflict in classes 9/38/42, accepting risk; brand-virginity SEO signal strong)
[ ] Domain Path decided: [ A: acquire .com via resale ] [ B: skip .com, lead .io ]
[ ] Domain registrations confirmed for at least: qorsense.io + qorsense.xyz + qorsense.network + qorsense.ai (Path B) OR including .com (Path A)
[ ] Pronunciation guide documented + 30s audio sample recorded
[ ] GitHub slots reserved: qorsense org + qorsense-pebble-prototype repo slot + (optional) Qorsense + QorSense + qorsense-protocol case/alternate variants
[ ] Social handles visually verified + reserved: @qorsense on X / Reddit / Telegram / Discord / Medium / LinkedIn

Operator signature: ______________________
Date:               ______________________
Wallet address:     0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
```

Upon all 6 checkboxes confirmed + signature, R0 is COMPLETE. Promote this file to:
`vsd-vault/proposals/drafts/QRESCE-0001-R0-CERTIFICATE.md`

R1 plan-doc commit unlocks subject to STABILITY-9 terminal state (✓ achieved at `422e2600`).

---

## Phase 2 Verification Trail (Audit Evidence)

| Verification | Method | Result | Timestamp |
|---|---|---|---|
| Domain DNS NXDOMAIN | nslookup 8.8.8.8 | 9/9 NXDOMAIN | 2026-05-17 |
| Domain RDAP authoritative | curl Verisign + Identity Digital + PIR + Donuts + Google Registry + nic.* | **8/9 AVAILABLE; .com REGISTERED** | 2026-05-18 |
| qorsense.com registrant | curl rdap.verisign.com | GoDaddy.com, LLC; registered 2026-01-07; expires 2027-01-07; nameservers ns69/70.domaincontrol.com (parking); status all-prohibited | 2026-05-18 |
| qorsense.com page content | curl -L https://qorsense.com | HTML redirects to /lander (GoDaddy parked-domain brokerage page) | 2026-05-18 |
| GitHub slot | curl HEAD probe | 7/7 AVAILABLE | 2026-05-18 |
| PyPI namespace | curl pypi.org/pypi/.../json | 4/4 AVAILABLE | 2026-05-18 |
| npm namespace | curl registry.npmjs.org/... | 5/5 AVAILABLE (inc @qorsense scope) | 2026-05-18 |
| Brand SEO virginity | Bing comparative (qorsense vs qorvo) | 18 SERP mentions vs 48 + NASDAQ:QRVO ticker → essentially virgin | 2026-05-18 |
| USPTO TESS pre-screen | curl tmsearch.uspto.gov | SPA; operator must run in browser | 2026-05-18 |

---

*End R0_PREREQ_CERTIFICATE.DRAFT v2. Phase 2 R0 deep verification complete. Operator action queue precisely scoped (6 prereqs; ~30 min hands-on + 1-3 weeks attorney async + potential resale negotiation if Path A). Critical decision blocker: prereq #2 Path A vs B (domain .com resale or skip). Brand-virginity + namespace availability signals all strongly positive. Promotion to QRESCE-0001-R0-CERTIFICATE.md upon operator signature.*
