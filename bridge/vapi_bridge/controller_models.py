"""Controller model lookup — Path A Arc 1 Commit 4 (D-4B shared module).

Promoted from the inline KNOWN_MODELS dict in scripts/provision_device_mfg.py
so multiple surfaces share one source of truth:

  • scripts/provision_device_mfg.py — uses NAMES + default tiers at ceremony time
  • bridge/vapi_bridge/chain.py     — uses HASHES to reverse-lookup the model
                                       string for GET /player/session-status
  • frontend (future)               — same hashes for any client-side display

VAPIManufacturerDeviceRegistry stores controllerModel as bytes32 = keccak256
(utf8(model_string)). The on-chain blob is one-way; this table is the inverse.

Adding a new model REQUIRES a vapi_invariant_gate.py invariant entry pinning
the (name, default_tier) pair so an off-by-one tier reclassification cannot
ship unnoticed.
"""
from __future__ import annotations

# (name, default_proof_tier) — keccak256(name.encode()) is the on-chain key.
KNOWN_MODELS_LIST = [
    ("CFI-ZCP1", "FULL"),      # Sony DualSense Edge (Path A reference)
    ("CFI-ZCT1", "STANDARD"),  # Sony DualSense (limited adaptive triggers)
]


def _keccak256_utf8(text: str) -> bytes:
    """Same hash the on-chain controllerModel uses. keccak256, not sha256."""
    try:
        from eth_utils import keccak
        return keccak(text=text)
    except ImportError:
        from Crypto.Hash import keccak as _k
        h = _k.new(digest_bits=256)
        h.update(text.encode("utf-8"))
        return h.digest()


# Forward: name → (hash_bytes32, default_tier)
KNOWN_MODELS = {name: (_keccak256_utf8(name), default_tier)
                for name, default_tier in KNOWN_MODELS_LIST}

# Reverse: hash_bytes32 → name (for bridge readback of on-chain controllerModel)
KNOWN_MODELS_BY_HASH = {_keccak256_utf8(name): name
                        for name, _tier in KNOWN_MODELS_LIST}


def name_for_hash(controller_model_b32: bytes) -> str | None:
    """Reverse-lookup the controller model name from its on-chain bytes32.
    Returns None for unknown / zero-padded / corrupted hashes — caller MUST
    surface the None honestly (not a fabricated 'unknown')."""
    if not isinstance(controller_model_b32, (bytes, bytearray)):
        return None
    if len(controller_model_b32) != 32:
        return None
    return KNOWN_MODELS_BY_HASH.get(bytes(controller_model_b32))


def default_tier_for(name: str) -> str | None:
    """Look up the FROZEN default proof tier for a known controller model.
    Returns None for unknown names."""
    entry = KNOWN_MODELS.get(name)
    return entry[1] if entry else None
