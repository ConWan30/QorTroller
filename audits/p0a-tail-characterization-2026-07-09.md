# P0-A — sub-0.20 coupling tail characterization (builder diagnostic)

**Purpose:** answer the design question raised by the INCONCLUSIVE first OP — are the 22 sub-0.20
human sessions *low-aim* (legitimately reliability-filterable) or *genuine coupling failures* (which
must count against the human class)? Feeds grok's §5.1 reliability-gate decision. Offline, advisory.

## Result: the tail is LOW-AIM, not coupling failure

| Metric | sub-0.20 (n=22) | ≥0.20 (n=22) |
|--------|-----------------|--------------|
| median `coupling_score` | 0.09 | 0.42 |
| **median stick-std (aim-activity proxy)** | **12.6** | **46.0** |
| median duration | 60 s | 60 s |
| median `negative_control` | 0.03 | 0.03 |

- **17 / 22** sub-0.20 sessions have stick-std below the ≥0.20 group's p25 (34.2) — i.e. low aim.
- **Pearson r(coupling_score, stick-std) = 0.50** over all 44 scored — more aim → more coupling.
- **Same duration** both groups → the effect is aim activity *within* the session, not session length.
- **Player confound:** sub-0.20 is **P1-dominated (15/22)**; ≥0.20 is P2/P3-dominated. P1's captured
  sessions were systematically lower-aim.

## Interpretation

The 15 skipped sessions already fell below the oracle's `MIN_STICK_STD` abstain gate. The 22 sub-0.20
*scored* sessions cleared that gate but still carry **minimal aim** (median stick-std 12.6 vs 46.0) —
there is little aim motion for the camera to couple to, so a low `coupling_score` reflects **absence
of the signal, not failed human presence**. This **supports** a pre-registered **aim-activity
reliability gate** on the positive class (README Stream A used exactly this), scoping the claim to
"human-vs-modeled-automation **on aim-active sessions**."

**Honest caveats (grok's §5.1 call must pin):**
1. It is a **continuum** (r=0.50, not 1.0): ~5/22 sub-0.20 sessions have decent aim but still low
   coupling — a hard aim-threshold will admit/exclude borderline cases; the threshold must be
   pre-registered, not tuned to clear TAU_HUMAN.
2. **Player confound:** the median is dragged by P1's low-aim pile. A per-player aim-balance or a
   reported player histogram is worth pinning so the OP isn't a single-player-aim-style artifact.
3. Applying the gate is a **claim-scope change** → new study schema `p0a-presence-op-v2` (per §6 /
   §10.9); the raw-pool **INCONCLUSIVE** stays the honest v1 record.

## Recommendation (builder → designer)

A pre-registered aim-activity gate on positives is **justified by this data** and consistent with the
banked methodology. grok owns the §5.1 amendment (threshold value + claim rewording); operator signs
§9; Claude re-runs `p0a-presence-op-v2`. Do **not** retune TAU_HUMAN/GAP_MIN to clear the raw pool —
fix the *inclusion criterion*, keep the *decision constants* frozen.

*Source: `audits/p0a-presence-op-2026-07-09.json` (raw OP) + this characterization. Metric =
`analyze_session_data` coupling_score; aim proxy = max(std(in_sx), std(in_sy)).*
