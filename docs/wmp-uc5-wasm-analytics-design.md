# UC-5 — W3bstream provenance-preserving analytics (wasm port spec)

**Status (2026-07-16): Python REFERENCE built + tested (`bridge/vapi_bridge/wmp/analytics_ref.py`,
`test_wmp_analytics_ref.py`, 10 tests). The Rust `wasm32-unknown-unknown` port is DEFERRED — the wasm
target is uninstallable in the current sandbox (`rustup target add wasm32-unknown-unknown` no-ops,
network-restricted). CI builds the applet on its matrix; the port lands there or on a toolchain machine
and is validated against the parity vectors below. This doc is the contract; nothing here is a claim that
the wasm artifact exists yet.**

## What it is
A buyer verifies the STATISTIC, not the raw corpus: aggregate functions run inside the W3bstream wasm
sandbox over consented export rows, emitting a `(statistic, input_commitment_set, applet_version)` triple
the buyer re-checks. Additive to `w3bstream/applet/src/lib.rs`; the sandbox stays
mechanical-validation+aggregation (`sandbox_config.json` `frame_grabbing`/`optical_capture` stay `false`;
INV-W3S-001/002/005/006 unchanged).

## Row schema (the applet's input; each row is a pre-bound export ref, never raw HID)
```
{ field_id: string, value_i64: i64, consent_bits: u32,
  cross_aggregate_ok: bool, gamer_export_commitment: 64-hex }
```

## Rails (fail-closed; the Rust must reproduce EXACTLY — grok round-1 hammers)
1. **Consent is bound into provenance, not host-asserted.**
   `row_commit = SHA-256( b"WMP-ANALYTICS-ROW-v0" | field_id | be64(value_i64) | be32(consent_bits) |
   cross_u8 | gamer_export_commitment[32B] )`. Flipping consent/value/cross changes the commitment →
   a host cannot forge `consent=1` without the published `gamer_export_commitment`.
2. **Requested export category's consent bit MUST be set on every row** (categories mirror CONSENT-v1:
   TOURNAMENT_GATE=0, ANONYMIZED_RESEARCH=1, MANUFACTURER_CERT=2, MARKETPLACE=3).
3. **Cross-gamer** (>1 distinct `gamer_export_commitment`) requires `cross_aggregate_ok==true` on EVERY
   row — no single global consent flag.
4. **field_id ∈ FROZEN ALLOWLIST** (`session_tick_count, match_span_s, authored_kill_count,
   clean_session_count, verdict_class`) — deny-by-default; no IMU/tremor/humanity/liveness/APM.
5. **No IEEE float in the attested surface** — `mean` is fixed-point milli (`sum*1000//n`, `scale:"milli"`).

## Ops (v1): `count`, `sum`, `mean` (milli), `p50` (integer lower-median), `hist` (discrete value bins).

## Output triple
```
{ statistic: { op, field_id, payload:{ n, value|null, scale?, bins? } },
  input_commitment_set: { algo:"sha256-sorted-leaf-merkle-v0", root:64-hex, n, leaves:[64-hex] },
  applet_version: { crate:"w3bstream_applet", semver, wasm_sha256:64-hex } }
```
`input_commitment_set.root` = binary merkle over SORTED row_commit leaves (dup last if odd); empty set →
`SHA-256(b"WMP-ANALYTICS-EMPTY-v0")`.

## Parity vectors (the wasm port must reproduce these; from the Python reference tests)
- rows `[10,20,30,40]` `session_tick_count`, MARKETPLACE consent → count `"4"`, sum `"100"`,
  mean `"25000"` (milli), p50 `"20"`.
- `verdict_class` `[1,1,2,3,1]` → hist `{"1":3,"2":1,"3":1}`.
- row `{session_tick_count, 42, MARKETPLACE, cross=true, gec=aa*32}` → a fixed 64-hex `row_commit`
  (regenerate the golden from `row_commitment()` and pin it in the Rust test).

## Test plan for the port
1. `cargo build --release --target wasm32-unknown-unknown` (CI matrix).
2. Rust `#[cfg(test)]` unit tests over the pure `aggregate_*` + every consent fail case.
3. Assert the Rust reproduces the parity vectors above byte-for-byte (Python ↔ Rust mirror).
4. Extend `scripts/test_w3bstream_ingestion.py` only for the new payload schema / exit codes (it is Python
   mechanical validation — it does NOT execute the wasm binary; do not pretend it does).

## Honest ceiling
The applet attests **format + aggregation over consented exports**, NOT that a published export is
truthful (same class as DEPIN-1 "format only, not a truth oracle"). No cross-gamer pool without every
contributor's consent bit; no biometric/liveness-derived metrics; sandbox capture mechanisms stay off.
