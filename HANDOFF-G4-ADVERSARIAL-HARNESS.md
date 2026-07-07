# G4 Adversarial Harness — Grok Build Handoff (2026-07-06)

## What this is

A complete build spec for the G4 adversarial harness on branch
`feat/l9-consistency-adversarial-harness`. No ambiguity — implement exactly this.

This handoff comes from a scoping session that identified a **pre-existing
verdict-forgery vulnerability** in the SDK, then designed a 12-test harness that
proves the gap and verifies the fix.

---

## Hard constraints (non-negotiable)

- No FROZEN-v1 / PV-CI-pinned / chain / contract / PoAC / `vapi_invariant_gate.py` edits.
- Operator is the single committer. Stage everything, do NOT commit or push.
- No live capture, no daemon, no chain writes (0 IOTX).
- PV-CI stays at 182 (the gate runs `scripts/vapi_invariant_gate.py`; nothing you touch is invariant-pinned).
- The anti-splice invariant stays: B2 alone NEVER opens classification (unrelated but preserved).

---

## Pre-existing gap: verdict-forgery in `is_synchronized()`

**File:** `sdk/vapi_sdk.py` line 10011–10013

**Current (buggy):**
```python
def is_synchronized(self) -> bool:
    """True only when BOTH surfaces present AND BOTH id-verified."""
    return self.verdict == "SYNCHRONIZED"
```

**Problem:** The docstring says "BOTH id-verified" but the implementation only checks
the `verdict` string. A hand-crafted dict `{"verdict": "SYNCHRONIZED", "kas":
{"id_verified": False}, "fusion": {"id_verified": False}}` would pass `is_synchronized()`.
The builder (`l9_presence/posp.py::build_posp()`) is correct — the anti-assertion rail
there is fine. The SDK reader is the gap.

**Fix (exact replacement — one logical expression added):**
```python
def is_synchronized(self) -> bool:
    """True only when BOTH surfaces present AND BOTH id-verified."""
    return (self.verdict == "SYNCHRONIZED"
            and self.kas_id_verified is True
            and self.fusion_id_verified is True)
```

Apply this fix FIRST. The harness tests T-ADV-VERDICT-1 and T-ADV-VERDICT-2 will
fail before the fix and pass after — they are the proof.

---

## Files to create / modify

| File | Action |
|------|--------|
| `sdk/vapi_sdk.py` | EDIT — `is_synchronized()` lines 10011–10013 (fix above) |
| `l9_presence/tests/test_posp_adversarial.py` | CREATE — 12-test adversarial harness |

No other files. Do not touch `l9_presence/posp.py`, `l9_presence/session_identity.py`,
or any existing test file.

---

## The 12-test harness: `l9_presence/tests/test_posp_adversarial.py`

### Imports and setup

```python
"""G4 Adversarial Harness — session-identity nonce properties, anti-splice rail,
verdict-integrity fix, and live-artifact cross-validation.

Four attack layers:
  Layer 1 — Session-identity nonce properties (T-ADV-SID-1..4)
  Layer 2 — Anti-splice rail on build_posp (T-ADV-SPLICE-1..4)
  Layer 3 — Verdict-integrity / is_synchronized() fix (T-ADV-VERDICT-1..2)
  Layer 4 — Live artifact cross-validation (T-ADV-LIVE-1..2)
"""
import hashlib
import json
import pathlib
import pytest

from l9_presence.session_identity import derive_session_id, session_display, parse_daemon_log_name
from l9_presence.posp import build_posp, SYNCHRONIZED, UNVERIFIABLE, PARTIAL_SURFACES
from sdk.vapi_sdk import VAPIPoSPRecord

AUDITS = pathlib.Path(__file__).parents[2] / "audits"
M13_POSP = AUDITS / "posp_record_match13_hdmi_direct_2026-07-06.json"
M11_POSP = AUDITS / "posp_record_match11_kas_validation_2026-07-06.json"
```

---

### Layer 1 — Session-identity nonce properties

```python
# --- Layer 1: Session-identity nonce properties ---

def test_adv_sid_1_determinism():
    """T-ADV-SID-1: derive_session_id is pure — same inputs always yield same id."""
    sid_a = derive_session_id("match13", 1783385280)
    sid_b = derive_session_id("match13", 1783385280)
    assert sid_a == sid_b
    # Cross-check: it is the SHA-256 of the display string
    expected = hashlib.sha256("match13_1783385280".encode("utf-8")).hexdigest()
    assert sid_a == expected


def test_adv_sid_2_adjacent_stamp_uniqueness():
    """T-ADV-SID-2: adjacent stamps (differing by 1 second) produce distinct ids.
    The nonce property holds at 1-second resolution."""
    sid_a = derive_session_id("match", 1783385280)
    sid_b = derive_session_id("match", 1783385281)
    assert sid_a != sid_b


def test_adv_sid_3_log_name_round_trip():
    """T-ADV-SID-3: parse_daemon_log_name -> derive_session_id matches direct derivation.
    The stop-time issuance path and the mint-time path produce identical ids."""
    log = "retina_daemon_match13_hdmi_direct_1783385280.log"
    parsed = parse_daemon_log_name(log)
    assert parsed is not None
    label, stamp = parsed
    sid_from_log = derive_session_id(label, stamp)
    sid_direct = derive_session_id("match13_hdmi_direct", 1783385280)
    assert sid_from_log == sid_direct


def test_adv_sid_4_label_is_load_bearing():
    """T-ADV-SID-4: same stamp, different labels -> distinct ids.
    The label is part of the nonce — not cosmetic."""
    sid_a = derive_session_id("match11", 1783385280)
    sid_b = derive_session_id("match13", 1783385280)
    assert sid_a != sid_b
```

---

### Layer 2 — Anti-splice rail

The build_posp function signature:
```python
build_posp(session_id, session_display, kas_record, fusion_rows, archive_manifest,
           retina_perception_root=None)
```

Where:
- `kas_record` is a dict with keys: `commitment`, `verdict`, `authored_kills`, `events_root`, `session_id` (and `id_verified` in `_surface_id_check` logic)
- `fusion_rows` is a list of dicts with `session_id` key
- `archive_manifest` is a dict with `session_id` key or None

Look at the actual function signature in `l9_presence/posp.py` and match precisely.
The key invariant: if any surface carries a different `session_id` than the wrapper's
`session_id`, `_surface_id_check` returns `False` → verdict must be `UNVERIFIABLE`.

```python
# --- Layer 2: Anti-splice rail ---

def _make_kas(session_id: str, authored_kills: int = 3) -> dict:
    """Minimal KAS record with the required session_id field."""
    return {
        "commitment": "a" * 64,
        "verdict": "VERIFIED_KILLS",
        "authored_kills": authored_kills,
        "events_root": "b" * 64,
        "session_id": session_id,
        "id_verified": True,
    }


def _make_fusion_row(session_id: str) -> dict:
    """Minimal NQPV co-capture row."""
    return {"session_id": session_id, "record_hash_hex": "c" * 64}


def _make_archive(session_id: str) -> dict:
    """Minimal archive manifest."""
    return {"session_id": session_id, "manifest_schema": "qortroller-session-archive-v1",
            "count": 1, "dir": "retina_kf_archive/test"}


def test_adv_splice_1_kas_nqpv_cross_session():
    """T-ADV-SPLICE-1: KAS from session A + NQPV fusion rows from session B -> UNVERIFIABLE.
    The core splice attack — cross-session surface mix must never reach SYNCHRONIZED."""
    sid_a = derive_session_id("session_a", 1000000)
    sid_b = derive_session_id("session_b", 2000000)
    kas = _make_kas(sid_a)
    fusion_rows = [_make_fusion_row(sid_b), _make_fusion_row(sid_b)]
    record = build_posp(sid_a, "session_a_1000000", kas, fusion_rows, None)
    assert record.verdict == UNVERIFIABLE, (
        f"Cross-session surface mix must be UNVERIFIABLE, got {record.verdict}"
    )


def test_adv_splice_2_partial_injection():
    """T-ADV-SPLICE-2: majority rows from session A + ONE row from session B -> UNVERIFIABLE.
    A single foreign row is enough to poison — no majority-vote escape."""
    sid_a = derive_session_id("session_a", 1000000)
    sid_b = derive_session_id("session_b", 2000000)
    kas = _make_kas(sid_a)
    fusion_rows = [_make_fusion_row(sid_a)] * 4 + [_make_fusion_row(sid_b)]
    record = build_posp(sid_a, "session_a_1000000", kas, fusion_rows, None)
    assert record.verdict == UNVERIFIABLE, (
        f"Single foreign fusion row must poison to UNVERIFIABLE, got {record.verdict}"
    )


def test_adv_splice_3_archive_swap():
    """T-ADV-SPLICE-3: correct KAS + correct fusion (session A) + archive from session B -> UNVERIFIABLE.
    Archive mismatch poisons even when both primary surfaces are clean."""
    sid_a = derive_session_id("session_a", 1000000)
    sid_b = derive_session_id("session_b", 2000000)
    kas = _make_kas(sid_a)
    fusion_rows = [_make_fusion_row(sid_a)] * 3
    archive = _make_archive(sid_b)
    record = build_posp(sid_a, "session_a_1000000", kas, fusion_rows, archive)
    assert record.verdict == UNVERIFIABLE, (
        f"Archive session_id mismatch must poison to UNVERIFIABLE, got {record.verdict}"
    )


def test_adv_splice_4_three_way_cross():
    """T-ADV-SPLICE-4: KAS=A, fusion=B, archive=C (three distinct sessions) -> UNVERIFIABLE.
    Poisoning is not order-dependent; any mismatch kills the verdict."""
    sid_a = derive_session_id("session_a", 1000000)
    sid_b = derive_session_id("session_b", 2000000)
    sid_c = derive_session_id("session_c", 3000000)
    kas = _make_kas(sid_a)
    fusion_rows = [_make_fusion_row(sid_b)]
    archive = _make_archive(sid_c)
    record = build_posp(sid_a, "session_a_1000000", kas, fusion_rows, archive)
    assert record.verdict == UNVERIFIABLE, (
        f"Three-way cross-session splice must be UNVERIFIABLE, got {record.verdict}"
    )
```

---

### Layer 3 — Verdict-integrity / `is_synchronized()` fix

These two tests FAIL before the fix and PASS after it. They are the proof of the gap.

```python
# --- Layer 3: Verdict-integrity (is_synchronized() fix) ---

def test_adv_verdict_1_forged_kas_not_verified():
    """T-ADV-VERDICT-1: forged dict claiming SYNCHRONIZED but kas_id_verified=False.
    is_synchronized() MUST return False — the verdict string alone is not a security guarantee.
    FAILS before the sdk/vapi_sdk.py fix; PASSES after."""
    forged = {
        "verdict": "SYNCHRONIZED",
        "session_id": "a" * 64,
        "session_display": "forged_0",
        "device_id": None,
        "span_ms": None,
        "kas": {"commitment": "b" * 64, "verdict": "VERIFIED_KILLS",
                "authored_kills": 5, "id_verified": False},  # <-- FORGED
        "fusion": {"n_rows": 10, "n_id_verified": 10, "record_hashes": [], "id_verified": True},
        "events_roots": {},
        "archive": None,
        "notes": [],
        "schema": "qortroller-posp-v0",
        "advisory": True,
    }
    record = VAPIPoSPRecord.from_dict(forged)
    assert not record.is_synchronized(), (
        "is_synchronized() must return False when kas_id_verified=False, "
        "regardless of the verdict string"
    )


def test_adv_verdict_2_forged_fusion_not_verified():
    """T-ADV-VERDICT-2: forged dict claiming SYNCHRONIZED but fusion_id_verified=False.
    is_synchronized() MUST return False.
    FAILS before the sdk/vapi_sdk.py fix; PASSES after."""
    forged = {
        "verdict": "SYNCHRONIZED",
        "session_id": "a" * 64,
        "session_display": "forged_0",
        "device_id": None,
        "span_ms": None,
        "kas": {"commitment": "b" * 64, "verdict": "VERIFIED_KILLS",
                "authored_kills": 5, "id_verified": True},
        "fusion": {"n_rows": 10, "n_id_verified": 0, "record_hashes": [], "id_verified": False},  # <-- FORGED
        "events_roots": {},
        "archive": None,
        "notes": [],
        "schema": "qortroller-posp-v0",
        "advisory": True,
    }
    record = VAPIPoSPRecord.from_dict(forged)
    assert not record.is_synchronized(), (
        "is_synchronized() must return False when fusion_id_verified=False, "
        "regardless of the verdict string"
    )
```

---

### Layer 4 — Live artifact cross-validation

These use the real committed PoSP artifacts from `audits/`. Skip if files absent
(CI doesn't have them) — but they WILL run locally on the rig.

```python
# --- Layer 4: Live artifact cross-validation ---

@pytest.mark.skipif(not M13_POSP.exists(), reason="M13 PoSP artifact not present (CI)")
def test_adv_live_1_m13_satisfies_predicate():
    """T-ADV-LIVE-1: M13 PoSP artifact (from_file) -> is_synchronized() True.
    The live production artifact from Match 13 (8 authored kills) satisfies the predicate."""
    record = VAPIPoSPRecord.from_file(str(M13_POSP))
    assert record.is_synchronized(), "M13 must be SYNCHRONIZED"
    assert record.kas_id_verified is True
    assert record.fusion_id_verified is True
    assert record.kas_authored_kills == 8
    assert record.n_fusion_rows > 0


@pytest.mark.skipif(
    not M13_POSP.exists() or not M11_POSP.exists(),
    reason="Live PoSP artifacts not present (CI)"
)
def test_adv_live_2_cross_match_session_id_mismatch():
    """T-ADV-LIVE-2: M11 session_id as wrapper + M13 data -> UNVERIFIABLE.
    The join key guards the binding even when both artifacts are genuine SYNCHRONIZED records.
    M11 session_id: c5d9dc3b... ; M13 session_id: 0283fc1e...
    """
    d11 = json.loads(M11_POSP.read_text())
    d13 = json.loads(M13_POSP.read_text())
    sid_11 = d11["session_id"]
    sid_13 = d13["session_id"]
    # Sanity: they must be different (different sessions)
    assert sid_11 != sid_13, "Test premise: M11 and M13 must have distinct session_ids"
    # Build PoSP with M11 wrapper session_id but M13's KAS record (carries M13's session_id)
    kas_m13 = d13["kas"]
    kas_m13["session_id"] = sid_13          # M13 KAS is bound to M13's session_id
    fusion_rows = [{"session_id": sid_13, "record_hash_hex": "0" * 64}]
    record = build_posp(sid_11, "match11_wrapper", kas_m13, fusion_rows, None)
    assert record.verdict == UNVERIFIABLE, (
        f"Cross-match session_id mismatch must be UNVERIFIABLE, got {record.verdict}"
    )
```

---

## Verification commands

Run from the project root `C:\Users\Contr\vapi-pebble-prototype`:

```bash
# 1. Confirm the verdict-forgery tests FAIL before the fix:
python -m pytest l9_presence/tests/test_posp_adversarial.py::test_adv_verdict_1_forged_kas_not_verified l9_presence/tests/test_posp_adversarial.py::test_adv_verdict_2_forged_fusion_not_verified -v

# 2. Apply the is_synchronized() fix to sdk/vapi_sdk.py (lines 10011-10013).

# 3. Run the full harness — all 12 must pass:
python -m pytest l9_presence/tests/test_posp_adversarial.py -v

# 4. Run existing PoSP and SDK tests for regression:
python -m pytest l9_presence/tests/test_posp.py sdk/tests/test_u2b_posp_record.py -v

# 5. PV-CI gate (must exit 0, 182 invariants unchanged):
python scripts/vapi_invariant_gate.py
```

---

## What to stage for operator commit

```bash
git add sdk/vapi_sdk.py l9_presence/tests/test_posp_adversarial.py
```

Do NOT add anything else. Do NOT commit. Hand back to operator.

---

## Commit message (for operator to use)

```
test(l9/g4): adversarial harness — session-identity nonces + anti-splice rail + verdict-forgery fix

Layer 1 (T-ADV-SID-1..4): session_id nonce properties — determinism, adjacent-stamp
uniqueness, log-name round-trip, label load-bearing. Proves the join key has the
structural properties the splice-resistance argument depends on.

Layer 2 (T-ADV-SPLICE-1..4): anti-splice rail on build_posp — KAS×NQPV cross-session,
partial injection (1 foreign row poisons), archive swap, three-way cross. Any cross-session
surface mix produces UNVERIFIABLE; no path to SYNCHRONIZED through mixing.

Layer 3 (T-ADV-VERDICT-1..2): verdict-forgery gap in VAPIPoSPRecord.is_synchronized().
Pre-fix: only checked `self.verdict == "SYNCHRONIZED"` — a forged dict with
`kas_id_verified=False` or `fusion_id_verified=False` would return True. Fixed by adding
`and self.kas_id_verified is True and self.fusion_id_verified is True`. Tests fail before
fix, pass after — the finding and the closure in one commit.

Layer 4 (T-ADV-LIVE-1..2): live artifact cross-validation — M13 PoSP (8 authored kills)
satisfies predicate; cross-pairing M11 session_id with M13 KAS → UNVERIFIABLE.

Finding: G4 harness identified the is_synchronized() verdict-forgery gap pre-existing in
sdk/vapi_sdk.py. Builder (l9_presence/posp.py) was correct throughout — anti-assertion
rail in build_posp() is sound. SDK reader is the fixed surface.

PV-CI 182 unchanged. 0 IOTX. No FROZEN-v1 edit. No chain write.
```

---

## Key code references for Grok

- `l9_presence/session_identity.py` — `derive_session_id`, `parse_daemon_log_name` (Layer 1)
- `l9_presence/posp.py` — `build_posp`, `_surface_id_check`, anti-assertion rail (Layer 2)
- `sdk/vapi_sdk.py` lines 9968–10050 — `VAPIPoSPRecord` dataclass + `is_synchronized()` (fix target)
- `l9_presence/tests/test_posp.py` — existing 6 tests (check for fixture patterns)
- `sdk/tests/test_u2b_posp_record.py` — existing 6 SDK tests (regression baseline)
- `audits/posp_record_match13_hdmi_direct_2026-07-06.json` — M13 live artifact (Layer 4)
- `audits/posp_record_match11_kas_validation_2026-07-06.json` — M11 live artifact (Layer 4)
