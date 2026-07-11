# Pilot Ops Runbook — running one pilot match end-to-end

**Companion to:** [`pilot-organizer-onepager-2026-07-10.md`](pilot-organizer-onepager-2026-07-10.md) (the four
ceilings ride along with every artifact this runbook produces).
**Scope:** the operator-side procedure for ONE pilot match on the current rig (Remote Play window capture,
`developer_self` scope). Every command below is the exact invocation validated live on 2026-07-10
(`lean_d11`, `lean_f2_validate`). Advisory only; testnet only; 0 IOTX in this flow.
**Reliability posture (D-F2X-1):** the deliverable authorship figure comes from the **offline deferred path
(§5)** — live authored>0 is a bonus when fps allows, never the promise.

---

## 0. Once per pilot day — the gate (golden pack bar G)

```bash
python scripts/golden_offline_authored.py        # MUST print the bar-F PASS line and exit 0
python scripts/vapi_invariant_gate.py            # MUST print PASS — 182 invariants
```

Exit 1 (present golden regressed) → **stop; no pilot claims today**; fix deferred logic first.
Exit 2 (golden archive missing) → restore the named archive; never treat as pass.

## 1. Per-match preflight

```bash
python scripts/match_preflight.py                # RP-5 contention-hygiene gate
```

WARNs are advisory, but two fire on this rig today and are worth heeding pre-pilot: `bridge_db_size`
(5.3 GB DB → per-record write-lag risk; consider a fresh `DB_PATH` override for the pilot session) and
`env_sanity` (`RETINA_KILLFEED_CAPTURE_MAX` unset → default ring may be small for a long match).

Plus the manual three: controller **USB-C to laptop + BT to PS5** (dual-connection); Remote Play window
open and visible on monitor 0; no other capture/encode-heavy apps running (the lag class is systemic
CPU/GIL contention — every extra load steals frames).

## 2. Start capture (the validated invocation)

```bash
RETINA_MATCH_STATE_ENABLED=1 RETINA_CANDIDATE_DENSE_SCORE=1 \
python scripts/retina_capture_daemon.py start --label pilot_<event>_<n> --monitor 0 \
  --killfeed --capture --killfeed-inline --session-anchor --dense-classify --classify-burst --hid-events
```

Wait for `CAPTURE LIVE`. The daemon self-sets `PRESENCE_LEAN_MODE=true`, `NQPV_COCAPTURE_ENABLED=true`,
`CHAIN_SUBMISSION_PAUSED=true` (kill-switch ON) and mints the `session_id` join key.

| Flag | Why it's on |
|---|---|
| `RETINA_MATCH_STATE_ENABLED=1` | LUMEN-2b advisory match view — MATCH_STARTED live + MATCH_ENDED sealed at stop (F-ARCB-1b) |
| `RETINA_CANDIDATE_DENSE_SCORE=1` | dense-candidate promotion — the live authorship mechanism (works when fps allows) |
| `LOOP_STARVATION_ATTRIBUTION_ENABLED=1` | OPTIONAL diagnostic — add only if you want lag attribution; not needed for the pilot deliverable |

**Sanity before the match starts** (10-20 s after CAPTURE LIVE):

```bash
curl -s http://127.0.0.1:8080/health              # {"status":"ok"}
```

and in the daemon log: `dense-candidate worker ON`, `'match_state_enabled': True`, `frames_seen` climbing.
A transiently empty `/health` response during play is the known lag class — frames capture on a worker
thread and are unaffected.

## 3. During the match

Nothing to do. Optional glance: `match-state: MATCH_STARTED` appears in the log ~15-30 s into real combat.
Do **not** restart anything mid-match; a `CONTESTED`/laggy patch resolves itself or is honestly reflected
in the verdicts.

## 4. Stop + harvest (seals everything)

```bash
python scripts/retina_capture_daemon.py stop --kas
```

Expect, in order: corpus summary → `match-state: sealed MATCH_ENDED` (if a match was open) →
`ring-archive: copied N crops` → `KAS: <verdict> authored=<n>` → `PoSP: SYNCHRONIZED ...`.

**Honest-verdict table — what KAS may print and what it means:**

| Live KAS verdict | Meaning | Action |
|---|---|---|
| `AUTHORED_SESSION authored=N` | live path promoted (fps allowed it) | bonus — record it |
| `INSUFFICIENT_KILLS authored=0` | **expected under lag** — live crops thinned below K=3 | proceed to §5; this is why the offline path is primary |
| `HYGIENE_FAIL` / `UNVERIFIABLE` | rails fired | investigate before any claim; never override |

## 5. The reliability path — offline deferred recovery (the pilot deliverable)

```bash
python scripts/rp_ocr_precision_scan.py --archive retina_kf_archive/<label>_<stamp> \
    --out audits/rp_ocr_scan_<label>.json                        # ~12 min per 600 crops
python scripts/build_deferred_attestation.py \
    --scan audits/rp_ocr_scan_<label>.json \
    --archive retina_kf_archive/<label>_<stamp> \
    --kas audits/kas_record_<label>_<date>.json \
    --window-latency-pad-ms 4000
```

Accept only: `verdict: DEFERRED_AUTHORED_SESSION` + `verifier: OK`. The record is written to
`audits/kas_deferred_record_<label>_<date>.json`. `DEFERRED_OBSERVED_ONLY` or authored below floor is an
honest low-kill/low-density result — report it as such, never pad past 4000 to force a verdict (golden
pack bar E; the >4 s tail is a documented limit).

## 6. Certificate handoff (what the organizer receives)

```bash
python scripts/match_certificate.py build \
    --posp audits/posp_record_<label>_<date>.json \
    --kas audits/kas_record_<label>_<date>.json \
    --deferred audits/kas_deferred_record_<label>_<date>.json \
    --out audits/match_certificate_<label>.json
python scripts/match_certificate.py verify --cert audits/match_certificate_<label>.json \
    --posp audits/posp_record_<label>_<date>.json     # off-rig re-check; add --snarkjs/--chain-rpc for C5/C6
```

Without `--snarkjs`/`--chain-rpc` the verify honestly reports **`OVERALL: PARTIAL` (ZK UNCHECKED,
anchor-onchain UNCHECKED)** — a valid, honest handoff as long as it is reported as PARTIAL. For the full
**`VERIFIED`** (C5 Groth16 re-verify + C6 on-chain anchor read, 0 IOTX), use the one-command runner:

```bash
python scripts/portcert_full_verify.py --cert audits/match_certificate_<label>.json \
    --posp audits/posp_record_<label>_<date>.json
```

It discovers a local snarkjs (env `SNARKJS` → `contracts/node_modules/.bin` → PATH → npx), defaults the
IoTeX **testnet** RPC, pre-checks the cert's ZK refs, and holds a VERIFIED-only bar: exit 0 =
`OVERALL: VERIFIED`; exit 1 = ran but not VERIFIED; exit 2 = incomplete environment (never a pass).
Demonstrated on the M17 demo cert 2026-07-10: all checks green incl. `snarkjs groth16 verify OK` + anchor
tx confirmed on-chain.

**Goes to the organizer:** the certificate JSON (`qortroller-match-certificate-v0` — carries
`advisory=true`, `population_certified=false`, `verifier_independence` limits) + the verify command +
the one-pager + the golden-pack PASS line from §0.
**NEVER leaves the rig:** `retina_kf_archive/` crops, `sessions/` biometric data, the bridge DB, `.env`,
wallet keys. The certificate references sealed hashes; the raw evidence stays gamer-sovereign.

## 7. Say / don't-say (narrative rails, enforced by the one-pager's ceilings)

| Say | Don't say |
|---|---|
| "advisory presence + authorship attestation, post-match review signal" | anything that makes it a ban/prize input |
| "authorship proven offline on the sealed archive (deferred + pad + verify)" | "live path is healthy/fixed" — self-starving criterion is OPEN |
| "oracle SEPARATED vs modeled automation; `developer_self` scope" | field-FAR numbers, identity claims, population certification |
| "testnet demonstration; nothing purchasable" | any token/TGE framing |

## 8. Failure modes

| Symptom | Cause | Move |
|---|---|---|
| `already running (pid=…). Run 'stop' first.` | prior daemon alive | `stop` (harvests it), then `start` fresh |
| golden pack exit 1/2 during pilot day | regression / missing archive | halt pilot claims; fix per §0 |
| scan matches ≈0 | wrong window captured (check `--monitor`, RP window visible) | re-check §1-2; the archive is still sealed for later |
| `PARTIAL_SURFACES` PoSP | one surface missing (e.g. no fusion rows) | honest partial — report as-is |
| deferred `UNVERIFIABLE` | session_id mismatch / manifest tamper rail fired | do NOT hand off; investigate the join |

---

*Pilot ops runbook v0.1 — 2026-07-10. Commands validated live on this rig (lean_d11 / lean_f2_validate).
Loop: grok designs · Claude audits+builds · operator runs and decides distribution.*
