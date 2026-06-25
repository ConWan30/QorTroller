# QorTroller Frontend — Design Brief for Revamp Handoff

> Hand this whole file to the design chat. It captures the existing frontend's
> identity, structure, palette, type, motion, and the hard brand/honesty rules a
> revamp must not break. Everything below is extracted from the live codebase
> (`frontend/`), not invented.

---

## 0. What this product is (one paragraph)

**QorTroller — Core Controllers of their gaming data.** It's the reference
implementation of **V.A.P.I.** (Verifiable Autonomous Physical Intelligence), a
DePIN sub-category where the physical-input source (a gamer + their DualSense Edge
controller) is also the cryptographic owner of the data those inputs generate.
Built native to IoTeX L1. The thesis: *cheating can't exist when humanity is
cryptographically proven and the gamer keeps sovereignty.* The frontend is a
**forensic instrument panel** — it shows live cryptographic state (hash chains,
SHA-256 re-derivation, on-chain anchors, capture-health), and lets operators act
on it. The aesthetic word that governs everything is **"forensic-restraint"**:
green is *earned* (only shown when a real hash re-derives OK), every red/amber
state carries a text label, nothing decorative claims a verdict it didn't compute.

**Audience:** three overlapping readers — gamers (their own data + grind
progress), grant evaluators / partners (IoTeX, Qorvo, hardware makers), and
operators (running the protocol). The current build leans hard toward the
grant-evaluator + forensic reader.

---

## 1. Tech stack (so the revamp stays compatible)

- **React 18 + Vite 6**, JS/JSX (some TS in the `brp/` 3D module).
- **Tailwind 3.4** (minimal usage — most styling is inline-style objects + a
  hand-written CSS kit, NOT utility classes).
- **framer-motion 11** for all motion.
- **@react-three/fiber + drei + rapier + three** for the 3D "Controller Twin".
- **recharts + d3** for charts; **wagmi + viem** for chain reads; **zustand** for
  the heartbeat store; **react-router-dom 6** for the public `/os/...` routes.
- Fonts loaded via Google Fonts in `index.html`.

Two parallel styling systems exist (this is the single biggest cleanup
opportunity — see §7):
1. **Legacy tier system** — `src/shared/design/tokens.js` + `src/styles/vapi-theme.css`
   (Rajdhani display font, per-tier cyan/orange/blue palettes). Used by the 6
   older "tier" views.
2. **Current design kit** — `src/design/qortroller-kit.css` scoped under
   `.qt-design-root` (Syne display font, amber + chain-green forensic palette).
   Used by the 4 grant-facing views. **This is the newer, canonical direction.**

---

## 2. Brand rules (LOAD-BEARING — a revamp must obey these)

From `docs/qortroller-brand-guidelines.md`:

- **Display name is always `QorTroller`** — medial capital T, like iPhone/GitHub.
  Never "Qortroller", never all-caps in display, never hyphenated/spaced.
  The wordmark renders the **T in amber** (`.qt-wordmark .t`).
- **Category is `V.A.P.I.` with periods** in display copy; `VAPI` without periods
  only in code identifiers. Don't "fix" the periods in UI copy.
- **Tagline (opening copy):** "Core Controllers of their gaming data."
- **Pronunciation:** KOR-TROLL-er. Qor (as in Qorvo / "core") + Troller (from
  Controller). Avoid any "troll" wordplay in UI copy.
- **Honesty discipline (non-negotiable):** chain-green = a real SHA-256
  re-derived OK. Never use green as a decorative/brand accent. Every error/warn
  state keeps a written label, never color-only. Mock/placeholder data must be
  visibly flagged (there's a `--status-mock` blinking chip and a `GlobalMockBanner`).

---

## 3. Color palette (exact hex, current canonical "forensic" kit)

From `src/design/qortroller-kit.css` (`.qt-design-root` scope):

| Role | Token | Hex |
|---|---|---|
| Void background | `--bg` | `#04060a` |
| Panel | `--panel` | `#0a0e14` |
| Panel soft / raised | `--panel-soft` / `--panel-raised` | `#0b1119` / `#11161f` |
| Border | `--border` / `--border-soft` / `--border-strong` | `#1b2433` / `#141b27` / `#2a3850` |
| Text | `--text` / `--text-dim` / `--text-faint` / `--text-ghost` | `#d4dde8` / `#8a98ab` / `#5a6878` / `#36404e` |
| **Brand amber** (the medial-T accent, primary action) | `--accent-amber` | `#f0a868` |
| **Chain green** (verified / re-derived OK — EARNED) | `--chain` | `#5bd6a3` |
| Status: live | `--status-live` | `#5bd6a3` |
| Status: pending | `--status-pending` | `#f0a868` |
| Status: blocked | `--status-blocked` | `#d65b78` |
| Status: dormant | `--status-dormant` | `#5a6878` |
| Status: verified | `--status-verified` | `#22d3ee` (cyan) |
| Status: mock | `--status-mock` | `#d65b78` |

**Palette character:** near-black blue-tinted void, a single warm **amber**
(`#f0a868`) for brand + action, a single mint **chain-green** (`#5bd6a3`) reserved
for cryptographic truth, and a muted rose (`#d65b78`) for blocked/mock. It is
deliberately NOT the three AI-default looks (cream/serif/terracotta;
black/acid-green; broadsheet). It's a desaturated instrument panel.

**Legacy tier palette** (older 6 views, `tokens.js`) — keep for reference but the
revamp should consolidate toward the kit above:
- Gamer: cyan `#00d4ff` + green `#00ff88` on `#050a0f`
- Developer: orange `#ff6b00` + amber `#ffaa44` on `#030507`
- Manufacturer: blue `#4a9eff` + gold `#ffd700` on `#020408`
- Curator tier badges: basic slate `#7d8590` → verified cyan `#22d3ee` → attested
  amber `#f59e0b` → premium gold `#facc15` (multiplier 1.0/1.5/2.0/3.0×).

---

## 4. Typography

Three roles, loaded in `index.html`:

- **Display / wordmark:** `Syne` (700–800 weight, tight `-0.02em` tracking).
  *(Legacy tier views still use `Rajdhani` — the kit replaced it with Syne; the
  revamp should standardize on Syne.)*
- **Body:** `Syne` (400–700).
- **Data / mono / hashes / eyebrows / chips / labels:** `JetBrains Mono`
  (400–700, ligatures OFF for hash legibility).

**Type alignment locks** (named vars so values never drift):
`--eye-tracking: 0.14em` (eyebrows), `--chip-tracking: 0.06em` (chips),
`--h2-size: 20px` (section headers), `--hash-size: 14px` (hash specimens).
Eyebrows & labels are uppercase mono, faint, wide-tracked. Hashes are mono,
`word-break: break-all`, chain-green when verified.

---

## 5. Layout & information architecture

**App shell** (`App.jsx`): fixed-viewport (`100dvh`, `overflow:hidden`), vertical
flex — a top **ViewSelector** tab bar, a 32px **eyebrow spine** (per-view name +
live readouts), an optional cross-view drift-alert badge, then the active view in
an `AnimatePresence` crossfade.

**Tab bar** (`ViewSelector.jsx`) — current live tabs (numbered `01`–`08`, stacked
number-over-label):
1. `01 Gamer` — the hero/twin view (cyan accent)
2. `02 Forensic · Explorer` — cryptographic depth, real SHA-256 (chain-green)
3. `03 Operator · Evidence` — self-monitoring honesty (amber)
4. `04 VPM · Proofs` — autonomous HTML-snapshot proof gallery (amber)
5. `05 Grant · Brief` — IoTeX grant-evaluator deck (amber)
6. `06 Reference` — canonical what/how/forward codex (chain-green)
7. `07 Partner · Brief` — manufacturer/partner pitch (amber)
8. `08 AI · Chat` — LLM assistant (cyan)

Bar layout: left = QorTroller wordmark + `V.A.P.I.` label + an `Evidence OS →`
deep link; center = the numbered tabs (never wrap, never side-scroll); right =
live `● ON-CHAIN / ○ PENDING` status + merkle-root tail + a "reality" heartbeat
dot. Several views are still in `VIEW_MAP` but off the bar (Developer,
Manufacturer, Marketplace, BRP) — dense tooling deferred.

**There's also a second IA** — a proof-native "Evidence OS" under React Router
routes (`src/os/workspaces/`: LiveMatchWorkspace, OperatorQueueWorkspace,
EvidenceGraphWorkspace, ForensicReplayWorkspace, ProtocolStateWorkspace) plus
public explorer views (`PublicSessionViewer`, `GicChainExplorerView`,
`PoacRecordExplorerView`, `AlgorithmCatalogView`, `MarketplaceView`).

**Layout primitives** (use these, don't hand-roll grids):
`.qt-grid` (12-col), `.qt-row` / `.qt-row--2` / `.qt-row--3`, `.qt-stage`
(full-bleed), with `.span-3..12` children.

**Signature layout element:** the **Controller Twin** — a full-bleed 3D
DualSense Edge on a graticule grid (`.twin-stage`, 96px/24px dual grid) with
floating glass `.overlay-panel` clusters in the corners and a **live "grind
ribbon"** along the bottom (one cell per GIC chain link, the latest cell glowing
chain-green). This is the single most distinctive thing in the product — protect
it.

---

## 6. Component kit (the reusable vocabulary)

From `qortroller-kit.css` — a revamp should keep these primitives and their names:

- **Panels:** `.p-panel` (+`--soft`/`--raised`/`--breath`), with `.p-head`
  (eyebrow + meta row) and `.p-body`. 6px radius, hairline borders.
- **Status chips:** `.s-chip` — mono, uppercase, dot + label, color variants
  `--live/--pending/--blocked/--dormant/--verified/--mock`. **Always label+dot,
  never dot-only.**
- **Buttons:** `.btn` `--primary` (amber fill) / `--secondary` (amber outline) /
  `--ghost` / `--danger` / `--sm`.
- **Verdict triplet:** `.qt-verdict` `--computing` (amber pulse) / `--ok`
  (chain-green) / `--err` (rose). **Only COMPUTING animates** — settled verdicts
  don't keep flashing.
- **Specimen frame:** `.qt-specimen` — diagonal corner brackets around
  "bytes-as-evidence" blocks (PoAC byte tables, proof stages).
- **Wordmark:** `.qt-wordmark` with amber `.t`.
- **Hash/mono helpers:** `.mono`, `.hash` (chain-green, break-all), `.dim`,
  `.faint`, `.amber`, `.chain`, `.err`.
- **Grind ribbon:** `.ribbon` / `.ribbon__cell` (`--filled` / `--latest`).

---

## 7. Motion (event-tied, restrained by default)

framer-motion variants in `src/shared/design/animations.js` and CSS keyframes in
the kit. **Every animation is tied to a real event** — the discipline is "honest
motion": don't animate idle decoration.

- Page/tab transitions: 0.18–0.22s fade+scale crossfade.
- Stagger reveals: 60ms (cards), 80ms (PITL layer rows), 120ms (pipeline nodes).
- `qt-settle` (amber→chain-green when a hash re-derives), `qt-mismatch-flash`
  (blocked), `qt-land` / `qt-fx-bloom` / `qt-fx-shockwave` (new GIC ribbon cell),
  `qt-breath` (4s panel respiration), `qt-live-pulse` (2s reality dot).
- All gated by `@media (prefers-reduced-motion: reduce)` → animations off.

**Opt-in "gamer vibe" layer** (`src/design/Tweaks.jsx` + kit overlays): a
fixed-corner Tweaks toggle lets a gamer turn on scanlines, CRT vignette, film
grain, hash-storm, glow intensity, accent-swatch, and GIC "level-up" flashes.
**Default is forensic-restraint (glow 0.35, no overlays).** The honesty rails
hold even in arcade mode. Keep this opt-in pattern.

---

## 8. The cleanup / revamp opportunities (what to actually improve)

1. **Consolidate the two styling systems.** Legacy `tokens.js` + `vapi-theme.css`
   (Rajdhani, per-tier cyan/orange/blue) vs the newer `.qt-design-root` kit
   (Syne, amber + chain-green). The kit is the canonical direction — migrate the
   6 legacy tier views onto it, or formally retire them.
2. **Standardize the font** on Syne display + JetBrains Mono data; drop Rajdhani.
3. **Reduce inline-style sprawl.** Most components use large inline-style objects
   instead of the kit classes/Tailwind. Pulling these into the kit primitives
   would cut drift and make a revamp tractable.
4. **Two IAs coexist** (the 8-tab SPA + the Evidence OS router). Decide which is
   the front door, or unify them.
5. **Tab count is high (8 + 4 off-bar).** Consider grouping (e.g. a "gamer"
   front door vs a "verify/forensic" cluster vs "partner/grant" decks).
6. **Mobile/responsive + a11y floor:** there are Android responsive guards and
   `viewport-fit=cover` handling already — keep visible keyboard focus,
   reduced-motion respect, and the side-scroll guards intact in any revamp.

---

## 9. What NOT to touch (hard constraints for the design chat)

- The **honesty rails**: green-is-earned, labels on every status, mock data
  visibly flagged. These are a product principle, not a style choice.
- The **brand name rendering** (`QorTroller` medial-cap, amber T; `V.A.P.I.` with
  periods in display).
- The **Controller Twin + grind ribbon** as the signature hero.
- The **forensic-restraint default** (the arcade vibe is opt-in only).
- Reduced-motion and keyboard-focus accessibility.

---

## 10. One-line summary for the design chat

> Revamp a void-black **forensic instrument panel** for QorTroller (a
> cryptographic gamer-data-sovereignty protocol on IoTeX). Keep the Syne +
> JetBrains-Mono type, the amber-action / chain-green-verified palette, the 3D
> Controller-Twin-with-live-grind-ribbon hero, and the strict honesty rails
> (green is earned, every status labeled). Main job: consolidate the two legacy
> styling systems into the single `.qt-design-root` kit, tame the inline-style
> sprawl and the 8-tab IA, and make the whole thing read as one disciplined
> instrument rather than several stitched-together design iterations.
