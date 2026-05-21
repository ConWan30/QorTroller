"""QorTroller L9 — Proof of Causal Presence (PoCP) commitment (CANDIDATE, design-only).

A FROZEN-SAFE, PARALLEL commitment over one session's L9 causal-presence evidence.
It does NOT touch the 228-byte PoAC wire format, the chain link hash, or any
registered PATTERN-017 / FROZEN-v1 primitive. It is a v0 CANDIDATE living in the
standalone l9_presence package — intended to become the artifact Sentry anchors on
AdjudicationRegistry once gate-2 (biometric separability) passes and the primitive
is taken through governance. Until then it is a local, reproducible digest only.

Preimage (deterministic, OS-independent integer encoding — floats scaled to milli
big-endian ints, exactly as the project encodes ratios as milliratio):
  domain(21) || player_h(32) || session_h(32) || coupling_milli(4) || lag_ms(4)
  || negctrl_milli(4) || decoupled_milli(4) || n_samples(4) || ts_ns(8)
-> SHA-256 -> 32-byte commitment (hex).

STATUS: design-only candidate. NOT a registered protocol primitive; not in the
PV-CI allowlist; not anchored. v0 = pre-governance.
"""
from __future__ import annotations

import hashlib

_DOMAIN = b"QORTROLLER-L9-POCP-v0"
_U32_MAX = 2 ** 31 - 1


def _u(x: int, n: int) -> bytes:
    return int(x).to_bytes(n, "big", signed=False)


def _milli(x: float) -> int:
    """Scale a [0,1]-ish float to a clamped non-negative milli integer."""
    return max(0, min(_U32_MAX, int(round(float(x) * 1000.0))))


def _h32(s: str) -> bytes:
    return hashlib.sha256(s.encode("utf-8")).digest()


def compute_pocp_commitment(*, player: str, session_id: str, coupling: float,
                            lag_ms: float, negative_control: float,
                            decoupled_energy: float, n_samples: int,
                            ts_ns: int) -> str:
    """Return the 32-byte PoCP commitment (hex) for one session's evidence.
    Reproducible by any third party holding the same feature values."""
    pre = (
        _DOMAIN
        + _h32(player) + _h32(session_id)
        + _u(_milli(coupling), 4)
        + _u(max(0, min(_U32_MAX, int(round(lag_ms)))), 4)
        + _u(_milli(negative_control), 4)
        + _u(_milli(decoupled_energy), 4)
        + _u(max(0, min(_U32_MAX, int(n_samples))), 4)
        + _u(int(ts_ns) & (2 ** 64 - 1), 8)
    )
    return hashlib.sha256(pre).hexdigest()


def preimage_len() -> int:
    """Expected preimage byte length (drift guard): 21+32+32+4+4+4+4+4+8 = 113."""
    return len(_DOMAIN) + 32 + 32 + 4 + 4 + 4 + 4 + 4 + 8
