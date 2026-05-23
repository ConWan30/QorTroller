# QorTroller frontend — current-state design brief (for Claude Design)

> **Give this file to Claude Design.** It is an accurate snapshot of how the
> QorTroller operator frontend **looks and is built right now** — brand, design
> tokens, components, motion, the gamer-vibe layer, the full tab IA, and the
> Evidence OS surface. Design *against this reality*; don't reinvent it. When you
> propose new work, reuse these tokens, classes, and primitives so the output
> drops into the real React + Vite app cleanly.

Stack: **React 18 + Vite**, react-query data hooks, framer-motion, wagmi/viem.
Brand-lock: **QRESCE-0001 v0.5**. Repo: `github.com/ConWan30/QorTroller`.

---

## 0 · One-paragraph context

QorTroller is a cryptographic anti-cheat protocol for competitive console gaming
— the reference implementation of **V.A.P.I.** (Verifiable Autonomous Physical
Intelligence), a coined DePIN sub-category on IoTeX. Tagline: **"QorTroller —
Core Controllers of their gaming data."** The frontend is a desktop-first
operator/grant-evaluator dashboard. Aesthetic north star: **"forensic instrument
panel meets living cryptographic specimen"** — void-black, oscilloscope
graticule, evidence-room labelling, *alive* because a real human is on the
controller. Anti-tropes: no purple-cyan Web3 gradients, no glassmorphism, no
playful icons, no marketing parallax, **no emoji**.

---

## 1 · Brand discipline (load-bearing — never drift)

- **Wordmark:** `QorTroller` with the medial capital **T** in amber `#f0a868`
  (Syne weight 800), `Qor` + `roller` in `#d4dde8` (Syne 700). Never
  `Qortroller` / `QORTROLLER` / `Qor Troller` / `qorTroller`.
- **Category:** `V.A.P.I.` (with periods) in display copy; `VAPI` (no periods)
  only in code/byte-literal contexts (`isFullyEligible()`, `"VAPI-CONSENT-v1"`).
- **Honesty discipline:** green is *earned* — only attached to something
  cryptographically verified (a real `crypto.subtle.digest` returning OK, an
  intact chain). Amber = honest pause/advisory (`KILL-SWITCH PAUSED`); red =
  honest failure, always with a text label (`MISMATCH`, `BRIDGE UNREACHABLE`,
  `MOCK DATA`). Status colour is **never** shown without a text label.
- **noMock:** grind-critical surfaces never fabricate data; a bridge outage shows
  an explicit `—` / offline state, never invented numbers.
- **Hashes:** JetBrains Mono, ligatures off, middle-ellipsis only (`7f3a…0c4e`).
- **Min readable size 11px** on shipped surfaces.

---

## 2 · Design tokens (live values from `src/design/qortroller-kit.css`)

These apply under a `.qt-design-root` ancestor (every design view wraps in it).

```css
/* Surfaces (void-black forensic) */
--bg:#04060a;  --panel:#0a0e14;  --panel-soft:#0b1119;  --panel-raised:#11161f;
/* Borders — mostly-invisible hairlines */
--border:#1b2433;  --border-soft:#141b27;  --border-strong:#2a3850;
/* Text — no pure white */
--text:#d4dde8;  --text-dim:#8a98ab;  --text-faint:#5a6878;  --text-ghost:#36404e;
/* Accents */
--accent-amber:#f0a868;  --accent-amber-soft:rgba(240,168,104,.35);  --accent-amber-trace:rgba(240,168,104,.08);
--chain:#5bd6a3;                 /* cryptographic-flow green (verified OK) */
--gamer-cyan:#00d4ff;            /* gamer-tier accent (sparingly) */
/* Status (semantic — always paired with text) */
--status-live:#5bd6a3;  --status-pending:#f0a868;  --status-blocked:#d65b78;
--status-dormant:#5a6878;  --status-verified:#22d3ee;  --status-mock:#d65b78;
/* Type */
--font-display:'Syne';  --font-body:'Syne';  --font-mono:'JetBrains Mono';
/* Geometry / motion */
--radius:6px;  --strip-h:48px;
--dur-tick:150ms;  --dur-breath:4s;
--ease-snap:cubic-bezier(.22,1,.36,1);  --ease-instrument:cubic-bezier(.16,1,.3,1);
```

**Fonts:** Syne (display/wordmark/headings) + JetBrains Mono (all data) — loaded
via Google Fonts in `index.html` for the SPA, and served **locally** from
`/fonts/*.ttf` for the self-contained iframe pages (Grant Brief, Reference).
Headings = Syne; numbers/hashes/labels = JBM. (`Rajdhani` is legacy — do not use.)

**Reusable kit classes:** `.p-panel` / `.p-panel--soft|--raised|--breath`,
`.p-head` + `.p-head__eye` / `.p-head__meta`, `.s-chip` + `--live|pending|blocked|dormant|verified|mock`,
`.btn` + `--primary|secondary|ghost|danger|sm`, `.mono` `.hash` `.dim` `.faint`
`.amber` `.chain` `.err`, `.eye` `.label`, `.qt-wordmark` (+`.t`), `.overlay-panel`
(+`--accent`), `.ribbon` / `.ribbon__cell` (+`--filled|--latest|--fx-pulse|--fx-bloom|--fx-shockwave`),
`.twin-stage` (graticule).

---

## 3 · Motion primitives (`src/design/motion.js`)

Motion is **evidence of computation, never decoration.** Easing = instrument
curve. `prefers-reduced-motion` snaps everything to instant.

- `useReDeriveHash(input, compareTo?)` — real in-browser `crypto.subtle.digest`
  → `{hex, state:'computing'|'settled'|'mismatch', duration, settledAt}`.
- `useChainPulse(realLength)` — fires a landing pulse only when the **real**
  polled chain length increases (never simulates growth).
- `useRelativeTime(ts)` · `useTick(ms, paused)`.
- CSS: `.motion--settle` (amber→chain 280ms), `.motion--mismatch` (red flash),
  `.motion--land`, `.motion--pulse`, `.motion--scan`.

---

## 4 · Primitives (`src/design/Primitives.jsx`)

`Wordmark` (medial-T), `StatusChip` (always with a text child), `Panel`
(eyebrow + meta + optional breath), `OverlayPanel` (floating translucent panel
for the twin stage), `Hash` (middle-ellipsis), `Icon` (inline Lucide-style SVGs,
stroke 1.5, no fill: chevron/copy/external/info/x/search/pause/shield/link/alert/clock/play/refresh/cpu).

---

## 5 · Gamer-vibe Tweaks layer (`src/design/Tweaks.jsx`) — the "alive" surface

App-root provider (`QtTweaksProvider`, mounted in `App.jsx`). **Default state is
forensic-restraint** — the dashboard looks identical until the gamer opts in via
a fixed **"✦ Tweaks"** toggle (bottom-right). Persists to `localStorage`
(`qt.tweaks.v1`). Honesty preserved: a `VIBE · ARCADE` label shows in the foot
when off-forensic; green stays earned.

Controls (the gamer aesthetic, opt-in):
- **Vibe preset:** `forensic` (default) · `cinematic` · `arcade` — sweeps the knobs.
- **Accent palette:** gamer-cyan · chain-green · neon-pink · ultraviolet.
- **Atmosphere:** scanlines (+intensity) · CRT curve · film grain · glow.
- **Hash storm:** drifting real-hex particle canvas (+density).
- **Pace:** twin-breath seconds.
- **GIC landing FX:** pulse · bloom · shockwave · off.

Driven via CSS vars on `:root` (`--qt-glow`, `--qt-breath`, `--qt-scanline-alpha`,
`--qt-accent`) that `qortroller-kit.css` overlays react to. `LevelUpBadge` flashes
on real GIC chain-length 10× crossings. All overlays honour reduced-motion and
are `pointer-events:none`.

---

## 6 · Information architecture — the dashboard tab bar

Top bar (`src/ViewSelector.jsx`): **left** = Syne medial-T wordmark + `V.A.P.I. ·
phase 235` tag + an `Evidence OS →` link; **center** = numbered **stacked** tabs
(number above label, amber on active, framer-motion pill); **right** = `● ON-CHAIN`
status + truncated merkle hash. (An agent-count chip used to sit here; it was
removed.)

Six tabs (`App.jsx` `VIEW_MAP`, lazy-loaded, named exports):

| Tab | Accent | What it is now |
|---|---|---|
| **01 Gamer** | cyan | Hero. Full-bleed **real 3D Controller Twin iframe** on a graticule stage; four floating translucent corner overlay panels (Capture Health · Latest GIC Hash · Consent Matrix · Analytics); a live grind-integrity **chain ribbon** along the bottom (GIC landing FX); the APOP evidence prism; a right-edge PCC drawer; the consent drawer; level-up badge; breathing twin vignette. All telemetry from real `noMock` bridge hooks. |
| **02 Forensic · Explorer** | chain-green | Side-by-side cryptographic **workbench**: PoAC byte table (228 bytes) left, CryptoReplayPanel verifier readouts right; GicChainTimeline + verifier registry below. Real SHA-256 re-derivation. Scrolls internally. |
| **03 Operator · Evidence** | amber | Honesty heroes up top: **kill-switch** state + **fleet coherence** (contradictions/orphans/inversions). Then tournament pre-flight gates; AIT separation matrix; PCC; protocol coherence + Merkle anchor; blocking reasons. Scrolls internally. |
| **04 VPM · Proofs** | amber | Filterable proof gallery (horizontal card rail + filter chips) → selected proof renders via the **FROZEN render rule** (`fetch(no-store)` → `srcDoc`, sandbox `allow-scripts allow-same-origin`). **The view page-scrolls; the proof iframe auto-sizes to the certificate's full height; the inspector is sticky.** Inspector: live SHA-256 verdict (HASH OK / MISMATCH via real `crypto.subtle`), FLIP-A-BYTE tamper, visual-grammar verdict, provenance. |
| **05 Grant · Brief** | amber | Full-bleed iframe of the brand-locked IoTeX grant deck (`/grant-brief.html`, 9 slides, `deck-stage.js`, arrow-key nav, 1/9 counter). Public, no auth. |
| **06 Reference** | chain-green | Full-bleed iframe of the **Reference codex** (`/qortroller-reference.html`): the canonical "what / how / forward" page — V.A.P.I. category + sovereignty thesis, PITL stack, 228-byte PoAC, humanity formula, GIC chain, operator fleet O0→O3, consent, on-chain, FROZEN-v1 primitives, hardware, roadmap. Self-contained; carries `data-anim` hooks for a motion pass. |

Developer / Manufacturer / Marketplace / BRP views still exist in `VIEW_MAP` but
are intentionally off the tab bar.

---

## 7 · Evidence OS (`/os/*`) — secondary surface, same design language

A separate proof-native IA reached via the `Evidence OS →` link. It now wears the
**same chrome** as the dashboard: `.qt-design-root` + the kit, a Syne medial-T
wordmark in the StatusStrip (`QorTroller` + `Evidence OS`), and a **numbered
top-tab bar**. De-duplicated against the dashboard's 6 tabs — it keeps only the
three surfaces with no dashboard analog:

- **01 Evidence Graph** — HID → on-chain causal DAG (11 nodes, 4 edge styles).
- **02 Forensic Replay** — re-derive historical claims + the public deep-link
  viewers (session / gic / record / vhp / algorithms).
- **03 Protocol State** — PV-CI invariants / agent fleet / kill-switch posture.

A `StatusStrip` shows Agents · PV-CI · VPM · GIC · Merkle · Blockers (honest `—`
when unavailable). Tokens are shared `--os-*` that equal the design tokens.

---

## 8 · Visual foundations recap (answer these the same way if you extend)

- **Backgrounds:** full-bleed `#04060a`; optional graticule (24px minor + 96px
  major hairlines, very low alpha). No images, no gradients beyond the graticule.
- **Cards:** 1px `--border` hairline, ~6px radius, `--panel` bg, mono UPPERCASE
  eyebrow, optional status chip top-right. No drop-shadow, no avatar.
- **Elevation:** near-black layering + faint border + inset hairline — not
  material-design float. `--panel` → `--panel-raised` on hover.
- **Radii:** 2px (chips/byte cells), 4–6px (panels/buttons), pill (filter only).
- **Hover:** raise one panel tier + 1px stronger border; buttons gain a 1px amber
  outline. **Press:** no shrink; background drops a tier.
- **Transparency:** used for translucent overlay panels + glow halos + ghost
  (kill-switch) dashed lines. **No backdrop-blur frosted glass** on instrument
  panels (the twin overlays use a light blur only).
- **Imagery:** image-light by discipline. The "imagery" is the wordmark, the 3D
  twin iframe (reserved rectangle — never draw a controller), and the byte
  tables / chain timelines / graticule rendered as first-class heroes.

---

## 9 · Hard technical constraints (for anything that ships to code)

1. **Never draw a 3D controller.** The twin is a real external iframe
   (`/controller-twin.html?minimal=1`); treat it as a reserved rectangle UI
   composes around (overlays at `z-index ≥ 3`).
2. **VPM render rule is FROZEN:** `fetch(url, {cache:'no-store'}) → text() →
   srcDoc`; never iframe `src=`; sandbox exactly `allow-scripts allow-same-origin`.
3. **Frozen facts** (don't alter in any surface): PoAC 228 bytes = 164 signed
   body + 64 ECDSA-P256 sig; chain-link hash = `SHA-256(raw[0:164])`; PITL codes
   (hard 0x28/0x29/0x2A, advisory 0x30/0x31/0x32/0x2B); humanity weights
   0.28/0.27/0.20/0.15/0.10; consent bitmask TOURNAMENT_GATE=0 / ANONYMIZED_RESEARCH=1
   / MANUFACTURER_CERT=2 / MARKETPLACE=3; GIC = `SHA-256(prev‖commitment‖verdict‖host‖ts_ns)`;
   IoTeX chain ID 4690.
4. **Grind-critical hooks stay `noMock:true`;** never add a mock fallback.
5. **Self-contained iframe pages** (Grant Brief, Reference) keep local `/fonts/`
   and inline `<style>` — no CDN.
6. **Desktop-first** (operator laptops + grant evaluators). Responsive reflow is
   a post-grant polish; don't block on it.

---

## 10 · How to use this brief

Tell Claude Design what you want to build/redesign; it should reuse the tokens in
§2, the primitives in §4, the motion vocabulary in §3, and respect §1 + §9. For
throwaway artifacts, output a self-contained HTML using the §2 palette + local
fonts. For production proposals, mirror the existing component shapes so the
hand-off to the React + Vite app is one-to-one. Always run the brand self-check:
medial-T amber on every wordmark; `V.A.P.I.` (periods) in display copy; zero
emoji; green only where something is cryptographically verified.

*Snapshot brief · reflects the frontend after the gamer-vibe Tweaks layer, the
Grant Brief (05) + Reference (06) tabs, the VPM page-scroll fix, the Evidence OS
design alignment, and the header agent-count removal. Living document.*
