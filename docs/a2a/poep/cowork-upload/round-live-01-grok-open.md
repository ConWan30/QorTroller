# Round LIVE-01 — grok open: dual-connect challenge-live

**From:** grok · **To:** Claude / Cowork  
**Loop:** `docs/a2a/poep/poep-gameplay-live-loop.md`  
**Design (normative):** `docs/a2a/poep/poep-gameplay-live-design.md`  
**Charter (a):** you build; grok verifies; operator commits + dogfoods.

---

## 0. Context

Dry gameplay path is **PASS** (round-05). It intentionally **cannot** mint  
`presence_session_candidate_ok`. This arc closes that gap with **live dual-connect**,  
not desk volume.

**Do not re-open** round-04 honesty (two-bool, MIN_GO=2, bridge trust, amplitude ≤80).

---

## 1. BUILD-NOW (L1 + L2)

### L1 — Live session shell + seal + bridge activity (tests mockable)

1. `start-live` path: `mode=live`, `activity_source=bridge`, **live_seal** per design §5.4.  
2. Activity poll adapter: pure function + injected fetcher (HTTP capture-health and/or HID sample dict) → `classify_activity`; never mark `bridge` unless from adapter.  
3. Refuse challenges if activity not ACTIVE or PCC bad (mockable).  
4. Tests: dry still cannot candidate; live without seal cannot; MENU cannot issue; seal round-trip.

### L2 — Challenge driver

1. Implement `challenge-live` (or session loop method): real fire path at amplitude ≤80.  
2. Prefer reuse of existing fire primitive (`_fire_probe_silent` / L6TriggerDriver) with **documented** HID ownership vs bridge.  
3. Build real `verify_live_response` + optional catch NO_GO.  
4. `SessionChallengeEvent(live_hardware=True)` only on real GO fire.  
5. If full HID in CI is impossible: mock fire boundary + one integration test; real fire behind operator flag.  
6. Tests: amplitude clamp; NO_GO no force; GO pass/fail uses real verify; summary candidate_ok only when all live gates hold (can use test double for fire).

### L3 — Operator only (not agent-complete)

Dogfood dual-connect; not required for round-02 software PASS.

---

## 2. Deliverables

| Path | |
|------|--|
| Design | already: `poep-gameplay-live-design.md` |
| Code | extend `poep_gameplay_session.py` + CLI; optional `poep_gameplay_live_driver.py` |
| Tests | `test_poep_gameplay_live.py` (or extend existing) |
| Report | `docs/a2a/poep/round-live-02-claude-build.md` |
| Runbook delta | live section in `gameplay-embedded-runbook.md` |

---

## 3. NON-goals

Desk N campaigns · flag flips · F-PATHA-1 · chain · waveform freeze · autonomous commit  

---

## 4. Grok verify bars (round-03)

Design §8 (honesty + PCC refuse + claim + flags).

---

## 5. Paste for Cowork

```text
Arc: poep-gameplay-live
READ: docs/a2a/poep/poep-gameplay-live-design.md
      docs/a2a/poep/poep-gameplay-live-loop.md
      docs/a2a/poep/round-live-01-grok-open.md
      l9_presence/poep_gameplay_session.py (round-04 honesty)
BUILD: L1+L2 challenge-live dual-connect path. Dry must stay non-candidate.
poep_enabled False. No desk campaigns. No commit. Write round-live-02-claude-build.md
```

---

## 6. Operator note (is this “just play”?)

**No.** Order: design (done) → **build L1/L2** → **then** you play for L3 dogfood.

---

*grok round-live-01 · 2026-07-17 · first candidate-grade session liveness path · not a flip*
