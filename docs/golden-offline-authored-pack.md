# Golden Offline Authored Pack (P0 #2)

**The card-free "run this → authored>0" proof.** One command reproduces a verifiable Remote-Play
authorship figure from a fixed, known-good archive — **without playing another match**, no rig, no
chain, no IOTX, no FROZEN-v1 surface touched.

```bash
python scripts/golden_offline_authored.py
```

Exit `0` = PASS (≥1 golden reproduced `DEFERRED_AUTHORED_SESSION` + verifier OK) ·
`1` = FAIL (a present golden regressed — deferred logic broke) ·
`2` = no golden archive on disk (restore one; **never a silent pass**).

## Why this is the reliability path today

Live `authored>0` is still fragile under capture lag (the D1.1/F2 lag work targets that). The
**deferred-attestation** path (arc A / RP-2d) is the proof that works *now*: the session's archive
is manifest-committed live evidence, and attesting from it post-hoc is the same evidence read later
(identical trust boundary at `developer_self` scope). On both goldens the **live** KAS verdict is
`INSUFFICIENT_KILLS` (RP thinned the live crops to below the K=3 floor) yet the deferred path
recovers **authored=3** — that recovery *is* the card-free result.

| Golden archive | Live KAS | Deferred @ pad=4000 | Verifier |
|---|---|---|---|
| `densecand_validate_1783711025` | INSUFFICIENT_KILLS | **DEFERRED_AUTHORED_SESSION authored=3** | OK (40 checks) |
| `match14_rp_option_b_1783475385` | INSUFFICIENT_KILLS | **DEFERRED_AUTHORED_SESSION authored=3** | OK (23 checks) |

## Honest scope — do not soften

- **Bounded-lag only.** `authored>0` is guaranteed for archives whose RP fire→kill gap fits inside
  the **4000 ms** window-latency pad (arc A, forward first-appearance predicate). The pad is applied
  identically at build and re-derived by the verifier, so it is auditable, not a fudge factor.
- **M18 is intentionally excluded.** M18's >4 s lag is an **honest 0** — `pad=4000` recovered only
  3/8 of its kills. A looser pad would paper over the limit, not fix it; the >4 s tail needs a
  **deferred-FAR study**, not a bigger number. `test_golden_offline_pack::test_no_m18_honest_scope_rail`
  pins this — M18 can never be quietly promoted into the golden set.
- **`developer_self` scope.** This is a card-free authorship *demonstration*, not a
  population-certified or field-FAR claim, and not identity attestation.

## What is committed vs local

`retina_kf_archive/` is **gitignored** (biometric-capture policy) — the crop archives live on the
operator's disk, not in the repo. **Committed:** `scripts/golden_offline_authored.py` + this doc +
`l9_presence/tests/test_golden_offline_pack.py`. **Local (operator's reliability asset):** the two
golden archives + their `audits/rp_ocr_scan_*.json` / `audits/kas_record_*.json` inputs. If a golden
is evicted, the pack reports `MISSING` and names it; re-derive via `scripts/rp_ocr_precision_scan.py`
+ `scripts/build_deferred_attestation.py` on a retained archive, or capture a fresh bounded-lag RP
session.

## Acceptance checklist (bars — grok owns; Claude implements)

_This section is the interface for grok's acceptance-checklist design; the mechanics above are built._

- [ ] Which verdict counts as PASS (`DEFERRED_AUTHORED_SESSION` only) and the `authored` floor (≥2).
- [ ] Verifier MUST pass (re-hash of every referenced crop) — no PASS on `verify=FAIL`.
- [ ] Pad ceiling documented + a present golden that *regresses* is a FAIL, not a skip.
- [ ] `session_id` / manifest / KAS join asserted (the three-artifact bind).
- [ ] Golden set stays bounded-lag (no M18-class); any new golden must state its measured lag.
