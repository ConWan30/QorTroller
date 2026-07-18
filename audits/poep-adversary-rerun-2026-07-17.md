# PoEP adversary re-run (software gate)

**poep_enabled=False** · **flip_authorized=False**
Band: `[80.0, 450.0]`

## 1. TellWatcher (F-POEP-LIVE-1)

| metric | value | bar |
|--------|------:|-----|
| FAR stdout_tell | 1.000 | ≥ 0.9 |
| FAR pollburst naive | 0.795 | ≥ 0.3 |
| FAR continuous_poll | 0.033 | ≤ 0.15 |
| **passes_tell_removal_proof** | **True** | |

## 2. Catch trials (always-fire vs honest sim)

- schedule N=200 · NO_GO=40
- always-fire catch rate: **1.000** (bar ≥ 0.9) → ok=True
- honest human FA rate (sim): **0.02** (budget ≤ 0.05) → ok=True

## 3. Band-only macro (honesty check)

- A-RAND FAR: **1.000** — FAR≈1 expected — live-verify alone without catch/shape is not presence.

## Software gate

**PASS=True** — tell-removal proof + always-fire catch bar (structural). Human FA sim is advisory; live FA measured on-rig with --catch. NOT FLIP-A flip.

### Still required for poep_enabled=True

- live catch-trial sessions with measured human FA <=5%
- operator review of claim language (FLIP-A only)
- two-key operator fire of poep_enabled
- A-REACTIVE still out of claim
