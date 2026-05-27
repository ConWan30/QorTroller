# Path A Silicon-Rooted Signing — Arc 2 (SecureElementBackend + Hardware Integration)

> **Hardware gate confirmed cleared before this session starts.** This prompt
> does not execute until both pieces of hardware are physically connected:
>
> - ATECC608A breakout board (SparkFun DEV-18226 or Adafruit 4314 or equivalent)
> - CH341A USB-I2C adapter (or equivalent) connecting the breakout to the
>   laptop via USB-A
>
> If either is absent, stop here. Arc 2 cannot be partially executed — the
> `SecureElementBackend` must be tested against real silicon, not mocked.

## Context

Arc 1 delivered the complete protocol side of Path A: `SigningBackend` Protocol,
`HostKeyBackend`, `SecureElementBackend` stub (raises `NotImplementedError`),
`VAPIManufacturerDeviceRegistry` deployed on testnet, `VAPIProtocolLens_v2`
with `isFullyEligible_PathA()`, `DeviceBirthCertificate` format,
`provision_device_mfg.py` ceremony tooling, and `docs/path-a-manufacturing-spec.md`.
All of that is complete and waiting.

Arc 2 wires the stub to real hardware. One session. Four commits.

## Honest framing (locked before implementation starts)

Path A v1 composite signature structure:

- **ECDSA-P256 half**: signed in ATECC608A silicon — private key generated on-
  chip, locked, never exported under any condition
- **ML-DSA-44 half**: computed in bridge software (same as Path B) — the PQ half
  adds quantum-resistance but is not silicon-rooted

This is still called Path A because the ECDSA-P256 identity anchor — the key
that establishes controller identity — is physically unextractable from silicon.
The ML-DSA-44 PQ half remains software-computed until a future secure element
with Dilithium support ships (Path A v3+). This framing must appear in all
user-facing surfaces and the manufacturing spec update.

---

## Pre-implementation investigation (read-only, no code)

### 1. Arc 1 landing verification

Confirm the following exist and are correct:

- `bridge/vapi_bridge/signing_backends/secure_element.py` —
  `SecureElementBackend.__init__()` raises
  `NotImplementedError("Arc 2: requires ATECC608A hardware")`
- `bridge/vapi_bridge/signing_backends/base.py` — `SigningBackend` Protocol
  with `sign()`, `get_pubkey()`, `get_device_id()`, `signing_path()`,
  `backend_type()` methods
- `scripts/provision_device_mfg.py` — exists, has `--execute` flag, calls
  `VAPIManufacturerDeviceRegistry.registerDevice()`
- `contracts/deployed-addresses.json` — contains `VAPIManufacturerDeviceRegistry`
  with address
- `bridge/vapi_bridge/chain.py` — contains `is_path_a()`,
  `is_fully_eligible_path_a()`, `get_device_signing_path()` methods

If any of these are missing or malformed, stop and surface as findings before
proceeding.

### 2. Hardware detection

```bash
pip show cryptoauthlib 2>&1 || echo "NOT_INSTALLED"
python -c "import hid; print([d for d in hid.enumerate() if 'CH34' in str(d.get('product_string',''))])" 2>&1
ls /dev/i2c-* 2>&1  # Linux
# Windows: check Device Manager for CH341 USB-I2C appearing under "Ports" or "USB Serial"
```

Confirm: is `cryptoauthlib` installed? Is the CH341A visible to the OS? What is
the I2C bus number or device path?

### 3. ATECC608A connectivity probe

```python
from cryptoauthlib import *
cfg = cfg_ateccx08a_i2c_default()
cfg.cfg.atcai2c.slave_address = 0xC0
cfg.cfg.atcai2c.bus = 1  # adjust based on finding 2
atcab_init(cfg)
info = bytearray(4)
atcab_info(info)
print("ATECC608A revision:", info.hex())
serial = bytearray(9)
atcab_read_serial_number(serial)
print("Serial:", serial.hex())
atcab_release()
```

Report: does the chip respond? What is the revision and serial number? If
`atcab_init` fails, report the exact error — likely I2C bus number mismatch or
wiring issue.

### 4. Key slot state

```python
zone_locked = AtcaReference(False)
atcab_is_slot_locked(0, zone_locked)
print("Slot 0 locked:", bool(zone_locked))
```

Report: is slot 0 already locked (key exists from a prior session) or blank
(key needs generating)?

### 5. `provision_device_mfg.py` interface

Read `scripts/provision_device_mfg.py`. Confirm: what does it expect the
`SecureElementBackend` to expose? Does it call `get_pubkey()` directly, or does
it load from a separate path? Does it need a `device_id` passed in or does it
read it from the backend? Map the exact call surface so `SecureElementBackend`
satisfies it without changes to the provisioning script.

**Output**: pre-implementation findings note. Confirm hardware is live, chip
responds, call surface is mapped. **Hold for operator review before any code.**

---

## Commit 1 — `SecureElementBackend` implementation

Replace `secure_element.py` stub with full implementation:

```python
from cryptoauthlib import *
from .base import SigningBackend, CompositePubkey, CompositeSignature
from l9_presence.composite_sig import sign as mldsa_sign  # ML-DSA-44 software half

class SecureElementBackend:
    """
    Path A silicon-rooted SigningBackend.
    ECDSA-P256: hardware (ATECC608A, key never leaves silicon).
    ML-DSA-44: software (bridge host). PQ half; not silicon-rooted until Path A v3+.
    """

    def __init__(self, i2c_bus: int = 1, slave_address: int = 0xC0, key_slot: int = 0):
        cfg = cfg_ateccx08a_i2c_default()
        cfg.cfg.atcai2c.slave_address = slave_address
        cfg.cfg.atcai2c.bus = i2c_bus
        status = atcab_init(cfg)
        if status != ATCA_SUCCESS:
            raise RuntimeError(f"ATECC608A init failed: status {status:#04x}")
        self._key_slot = key_slot
        self._device_id = self._read_serial()
        self._pubkey_compressed = self._load_or_generate_pubkey()
        self._mldsa_keypair = self._load_mldsa_keypair()  # ~/.vapi/device_mldsa44_arc2.json

    def _read_serial(self) -> str:
        serial = bytearray(9)
        atcab_read_serial_number(serial)
        return "atecc-" + serial.hex()

    def _load_or_generate_pubkey(self) -> bytes:
        locked = AtcaReference(False)
        atcab_is_slot_locked(self._key_slot, locked)
        pubkey_raw = bytearray(64)  # uncompressed, no 0x04 prefix
        if not bool(locked):
            atcab_genkey(self._key_slot, pubkey_raw)
        else:
            atcab_get_pubkey(self._key_slot, pubkey_raw)
        x = pubkey_raw[:32]
        y = pubkey_raw[32:]
        prefix = b'\x02' if y[-1] % 2 == 0 else b'\x03'
        return prefix + bytes(x)

    def sign(self, digest: bytes, ctx: bytes) -> CompositeSignature:
        assert len(digest) == 32, "digest must be 32 bytes"
        ecdsa_sig = bytearray(64)
        status = atcab_sign(self._key_slot, digest, ecdsa_sig)
        if status != ATCA_SUCCESS:
            raise RuntimeError(f"ATECC608A sign failed: {status:#04x}")
        mldsa_sig = mldsa_sign(self._mldsa_keypair, ctx=ctx, commitment=digest)
        return CompositeSignature(ecdsa_p256_sig=bytes(ecdsa_sig), mldsa44_sig=mldsa_sig)

    def get_pubkey(self) -> CompositePubkey:
        return CompositePubkey(
            ecdsa_p256_compressed=self._pubkey_compressed,
            mldsa44_public=self._mldsa_keypair.public_key
        )

    def get_device_id(self) -> str:
        return self._device_id

    def signing_path(self) -> str:
        return "A"

    def backend_type(self) -> str:
        return "atecc608a"

    def __del__(self):
        try:
            atcab_release()
        except Exception:
            pass
```

> **Arc 2 pre-implementation V-check note (from Arc 1 C1):** the Arc 1
> `CompositeSignature` dataclass landed with field names
> `(blob, ec_p256_sig_der, mldsa44_sig, label)` — DER ECDSA + wire blob, not
> raw `r||s`. The ATECC608A `atcab_sign` API produces raw 64-byte `r||s`. Arc 2
> must either (a) wrap the 64B raw into DER + call `composite_sig.encode_composite`
> to produce a valid `blob`, OR (b) extend `CompositeSignature` with an
> `ec_p256_sig_raw` field. Decision belongs in Arc 2 pre-investigation.

`requirements.txt` / `pyproject.toml` — add `cryptoauthlib>=20240101`.

**Tests** (`bridge/tests/test_secure_element_backend.py`, 6 tests):

- `SecureElementBackend` satisfies `SigningBackend` protocol (structural check)
- `signing_path()` returns `"A"`
- `backend_type()` returns `"atecc608a"`
- `sign()` returns `CompositeSignature` with 64-byte ECDSA half and non-empty
  ML-DSA half
- `get_pubkey()` returns `CompositePubkey` with 33-byte compressed ECDSA-P256
  key
- `get_device_id()` returns string starting with `"atecc-"`

**These tests run against real hardware.** Mark with `@pytest.mark.hardware`
and document in `pytest.ini` that `--hardware` flag is required:
`pytest -m hardware`. CI skips hardware tests; human runs them with hardware
connected.

P-check: `pytest -m hardware` passes (6 tests), `pytest -m "not hardware"` full
suite passes (no regressions), `vapi_invariant_gate --report` 0 violations.
**Hold for operator review before Commit 2.**

---

## Commit 2 — Bridge auto-detection + config wiring

`bridge/vapi_bridge/signing_backends/__init__.py` — add `detect_backend()`:

```python
def detect_backend(config) -> SigningBackend:
    """
    Auto-detect signing backend.
    Path A (SecureElementBackend) if ATECC608A detected on configured I2C bus.
    Path B (HostKeyBackend) otherwise.
    Never silently falls back without logging the reason.
    """
    if config.secure_element_enabled:
        try:
            backend = SecureElementBackend(
                i2c_bus=config.secure_element_i2c_bus,
                slave_address=config.secure_element_i2c_address,
                key_slot=config.secure_element_key_slot
            )
            logger.info(f"[Path A] SecureElementBackend active — device_id={backend.get_device_id()}")
            return backend
        except Exception as e:
            logger.error(f"[Path A] SecureElementBackend failed ({e}); falling back to Path B (HostKeyBackend)")
    backend = HostKeyBackend.load(config.composite_key_path)
    logger.info(f"[Path B] HostKeyBackend active — device_id={backend.get_device_id()}")
    return backend
```

`bridge/vapi_bridge/config.py` — add:

```python
secure_element_enabled: bool = False        # set True when ATECC608A connected
secure_element_i2c_bus: int = 1
secure_element_i2c_address: int = 0xC0
secure_element_key_slot: int = 0
```

`bridge/.env` — document new vars with comments explaining the hardware gate.

`composite_device_identity.py` shim — update to use `detect_backend()`
internally when `secure_element_enabled=True`. Zero change to
`make_reattest_signer()` call signature.

`GET /player/session-status` — `signing_path` field now reads from the live
backend (`"A"` if `SecureElementBackend` active, `"B"` if `HostKeyBackend`).

**Tests** (3 new in `test_signing_backends.py`): `detect_backend()` returns
`HostKeyBackend` when `secure_element_enabled=False`, `detect_backend()`
returns `SecureElementBackend` when enabled + hardware present
(`@pytest.mark.hardware`), fallback to Path B logged correctly when ATECC608A
unavailable.

P-check: full suite, hardware suite, `vapi_invariant_gate --report` 0
violations. **Hold for operator review before Commit 3.**

---

## Commit 3 — End-to-end Path A registration + session-status verification

Execute in sequence:

**Step 1**: Set `SECURE_ELEMENT_ENABLED=true` in `bridge/.env`. Start bridge.
Confirm log shows `[Path A] SecureElementBackend active`.

**Step 2**: Run `provision_device_mfg.py --dry-run` against the live
`SecureElementBackend`. Confirm: device_id reads from chip serial, pubkey reads
from slot 0, `DeviceBirthCertificate` generates correctly with
`signing_path: "A"`.

**Step 3**: Operator authorization for on-chain registration. Run
`provision_device_mfg.py --execute`. This calls
`VAPIManufacturerDeviceRegistry.registerDevice()` on IoTeX testnet. Wallet spend
~0.05–0.1 IOTX (small call, not a deploy). Confirm tx hash, block number.

**Step 4**: Run `verify_device_cert.py`. Confirm: VALID + `isActive()` true
on-chain.

**Step 5**: Call `GET /player/session-status`. Confirm response shows:

```json
"signing_path": "A",
"proof_tier": "FULL",
"controller_model": "CFI-ZCP1",
"path_a_eligible": false  // isFullyEligible() still gated on VHP etc — honest
```

Note: `path_a_eligible` may be false if VHP or other eligibility conditions
aren't met — that's the honest state. `signing_path: "A"` is what matters here.

**Step 6**: Update `docs/path-a-manufacturing-spec.md` §1 to add: "Path A v1
reference implementation demonstrated: ATECC608A + CH341A USB-I2C + QorTroller
bridge. Device `atecc-<serial>` registered on IoTeX testnet at `<tx_hash>`."

Commit message captures: device serial, registration tx hash, block number. The
on-chain anchor is the receipt that Path A v1 works end-to-end.

**Tests** (3 `@pytest.mark.hardware` integration tests):
`provision_device_mfg.py --dry-run` produces valid cert, `verify_device_cert.py`
returns VALID against testnet, session-status `signing_path` is `"A"` when
`SecureElementBackend` active.

P-check: full hardware suite, `vapi_invariant_gate --report`, session-status
confirmed. **Hold for operator review before Commit 4.**

---

## Commit 4 — MEMORY.md + CLAUDE.md + Arc 2 completion sync

**MEMORY.md updates:**

- Arc 2 complete. `SecureElementBackend` live, hardware-tested.
- ATECC608A device serial: `atecc-<serial>` registered in
  `VAPIManufacturerDeviceRegistry` at `<addr>`.
- Registration tx: `<hash>`, block `<N>`, cost `<X>` IOTX.
- `signing_path: "A"` confirmed in session-status.
- Path A v1 honest framing locked: ECDSA-P256 silicon-rooted; ML-DSA-44
  software-computed.
- Arc 3+ (Path A v2): per-PoAC record silicon-root — requires ATECC608A at
  1 kHz cadence (latency study needed) or alternative secure element with
  faster signing.
- `secure_element_enabled=True` in `bridge/.env` to activate Path A.

**CLAUDE.md updates:**

- New phase entry: Path A Arc 2 complete.
- Hardware: ATECC608A breakout + CH341A USB-I2C, both physically connected
  to rig.
- `@pytest.mark.hardware` test suite: run with `pytest -m hardware` when
  hardware connected.
- Arc 3+ (Path A v2) documented as future.

`docs/arc2-completion-report.md` — brief operational record: hardware used,
I2C bus config, chip serial, key slot, registration tx, session-status
confirmed, honesty notes on ML-DSA-44 software half.

No P-check needed. Commit directly.

---

## Honesty rails throughout Arc 2

- `SecureElementBackend` log line on init: `"[Path A] ECDSA-P256 from ATECC608A
  silicon (hardware-rooted). ML-DSA-44 from software (not silicon-rooted —
  Path A v3+)."`
- Session-status `signing_path: "A"` surfaces only when `SecureElementBackend`
  is active — never set manually or faked
- `path_a_eligible: false` is expected and correct if VHP or other eligibility
  conditions aren't satisfied — do not force-pass eligibility to make the demo
  look cleaner
- `provision_device_mfg.py` cert header: `"issuer: QorTroller self-signed
  reference implementation (bridge wallet). Production: hardware HSM ceremony
  required."`
- Hardware tests marked `@pytest.mark.hardware` — CI never runs them against
  missing hardware

**Wallet gate:** Step 3 (Commit 3) requires on-chain registration. Operator
authorization required before `--execute` fires. Estimated: ~0.05–0.1 IOTX.
Well within wallet headroom.

**Arc 3+ note** (documented, not scoped): Per-PoAC record silicon-root at
1000 Hz requires ATECC608A sign latency study (~3ms per sign at I2C 1 MHz =
feasible but needs buffering design). Alternatively: nRF9160 or STM32 with
onboard ECDSA acceleration. Arc 3+ is a separate design pass; do not scope it
here.

Standing by for pre-implementation findings.
