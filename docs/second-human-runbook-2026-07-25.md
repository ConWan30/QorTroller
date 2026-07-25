# Second-Human Runbook — one certified-human, fresh-rig grind

> **STATUS: PREP, NOT YET VERIFIED.** This runbook was authored 2026-07-25 as
> part of the engineering pass that produced moves #1/#3/#4 on branch
> `feat/cut-advisory-surface`. It has NOT been exercised yet. Every claim
> below marked **[PREP]** is design-validated against the existing CLI and
> runbooks but not run end-to-end with a real second human at the rig.
>
> When **the second player is ready**, this is the procedure to try. When any
> step fails — STOP and report what happened rather than workaround. The
> honest model is: an unknown second-human is the **first** integrity test
> the project has had, and the only way to up the N=1 ceiling named in the
> project's CLAUDE.md is to actually run this and let real failures (if any)
> surface.

**Scope:** a second human, on the project's existing Windows rig (the
DualShock Edge + PS5 + NCAA CFB 26 dual-connection setup already used for
the operator's `developer_self` grind), playing **one full grind match**.
NOT a buyer, NOT a tournament pilot, NOT a new rig — the goal is the
**single honest number**: "what happens when this protocol meets a
controller that isn't the operator's, in the same room as the operator,
for one real match".

**Honest limits stated up front (mirrors CLAUDE.md ceilings):**
- **Advisory pilot + demo on testnet** — N=1 still. The second match
  is still 1 human + 1 rig + advisory-only verdicts; it does NOT flip
  `poep_enabled`, `L6B`, or the dual-connection writer split.
- **No token, no buyer, nothing for sale.** Same posture as the first
  bundle — this is a smoke test for the second-human path, not a data
  transaction.
- **Operator still signs** any chain write (`qortroller anchor`) in
  their own PowerShell. The agent never spends.
- **The second human's controller becomes the subject**. Their data does
  NOT become the property of the project — see `BRIDGE NEVER GRANTS OR
  REVOKE CONSENT` invariant in CLAUDE.md. Their wallet signature (when
  given) is their own; nothing is granted on their behalf.

---

## P0 — Pre-flight sanity check (DO THIS BEFORE THE PLAYER TOUCHES THE PAD)

Every command below says "exit 0" or it's a hard stop. Each is on a
separate line on purpose — paste one at a time, watch the result.

```bash
# 1. The repo + submodule are initialized (else the invariant gate lies).
git submodule update --init bridge/firmware/joypad-os

# 2. The PV-CI gate is green. (184 today; if 183/182 or 2 failures, STOP — 
#    main is in a broken state and your session data has no proof posture.)
python scripts/vapi_invariant_gate.py                                  # exit 0 / "PASS — 184 invariants verified"

# 3. The golden offline-authored pack still re-proves authored>0 deterministically.
#    (Per pilot-ops-runbook; bar-G; bars A-H frozen. This is the regression gate.)
python scripts/golden_offline_authored.py                              # exit 0 = bar G PASS

# 4. The controller on the USB-C cable IS the certified Edge, not a random pad.
#    The ioID-registered device is the real Edge with pubkey hash 0x235a2c04.
#    `l6_hardware_check.py` verifies VID 0x054C / PID 0x0DF2 + ≥900 Hz polling +
#    gravity + gyro noise + haptic challenge roundtrip. This catches the
#    F-MATCH-2 wrong-controller-substitution failure mode BEFORE it costs a match.
python scripts/l6_hardware_check.py                                    # exit 0 = hardware OK
```

**If any of P0 fails — STOP and report the failure.** Do NOT proceed and do NOT
work around it. The whole shape of the protocol's integrity argument is that
every artifact downstream of a broken gate is suspect. A real second human
hitting a broken P0 is the most valuable signal you could get; masking it with
a workaround produces garbage.

The webcam also needs to pointed at the player's screen **and verified via the
EYE-CHECK PROTOCOL** (content-verify the first ring crop pre-queue) — the
F-MATCH-2 wrong-eye finding on 2026-07-13 was caught exactly this way, so DON'T
skip this just because "this time we know what we're doing".

---

## P1 — Setup ceremony (one time, second human present)

The `qortroller setup` CLI walks 3 stages: ROI / controller port / card
acknowledgement. The second human watches this happen; the operator types.
The point of having the second human watch is that they see — with their own
eyes — that nothing about their controller's baseline is being **fabricated**;
the calibration is mechanical.

```bash
# ALL stages. The CLI prompts for: (a) the webcam uvc_index (point at the screen
# the player will use, NOT at the operator's room); (b) killfeed ROI box around
# the score panel; (c) controller port confirmation; (d) observer-only pack.
# Observer-only because the second human is NOT granting prod consent yet —
# the pack writes only local, no on-chain consent.
python scripts/qortroller.py setup --pack observer-only
```

**EYE-CHECK PROTOCOL (mandatory given the 2026-07-13 wrong-eye finding):**
after setup writes the killfeed-ROI config, before play, content-verify the
first ring crop by viewing it directly. If the crop shows the operator's room
(not the player's screen), STOP, fix the `uvc_index`, re-run.

---

## P2 — The match (grind-shaped, NOT a tournament)

```bash
# Start the capture session. The engine records HID + camera + the sealed
# evidence stream for the configured game_duration. The session ID is
# persisted on first run; do NOT delete it mid-match.
python scripts/qortroller.py play
```

The second human plays one NCAA CFB 26 match normally. The grind session
adjudicator runs the same PCC / GIC / GAD gates it runs for the operator —
the second human gets EXACTLY the same scrutiny. If the session doesn't
register as NOMINAL / EXCLUSIVE_USB within ~30s of starting, see the
`docs/phase_235_pcc_dual_connection_clarification.md` recovery procedure.

```bash
# Stop the session and write the Proof Receipt. This is the artifact; 
# post-PR it is re-checkable by ANY stranger with one command.
python scripts/qortroller.py stop
```

---

## P3 — Stranger-side re-verify (the whole reason the second human matters)

```bash
# Re-render the receipt from the sealed artifacts (no live capture needed).
python scripts/qortroller.py receipt

# Stranger re-verify of the LOCAL receipt (full fidelity, postcard-tier 
# NOW — pack→STRANGER_OK-tier verification after).
python scripts/qortroller.py verify

# Print the match self-scorecard. Recall denominator is OPERATOR-REPORTED
# only (never fabricated-0). Every field tagged [MEASURED] / 
# [OPERATOR-REPORTED] / [DERIVED]. Honest 0 is a real result; if the
# recall is 0 again as it was the first time on 2026-07-13, that's the
# honest signal of where the rig is, NOT a regression.
python scripts/qortroller.py score
```

The honest output of the second-human session, in plaintext:
- N=2 grind corpus (was 1). The protocol's biometric separation gate
  is still unproven at this scale — the README's "CROSS-LESSON-001" gap
  (`no cross-session controller-identity claims until that study
  exists`) is NOT closed by adding one human.
- 184 invariants held through the run — provable by `git log` if the
  invariant-allowlist digest hasn't moved.
- 0 IOTX spent (anchor is operator-fired and skipped by default;
  drill only if the operator explicitly invokes `qortroller anchor` — pack
  ledger entry goes from PENDING → ANCHORED only after the real receipt).

---

## What is the operator's call to make this real

The second human's session is meaningful if and only if the receipt from P3
is left **exactly as the second human saw it** — not edited, not "improved",
not re-rendered after cleanup. If anything goes wrong, the value of the
session is the failure trace, not a re-do. Per the project's own discipline
(see `docs/a2a/ci-debt/backlog.md` fifth-pass RO): **failure-trace evidence
gets archived, not laundered.**

The two questions an honest second-human session can answer:
1. **Does the stranger-side re-verify path (`qortroller verify`) work for a
   receipt the second human saw written?** If yes — that's the first ever
   zero-trust re-check on non-operator-authored data in this repo's history.
2. **Does a different grip produce obviously-different biometric features**
   in the same session the operator would have produced? If yes — that's a
   qualitatively-new signal that the L4 / L4-Mahalanobis fingerprint is 
   actually capturing player-specific structure, not just noise.

Either way, **record what happened** in `docs/second_human_session_<date>.md`
afterwards — concrete outputs, the score the CLI emitted, and any F-* finding
that surfaced. If the run doesn't happen or aborts, write THAT record too;
this runbook being prepped and unused is also a real result.

---

## What this runbook explicitly does NOT do

- Does not flip `poep_enabled`, `L6B_ENABLED`, `L6_CHALLENGES_ENABLED`, or any
  operator-gated flag. Those are operator decisions and lie unchanged.
- Does not fire any chain write. `qortroller anchor` exists in the CLI but is
  leftover operator-fired. Default run of this runbook = 0 IOTX.
- Does not produce a "second-human product" — it produces pre-launch-quality
  evidence under the existing four-ceilings freeze.
- Does not modify any FROZEN-v1 primitive, any `b"VAPI-..."` domain tag, or any
  commit invariant. The gate stays at 184.
- Does not introduce any new test, contract, or invariant. The whole point
  is to exercise what's there with a new human subject.

---

## Pre-flight checklist (one line per item — print and tick off)

```
[ ] git submodule initialized (P0 step 1)         result: ___________
[ ] PV-CI gate 184/184 PASS                       result: ___________
[ ] golden_offline_authored.py bar G PASS         result: ___________
[ ] l6_hardware_check.py exit 0                   result: ___________
[ ] EYE-CHECK first ring crop shows player screen webcam uvc_index=___
[ ] qortroller setup --pack observer-only         result: ___________
[ ] qortroller play (session_id)                 result: ___________
[ ] qortroller stop                               result: ___________
[ ] qortroller receipt                            result: ___________
[ ] qortroller verify (status)                    result: ___________
[ ] qortroller score (recall, authored, MEASURED/DERIVED counts) ___________
[ ] session record file written: docs/second_human_session_2026-07-__.md
```

Signed by both parties (operator + second human) when complete. The signature
on paper is the witness the protocol can't prove. **If you can't tick every box
honestly, leave the unticked ones unticked.** That's the actual honest-holding
record — a perfect run with one unticked box is far more useful to the project's
integrity story than a polished "everything was fine".
