# QorTroller — Gamer View Direction (for the design chat)

> Build target: the **gamer-facing** view of QorTroller (tab `01 Gamer`). This is
> a design direction, not a spec dump — pair it with `DESIGN_BRIEF_FOR_REVAMP.md`
> (which holds the full palette, type, kit primitives, and hard brand rules). Read
> the §"What stays non-negotiable" section before you change anything.

---

## 1. The reframe (read this first)

The current frontend is tuned for a **grant evaluator / forensic auditor**:
restraint, hairlines, hashes, "is this real?". The gamer is a different reader.

**The gamer view is a player passport, not a smaller forensic dashboard.** It's
the post-match / profile-progression screen of a competitive game — except every
stat is cryptographically real instead of a server number someone could fake.
That IS the QorTroller pitch turned into a feeling: *your skill, your humanity,
your data — provably yours.*

- Forensic views answer **"is this real?"** for an auditor.
- The gamer view answers **"who am I here, and what have I earned?"** for the
  person holding the controller.

If a gamer opens this screen and it feels inert, we've failed — even though
"inert" reads as "disciplined" to the evaluator. The gamer view is allowed to
feel **alive**. It is not allowed to feel **generous with claims it can't prove.**

---

## 2. The hero: "your hands, proven"

Do **not** open with a big number + label + gradient accent. That's the template
answer, and QorTroller has something far more characteristic in the gamer's own
world: **the controller is the gamer.** The adaptive-trigger force-curve and
micro-tremor are a biometric fingerprint; the protocol proves "a live human on
this certified DualSense Edge, *now*."

The hero is a **Humanity Sigil** — a generative crest, unique to each gamer,
**deterministically seeded from the gamer's signed PoAC / device commitment.** In
the frontend today that seed is `device_id = keccak256(pubkey)` plus the live PoAC
`record_hash` chain as entropy — the *signed output* of the biometric proof
pipeline, not raw biometrics read in the browser. (Upgrade the seed to the
biometric-snapshot commitment if/when it is exposed gamer-side; until then the crest
is device/PoAC-derived and its label must say exactly that — it must not claim a
biometric seed it doesn't have.) The certified controller's proven identity becomes
a personal mark no one else can produce and anyone can verify.

This is not a stretch — the codebase already ships a hash-seeded ambient renderer:
- `src/brp/hash/deriveBrpSeed.ts`
- `src/brp/hash/mulberry32.ts`
- `src/brp/components/` (AmbientLayer, BrpCanvas, etc.)

Point that renderer at the gamer's identity hash instead of a scene seed, and the
crest is both delightful AND honest: it changes only when their proven identity
changes. Label it with the hash it derived from. Use the existing `qt-settle`
amber→chain-green motion for the moment it re-derives OK.

> One pixel, two truths: a gamer sees a crest that's unmistakably theirs; an
> auditor sees a deterministic function of a real signature. That duality is the
> entire QorTroller thesis in a single element.

The Sigil sits over / fused with the existing **3D Controller Twin** (the
full-bleed DualSense Edge on the `.twin-stage` graticule). Twin = live presence;
Sigil = proven identity. Together they own the stage.

---

## 3. Layout concept

A **cockpit**, not a grid of equal cards. The Twin + Sigil own the center stage;
everything else is a readable HUD around it. The core loop fits one screen, no
scroll.

```
┌──────────────────────────────────────────────────────────────┐
│  QorTroller          ◢ HUMANITY 0.94 · PROVEN       ● ON-CHAIN│  ← passport strip
├───────────────────────────────┬──────────────────────────────┤
│                               │  GRIND          [ 73 / 100 ]  │
│      ╱╲   LIVING TWIN +       │  ▰▰▰▰▰▰▰▰▰▱▱▱   ← GIC ribbon  │
│     (  )  HUMANITY SIGIL      │  next milestone in 7 · lv.7   │
│      ╲╱   hash-seeded crest   │                               │
│           breathing over the  │  TOURNAMENT      ◆ ELIGIBLE   │
│           live 3D controller  │  isFullyEligible() ✓ on-chain │
│                               │                               │
│   trigger force-curve ∿∿∿     │  YOUR DATA       ◇ ATTESTED 2×│
│   tremor spectrum   ▁▃▇▅▂     │  3 anchors · tier 2.0× (live) │
├───────────────────────────────┴──────────────────────────────┤
│  SOVEREIGNTY  research [on] · tournament [on] · market [off]  │  ← consent, gamer-controlled
└──────────────────────────────────────────────────────────────┘
```

### Five zones — each a game-UI convention made cryptographic

| Zone | Game-UI analog | The real QorTroller thing | Data source |
|---|---|---|---|
| **Sigil + Twin** | profile crest / character | live presence + proven identity (PoAC / device commitment) | PoAC chain (`device_id`/`record_hash`), heartbeat store, twin stream |
| **Grind ribbon** | XP / progression bar | GIC chain → 100; level-up each ×10 | `useGrindChain` / capture-health |
| **Tournament** | rank / unlock badge | `isFullyEligible()` on-chain | chain read / preflight |
| **Your Data** | inventory value | marketplace tier (1.0→3.0× by anchor count) | tier badge / marketplace |
| **Sovereignty** | settings / permissions | consent matrix — grant/revoke *yourself* | consent ledger / `ConsentMatrix` |

The grind ribbon and level-up already exist (`.ribbon`, `.ribbon__cell--latest`,
`.qt-levelup`, GIC-landing FX `qt-fx-bloom` / `qt-fx-shockwave`). Lean into them
here — this is the view they were built for.

---

## 4. Palette & type — within the brand locks, but warmer

Keep the brand exactly (see `DESIGN_BRIEF_FOR_REVAMP.md` §3–4): void `#04060a`,
**amber `#f0a868`** = the gamer's action, **chain-green `#5bd6a3`** = earned
truth, **Syne** display + **JetBrains Mono** data. Spend the gamer view's freedom
on **letting the void come alive** where the evaluator views stay flat:

- The Sigil + Twin get ambient depth/glow. In the gamer view the existing Tweaks
  "vibe" layer should sit **closer to default** — glow ≈ 0.5 (vs the forensic
  0.35), with scanline / CRT / grain one tap away (not on by default, but
  one-tap, not buried).
- **Amber stays the only "you did / you can do this" color.** Don't spray it.
- **Green stays earned.** A grind cell lights chain-green only when its hash
  actually chains. That single rail is what keeps the cockpit from feeling like a
  cosmetic progress bar.
- Status words keep their palette: `PROVEN`/`ELIGIBLE`/`ATTESTED` = chain-green or
  amber per the `.s-chip` variants; warming-up / pending = amber `--status-pending`;
  blocked / mock = rose `#d65b78` with its label.

Do **not** drift toward the three AI-default looks (cream-serif-terracotta;
black + acid-green; broadsheet hairlines). The gamer view's distinctiveness is the
**Sigil-over-Twin cockpit**, not a new color story.

---

## 5. Motion

Honest motion only — every animation tied to a real event (the existing
discipline). For the gamer view specifically:

- **Sigil re-derive:** `qt-settle` (amber → chain-green) the moment the identity
  hash verifies. This is the emotional beat — make it land.
- **Grind milestone:** `qt-fx-bloom` / `qt-fx-shockwave` on the freshest ribbon
  cell; `qt-levelup` flash at each ×10. Subtle, not gameshow.
- **Twin / panel breath:** `qt-breath` / `qt-twin-breath` at the gamer glow level.
- **Reality dot:** `qt-live-pulse` 2s — the "we're live" respiration.
- Everything respects `@media (prefers-reduced-motion: reduce)` → ambient layer
  and FX off, content fully usable.

---

## 6. Copy & voice

Write from the gamer's side of the screen. Plain, earned, never hype.

- Label things by what the gamer recognizes: **Grind**, **Tournament**,
  **Your Data**, **Sovereignty** — not `GIC chain`, `isFullyEligible`,
  `curator tier`, `consent ledger`. (Keep the technical term as a small mono
  sub-label where it adds proof, e.g. `isFullyEligible() ✓ on-chain`.)
- Verdicts are nouns the gamer owns: `PROVEN`, `ELIGIBLE`, `ATTESTED 2×`.
- Empty / warming-up states are invitations, not apologies: "Play a clean
  session to light your first chain link," not "No data available."
- Never play on "troll" (brand rule). Never claim a state that isn't anchored.

---

## 7. Build notes (so it drops into the existing app)

- Lives at tab `01 Gamer` → `src/views/GamerView.jsx` (lazy-loaded in `App.jsx`).
- Wrap the root in `className="qt-design-root"` so it inherits the canonical kit
  (`src/design/qortroller-kit.css`) — **migrate off the legacy `tokens.js` cyan
  tier palette** as part of this work (see brief §8 #1). Budget this as a real
  refactor, not a freebie: the current `GamerView.jsx` reads the `GAMER` cyan tier
  from `tokens.js`, so the migration has a regression surface (every tier-colored
  panel must be re-derived from the kit and re-checked against the honesty palette).
- Use the kit primitives, don't hand-roll: `.qt-stage` (full-bleed twin),
  `.overlay-panel` (corner HUD clusters, glass), `.p-panel` / `.s-chip` /
  `.qt-verdict` / `.ribbon` / `.qt-specimen` (for the byte/hash specimen under
  the Sigil), `.btn`.
- Reuse existing components where they fit: `ConsentMatrix`, `TierBadge`,
  `PoacChainRibbon`, the heartbeat store (`useHeartbeat`), the BRP renderer for
  the Sigil.
- Respect the side-scroll guards (`overflow-x: hidden`, `min-width: 0`) and the
  Android/`viewport-fit=cover` handling already in place.

---

## 8. What stays non-negotiable

1. **Honesty rails.** Green is earned (real SHA-256 re-derived). Every status
   carries its word + its on-chain anchor. Mock / warming-up state is visibly
   flagged. The **Your Data** zone shows the marketplace **tier multiplier
   (1.0→3.0×)**, never an estimated fiat/token value — the market is testnet /
   dormant, so a dollar figure would be a claim we can't prove. These are product
   principles, not style choices.
2. **Brand rendering.** `QorTroller` medial-cap with the **amber T**; `V.A.P.I.`
   with periods in display copy.
3. **The Sigil is derived, not decorative.** Seed only from the gamer's signed
   PoAC / device commitment (`device_id = keccak256(pubkey)` today; the
   biometric-snapshot commitment when it's exposed gamer-side); label it with the
   exact hash it derived from — **never claim a biometric seed over a device-key
   one**; let it re-derive live.
4. **The Twin + grind ribbon** stay the signature hero.
5. **Accessibility floor:** visible keyboard focus, reduced-motion respected,
   responsive to mobile.

---

## 9. One-line summary

> Make the QorTroller gamer view a **player-passport cockpit**: a hash-seeded
> **Humanity Sigil** fused with the live 3D Controller Twin as the hero, ringed by
> five HUD zones (Grind / Tournament / Your Data / Sovereignty) that read like a
> competitive game's progression screen — except every stat is cryptographically
> real. Keep the amber-action / chain-green-earned palette and Syne + JetBrains
> Mono type, let the void come alive (glow ≈ 0.5, vibe one tap away), and never
> let the cockpit claim a verdict it didn't compute.
