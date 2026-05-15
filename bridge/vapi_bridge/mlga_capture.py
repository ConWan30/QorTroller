"""Phase O5-MLGA Stage 2 — MLGA capture pipeline + dataproof primitive.

Mythos Live Gameplay Audit (MLGA) v1 capability — see
wiki/methodology/mlga_architectural_proposal_v1.md.

This module ships the cryptographic dataproof primitive that binds each
gameplay session's observations into a single 32-byte commitment. NOT
an 11th PATTERN-017 commitment family — MLGA is a CAPABILITY tag per
the POSEIDON-BN254-AS reframe precedent (commitment family count stays
10+PDA=11).

FROZEN INVARIANTS (Stream 5 PV-CI ceremony pins these):
    INV-MLGA-DOMAIN-TAG-001     Domain tag b"VAPI-MLGA-SESSION-v1" (20 bytes literal).
    INV-MLGA-CAPABILITY-NOT-FAMILY-001  Capability registered in _KNOWN_CAPABILITY_TAGS
                                        in mythos_variants.py; NOT in _PATTERN_017_FROZEN_TAGS.
    INV-MLGA-DATAPROOF-PREIMAGE-001  Byte layout FROZEN at:
        tag(20) || start_ts_ns(8) || end_ts_ns(8) || n_poac(8) ||
        n_r2(4) || n_l2(4) || apop_summary(32) || bt_observability(1) ||
        gic_advances(4) = 89 bytes preimage → 32 bytes output.

Usage pattern (operator-runtime):

    from vapi_bridge.mlga_capture import (
        compute_mlga_session_dataproof,
        record_mlga_session,
    )

    # Called at session end (player closes NCAA CFB 26 or stops gameplay):
    dataproof = compute_mlga_session_dataproof(
        session_start_ts_ns=session.start_ts_ns,
        session_end_ts_ns=time.time_ns(),
        n_poac_records=session.n_records,
        n_trigger_pulls_r2=session.n_r2,
        n_trigger_pulls_l2=session.n_l2,
        apop_state_counts=session.apop_counts,  # dict
        bt_observability=session.bt_observed,    # 0/1/2 byte
        gic_advances_in_session=session.gic_delta,
    )
    record_mlga_session(store=store, session=session, dataproof=dataproof)

Wallet-free; READ-ONLY against chain (no anchor); writes only to local
SQLite mlga_session_log table.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict


# ----- FROZEN constants (Stream 5 PV-CI ceremony pins) -----

#: Domain tag (20 bytes). Distinguishes MLGA session dataproofs from
#: every PATTERN-017 commitment family + every other capability tag.
#: Width MUST stay 20; new MLGA versions get a separate tag.
MLGA_SESSION_DOMAIN_TAG: bytes = b"VAPI-MLGA-SESSION-v1"
assert len(MLGA_SESSION_DOMAIN_TAG) == 20, (
    "MLGA_SESSION_DOMAIN_TAG must be 20 bytes"
)

#: BT observability byte values FROZEN.
MLGA_BT_NOT_OBSERVED: int = 0x00       # no BT dongle / no scan attempted
MLGA_BT_OBSERVED: int = 0x01           # BT seen during session (RSSI samples captured)
MLGA_BT_HELD_PLACED_IDENTIFIED: int = 0x02  # held-vs-placed transition observed


# ----- Result dataclass -----

@dataclass(slots=True)
class MLGASessionResult:
    """Slotted record of one gameplay session's MLGA capture state."""
    session_id: str                    # human-readable session identifier
    session_start_ts_ns: int
    session_end_ts_ns: int
    n_poac_records: int
    n_trigger_pulls_r2: int
    n_trigger_pulls_l2: int
    apop_state_counts: Dict[str, int] = field(default_factory=dict)
    bt_observability: int = 0
    gic_advances_in_session: int = 0
    dataproof_hex: str = ""
    error: str = ""


# ----- Commitment primitive -----

def _canonical_apop_summary(apop_state_counts: Dict[str, int]) -> bytes:
    """SHA-256 of canonical-JSON-sorted APOP state counts dict.

    Stream 1 callers MUST pass a dict whose keys are the 5 FROZEN APOP
    state values per Phase 241-APOP. Empty dict → SHA-256 of "{}".
    Canonical JSON: sort_keys=True, separators=(",", ":"), ensure_ascii=False.
    """
    if apop_state_counts is None:
        apop_state_counts = {}
    canonical = json.dumps(
        apop_state_counts,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).digest()


def compute_mlga_session_dataproof(
    *,
    session_start_ts_ns: int,
    session_end_ts_ns: int,
    n_poac_records: int,
    n_trigger_pulls_r2: int,
    n_trigger_pulls_l2: int,
    apop_state_counts: Dict[str, int],
    bt_observability: int = MLGA_BT_NOT_OBSERVED,
    gic_advances_in_session: int = 0,
) -> bytes:
    """Compute the FROZEN MLGA session dataproof (32 bytes).

    FROZEN byte layout (INV-MLGA-DATAPROOF-PREIMAGE-001):
        SHA-256(
            MLGA_SESSION_DOMAIN_TAG (20 B) ||
            session_start_ts_ns (8 B; uint64 big-endian) ||
            session_end_ts_ns (8 B) ||
            n_poac_records (8 B; uint64) ||
            n_trigger_pulls_r2 (4 B; uint32) ||
            n_trigger_pulls_l2 (4 B; uint32) ||
            apop_summary (32 B; SHA-256 of canonical-JSON sorted dict) ||
            bt_observability (1 B; uint8) ||
            gic_advances_in_session (4 B; uint32)
        ) = 89 B preimage → 32 B output

    Validates input bounds + raises ValueError on overflow / negative.
    """
    # Bounds checks (uint64 for ts_ns + n_poac; uint32 for triggers + GIC)
    for name, val, width in (
        ("session_start_ts_ns",       session_start_ts_ns,       64),
        ("session_end_ts_ns",         session_end_ts_ns,         64),
        ("n_poac_records",            n_poac_records,            64),
        ("n_trigger_pulls_r2",        n_trigger_pulls_r2,        32),
        ("n_trigger_pulls_l2",        n_trigger_pulls_l2,        32),
        ("gic_advances_in_session",   gic_advances_in_session,   32),
    ):
        if not isinstance(val, int) or val < 0:
            raise ValueError(f"{name}: expected non-negative int, got {val!r}")
        if val >= (1 << width):
            raise ValueError(f"{name}: overflow uint{width} ({val})")

    if not isinstance(bt_observability, int) or not 0 <= bt_observability <= 0xFF:
        raise ValueError(
            f"bt_observability: expected uint8 (0..255), got {bt_observability!r}"
        )
    if bt_observability not in (
        MLGA_BT_NOT_OBSERVED,
        MLGA_BT_OBSERVED,
        MLGA_BT_HELD_PLACED_IDENTIFIED,
    ):
        raise ValueError(
            f"bt_observability: must be one of the 3 FROZEN values "
            f"(0x00/0x01/0x02), got 0x{bt_observability:02x}"
        )

    if session_end_ts_ns < session_start_ts_ns:
        raise ValueError(
            f"session_end_ts_ns ({session_end_ts_ns}) < "
            f"session_start_ts_ns ({session_start_ts_ns}): "
            "end must be >= start"
        )

    apop_summary = _canonical_apop_summary(apop_state_counts)
    assert len(apop_summary) == 32

    preimage = (
        MLGA_SESSION_DOMAIN_TAG
        + session_start_ts_ns.to_bytes(8, "big")
        + session_end_ts_ns.to_bytes(8, "big")
        + n_poac_records.to_bytes(8, "big")
        + n_trigger_pulls_r2.to_bytes(4, "big")
        + n_trigger_pulls_l2.to_bytes(4, "big")
        + apop_summary
        + bt_observability.to_bytes(1, "big")
        + gic_advances_in_session.to_bytes(4, "big")
    )
    assert len(preimage) == 20 + 8 + 8 + 8 + 4 + 4 + 32 + 1 + 4 == 89

    return hashlib.sha256(preimage).digest()


def record_mlga_session(*, store, session: MLGASessionResult) -> int:
    """Persist one MLGA session record to mlga_session_log. Returns row id;
    0 on UNIQUE collision (idempotent — same session_id + dataproof already
    recorded). Fail-open: returns 0 on DB error, never raises."""
    try:
        return int(store.insert_mlga_session(
            session_id=session.session_id,
            session_start_ts_ns=session.session_start_ts_ns,
            session_end_ts_ns=session.session_end_ts_ns,
            n_poac_records=session.n_poac_records,
            n_trigger_pulls_r2=session.n_trigger_pulls_r2,
            n_trigger_pulls_l2=session.n_trigger_pulls_l2,
            apop_state_counts_json=json.dumps(
                session.apop_state_counts,
                sort_keys=True,
                separators=(",", ":"),
            ),
            bt_observability=session.bt_observability,
            gic_advances_in_session=session.gic_advances_in_session,
            dataproof_hex=session.dataproof_hex,
        ))
    except Exception:  # noqa: BLE001 — fail-open
        return 0
