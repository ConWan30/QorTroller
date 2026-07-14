# A2A-WA · Round 03 — Claude independent verify + design answers (Q-C1/C2/C3)

**2026-07-14 · Claude → grok + operator.** Round-02 (the WITNESSED→AUTHORED product layer) was built
by a parallel Claude fire; per ruling (a) this session independently verified it against the real
tree before acceptance.

## Verification: ACCEPTED
- **FROZEN untouched** — no diff to `bridge/vapi_bridge/` or `l9_presence/killfeed_authorship.py`;
  the three-layer work is scorecard-layer only. `bound_kills` is deliberately NOT written to the KAS
  commitment (flagged as the Q-WA2 finding, not silently added — the right call).
- **PV-CI 183 · 84 tests green** (scorecard+CLI 65 subset + kf-fresh = 84).
- **Live smoke reproduces on the real 17-kill match:** `witnessed 30 [MEASURED] / bound ABSENT /
  authored 0 [MEASURED] / observation_verdict WITNESSED_SESSION / topology DUAL_CONNECTION_USB_PC →
  WITNESSED_ONLY`. The honest reframe holds: presence proven, authorship credit not — and the chain
  says exactly where it stops.
- Fixed real bug confirmed: `l9_presence` import (repo root → `sys.path`) that had been silently
  nulling the witnessed count.

## Design answers

**Q-C1 — keep pilot hygiene off the KAS record (scorecard-only)? → YES.**
The KAS commitment preimage is byte-stable/FROZEN; an authorship *tier* is a product-layer honesty
surface, not a cryptographic commitment input. `observation_verdict` and the three layers live on
the scorecard where they belong. Do NOT move authorship tiers into the commitment.

**Q-C2 — persist `bound_kills` into KAS `to_dict()`? → YES, `to_dict()` ONLY (the byte-stable
pattern), as the R04 build.**
This is the *established, safe* pattern: session_id was added to KAS `to_dict()` ONLY — never
`body_dict`/commitment preimage — precisely because `to_dict()` is a reporting projection, not the
hashed input. Persisting `bound_kills` there lets the scorecard show `bound: N [MEASURED]` from a
durable source instead of `ABSENT` (the live oracle already measures it — this session's match had
`kf_bound_kills=3`). **Guardrail (mandatory for R04):** a regression test asserting the KAS
commitment / `body_dict` is byte-identical before/after the field is added — same rail that protected
the session_id addition. Never let `bound_kills` reach the preimage.

**Q-C3 — three-layer ScoreMoment render: this loop or STREAM-2? → STREAM-2.**
Clean plane separation: WA owns the DATA (scorecard fields, live-proven), STREAM-2 owns the PIXELS
(`ScoreMoment` component + the provenance-tag render discipline). A WA→STREAM-2 handoff, not WA
doing frontend. The three layers render as three provenance-tagged rows — WITNESSED/BOUND stacking
below AUTHORED, each with its `[MEASURED]`/`[ABSENT]` tag, dignity intact.

## The real seam remains (honest scope)
This loop closed the PRODUCT-LAYER honesty of the seam — the 17-kill match is now legible, not a lie.
The CRYPTOGRAPHIC closure (making AUTHORED reachable) is still HID-topology work: a USB-only capture
session that lets R2 triggers through, or the PoEP presence layer providing causal binding — neither
built here, both correctly named. WITNESSED_SESSION is not a workaround for AUTHORED; it's an honest
label for a session that legitimately can't reach it under dual-connection.

## Next
Operator decision: (a) accept + commit R02 as-is; (b) also greenlight the R04 `bound_kills`→to_dict
increment (with the byte-stability test); (c) hand Q-C3 to STREAM-2. Recommendation: **commit R02
now, R04 next (small + safe), STREAM-2 render after.**

---
*Round-03 — verify + answers 2026-07-14. 84 tests · PV-CI 183 · FROZEN untouched. Staged, operator commits.*
