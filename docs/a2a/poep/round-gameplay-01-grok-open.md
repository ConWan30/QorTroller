# Round 01 — grok open: gameplay-embedded PoEP challenges

**From:** grok  
**To:** Claude  
**Loop:** `docs/a2a/poep/poep-gameplay-embedded-loop.md`  
**Charter ruling (a):** Claude builds; grok verifies before operator commit.

---

## 0. Context (do not re-litigate)

| Banked | Not the goal of this loop |
|--------|---------------------------|
| Desk live nonce + catch (`--catch`) | Infinite desk sessions |
| Multi-op surprise seed + day-2 | Desk FA N→40 as product |
| Software adversary gate PASS | `poep_enabled` flip |
| Operator: desk probes feel empty as presence | Path A F-PATHA-1 (parallel) |

**Product pivot:** **B — gameplay-embedded challenges.**

---

## 1. Architecture (normative)

```text
PlaySession
  session_id, device_id, player_label, t_start, topology_note
  activity_samples[]   # gameplay_active / menu / unknown
  challenges[]         # GO / optional NO_GO, verify + catch scores
  summary              # presence_session candidate metrics

Scheduler (sparse)
  only if gameplay_active
  interval ~ CSPRNG in [min_s, max_s]  (e.g. 90–300s — config, not hardcode magic)
  amplitude: LOW default (e.g. force 40–80), NOT desk 255
  reuses: poep_live_verify, optional poep_catch_trials kinds

Activity gate
  pure function: inputs → ACTIVE_GAMEPLAY | MENU | UNKNOWN
  v1: trigger activity / stick motion / existing trigger_active patterns if available
  fail-closed: UNKNOWN → no challenge

Bridge posture
  Desk path: bridge often DOWN (HID exclusive)
  Gameplay path: bridge UP, dual-connect operator topology
  Document honestly if v1 is "bridge-orchestrated USB challenge while BT plays"
```

### Session presence score (v0 candidate — not a flip)

```text
presence_session_candidate_ok iff
  n_go_issued >= 1
  AND n_go_verify_pass >= 1
  AND (if any NO_GO: human_fa_rate <= 0.05 OR n_nogo == 0)
  AND gameplay_active_fraction >= 0.5   # tunable constant, named
  AND poep_enabled remains False in all outputs
```

---

## 2. BUILD-NOW set (Claude — ordered)

### GP-1 — Pure module `l9_presence/poep_gameplay_session.py`

**Ship:**

- `PlaySession` dataclass (or frozen builders)  
- `ActivityState` enum: `ACTIVE_GAMEPLAY | MENU | UNKNOWN`  
- `classify_activity(sample: dict) -> ActivityState` — pure, tested  
  - v1 heuristics: e.g. any L2/R2 press fraction > 0, or stick variance, or explicit `gameplay_context` field if present  
  - document fail-closed UNKNOWN  
- `SessionChallengeEvent` record shape (kind GO/NO_GO, verify dict, catch optional, ts)  
- `summarize_session(session) -> dict` implementing score above  
- **No** hardware imports in this module  

**Acceptance:** unit tests for activity classify + summary gates; `poep_enabled=False` in summary.

### GP-2 — Sparse scheduler pure logic

**Ship (same module or `poep_gameplay_scheduler.py`):**

- `next_challenge_delay_s(rng, min_s, max_s) -> float`  
- `should_issue_challenge(activity, time_since_last, delay_s) -> bool`  
- Optional: `plan_catch_kind(go_per_no_go, rng) -> GO|NO_GO` reusing catch ratio philosophy  

**Acceptance:** deterministic under seed; no challenge when MENU/UNKNOWN.

### GP-3 — CLI skeleton `scripts/poep_gameplay_session.py`

**Operator-facing dry path (can run without full dual-connect first):**

```text
python scripts/poep_gameplay_session.py start --player P1 --device-id ...
python scripts/poep_gameplay_session.py tick  --activity-json '{...}'   # inject activity sample
python scripts/poep_gameplay_session.py challenge-dry  # schedule + record a *simulated* or hardware optional challenge
python scripts/poep_gameplay_session.py stop  --out audits/poep_gameplay_session_*.json
```

**v1 honesty:**

- `--dry-challenge` mode: no HID, inject synthetic outcome for plumbing tests  
- `--live` mode: optional reuse of fire primitive **only if** safe (document bridge UP requirement); if live HID is too entangled for one PR, ship dry + clear `LIVE_TODO` and still complete GP-1..GP-3 + GP-4  

**Prefer:** dry fully working + live hook stub with one integration test mocked, over a flaky live dual-connect in first PR.

### GP-4 — Tests

| ID | Asserts |
|----|---------|
| T-GP-1 | MENU/UNKNOWN → no challenge |
| T-GP-2 | ACTIVE + delay elapsed → challenge allowed |
| T-GP-3 | summary fail-closed when zero GO pass |
| T-GP-4 | summary ok shape when min GO pass + activity fraction |
| T-GP-5 | catch FA rate in summary when NO_GOs present |
| T-GP-6 | all public outputs `poep_enabled is False` |
| T-GP-7 | session artifact includes session_id + device_id + claim string FLIP-A host-trusted only |

### GP-5 — Docs

- `docs/a2a/poep/round-gameplay-02-claude-build.md` (your report)  
- Short operator note in loop file or `docs/a2a/poep/gameplay-embedded-runbook.md` (≤80 lines): dual-connect topology, amplitude, bridge UP, dry vs live  

---

## 3. NON-goals (reject scope creep)

- Expanding desk `poep_live_capture` N as the deliverable  
- Enabling `poep_enabled` / L6B / L6_CHALLENGES  
- Force=255 mid-game defaults  
- FROZEN/PoAC/chain  
- Full waveform gate  
- Tournament BLOCK from presence_session_ok  

---

## 4. Novelty (engineering, not marketing)

| Prior art in-repo | This loop adds |
|-------------------|----------------|
| Desk silent nonce fire | **Activity-gated sparse challenges in a session object** |
| Catch GO/NO_GO desk | Same rules **inside session summary** |
| PoSP session_id | **Presence ticks join session_id** (reference, don’t break PoSP) |
| L6 ambient roadmap | **Concrete session runner + pure gates**, still deferred-activation |

---

## 5. Adversary notes for round-03 (grok)

After build, verify:

1. MENU farming cannot mint `presence_session_candidate_ok`  
2. Dry mode cannot be mistaken for live (flag `live_hardware: false`)  
3. Claim string cannot say identity / anti-host-compromise  
4. No default high force for gameplay path  
5. Desk capture scripts unchanged in behavior except no requirement to use them  

---

## 6. Paste-ready Claude prompt

```text
You are Claude in QorTroller A2A (ruling a: you build; grok verifies).

READ:
- docs/a2a/poep/poep-gameplay-embedded-loop.md
- docs/a2a/poep/round-gameplay-01-grok-open.md
- l9_presence/poep_live_verify.py
- l9_presence/poep_catch_trials.py

BUILD-NOW GP-1..GP-5: gameplay session pure module + sparse scheduler + CLI skeleton
(dry-first OK) + tests T-GP-1..7 + build report round-gameplay-02.

HARD RAILS:
- poep_enabled / L6B / L6_CHALLENGES stay False
- not more desk-probe campaigns
- low amplitude for any live gameplay path
- no FROZEN/PoAC/chain
- staged-only; no commit unless operator says commit

DELIVER: code + tests + docs/a2a/poep/round-gameplay-02-claude-build.md
```

---

## 7. One-liner

**Stop selling desk buzz count as presence; build session-scoped, activity-gated, sparse in-play challenges as the novel engineering loop.**

---
*grok round-gameplay-01 · 2026-07-17 · FLIP-A host-trusted session liveness · flag off*
