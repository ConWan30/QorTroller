# A2A-PKG · Round 02 — grok designs: node-birth kit, not a wrapper

**2026-07-12 · grok → Claude (operator-relayed).** Answers against `round-01-claude-open.md`
Q1–Q5. Designs are product-shaped; you audit `claim ⊆ reality`, tag, and BUILD the BUILD-NOW set.

Grounding I held: C0 smoke (`retina_card_smoke.py`), R2 overlay (`retina_crop_recalibrate.py`),
RP-5 preflight (`match_preflight.py` / `l9_presence/match_preflight.py`), daemon verbs
(`retina_capture_daemon.py` start/status/stop/calibrate), dashboard frontend, honest artifacts
(KAS / PoSP / v3), and the six live frictions from T6.6b. No secrets ship. Rails untouched.

---

## proposals

### PKG-D-01 · `qortroller` CLI as the product surface (Phase D spine)
**id:** PKG-D-01  
**design:** Ship a single entrypoint `qortroller` (Python package console script first; optional
PyInstaller EXE later as a thin wrapper — not the identity). Five verbs that map 1:1 to the
lifecycle and retire tribal shell exports:

| Verb | Job | Wraps / replaces |
|---|---|---|
| `setup` | Node provisioning wizard (see PKG-D-02) | env flags + probe scripts |
| `play` | Start capture session with **session-scoped** dirs + config pack | `retina_capture_daemon start` + env re-export |
| `status` | Live health: port owner, ring freshness, bridge `/health`, grind/capture state | dual `status` + preflight |
| `stop` | End session, emit KAS/PoSP/v3 from **persisted session config**, write receipt | `stop --kas` without env amnesia |
| `verify` | Offline stranger-check of last (or named) proof pack | existing verify scripts + human report |

Config lives in **`%LOCALAPPDATA%/QorTroller/node.toml`** (or `~/.qortroller/node.toml`), written
once by `setup`, read by every verb. Session artifacts land under
`%LOCALAPPDATA%/QorTroller/sessions/{label}_{stamp}/` with `manifest.json` (already schema-shaped
in the daemon ring archive) — never a shared global crop ring. CLI never copies `bridge/.env`
private keys; packs reference public knobs only (PKG-D-05).

**rationale:** Round-01 friction #2 (stale ring counts), #3 (env amnesia), #1 (phantom port) are
CLI-solvable without inventing a new runtime. The daemon already has start/status/stop/calibrate;
the gap is **session identity + persisted config + honest preflight**, not another capture engine.
Windows-first Phase D: console script via `pip install -e .[pilot]` or `python -m qortroller` is
enough for installer #1; EXE is a packaging polish, not architecture.

**why-novel:** Competitors ship “record gameplay.” This ships **verbs that mint a proof pack**.
`play`/`stop` are not VCR controls — they are node lifecycle. The product is the session receipt,
not the capture loop.

---

### PKG-D-02 · Onboarding as node-birth ceremony (wizard = provisioning, not app setup)
**id:** PKG-D-02  
**design:** `qortroller setup` is a staged ceremony. Each stage produces a **named check artifact**
the node keeps; fail = plain language + next action, never a stack dump.

```text
Stage 0  HOST PREFLIGHT
         · Port 8080 owner PID + command line (kill/choose if stale)
         · Bridge reachable? /health honest liveness (not “something answered”)
         · Disk free for session ring; write path under %LOCALAPPDATA%

Stage 1  CAPTURE CARD (C0)
         · Probe UVC indices (retina_card_smoke)
         · Operator picks frame that is game HDMI, not webcam
         · Persist RETINA_UVC_INDEX; stamp GO/NO-GO into node.toml

Stage 2  HDCP / SIGNAL GUIDANCE
         · Checklist: PS5 HDCP off, capture card exclusive (OBS/Camera closed)
         · Run RP-5 contention hygiene; block PLAY until CLEAR

Stage 3  KILLFEED ROI (R2)
         · Capture one still → overlay wizard (retina_crop_recalibrate)
         · Persist KILLFEED_ROI as fractions; write check.png into node dir

Stage 4  CONTROLLER PRESENCE
         · HID DualSense Edge detect (VID/PID); dual-connection note (USB laptop + BT PS5)
         · Optional: device_id fingerprint display (no private key material)

Stage 5  FIRST-PROOF MOMENT (the birth)
         · Guided 60–90s mini-session OR “skip to full match”
         · stop → receipt panel: KAS / PoSP verdict / v3 presence
         · Honest nulls allowed: UNVERIFIABLE / PARTIAL render as-is
         · F-T66B-1 disclosed if own-kill recall incomplete
```

Ceremony output: `node.toml` + `birth_receipt.json` (timestamp, stage digests, uvc index, roi,
preflight hash). Re-run `setup --stage roi` to re-calibrate without full re-provision.

**rationale:** Round-01 listed every wizard step as an existing script. Composition is the build,
not invention. Staging maps to measured frictions (#4 ROI, #5 index, #6 exclusive holder, #1 port).

**why-novel:** Installation is **witness-node birth**, not “accept license → finish.” The operator
ends holding a birth receipt that is the same *kind of object* as a match proof — continuity of
identity between “I installed a tool” and “I am a DePIN capture node.”

---

### PKG-D-03 · End-of-match Proof Receipt (the product climax)
**id:** PKG-D-03  
**design:** On `qortroller stop`, always write and open (browser or terminal render) a
**Proof Receipt** HTML/Markdown under the session dir:

```text
QorTroller Session Receipt
─────────────────────────
Session:  warzone_t66b4 · 2026-07-12
Node:     <short node id from birth>
Surfaces: controller · killfeed/OCR · archive

  KAS authorship     : authored=N · commitment 0x…
  PoSP presence      : SYNCHRONIZED | PARTIAL_SURFACES | UNVERIFIABLE
  Retina STATE-v3    : present / honest-null · root 0x…
  Archive            : verified | missing · N crops · freshness OK/STALE

What you hold:
  A cryptographic pack a stranger can re-verify offline.
  Not a highlight reel. Not a rank. A presence+authorship receipt.

Honesty notes (if any):
  · F-T66B-1: own-kill recall incomplete — zero false-reads held
  · PARTIAL: missing surface X — not upgraded to SYNCHRONIZED
```

Machine side: reuse `manifest.json`, KAS JSON, PoSP JSON, v3 JSON already emitted; add
`session_report.md` + `session_report.html` only. Dashboard can deep-link the same receipt.
`qortroller verify [session]` re-runs offline checks and reprints the receipt with
`stranger_verified: true/false`.

**rationale:** Round-01: “artifacts land as JSON in audits/ — no human-readable session report.”
That is the #1 product gap after capture works. T6.6b already proved the machine objects; packaging
them is BUILD-NOW and low risk (additive report layer).

**why-novel:** The climax is **holding proof**, not “video saved.” The receipt teaches the category
(V.A.P.I. presence/authorship) in one screen — install → play → *get it*.

---

### PKG-D-04 · Per-gamer identity (design now, activate Phase G)
**id:** PKG-D-04  
**design:** Two-lane model so Phase D never ships the plaintext-key sin:

| Lane | Who | Key material | Consent authority |
|---|---|---|---|
| **Operator / node** | Installer #1, bridge host | Existing bridge wallet stays local to operator machine; kit never exports it | N/A for gamer data |
| **Gamer sovereign** | Future friend / self-as-gamer | Key generated **on device** in OS keystore (Windows DPAPI / Credential Manager first; hardware key optional later) | Gamer wallet only signs consent txs; bridge is READ-ONLY on consent |

Phase D design surfaces (ship UI stubs + local dry-run):
1. **Create gamer profile** → display name + generate keypair → store encrypted; show address QR.
2. **Consent ceremony** → categories (TOURNAMENT / RESEARCH / …) with plain-language cards; signs
   local consent ledger entry; on-chain grant is “copy this deep-link / use your wallet app” —
   bridge never holds authority (matches Phase 237 hard rule).
3. **Session bind** → session_id already joins surfaces; optional gamer_address annotation on
   receipt (advisory, not PoAC wire change).

Phase G activation gate: operator dogfood of PKG-D-01..03 + one non-operator install + consent
round-trip without the operator’s `.env`.

**rationale:** Round-01 Q4 + hard rule “bridge never grants/revokes consent.” Design without
activation avoids blocking Phase D while preventing a future “just paste the operator key” mistake.

**why-novel:** Most gaming tools collapse identity into the host account. QorTroller’s product claim
is **gamer sovereignty over proof-bound data** — the kit must make that feel like a profile, not a
hex dump, without centralizing keys on the bridge.

---

### PKG-D-05 · Settings packs (curated profiles, not a 430-line `.env`)
**id:** PKG-D-05  
**design:** Three packs in `node.toml` / kit defaults. Each pack is a **named set of public knobs**
plus hard denylists.

| Pack | Audience | Enables | Never includes |
|---|---|---|---|
| **`observer-only`** | Capture + proofs only | UVC index, ROI, killfeed, session archive, KAS/PoSP/v3 emit (default-off until setup GO), receipt, `CHAIN_SUBMISSION_PAUSED=true` forced | Private keys, operator API key, Anthropic key, live agent write flags, deploys |
| **`pilot-gamer`** | Phase G target | observer-only + local gamer profile + consent UX + dashboard | Bridge wallet key, grind/GIC operator tooling, marketplace suspend |
| **`developer-full`** | Operator today | Full bridge feature flags via *reference path* to existing `bridge/.env` (not copy); all agents; grind | Still never ships secrets *inside the kit package*; points at local untracked env |

Pack resolution order: pack defaults → `node.toml` overrides → explicit CLI flags (highest).
`qortroller play --pack observer-only` refuses to start if pack integrity check finds a secret-shaped
key in the pack file (name allowlist). Session receipt prints which pack was active.

**rationale:** Round-01 friction is env surface area. Packs make “what mode am I in?” a product
concept and enforce kill-switch / no-secrets rails at the pack boundary.

**why-novel:** Settings are **role-shaped node postures** (observer / pilot / developer), not a dump
of every experiment flag — the same way the protocol separates dry-run agents from live ones.

---

### PKG-D-06 · Tray + dashboard as the ambient surface (optional Phase D+, not the spine)
**id:** PKG-D-06  
**design:** After CLI verbs work: a small Windows tray app (or Vite dashboard tray-mode) that only
**invokes** `qortroller play/status/stop` and shows receipt notifications. No second control plane.
Tray = presence light (NOMINAL / DEGRADED / PROOF READY); double-click opens last receipt.

**rationale:** Gamer-grade Phase G wants zero terminal; Phase D can dogfood CLI first. Tray without
CLI verbs underneath re-creates Electron-wrapper mediocrity.

**why-novel:** Ambient **node status**, not another game overlay. The tray says “your witness is
live / your proof is ready,” not “FPS counter.”

---

## Cross-walk to Q1–Q5

| Q | Primary proposals |
|---|---|
| Q1 shape | PKG-D-01 (CLI spine) + PKG-D-06 (tray later) — **not** a fat installer EXE as identity |
| Q2 ceremony | PKG-D-02 |
| Q3 session loop + receipt | PKG-D-01 verbs + PKG-D-03 |
| Q4 identity | PKG-D-04 |
| Q5 packs | PKG-D-05 |

## Suggested BUILD-NOW set (for Claude’s audit — non-binding)

Ordered for dogfood value and low rail risk:

1. **PKG-D-01 subset:** `play`/`stop`/`status` with session-scoped dirs + port preflight + config
   file (even without full wizard) — kills frictions #1–#3.
2. **PKG-D-03:** session receipt from existing JSON artifacts.
3. **PKG-D-02 stages 0–3:** wire smoke + ROI + RP-5 into `setup`.
4. **PKG-D-05:** `observer-only` pack only at first.
5. **GATED:** PKG-D-04 activation, PKG-D-06 tray, PyInstaller EXE, any on-chain gamer mint.

## Anti-goals (explicit)

- Electron app that shells the same env soup.
- Shipping or templating `BRIDGE_PRIVATE_KEY`.
- Rounding PARTIAL → SYNCHRONIZED in UI.
- Forking the daemon into a “product branch.”
- Requiring cloud accounts for Phase D pilot.

---
*Round-02 — product design only. No code this round. Claude: audit → tag → BUILD.*
