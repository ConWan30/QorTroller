# L4 conjunction verdict — scope (Fusion Increment 2, 2026-07-03)

Scoping doc only (no build). Written at the close of Increment 1 (5 live matches, producer green across both
rendering families, B2-as-trigger refuted). Defines WHAT the fused verdict is, what is genuinely NEW vs
already built, the adversarial surface G4 must defeat, and pre-registered acceptance bars — so the build
starts from a fixed target, not a moving one.

## 1. The claim the verdict makes

**KILL-AUTHORSHIP SESSION CERTIFICATE**: "a live human, providing real controller input on THIS certified
device, authored N kill events in THIS session — each kill witnessed as own-handle-in-killer-slot DURING a
live trigger window." It is the anti-spectate / anti-splice presence verdict that correlation channels could
not deliver (cycle-56 refutation: FAR 0.46 — spectate-spam supplies the same correlation as causation).

## 2. The legs (all live-measured; weights per evidence class)

| leg | role | evidence base |
|---|---|---|
| **R2 window** (controller trigger onset) | STRUCTURAL GATE — no live input, no classification. Not a score; an existence precondition. | wired since inline v1; the standing R2^B2 rail pins that nothing classifies outside it |
| **Killfeed authorship** (composite AUTHORED @0.66, session-anchor regime tag) | PRIMARY SEMANTIC LEG — own handle read/matched in the killer slot inside a live window | 5 matches, 33+ live AUTHORED, 0 false positives; zero-false-read OCR gate (G1'); per-session anchor defeats rendering variance |
| **B2/th2 coupling** (windowed aggregate) | CORROBORATION ONLY — session-level consistency signal, never per-kill, never required | B2-as-trigger REFUTED (4/10 amp vs 25% ctrl; 6/10 d-red vs 34%); windowed coupling real at match granularity (coupled_true 5 death-only vs 26/55 kill-heavy) |
| session hygiene (frame health, ts_source, tripwire/crosscheck state) | VALIDITY CONDITIONS — a certificate is only issued over a clean capture | existing RGC diag surface |

Explicitly OUT: B2 as a required leg (refuted); L2/l2_ads (parked on the RP-L2-source finding, enabled=False);
any FROZEN-v1 / 228B PoAC / chain surface (this is an l9_presence advisory artifact).

## 3. What is genuinely NEW (the per-kill conjunction already EXISTS)

The producer already enforces the per-kill conjunction structurally — AUTHORED composites only resolve inside
R2 windows. Increment 2 builds the SESSION-level artifact on top:

1. **`KillAuthorshipSessionRecord`** (pure module, l9_presence): folds a session's composite AUTHORED set +
   window stats + anchor provenance (bootstrap_source, sha, regime tags, cut/promote/demote event trail) +
   th2-coupling corroboration + hygiene conditions into ONE record with an explicit verdict enum:
   `AUTHORED_SESSION` / `INSUFFICIENT_KILLS` / `HYGIENE_FAIL` / `UNVERIFIABLE`. Fail-closed; carries every
   number it was computed from (re-derivable).
2. **Commitment**: SHA-256 over the canonical record (domain tag `QORTROLLER-KAS-v0`, candidate/NOT FROZEN-v1)
   so a session certificate is tamper-evident and citable by D-CERT-5. No chain write; no new capability tag
   without the registration ceremony (PR-#46 lesson).
3. **G4 harness**: adversarial pairing runner (extends `scripts/adv_splice_replay.py` + the splice-FAR
   Monte-Carlo discipline of `docs/composite-splice-far-2026-07-01.md`) producing genuine-vs-adversarial
   record pairs and the separation table.

## 4. G4 — the adversarial surface (the gate; pre-registered)

| attack | mechanism | expected defense | measured-by |
|---|---|---|---|
| A1 spectate-spam | spam R2 while spectating a teammate's POV | authorship leg: feed shows TEAMMATE kills, own handle absent from killer slot | live spectate segment or archived spectate crops |
| A2 replay-splice | screen replay of recorded kill footage + live R2 spam | window gating + fresh-row (R2 rider): kill rows must appear DURING live windows; splice-FAR machinery already built | `adv_splice_replay.py` re-run through the WIRED producer |
| A3 handle spoof | another player's name canon-colliding | strict 10-glyph canon (G1': 0 false reads over 611 crops); G4 adds a synthetic near-collision probe (1-glyph-off names) | offline probe set |
| A4 menu/kill-cam leak | own kills re-shown in killcam/summary screens | fresh-row transient gate + R2 window (summary screens: no live fire) | archived end-screen crops |

**Pre-registered bars (set NOW, before any G4 run; no post-hoc tuning):**
- Genuine sessions (the 5 Increment-1 matches replayed through the record builder): verdict AUTHORED_SESSION
  wherever composite AUTHORED >= 2 with clean hygiene.
- Adversarial sessions: **ZERO AUTHORED_SESSION certificates.** Any single adversarial certificate = G4 FAIL
  -> diagnose + fix + full re-run (the l2_ads pre-registration discipline).
- Per-kill FAR under A2 splice: consistent with the splice-FAR doc's measured baseline or better.

## 5. Build order (Increment 2, each step gated)

1. `KillAuthorshipSessionRecord` module + tests (pure; consumes the composite jsonl + daemon event trail).
2. Retro-issuance over the 5 archived Increment-1 matches -> 5 genuine records (the positive corpus).
3. G4 harness + adversarial corpus (A1 spectate capture is the only new rig ask; A2-A4 run from archives).
4. G4 run -> separation table -> HOLD (operator adjudicates before the verdict is called anything publicly).
5. Only after G4 green: wire record issuance into the daemon session-close path (default-OFF flag, as ever).

Non-goals for Increment 2: chain anchoring, FROZEN-v1 status, PoEP fusion (separate track), B2 re-measurement
(the refutation stands unless a tight-ROI/high-rate trace is explicitly re-scoped).
