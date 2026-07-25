# Full ladder dogfood — diverse session `cfb_rwm_live_10` (2026-07-25)

**Verdict: ALL LAYERS PASS on diverse pure-session archive (preferred cite).**

Archive: `retina_kf_archive/cfb_rwm_live_10_1784953588`  
L0: **367 frames · unique 367/367 (100%)** · auto-RWM · locator PASS  
(see `l0-live-session-live10-2026-07-25.md`)

This supersedes live_07 ladder dogfood for **quality of evidence** (live_07 was FROZEN_RING).

## Results

| Layer | Surface | Result |
|-------|---------|--------|
| **L0** | stop auto-RWM + post-check | EXIT 0 · N=367 · unique=100% · locator PASS |
| **NOV-3** | `rwm_dispute_escrow.py` reveal 0–7 | BUILD/VERIFY OK · set_size=367 · L0 disk re-verify · media hashes |
| **NOV-2 bind** | `rwm_nov2_cli.py bind --kind none` + attach | BIND OK · ATTACHED |
| **NOV-2 checkpoints** | `rwm_nov2_cli.py checkpoints` | CHECKPOINTS OK (n=5 / 367) |
| **NOV-2 share** | `rwm_nov2_cli.py share` | SHARE OK |
| **NOV-1 sd1** | `rwm_nov1_cli.py --mode sd1_inline_media_v0` | BUILD/VERIFY OK archive-free |
| **NOV-1.1 merkle** | `rwm_nov1_cli.py --mode merkle_inline_media_v0` | BUILD/VERIFY OK archive-free · inclusion proofs · no full leaf list |

All exits **0**. Consent banners on escrow/share/stranger paths (no upload).

## Local artifacts (not committed — media-heavy stranger packs)

```text
audits/rwm_escrow_LIVE10-DOGFOOD.json
audits/rwm_escrow_LIVE10-DOGFOOD-bound.json
audits/rwm_bind_LIVE10.json
audits/rwm_cp_inv_LIVE10.json
audits/rwm_share_LIVE10.json
audits/rwm_stranger_LIVE10_sd1.json      (~6.5 MB)
audits/rwm_stranger_LIVE10_merkle.json   (~6.5 MB)
```

## Honest ceilings (unchanged)

- Membership + binding of L0 leaves; not re-encode proof
- CANDIDATE schemas; not FROZEN-v1
- No stop-path coupling for NOV-3/2/1; no chain spend
- Stranger packs embed marked frames — consent required before any share

## Cite guidance

| Claim | Cite |
|-------|------|
| End-to-end ladder on **diverse** live capture | **This note + live_10 L0 note** |
| Ladder still works on frozen content (pipeline only) | live_07 dogfood (historical) |
