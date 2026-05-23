# Claude Design prompt — QorTroller Reference (motion + novel tweaks)

> Paste this into Claude Design (claude.ai/design) **with the file
> `frontend/public/qortroller-reference.html` attached**. Your job is to make
> that one file *come alive* — add animation and novel, tasteful tweaks — without
> changing a single fact or breaking brand discipline. Return one enhanced,
> self-contained HTML file that drops back in at the same path.

---

## 1 · What this page is

The **QorTroller Reference** — the canonical "what / how / forward" codex tab in
the operator frontend. It is the single page a newcomer, grant evaluator, or
partner reads to understand **everything representative of what QorTroller is,
how it functions, and how it will look and function going forward.**

QorTroller is a cryptographic anti-cheat protocol for competitive console gaming
— the reference implementation of **V.A.P.I.** (Verifiable Autonomous Physical
Intelligence), a coined DePIN sub-category on IoTeX. Tagline: **"QorTroller —
Core Controllers of their gaming data."**

The page already carries the brand-locked content in 11 sections (What · PITL
stack · PoAC 228-byte record · Humanity probability · GIC chain · Operator fleet
· Sovereignty/consent · On-chain · FROZEN-v1 primitives · Hardware · Forward
roadmap). **The content and structure are done.** Your work is purely the
*motion and feel* layer on top.

## 2 · Aesthetic north star (FROZEN — match it, don't reinvent)

**"Forensic instrument panel meets living cryptographic specimen."** Oscilloscope
graticule, evidence-room labelling discipline, laboratory measurement device —
but **alive**, because there's a real human on the controller.

- Palette: void-black `--bg #04060a` → `--panel #0a0e14`; amber `--accent-amber
  #f0a868` (operator + medial-T); chain-green `--chain #5bd6a3` (cryptographic
  flow); red `#d65b78` (honest failure only). All tokens are already declared in
  `:root`.
- Type: **Syne** (display/wordmark/headings, medial-T at weight 800), **JetBrains
  Mono** (all data, hashes, numbers). Both are served locally from `/fonts/` —
  **keep them local, add no font CDN.**
- Anti-tropes: no purple-cyan Web3 gradients, no glassmorphism, no playful icons,
  no marketing hero parallax, no emoji (the amber medial-T is the brand's emoji).

## 3 · Hard constraints (do not violate)

1. **Do not change any fact.** The 228-byte PoAC wire format (164 body + 64 sig),
   `SHA-256(raw[0:164])` chain-link rule, the PITL layer codes (0x28/0x29/0x2A
   hard; 0x30/0x31/0x32/0x2B advisory), the humanity formula weights
   (0.28/0.27/0.20/0.15/0.10), the consent bitmask positions (0–3), chain ID
   4690, the contract addresses, and the FROZEN-v1 primitive names are
   **load-bearing and frozen**. Animate them; never edit them.
2. **Brand casing is load-bearing.** `QorTroller` always renders with the medial
   capital **T** in amber — never `Qortroller` / `QORTROLLER` / `Qor Troller`.
   **`V.A.P.I.`** (with periods) in display copy; `VAPI` (no periods) only inside
   code/byte-literal contexts (e.g. `"VAPI-CONSENT-v1"`, `isFullyEligible()`).
3. **Honesty discipline.** Green is *earned* — only ever attached to something
   cryptographically true (a real hash, a verified chain). If you add a live
   verifier, it must run real `crypto.subtle.digest` — never fake a green state.
   Amber = honest pause/advisory; red = honest failure, always with a text label.
4. **Self-contained, single file.** One `.html` with inline `<style>` (and inline
   `<script>` if you add JS). No external resources except the local `/fonts/`.
   No build step. It must open correctly both standalone and inside an iframe
   (`sandbox="allow-scripts allow-same-origin"`).
5. **Respect `prefers-reduced-motion: reduce`** — every animation must degrade to
   instant/static. The page already gates its baseline motion this way.
6. **11px readable floor** on shipped text. Motion may briefly scale text, but it
   must settle ≥ 11px.

## 4 · The ask — motion as evidence of computation

Motion here is **evidence of the protocol computing — never decoration.** Three
primitives, reused throughout (the same vocabulary as the dashboard):

- **Hash re-derive / settle** — a value resolving from amber → chain-green over
  ~280 ms, mono, ticking into place. Use real `crypto.subtle` where a hash is
  shown.
- **Chain-link landing** — a new element fades-up ~120 ms with a one-shot
  chain-green glow pulse.
- **Breathing** — living surfaces respire over ~2.8 s (opacity 0.85 ↔ 1.0). The
  "a real human is here" signal.

No bounces, no spring overshoot, no marketing entrance "wow." Easing is the
instrument curve `cubic-bezier(0.2, 0.6, 0.2, 1)`.

### Per-section briefs (animation hooks are already in the markup as `data-anim`)

- `data-anim="hero"` / `wordmark` — on load, the graticule background draws in
  faintly; the medial-T amber settles last (the brand "powering on"). Subtle.
- `reveal` (every `<section>`) — **scroll-triggered reveal**: each section fades +
  rises ~12px as it enters the viewport, once. Stagger child panels by ~60 ms.
  IntersectionObserver; respect reduced-motion.
- `poac-bytes` — the **228-byte band assembles**: the 164 body segment fills
  left-to-right in chain-green, then the 64-byte signature segment snaps in amber
  — visualizing "body signed, then signature appended." Tasteful, ~600 ms total.
- `hash` / `formula` — when scrolled into view, the `SHA-256(...)` line does a
  one-shot scan-line wipe and the result settles amber → chain-green. Bonus: make
  the PoAC hash line a **real** in-browser SHA-256 of a sample 164-byte buffer so
  the displayed digest is genuine (label it "sample").
- `gic-chain` — the ribbon **lands link by link** left→right on first view, the
  final link keeping a steady breathing glow (it already pulses — deepen it).
- `formula` (humanity) — animate a small **probability gauge** filling to a
  representative p_human as the section enters; the five weighted terms can
  highlight in sequence to show the fusion. Keep the numbers exact.
- `ladder` — the O0→O3 operator-initiative ladder **illuminates step by step**;
  the live `O3 · Acting` step gets the amber breathing treatment.
- `stack-table` — PITL rows **illuminate top-to-bottom**; the two hard-cheat rows
  (0x28, 0x29/0x2A) carry a brief red edge-flash to mark "these block eligibility."
- `primitives` — render the FROZEN-v1 family as a quietly **living constellation**:
  each primitive card glints chain-green on a slow, offset cadence (evidence
  accumulating), not a disco.

### Novel tweaks (pick the few that elevate, skip the rest)

- A faint **hash-storm** layer behind the hero only (8-char hex slugs drifting up,
  low opacity) — the same honest "the bytes are real" motif as the dashboard.
  Off under reduced-motion.
- A thin **scroll-progress hairline** in amber at the very top.
- A right-side **section rail / mini-nav** (01–11) that highlights the active
  section as you scroll — instrument-panel index, mono, subtle.
- Optional: a small **Tweaks toggle** (forensic default · "cinematic" deepens
  glow + grain) mirroring the dashboard's vibe layer — but default must stay
  forensic-restraint.

## 5 · Performance & accessibility

- 60 fps; prefer `transform`/`opacity` and CSS where possible; one
  IntersectionObserver, not per-element timers. Pause off-screen work.
- Keyboard + screen-reader unaffected: reveals must not hide content from
  assistive tech (animate from a visible baseline, or reveal on observe without
  `display:none` traps). Headings/landmarks stay intact.
- Everything no-ops cleanly under `prefers-reduced-motion: reduce`.

## 6 · Deliverable

One enhanced, self-contained `qortroller-reference.html` — same sections, same
facts, same palette/type, now alive. It must render correctly inside the
operator frontend's `06 · Reference` tab (an iframe) and standalone in a browser.
When done, do a brand self-check: medial-T amber on every wordmark; `V.A.P.I.`
(periods) in all display copy; zero emoji; green only where something is actually
verified.
