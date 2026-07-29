"""Core types for the attestation loop.

ChannelSnapshot: A point-in-time read from all attestation channels.
AttestationEnvelope: The cryptographic bundle that binds all channels together.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List


@dataclass
class ChannelSnapshot:
    """Point-in-time read from all attestation channels.

    All fields are Optional — a channel returns None if it's not
    configured, not available, or has never produced output.
    The ticker handles missing channels gracefully.
    """

    tick: int = 0
    timestamp: float = 0.0
    session_id: str = ""

    # ── Hardware ────────────────────────────────────────
    hardware: Optional[Dict[str, Any]] = None
    """HardwareWatcher.last_state — dualshock, capture, bridge status."""

    # ── Controller ──────────────────────────────────────
    controller: Optional[Dict[str, Any]] = None
    """ProtocolState.bridge_health() — PoAC state, agent statuses."""

    # ── Biometrics ──────────────────────────────────────
    biometrics: Optional[Dict[str, Any]] = None
    """ReflexConcierge.assess_operator_state() — PoEP separation ratio."""

    # ── Dual-lobe retina ────────────────────────────────
    retina: Optional[Dict[str, Any]] = None
    """ScreenRetinaFusion.last_analysis() — person detection, landmarks."""

    # ── VLM third lobe ──────────────────────────────────
    vlm: Optional[Dict[str, Any]] = None
    """RetinaVisualOracle.last_observation() — scene description, text."""

    # ── FSCA ────────────────────────────────────────────
    contradictions: Optional[List[Dict[str, Any]]] = None
    """ContradictionOracle.active_contradictions() — rule violations."""

    # ── PV-CI ────────────────────────────────────────────
    invariants: Optional[Dict[str, Any]] = None
    """InvariantSentinel.summary() — invariant check results."""


@dataclass
class AttestationEnvelope:
    """Cryptographic bundle binding all channels for a single tick.

    Each channel is hashed independently, then a cross-modal hash
    binds all channel hashes together. The envelope_hash is the
    final binding that can be KAS-signed.
    """

    tick: int
    timestamp: float
    session_id: str

    # ── Channel hashes ──────────────────────────────────
    channel_hashes: Dict[str, str] = field(default_factory=dict)
    """SHA-256 hash of each channel's payload.
    Key: channel name (poac, poep, retina, vlm, fsca, pv_ci).
    Value: hex digest of the channel payload."""

    # ── Cross-modal binding ─────────────────────────────
    cross_modal_hash: str = ""
    """SHA-256(channel_hashes values concatenated in sorted key order).
    Binds every channel to every other channel for this tick."""

    # ── Integrity fingerprints ──────────────────────────
    pv_ci_fingerprint: str = ""
    """Fingerprint of the invariant check. Empty if PV-CI not available."""

    # ── Final hash chain ────────────────────────────────
    envelope_hash: str = ""
    """SHA-256(tick | timestamp | session_id | cross_modal_hash |
    pv_ci_fingerprint | previous_envelope_hash).
    The previous_envelope_hash chains ticks together."""

    previous_envelope_hash: str = ""
    """Hash of the previous tick's envelope. Empty for tick 0."""

    # ── Serialization ───────────────────────────────────
    raw: Dict[str, Any] = field(default_factory=dict)
    """Full JSON-serializable dict for database storage."""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dict for storage."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AttestationEnvelope":
        """Deserialize from a dict."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})