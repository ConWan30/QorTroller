# L9 x Trio-Retina Presence-Consistency Fusion (RESEARCH — instrument built, separation UNVALIDATED)

**Status:** RESEARCH / ADVISORY. The fusion *instrument* is built and logic-tested
(`l9_presence/presence_retina_consistency.py`, 21 tests). The claim that it
*separates cheat from skill* is **[UNVALIDATED]** and stays that way until the
adversarial experiment in §5 runs. Default-OFF; gates nothing; does not touch the
228-byte PoAC wire or any FROZEN-v1 primitive.

## 1. The thesis

L9/PoEP and Trio-Retina measure two **orthogonal** axes of "humanness":

| Oracle | Axis | Cadence | Answers |
|--------|------|---------|---------|
| **PoEP / presence** | embodiment (live reflexive human, device-auth, nonce) | sparse, event-driven | *Is a human in the loop?* |
| **Trio-Retina** | trajectory authenticity (continuous output physically plausible) | dense, per cognition cycle | *Is the output human-generated end-to-end?* |

The **security signal is their DISAGREEMENT**, not either verdict. This is the
deliberate departure from single-classifier fusion (cf. the **GCAP honest
negative**, where tightening one classifier collapsed genuine-human TAR
0.806 → 0.581). Inconsistency between two *independent* oracles that should agree
for a genuine human can have a better operating point than human-vs-bot
classification on one noisy axis — an adversary must satisfy two independent
models *and* forge their agreement under a cryptographic binding.

## 2. The consistency lattice (`assemble_consistency`)

| presence × trajectory | verdict | security | meaning |
|---|---|---|---|
| PRESENT × PLAUSIBLE | `CONSISTENT_HUMAN` | — | both agree human (unless L4 2v1-splits → INCONSISTENT) |
| **PRESENT × IMPLAUSIBLE** | `INCONSISTENT_PRESENCE_WITHOUT_AUTHENTIC_TRAJECTORY` | **HIGH** | **the machine-assist / relay catch** — live human, non-human continuous output |
| REJECT × PLAUSIBLE | `INCONSISTENT_AUTHENTIC_TRAJECTORY_WITHOUT_PRESENCE` | MEDIUM | replay / synthetic-humanised, or presence not exercised |
| REJECT × IMPLAUSIBLE | `CONSISTENT_INACTIVE` | — | agree: no genuine human activity |
| any × UNKNOWN (one oracle) | `INDETERMINATE` | — | single-oracle window, no call |
| UNKNOWN × UNKNOWN / unbound | `UNVERIFIABLE` | — | fail-open, never accuses |

## 3. Binding is the security (`check_binding`)

Oracles fuse ONLY when bound to the **same `device_id`**, an **overlapping time
window**, and a **present `record_hash`** anchor. Any gap → `UNVERIFIABLE`
(fail-closed-to-open). This is what defeats relay-via-desynchronisation: you
cannot pass presence on device A while a bot drives device B, nor splice an old
trajectory beside a fresh presence proof. Test
`test_unbound_never_accuses_even_when_states_would_be_inconsistent` pins it: a
PRESENT × IMPLAUSIBLE pair that *would* be the HIGH catch becomes `UNVERIFIABLE`
with `security_flag=False` when the two oracles are not bound.

## 4. Honesty rails (load-bearing)

1. **Advisory only** — no P0 gate, not in `humanity_probability`, no PoAC edit.
2. **Fail-open** — missing / unbound / partial → `UNVERIFIABLE`, never a cheat verdict.
3. **Uncalibrated** — emits a categorical verdict + contributing states, **never a
   probability/confidence/score**. `calibration_status` is permanently
   `UNCALIBRATED_SYNTHETIC` until §5 lands.
4. **What it does NOT close** — account-sharing / smurfing / carrying. A present,
   skilled, legitimate-trajectory human who is not the account owner passes BOTH
   oracles. That is *identity*; this fusion makes no identity claim.

## 5. The decisive experiment (this is what makes it real or kills it)

The instrument is worthless as a security claim until the disagreement signal is
shown to separate on **adversarial** data. Quiescence-only capture (both oracles
quiet on neutral sticks) proves nothing. Required capture matrix, extending the
Phase G desk protocol:

| Class | Capture | Expected fusion verdict (hypothesis) |
|-------|---------|--------------------------------------|
| `HUMAN_CLEAN` | genuine play, certified Edge | `CONSISTENT_HUMAN` |
| `BOT_FULL` | scripted input, no human | `CONSISTENT_INACTIVE` / `INCONSISTENT_*-WITHOUT_PRESENCE` |
| `HUMAN_AIM_ASSIST` | real human + downstream aim-assist | **`INCONSISTENT_PRESENCE_WITHOUT_AUTHENTIC_TRAJECTORY`** |
| `HUMAN_RELAY` | human passes challenges, bot plays between | `INCONSISTENT_*` iff binding tight |
| `PRO_SKILL` | elite human, inhuman-looking-but-real snaps | **must stay `CONSISTENT_HUMAN`** (the false-positive risk) |

**Decision rule:** the fusion is real iff the **disagreement ROC beats both the
PoEP-alone and retina-alone ROCs** at a usable operating point — specifically iff
`HUMAN_AIM_ASSIST` separates from `PRO_SKILL` better under the disagreement signal
than under either oracle standalone. If `PRO_SKILL` collapses into the security
states (the GCAP failure mode recurring on the retina axis), the fusion is
elegant but **not** a deployable edge, and its honest home stays forensic /
adjudication (a third-party-verifiable consistency record), not a real-time gate.

**N target:** ≥10 players × the 5 classes, per certified controller class
(Edge first; mid-tier DualSense second). Until then: instrument only.

## 6. Integration path (deferred — not in this slice)

1. Add presence as a **third oracle in the FSCA cross-oracle lattice** alongside
   the existing `RETINA_TRAJECTORY_WITHOUT_L4_ANOMALY` / `L4_ANOMALY_WITHOUT_RETINA_SIGNAL`
   rules (`fleet_signal_coherence_agent.py`) — new advisory CONTRADICTION rules
   keyed on the presence × retina × L4 binding.
2. A DB runner that pulls bound `(presence proof, retina_event_log row, records.pitl_l4_distance)`
   triples by `record_hash` / `device_id` / time-window and feeds the pure core.
3. Surface the advisory verdict on `GET /player/session-status` under a new
   `presence_consistency` block (read-only), default-OFF behind a config flag.

None of this is built here. This slice is the **pure fusion engine + its logic
proof + this honest scope**. The next real step is §5, not §6 — wiring an
unvalidated signal into surfaces would put the cart before the evidence.
