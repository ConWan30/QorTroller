# Full ladder dogfood — pure session `cfb_rwm_live_07` (2026-07-25)

**Verdict: ALL LAYERS PASS on pure-session archive.**

Archive: `retina_kf_archive/cfb_rwm_live_07_1784949135` (135 frames, FROZEN_RING content — see L0 note).

## Results

| Layer | Command surface | Result |
|-------|-----------------|--------|
| **L0** | stop auto-RWM + `rwm_post_session_check.py --label cfb_rwm_live_07` | EXIT 0 load-bearing |
| **NOV-3** | `rwm_dispute_escrow.py build/verify` reveal 0–7 | BUILD OK · VERIFY OK (incl. L0 disk re-verify + media hashes) |
| **NOV-2 bind** | `rwm_nov2_cli.py bind --kind none` + attach escrow | BIND OK · ATTACHED |
| **NOV-2 checkpoints** | `rwm_nov2_cli.py checkpoints` | CHECKPOINTS OK (n=5 / 135) |
| **NOV-2 share** | `rwm_nov2_cli.py share` | SHARE OK (redacted postcard) |
| **NOV-1 sd1** | `rwm_nov1_cli.py build --mode sd1_inline_media_v0` + verify | BUILD/VERIFY OK archive-free |
| **NOV-1.1 merkle** | `rwm_nov1_cli.py build --mode merkle_inline_media_v0` + verify | BUILD/VERIFY OK archive-free · no full leaf list · inclusion proofs |

## Local artifacts (gitignored / not for public share without consent)

```text
audits/rwm_escrow_LIVE07-DOGFOOD.json
audits/rwm_escrow_LIVE07-DOGFOOD-bound.json
audits/rwm_bind_LIVE07.json
audits/rwm_cp_inv_LIVE07.json
audits/rwm_share_LIVE07.json
audits/rwm_stranger_LIVE07_sd1.json
audits/rwm_stranger_LIVE07_merkle.json
```

Consent banners fired on escrow/share/stranger paths (no upload).

## Honest ceilings reaffirmed

- Membership + binding of L0 leaves; not re-encode proof
- FROZEN_RING: all 135 panels same content hash — dogfood proves **pipeline**, not live-play diversity
- Stranger merkle pack is archive-free verify; still CANDIDATE, not FROZEN-v1
- No stop-path coupling for NOV-3/2/1; no chain spend

## Ladder status after this dogfood

```text
L0 LIVE ops pure-session  ✓
NOV-3 escrow              ✓ built + dogfood live_07
NOV-2 bind/cp/share       ✓ built + dogfood live_07
NOV-1 sd1 + merkle        ✓ built + dogfood live_07
```

**Next candidates (need operator pick):** longer diverse capture (N≥146, non-frozen) · NOV-2 with real PoAC/GIC tip bind · stranger-pack size/redaction polish · FROZEN ceremony (not default).
