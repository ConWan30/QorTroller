# QorTroller Brand Guidelines

**Brand**: **QorTroller** — Core Controllers of their gaming data
**Category**: Verifiable Autonomous Physical Intelligence (V.A.P.I.) — coined DePIN sub-category
**Brand-lock date**: 2026-05-18 (QRESCE-0001 v0.5, commit `2c762835`)
**Repo**: https://github.com/ConWan30/QorTroller

---

## §1 Tagline (canonical)

**QorTroller — Core Controllers of their gaming data.**

> The reference implementation of Verifiable Autonomous Physical Intelligence (V.A.P.I.) — a Decentralized Physical Infrastructure (DePIN) sub-category coined to describe protocols where the physical-input source is also the cryptographic agency-holder over the data those physical interactions generate. In QorTroller's case: gamers and their controllers, producing data, owning that data.
>
> Built native to IoTeX's Internet of Trusted Things foundation. Anchored on IoTeX L1. Composable as a single on-chain call. Designed so cheating doesn't need to be punished — it can't exist when humanity is cryptographically proven and the gamer retains sovereignty.

Use the tagline as opening copy in: README, whitepaper abstract, grant application cover, conference-talk first slide, social profile bios, partnership decks.

---

## §2 Pronunciation

- **Phonetic**: **KOR-TROLL-er**
- **IPA**: `/ˈkɔːrˌtroʊlər/`
- **Syllables**: 3 (KOR · TROLL · er)
- **Stress**: First syllable primary (KOR), second secondary (TROLL), third unstressed (er)

### Do NOT say
- kwo-TROLL-er (treats Q as Italian/Latin KW)
- KEW-troller (treats Q as K-Y-OO)
- KORE-troller (loses the silent-K-or pattern)
- kor-troh-LAIR (stress on third)

### Etymology
Qor (Qorvo NASDAQ:QRVO commercial precedent for Q-without-U coined technology brands; semantic anchor "core") + Troller (from Controller — dual meaning: physical hardware verification + agentic gamer-data sovereignty)

---

## §3 Capitalization (load-bearing)

| Context | Use | Examples |
|---|---|---|
| **Display brand** (project name visible to humans) | **QorTroller** (medial capital T) | README title, frontend strings, marketing copy, social bios, deck headlines |
| **URL / file path / module slug** | `qortroller` (lowercase) | github.com/ConWan30/QorTroller, qortroller.io, `qortroller/` directory |
| **Byte literal / env var / constant** | `QORTROLLER` (uppercase) | `QORTROLLER_API_KEY`, byte-prefix constants (forward primitives only) |
| **NEVER use** | "Qortroller" (sentence case) ✗ "QORTROLLER" in display ✗ "qorTroller" ✗ "Qor-Troller" with hyphen ✗ "Qor Troller" with space ✗ | These are non-canonical and dilute brand recognition |

Pattern matches: **iPhone** (medial cap on P) / **GitHub** (medial cap on H) / **OpenAI** (medial cap on A) / **OpenSea** (medial cap on S) / **PayPal** (medial cap on P) / **DePIN** (medial cap on P).

---

## §4 V.A.P.I. styling (category vs project)

V.A.P.I. is the **coined DePIN sub-category**. QorTroller is the **project that implements it**.

| Context | Use | Why |
|---|---|---|
| **Display references to category** | `V.A.P.I.` (with periods) | Differentiates the coined V.A.P.I. category from unrelated similarly-named projects in other categories |
| **Code identifiers** (Python modules, Solidity contracts, byte literals, class names) | `VAPI` (without periods) | Periods break syntax. Categorical-technical infrastructure stays `VAPI` per Layer C FROZEN-v1 discipline |
| **Acronym introduction** | "Verifiable Autonomous Physical Intelligence (V.A.P.I.)" | First-mention pattern |
| **Inline adjective forms** | "V.A.P.I.-compliant", "V.A.P.I.-native", "V.A.P.I. category primitives" | Hyphen-adjective composition |
| **Categorical phrases** | "the V.A.P.I. sub-category", "V.A.P.I. primitives", "future V.A.P.I. projects" | Display contexts use periods |
| **Technical references** | `VAPI_GIC_GENESIS_v1`, `class VAPISession`, `VAPIToken.sol` | Code-context omits periods |

### When to use QorTroller vs V.A.P.I. in narrative

- **QorTroller** → when referring to the project, implementation, brand, repo, infrastructure, this codebase
- **V.A.P.I.** → when referring to the category, the conceptual framing, future compliant implementations, technical primitives shared across V.A.P.I.-compliant projects

Example:
> "QorTroller, the reference implementation of V.A.P.I., is built native to IoTeX. The V.A.P.I. category includes 12 FROZEN-v1 cryptographic primitives that any V.A.P.I.-compliant project shares. QorTroller-specific marketing materials use the QorTroller brand; technical references to category-shared infrastructure use V.A.P.I. naming."

---

## §5 First-mention discipline

In any external-facing document (grant application, blog post, conference talk, partner deck, social-media intro thread):

1. **Lead with the tagline**:
   > QorTroller — Core Controllers of their gaming data.

2. **Define V.A.P.I. at first mention**:
   > The reference implementation of Verifiable Autonomous Physical Intelligence (V.A.P.I.), a coined Decentralized Physical Infrastructure (DePIN) sub-category.

3. **Anchor to IoTeX**:
   > Built native to IoTeX's Internet of Trusted Things foundation.

4. **State the cryptographic-sovereignty thesis**:
   > Cheating doesn't need to be punished — it can't exist when humanity is cryptographically proven and the gamer retains sovereignty.

After first mention: use "QorTroller" alone; no need to re-explain V.A.P.I. unless audience requires category context.

---

## §6 Hostile-read mitigation

QorTroller phonetically contains "TROLL" — a gaming-culture pejorative for toxic player / harasser / rule-breaker. Adversarial readers may extract "Troll" from "Troller" for mockery.

### Mitigation discipline

1. **Always medial-cap in display**: `QorTroller` emphasizes Qor + Troller compound (not Q + orTroll). Lowercase `qortroller` in URLs/code is fine; never lowercase in marketing.

2. **Etymology footnote at first mention** in formal documents:
   > QorTroller — Qor (Qorvo NASDAQ:QRVO commercial precedent for Q-without-U coined technology brands) + Troller (from "Controller" — the physical gaming controllers the protocol verifies, AND the gamers who are the agentic Core Controllers of their own gaming data).

3. **Tagline pairing** at first mention to immediately frame intent.

4. **Avoid in-house jokes** that play on "Troll" — no team Discord channels named `#qor-trollin`, no commit messages with "QorTrolled this fix lol". Brand dignity compounds.

5. **Pre-empt in FAQ**:
   > **Q: "Doesn't 'QorTroller' contain 'troll'? Isn't that ironic for an anti-cheat protocol?"**
   > A: QorTroller is *Qor + Troller* (from Controller), not *Qor + Troll + er*. The brand is about empowering gamers (Core Controllers of their data), not about trolling — verification proves you're real so trolls have nowhere to hide.

Adversarial readings exist for every brand (Apple "rotten" / Amazon "indifferent forest" / Tesla "dead inventor" / Stripe "just lines"). Accepted cost of doing business in exchange for QorTroller's substantive advantages (9/9 domain availability, dual-meaning semantic depth, DePIN-native positioning, alignment with existing sovereignty architecture).

---

## §7 International considerations

For non-English-primary audiences (especially IoTeX foundation evaluators with global footprint):

- **Romance language speakers** (Spanish, Italian, French): natural temptation to pronounce Q as KW. Footnote: "Q pronounced as K, following NASDAQ:QRVO Qorvo commercial precedent."
- **Mandarin Chinese speakers**: Q in Pinyin is "ch" (like "chip"). Footnote: "K sound, not 'ch' sound."
- **Arabic speakers**: Qaf (ق) is a back-of-throat K — closer to canonical. No correction needed.
- **German speakers**: Q always paired with U → "kv" sound. Footnote: "K only, no U."
- **Korean/Japanese speakers**: closer to canonical when transliterated; minimal correction.

---

## §8 Versioning discipline

| Component | Version |
|---|---|
| Brand | QorTroller v0.5 (locked 2026-05-18, commit `2c762835`) |
| Whitepaper | v5 (brand-layer revamp); v6 reserved for post-R5 full rewrite |
| Category framing | V.A.P.I. (Verifiable Autonomous Physical Intelligence) — v1 of coined framing |
| Tagline | "Core Controllers of their gaming data" — v1 locked |
| Pronunciation guide | v2 (QorTroller canonical; supersedes v1 QorSense) |
| Brand iteration history | 5 documented iterations preserved for trademark prosecution support |

---

## §9 R0 prerequisites (pending operator-side)

See `vsd-vault/proposals/drafts/qresce-0001-r0-artifacts/R0_PREREQ_CERTIFICATE.DRAFT.md` v3 for the 7-item operator action queue:

1. Trademark attorney clearance (USPTO TESS templates provided)
2. Domain purchases (.com + .io + .ai + .network minimum-viable)
3. GitHub `qortroller` org + `qortroller-pebble-prototype` repo slot
4. Social handles visual-verify + reserve
5. 30s audio sample recording
6. Sign R0 certificate → promote to `QRESCE-0001-R0-CERTIFICATE.md`

**Brand-iteration provenance** (Qoresence → Qorsence → QorSense → Qorify[eliminated] → ConTrolla[skipped] → QorTroller[FINAL]) preserved for trademark prosecution support; each iteration deep-verified via RDAP + GitHub + PyPI + npm + Bing SEO comparative.

---

*End QorTroller Brand Guidelines v1. Brand-lock commit `2c762835`. Living document — amend as operational learnings surface from public-launch + grant submission + community adoption.*
