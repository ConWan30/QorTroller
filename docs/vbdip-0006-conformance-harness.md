# VBDIP-0006 Conformance Harness — M0 Implementation Plan

**Status:** M0 planning artifact. No vectors generated. No harness code written. No mock-controller scaffold yet. Implementation requires explicit operator authorization per phase.
**Date:** 2026-05-16
**Authoring discipline:** Mirrors `docs/mobile-companion-app.md` M0 pattern (plan only; stop at commit; phased commission downstream).
**Anchors consumed:**
- `wiki/methodology/VBDIP-0006-vapi-firmware-reference-implementation.md` §8 (SHA-256 `0667cd34...d3db`, architect-signed at commit `1f30057d` per `vsd-vault/manifests/proposals-VBDIP-0006/001.manifest.json`)
- `bridge/vapi_bridge/codec.py` (the canonical 228B/164B PoAC wire-format implementation)
- `docs/mobile-companion-app.md` (parallel M0 discipline reference)

---

## 1. Scope and authority

### 1.1 Source of truth

**VBDIP-0006 §8 is the source of truth** for what conformance means. This document is an **implementation plan** for turning §8's requirement ("100 deterministic test vectors") into a concrete, repo-resident software harness. This document is NOT a successor specification. If §8 and this document ever disagree, §8 wins; this document gets amended.

The architect-signed manifest at `vsd-vault/manifests/proposals-VBDIP-0006/001.manifest.json` pins VBDIP-0006 v1.0 by SHA-256. Any change to §8's vector-category breakdown, 100-count target, or 8-step validation flow requires a new VBDIP-0006 version + a fresh architect signing ceremony — not an edit to this plan.

### 1.2 What this plan covers

Concrete, repo-shipped engineering work to produce:

1. A deterministic generator that emits the 100 conformance vectors from the bridge's existing wire-format reference (`codec.py` as oracle).
2. A mock-controller simulator that satisfies the wire-format contract a real VBDIP-0006-conformant controller must satisfy — used as the v0 reference for any firmware engineer.
3. A test harness that exercises both (a) the mock controller in software and (b) a future real USB-HID-connected VAPI-Native Controller, with shared validation logic.
4. CI integration that runs the software path on every commit and gates the hardware path behind an explicit marker.

### 1.3 What this plan does NOT cover

- Firmware itself (out of scope — VBDIP-0006 §4 names that as a separate manufacturer/operator engineering track).
- Manufacturer outreach or partnership work (cross-references VBDIP-0006 §7 but the relationship work is operator-runtime, not engineering).
- Bridge runtime changes (the harness is a consumer of the existing codec; no bridge writes).
- Frontend / mobile companion surfaces (this work is separate from the mobile companion track; both can proceed independently).
- Any wallet, on-chain, signing-ceremony, or PV-CI invariant additions.

---

## 2. Vector generation methodology

### 2.1 Bridge `codec.py` is the oracle

The bridge module at `bridge/vapi_bridge/codec.py` is the canonical 228-byte/164-byte wire-format implementation. Verified primitives:

| Symbol | Role |
|---|---|
| `POAC_BODY_SIZE = 164` | FROZEN body length (everything before the signature) |
| `POAC_SIG_SIZE = 64` | FROZEN ECDSA-P256 signature length |
| `POAC_RECORD_SIZE = 228` | FROZEN total record length |
| `class PoACRecord` | Dataclass holding the 9 body fields + signature |
| `parse_record(data: bytes) -> PoACRecord` | Bytes → struct (also asserts 228-byte input) |
| `verify_signature(record, pubkey_bytes) -> bool` | ECDSA-P256 verify over the 164-byte body |
| `compute_device_id(pubkey_bytes) -> bytes` | `keccak256(pubkey)[0:8]` per VBDIP-0006 §3.1 byte layout |
| `verify_chain_link(prev_record, record) -> bool` | `prev_record_hash` integrity check per CLAUDE.md hard rule |

These primitives constitute the **oracle**: for any well-formed input tuple `(device_pubkey, counter, timestamp_ms, prev_record_hash, sensor_commitment, inference_code, l4_features, l5_rhythm_cv/entropy/quant_flag)`, the bridge's existing serialization path produces exactly one canonical 164-byte body. The generator's job is to enumerate inputs in the §8 categories and capture the canonical output.

### 2.2 Why this is deterministic

The codec uses `struct.pack` over a frozen field-format string + raw 32-byte hashes + IEEE 754 float16 for L4 features (per VBDIP-0006 §3.1 ref). No randomness, no system clock, no platform-dependent encoding. Given identical inputs, `parse_record(serialize(inputs))` returns identical bytes on every platform. Vector generation can therefore happen once + be committed as fixtures + replayed against any future firmware.

### 2.3 Vector categories (per VBDIP-0006 §8.1, count distribution as named)

| # | Category | Vectors | Generator approach |
|---|---|---|---|
| C1 | Random | 20 | Mersenne Twister seed=0; each field sampled from its full domain (`device_pubkey_hash` from `urandom`-but-seeded byte gen, `counter` uniform on `[1, 2^63)`, `timestamp_ms` uniform on plausible epoch range, etc.) |
| C2 | Edge case | 20 | Field-domain extremes: zero-valued, max-valued, negative L4 floats (NaN/Inf rejected per IEEE 754 float16 quiet-NaN rule), zero device_pubkey, max counter just below rollover, L5 entropy at 0.0 and at `log2(64)` ≈ 6.0, l5_rhythm_quant_flag both 0 and 1 |
| C3 | Hard-cheat | 20 | `inference_code` set to `0x28` DRIVER_INJECT; other fields varied across the C2 edge-case distribution so the harness validates that hard-cheat encoding is independent of biometric field values (cheat detection happens at the inference_code level, not the L4/L5 level) |
| C4 | GIC chain rollup | 20 | Sequence of 20 records with `prev_record_hash[i] = SHA-256(body[i-1])` chained; vector i carries the running-chain state so harness validates `verify_chain_link` end-to-end |
| C5 | Counter rollover | 20 | `counter` values clustered near `2^64 - 1` (exact rollover behavior is uint64 wrap-around per `struct.pack("Q")`; verifies firmware handles the boundary without overflow) |

**Total: 100 vectors.** Counts match VBDIP-0006 §8.1 verbatim. The allocation is operator-authorizable in §9.

### 2.4 Negative-suite extension (operator-authorizable in §9)

VBDIP-0006 §8.1's 100 vectors are all **passing** vectors (firmware must serialize each one byte-for-byte). A negative suite — vectors that an attacker might submit (truncated records, bit-flipped signatures, mismatched device_id) — is NOT named in §8. We can either:

- **Bundle negative vectors alongside the 100** in a separate `negative/` subdirectory with `expected_signature_status: invalid` markers, OR
- **Keep them in a separate harness** under `scripts/vbdip_0006_conformance/negative_suite/`

§9 names this as an unresolved decision.

### 2.5 Signature handling

The 100 vectors per §8 cover **wire-format compliance** primarily. Signing is a separate step (§8.1 steps 6-8). Two approaches for signature inclusion in vectors:

- **Approach A — Deterministic test key**: A single test-only Ed25519/ECDSA-P256 key pair is committed in `scripts/vbdip_0006_conformance/test_signing_key.pem` (private + public). Every vector ships with a pre-computed signature over its `expected_body_bytes`. The mock controller AND any real firmware running with the same test key produce the same signatures byte-for-byte. **Downside**: a committed private key is by definition compromised; harness must enforce "this key MUST NOT register a real device on `VAPIHardwareCertRegistry`" via a regtest-only flag.
- **Approach B — Fixture signatures from a one-time canonical signer**: Vectors ship with pre-computed signatures from a key that was generated, signed all 100 vectors, and then deleted. The private key never exists post-generation. Real firmware running with its OWN device key cannot reproduce these signatures — the harness validates "signature was VALID at generation time" not "signature is reproducible by you." Real firmware passes if the harness verifies its own signatures against its own pubkey.

§9 names this as an unresolved decision. **Approach B is cleaner cryptographically**; Approach A is simpler operationally. Recommendation pending operator decision.

---

## 3. Concrete vector schema

### 3.1 Per-vector JSON shape

```json
{
  "vector_id": "TV-001",
  "vbdip_version": "0006-v1.0",
  "vbdip_spec_hash": "0667cd34ec2635e58da3fb7860d537018ed3b4f30290df2ccac4a84ecbf1d3db",
  "category": "random",
  "input": {
    "device_pubkey_hash_hex": "...",                                  // 64 hex chars = 32 bytes (keccak256 of full pubkey, per VBDIP-0006 §3.1)
    "counter": 12345,                                                  // uint64
    "timestamp_ms": 1747252800000,                                     // uint64
    "prev_record_hash_hex": "0000...",                                 // 64 hex chars = 32 bytes (zero for first record in any C4 chain)
    "model_manifest_hash_hex": "...",                                  // 64 hex chars
    "world_model_hash_hex": "...",                                     // 64 hex chars
    "sensor_commitment_hex": "...",                                    // 64 hex chars
    "inference_code": 0,                                               // uint8
    "l4_features_float16": [/* 13 IEEE 754 float16 values, hex */],
    "l5_rhythm_cv_float16_hex": "...",
    "l5_rhythm_entropy_float16_hex": "...",
    "l5_rhythm_quant_flag": 0
  },
  "expected": {
    "body_hex": "...",                                                 // 328 hex chars = 164 bytes (the FROZEN serialization)
    "body_sha256_hex": "...",                                          // 64 hex chars = full SHA-256
    "record_hash_hex": "...",                                          // 32 hex chars = SHA-256(body)[0:16] per CLAUDE.md hard rule
    "signature_status": "valid_test_fixture",                          // 'valid_test_fixture' | 'unsigned' | 'invalid_intentional'
    "signature_hex": "...",                                            // 128 hex chars = 64 bytes, OR null when signature_status is 'unsigned'
    "signing_pubkey_hex": "..."                                        // 64 hex chars = 32 bytes raw Ed25519 pubkey, OR null
  },
  "validation": {
    "expected_verdict": "pass",                                        // 'pass' | 'fail_format' | 'fail_signature' | 'fail_chain'
    "failure_mode_when_fail": null,                                    // human description for negative vectors only
    "verifies_chain_against_prev_vector_id": null                       // C4 GIC chain vectors point at the predecessor: "TV-041" for "TV-042"
  },
  "notes": "Random-category vector (Mersenne Twister seed=0, sample 1)"
}
```

### 3.2 Field discipline

- All hex fields are **lowercase, no 0x prefix**, fixed-length per the underlying byte count.
- IEEE 754 float16 values stored as hex (4 hex chars = 2 bytes) rather than as JSON floats, since JSON numbers cannot losslessly represent float16 subnormals/NaN/Inf. Avoids parser drift.
- `vbdip_spec_hash` pinned in every vector — if the spec is amended, regenerate-all is required and the hash change makes drift visible.
- `vector_id` format `TV-NNN` with zero-padded 3-digit sequence; 001-020 = C1 random, 021-040 = C2 edge-case, 041-060 = C3 hard-cheat, 061-080 = C4 GIC chain, 081-100 = C5 counter rollover. Naming convention operator-authorizable in §9.

### 3.3 Vector storage format

Two options:

- **All-in-one**: single `vectors.json` array of 100 objects (~80-150 KB compressed)
- **Per-category files**: `vectors/001-020-random.json`, `vectors/021-040-edge.json`, etc.

§9 names this as an unresolved decision. Recommend per-category for readability + smaller diffs when regenerated.

Binary fixtures (raw 164-byte body bytes, raw 228-byte record bytes including signatures) committed alongside as `.bin` files for byte-level comparison without JSON parser involvement. §9 names this as an unresolved decision.

---

## 4. Repo file layout

### 4.1 Proposed paths

```
scripts/vbdip_0006_conformance/
├── README.md                          # consumer-facing: how to run, how to add vectors
├── generator.py                       # M1 deliverable — generates vectors from codec.py oracle
├── mock_controller.py                 # M2 deliverable — Python reference simulator
├── harness.py                         # M3 deliverable — validation loop
├── test_signing_key.pub.pem           # public key only (private key handling per §9 Approach A vs B)
├── vectors/
│   ├── 001-020-random.json
│   ├── 021-040-edge.json
│   ├── 041-060-hardcheat.json
│   ├── 061-080-chain.json
│   ├── 081-100-rollover.json
│   ├── binary/                        # parallel directory; one .bin per vector_id
│   │   ├── TV-001.body.bin
│   │   ├── TV-001.record.bin           # null when signature_status == 'unsigned'
│   │   └── ...
│   └── negative/                       # optional per §9 unresolved decision
│       └── ...
└── manifests/
    └── conformance-run-YYYYMMDD-HHMMSS.json   # M4 deliverable — pass report fixture

bridge/tests/test_vbdip_0006_conformance_mock.py     # M3 deliverable — software-only suite
bridge/tests/hardware/test_vbdip_0006_conformance_hw.py  # M3 deliverable — hardware-gated; marker pattern
```

### 4.2 Why under `scripts/` not `bridge/`

The harness exercises the bridge's `codec.py` as an oracle but does NOT extend the bridge runtime. Mock controller is a standalone simulator for external use (manufacturer engineer pulls the directory + runs against their firmware). Placing it under `scripts/` matches the convention used by `scripts/zkba_compile_*.py`, `scripts/mlga_compile_session_artifact.py`, `scripts/vapi_invariant_gate.py`, and the existing protocol-tooling families.

### 4.3 What stays inside `bridge/tests/`

Only the actual pytest test files that the bridge's CI gate runs. The vector fixtures + generator + mock controller live in `scripts/` so they can be redistributed independently (manufacturer ZIP, harness-only release) without dragging the entire bridge codebase.

---

## 5. Mock-controller simulator plan

### 5.1 Role

`scripts/vbdip_0006_conformance/mock_controller.py` is a Python class implementing the **same wire-format contract** a VBDIP-0006-conformant controller's firmware must satisfy. Two roles:

- **Test harness consumer**: the harness drives the mock controller with vector inputs + collects outputs + compares against expected bytes. This is how `bridge/tests/test_vbdip_0006_conformance_mock.py` runs in CI without any hardware.
- **Reference implementation for firmware engineers**: a manufacturer engineer reads `mock_controller.py` to understand the exact wire-format expected before writing the C/Rust firmware. Comments + assertions in the simulator are documentation by code.

### 5.2 Class shape (M2 deliverable; documented here for planning)

```python
class VBDIP0006MockController:
    """
    Pure-software reference of a VBDIP-0006 v1.0-conformant controller.
    Implements the wire-format contract — NOT the secure-element semantics
    (no anti-tamper, no rate-limiting, no power-state-machine). Firmware
    engineers use this to verify their serialization matches before
    bringing up real hardware.
    """
    def __init__(self, device_pubkey: bytes, signing_method: str):
        # signing_method ∈ {'test_fixture', 'live_sign', 'unsigned'}
        ...

    def serialize_body(self, vector_input: dict) -> bytes:
        """Construct the 164-byte body per VBDIP-0006 §3.1 byte layout.
        MUST byte-match what bridge/vapi_bridge/codec.py produces from
        the same inputs — this is the conformance discipline."""
        ...

    def sign_body(self, body: bytes) -> bytes:
        """Produce a 64-byte ECDSA-P256 signature over body.
        Behavior depends on signing_method (see __init__)."""
        ...

    def emit_record(self, vector_input: dict) -> bytes:
        """Compose body + signature → 228-byte record."""
        ...

    def respond_to_test_harness_command(self, cmd: dict) -> dict:
        """Mirror VBDIP-0006 §8.2 step-by-step harness protocol.
        Real firmware exposes this via USB-HID OUT/IN reports; the
        mock exposes it as a Python method call."""
        ...
```

### 5.3 Discipline guards

- **No hardware imports.** `mock_controller.py` MUST NOT import `hidapi`, `pyusb`, `serial`, etc. Pure software. Verifiable via static-grep CI guard (mirror `INV-PUBLIC-FORENSIC-001` pattern).
- **Bridge codec.py as oracle, NOT as dependency.** Mock controller implements the wire format independently. The harness compares mock's output against codec's output as the cross-check. If mock just imports codec.py, the comparison is degenerate (always equal). The two implementations are kept independent so they're a real reference vs reference cross-check. This is the **R5 overfitting risk** named in §10.

---

## 6. Real-controller harness plan

### 6.1 Future path

When the first VBDIP-0006-conformant firmware exists (operator-runtime build OR manufacturer-shipped controller), the same 100 vectors validate it. Two interface deltas vs the mock:

- **Transport**: USB-HID via `hidapi` (Python `hidapi` bindings; already in `bridge/vapi_bridge/dualshock_integration.py` use). Real firmware presents Interface 3 with Usage Page 0xFF00 per VBDIP-0006 §2 Channel A; harness opens that interface + writes vector inputs as OUT reports + reads expected_body responses as IN reports.
- **Signature collection**: harness reads the device's public key via Report ID 0x02 heartbeat (per VBDIP-0006 §8.2), then verifies signatures the device produces using the device's own pubkey (NOT the test-fixture pubkey).

### 6.2 Hardware test marker discipline

Following the existing repo convention:

```python
# In bridge/tests/hardware/test_vbdip_0006_conformance_hw.py
import pytest

pytestmark = pytest.mark.hardware  # default-excluded from CI
```

CI runs the `_mock.py` suite on every commit; hardware suite runs only when an engineer explicitly opts in with `pytest -m hardware`. Mirrors the existing `tests/hardware/test_*.py` family (`@pytest.mark.hardware` per CLAUDE.md "Hardware tests gated @pytest.mark.hardware, excluded from CI" hard rule).

### 6.3 Parity contract

Firmware passes conformance iff:

1. All 100 vectors in the mock suite pass — **same vector file**, no firmware-specific divergence.
2. When run against real hardware via the `_hw.py` suite, every vector's body output is byte-identical to the `expected.body_hex`.
3. Every vector's record_hash output is byte-identical to `expected.record_hash_hex`.
4. Every signature the firmware produces verifies against the firmware's own pubkey via the harness's own ECDSA-P256 verifier (NOT the test-fixture verifier, because the firmware has its own SE-resident key).
5. Aggregate pass report manifest is committed to the manufacturer's `VAPIHardwareCertRegistry` cert IPFS payload per VBDIP-0006 §7.2.

---

## 7. Validation loop

### 7.1 Per-vector 8-step check (codified from VBDIP-0006 §8.1)

For each vector V in the 100-vector suite, the harness executes:

```
1.  load_vector(V):
       parse JSON; assert vbdip_spec_hash matches the current
       architect-signed VBDIP-0006 hash; load binary fixtures
       from vectors/binary/<vector_id>.body.bin

2.  construct_inputs(V.input):
       decode hex fields to bytes; reconstruct float16 features

3.  serialize_body(inputs) → produced_body_bytes:
       Mock case: mock_controller.serialize_body(inputs)
       Real-hardware case: USB-HID OUT cmd + read IN response

4.  compare_body_hex:
       assert produced_body_bytes.hex() == V.expected.body_hex
       FAIL → "body serialization drift at byte N (expected X got Y)"

5.  compute_record_hash:
       computed = sha256(produced_body_bytes).digest()[:16]
       (CLAUDE.md hard rule: chain link hash = SHA-256(164B body))

6.  compare_expected_hash:
       assert computed.hex() == V.expected.record_hash_hex
       FAIL → "record_hash drift — body and hash inconsistent"

7.  verify_signature_expectation:
       If V.expected.signature_status == 'valid_test_fixture':
           ecdsa_p256_verify(V.expected.signing_pubkey_hex,
                             V.expected.signature_hex,
                             produced_body_bytes)
           assert PASS
       If V.expected.signature_status == 'unsigned':
           assert V.expected.signature_hex is null
           (skip signature check entirely)
       If V.expected.signature_status == 'invalid_intentional':
           (negative vector — see §9 unresolved decision on
            whether negative vectors live in the main suite or
            separate negative_suite/ subdir)

8.  assert_verdict_or_failure:
       expected = V.validation.expected_verdict
       actual   = derived from steps 4-7
       assert actual == expected
       If actual != expected:
           emit per-vector failure trace +
           emit aggregate failure summary at end of suite
```

### 7.2 Aggregate manifest

After all 100 vectors complete, harness writes:

```
scripts/vbdip_0006_conformance/manifests/
   conformance-run-YYYYMMDD-HHMMSS.json
```

Fields: `run_ts_ns`, `vbdip_spec_hash`, `harness_version`, `controller_type` (mock/hardware), `firmware_pubkey_hex` (when hardware), `passed_count`, `failed_count`, `failed_vector_ids[]`, `per_failure_trace_ipfs_cid` (optional). Manufacturers ship this manifest to IPFS + reference its CID in their VAPIHardwareCertRegistry cert payload per VBDIP-0006 §7.2.

---

## 8. CI integration path

### 8.1 Software suite (mock)

`bridge/tests/test_vbdip_0006_conformance_mock.py`:
- Runs as part of standard `python -m pytest bridge/tests/` CI gate
- Expected test count delta: +100 (one parametrized test per vector) OR +5 (one parametrized test per category with 20 sub-cases). Recommend per-category for readable CI output, per-vector for granular failure isolation. **§9 names this as unresolved.**
- Estimated runtime: <30 seconds for all 100 vectors (pure-Python serialization + SHA-256 + ECDSA verify; no I/O)
- Counts toward the existing bridge test total (currently 3487 per CLAUDE.md header)

### 8.2 Hardware suite (real-controller)

`bridge/tests/hardware/test_vbdip_0006_conformance_hw.py`:
- Marker pattern: `pytestmark = pytest.mark.hardware`
- Default CI: SKIPPED (matches existing `tests/hardware/*` discipline)
- Manual run: `python -m pytest bridge/tests/hardware/test_vbdip_0006_conformance_hw.py -v -m hardware -s`
- Estimated runtime: 1-5 minutes depending on USB-HID polling cadence + per-vector firmware response time
- Operator runs this when a candidate firmware exists; manufacturer runs this as part of device family certification gate

### 8.3 PV-CI invariant scope (currently NONE planned)

Per the brief's instruction "do not invent new PV-CI scope," this plan does NOT propose new PV-CI invariants for the conformance harness. The existing `INV-VBDIP-0006-001..004` invariants pin regions of the spec; spec stability already guards harness stability transitively (any spec change forces vector regeneration + harness drift becomes visible).

A future implementation phase MAY propose:
- `INV-VBDIP-0006-HARNESS-001` pinning the vector_id format `TV-NNN`
- `INV-VBDIP-0006-HARNESS-002` pinning the vector count = 100
- `INV-VBDIP-0006-HARNESS-003` pinning `mock_controller.py` MUST NOT import hidapi/pyusb/serial (overfitting guard from §5.3 + §10 R5)

These are deferred per the brief; M0 introduces nothing.

---

## 9. Unresolved decisions

These need operator input before implementation phases commission. Each marked **R** for recommended-default; operator can accept all or override specific items.

1. **Vector count allocation across categories.** **R: §8.1 verbatim (20+20+20+20+20 = 100).** Deviating from §8.1 would require a VBDIP-0006 amendment + fresh architect signing. Recommendation: stay verbatim with §8.1.
2. **Signature handling — Approach A (committed test key) vs Approach B (fixture signatures from deleted key).** **R: Approach B.** Cryptographically cleaner; eliminates the "committed private key MUST NOT be used on a real device" enforcement burden. Generator phase produces signatures with an ephemeral key + emits the pubkey-only PEM + securely shreds the private key + checks in only signed fixtures. Approach A is simpler operationally if the operator prefers reproducibility over key hygiene.
3. **Binary fixture storage format.** **R: per-vector `.bin` files in `vectors/binary/`.** Easier to diff (one file per vector) + readable via `xxd` / `hexdump` without JSON parser involvement. Alternative: single concatenated binary blob with offset table (smaller storage; harder debug).
4. **Negative vectors — main suite vs separate `negative_suite/`.** **R: separate `negative_suite/`.** Keeps the 100-vector "passing" set obviously aligned with §8.1; negative testing is harness-additive, not spec-additive. Easier to reason about coverage.
5. **Vector storage layout — all-in-one vs per-category.** **R: per-category files.** Better readability + smaller diffs when regenerated.
6. **Test parametrization granularity — one test per vector vs one per category.** **R: per-vector.** Granular failure isolation (CI shows exactly which vector_id failed); 100 tests is not noisy at the bridge's current 3487-test scale.
7. **Naming convention for VBDIP-0006 conformance versions.** **R: tie versions to VBDIP-0006 spec versions.** Vectors generated against VBDIP-0006 v1.0 are named `vectors-v1.0/`. Future VBDIP-0006 v1.1 amendments would produce `vectors-v1.1/` alongside, with the v1.0 vectors preserved for backward-compatibility validation. Pubkey/private-key fixtures versioned together (`test_signing_key_v1.0.pub.pem`).
8. **Harness consumer's pubkey-from-real-firmware path.** **R: Report ID 0x02 heartbeat read per VBDIP-0006 §8.2** — already named in the spec. No operator decision needed; called out for completeness.

### 9.1 Acceptance protocol

Operator's three options (mirroring mobile companion §9 acceptance protocol):
- **Accept all 8 defaults as-is** — explicit single message; defaults become binding for M1 commissioning.
- **Accept some, modify others** — name overrides; this doc gets a follow-up amendment before M1.
- **Defer entirely** — plan stays live as canonical reference; no harness work starts.

### 9.2 Operator decisions accepted (M0.1 amendment, 2026-05-16)

**All 8 recommended defaults R1-R8 ACCEPTED** by operator as the binding basis for M1 commissioning, with one clarification to R2. The §9 numbered list above remains as the M0 "as-proposed" record; this section carries the binding accepted state (per the §1.2 authoring discipline: amendments append; the original record persists).

| # | Decision | Status |
|---|---|---|
| R1 | Vector counts §8.1 verbatim (20 × 5 = 100) | **ACCEPTED** |
| R2 | Signature handling | **ACCEPTED (CLARIFIED — see below)** |
| R3 | Per-vector `.bin` files in `vectors/binary/` | **ACCEPTED** |
| R4 | Separate `negative_suite/` (negative vectors NOT in main 100) | **ACCEPTED** |
| R5 | Per-category vector JSON files | **ACCEPTED** |
| R6 | Per-vector pytest parametrization (granular failure isolation) | **ACCEPTED** |
| R7 | Vectors versioned with spec (`vectors-v1.0/` alongside future `vectors-v1.x/`) | **ACCEPTED** |
| R8 | Pubkey-from-firmware via Report ID 0x02 heartbeat (already in VBDIP-0006 §8.2) | **ACCEPTED** |

#### R2 (CLARIFIED, BINDING) — deleted-key deterministic fixture signatures

Replaces the original R2 recommended wording with the more specific operator-clarified contract. This is what M1 implements:

- **M1 generator MAY create a deterministic ephemeral test key** for fixture generation (deterministic = produced from a fixed seed so a re-run of the generator yields an identical key pair before deletion; ephemeral = exists only for the duration of the M1 generator invocation).
- **Generator commits ONLY** the following to the repo:
  1. **Public key** — PEM-encoded at `scripts/vbdip_0006_conformance/test_signing_key_v1.0.pub.pem` (extension carries the spec-version tie from R7)
  2. **Signatures** — one per vector whose `signature_status == 'valid_test_fixture'`, embedded in the vector JSON's `expected.signature_hex` field
  3. **Vectors** — the 100 JSON files + binary fixtures under `scripts/vbdip_0006_conformance/vectors/`
  4. **Generator transcript / deletion attestation** — an audit-bearing JSON document at `scripts/vbdip_0006_conformance/manifests/generator-transcript-v1.0.json` recording: (a) when the generator ran, (b) what deterministic seed was used, (c) what method produced the ephemeral key, (d) what method then destroyed the private key (`secure_zero_then_unlink` or equivalent), (e) the VBDIP-0006 spec hash the run was bound to (`0667cd34...d3db`), (f) the architect-signed manifest commit reference (`1f30057d`), (g) cryptographic hash of the generator script source at run time so post-hoc auditors can confirm no in-place tampering
- **NEVER commits the private key.** No path under `scripts/vbdip_0006_conformance/` may contain a private key file. CI guard: static-grep regression test asserting the absence of `BEGIN PRIVATE KEY` / `BEGIN ED25519 PRIVATE KEY` / `BEGIN EC PRIVATE KEY` substrings under the conformance directory.
- **Signature fixtures are reproducible ONLY through the recorded generator method + transcript**, NOT by retaining signing material. The transcript is the audit primitive that lets anyone confirm "yes, valid signatures were produced + the key was destroyed" — it does NOT enable signature regeneration without re-running the generator (which would produce identical signatures given the same deterministic seed + script hash + spec hash).

#### Operational consequences

- **Real firmware running with its own SE-resident key does NOT reproduce these fixture signatures byte-for-byte.** Impossible by design — the fixture key is gone. Firmware passes by verifying its OWN signatures against its OWN pubkey using the harness's ECDSA-P256 verifier (per the §6.3 parity contract).
- **Fixture signatures function as an integrity artifact** proving "vectors were signed with a valid key at generation time" — they are not a reproducibility primitive for firmware conformance.
- **The generator transcript provides post-hoc audit.** Anyone can read it and verify: no private key shipped, no private key retained, no private key recoverable from any committed file. Combined with the static-grep CI guard, this is belt-and-suspenders.
- **A future spec amendment** (VBDIP-0006 v1.x per §11 versioning) triggers a fresh M1 generator run producing `vectors-v1.x/` + `test_signing_key_v1.x.pub.pem` + `generator-transcript-v1.x.json`. The v1.0 artifacts remain committed for backward-compat validation; the new key for v1.x is generated + destroyed independently of the v1.0 key.

#### M1 commissioning basis

§9.2 (this section) is now the binding basis for M1 commissioning. The original §9 list remains as the M0 "as-proposed" record. When M1 ships, the closure note at the bottom of this document will cite this §9.2 + the commit hash of the M1 ship.

---

## 10. Risk register

| # | Risk | Severity | Likelihood | Mitigation |
|---|------|----------|------------|------------|
| R1 | **Codec oracle drift.** `codec.py` byte layout changes between vector-generation time and vector-validation time → all 100 vectors silently invalidated. | HIGH | LOW | Pin codec.py region in PV-CI under a future `INV-CODEC-WIREFORMAT-001` invariant; vector files carry `vbdip_spec_hash` field; harness asserts the field matches the architect-signed VBDIP-0006 hash at runtime; mismatch = harness fails-fast with a clear "spec drift; regenerate" message before validating any vector. |
| R2 | **Accidental successor-spec behavior.** This plan document creeps into adding requirements not in VBDIP-0006 §8 (e.g. specifying a 101st vector category, mandating Approach A vs B). | MEDIUM | MEDIUM | This document explicitly disclaims successor-spec status in §1.1. Every operator-authorizable decision in §9 names the specific tradeoff being made + flags any deviation from §8.1 as requiring a VBDIP-0006 amendment + fresh architect signing. |
| R3 | **Signature-fixture ambiguity.** Approach A's committed private key gets used on a real `VAPIHardwareCertRegistry` certification → false-positive certified controllers using a shared/leaked key. | HIGH | MEDIUM (if A chosen) | If Approach A selected: `test_signing_key.pem` filename + commit message + README explicitly mark the key as REGTEST-ONLY; the bridge enforces a refusal: any cert request whose `device_pubkey == test_signing_key.pub` returns 400. Approach B eliminates the risk entirely. |
| R4 | **Hardware HID variability.** USB-HID descriptors differ across MCU vendors (Teensy 4.1 vs STM32H743 vs NXP MCXN947); harness assumes one descriptor shape; real firmware uses another. | MEDIUM | HIGH | VBDIP-0006 §2 specifies Usage Page 0xFF00 + Report ID 0x01 as FROZEN. Harness opens by usage-page lookup (NOT vendor/product ID), so any conformant firmware works regardless of MCU. Document a `connect_via_usage_page()` helper in `harness.py`. |
| R5 | **Overfitting mock controller to bridge implementation.** `mock_controller.py` accidentally imports `codec.py` for serialization OR mirrors a codec-private helper → mock's "PASS" becomes circular (mock matches codec because mock IS codec). | HIGH | MEDIUM | Static-grep CI guard: `mock_controller.py` MUST NOT contain `from bridge` OR `import codec` OR equivalent. Mock must reimplement `struct.pack` + hash chains independently. Cross-check with codec.py is the validation discipline, not the construction. |
| R6 | **Confusing PoAC body hash vs full signed record hash.** The §8 spec carefully distinguishes `SHA-256(164B body)[0:16]` (the 16-byte record_hash field) from `SHA-256(228B record)` (which is computed nowhere because the signature is over the body, not over a re-hashed full record). A confused implementer could compute the wrong hash + the harness might silently agree if vectors were generated wrong. | MEDIUM | MEDIUM | Vector field naming explicit: `body_sha256_hex` (full 32-byte hash of body) + `record_hash_hex` (the 16-byte truncation actually stored in the wire format) are SEPARATE fields. Validation step 5 distinguishes them. Reviewer reads two fields; ambiguity surfaces. |
| R7 | **Vector file diff churn on regeneration.** Regenerating vectors with a different RNG seed or generator version produces 100 different files; PR diff becomes enormous. | LOW | HIGH | (a) Seed fixed at `Mersenne Twister seed=0` for C1; (b) Generator emits stable byte-order (sort_keys=True canonical JSON); (c) Re-running generator with same inputs produces byte-identical files (deterministic); (d) Generator commits a `vectors-generator-version: N` field; only bump on real generator changes; (e) PR title convention `feat(vbdip-conformance): regenerate v1.0 vectors` flags regeneration explicitly. |
| R8 | **Manufacturer ZIP redistribution drift.** Harness shipped to a manufacturer engineer + they modify it locally → their pass-report uses a different harness than the canonical one. | MEDIUM | LOW | Pass-report manifest includes `harness_version` field; the `VAPIHardwareCertRegistry` cert verification path checks that the reported harness_version matches a known-canonical hash. Manufacturer's modified harness fails the cert verification — the manufacturer must re-pull the canonical version. |

---

## 11. Implementation milestones — M0 → M4

### M0 — Planning artifact ✅ COMPLETE (this document)

### M1 — Vector generator + 100 vectors

Deliverables:
- `scripts/vbdip_0006_conformance/generator.py` (~200-400 LOC)
- 100 vectors in `scripts/vbdip_0006_conformance/vectors/`
- Binary fixtures in `scripts/vbdip_0006_conformance/vectors/binary/`
- `scripts/vbdip_0006_conformance/test_signing_key.pub.pem` (signature pubkey only, per Approach B)

Pass criteria: 100 vectors generated; binary fixtures match JSON expectations; idempotent (re-running generator produces byte-identical files).

### M2 — Mock controller simulator

Deliverables:
- `scripts/vbdip_0006_conformance/mock_controller.py` (~300-500 LOC)
- Static-grep CI guard verifying mock does NOT import from `bridge/` or `codec` (R5 mitigation)

Pass criteria: mock controller serializes inputs to byte-identical outputs as the bridge codec for all 100 vectors WITHOUT importing the codec.

### M3 — Validation harness + CI integration

Deliverables:
- `scripts/vbdip_0006_conformance/harness.py` (~200-400 LOC)
- `bridge/tests/test_vbdip_0006_conformance_mock.py` (~150 LOC; 100 parametrized tests)
- `bridge/tests/hardware/test_vbdip_0006_conformance_hw.py` (~100 LOC; marker-gated)
- `scripts/vbdip_0006_conformance/README.md` (~150 lines; operator + manufacturer instructions)

Pass criteria: software suite passes 100/100 in CI; hardware suite skips by default; manual hardware-marker invocation correctly opens a real Interface 3 + walks vectors.

### M4 — Pass-report manifest + manufacturer distribution shape

Deliverables:
- Aggregate manifest schema + writer (`scripts/vbdip_0006_conformance/manifests/`)
- Manufacturer-ZIP build script that packages only the conformance directory + spec snapshot + README, for redistribution
- `docs/vbdip-0006-conformance-harness.md` Mn closure notes per milestone

Pass criteria: a manufacturer engineer can pull the ZIP, run the suite against their candidate firmware, and produce a signed pass-report manifest matching the schema.

---

## 12. Authoring discipline

This document follows the same pattern as `docs/mobile-companion-app.md`:
- Plan-only; M0 is just this document
- Each milestone (M1-M4) closes with a `## Mn Closure Note` section appended (commit hash + actual LOC + deviations from plan)
- This document is the canonical implementation reference; future amendments land here, not in the architect-signed VBDIP-0006 spec
- Any conflict with VBDIP-0006 §8 = VBDIP-0006 wins; this doc gets amended

Cross-reference: when VBDIP-0006 v1.x amendments ship in the future (per VBDIP-0006 §11 versioning), this conformance plan generates `vectors-v1.x/` alongside `vectors-v1.0/` rather than replacing — backward compatibility validates that v1.0 firmware continues to pass against v1.0 vectors after a v1.1 spec amendment.

---

## Stop point

**Per operator brief: implementation does NOT begin. M1 commissions only after §9 is operator-resolved (accept defaults or override).** This document is the M0 deliverable. Mythos co-architect review of this plan is the recommended next step if operator wants protocol-consistency sanity-check before M1 — same cadence pattern as mobile companion §9 R6.
