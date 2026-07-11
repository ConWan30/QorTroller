# Match 14 — First Full Authorship Stack Under Remote Play (RP-2, Option B)

**2026-07-07. D-RP-1 Option B: same-machine RP, lean bridge, fresh DB, VPN off,
daemon-solo topology. Operator ground truth: 11 kills. Span ~7.4 min.**

## Headline results

| Claim | Result |
|-------|--------|
| PoSP under Remote Play | **SYNCHRONIZED** — first ever (kas_verified=True, fusion_rows=368, archive_verified=True) |
| Arc A offline verification | **VERIFIED 7/7** (`scripts/verify_posp_record.py`, exit 0) — first RP-born PoSP record to pass |
| Zero-false-read bar (RP-dense) | **HELD** — 0 suspect / 413 crops (RP-era total now 0/564) |
| Capture health under RP | **38.6 fps ema** (M12 died at 3.76) — the M12 remediation chain (lean + fresh DB + solo topology + VPN off) is VALIDATED |
| KAS live attestation | `INSUFFICIENT_KILLS` authored=**0/11** at the K=3 floor (honest tier-2) |
| Live read-level | 2/11 inline OWN_KILL reads; 45 inline classifications across 7 R2 windows |
| Presence surface | 24 PRESENT_COHERENT / 59 ge2ch sessions during the match |

## Archive ground truth (Instrument A, v6-only, 405s)

413 crops → **29 own-kill reads, 15 clusters, 0 false reads.** Every matched text
carries the own handle (suffix fusions = the known victim-name-bleed genuine pattern).
Against the operator's 11 kills, the dense archive saw effectively every kill —
**readability through the RP codec is CLOSED as a concern** (RP-3's open half).

Cluster sizes: `[5, 4, 3, 3, 2, 2, 2, 1×8]`
- Promotable at K=3: **4** → archive-side ceiling 4/11 = **36%**
- Promotable at K=2: **7** → K=2 ceiling 7/11 = **64%**
- Singletons: 8

## The finding — F-RP2-1: RP's tax is crops-per-kill, not readability

| | M13 (HDMI) | M14 (RP, Option B) |
|---|---|---|
| crops archived | 524 | 413 |
| own-kill reads | 77 | 29 |
| clusters | 27 | 15 |
| **reads per cluster** | **2.85** | **1.93** |
| K=3-promotable share | 41% (11/27) | 27% (4/15) |
| KAS authored (live) | 8 | 0 |

Same engine, same thresholds, same code. Remote Play (38fps capture + governor
downscale=5) thins the crop count each kill-row dwell produces, so fewer clusters
reach K=3 and live promotion starves — despite healthy classification density
(45 vs M11's 23) and working R2 windows (7). Precision stayed perfect throughout.
**The binding constraint is dense-stream density per kill, which is exactly what
the Option A sidecar device buys** — the B/A delta is now a measured argument,
not a hypothesis.

## Decision candidate — D-RP-2 (NOT taken): lower live K under RP?

K=2 live would plausibly have attested some of the 7 two-plus-crop kills. NOT adopted:
the K=3 floor is the zero-false-attestation posture, and any K change on a certificate
path requires its own adversarial re-pairing first (splice-FAR at K=2 is unmeasured —
the C1/B8 discipline). Option A (hardware density) is the preferred fix; D-RP-2 stays
parked unless Match 15 data argues otherwise.

## What Match 14 proved, in one paragraph

The three-surface synchronized presence proof works in the environment that makes it
matter: a QORTROLLER-POSP-v0 record was minted from a live Remote Play match, joined
KAS + 368 NQPV fusion rows + a 413-crop archive on one session_id, and verified 7/7
offline. The perception pipeline read kills through the RP codec with zero false reads.
What Remote Play costs — measured, not guessed — is per-kill crop density, which zeroes
the conservative K=3 live attestation on this hardware and prices the sidecar witness
device as the path to the full claim. Scope rails unchanged: developer_self, N=1,
verifier_independence=False, advisory throughout.

## Files

- KAS: `audits/kas_record_match14_rp_option_b_2026-07-07.json` (commit b881ad977d68da9c)
- PoSP: `audits/posp_record_match14_rp_option_b_2026-07-07.json`
- Scan: `audits/rp_ocr_precision_scan_match14.json`
- Archive: `retina_kf_archive/match14_rp_option_b_1783475385/` (413 crops)
- Corpus: `match14_rp_option_b_1783475385.jsonl` (92 diag samples)
