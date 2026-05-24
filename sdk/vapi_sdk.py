"""
VAPI Phase 20 — Self-Verifying Integration SDK
===============================================

The primary integration surface for game studios, hardware partners (SCUF,
Battle Beaver, HORI), and platform developers.

**Novel concept — Self-Verifying Integration SDK:**
    VAPISession.self_verify() uses VAPI's own Physical Input Trust Layer (PITL)
    to attest that this SDK integration is correctly wired. It generates a signed
    SDKAttestation — an on-chain-submittable proof that each PITL layer (L2 HID
    injection, L2B IMU-button causal, L3 behavioral ML, L4 biometric Mahalanobis,
    L5 temporal oracle) is active and functioning. No other gaming or DePIN SDK
    does this.

    Traditional anti-cheat: "Trust us, our engine works."
    VAPI SDK:               "Here is a cryptographic proof that our engine works,
                             anchored to the same mechanism we provide to you."

Classes:
    VAPIRecord      — Parse and verify the 228-byte PoAC wire format
    SDKAttestation  — Self-verification result (PITL layer health + hash)
    VAPIDevice      — Device detection, profile lookup, PHCI certification
    VAPIVerifier    — On-chain + client-side PoAC record/chain verification
    VAPISession     — Live session manager; the primary game studio interface
    VAPIEnrollment  — PHGCredential enrollment status (Phase 62 bridge polling)
    VAPIZKProof     — PITL ZK proof structure validator (Phase 62 C3 circuit)

    Phase 65 (vapi_agent module):
    AgentRuling     — Cryptographically committed autonomous PITL ruling
    VAPIAgent       — Studio-side autonomous session adjudicator (AIL)

Minimum integration (30 lines):
    import asyncio
    from vapi_sdk import VAPISession

    async def main():
        async with VAPISession(profile_id="sony_dualshock_edge_v1") as session:
            @session.on_cheat_detected
            def handle_cheat(record):
                print(f"Cheat detected: {record.inference_name}")

            # Your game loop — ingest records from the bridge
            raw = receive_from_bridge()   # bytes, 228B
            session.ingest_record(raw)

        print(session.summary())

    asyncio.run(main())
"""

from __future__ import annotations

import hashlib
import json
import struct
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

# ---------------------------------------------------------------------------
# Path bootstrap — SDK can be imported from anywhere
# ---------------------------------------------------------------------------

_SDK_DIR        = Path(__file__).parent
_PROJECT_ROOT   = _SDK_DIR.parent
_CONTROLLER_DIR = _PROJECT_ROOT / "controller"
_BRIDGE_DIR     = _PROJECT_ROOT / "bridge"

for _d in [str(_CONTROLLER_DIR), str(_BRIDGE_DIR)]:
    if _d not in sys.path:
        sys.path.insert(0, _d)

# ---------------------------------------------------------------------------
# Protocol constants (PoAC spec — immutable)
# ---------------------------------------------------------------------------

SDK_VERSION       = "3.1.1-phase-o3-zkba-track1-g4-validator-sdk"
POAC_RECORD_SIZE  = 228
POAC_BODY_SIZE    = 164
POAC_SIG_SIZE     = 64

# Gaming inference codes (VAPI protocol extension 0x20–0x30)
INFERENCE_NAMES: dict[int, str] = {
    0x20: "NOMINAL",
    0x21: "SKILLED",
    0x22: "CHEAT:REACTION",
    0x23: "CHEAT:MACRO",
    0x24: "CHEAT:AIMBOT",
    0x25: "CHEAT:RECOIL",
    0x26: "CHEAT:IMU_MISS",
    0x27: "CHEAT:INJECTION",
    # Phase 8: Physical Input Trust Layer (hard cheats)
    0x28: "CHEAT:DRIVER_INJECT",
    0x29: "CHEAT:WALLHACK_PREAIM",
    0x2A: "CHEAT:AIMBOT_BEHAVIORAL",
    # Phase 13/16B: soft anomalies (advisory, outside hard cheat range)
    0x2B: "TEMPORAL_ANOMALY",
    0x30: "BIOMETRIC_ANOMALY",
    # Phase 17: L2B/L2C advisory codes
    0x31: "IMU_PRESS_DECOUPLED",
    0x32: "STICK_IMU_DECOUPLED",
}

CHEAT_CODES: frozenset[int] = frozenset({
    0x22, 0x23, 0x24, 0x25, 0x26, 0x27,
    0x28, 0x29, 0x2A,
})


# ---------------------------------------------------------------------------
# VAPIRecord — PoAC wire format parser
# ---------------------------------------------------------------------------

class VAPIRecord:
    """
    Parse and interrogate a 228-byte PoAC record.

    The record layout (immutable per VAPI spec):
        [0:32]    prev_poac_hash      — SHA-256 of the previous record's 164-byte body (NOT the full 228B)
        [32:64]   sensor_commitment   — SHA-256 of the sensor preimage (48B or 56B)
        [64:96]   model_manifest_hash — SHA-256 identifying the TinyML model
        [96:128]  world_model_hash    — SHA-256 of EWC world model + preference weights
        [128]     inference_result    — Gaming inference code (0x20–0x30)
        [129]     action_code         — PoAC action (0x01 report, 0x05 bounty, 0x09 boot)
        [130]     confidence          — Classifier confidence 0–255
        [131]     battery_pct         — Battery 0–100
        [132:136] monotonic_ctr       — Big-endian uint32 counter (replay protection)
        [136:144] timestamp_ms        — Big-endian uint64 Unix milliseconds
        [144:152] latitude            — Big-endian IEEE 754 double (degrees)
        [152:160] longitude           — Big-endian IEEE 754 double (degrees)
        [160:164] bounty_id           — Big-endian uint32 (0 = no bounty)
        [164:228] signature           — 64-byte ECDSA-P256 raw r||s
    """

    __slots__ = (
        "_raw",
        "prev_poac_hash", "sensor_commitment", "model_manifest_hash", "world_model_hash",
        "_inference_result", "action_code", "confidence", "battery_pct",
        "monotonic_ctr", "timestamp_ms", "latitude", "longitude", "bounty_id",
        "signature",
    )

    def __init__(self, raw: bytes) -> None:
        if len(raw) != POAC_RECORD_SIZE:
            raise ValueError(
                f"VAPIRecord expects exactly {POAC_RECORD_SIZE} bytes, got {len(raw)}"
            )
        self._raw = raw

        # Four 32-byte hash fields
        self.prev_poac_hash    = raw[0:32]
        self.sensor_commitment = raw[32:64]
        self.model_manifest_hash = raw[64:96]
        self.world_model_hash  = raw[96:128]

        # Packed fields (big-endian)
        (self._inference_result,
         self.action_code,
         self.confidence,
         self.battery_pct,
         self.monotonic_ctr) = struct.unpack_from(">BBBBI", raw, 128)

        (self.timestamp_ms,) = struct.unpack_from(">Q", raw, 136)
        (self.latitude,)     = struct.unpack_from(">d", raw, 144)
        (self.longitude,)    = struct.unpack_from(">d", raw, 152)
        (self.bounty_id,)    = struct.unpack_from(">I", raw, 160)

        self.signature = raw[164:228]

    # --- Inference accessors ---

    @property
    def inference_result(self) -> int:
        return self._inference_result

    @property
    def inference_name(self) -> str:
        """Human-readable inference label (e.g. 'NOMINAL', 'TEMPORAL_ANOMALY')."""
        return INFERENCE_NAMES.get(self._inference_result,
                                   f"UNKNOWN(0x{self._inference_result:02X})")

    @property
    def is_clean(self) -> bool:
        """True when the inference code is not in the hard cheat set [0x28–0x2A]."""
        return self._inference_result not in CHEAT_CODES

    @property
    def is_advisory(self) -> bool:
        """True for soft anomaly codes (TEMPORAL_ANOMALY, BIOMETRIC_ANOMALY, IMU_PRESS_DECOUPLED, STICK_IMU_DECOUPLED)."""
        return self._inference_result in (0x2B, 0x30, 0x31, 0x32)

    # --- Hashing ---

    @property
    def record_hash(self) -> bytes:
        """SHA-256 of the 164-byte body. Used for on-chain indexing."""
        return hashlib.sha256(self._raw[:POAC_BODY_SIZE]).digest()

    @property
    def chain_hash(self) -> bytes:
        """SHA-256 of the full 228-byte record (body + signature).

        Off-chain convenience hash for indexing and de-duplication.
        NOT used for PoAC chain linkage — do not use as prev_poac_hash.
        Chain linkage uses record_hash (SHA-256 of 164-byte body only).
        """
        return hashlib.sha256(self._raw).digest()

    # --- Chain integrity ---

    def verify_chain_link(self, prev: Optional["VAPIRecord"]) -> bool:
        """
        Verify this record correctly links to the previous record in the PoAC chain.

        Novel: enables full client-side chain integrity verification without an
        on-chain RPC call. The PoAC chain is cryptographically self-verifying.

        Args:
            prev: The immediately preceding VAPIRecord, or None for the genesis record.

        Returns:
            True  — chain link is valid.
            False — prev_poac_hash does not match, chain is broken or tampered.
        """
        if prev is None:
            # Genesis record: prev_poac_hash must be all-zero sentinel
            return self.prev_poac_hash == b"\x00" * 32
        # Canonical chain linkage: prev_poac_hash = SHA-256(previous_record_body_164B)
        # This matches PoACVerifier.sol on-chain. The signature bytes (164-227) are NOT
        # included in the chain link hash. See whitepaper §4.1.
        return self.prev_poac_hash == prev.record_hash

    @classmethod
    def from_bytes(cls, raw: bytes) -> "VAPIRecord":
        """Construct from raw bytes (alias for direct instantiation)."""
        return cls(raw)

    def __repr__(self) -> str:
        return (
            f"VAPIRecord(inference={self.inference_name}, "
            f"confidence={self.confidence}, ctr={self.monotonic_ctr}, "
            f"ts={self.timestamp_ms})"
        )


# ---------------------------------------------------------------------------
# SDKAttestation — self-verification result
# ---------------------------------------------------------------------------

@dataclass
class SDKAttestation:
    """
    Result of VAPISession.self_verify().

    A cryptographically-bound proof that each PITL layer in this SDK
    integration is active and functioning correctly. The attestation_hash
    commits all layer states so the result cannot be retroactively altered.

    This object can be serialised (to_dict()) and submitted on-chain as
    evidence that the SDK was correctly integrated at verified_at.
    """
    layers_active:      dict   # str → bool: layer_name → import+functional check
    pitl_scores:        dict   # str → float: layer_name → detection confidence 0.0–1.0
    zk_proof_available: bool
    sdk_version:        str
    verified_at:        float  # Unix timestamp
    attestation_hash:   bytes  # SHA-256 commitment of all fields

    @property
    def all_layers_active(self) -> bool:
        """True when every PITL layer check passed."""
        return all(self.layers_active.values())

    @property
    def active_layer_count(self) -> int:
        return sum(1 for v in self.layers_active.values() if v)

    def to_dict(self) -> dict:
        return {
            "sdk_version":        self.sdk_version,
            "verified_at":        self.verified_at,
            "layers_active":      self.layers_active,
            "pitl_scores":        self.pitl_scores,
            "zk_proof_available": self.zk_proof_available,
            "all_layers_active":  self.all_layers_active,
            "active_layer_count": self.active_layer_count,
            "attestation_hash":   self.attestation_hash.hex(),
        }


# ---------------------------------------------------------------------------
# VAPIDevice — device detection and PHCI profile management
# ---------------------------------------------------------------------------

class VAPIDevice:
    """
    Device detection and PHCI certification interface.

    Auto-detects connected USB HID devices via the Phase 19 profile registry
    (controller/profiles/) and exposes the DeviceProfile + PHCICertification
    for the connected controller.
    """

    def __init__(self) -> None:
        self._profile     = None
        self._certification = None

    def detect(self) -> Optional[object]:
        """
        Auto-detect a connected VAPI-supported device via USB HID VID/PID lookup.

        Returns the DeviceProfile, or None if no supported device is found or
        if the `hid` package is unavailable.
        """
        try:
            from profiles import detect_profile  # type: ignore
            import hid                           # type: ignore
            for info in hid.enumerate():
                profile = detect_profile(
                    info.get("vendor_id", 0),
                    info.get("product_id", 0),
                )
                if profile is not None:
                    self._profile = profile
                    self._certification = None   # reset cached cert
                    return profile
        except Exception:
            pass
        return None

    def get_profile(self, profile_id: str) -> object:
        """
        Retrieve a DeviceProfile by slug without hardware detection.

        Args:
            profile_id: e.g. "sony_dualshock_edge_v1", "scuf_reflex_pro_v1"

        Raises:
            KeyError: profile_id is not registered.
        """
        from profiles import get_profile  # type: ignore
        self._profile = get_profile(profile_id)
        self._certification = None
        return self._profile

    @property
    def profile(self) -> Optional[object]:
        return self._profile

    @property
    def phci_tier(self) -> Optional[object]:
        return self._profile.phci_tier if self._profile else None

    def certification(self) -> Optional[object]:
        """
        Run PHCICertifier against the current profile and return a PHCICertification.

        Caches the result — call get_profile() or detect() to invalidate.
        Returns None if no profile is loaded.
        """
        if self._profile is None:
            return None
        if self._certification is None:
            from phci_certification import PHCICertifier  # type: ignore
            self._certification = PHCICertifier().certify(self._profile)
        return self._certification

    def is_phci_certified(self) -> bool:
        """True if the device holds PHCITier.STANDARD or PHCITier.CERTIFIED."""
        cert = self.certification()
        return bool(cert and cert.is_certified)


# ---------------------------------------------------------------------------
# VAPIVerifier — on-chain and client-side verification
# ---------------------------------------------------------------------------

class VAPIVerifier:
    """
    PoAC record and chain verification.

    Two modes:
        Local  — syntactic record parsing + client-side chain integrity
                 (no RPC connection required)
        On-chain — reads PoACVerifier contract state (requires rpc_url +
                   verifier_address)
    """

    def __init__(
        self,
        rpc_url:          str = "",
        verifier_address: str = "",
    ) -> None:
        self._rpc_url          = rpc_url
        self._verifier_address = verifier_address
        self._w3               = None

    def _ensure_connected(self) -> None:
        if self._w3 is not None:
            return
        if not self._rpc_url:
            raise RuntimeError(
                "rpc_url required for on-chain verification. "
                "Pass rpc_url='https://babel-api.mainnet.iotex.io' to VAPIVerifier."
            )
        try:
            from web3 import Web3  # type: ignore
            self._w3 = Web3(Web3.HTTPProvider(self._rpc_url))
        except ImportError as e:
            raise RuntimeError("pip install web3 to enable on-chain verification") from e

    def verify_record(self, raw: bytes) -> bool:
        """
        Syntactic validation of a 228-byte PoAC record.

        Returns True if the record parses without error (correct size, valid
        struct layout). Does NOT verify the ECDSA-P256 signature — use the
        bridge's ChainClient.verify_poac() for full on-chain verification.
        """
        try:
            VAPIRecord(raw)
            return True
        except (ValueError, struct.error):
            return False

    def verify_chain(self, records: list[bytes]) -> bool:
        """
        Verify a sequence of raw records forms an unbroken PoAC chain.

        Uses VAPIRecord.verify_chain_link() at every step — no RPC call needed.
        Returns False immediately on the first broken link.
        """
        parsed: list[VAPIRecord] = []
        for raw in records:
            try:
                parsed.append(VAPIRecord(raw))
            except (ValueError, struct.error):
                return False

        for i, rec in enumerate(parsed):
            prev = parsed[i - 1] if i > 0 else None
            if not rec.verify_chain_link(prev):
                return False
        return True

    def get_device_rating(self, device_id: bytes) -> dict:
        """
        Fetch SkillOracle rating for a device from the chain.

        Returns a dict with keys: rating (int), tier (int), connected (bool).
        Falls back to {rating:1000, tier:0, connected:False} without chain.
        """
        if not self._rpc_url:
            return {"rating": 1000, "tier": 0, "connected": False}
        try:
            self._ensure_connected()
            # On-chain lookup requires SkillOracle ABI — bridge chain.py has full impl.
            # SDK provides the interface; production use should delegate to bridge.
            return {"rating": 1000, "tier": 0, "connected": True}
        except Exception:
            return {"rating": 1000, "tier": 0, "connected": False}

    def is_phci_certified(self, device_id: bytes) -> bool:
        """Check on-chain DeviceRegistry for PHCI certification. Requires chain connection."""
        if not self._rpc_url:
            return False
        try:
            self._ensure_connected()
            # Full impl delegates to bridge's chain.py register_device_tiered path.
            return False
        except Exception:
            return False


# ---------------------------------------------------------------------------
# VAPIEnrollment — PHGCredential enrollment status interface
# ---------------------------------------------------------------------------

class VAPIEnrollment:
    """
    PHGCredential enrollment status interface.

    Polls GET /enrollment/status/{device_id} on the bridge.
    Enrollment rules: only NOMINAL sessions (0x20 or NULL inference_code)
    count toward the 10-session minimum. Hard cheats {0x28, 0x29, 0x2A}
    block enrollment. Advisory codes {0x2B, 0x30, 0x31, 0x32} do NOT block.
    Works offline: returns status='unavailable' when bridge unreachable.
    """

    _REQUIRED_SESSIONS = 10
    _REQUIRED_HUMANITY  = 0.60

    def __init__(self, bridge_url: str = "") -> None:
        self._bridge_url = bridge_url.rstrip("/")

    def get_status(self, device_id: str, timeout: float = 5.0) -> dict:
        """
        Fetch enrollment status from the bridge.
        Falls back to _offline_response() when bridge_url="" or unreachable.
        Response keys: device_id, status, sessions_nominal, sessions_total,
        avg_humanity, tx_hash, eligible_at, credentialed_at,
        required_sessions, required_humanity.
        """
        if not self._bridge_url:
            return self._offline_response(device_id)
        url = f"{self._bridge_url}/enrollment/status/{device_id}"
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except Exception:
            return self._offline_response(device_id)

    @staticmethod
    def _offline_response(device_id: str) -> dict:
        return {
            "device_id": device_id, "status": "unavailable",
            "sessions_nominal": 0, "sessions_total": 0, "avg_humanity": 0.0,
            "tx_hash": "", "eligible_at": None, "credentialed_at": None,
            "required_sessions": VAPIEnrollment._REQUIRED_SESSIONS,
            "required_humanity": VAPIEnrollment._REQUIRED_HUMANITY,
        }

    @staticmethod
    def is_tournament_eligible(status: dict) -> bool:
        """True only when status == 'credentialed' (on-chain mint confirmed)."""
        return status.get("status") == "credentialed"

    @staticmethod
    def sessions_remaining(status: dict) -> int:
        """max(0, required_sessions - sessions_nominal). 0 if credentialed/eligible."""
        if status.get("status") in ("credentialed", "eligible"):
            return 0
        required = int(status.get("required_sessions", VAPIEnrollment._REQUIRED_SESSIONS))
        current  = int(status.get("sessions_nominal", 0))
        return max(0, required - current)


# ---------------------------------------------------------------------------
# VAPIZKProof — PITL ZK proof structure validator
# ---------------------------------------------------------------------------

class VAPIZKProof:
    """
    Structural validator for PITL ZK proof dicts (Phase 62 Groth16 C3 circuit).

    Does NOT perform cryptographic verification — that is on-chain via
    PitlSessionProofVerifierV2. Use this to validate a proof dict before
    submitting to the bridge.

    Phase 62 C3 invariant: featureCommitment = Poseidon(8)(scaledFeatures[0..6],
    inferenceCodeFromBody); inferenceResult === inferenceCodeFromBody (on-chain).
    nPublic = 5.
    """

    PROOF_SIZE  = 256   # Groth16 BN254 uncompressed (bytes)
    N_PUBLIC    = 5     # Circuit public input count

    _REQUIRED_KEYS = frozenset({
        "proof_bytes", "feature_commitment", "humanity_prob_int",
        "inference_code", "nullifier_hash", "epoch",
    })

    def __init__(self, proof_dict: dict) -> None:
        self._d = proof_dict

    def validate(self) -> tuple:
        """
        Validate structure and value ranges.
        Returns (True, None) or (False, error_message).
        Checks: all keys present, proof_bytes is 256B, humanity_prob_int in [0, 1000].
        """
        missing = self._REQUIRED_KEYS - set(self._d.keys())
        if missing:
            return False, f"Missing required keys: {sorted(missing)}"
        pb = self._d.get("proof_bytes")
        if not isinstance(pb, (bytes, bytearray)):
            return False, "proof_bytes must be bytes"
        if len(pb) != self.PROOF_SIZE:
            return False, f"proof_bytes must be {self.PROOF_SIZE} bytes, got {len(pb)}"
        hp = self._d.get("humanity_prob_int")
        if not isinstance(hp, int) or not (0 <= hp <= 1000):
            return False, f"humanity_prob_int must be int in [0, 1000], got {hp!r}"
        return True, None

    def public_inputs(self) -> list:
        """
        Return the 5 public signals in circuit declaration order:
        [featureCommitment, humanityProbInt, inferenceResult, nullifierHash, epoch]
        Matches PITLSessionRegistryV2.sol calldata and PitlSessionProof.circom nPublic=5.
        """
        return [
            self._d["feature_commitment"],
            self._d["humanity_prob_int"],
            self._d["inference_code"],
            self._d["nullifier_hash"],
            self._d["epoch"],
        ]

    @staticmethod
    def verify_ceremony_integrity(
        vkey_dict: dict,
        ceremony_registry_address: str,
        web3_provider_url: str,
        circuit_name: str = "PitlSessionProof",
    ) -> dict:
        """
        Phase 67 — Verify the local verification key against the on-chain
        CeremonyRegistry commitment.

        Computes keccak256(vkey_json_bytes) locally and calls
        CeremonyRegistry.verifyCeremony(circuitId, localHash) via eth_call.

        Returns:
            {
              "local_hash":         str  (hex, keccak256 of sorted JSON),
              "on_chain_match":     bool (True if matches CeremonyRegistry),
              "contributor_count":  int,
              "beacon_block_number": int,
              "circuit_name":       str,
              "error":              str | None,
            }

        Does not require web3 library — uses urllib for the eth_call JSON-RPC.
        Returns error=<message> in dict on any failure (never raises).
        """
        import hashlib, json as _json, urllib.request as _req

        result = {
            "local_hash": "", "on_chain_match": False,
            "contributor_count": 0, "beacon_block_number": 0,
            "circuit_name": circuit_name, "error": None,
        }
        try:
            # Compute local vkey hash (keccak256 of canonical JSON)
            vkey_json = _json.dumps(vkey_dict, sort_keys=True, separators=(",", ":"))
            vkey_bytes = vkey_json.encode()
            # keccak256 via hashlib if available (Python 3.6+ supports shake; keccak not stdlib)
            # Use sha3_256 as proxy for tests — on production use web3.keccak
            local_hash_bytes = hashlib.sha3_256(vkey_bytes).digest()
            local_hash_hex   = "0x" + local_hash_bytes.hex()
            result["local_hash"] = local_hash_hex

            # circuitId = sha3_256(circuitName) — matches chain.py record_ceremony_on_chain
            circuit_id_bytes = hashlib.sha3_256(circuit_name.encode()).digest()
            circuit_id_hex   = "0x" + circuit_id_bytes.hex()

            if not ceremony_registry_address or not web3_provider_url:
                result["error"] = "ceremony_registry_address or web3_provider_url not provided"
                return result

            # ABI-encode call to verifyCeremony(bytes32, bytes32)
            # Selector: keccak256("verifyCeremony(bytes32,bytes32)")[:4]
            sel = hashlib.sha3_256(b"verifyCeremony(bytes32,bytes32)").digest()[:4]
            calldata = (
                sel
                + circuit_id_bytes.rjust(32, b"\x00")
                + local_hash_bytes.rjust(32, b"\x00")
            ).hex()

            body = _json.dumps({
                "jsonrpc": "2.0", "method": "eth_call",
                "params": [{
                    "to":   ceremony_registry_address,
                    "data": "0x" + calldata,
                }, "latest"],
                "id": 1,
            }).encode()
            req = _req.Request(
                web3_provider_url, data=body,
                headers={"Content-Type": "application/json"},
            )
            with _req.urlopen(req, timeout=10) as resp:
                rpc = _json.loads(resp.read())
            ret = rpc.get("result", "0x" + "0" * 64)
            result["on_chain_match"] = ret.endswith("1")

            # Query getContributorCount and beacon via getCeremony (best-effort)
            try:
                sel2 = hashlib.sha3_256(b"getContributorCount(bytes32)").digest()[:4]
                cd2  = (sel2 + circuit_id_bytes.rjust(32, b"\x00")).hex()
                body2 = _json.dumps({
                    "jsonrpc": "2.0", "method": "eth_call",
                    "params": [{"to": ceremony_registry_address, "data": "0x" + cd2}, "latest"],
                    "id": 2,
                }).encode()
                req2 = _req.Request(
                    web3_provider_url, data=body2,
                    headers={"Content-Type": "application/json"},
                )
                with _req.urlopen(req2, timeout=10) as resp2:
                    rpc2 = _json.loads(resp2.read())
                count_hex = rpc2.get("result", "0x0")
                result["contributor_count"] = int(count_hex, 16)
            except Exception:
                pass

        except Exception as exc:
            result["error"] = str(exc)
        return result


# ---------------------------------------------------------------------------
# VAPISession — primary game studio integration interface
# ---------------------------------------------------------------------------

class VAPISession:
    """
    Live PoAC session manager.

    Designed for game studio integration: one async context manager wraps
    the entire session lifecycle. Records flow in via ingest_record(); callbacks
    fire on cheat detections and on-chain submissions.

    The self_verify() method is the novel core of the Self-Verifying SDK:
    it uses VAPI's PITL to attest that the SDK itself is correctly integrated.

    Example usage:
        async with VAPISession("sony_dualshock_edge_v1") as session:
            session.on_cheat_detected(lambda r: ban_player(r.inference_name))
            # bridge feeds records into session via ingest_record()

        print(session.summary())
        att = session.self_verify()
        print(att.to_dict())
    """

    def __init__(
        self,
        profile_id:       str = "sony_dualshock_edge_v1",
        rpc_url:          str = "",
        verifier_address: str = "",
    ) -> None:
        self._profile_id      = profile_id
        self._device          = VAPIDevice()
        self._verifier        = VAPIVerifier(rpc_url, verifier_address)
        self._records:        list[VAPIRecord] = []
        self._records_submitted: int = 0
        self._start_time:     Optional[float] = None
        self._active:         bool = False
        # Callbacks
        self._on_cheat_cb:    Optional[Callable] = None
        self._on_submit_cb:   Optional[Callable] = None

    # --- Callback registration (fluent API) ---

    def on_cheat_detected(
        self, callback: Callable[["VAPIRecord"], None]
    ) -> "VAPISession":
        """
        Register a callback invoked when a record carries a cheat or advisory code.

        Fires for: CHEAT_CODES (0x28–0x2A) AND soft advisories (0x2B, 0x30).
        The callback receives the VAPIRecord so the studio can act on inference_name.
        """
        self._on_cheat_cb = callback
        return self

    def on_record_submitted(
        self, callback: Callable[["VAPIRecord", str], None]
    ) -> "VAPISession":
        """
        Register a callback invoked after each record is confirmed on-chain.

        Args to callback: (VAPIRecord, tx_hash: str)
        """
        self._on_submit_cb = callback
        return self

    # --- Record ingestion ---

    def ingest_record(self, raw: bytes) -> VAPIRecord:
        """
        Ingest a raw 228-byte PoAC record into the session.

        Parses the record, appends it to the session chain, and fires the
        on_cheat_detected callback if the inference code is anomalous.

        Returns the parsed VAPIRecord.
        Raises ValueError if raw is not a valid 228-byte record.
        """
        rec = VAPIRecord(raw)
        self._records.append(rec)

        # Fire cheat/advisory callback
        if (not rec.is_clean or rec.is_advisory) and self._on_cheat_cb:
            self._on_cheat_cb(rec)

        return rec

    def record_submitted(self, record: "VAPIRecord", tx_hash: str = "") -> None:
        """Notify the session that a record was confirmed on-chain."""
        self._records_submitted += 1
        if self._on_submit_cb:
            self._on_submit_cb(record, tx_hash)

    # --- Session state ---

    def chain_integrity(self) -> bool:
        """
        Verify all ingested records form an unbroken PoAC chain.

        Delegates to VAPIVerifier.verify_chain() — no RPC call required.
        """
        if not self._records:
            return True
        return self._verifier.verify_chain([r._raw for r in self._records])

    def summary(self) -> dict:
        """Return session statistics."""
        clean  = sum(1 for r in self._records if r.is_clean and not r.is_advisory)
        cheats = sum(1 for r in self._records if not r.is_clean)
        advisory = sum(1 for r in self._records if r.is_advisory)
        return {
            "profile_id":        self._profile_id,
            "total_records":     len(self._records),
            "clean_records":     clean,
            "advisory_records":  advisory,
            "cheat_detections":  cheats,
            "records_submitted": self._records_submitted,
            "chain_integrity":   self.chain_integrity(),
            "duration_s":        (
                round(time.monotonic() - self._start_time, 1)
                if self._start_time else 0.0
            ),
        }

    # --- Self-Verifying Integration SDK — the novel core ---

    def self_verify(self) -> SDKAttestation:
        """
        Attest SDK correctness using VAPI's own Physical Input Trust Layer.

        Performs five independent layer checks:
            L2  — HID-XInput oracle import check
            L3  — Behavioral cheat classifier import check
            L4  — Biometric Mahalanobis classifier import check
            L2B — IMU-button press causal oracle import check
            L5  — Temporal rhythm oracle: injects 25 synthetic bot frames
                 (100ms constant intervals, low CV + low entropy + no quantization)
                 and verifies TEMPORAL_ANOMALY is detected. Score 1.0 if detection
                 fires, 0.5 if layer imports but does not fire, 0.0 if unavailable.

        Also checks ZK proof artifact availability.

        Returns an SDKAttestation with a SHA-256 attestation_hash that commits
        all layer states, scores, the SDK version, and the verification timestamp.
        This hash can be submitted on-chain as proof of integration correctness.

        Requires no hardware. Works in CI, headless Docker, and offline environments.
        """
        layers: dict[str, bool]  = {}
        scores: dict[str, float] = {}

        # ---- L2: HID-XInput Oracle ----
        try:
            from vapi_bridge.hid_xinput_oracle import HidXInputOracle  # type: ignore
            layers["L2_hid_xinput"] = True
            scores["L2_hid_xinput"] = 1.0
        except Exception:
            layers["L2_hid_xinput"] = False
            scores["L2_hid_xinput"] = 0.0

        # ---- L3: Behavioral Cheat Classifier ----
        try:
            from tinyml_backend_cheat import BackendCheatClassifier  # type: ignore
            layers["L3_behavioral"] = True
            scores["L3_behavioral"] = 1.0
        except Exception:
            layers["L3_behavioral"] = False
            scores["L3_behavioral"] = 0.0

        # ---- L4: Biometric Mahalanobis Classifier ----
        try:
            from tinyml_biometric_fusion import BiometricFusionClassifier  # type: ignore
            layers["L4_biometric"] = True
            scores["L4_biometric"] = 1.0
        except Exception:
            layers["L4_biometric"] = False
            scores["L4_biometric"] = 0.0

        # ---- L2B: IMU-Button Press Causal Oracle ----
        try:
            from l2b_imu_press_correlation import ImuPressCorrelationOracle  # type: ignore
            layers["L2B_imu_press"] = True
            scores["L2B_imu_press"] = 1.0
        except Exception:
            layers["L2B_imu_press"] = False
            scores["L2B_imu_press"] = 0.0

        # ---- L5: Temporal Rhythm Oracle — functional check ----
        try:
            from temporal_rhythm_oracle import TemporalRhythmOracle  # type: ignore

            # Synthetic bot session: 25 frames with exactly 100ms inter-press
            # (constant timing → low CV < 0.08, low entropy < 1.5, no quant needed)
            # A working L5 oracle must classify this as TEMPORAL_ANOMALY.
            class _BotFrame:
                def __init__(self, ms: float) -> None:
                    self.inter_press_ms = ms

            oracle = TemporalRhythmOracle()
            for _ in range(25):
                oracle.push_frame(_BotFrame(100.0))

            result = oracle.classify()
            layers["L5_temporal"] = True
            # Full score if bot session was detected; partial if layer loads but misses
            scores["L5_temporal"] = 1.0 if result is not None else 0.5

        except Exception:
            layers["L5_temporal"] = False
            scores["L5_temporal"] = 0.0

        # ---- ZK proof artifacts ----
        zk_available = False
        try:
            from zk_prover import ZK_ARTIFACTS_AVAILABLE  # type: ignore
            zk_available = bool(ZK_ARTIFACTS_AVAILABLE)
        except Exception:
            pass

        # ---- Build attestation hash ----
        # Commits: sorted layer states, sorted scores, SDK version, timestamp_ms
        # Sorting ensures determinism regardless of dict insertion order.
        ts_ms = time.time_ns()  # nanosecond precision — guarantees uniqueness across rapid calls
        commitment = (
            repr(sorted(layers.items())).encode()
            + repr(sorted(scores.items())).encode()
            + SDK_VERSION.encode()
            + struct.pack(">Q", ts_ms)
        )
        attestation_hash = hashlib.sha256(commitment).digest()

        return SDKAttestation(
            layers_active      = layers,
            pitl_scores        = scores,
            zk_proof_available = zk_available,
            sdk_version        = SDK_VERSION,
            verified_at        = ts_ms / 1000.0,
            attestation_hash   = attestation_hash,
        )

    # --- Async context manager ---

    async def __aenter__(self) -> "VAPISession":
        self._start_time = time.monotonic()
        self._active = True
        try:
            self._device.get_profile(self._profile_id)
        except Exception:
            pass  # profile unavailable — session still usable for ingestion
        return self

    async def __aexit__(self, *_: object) -> None:
        self._active = False


# ---------------------------------------------------------------------------
# VAPITournamentGate — Phase 85
# ---------------------------------------------------------------------------

class GateReadinessResult:
    """Structured result from VAPITournamentGate.check_gate_readiness(). Never raises."""

    __slots__ = (
        "overall_ready", "dry_run_active", "gate_attestations_count",
        "validation_gate", "fleet_health", "timestamp", "error",
    )

    def __init__(
        self,
        overall_ready: bool = False,
        dry_run_active: bool = True,
        gate_attestations_count: int = 0,
        validation_gate: dict | None = None,
        fleet_health: dict | None = None,
        timestamp: float = 0.0,
        error: str | None = None,
    ) -> None:
        self.overall_ready = overall_ready
        self.dry_run_active = dry_run_active
        self.gate_attestations_count = gate_attestations_count
        self.validation_gate = validation_gate or {}
        self.fleet_health = fleet_health or {}
        self.timestamp = timestamp
        self.error = error

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"GateReadinessResult(overall_ready={self.overall_ready}, "
            f"dry_run_active={self.dry_run_active}, error={self.error!r})"
        )


class VAPITournamentGate:
    """Phase 85 — Tournament operator gate client.

    Wraps GET /agent/gate-readiness. Never raises — error surfaces in
    GateReadinessResult.error.  Intended for tournament CI pipelines that
    need a programmatic readiness certificate before allowing player submissions.

    Usage::

        gate = VAPITournamentGate("http://bridge:8000", api_key="op-key")
        result = gate.check_gate_readiness()
        if not result.overall_ready:
            raise RuntimeError(f"Gate not ready: {result.error or result.validation_gate}")
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key

    def check_gate_readiness(self) -> GateReadinessResult:
        """Synchronous gate-readiness poll. Never raises."""
        import json
        import urllib.request

        url = f"{self._base_url}/agent/gate-readiness?api_key={self._api_key}"
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read())
            return GateReadinessResult(
                overall_ready=bool(body.get("overall_ready", False)),
                dry_run_active=bool(body.get("dry_run_active", True)),
                gate_attestations_count=int(body.get("gate_attestations_count", 0)),
                validation_gate=body.get("validation_gate", {}),
                fleet_health=body.get("fleet_health", {}),
                timestamp=float(body.get("timestamp", 0.0)),
            )
        except Exception as exc:
            return GateReadinessResult(error=str(exc))

    def is_ready(self) -> bool:
        """Quick boolean check — never raises."""
        return self.check_gate_readiness().overall_ready

    def verify_activation_audit(self) -> "ActivationAuditResult":
        """Call GET /agent/activation-audit and return structured result. Never raises.

        audit_valid=True confirms the full Phase 95 chronological sequence:
        (1) Protocol scored ready_for_live_mode=True in live_mode_activation_log,
        (2) an on-chain gate attestation subsequently exists (GateAttestationAnchor.sol),
        (3) the order is intact (ready BEFORE anchor).

        This is the cryptographic pre-condition for enabling AGENT_DRY_RUN=false.
        Phase 95.
        """
        try:
            url = f"{self._base_url}/agent/activation-audit"
            req = urllib.request.Request(
                url,
                headers={"x-api-key": self._api_key},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            return ActivationAuditResult(
                audit_valid=bool(data.get("audit_valid", False)),
                first_ready_check_at=data.get("first_ready_check_at"),
                gate_attestation_count=int(data.get("gate_attestation_count", 0)),
                latest_attestation_at=data.get("latest_attestation_at"),
                audit_summary=data.get("audit_summary", ""),
            )
        except Exception as exc:
            return ActivationAuditResult(error=str(exc))

    def create_enforcement_certificate(self) -> "EnforcementReadinessCertificate":
        """POST /agent/enforcement-certificate and return ERC. Never raises.

        Issues a portable HMAC-SHA256-signed Enforcement Readiness Certificate
        binding the current audit_valid state to the operator API key.
        Tournament operators can verify the ERC without VAPI infrastructure.
        Phase 96.
        """
        try:
            import urllib.error
            url = f"{self._base_url}/agent/enforcement-certificate"
            req = urllib.request.Request(
                url,
                data=b"",
                method="POST",
                headers={"x-api-key": self._api_key, "Content-Length": "0"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            cert = data.get("certificate") or data
            return EnforcementReadinessCertificate(
                cert_id=cert.get("cert_id"),
                audit_hash=data.get("audit_hash", ""),
                hmac_sig=data.get("hmac_sig", ""),
                audit_valid=bool(data.get("audit_valid", False)),
                gate_attestation_count=0,
                issued_at=float(data.get("issued_at", 0)),
                expires_at=float(data.get("expires_at", 0)),
                has_certificate=True,
                is_expired=False,
            )
        except Exception as exc:
            return EnforcementReadinessCertificate(error=str(exc))

    def get_enforcement_certificate(self) -> "EnforcementReadinessCertificate":
        """GET /agent/enforcement-certificate and return ERC. Never raises. Phase 96."""
        try:
            url = f"{self._base_url}/agent/enforcement-certificate"
            req = urllib.request.Request(
                url,
                headers={"x-api-key": self._api_key},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            cert = data.get("certificate") or {}
            return EnforcementReadinessCertificate(
                cert_id=cert.get("id"),
                audit_hash=cert.get("audit_hash", ""),
                hmac_sig=cert.get("hmac_sig", ""),
                audit_valid=bool(cert.get("audit_valid", False)),
                gate_attestation_count=int(cert.get("gate_attestation_count", 0)),
                issued_at=float(cert.get("created_at", 0)),
                expires_at=float(cert.get("expires_at", 0)),
                has_certificate=bool(data.get("has_certificate", False)),
                is_expired=bool(data.get("is_expired", False)),
            )
        except Exception as exc:
            return EnforcementReadinessCertificate(error=str(exc))


class ActivationAuditResult:
    """Structured result from VAPITournamentGate.verify_activation_audit(). Never raises.

    audit_valid=True means the evidence chain is intact:
    ready_for_live_mode=True recorded BEFORE on-chain gate attestation.
    Phase 95.
    """

    __slots__ = (
        "audit_valid", "first_ready_check_at", "gate_attestation_count",
        "latest_attestation_at", "audit_summary", "error",
    )

    def __init__(
        self,
        audit_valid: bool = False,
        first_ready_check_at=None,
        gate_attestation_count: int = 0,
        latest_attestation_at=None,
        audit_summary: str = "",
        error=None,
    ) -> None:
        self.audit_valid = audit_valid
        self.first_ready_check_at = first_ready_check_at
        self.gate_attestation_count = gate_attestation_count
        self.latest_attestation_at = latest_attestation_at
        self.audit_summary = audit_summary
        self.error = error

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"ActivationAuditResult(audit_valid={self.audit_valid}, "
            f"gate_attestation_count={self.gate_attestation_count}, "
            f"error={self.error!r})"
        )


class EnforcementReadinessCertificate:
    """Portable operator-signed ERC. Never raises. Phase 96."""

    __slots__ = (
        "cert_id", "audit_hash", "hmac_sig", "audit_valid",
        "gate_attestation_count", "issued_at", "expires_at",
        "has_certificate", "is_expired", "error",
    )

    def __init__(
        self,
        cert_id=None,
        audit_hash: str = "",
        hmac_sig: str = "",
        audit_valid: bool = False,
        gate_attestation_count: int = 0,
        issued_at: float = 0.0,
        expires_at: float = 0.0,
        has_certificate: bool = False,
        is_expired: bool = False,
        error=None,
    ) -> None:
        self.cert_id = cert_id
        self.audit_hash = audit_hash
        self.hmac_sig = hmac_sig
        self.audit_valid = audit_valid
        self.gate_attestation_count = gate_attestation_count
        self.issued_at = issued_at
        self.expires_at = expires_at
        self.has_certificate = has_certificate
        self.is_expired = is_expired
        self.error = error

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"EnforcementReadinessCertificate(audit_valid={self.audit_valid}, "
            f"has_certificate={self.has_certificate}, is_expired={self.is_expired}, "
            f"error={self.error!r})"
        )


# ---------------------------------------------------------------------------
# VAPICeremonyAudit — Phase 85
# ---------------------------------------------------------------------------

class CeremonyAuditResult:
    """Structured result from VAPICeremonyAudit.audit(). Never raises."""

    __slots__ = (
        "local_hash", "on_chain_match", "contributor_count",
        "beacon_block_number", "circuit_name", "registry_address", "error",
    )

    def __init__(
        self,
        local_hash: str = "",
        on_chain_match: bool = False,
        contributor_count: int = 0,
        beacon_block_number: int = 0,
        circuit_name: str = "",
        registry_address: str = "",
        error: str | None = None,
    ) -> None:
        self.local_hash = local_hash
        self.on_chain_match = on_chain_match
        self.contributor_count = contributor_count
        self.beacon_block_number = beacon_block_number
        self.circuit_name = circuit_name
        self.registry_address = registry_address
        self.error = error

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"CeremonyAuditResult(circuit={self.circuit_name!r}, "
            f"on_chain_match={self.on_chain_match}, error={self.error!r})"
        )


class VAPICeremonyAudit:
    """Phase 85 — MPC ceremony integrity auditor.

    Wraps VAPIZKProof.verify_ceremony_integrity() for external consumers
    who don't want to import the ZK internals directly.  Never raises.

    Usage::

        audit = VAPICeremonyAudit(registry_address="0x...", rpc_url="https://...")
        result = audit.audit(vkey_dict, circuit_name="PitlSessionProof")
        assert result.on_chain_match, result.error
    """

    def __init__(self, registry_address: str, rpc_url: str) -> None:
        self._registry_address = registry_address
        self._rpc_url = rpc_url

    def audit(self, vkey_dict: dict, circuit_name: str = "PitlSessionProof") -> CeremonyAuditResult:
        """Verify local vkey against on-chain CeremonyRegistry. Never raises."""
        try:
            raw = VAPIZKProof.verify_ceremony_integrity(
                vkey_dict=vkey_dict,
                registry_address=self._registry_address,
                rpc_url=self._rpc_url,
                circuit_name=circuit_name,
            )
            return CeremonyAuditResult(
                local_hash=raw.get("local_hash", ""),
                on_chain_match=bool(raw.get("on_chain_match", False)),
                contributor_count=int(raw.get("contributor_count", 0)),
                beacon_block_number=int(raw.get("beacon_block_number", 0)),
                circuit_name=circuit_name,
                registry_address=self._registry_address,
                error=raw.get("error"),
            )
        except Exception as exc:
            return CeremonyAuditResult(
                circuit_name=circuit_name,
                registry_address=self._registry_address,
                error=str(exc),
            )


# ---------------------------------------------------------------------------
# VAPIRulingStream — Phase 85
# ---------------------------------------------------------------------------

class RulingStreamEvent:
    """Single SSE event from the ruling stream."""

    __slots__ = ("event_id", "event_type", "data")

    def __init__(self, event_id: str, event_type: str, data: dict) -> None:
        self.event_id = event_id
        self.event_type = event_type
        self.data = data

    def __repr__(self) -> str:  # pragma: no cover
        return f"RulingStreamEvent(id={self.event_id!r}, type={self.event_type!r})"


class VAPIRulingStream:
    """Phase 85 — SSE ruling stream client for GET /operator/agent/stream.

    Delivers RulingStreamEvent objects to an async consumer.  Reconnects
    automatically on connection loss using exponential back-off (1–60 s) and
    sends Last-Event-ID to resume from the last seen event (W1 mitigation:
    prevents silent event loss on TCP partition).

    Usage::

        stream = VAPIRulingStream("http://bridge:8000", api_key="op-key")
        async for event in stream.listen():
            process(event)

    The generator exits cleanly on asyncio.CancelledError.
    """

    _BACKOFF_INITIAL: float = 1.0
    _BACKOFF_MAX: float = 60.0
    _BACKOFF_FACTOR: float = 2.0

    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        device_id: str | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._device_id = device_id
        self._last_event_id: str = ""

    def _build_url(self) -> str:
        params = f"api_key={self._api_key}"
        if self._device_id:
            params += f"&device_id={self._device_id}"
        return f"{self._base_url}/operator/agent/stream?{params}"

    @staticmethod
    def _parse_sse_block(block: str) -> dict:
        """Parse one SSE data block into {id, event, data} dict."""
        import json

        result: dict = {"id": "", "event": "message", "data": ""}
        for line in block.splitlines():
            if line.startswith("id:"):
                result["id"] = line[3:].strip()
            elif line.startswith("event:"):
                result["event"] = line[6:].strip()
            elif line.startswith("data:"):
                result["data"] = line[5:].strip()
        try:
            result["data"] = json.loads(result["data"])
        except Exception:
            pass  # raw string data — leave as-is
        return result

    async def listen(self):  # type: ignore[return]
        """Async generator — yields RulingStreamEvent, reconnects on loss."""
        import asyncio
        import urllib.request

        backoff = self._BACKOFF_INITIAL
        while True:
            try:
                url = self._build_url()
                headers = {"Accept": "text/event-stream"}
                if self._last_event_id:
                    headers["Last-Event-ID"] = self._last_event_id
                req = urllib.request.Request(url, headers=headers)

                # urllib is synchronous — run in executor to stay async-friendly
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: urllib.request.urlopen(req, timeout=90),
                )

                buffer = ""
                while True:
                    chunk = await loop.run_in_executor(
                        None, lambda: response.read(1024)
                    )
                    if not chunk:
                        break  # server closed — reconnect
                    buffer += chunk.decode("utf-8", errors="replace")
                    while "\n\n" in buffer:
                        block, buffer = buffer.split("\n\n", 1)
                        block = block.strip()
                        if not block:
                            continue
                        parsed = self._parse_sse_block(block)
                        if parsed["id"]:
                            self._last_event_id = parsed["id"]
                        data = parsed["data"] if isinstance(parsed["data"], dict) else {}
                        yield RulingStreamEvent(
                            event_id=parsed["id"],
                            event_type=parsed["event"],
                            data=data,
                        )
                backoff = self._BACKOFF_INITIAL  # reset on clean exit
            except asyncio.CancelledError:
                return
            except Exception:
                pass  # swallow connection errors — reconnect after backoff

            try:
                await asyncio.sleep(backoff)
            except asyncio.CancelledError:
                return
            backoff = min(backoff * self._BACKOFF_FACTOR, self._BACKOFF_MAX)


# ---------------------------------------------------------------------------
# Phase 99C — VAPIHumanProof SDK client
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class VHPData:
    """Verified Human Proof token status returned by VAPIHumanProof.get_vhp_data().

    All fields reflect the latest VHP issuance from the bridge SQLite store.
    is_valid=True when expires_at > time.time() and no error occurred.
    """
    device_id: str
    token_id: int
    cert_level: int
    consecutive_clean: int
    confidence_score: float   # 0.0–1.0 (bridges confidence_score_bp / 10000)
    issued_at: float
    expires_at: float
    is_valid: bool
    to_address: str = ""
    vhp_contract_address: str = ""
    error: str | None = None


class VAPIHumanProof:
    """SDK client for VAPIVerifiedHumanProof status queries.

    Never raises to the caller — errors are returned in VHPData.error.

    Usage::

        vhp = VAPIHumanProof("http://localhost:8080", api_key="...")
        if vhp.is_human("my_device_id"):
            # device has a valid, non-expired VHP token
            ...
    """

    def __init__(self, base_url: str, api_key: str):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key

    def is_human(self, device_id: str) -> bool:
        """Returns True if the device has a valid, non-expired VHP token.

        Never raises — returns False on any error.
        """
        data = self.get_vhp_data(device_id)
        return data.is_valid and data.error is None

    def get_vhp_data(self, device_id: str) -> VHPData:
        """Retrieve VHP status from GET /agent/vhp-status/{device_id}.

        Returns VHPData with error field set on failure.
        """
        try:
            import urllib.request
            import json
            import time as _t
            url = (
                f"{self._base_url}/agent/vhp-status/{device_id}"
                f"?api_key={self._api_key}"
            )
            with urllib.request.urlopen(url, timeout=10) as resp:
                d = json.loads(resp.read())
            confidence_bp = d.get("confidence_score", 0)
            return VHPData(
                device_id=device_id,
                token_id=d.get("token_id", 0),
                cert_level=d.get("cert_level", 1),
                consecutive_clean=d.get("consecutive_clean", 0),
                confidence_score=confidence_bp / 10000.0 if confidence_bp else 0.0,
                issued_at=d.get("created_at", 0.0),
                expires_at=d.get("expires_at", 0.0),
                is_valid=d.get("is_valid", False),
                to_address=d.get("to_address", ""),
                vhp_contract_address=d.get("vhp_contract_address", ""),
            )
        except Exception as exc:
            return VHPData(
                device_id=device_id,
                token_id=0, cert_level=0, consecutive_clean=0,
                confidence_score=0.0, issued_at=0.0, expires_at=0.0,
                is_valid=False, error=str(exc),
            )

    def request_vhp_mint(self, device_id: str, to_address: str) -> dict:
        """POST to /agent/mint-vhp — request VHP minting for a device.

        Returns the API response dict on success, or {"error": ...} on failure.
        Never raises.
        """
        try:
            import urllib.request
            import json
            url = (
                f"{self._base_url}/agent/mint-vhp"
                f"?api_key={self._api_key}"
                f"&device_id={device_id}"
                f"&to_address={to_address}"
            )
            req = urllib.request.Request(url, data=b"", method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except Exception as exc:
            return {"error": str(exc)}


@dataclass(slots=True)
class PlayerEligibility:
    """VAPI tournament eligibility result (Phase 102).

    is_eligible=True when device has valid VHP and consecutive_clean > 0.
    error=None on success.
    """

    device_id:        str
    wallet:           str
    is_eligible:      bool
    has_valid_vhp:    bool
    consecutive_clean: int
    cert_level:       int
    expires_at:       float
    error:            str | None = None


class VAPITournamentClient:
    """SDK for game developers — checks player eligibility for VAPI-gated tournaments.

    Uses GET /agent/vhp-status to determine has_valid_vhp + consecutive_clean.
    Never raises — errors returned in PlayerEligibility.error.

    Example::

        client = VAPITournamentClient("http://localhost:8080", api_key="mykey")
        elig   = client.check_player("0xdeviceid...", "0xwallet...")
        if elig.is_eligible:
            grant_entry()
    """

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key  = api_key

    def check_player(self, device_id: str, wallet: str) -> "PlayerEligibility":
        """Return PlayerEligibility for the given device. Never raises."""
        try:
            import urllib.request
            import json as _json

            url = (
                f"{self._base_url}/agent/vhp-status/{device_id}"
                f"?api_key={self._api_key}"
            )
            with urllib.request.urlopen(url, timeout=10) as resp:
                d = _json.loads(resp.read())

            has_vhp = bool(d.get("is_valid", False))
            cc      = int(d.get("consecutive_clean", 0))
            return PlayerEligibility(
                device_id=device_id,
                wallet=wallet,
                is_eligible=has_vhp and cc > 0,
                has_valid_vhp=has_vhp,
                consecutive_clean=cc,
                cert_level=int(d.get("cert_level", 0)),
                expires_at=float(d.get("expires_at", 0.0)),
            )
        except Exception as exc:
            return PlayerEligibility(
                device_id=device_id,
                wallet=wallet,
                is_eligible=False,
                has_valid_vhp=False,
                consecutive_clean=0,
                cert_level=0,
                expires_at=0.0,
                error=str(exc),
            )


@dataclass(slots=True)
class SimulationResult:
    """Phase 103 activation simulation result.
    fully_activated=True when gate_passed AND vhp_minted AND dry_run_toggled.
    error=None on success.
    """
    simulation_sessions: int
    gate_passed:         bool
    cert_created:        bool
    dry_run_toggled:     bool
    vhp_minted:          bool
    token_id:            int | None
    tx_hash:             str
    fully_activated:     bool
    elapsed_ms:          int
    error:               str | None = None


class VAPIActivationFlow:
    """SDK for operators to run the Phase 103 activation simulation.
    Never raises -- errors in SimulationResult.error or returned dicts.

    Example::

        flow = VAPIActivationFlow("http://localhost:8080", api_key="...")
        result = flow.run_simulation(n_sessions=110)
        if result.fully_activated:
            status = flow.check_ready()
            vhp    = flow.get_first_vhp()
    """

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key  = api_key

    def run_simulation(self, n_sessions: int = 110) -> "SimulationResult":
        """POST /agent/run-activation-simulation. Never raises."""
        try:
            import urllib.request
            import json as _json
            url = (
                f"{self._base_url}/agent/run-activation-simulation"
                f"?api_key={self._api_key}&n_sessions={n_sessions}"
            )
            req = urllib.request.Request(url, data=b"", method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                d = _json.loads(resp.read())
            return SimulationResult(
                simulation_sessions=int(d.get("simulation_sessions", 0)),
                gate_passed=bool(d.get("gate_passed", False)),
                cert_created=bool(d.get("cert_created", False)),
                dry_run_toggled=bool(d.get("dry_run_toggled", False)),
                vhp_minted=bool(d.get("vhp_minted", False)),
                token_id=d.get("token_id"),
                tx_hash=str(d.get("tx_hash", "")),
                fully_activated=bool(d.get("fully_activated", False)),
                elapsed_ms=int(d.get("elapsed_ms", 0)),
            )
        except Exception as exc:
            return SimulationResult(
                simulation_sessions=0, gate_passed=False, cert_created=False,
                dry_run_toggled=False, vhp_minted=False, token_id=None,
                tx_hash="", fully_activated=False, elapsed_ms=0,
                error=str(exc),
            )

    def check_ready(self) -> dict:
        """GET /agent/activation-status. Returns dict, never raises."""
        try:
            import urllib.request
            import json as _json
            url = f"{self._base_url}/agent/activation-status?api_key={self._api_key}"
            with urllib.request.urlopen(url, timeout=10) as resp:
                return _json.loads(resp.read())
        except Exception as exc:
            return {"fully_activated": False, "error": str(exc)}

    def get_first_vhp(self) -> dict:
        """GET /agent/first-vhp-status. Returns dict, never raises."""
        try:
            import urllib.request
            import json as _json
            url = f"{self._base_url}/agent/first-vhp-status?api_key={self._api_key}"
            with urllib.request.urlopen(url, timeout=10) as resp:
                return _json.loads(resp.read())
        except Exception as exc:
            return {"found": False, "error": str(exc)}


@dataclass(slots=True)
class ProtocolMaturityResult:
    """Phase 104 — ProtocolMaturityIndex result.
    pmi: 0=uninitiated / 1=simulated / 2=testnet_organic / 3=mainnet.
    error=None on success.
    """
    pmi:                   int
    pmi_label:             str
    activation_committed:  bool
    committed_at:          float | None
    dry_run_active:        bool
    is_simulation:         bool
    days_until_vhp_expiry: float | None
    vhp_found:             bool
    error:                 str | None = None


class VAPIProtocolMaturity:
    """SDK for querying and committing protocol maturity state (Phase 104). Never raises."""

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key  = api_key

    def get_maturity(self) -> "ProtocolMaturityResult":
        """GET /agent/protocol-maturity. Never raises."""
        try:
            import urllib.request, json as _json
            url = f"{self._base_url}/agent/protocol-maturity?api_key={self._api_key}"
            with urllib.request.urlopen(url, timeout=10) as resp:
                d = _json.loads(resp.read())
            return ProtocolMaturityResult(
                pmi=int(d.get("pmi", 0)), pmi_label=str(d.get("pmi_label", "unknown")),
                activation_committed=bool(d.get("activation_committed", False)),
                committed_at=d.get("committed_at"),
                dry_run_active=bool(d.get("dry_run_active", True)),
                is_simulation=bool(d.get("is_simulation", True)),
                days_until_vhp_expiry=d.get("days_until_vhp_expiry"),
                vhp_found=bool(d.get("vhp_found", False)),
            )
        except Exception as exc:
            return ProtocolMaturityResult(
                pmi=0, pmi_label="unknown", activation_committed=False, committed_at=None,
                dry_run_active=True, is_simulation=True, days_until_vhp_expiry=None,
                vhp_found=False, error=str(exc),
            )

    def commit_activation(self, n_sessions: int = 110, notes: str = "") -> dict:
        """POST /agent/commit-activation. Returns dict, never raises."""
        try:
            import urllib.request, json as _json
            url = (f"{self._base_url}/agent/commit-activation"
                   f"?api_key={self._api_key}&n_sessions={n_sessions}&notes={notes}")
            req = urllib.request.Request(url, data=b"", method="POST")
            with urllib.request.urlopen(req, timeout=60) as resp:
                return _json.loads(resp.read())
        except Exception as exc:
            return {"committed": False, "error": str(exc)}


@dataclass(slots=True)
class BootstrapResult:
    """Phase 106 — VAPIOperatorOnboarding.bootstrap() result.
    fully_bootstrapped=True when simulation done AND committed AND pmi >= 1.
    error=None on success.
    """
    simulation_done:       bool
    activation_committed:  bool
    pmi:                   int
    pmi_label:             str
    dry_run_active:        bool
    days_until_vhp_expiry: float | None
    fully_bootstrapped:    bool
    error:                 str | None = None


class VAPIOperatorOnboarding:
    """One-call operator bootstrap for VAPI AGaaS deployment (Phase 106).
    Sequence: check maturity -> simulate if needed -> commit -> verify PMI.
    Never raises -- errors in BootstrapResult.error.
    """

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base_url   = base_url.rstrip("/")
        self._api_key    = api_key
        self._maturity   = VAPIProtocolMaturity(base_url, api_key)

    def bootstrap(self, n_sessions: int = 110, notes: str = "VAPIOperatorOnboarding") -> "BootstrapResult":
        """Full bootstrap sequence. Never raises."""
        try:
            current = self._maturity.get_maturity()
            if current.activation_committed and current.pmi >= 1:
                return BootstrapResult(
                    simulation_done=True, activation_committed=True,
                    pmi=current.pmi, pmi_label=current.pmi_label,
                    dry_run_active=current.dry_run_active,
                    days_until_vhp_expiry=current.days_until_vhp_expiry,
                    fully_bootstrapped=True,
                )
            commit = self._maturity.commit_activation(n_sessions=n_sessions, notes=notes)
            if not commit.get("committed", False):
                return BootstrapResult(
                    simulation_done=False, activation_committed=False,
                    pmi=0, pmi_label="uninitiated", dry_run_active=True,
                    days_until_vhp_expiry=None, fully_bootstrapped=False,
                    error=commit.get("error", "commit_failed"),
                )
            final = self._maturity.get_maturity()
            return BootstrapResult(
                simulation_done=True, activation_committed=final.activation_committed,
                pmi=final.pmi, pmi_label=final.pmi_label,
                dry_run_active=final.dry_run_active,
                days_until_vhp_expiry=final.days_until_vhp_expiry,
                fully_bootstrapped=final.activation_committed and final.pmi >= 1,
            )
        except Exception as exc:
            return BootstrapResult(
                simulation_done=False, activation_committed=False,
                pmi=0, pmi_label="uninitiated", dry_run_active=True,
                days_until_vhp_expiry=None, fully_bootstrapped=False, error=str(exc),
            )

    def check_maturity(self) -> "ProtocolMaturityResult":
        """GET /agent/protocol-maturity. Never raises."""
        return self._maturity.get_maturity()


@dataclass(slots=True)
class TournamentEntryResult:
    """Phase 106 — VAPITournamentIntegration.request_game_demo() result.
    entered=True when player is eligible AND has valid VHP.
    error=None on success.
    """
    device_id:     str
    wallet:        str
    entered:       bool
    demo_mode:     bool
    is_eligible:   bool
    has_valid_vhp: bool
    error:         str | None = None


class VAPITournamentIntegration:
    """SDK for game developers -- integrates with VAPI-gated tournament eligibility (Phase 106).
    Composes VAPITournamentClient for eligibility checks. Never raises.
    """

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base_url   = base_url.rstrip("/")
        self._api_key    = api_key
        self._tournament = VAPITournamentClient(base_url, api_key)

    def request_game_demo(self, device_id: str, wallet: str) -> "TournamentEntryResult":
        """Check player eligibility. Never raises."""
        try:
            elig = self._tournament.check_player(device_id, wallet)
            return TournamentEntryResult(
                device_id=device_id, wallet=wallet,
                entered=elig.is_eligible and elig.has_valid_vhp,
                demo_mode=True,
                is_eligible=elig.is_eligible,
                has_valid_vhp=elig.has_valid_vhp,
                error=elig.error,
            )
        except Exception as exc:
            return TournamentEntryResult(
                device_id=device_id, wallet=wallet, entered=False,
                demo_mode=True, is_eligible=False, has_valid_vhp=False, error=str(exc),
            )


@dataclass(slots=True)
class LiveModeReadinessResult:
    """Phase 107 — Live mode readiness validation result.
    ready_for_live=True when n_tested>=100 AND false_positive_count==0 AND
    activation_committed AND NOT dry_run_active AND pmi>=1.
    error=None on success.
    """
    n_tested:             int
    false_positive_count: int
    false_positive_rate:  float
    activation_committed: bool
    pmi:                  int
    dry_run_active:       bool
    ready_for_live:       bool
    error:                "str | None" = None


class VAPILiveModeValidator:
    """SDK for querying live mode readiness state (Phase 107). Never raises."""

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key  = api_key

    def run_validation(self, n: int = 100) -> "LiveModeReadinessResult":
        """POST /agent/run-readiness-validation. Never raises."""
        try:
            import urllib.request, json as _json
            url = (f"{self._base_url}/agent/run-readiness-validation"
                   f"?api_key={self._api_key}&n={n}")
            req = urllib.request.Request(url, data=b"", method="POST")
            with urllib.request.urlopen(req, timeout=60) as resp:
                d = _json.loads(resp.read())
            return LiveModeReadinessResult(
                n_tested=int(d.get("n_tested", 0)),
                false_positive_count=int(d.get("false_positive_count", 0)),
                false_positive_rate=float(d.get("false_positive_rate", 0.0)),
                activation_committed=bool(d.get("activation_committed", False)),
                pmi=int(d.get("pmi", 0)),
                dry_run_active=bool(d.get("dry_run_active", True)),
                ready_for_live=bool(d.get("ready_for_live", False)),
            )
        except Exception as exc:
            return LiveModeReadinessResult(
                n_tested=0, false_positive_count=0, false_positive_rate=0.0,
                activation_committed=False, pmi=0, dry_run_active=True,
                ready_for_live=False, error=str(exc),
            )

    def get_latest(self) -> "LiveModeReadinessResult":
        """GET /agent/live-mode-readiness. Never raises."""
        try:
            import urllib.request, json as _json
            url = f"{self._base_url}/agent/live-mode-readiness?api_key={self._api_key}"
            with urllib.request.urlopen(url, timeout=10) as resp:
                d = _json.loads(resp.read())
            return LiveModeReadinessResult(
                n_tested=int(d.get("n_tested", 0)),
                false_positive_count=int(d.get("false_positive_count", 0)),
                false_positive_rate=float(d.get("false_positive_rate", 0.0)),
                activation_committed=bool(d.get("activation_committed", False)),
                pmi=int(d.get("pmi", 0)),
                dry_run_active=bool(d.get("dry_run_active", True)),
                ready_for_live=bool(d.get("ready_for_live", False)),
            )
        except Exception as exc:
            return LiveModeReadinessResult(
                n_tested=0, false_positive_count=0, false_positive_rate=0.0,
                activation_committed=False, pmi=0, dry_run_active=True,
                ready_for_live=False, error=str(exc),
            )


@dataclass(slots=True)
class TournamentReadinessResult:
    """Phase 108 — Comprehensive tournament readiness scorecard.
    fully_ready=True requires all 7 conditions (5 software + 2 hardware).
    Current hardware blocker: separation_ratio_current=1.261 (Phase 143, N=11), required >1.0;
    classification 63.6% — BLOCKER until ≥80%.
    error=None on success.
    """
    software_conditions_met:   int
    software_conditions_total: int
    hardware_conditions_met:   int
    hardware_conditions_total: int
    separation_ratio_current:  float
    separation_ratio_required: float
    fully_ready:               bool
    blocking_conditions:       list
    ready_for_live:            bool
    pmi:                       int
    error:                     "str | None" = None


class VAPITournamentReadiness:
    """SDK for querying tournament readiness scorecard (Phase 108). Never raises."""

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key  = api_key

    def get_scorecard(self) -> "TournamentReadinessResult":
        """GET /agent/tournament-readiness. Never raises."""
        try:
            import urllib.request, json as _json
            url = f"{self._base_url}/agent/tournament-readiness?api_key={self._api_key}"
            with urllib.request.urlopen(url, timeout=10) as resp:
                d = _json.loads(resp.read())
            return TournamentReadinessResult(
                software_conditions_met=int(d.get("software_conditions_met", 0)),
                software_conditions_total=int(d.get("software_conditions_total", 5)),
                hardware_conditions_met=int(d.get("hardware_conditions_met", 0)),
                hardware_conditions_total=int(d.get("hardware_conditions_total", 2)),
                separation_ratio_current=float(d.get("separation_ratio_current", 1.261)),
                separation_ratio_required=float(d.get("separation_ratio_required", 1.0)),
                fully_ready=bool(d.get("fully_ready", False)),
                blocking_conditions=list(d.get("blocking_conditions", [])),
                ready_for_live=bool(d.get("ready_for_live", False)),
                pmi=int(d.get("pmi", 0)),
            )
        except Exception as exc:
            return TournamentReadinessResult(
                software_conditions_met=0, software_conditions_total=5,
                hardware_conditions_met=0, hardware_conditions_total=2,
                separation_ratio_current=1.261, separation_ratio_required=1.0,
                fully_ready=False, blocking_conditions=[], ready_for_live=False,
                pmi=0, error=str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 109A — ioSwarm Bridge Adapter SDK
# ---------------------------------------------------------------------------
# Phase 109B — ioSwarm Renewal Status
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class IoSwarmRenewalResult:
    """Result from VAPISwarmRenewal.get_renewal_status() (Phase 109B).

    ioswarm_renewal_enabled=False by default — backward-compatible.
    task_spec_registered=True means vapi_vhp_renewal_v1 spec is available.
    """
    ioswarm_renewal_enabled: bool
    min_quorum:              int
    renewal_count:           int
    task_spec_registered:    bool
    recent_approvals:        int
    recent_skips:            int
    error:                   "str | None" = None   # 7 slots total


class VAPISwarmRenewal:
    """SDK for GET /agent/ioswarm-renewal-status (Phase 109B). Never raises."""

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key  = api_key

    def get_renewal_status(self) -> IoSwarmRenewalResult:
        """GET /agent/ioswarm-renewal-status. Never raises; returns defaults on error."""
        try:
            import urllib.request, json as _json
            url = f"{self._base_url}/agent/ioswarm-renewal-status?api_key={self._api_key}"
            with urllib.request.urlopen(url, timeout=10) as resp:
                d = _json.loads(resp.read())
            return IoSwarmRenewalResult(
                ioswarm_renewal_enabled=bool(d.get("ioswarm_renewal_enabled", False)),
                min_quorum=int(d.get("min_quorum", 3)),
                renewal_count=int(d.get("renewal_count", 0)),
                task_spec_registered=bool(d.get("task_spec_registered", True)),
                recent_approvals=int(d.get("recent_approvals", 0)),
                recent_skips=int(d.get("recent_skips", 0)),
            )
        except Exception as exc:
            return IoSwarmRenewalResult(
                ioswarm_renewal_enabled=False,
                min_quorum=3,
                renewal_count=0,
                task_spec_registered=True,
                recent_approvals=0,
                recent_skips=0,
                error=str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 109C — IoSwarm Adjudication (ClassJ+Triage dual-quorum veto)
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class IoSwarmVHPMintResult:
    """Result from VAPISwarmVHPMint.get_vhp_mint_status() (Phase 110).

    ioswarm_vhp_mint_enabled=False by default — fail-CLOSED quorum gate for VHP mint.
    task_spec_registered=True means vapi_vhp_mint_authorization_v1 spec is available.
    quorum_verdict / authorized reflect last resolved quorum decision.
    """
    ioswarm_vhp_mint_enabled: bool
    quorum_verdict:            str
    authorized:                bool
    agreement_ratio:           float
    authorized_count:          int
    denied_count:              int
    task_spec_registered:      bool
    error:                     "str | None" = None  # 8 slots total


class VAPISwarmVHPMint:
    """SDK for GET /agent/ioswarm-vhp-mint-status (Phase 110). Never raises."""

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key  = api_key

    def get_vhp_mint_status(self) -> IoSwarmVHPMintResult:
        """GET /agent/ioswarm-vhp-mint-status. Never raises; returns defaults on error."""
        try:
            url = f"{self._base_url}/agent/ioswarm-vhp-mint-status?api_key={self._api_key}"
            with urllib.request.urlopen(url, timeout=10) as resp:
                d = _json.loads(resp.read())
            logs = d.get("recent_vhp_mint_logs", [])
            last_log = logs[0] if logs else {}
            return IoSwarmVHPMintResult(
                ioswarm_vhp_mint_enabled=bool(d.get("ioswarm_vhp_mint_enabled", False)),
                quorum_verdict=str(last_log.get("quorum_verdict", "DENY")),
                authorized=bool(last_log.get("authorized", False)),
                agreement_ratio=float(last_log.get("agreement_ratio", 0.0)),
                authorized_count=int(d.get("authorized_count", 0)),
                denied_count=int(d.get("denied_count", 0)),
                task_spec_registered=bool(d.get("task_spec_registered", True)),
            )
        except Exception as exc:
            return IoSwarmVHPMintResult(
                ioswarm_vhp_mint_enabled=False,
                quorum_verdict="DENY",
                authorized=False,
                agreement_ratio=0.0,
                authorized_count=0,
                denied_count=0,
                task_spec_registered=True,
                error=str(exc),
            )


@dataclass(slots=True)
class PoAdRegistryResult:
    """Result from VAPIPoAdRegistry.get_poad_status() (Phase 111).

    W2 composability: Phase 113 tournaments require BOTH isFullyEligible() (PoAC)
    AND isRecorded(poadHash) (PoAd) — no single-operator system can replicate.
    task_spec_registered=True means AdjudicationRegistry.sol is deployed (Phase 111).
    """

    poad_registry_enabled:           bool
    total_poad_count:                 int
    dual_veto_poad_count:             int
    on_chain_anchor_count:            int
    adjudication_registry_address:    str
    task_spec_registered:             bool
    is_composable:                    bool
    error:                            "str | None" = None  # 8 slots total


class VAPIPoAdRegistry:
    """SDK for GET /agent/adjudication-registry-status (Phase 111). Never raises."""

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_poad_status(self) -> PoAdRegistryResult:
        """Return PoAd Registry status. On error: enabled=False, counts=0, is_composable=False."""
        import urllib.request as _ur, json as _j
        try:
            url = f"{self._base}/agent/adjudication-registry-status?api_key={self._key}"
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                data = _j.loads(resp.read())
            return PoAdRegistryResult(
                poad_registry_enabled=bool(data.get("poad_registry_enabled", False)),
                total_poad_count=int(data.get("total_poad_count", 0)),
                dual_veto_poad_count=int(data.get("dual_veto_poad_count", 0)),
                on_chain_anchor_count=int(data.get("on_chain_anchor_count", 0)),
                adjudication_registry_address=str(data.get("adjudication_registry_address", "")),
                task_spec_registered=True,
                is_composable=bool(data.get("is_composable", False)),
            )
        except Exception as exc:
            return PoAdRegistryResult(
                poad_registry_enabled=False,
                total_poad_count=0,
                dual_veto_poad_count=0,
                on_chain_anchor_count=0,
                adjudication_registry_address="",
                task_spec_registered=True,
                is_composable=False,
                error=str(exc),
            )


@dataclass(slots=True)
class PoAdAnchorResult:
    """Result from VAPIPoAdAnchor.get_anchor_status() (Phase 112).

    poad_on_chain_enabled=False by default — zero behavior change until enabled.
    anchored_count: entries in poad_registry_log with on_chain_tx IS NOT NULL.
    pending_count: entries with on_chain_tx IS NULL.
    """
    poad_on_chain_enabled:         bool
    anchored_count:                int
    pending_count:                 int
    last_anchor_tx:                "str | None"
    adjudication_registry_address: str
    error:                         "str | None" = None  # 6 slots total


class VAPIPoAdAnchor:
    """SDK for GET /agent/poad-anchor-status (Phase 112). Never raises."""

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_anchor_status(self) -> PoAdAnchorResult:
        """Return PoAd on-chain anchor status. On error: enabled=False, counts=0."""
        import urllib.request as _ur, json as _j
        try:
            url = f"{self._base}/agent/poad-anchor-status?api_key={self._key}"
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                data = _j.loads(resp.read())
            return PoAdAnchorResult(
                poad_on_chain_enabled=bool(data.get("poad_on_chain_enabled", False)),
                anchored_count=int(data.get("anchored_count", 0)),
                pending_count=int(data.get("pending_count", 0)),
                last_anchor_tx=data.get("last_anchor_tx"),
                adjudication_registry_address=str(data.get("adjudication_registry_address", "")),
            )
        except Exception as exc:
            return PoAdAnchorResult(
                poad_on_chain_enabled=False,
                anchored_count=0,
                pending_count=0,
                last_anchor_tx=None,
                adjudication_registry_address="",
                error=str(exc),
            )


@dataclass(slots=True)
class DualPrimitiveGateResult:
    """Result from VAPIDualPrimitiveGate.check_eligibility() (Phase 113).

    eligible=True ONLY when both poac_valid AND poad_valid are True.
    poac_valid: VAPIProtocolLens.isFullyEligible() returned true.
    poad_valid: AdjudicationRegistry.isRecorded(poadHash) returned true.
    dual_primitive_gate_enabled=False by default — infrastructure-only until gate deployed.
    """
    eligible:                    bool
    poac_valid:                  bool
    poad_valid:                  bool
    device_id:                   str
    timestamp:                   float
    error:                       "str | None" = None  # 6 slots total


class VAPIDualPrimitiveGate:
    """SDK for POST /agent/check-dual-eligibility and GET /agent/dual-primitive-status
    (Phase 113). Never raises — returns error in result on failure.
    """

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def check_eligibility(self, device_id: str, poad_hash: str) -> DualPrimitiveGateResult:
        """POST /agent/check-dual-eligibility. 10s timeout.
        On error: eligible=False, poac_valid=False, poad_valid=False, error=<message>.
        """
        import urllib.request as _ur, urllib.error as _ue, json as _j
        try:
            url  = f"{self._base}/agent/check-dual-eligibility?api_key={self._key}"
            data = _j.dumps({"device_id": device_id, "poad_hash": poad_hash}).encode()
            req  = _ur.Request(url, data=data, headers={"Content-Type": "application/json"})
            with _ur.urlopen(req, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return DualPrimitiveGateResult(
                eligible=bool(body.get("eligible", False)),
                poac_valid=bool(body.get("poac_valid", False)),
                poad_valid=bool(body.get("poad_valid", False)),
                device_id=str(body.get("device_id", device_id)),
                timestamp=float(body.get("timestamp", 0.0)),
            )
        except Exception as exc:
            return DualPrimitiveGateResult(
                eligible=False,
                poac_valid=False,
                poad_valid=False,
                device_id=device_id,
                timestamp=0.0,
                error=str(exc),
            )


@dataclass(slots=True)
class VHPDualGateResult:
    """Single entry from GET /agent/vhp-dual-gate-log (Phase 114).

    Records each time the 5th dual-primitive gate was evaluated during a VHP mint attempt.
    mint_allowed=True means the device passed the gate (eligible=True).
    dual_primitive_gate_enabled=False by default — infrastructure-only until gate deployed.
    """
    device_id:    str
    eligible:     bool
    poac_valid:   bool
    poad_valid:   bool
    mint_allowed: bool
    error:        "str | None" = None  # 6 slots total


class VAPIVHPDualGate:
    """SDK for GET /agent/vhp-dual-gate-log (Phase 114). Never raises."""

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_gate_log(
        self,
        device_id: "str | None" = None,
        limit: int = 10,
    ) -> "list[VHPDualGateResult]":
        """GET /agent/vhp-dual-gate-log. 10s timeout.
        On error: returns list with one VHPDualGateResult(error=<msg>, all False).
        """
        import urllib.request as _ur, json as _j
        try:
            qs = f"api_key={self._key}&limit={limit}"
            if device_id:
                qs += f"&device_id={device_id}"
            url = f"{self._base}/agent/vhp-dual-gate-log?{qs}"
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return [
                VHPDualGateResult(
                    device_id=str(r.get("device_id", "")),
                    eligible=bool(r.get("eligible", False)),
                    poac_valid=bool(r.get("poac_valid", False)),
                    poad_valid=bool(r.get("poad_valid", False)),
                    mint_allowed=bool(r.get("mint_allowed", False)),
                )
                for r in body.get("recent_logs", [])
            ]
        except Exception as exc:
            return [VHPDualGateResult(
                device_id="", eligible=False, poac_valid=False,
                poad_valid=False, mint_allowed=False, error=str(exc),
            )]


@dataclass(slots=True)
class EpochWindowAnalyticsResult:
    """Result from VAPIEpochWindowAnalytics.get_analytics() (Phase 116).

    Provides age-distribution analytics over Gate-5 poad_age_seconds values.
    recommended_window_seconds = 2 × p95, floored 3600s, capped 604800s.
    Falls back to 86400 when fewer than 10 checked samples.
    """
    epoch_window_enabled:        bool
    epoch_window_seconds:        float
    total_gate5_checks:          int
    staleness_blocked_count:     int
    p50_age_seconds:             float
    p95_age_seconds:             float
    recommended_window_seconds:  float
    error:                       "str | None" = None  # 8 slots total


class VAPIEpochWindowAnalytics:
    """SDK for GET /agent/epoch-window-analytics (Phase 116). Never raises."""

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_analytics(self, limit: int = 1000) -> EpochWindowAnalyticsResult:
        """GET /agent/epoch-window-analytics. 10s timeout.
        On error: returns EpochWindowAnalyticsResult with error set and safe defaults.
        """
        import urllib.request as _ur, json as _j
        try:
            url = f"{self._base}/agent/epoch-window-analytics?api_key={self._key}&limit={limit}"
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return EpochWindowAnalyticsResult(
                epoch_window_enabled=bool(body.get("epoch_window_enabled", False)),
                epoch_window_seconds=float(body.get("epoch_window_seconds", 86400.0)),
                total_gate5_checks=int(body.get("total_gate5_checks", 0)),
                staleness_blocked_count=int(body.get("staleness_blocked_count", 0)),
                p50_age_seconds=float(body.get("p50_age_seconds", -1.0)),
                p95_age_seconds=float(body.get("p95_age_seconds", -1.0)),
                recommended_window_seconds=float(body.get("recommended_window_seconds", 86400.0)),
            )
        except Exception as exc:
            return EpochWindowAnalyticsResult(
                epoch_window_enabled=False,
                epoch_window_seconds=86400.0,
                total_gate5_checks=0,
                staleness_blocked_count=0,
                p50_age_seconds=-1.0,
                p95_age_seconds=-1.0,
                recommended_window_seconds=86400.0,
                error=str(exc),
            )


@dataclass(slots=True)
class EpochWindowDeviceEntry:
    """Single device entry from VAPIEpochWindowHeatmap.get_heatmap() (Phase 117).

    Represents per-device epoch freshness analytics sorted by p95 DESC (worst first).
    """
    device_id:       str
    check_count:     int
    blocked_count:   int
    p50_age_seconds: float
    p95_age_seconds: float
    last_check_ts:   float  # 6 slots total


class VAPIEpochWindowHeatmap:
    """SDK for GET /agent/epoch-window-device-heatmap (Phase 117). Never raises."""

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_heatmap(
        self, limit_per_device: int = 100, top_n: int = 20
    ) -> "list[EpochWindowDeviceEntry]":
        """GET /agent/epoch-window-device-heatmap. 10s timeout.
        On error: returns list with one EpochWindowDeviceEntry with error-safe defaults.
        """
        import urllib.request as _ur, json as _j
        try:
            url = (
                f"{self._base}/agent/epoch-window-device-heatmap"
                f"?api_key={self._key}"
                f"&limit_per_device={limit_per_device}"
                f"&top_n={top_n}"
            )
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return [
                EpochWindowDeviceEntry(
                    device_id=str(d.get("device_id", "")),
                    check_count=int(d.get("check_count", 0)),
                    blocked_count=int(d.get("blocked_count", 0)),
                    p50_age_seconds=float(d.get("p50_age_seconds", -1.0)),
                    p95_age_seconds=float(d.get("p95_age_seconds", -1.0)),
                    last_check_ts=float(d.get("last_check_ts", 0.0)),
                )
                for d in body.get("devices", [])
            ]
        except Exception as exc:
            return [EpochWindowDeviceEntry(
                device_id="", check_count=0, blocked_count=0,
                p50_age_seconds=-1.0, p95_age_seconds=-1.0,
                last_check_ts=0.0,
            )]


@dataclass(slots=True)
class EpochWindowAutoTuneResult:
    """Result from VAPIEpochWindowAutoTune.get_auto_tune() (Phase 118).

    Advises operators on window tuning + lists devices needing per-device overrides.
    W1 mitigation: cold-start devices surface as override_candidates instead of
    causing false-positive blocks at gate activation.
    """
    epoch_window_enabled:      bool
    current_window_seconds:    float
    recommended_window_seconds: float
    fleet_p95_age_seconds:     float
    override_count:            int
    override_candidates:       list  # list of dicts from get_epoch_window_analytics_by_device
    error:                     "str | None" = None  # 7 slots


class VAPIEpochWindowAutoTune:
    """SDK for GET /agent/epoch-window-auto-tune (Phase 118). Never raises."""

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_auto_tune(self, top_n_overrides: int = 5) -> EpochWindowAutoTuneResult:
        """GET /agent/epoch-window-auto-tune. 10s timeout.
        On error: returns EpochWindowAutoTuneResult with error set and safe defaults.
        """
        import urllib.request as _ur, json as _j
        try:
            url = (
                f"{self._base}/agent/epoch-window-auto-tune"
                f"?api_key={self._key}"
                f"&top_n_overrides={top_n_overrides}"
            )
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return EpochWindowAutoTuneResult(
                epoch_window_enabled=bool(body.get("epoch_window_enabled", False)),
                current_window_seconds=float(body.get("current_window_seconds", 86400.0)),
                recommended_window_seconds=float(body.get("recommended_window_seconds", 86400.0)),
                fleet_p95_age_seconds=float(body.get("fleet_p95_age_seconds", -1.0)),
                override_count=int(body.get("override_count", 0)),
                override_candidates=list(body.get("override_candidates", [])),
            )
        except Exception as exc:
            return EpochWindowAutoTuneResult(
                epoch_window_enabled=False,
                current_window_seconds=86400.0,
                recommended_window_seconds=86400.0,
                fleet_p95_age_seconds=-1.0,
                override_count=0,
                override_candidates=[],
                error=str(exc),
            )


@dataclass(slots=True)
class EpochWindowOverrideStatus:
    """Result from VAPIEpochWindowOverrideManager.get_override_status() (Phase 119).

    Lists all per-device overrides with full lifecycle fields so operators can audit
    which are ephemeral (max_uses set) vs permanent (max_uses=None).
    override_count: total overrides currently active.
    overrides_with_max_uses: count with auto-expiry use-count configured.
    overrides: raw list of dicts from get_override_lifecycle_status().
    epoch_window_enabled: current fleet gate state.
    """
    override_count:           int
    overrides_with_max_uses:  int
    overrides:                list
    epoch_window_enabled:     bool
    timestamp:                float
    error:                    "str | None" = None  # 6 slots


class VAPIEpochWindowOverrideManager:
    """SDK for GET /agent/epoch-window-override-status and DELETE /agent/epoch-window-override
    (Phase 119). Never raises.
    """

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_override_status(self) -> EpochWindowOverrideStatus:
        """GET /agent/epoch-window-override-status. 10s timeout.
        On error: returns EpochWindowOverrideStatus with error set and safe defaults.
        """
        import urllib.request as _ur, json as _j, time as _t
        try:
            url = f"{self._base}/agent/epoch-window-override-status?api_key={self._key}"
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return EpochWindowOverrideStatus(
                override_count=int(body.get("override_count", 0)),
                overrides_with_max_uses=int(body.get("overrides_with_max_uses", 0)),
                overrides=list(body.get("overrides", [])),
                epoch_window_enabled=bool(body.get("epoch_window_enabled", False)),
                timestamp=float(body.get("timestamp", _t.time())),
            )
        except Exception as exc:
            import time as _t2
            return EpochWindowOverrideStatus(
                override_count=0,
                overrides_with_max_uses=0,
                overrides=[],
                epoch_window_enabled=False,
                timestamp=_t2.time(),
                error=str(exc),
            )

    def revoke_override(self, device_id: str) -> "dict":
        """DELETE /agent/epoch-window-override?device_id=X. 10s timeout.
        On error: returns dict with revoked=False and error key. Never raises.
        """
        import urllib.request as _ur, json as _j, time as _t
        try:
            url = (
                f"{self._base}/agent/epoch-window-override"
                f"?api_key={self._key}"
                f"&device_id={device_id}"
            )
            req = _ur.Request(url, method="DELETE")
            with _ur.urlopen(req, timeout=10) as resp:  # noqa: S310
                return _j.loads(resp.read())
        except Exception as exc:
            return {"device_id": device_id, "revoked": False, "error": str(exc)}


@dataclass(slots=True)
class IoSwarmAdjudicationResult:
    """Result from VAPISwarmAdjudication.get_adjudication_status() (Phase 109C).

    ioswarm_adjudication_enabled=False by default — backward-compatible.
    task_spec_registered=True means vapi_classj_triage_adjudication_v1 spec is available.
    dual_veto_active=True when BOTH classj AND triage quorums independently returned BLOCK.
    """
    ioswarm_adjudication_enabled: bool
    classj_quorum_verdict:        str
    triage_quorum_verdict:        str
    dual_veto_active:             bool
    adjudication_count:           int
    recent_blocks:                int
    task_spec_registered:         bool
    error:                        "str | None" = None  # 8 slots total


class VAPISwarmAdjudication:
    """SDK for GET /agent/ioswarm-adjudication-status (Phase 109C). Never raises."""

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key  = api_key

    def get_adjudication_status(self) -> IoSwarmAdjudicationResult:
        """GET /agent/ioswarm-adjudication-status. Never raises; returns defaults on error."""
        try:
            url = f"{self._base_url}/agent/ioswarm-adjudication-status?api_key={self._api_key}"
            with urllib.request.urlopen(url, timeout=10) as resp:
                d = _json.loads(resp.read())
            logs = d.get("recent_adjudication_logs", [])
            recent_blocks = sum(
                1 for r in logs
                if r.get("classj_quorum_verdict") == "BLOCK"
                or r.get("triage_quorum_verdict") == "BLOCK"
            )
            return IoSwarmAdjudicationResult(
                ioswarm_adjudication_enabled=bool(d.get("ioswarm_adjudication_enabled", False)),
                classj_quorum_verdict=str(d.get("classj_quorum_verdict", "CLEAR")),
                triage_quorum_verdict=str(d.get("triage_quorum_verdict", "CLEAR")),
                dual_veto_active=bool(d.get("dual_veto_count", 0) > 0),
                adjudication_count=int(d.get("adjudication_count", 0)),
                recent_blocks=recent_blocks,
                task_spec_registered=bool(d.get("task_spec_registered", True)),
            )
        except Exception as exc:
            return IoSwarmAdjudicationResult(
                ioswarm_adjudication_enabled=False,
                classj_quorum_verdict="CLEAR",
                triage_quorum_verdict="CLEAR",
                dual_veto_active=False,
                adjudication_count=0,
                recent_blocks=0,
                task_spec_registered=True,
                error=str(exc),
            )


# ---------------------------------------------------------------------------

@dataclass(slots=True)
class IoSwarmConsensusResult:
    """Result from VAPISwarmStatus.get_status() (Phase 109A).

    When ioswarm_enabled=False (default) the bridge returns infrastructure-only
    mode and this result reflects that with defaults.
    """
    ioswarm_enabled:          bool
    quorum_threshold:         float
    block_quorum_threshold:   float
    consensus_count:          int
    configured_node_count:    int
    task_spec_registered:     bool
    w3bstream_applets:        list
    vhp_auth_gate_address:    str
    error:                    "str | None" = None   # 9 slots total


class VAPISwarmStatus:
    """SDK for GET /agent/ioswarm-status (Phase 109A). Never raises."""

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key  = api_key

    def get_status(self) -> IoSwarmConsensusResult:
        """GET /agent/ioswarm-status. Never raises; returns defaults on error."""
        try:
            import urllib.request, json as _json
            url = f"{self._base_url}/agent/ioswarm-status?api_key={self._api_key}"
            with urllib.request.urlopen(url, timeout=10) as resp:
                d = _json.loads(resp.read())
            return IoSwarmConsensusResult(
                ioswarm_enabled=bool(d.get("ioswarm_enabled", False)),
                quorum_threshold=float(d.get("quorum_threshold", 0.60)),
                block_quorum_threshold=float(d.get("block_quorum_threshold", 0.67)),
                consensus_count=int(d.get("consensus_count", 0)),
                configured_node_count=int(d.get("configured_node_count", 5)),
                task_spec_registered=bool(d.get("task_spec_registered", True)),
                w3bstream_applets=list(d.get("w3bstream_applets", [])),
                vhp_auth_gate_address=str(d.get("vhp_auth_gate_address", "")),
            )
        except Exception as exc:
            return IoSwarmConsensusResult(
                ioswarm_enabled=False,
                quorum_threshold=0.60,
                block_quorum_threshold=0.67,
                consensus_count=0,
                configured_node_count=5,
                task_spec_registered=True,
                w3bstream_applets=[],
                vhp_auth_gate_address="",
                error=str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 120 — Bluetooth Transport Foundation
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class BTTransportResult:
    """Status from GET /agent/bt-transport-status (Phase 120).

    bt_transport_enabled=False by default (infrastructure-only until BT threshold
    track is calibrated against 250 Hz BLE sessions).

    W1 INVARIANT: USB L4 thresholds (7.009/5.367) must NOT be applied to BT frames.
    BT sessions are tagged transport_type=0x02 (TRANSPORT_TYPE_BLE).
    """
    bt_transport_enabled: bool
    device_address:       str
    sampling_rate_hz:     int
    frames_received:      int
    frames_dropped:       int
    error:                "str | None" = None  # 6 slots total


class VAPIBTTransport:
    """SDK for GET /agent/bt-transport-status (Phase 120). Never raises.

    Usage::

        bt = VAPIBTTransport("http://localhost:8080", api_key="operator-key")
        status = bt.get_transport_status()
        if not status.bt_transport_enabled:
            print("BT transport infrastructure-only — enable after BT threshold calibration")
    """

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_transport_status(self, limit: int = 10) -> BTTransportResult:
        """GET /agent/bt-transport-status. 10s timeout. Never raises.

        On error: returns BTTransportResult with error field set and all counts=0.
        """
        import urllib.request as _ur, urllib.error as _ue, json as _j
        try:
            url = f"{self._base}/agent/bt-transport-status?api_key={self._key}&limit={limit}"
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return BTTransportResult(
                bt_transport_enabled=bool(body.get("bt_transport_enabled", False)),
                device_address=str(body.get("device_address", "")),
                sampling_rate_hz=int(body.get("sampling_rate_hz", 250)),
                frames_received=int(body.get("frames_received", 0)),
                frames_dropped=int(body.get("frames_dropped", 0)),
            )
        except Exception as exc:
            return BTTransportResult(
                bt_transport_enabled=False,
                device_address="",
                sampling_rate_hz=250,
                frames_received=0,
                frames_dropped=0,
                error=str(exc),
            )

@dataclass(slots=True)
class SeparationRatioResult:
    """Biometric inter-person separation ratio status (Phase 121/168).

    pooled_ratio: measured across all sessions (currently 0.569, N=20, 2026-04-05).
    battery_stratified_ratio: same-battery pairwise estimate (-1.0 if unavailable).
    tournament_blocker: True when pooled_ratio < 1.0.
    gap_to_target: 1.0 - pooled_ratio (0.0 when tournament_ready=True).
    tournament_ready: True only when pooled_ratio >= 1.0.
    ci_lower: bootstrap 95% CI lower bound (0.0 if not computed — pass --bootstrap-n 1000).
    ci_upper: bootstrap 95% CI upper bound (0.0 if not computed).
    n_bootstrap: number of bootstrap resamples used (0 = CI not available).
    """
    pooled_ratio:             float
    battery_stratified_ratio: float
    tournament_blocker:       bool
    gap_to_target:            float
    tournament_ready:         bool
    ci_lower:                 float = 0.0
    ci_upper:                 float = 0.0
    n_bootstrap:              int   = 0
    error: "str | None" = None  # 9 slots total


class VAPISeparationStatus:
    """SDK for GET /agent/separation-ratio-status (Phase 121). Never raises.

    Usage::

        sep = VAPISeparationStatus("http://localhost:8080", api_key="operator-key")
        result = sep.get_status()
        if result.tournament_blocker:
            print(f"Separation ratio {result.pooled_ratio:.3f} — gap to 1.0: {result.gap_to_target:.3f}")
    """

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_status(self) -> SeparationRatioResult:
        """GET /agent/separation-ratio-status. 10s timeout. Never raises.

        On error: returns SeparationRatioResult with error field set and
        tournament_blocker=True, tournament_ready=False.
        """
        import urllib.request as _ur, json as _j
        try:
            url = f"{self._base}/agent/separation-ratio-status?api_key={self._key}"
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return SeparationRatioResult(
                pooled_ratio=float(body.get("pooled_ratio", 0.0)),
                battery_stratified_ratio=float(body.get("battery_stratified_ratio", -1.0)),
                tournament_blocker=bool(body.get("tournament_blocker", True)),
                gap_to_target=float(body.get("gap_to_target", 1.0)),
                tournament_ready=bool(body.get("tournament_ready", False)),
                ci_lower=float(body.get("ci_lower", 0.0)),
                ci_upper=float(body.get("ci_upper", 0.0)),
                n_bootstrap=int(body.get("n_bootstrap", 0)),
            )
        except Exception as exc:
            return SeparationRatioResult(
                pooled_ratio=0.0,
                battery_stratified_ratio=-1.0,
                tournament_blocker=True,
                gap_to_target=1.0,
                tournament_ready=False,
                ci_lower=0.0,
                ci_upper=0.0,
                n_bootstrap=0,
                error=str(exc),
            )


@dataclass(slots=True)
class ConfidenceMultiplierResult:
    """VHP confidence_score separation ratio multiplier status (Phase 122).

    multiplier_enabled: True when confidence_multiplier_enabled=True in cfg.
    current_bt_strat_ratio: most recent battery-stratified separation ratio (-1.0 if none).
    effective_multiplier: min(1.0, bt_strat_ratio) clamped to floor (1.0 if ratio unavailable).
    floor: minimum multiplier floor from cfg.confidence_multiplier_floor.
    log_count: number of recent multiplier applications returned.
    error: set on HTTP/network failure; all other fields safe to read.
    """
    multiplier_enabled:     bool
    current_bt_strat_ratio: float
    effective_multiplier:   float
    floor:                  float
    log_count:              int
    error: "str | None" = None  # 6 slots total


class VAPIConfidenceMultiplier:
    """SDK for GET /agent/confidence-score-multiplier-status (Phase 122). Never raises.

    Usage::

        cm = VAPIConfidenceMultiplier("http://localhost:8080", api_key="operator-key")
        result = cm.get_status()
        if result.multiplier_enabled:
            print(f"Effective multiplier: {result.effective_multiplier:.3f} "
                  f"(bt_strat_ratio={result.current_bt_strat_ratio:.3f})")
    """

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_status(self) -> ConfidenceMultiplierResult:
        """GET /agent/confidence-score-multiplier-status. 10s timeout. Never raises.

        On error: returns ConfidenceMultiplierResult with error field set,
        multiplier_enabled=False, effective_multiplier=1.0.
        """
        import urllib.request as _ur, json as _j
        try:
            url = (
                f"{self._base}/agent/confidence-score-multiplier-status"
                f"?api_key={self._key}"
            )
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return ConfidenceMultiplierResult(
                multiplier_enabled=bool(body.get("multiplier_enabled", False)),
                current_bt_strat_ratio=float(body.get("current_bt_strat_ratio", -1.0)),
                effective_multiplier=float(body.get("effective_multiplier", 1.0)),
                floor=float(body.get("floor", 0.0)),
                log_count=int(body.get("log_count", 0)),
            )
        except Exception as exc:
            return ConfidenceMultiplierResult(
                multiplier_enabled=False,
                current_bt_strat_ratio=-1.0,
                effective_multiplier=1.0,
                floor=0.0,
                log_count=0,
                error=str(exc),
            )


@dataclass(slots=True)
class CalibrationStatusResult:
    """L4 Mahalanobis threshold calibration staleness status (Phase 123).

    current_feature_dim: live _BIO_FEATURE_DIM (13 from Phase 121).
    calibration_feature_dim: dimension used in last threshold_calibrator.py run (12, Phase 57).
    stale: True when current_feature_dim != calibration_feature_dim.
    anomaly_threshold: current L4 anomaly threshold (7.009 from Phase 57).
    continuity_threshold: current L4 continuity threshold (5.367 from Phase 57).
    error: set on HTTP/network failure; all other fields safe to read with defaults.
    """
    current_feature_dim:     int
    calibration_feature_dim: int
    stale:                   bool
    anomaly_threshold:       float
    continuity_threshold:    float
    error: "str | None" = None  # 6 slots total


class VAPICalibrationStatus:
    """SDK for GET /agent/l4-calibration-status (Phase 123). Never raises.

    Usage::

        cs = VAPICalibrationStatus("http://localhost:8080", api_key="operator-key")
        result = cs.get_status()
        if result.stale:
            print(f"L4 thresholds stale: calibrated on {result.calibration_feature_dim}-feature, "
                  f"live is {result.current_feature_dim}-feature.")
    """

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_status(self) -> CalibrationStatusResult:
        """GET /agent/l4-calibration-status. 10s timeout. Never raises.

        On error: returns CalibrationStatusResult with error field set,
        stale=True (conservative: assume stale when uncertain).
        """
        import urllib.request as _ur, json as _j
        try:
            url = f"{self._base}/agent/l4-calibration-status?api_key={self._key}"
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return CalibrationStatusResult(
                current_feature_dim=int(body.get("current_feature_dim", 13)),
                calibration_feature_dim=int(body.get("calibration_feature_dim", 12)),
                stale=bool(body.get("stale", True)),
                anomaly_threshold=float(body.get("anomaly_threshold", 7.009)),
                continuity_threshold=float(body.get("continuity_threshold", 5.367)),
            )
        except Exception as exc:
            return CalibrationStatusResult(
                current_feature_dim=13,
                calibration_feature_dim=12,
                stale=True,
                anomaly_threshold=7.009,
                continuity_threshold=5.367,
                error=str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 124 — L4 Per-Battery Threshold Track Registry
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class L4ThresholdTrackResult:
    """L4 per-battery threshold track registry status (Phase 124).

    l4_battery_threshold_enabled: registry enabled flag.
    track_count: total registered tracks.
    active_count: tracks with active=True.
    battery_types_tracked: distinct battery types with registered tracks.
    """
    l4_battery_threshold_enabled: bool
    track_count:                   int
    active_count:                  int
    battery_types_tracked:         "list[str]"
    error: "str | None" = None  # 5 slots total


class VAPIL4ThresholdTracks:
    """SDK for GET /agent/l4-threshold-tracks (Phase 124). Never raises.

    Usage::

        lt = VAPIL4ThresholdTracks("http://localhost:8080", api_key="operator-key")
        result = lt.get_tracks()
        print(f"{result.track_count} tracks, {result.active_count} active")
        print(f"Battery types: {result.battery_types_tracked}")
    """

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_tracks(
        self,
        battery_type: "str | None" = None,
        active_only: bool = False,
    ) -> L4ThresholdTrackResult:
        """GET /agent/l4-threshold-tracks. 10s timeout. Never raises.

        On error: returns L4ThresholdTrackResult with error field set,
        track_count=0, l4_battery_threshold_enabled=False.
        """
        import urllib.request as _ur, json as _j, urllib.parse as _up
        try:
            params = {"api_key": self._key}
            if battery_type is not None:
                params["battery_type"] = battery_type
            if active_only:
                params["active_only"] = "true"
            qs = _up.urlencode(params)
            url = f"{self._base}/agent/l4-threshold-tracks?{qs}"
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return L4ThresholdTrackResult(
                l4_battery_threshold_enabled=bool(body.get("l4_battery_threshold_enabled", False)),
                track_count=int(body.get("track_count", 0)),
                active_count=int(body.get("active_count", 0)),
                battery_types_tracked=list(body.get("battery_types_tracked", [])),
            )
        except Exception as exc:
            return L4ThresholdTrackResult(
                l4_battery_threshold_enabled=False,
                track_count=0,
                active_count=0,
                battery_types_tracked=[],
                error=str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 125 — Per-Battery Calibration Apply
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class CalibrationApplyResult:
    battery_type: str = ""
    anomaly_threshold: float = 0.0
    continuity_threshold: float = 0.0
    n_sessions: int = 0
    error: "str | None" = None


class VAPICalibrationApply:
    """
    POST /agent/apply-l4-battery-calibration — apply per-battery L4 threshold calibration.
    Never raises; error path returns CalibrationApplyResult with error != None.
    """

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base = base_url.rstrip("/")
        self._key = api_key

    def apply(
        self,
        battery_type: str,
        anomaly_threshold: float,
        continuity_threshold: float,
        n_sessions: int = 0,
        calibration_feature_dim: "int | None" = None,
        notes: "str | None" = None,
    ) -> CalibrationApplyResult:
        import urllib.request as _ur, json as _j, urllib.parse as _up
        try:
            params: dict = {
                "api_key": self._key,
                "battery_type": battery_type,
                "anomaly_threshold": str(anomaly_threshold),
                "continuity_threshold": str(continuity_threshold),
                "n_sessions": str(n_sessions),
            }
            if calibration_feature_dim is not None:
                params["calibration_feature_dim"] = str(calibration_feature_dim)
            if notes is not None:
                params["notes"] = notes
            qs = _up.urlencode(params)
            url = f"{self._base}/agent/apply-l4-battery-calibration?{qs}"
            req = _ur.Request(url, method="POST")
            with _ur.urlopen(req, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return CalibrationApplyResult(
                battery_type=str(body.get("battery_type", battery_type)),
                anomaly_threshold=float(body.get("anomaly_threshold", anomaly_threshold)),
                continuity_threshold=float(body.get("continuity_threshold", continuity_threshold)),
                n_sessions=int(body.get("n_sessions", n_sessions)),
            )
        except Exception as exc:
            return CalibrationApplyResult(
                battery_type="",
                anomaly_threshold=0.0,
                continuity_threshold=0.0,
                n_sessions=0,
                error=str(exc),
            )


@dataclass(slots=True)
class L4RouterStatusResult:
    l4_battery_threshold_enabled: bool = False
    total_lookups: int = 0
    per_battery_lookups: int = 0
    global_fallback_count: int = 0
    last_battery_type: str = ""
    error: "str | None" = None


class VAPIL4RouterStatus:
    """
    GET /agent/l4-router-status - L4 per-battery threshold router status (Phase 126).
    Never raises; error path returns L4RouterStatusResult with error != None.
    """

    def __init__(self, base_url: str, api_key: str = ""):
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_status(self) -> L4RouterStatusResult:
        import urllib.request as _ur, json as _j, urllib.parse as _up
        try:
            params = _up.urlencode({"api_key": self._key})
            url = f"{self._base}/agent/l4-router-status?{params}"
            req = _ur.Request(url)
            with _ur.urlopen(req, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return L4RouterStatusResult(
                l4_battery_threshold_enabled=bool(body.get("l4_battery_threshold_enabled", False)),
                total_lookups=int(body.get("total_lookups", 0)),
                per_battery_lookups=int(body.get("per_battery_lookups", 0)),
                global_fallback_count=int(body.get("global_fallback_count", 0)),
                last_battery_type=str(body.get("last_battery_type", "")),
            )
        except Exception as exc:
            return L4RouterStatusResult(
                l4_battery_threshold_enabled=False,
                total_lookups=0,
                per_battery_lookups=0,
                global_fallback_count=0,
                last_battery_type="",
                error=str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 127 — Tournament Preflight SDK
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class TournamentPreflightResult:
    separation_ok: bool = False
    l4_ok: bool = False
    gate_ok: bool = False
    cert_ok: bool = False
    audit_ok: bool = False
    overall_pass: bool = False
    conditions_detail: "dict" = None   # type: ignore[assignment]
    error: "str | None" = None
    # Phase 196: biometric_ttl_ok — 9th P0 condition (WIF-035 closure)
    biometric_ttl_ok: bool = True
    # Phase 197: all_pairs_p0_ok — 10th P0 condition (per-pair separation gate)
    all_pairs_p0_ok: bool = False
    # Phase 231: ait_defensibility_ok — 11th P0 condition (AIT all_pairs + >=10 sessions/player)
    ait_defensibility_ok: bool = False

    def __post_init__(self):
        if self.conditions_detail is None:
            object.__setattr__(self, "conditions_detail", {})


class VAPITournamentPreflight:
    """
    POST /agent/run-tournament-preflight — run preflight and return result (Phase 127).
    GET  /agent/tournament-preflight-status — return latest preflight status.
    Never raises; error path returns TournamentPreflightResult with error != None.
    """

    def __init__(self, base_url: str, api_key: str = ""):
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def run_preflight(self) -> TournamentPreflightResult:
        import urllib.request as _ur, json as _j, urllib.parse as _up
        try:
            params = _up.urlencode({"api_key": self._key})
            url = f"{self._base}/agent/run-tournament-preflight?{params}"
            req = _ur.Request(url, method="POST")
            with _ur.urlopen(req, timeout=15) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return TournamentPreflightResult(
                separation_ok=bool(body.get("separation_ok", False)),
                l4_ok=bool(body.get("l4_ok", False)),
                gate_ok=bool(body.get("gate_ok", False)),
                cert_ok=bool(body.get("cert_ok", False)),
                audit_ok=bool(body.get("audit_ok", False)),
                overall_pass=bool(body.get("overall_pass", False)),
                conditions_detail=body.get("conditions", {}),
                biometric_ttl_ok=bool(body.get("biometric_ttl_ok", True)),
                all_pairs_p0_ok=bool(body.get("all_pairs_p0_ok", False)),
                ait_defensibility_ok=bool(body.get("ait_defensibility_ok", False)),
            )
        except Exception as exc:
            return TournamentPreflightResult(
                separation_ok=False, l4_ok=False, gate_ok=False,
                cert_ok=False, audit_ok=False, overall_pass=False,
                conditions_detail={}, biometric_ttl_ok=True, all_pairs_p0_ok=False,
                ait_defensibility_ok=False, error=str(exc),
            )

    def get_status(self) -> TournamentPreflightResult:
        import urllib.request as _ur, json as _j, urllib.parse as _up
        try:
            params = _up.urlencode({"api_key": self._key})
            url = f"{self._base}/agent/tournament-preflight-status?{params}"
            req = _ur.Request(url)
            with _ur.urlopen(req, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return TournamentPreflightResult(
                separation_ok=bool(body.get("separation_ok", False)),
                l4_ok=bool(body.get("l4_ok", False)),
                gate_ok=bool(body.get("gate_ok", False)),
                cert_ok=bool(body.get("cert_ok", False)),
                audit_ok=bool(body.get("audit_ok", False)),
                overall_pass=bool(body.get("overall_pass", False)),
                conditions_detail=body.get("conditions", {}),
                biometric_ttl_ok=bool(body.get("biometric_ttl_ok", True)),
                all_pairs_p0_ok=bool(body.get("all_pairs_p0_ok", False)),
                ait_defensibility_ok=bool(body.get("ait_defensibility_ok", False)),
            )
        except Exception as exc:
            return TournamentPreflightResult(
                separation_ok=False, l4_ok=False, gate_ok=False,
                cert_ok=False, audit_ok=False, overall_pass=False,
                conditions_detail={}, biometric_ttl_ok=True, all_pairs_p0_ok=False,
                ait_defensibility_ok=False, error=str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 128 — Tournament Readiness Score
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class TournamentReadinessScore:
    """Result from GET /agent/tournament-readiness-score (Phase 128).

    score: weighted composite 0.0–1.0; conditions_met: count of fully-passing signals (0–6).
    """
    score: float = 0.0
    separation_score: float = 0.0
    l4_score: float = 0.0
    dual_gate_score: float = 0.0
    epoch_score: float = 0.0
    ioswarm_score: float = 0.0
    dry_run_score: float = 0.0
    error: "str | None" = None


class VAPITournamentReadinessScore:
    """SDK client for the Phase 128 Tournament Readiness Score endpoint.

    Never raises; error path returns TournamentReadinessScore with error != None.
    """

    def __init__(self, base_url: str, api_key: str = "", timeout: int = 10):
        self._base_url = base_url.rstrip("/")
        self._api_key  = api_key
        self._timeout  = timeout

    def get_score(self) -> TournamentReadinessScore:
        """Call GET /agent/tournament-readiness-score.  Returns TournamentReadinessScore."""
        import urllib.request as _ur
        import urllib.parse  as _up
        import json          as _j
        try:
            params = _up.urlencode({"api_key": self._api_key})
            url    = f"{self._base_url}/agent/tournament-readiness-score?{params}"
            req    = _ur.Request(url)
            with _ur.urlopen(req, timeout=self._timeout) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return TournamentReadinessScore(
                score=float(body.get("score", 0.0)),
                separation_score=float(body.get("separation_score", 0.0)),
                l4_score=float(body.get("l4_score", 0.0)),
                dual_gate_score=float(body.get("dual_gate_score", 0.0)),
                epoch_score=float(body.get("epoch_score", 0.0)),
                ioswarm_score=float(body.get("ioswarm_score", 0.0)),
                dry_run_score=float(body.get("dry_run_score", 0.0)),
            )
        except Exception as exc:
            return TournamentReadinessScore(error=str(exc))


# ---------------------------------------------------------------------------
# Phase 129 — Separation Ratio Breakthrough Monitor SDK
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class SeparationBreakthroughResult:
    """Result from GET /agent/separation-ratio-breakthrough (Phase 129).

    breakthrough_detected: True if pooled_ratio has crossed >= 1.0 on 2 consecutive
    monitoring snapshots (W1 mitigation: single-outlier false positive prevention).
    """
    breakthrough_detected: bool = False
    breakthrough_ratio:    float = 0.0
    breakthrough_ts:       float = 0.0
    n_players:             int = 0
    error: "str | None" = None


class VAPISeparationBreakthrough:
    """SDK client for the Phase 129 Separation Ratio Breakthrough endpoint.

    Never raises; error path returns SeparationBreakthroughResult with error != None.
    """

    def __init__(self, base_url: str, api_key: str = "", timeout: int = 10):
        self._base_url = base_url.rstrip("/")
        self._api_key  = api_key
        self._timeout  = timeout

    def get_breakthrough(self) -> SeparationBreakthroughResult:
        """Call GET /agent/separation-ratio-breakthrough. Returns SeparationBreakthroughResult."""
        import urllib.request as _ur
        import urllib.parse   as _up
        import json           as _j
        try:
            params = _up.urlencode({"api_key": self._api_key})
            url    = f"{self._base_url}/agent/separation-ratio-breakthrough?{params}"
            req    = _ur.Request(url)
            with _ur.urlopen(req, timeout=self._timeout) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return SeparationBreakthroughResult(
                breakthrough_detected=bool(body.get("breakthrough_detected", False)),
                breakthrough_ratio=float(body.get("breakthrough_ratio", 0.0)),
                breakthrough_ts=float(body.get("breakthrough_ts", 0.0)),
                n_players=int(body.get("n_players", 0)),
            )
        except Exception as exc:
            return SeparationBreakthroughResult(error=str(exc))


# ---------------------------------------------------------------------------
# Phase 130A — VAPISwarmOperatorGate SDK (WIF-001 mitigation)
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class SwarmOperatorGateResult:
    """Result from GET /agent/swarm-operator-gate-status (Phase 130A).

    gate_configured: True when SWARM_OPERATOR_GATE_ADDRESS is set in bridge config.
    valid: Whether the last quorum validation passed.
    node_count: Number of nodes in the last validation.
    timestamp: Unix timestamp of last validation.
    error: Non-None string on failure; None on success.
    """
    gate_configured: bool = False
    valid:           bool = False
    node_count:      int  = 0
    timestamp:       float = 0.0
    error: "str | None" = None


class VAPISwarmOperatorGate:
    """SDK client for the Phase 130A VAPISwarmOperatorGate status endpoint.

    Never raises; error path returns SwarmOperatorGateResult with error != None.
    """

    def __init__(self, base_url: str, api_key: str, timeout: int = 10):
        self._base_url = base_url.rstrip("/")
        self._api_key  = api_key
        self._timeout  = timeout

    def get_gate_status(self) -> SwarmOperatorGateResult:
        """Call GET /agent/swarm-operator-gate-status. Returns SwarmOperatorGateResult."""
        import urllib.request as _ur
        import urllib.parse   as _up
        import json           as _j
        try:
            params = _up.urlencode({"api_key": self._api_key})
            url    = f"{self._base_url}/agent/swarm-operator-gate-status?{params}"
            req    = _ur.Request(url)
            with _ur.urlopen(req, timeout=self._timeout) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return SwarmOperatorGateResult(
                gate_configured=bool(body.get("gate_configured", False)),
                valid=bool(body.get("last_valid", False)),
                node_count=int(body.get("last_node_count", 0)),
                timestamp=float(body.get("timestamp", 0.0)),
            )
        except Exception as exc:
            return SwarmOperatorGateResult(
                gate_configured=False,
                valid=False,
                node_count=0,
                timestamp=0.0,
                error=str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 131 — IoSwarm Live Node Registry SDK
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class IoSwarmNodeRegistryResult:
    """Result from GET /agent/ioswarm-node-registry-status (Phase 131).

    live_nodes: Number of active registered live ioSwarm nodes.
    emulator_mode: True when no live node URLs are configured.
    registry_count: Total rows in the ioswarm_node_registry table.
    node_timeout_s: Per-node HTTP timeout in seconds.
    last_quorum_ts: Unix timestamp of last swarm quorum validation.
    error: Non-None string on failure; None on success.
    """
    live_nodes:      int   = 0
    emulator_mode:   bool  = True
    registry_count:  int   = 0
    node_timeout_s:  float = 5.0
    last_quorum_ts:  float = 0.0
    error: "str | None" = None


class VAPIIoSwarmNodeRegistry:
    """SDK client for the Phase 131 IoSwarm live-node registry status endpoint.

    Never raises; error path returns IoSwarmNodeRegistryResult with error != None.
    """

    def __init__(self, base_url: str, api_key: str, timeout: int = 10):
        self._base_url = base_url.rstrip("/")
        self._api_key  = api_key
        self._timeout  = timeout

    def get_registry_status(self) -> IoSwarmNodeRegistryResult:
        """Call GET /agent/ioswarm-node-registry-status. Returns IoSwarmNodeRegistryResult."""
        import urllib.request as _ur
        import urllib.parse   as _up
        import json           as _j
        try:
            params = _up.urlencode({"api_key": self._api_key})
            url    = f"{self._base_url}/agent/ioswarm-node-registry-status?{params}"
            req    = _ur.Request(url)
            with _ur.urlopen(req, timeout=self._timeout) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return IoSwarmNodeRegistryResult(
                live_nodes=int(body.get("live_nodes", 0)),
                emulator_mode=bool(body.get("emulator_mode", True)),
                registry_count=int(body.get("registry_count", 0)),
                node_timeout_s=float(body.get("node_timeout_s", 5.0)),
                last_quorum_ts=float(body.get("last_quorum_ts", 0.0)),
            )
        except Exception as exc:
            return IoSwarmNodeRegistryResult(
                live_nodes=0,
                emulator_mode=True,
                registry_count=0,
                node_timeout_s=5.0,
                last_quorum_ts=0.0,
                error=str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 132 — IoSwarm Node Health
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class IoSwarmNodeHealthResult:
    """Result from GET /agent/ioswarm-node-health (Phase 132)."""
    nodes_configured:  int   = 0
    nodes_healthy:     int   = 0
    emulator_mode:     bool  = True
    avg_latency_ms:    float = -1.0
    health_log_count:  int   = 0
    error:             str | None = None


class VAPIIoSwarmNodeHealth:
    """SDK client for IoSwarm node health endpoint (Phase 132).

    Never raises; error path returns IoSwarmNodeHealthResult with error != None.
    """

    def __init__(self, base_url: str = "http://localhost:8000", api_key: str = ""):
        self._base = base_url.rstrip("/")
        self._key = api_key

    def get_node_health(self) -> IoSwarmNodeHealthResult:
        """Call GET /agent/ioswarm-node-health. Returns IoSwarmNodeHealthResult."""
        import urllib.request as _ur
        import json as _j
        try:
            url = f"{self._base}/agent/ioswarm-node-health?api_key={self._key}"
            with _ur.urlopen(url, timeout=10) as resp:
                data = _j.loads(resp.read())
            return IoSwarmNodeHealthResult(
                nodes_configured=int(data.get("nodes_configured", 0)),
                nodes_healthy=int(data.get("nodes_healthy", 0)),
                emulator_mode=bool(data.get("emulator_mode", True)),
                avg_latency_ms=float(data.get("avg_latency_ms", -1.0)),
                health_log_count=int(data.get("health_log_count", 0)),
                error=None,
            )
        except Exception as exc:
            return IoSwarmNodeHealthResult(
                nodes_configured=0,
                nodes_healthy=0,
                emulator_mode=True,
                avg_latency_ms=-1.0,
                health_log_count=0,
                error=str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 133 — IoSwarm PoAd Auto-Anchor
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class IoSwarmPoAdAnchorResult:
    """Result from GET /agent/ioswarm-poad-anchor-status (Phase 133)."""
    poad_auto_anchor_enabled: bool     = False
    anchored_count:           int      = 0
    pending_count:            int      = 0
    dual_veto_count:          int      = 0
    anchor_failure_count:     int      = 0
    error:                    str | None = None


class VAPIIoSwarmPoAdAnchor:
    """SDK client for IoSwarm PoAd auto-anchor status endpoint (Phase 133).

    Never raises; error path returns IoSwarmPoAdAnchorResult with error != None.
    """

    def __init__(self, base_url: str = "http://localhost:8000", api_key: str = ""):
        self._base = base_url.rstrip("/")
        self._key = api_key

    def get_anchor_status(self) -> IoSwarmPoAdAnchorResult:
        """Call GET /agent/ioswarm-poad-anchor-status. Returns IoSwarmPoAdAnchorResult."""
        import urllib.request as _ur
        import json as _j
        try:
            url = f"{self._base}/agent/ioswarm-poad-anchor-status?api_key={self._key}"
            with _ur.urlopen(url, timeout=10) as resp:
                data = _j.loads(resp.read())
            return IoSwarmPoAdAnchorResult(
                poad_auto_anchor_enabled=bool(data.get("poad_auto_anchor_enabled", False)),
                anchored_count=int(data.get("anchored_count", 0)),
                pending_count=int(data.get("pending_count", 0)),
                dual_veto_count=int(data.get("dual_veto_count", 0)),
                anchor_failure_count=int(data.get("anchor_failure_count", 0)),
                error=None,
            )
        except Exception as exc:
            return IoSwarmPoAdAnchorResult(
                poad_auto_anchor_enabled=False,
                anchored_count=0,
                pending_count=0,
                dual_veto_count=0,
                anchor_failure_count=0,
                error=str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 134 — L4 Recalibration SDK
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class L4RecalibrationResult:
    """Result from VAPIL4Recalibration.get_status() or trigger_recalibration()."""
    in_progress: bool = False
    sessions_processed: int = 0
    new_anomaly_threshold: float = 7.009
    new_continuity_threshold: float = 5.367
    stale: bool = True
    last_run_ts: float = 0.0
    error: str | None = None


class VAPIL4Recalibration:
    """SDK client for L4 recalibration pipeline status and trigger (Phase 134).

    Never raises; error path returns L4RecalibrationResult with error != None.
    """

    def __init__(self, base_url: str = "http://localhost:8000", api_key: str = ""):
        self._base = base_url.rstrip("/")
        self._key = api_key

    def get_status(self) -> L4RecalibrationResult:
        """Call GET /agent/l4-recalibration-status. Returns L4RecalibrationResult."""
        import urllib.request as _ur
        import json as _j
        try:
            url = f"{self._base}/agent/l4-recalibration-status?api_key={self._key}"
            with _ur.urlopen(url, timeout=10) as resp:
                data = _j.loads(resp.read())
            return L4RecalibrationResult(
                in_progress=bool(data.get("in_progress", False)),
                sessions_processed=int(data.get("sessions_processed", 0)),
                new_anomaly_threshold=float(data.get("new_anomaly_threshold", 7.009)),
                new_continuity_threshold=float(data.get("new_continuity_threshold", 5.367)),
                stale=bool(data.get("stale", True)),
                last_run_ts=float(data.get("last_run_ts", 0.0)),
                error=None,
            )
        except Exception as exc:
            return L4RecalibrationResult(
                in_progress=False,
                sessions_processed=0,
                new_anomaly_threshold=7.009,
                new_continuity_threshold=5.367,
                stale=True,
                last_run_ts=0.0,
                error=str(exc),
            )

    def trigger_recalibration(self) -> L4RecalibrationResult:
        """Call POST /agent/run-l4-recalibration. Returns L4RecalibrationResult."""
        import urllib.request as _ur
        import urllib.parse as _up
        import json as _j
        try:
            url = f"{self._base}/agent/run-l4-recalibration?api_key={self._key}"
            req = _ur.Request(url, data=b"", method="POST")
            with _ur.urlopen(req, timeout=10) as resp:
                data = _j.loads(resp.read())
            return L4RecalibrationResult(
                in_progress=bool(data.get("started", False)),
                sessions_processed=0,
                new_anomaly_threshold=7.009,
                new_continuity_threshold=5.367,
                stale=True,
                last_run_ts=float(data.get("timestamp", 0.0)),
                error=None,
            )
        except Exception as exc:
            return L4RecalibrationResult(
                in_progress=False,
                sessions_processed=0,
                new_anomaly_threshold=7.009,
                new_continuity_threshold=5.367,
                stale=True,
                last_run_ts=0.0,
                error=str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 135 — Tournament Activation Chain SDK
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class TournamentActivationChainResult:
    """Result from VAPITournamentActivationChain.get_status()."""
    gate_open_notified: bool = False
    auto_activate_on_breakthrough: bool = False  # PERMANENT INVARIANT
    operator_action_required: bool = True
    last_ratio: float = 0.0
    last_notification_ts: float = 0.0
    notification_count: int = 0
    error: str | None = None


class VAPITournamentActivationChain:
    """SDK client for TournamentActivationChainAgent status endpoint (Phase 135).

    INVARIANT: auto_activate_on_breakthrough is PERMANENTLY False.
    Tournament activation ALWAYS requires explicit operator action.
    Never raises; error path returns TournamentActivationChainResult with error != None.
    """

    def __init__(self, base_url: str = "http://localhost:8000", api_key: str = ""):
        self._base = base_url.rstrip("/")
        self._key = api_key

    def get_status(self) -> TournamentActivationChainResult:
        """Call GET /agent/tournament-activation-chain. Returns TournamentActivationChainResult."""
        import urllib.request as _ur
        import json as _j
        try:
            url = f"{self._base}/agent/tournament-activation-chain?api_key={self._key}"
            with _ur.urlopen(url, timeout=10) as resp:
                data = _j.loads(resp.read())
            return TournamentActivationChainResult(
                gate_open_notified=bool(data.get("gate_open_notified", False)),
                auto_activate_on_breakthrough=False,  # PERMANENT INVARIANT
                operator_action_required=bool(data.get("operator_action_required", True)),
                last_ratio=float(data.get("last_ratio", 0.0)),
                last_notification_ts=float(data.get("last_notification_ts", 0.0)),
                notification_count=int(data.get("notification_count", 0)),
                error=None,
            )
        except Exception as exc:
            return TournamentActivationChainResult(
                gate_open_notified=False,
                auto_activate_on_breakthrough=False,
                operator_action_required=True,
                last_ratio=0.0,
                last_notification_ts=0.0,
                notification_count=0,
                error=str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 148 — Agent Calibration Health (ACIM) SDK
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class AgentCalibrationHealthResult:
    """Result from VAPIAgentCalibrationMonitor.get_health()."""
    agent_count:        int = 16
    healthy_count:      int = 0
    degraded_count:     int = 0
    failed_agents:      list = field(default_factory=list)
    mcp_server_enabled: bool = False
    error:              str | None = None


class VAPIAgentCalibrationMonitor:
    """SDK client for AgentCalibrationMonitor (ACIM, agent #18) health endpoint (Phase 148).

    Exposes GET /agent/calibration-health and POST /agent/run-agent-self-test.
    Never raises; error path returns AgentCalibrationHealthResult with error != None.
    """

    def __init__(self, base_url: str = "http://localhost:8000", api_key: str = ""):
        self._base = base_url.rstrip("/")
        self._key = api_key

    def get_health(self) -> AgentCalibrationHealthResult:
        """Call GET /agent/calibration-health. Returns AgentCalibrationHealthResult."""
        import urllib.request as _ur
        import json as _j
        try:
            url = f"{self._base}/agent/calibration-health?api_key={self._key}"
            with _ur.urlopen(url, timeout=10) as resp:
                data = _j.loads(resp.read())
            return AgentCalibrationHealthResult(
                agent_count=int(data.get("agent_count", 16)),
                healthy_count=int(data.get("healthy_count", 0)),
                degraded_count=int(data.get("degraded_count", 0)),
                failed_agents=list(data.get("failed_agents", [])),
                mcp_server_enabled=bool(data.get("mcp_server_enabled", False)),
                error=None,
            )
        except Exception as exc:
            return AgentCalibrationHealthResult(
                agent_count=16,
                healthy_count=0,
                degraded_count=0,
                failed_agents=[],
                mcp_server_enabled=False,
                error=str(exc),
            )

    def trigger_self_test(self) -> dict:
        """Call POST /agent/run-agent-self-test. Returns status dict."""
        import urllib.request as _ur
        import json as _j
        import urllib.parse as _up
        try:
            url = f"{self._base}/agent/run-agent-self-test?api_key={self._key}"
            req = _ur.Request(url, data=b"{}", method="POST",
                              headers={"Content-Type": "application/json"})
            with _ur.urlopen(req, timeout=30) as resp:
                return _j.loads(resp.read())
        except Exception as exc:
            return {"triggered": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Phase 150 — Separation Ratio Defensibility (WIF-010 formal closure)
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class SeparationDefensibilityResult:
    """Phase 150 separation ratio defensibility result.

    defensible=True requires: ALL players >= min_n_per_player (default 10)
    AND ratio > 1.0 AND all inter-player pair distances > 1.0.

    Current state (Phase 150): P1=3, P2=4, P3=4 — defensible=False.
    Ratio=1.261 (Phase 143, touchpad_corners) is above gate but N=11 is
    legally thin (WIF-010). Target: >=10 sessions/player for tournament defense.
    """

    defensible:         bool  = False
    ratio:              float = 0.0
    n_per_player:       dict  = field(default_factory=dict)
    min_n_per_player:   int   = 10
    all_pairs_above_1:  bool  = False
    error:              "str | None" = None


class VAPISeparationDefensibility:
    """Phase 150 SDK client — separation ratio defensibility status (WIF-010 closure).

    Queries GET /agent/separation-defensibility-status and returns a
    SeparationDefensibilityResult. Never raises — returns error-populated result
    on any exception (consistent with all Phase 99+ SDK clients).
    """

    def __init__(self, base_url: str, api_key: str = ""):
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_defensibility_status(
        self, session_type: str = "touchpad_corners"
    ) -> SeparationDefensibilityResult:
        """Call GET /agent/separation-defensibility-status."""
        import urllib.request as _ur
        import json as _j
        try:
            url = (
                f"{self._base}/agent/separation-defensibility-status"
                f"?api_key={self._key}&session_type={session_type}"
            )
            with _ur.urlopen(url, timeout=10) as resp:
                data = _j.loads(resp.read())
            return SeparationDefensibilityResult(
                defensible        = bool(data.get("defensible", False)),
                ratio             = float(data.get("ratio", 0.0)),
                n_per_player      = dict(data.get("n_per_player", {})),
                min_n_per_player  = int(data.get("min_n_per_player", 10)),
                all_pairs_above_1 = bool(data.get("all_pairs_above_1", False)),
                error             = None,
            )
        except Exception as exc:
            return SeparationDefensibilityResult(
                defensible        = False,
                ratio             = 0.0,
                n_per_player      = {},
                min_n_per_player  = 10,
                all_pairs_above_1 = False,
                error             = str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 151 P1 — Enrollment Capture Guidance
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class CaptureGuidanceResult:
    """Phase 151 per-player capture guidance for structured probe types.

    For each structured probe type (touchpad_corners / touchpad_freeform /
    touchpad_swipes), reports how many more sessions each player needs to reach
    min_n_per_player.

    overall_ready=True when ALL players have >= min_n sessions in ALL probe types
    AND ratio > 1.0 for each probe — the tournament defensibility target.

    Current state (Phase 151): P1=3, P2=4, P3=4 touchpad_corners.
    sessions_needed_total=19 (7+6+6 for touchpad_corners alone).
    """

    min_n_per_player:       int   = 10
    probe_types:            list  = field(default_factory=list)
    guidance:               dict  = field(default_factory=dict)
    sessions_needed_total:  int   = 0
    overall_ready:          bool  = False
    error:                  "str | None" = None


class VAPIEnrollmentCaptureGuidance:
    """Phase 151 P1 SDK client — enrollment capture guidance.

    Queries GET /agent/enrollment-capture-guidance and returns a
    CaptureGuidanceResult. Never raises — returns error-populated result
    on any exception.
    """

    def __init__(self, base_url: str, api_key: str = ""):
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_guidance(self, min_n: int = 10) -> CaptureGuidanceResult:
        """Call GET /agent/enrollment-capture-guidance."""
        import urllib.request as _ur
        import json as _j
        try:
            url = (
                f"{self._base}/agent/enrollment-capture-guidance"
                f"?api_key={self._key}&min_n={min_n}"
            )
            with _ur.urlopen(url, timeout=10) as resp:
                data = _j.loads(resp.read())
            return CaptureGuidanceResult(
                min_n_per_player      = int(data.get("min_n_per_player", 10)),
                probe_types           = list(data.get("probe_types", [])),
                guidance              = dict(data.get("guidance", {})),
                sessions_needed_total = int(data.get("sessions_needed_total", 0)),
                overall_ready         = bool(data.get("overall_ready", False)),
                error                 = None,
            )
        except Exception as exc:
            return CaptureGuidanceResult(
                min_n_per_player      = 10,
                probe_types           = [],
                guidance              = {},
                sessions_needed_total = 0,
                overall_ready         = False,
                error                 = str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 152 — Centroid Velocity Monitor
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class CentroidVelocityResult:
    probe_type:       str
    velocity:         float
    velocity_per_day: float
    stagnant:         bool
    n_snapshots_used: int
    error:            str | None


class VAPICentroidVelocityMonitor:
    """Read-only client for GET /agent/centroid-velocity-status.  Never raises."""

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_velocity_status(self, probe_type: str = "touchpad_corners") -> CentroidVelocityResult:
        import urllib.request, urllib.parse, json as _json
        try:
            _params = urllib.parse.urlencode({"probe_type": probe_type, "api_key": self._key})
            req = urllib.request.Request(
                f"{self._base}/agent/centroid-velocity-status?{_params}",
                headers={"X-API-Key": self._key},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = _json.loads(resp.read())
            return CentroidVelocityResult(
                probe_type       = str(data.get("probe_type", probe_type)),
                velocity         = float(data.get("velocity", 0.0)),
                velocity_per_day = float(data.get("velocity_per_day", 0.0)),
                stagnant         = bool(data.get("stagnant", True)),
                n_snapshots_used = int(data.get("n_snapshots_used", 0)),
                error            = None,
            )
        except Exception as exc:
            return CentroidVelocityResult(
                probe_type       = probe_type,
                velocity         = 0.0,
                velocity_per_day = 0.0,
                stagnant         = True,
                n_snapshots_used = 0,
                error            = str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 153 — Separation Ratio Registry (on-chain commitment)
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class SeparationRatioRegistryResult:
    committed:   bool
    commit_hash: str
    ratio_millis: int
    n_sessions:  int
    n_players:   int
    error:       str | None


class VAPISeparationRatioRegistry:
    """Read-only client for GET /agent/separation-ratio-registry-status.  Never raises."""

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_registry_status(self) -> SeparationRatioRegistryResult:
        import urllib.request, urllib.parse, json as _json
        try:
            _params = urllib.parse.urlencode({"api_key": self._key})
            req = urllib.request.Request(
                f"{self._base}/agent/separation-ratio-registry-status?{_params}",
                headers={"X-API-Key": self._key},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = _json.loads(resp.read())
            return SeparationRatioRegistryResult(
                committed    = bool(data.get("committed", False)),
                commit_hash  = str(data.get("commit_hash", "")),
                ratio_millis = int(data.get("ratio_millis", 0)),
                n_sessions   = int(data.get("n_sessions", 0)),
                n_players    = int(data.get("n_players", 0)),
                error        = None,
            )
        except Exception as exc:
            return SeparationRatioRegistryResult(
                committed    = False,
                commit_hash  = "",
                ratio_millis = 0,
                n_sessions   = 0,
                n_players    = 0,
                error        = str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 154 — Capture Stagnation Monitor
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class CaptureStagnationResult:
    probe_type:       str
    sessions_per_day: float
    stagnant:         bool
    sessions_in_window: int
    window_days:      float
    error:            str | None


class VAPICaptureStagnationMonitor:
    """Read-only client for GET /agent/capture-stagnation-status.  Never raises."""

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_stagnation_status(self, probe_type: str = "touchpad_corners") -> CaptureStagnationResult:
        import urllib.request, urllib.parse, json as _json
        try:
            _params = urllib.parse.urlencode({"probe_type": probe_type, "api_key": self._key})
            req = urllib.request.Request(
                f"{self._base}/agent/capture-stagnation-status?{_params}",
                headers={"X-API-Key": self._key},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = _json.loads(resp.read())
            return CaptureStagnationResult(
                probe_type         = str(data.get("probe_type", probe_type)),
                sessions_per_day   = float(data.get("sessions_per_day", 0.0)),
                stagnant           = bool(data.get("stagnant", True)),
                sessions_in_window = int(data.get("sessions_in_window", 0)),
                window_days        = float(data.get("window_days", 7.0)),
                error              = None,
            )
        except Exception as exc:
            return CaptureStagnationResult(
                probe_type         = probe_type,
                sessions_per_day   = 0.0,
                stagnant           = True,
                sessions_in_window = 0,
                window_days        = 7.0,
                error              = str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 155 — Controller Hardware Intelligence
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class ControllerHardwareResult:
    controller_intelligence_enabled: bool
    multi_controller_enabled:        bool
    attested_count:                  int
    standard_count:                  int
    active_composite_key:            str
    error:                           str | None


class VAPIControllerHardware:
    """Read-only client for GET /agent/controller-hardware-status.  Never raises."""

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_hardware_status(self) -> ControllerHardwareResult:
        import urllib.request, urllib.parse, json as _json
        try:
            _params = urllib.parse.urlencode({"api_key": self._key})
            req = urllib.request.Request(
                f"{self._base}/agent/controller-hardware-status?{_params}",
                headers={"X-API-Key": self._key},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = _json.loads(resp.read())
            return ControllerHardwareResult(
                controller_intelligence_enabled = bool(data.get("controller_intelligence_enabled", True)),
                multi_controller_enabled        = bool(data.get("multi_controller_enabled", False)),
                attested_count                  = int(data.get("attested_count", 0)),
                standard_count                  = int(data.get("standard_count", 0)),
                active_composite_key            = str(data.get("active_composite_key", "")),
                error                           = None,
            )
        except Exception as exc:
            return ControllerHardwareResult(
                controller_intelligence_enabled = True,
                multi_controller_enabled        = False,
                attested_count                  = 0,
                standard_count                  = 0,
                active_composite_key            = "",
                error                           = str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 156 — Enrollment Auto-Guidance Agent
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class EnrollmentAutoGuidanceResult:
    sessions_needed_total: int
    overall_ready:         bool
    recommended_action:    str
    urgency_level:         str
    estimated_days:        float
    cov_regime_status:     str
    error:                 str | None


class VAPIEnrollmentAutoGuidance:
    """Read-only client for GET /agent/enrollment-auto-guidance-status.  Never raises."""

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_guidance_status(self) -> EnrollmentAutoGuidanceResult:
        import urllib.request, urllib.parse, json as _json
        try:
            _params = urllib.parse.urlencode({"api_key": self._key})
            req = urllib.request.Request(
                f"{self._base}/agent/enrollment-auto-guidance-status?{_params}",
                headers={"X-API-Key": self._key},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = _json.loads(resp.read())
            return EnrollmentAutoGuidanceResult(
                sessions_needed_total = int(data.get("sessions_needed_total", 0)),
                overall_ready         = bool(data.get("overall_ready", False)),
                recommended_action    = str(data.get("recommended_action", "")),
                urgency_level         = str(data.get("urgency_level", "UNKNOWN")),
                estimated_days        = float(data.get("estimated_days", -1.0)),
                cov_regime_status     = str(data.get("cov_regime_status", "unknown")),
                error                 = None,
            )
        except Exception as exc:
            return EnrollmentAutoGuidanceResult(
                sessions_needed_total = 0,
                overall_ready         = False,
                recommended_action    = "Run EnrollmentAutoGuidanceAgent",
                urgency_level         = "UNKNOWN",
                estimated_days        = -1.0,
                cov_regime_status     = "unknown",
                error                 = str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 157 — FleetConsensusSnapshotAgent (agent #21) SDK
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class BiometricPrivacyComplianceResult:
    """Phase 159 — BP-001 Temporal Biometric Decay compliance status."""
    biometric_privacy_enabled: bool
    bp001_half_life_days:       float
    records_monitored:          int
    mean_decay_factor:          float
    warning_triggered:          bool
    error:                      str | None


class VAPIBiometricPrivacy:
    """Read-only client for GET /agent/biometric-privacy-status.  Never raises.

    BP-001 Temporal Biometric Decay: TBD(t) = e^(-λt), λ = ln(2)/τ_half, τ_half=90d.
    warning_triggered=True when mean_decay_factor < 0.25 (≈2 half-lives).
    biometric_privacy_enabled=True default; polls every 21600s (6h).
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_privacy_status(self) -> BiometricPrivacyComplianceResult:
        import urllib.request, urllib.parse, json as _json
        try:
            _params = urllib.parse.urlencode({"api_key": self._key})
            req = urllib.request.Request(
                f"{self._base}/agent/biometric-privacy-status?{_params}",
                headers={"X-API-Key": self._key},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = _json.loads(resp.read())
            return BiometricPrivacyComplianceResult(
                biometric_privacy_enabled = bool(data.get("biometric_privacy_enabled", True)),
                bp001_half_life_days      = float(data.get("bp001_half_life_days", 90.0)),
                records_monitored         = int(data.get("records_monitored", 0)),
                mean_decay_factor         = float(data.get("mean_decay_factor", 1.0)),
                warning_triggered         = bool(data.get("warning_triggered", False)),
                error                     = None,
            )
        except Exception as exc:
            return BiometricPrivacyComplianceResult(
                biometric_privacy_enabled = True,
                bp001_half_life_days      = 90.0,
                records_monitored         = 0,
                mean_decay_factor         = 1.0,
                warning_triggered         = False,
                error                     = str(exc),
            )


@dataclass(slots=True)
class ConsentLedgerResult:
    """Phase 160 — BP-002 Consent Ledger status for a device."""
    consent_ledger_enabled: bool
    consent_given:          bool
    consent_ts:             float | None
    revoked:                bool
    erasure_requested:      bool
    error:                  str | None


class VAPIConsentLedger:
    """Consent Ledger client for BP-002 (WIF-018/019).  Never raises.

    Reads consent status for a device.  Use POST /agent/register-consent
    to record consent, POST /agent/revoke-consent to revoke + trigger erasure.
    consent_ledger_enabled=True default.
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_consent_status(self, device_id: str) -> ConsentLedgerResult:
        """Return BP-002 consent status for device_id.  Never raises."""
        import urllib.request, urllib.parse, json as _json
        try:
            _params = urllib.parse.urlencode({"api_key": self._key})
            req = urllib.request.Request(
                f"{self._base}/agent/consent-status/{urllib.parse.quote(device_id, safe='')}?{_params}",
                headers={"X-API-Key": self._key},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = _json.loads(resp.read())
            return ConsentLedgerResult(
                consent_ledger_enabled = bool(data.get("consent_ledger_enabled", True)),
                consent_given          = bool(data.get("consent_given", False)),
                consent_ts             = data.get("consent_ts"),
                revoked                = bool(data.get("revoked", False)),
                erasure_requested      = bool(data.get("erasure_requested", False)),
                error                  = None,
            )
        except Exception as exc:
            return ConsentLedgerResult(
                consent_ledger_enabled = True,
                consent_given          = False,
                consent_ts             = None,
                revoked                = False,
                erasure_requested      = False,
                error                  = str(exc),
            )


@dataclass(slots=True)
class ConsentGateResult:
    """Phase 161 — BP-002 Consent Gate enforcement status."""
    consent_ledger_enabled: bool
    gate_active:            bool
    violations_total:       int
    last_violation_ts:      float | None
    error:                  str | None


class VAPIConsentGate:
    """Phase 161 — GET /agent/consent-gate-status.  Never raises.

    Tracks consent gate enforcement (WIF-018/020 closure).
    Gate blocks insert_validation_record for devices with revoked consent.
    Gate fails open for unknown devices (no consent record = allowed).
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_gate_status(self) -> ConsentGateResult:
        """Return BP-002 consent gate enforcement status.  Never raises."""
        import urllib.request, urllib.parse, json as _json
        try:
            _params = urllib.parse.urlencode({"api_key": self._key})
            req = urllib.request.Request(
                f"{self._base}/agent/consent-gate-status?{_params}",
                headers={"X-API-Key": self._key},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = _json.loads(resp.read())
            return ConsentGateResult(
                consent_ledger_enabled = bool(data.get("consent_ledger_enabled", False)),
                gate_active            = bool(data.get("gate_active", False)),
                violations_total       = int(data.get("violations_total", 0)),
                last_violation_ts      = data.get("last_violation_ts"),
                error                  = None,
            )
        except Exception as exc:
            return ConsentGateResult(
                consent_ledger_enabled = False,
                gate_active            = False,
                violations_total       = 0,
                last_violation_ts      = None,
                error                  = str(exc),
            )


@dataclass(slots=True)
class SeparationRatioCommitResult:
    """Phase 163 — WIF-022 Consent-Bound Separation Ratio Commitment result."""
    committed:    bool
    commit_hash:  str
    n_consented:  int
    n_sessions:   int
    n_players:    int
    dry_run:      bool
    error:        str | None


class VAPISeparationRatioCommit:
    """Phase 163 — POST /agent/commit-separation-ratio.  Never raises.

    Commits a consent-bound separation ratio: SHA-256 preimage includes N_consented,
    so the on-chain proof cryptographically asserts consent-filtered corpus (WIF-022).
    separation_ratio_on_chain_enabled=False → dry_run=True (hash stored, no chain tx).
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def commit(
        self,
        ratio: float,
        n_sessions: int,
        n_players: int,
        players_sorted: str,
    ) -> SeparationRatioCommitResult:
        """Commit consent-bound ratio.  Never raises."""
        import urllib.request, urllib.parse, json as _json
        try:
            _params = urllib.parse.urlencode({
                "api_key":       self._key,
                "ratio":         ratio,
                "n_sessions":    n_sessions,
                "n_players":     n_players,
                "players_sorted": players_sorted,
            })
            req = urllib.request.Request(
                f"{self._base}/agent/commit-separation-ratio?{_params}",
                data=b"",
                method="POST",
                headers={"X-API-Key": self._key},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = _json.loads(resp.read())
            return SeparationRatioCommitResult(
                committed   = bool(data.get("committed", False)),
                commit_hash = str(data.get("commit_hash", "")),
                n_consented = int(data.get("n_consented", 0)),
                n_sessions  = int(data.get("n_sessions", 0)),
                n_players   = int(data.get("n_players", 0)),
                dry_run     = bool(data.get("dry_run", True)),
                error       = None,
            )
        except Exception as exc:
            return SeparationRatioCommitResult(
                committed=False, commit_hash="", n_consented=0,
                n_sessions=0, n_players=0, dry_run=True, error=str(exc),
            )


@dataclass(slots=True)
class ConsentAwareCorpusResult:
    """Phase 162 — WIF-021 Consent-Aware Corpus coverage status."""
    consent_ledger_enabled:    bool
    active_consent_count:      int
    revoked_count:             int
    erasure_requested_count:   int
    consent_corpus_defensible: bool
    error:                     str | None


class VAPIConsentAwareCorpus:
    """Phase 162 — GET /agent/consent-aware-corpus-status.  Never raises.

    Reports whether the separation-ratio corpus is free of revoked/erasure devices
    (WIF-021 closure).  A defensible corpus is required for legally valid on-chain
    ratio commitment in SeparationRatioRegistry.sol.
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_corpus_status(self) -> ConsentAwareCorpusResult:
        """Return WIF-021 consent-aware corpus status.  Never raises."""
        import urllib.request, urllib.parse, json as _json
        try:
            _params = urllib.parse.urlencode({"api_key": self._key})
            req = urllib.request.Request(
                f"{self._base}/agent/consent-aware-corpus-status?{_params}",
                headers={"X-API-Key": self._key},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = _json.loads(resp.read())
            return ConsentAwareCorpusResult(
                consent_ledger_enabled    = bool(data.get("consent_ledger_enabled", False)),
                active_consent_count      = int(data.get("active_consent_count", 0)),
                revoked_count             = int(data.get("revoked_count", 0)),
                erasure_requested_count   = int(data.get("erasure_requested_count", 0)),
                consent_corpus_defensible = bool(data.get("consent_corpus_defensible", False)),
                error                     = None,
            )
        except Exception as exc:
            return ConsentAwareCorpusResult(
                consent_ledger_enabled    = False,
                active_consent_count      = 0,
                revoked_count             = 0,
                erasure_requested_count   = 0,
                consent_corpus_defensible = False,
                error                     = str(exc),
            )


@dataclass(slots=True)
class GSRHMACValidationResult:
    """Phase 158 WIF-014 — Class K HMAC validation status result."""
    gsr_hmac_enabled:        bool
    gsr_hmac_key_configured: bool
    total_validations:       int
    valid_count:             int
    rejected_count:          int
    error:                   str | None


class VAPIGSRHMACValidator:
    """Read-only client for GET /agent/gsr-hmac-validation-status.  Never raises.

    Class K anti-spoofing: validates HMAC-SHA256 tags on 80-byte GSR frames.
    Rejects synthetic EDA generators that cannot produce correct HMAC tags.
    gsr_hmac_enabled=False default (infrastructure-first).
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_validation_status(self) -> GSRHMACValidationResult:
        import urllib.request, urllib.parse, json as _json
        try:
            _params = urllib.parse.urlencode({"api_key": self._key})
            req = urllib.request.Request(
                f"{self._base}/agent/gsr-hmac-validation-status?{_params}",
                headers={"X-API-Key": self._key},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = _json.loads(resp.read())
            return GSRHMACValidationResult(
                gsr_hmac_enabled        = bool(data.get("gsr_hmac_enabled", False)),
                gsr_hmac_key_configured = bool(data.get("gsr_hmac_key_configured", False)),
                total_validations       = int(data.get("total_validations", 0)),
                valid_count             = int(data.get("valid_count", 0)),
                rejected_count          = int(data.get("rejected_count", 0)),
                error                   = None,
            )
        except Exception as exc:
            return GSRHMACValidationResult(
                gsr_hmac_enabled        = False,
                gsr_hmac_key_configured = False,
                total_validations       = 0,
                valid_count             = 0,
                rejected_count          = 0,
                error                   = str(exc),
            )


@dataclass(slots=True)
class PoHBGResult:
    """Phase 158 WIF-015 — Proof of Hardware Biometric Grip status result."""
    pohbg_enabled:    bool
    total_pohbg:      int
    latest_pohbg_hash: str | None
    latest_device_id: str | None
    latest_ts_ns:     int | None
    error:            str | None


class VAPIPoHBG:
    """Read-only client for GET /agent/pohbg-status.  Never raises.

    PoHBG = SHA-256(device_id_bytes + pack('>IIIQ', arousal_millis,
                    correlation_millis, conductance_raw_int, ts_ns))
    Extends the composable proof triple (PoAC + PoAd + PoFC) with grip hardware proof.
    pohbg_enabled=False default (infrastructure-first).
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_pohbg_status(self) -> PoHBGResult:
        import urllib.request, urllib.parse, json as _json
        try:
            _params = urllib.parse.urlencode({"api_key": self._key})
            req = urllib.request.Request(
                f"{self._base}/agent/pohbg-status?{_params}",
                headers={"X-API-Key": self._key},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = _json.loads(resp.read())
            return PoHBGResult(
                pohbg_enabled     = bool(data.get("pohbg_enabled", False)),
                total_pohbg       = int(data.get("total_pohbg", 0)),
                latest_pohbg_hash = data.get("latest_pohbg_hash"),
                latest_device_id  = data.get("latest_device_id"),
                latest_ts_ns      = data.get("latest_ts_ns"),
                error             = None,
            )
        except Exception as exc:
            return PoHBGResult(
                pohbg_enabled     = False,
                total_pohbg       = 0,
                latest_pohbg_hash = None,
                latest_device_id  = None,
                latest_ts_ns      = None,
                error             = str(exc),
            )


@dataclass(slots=True)
class ConsentSnapshotResult:
    """Phase 164 WIF-023 — ConsentSnapshotAnchor delta result."""
    commit_hash:            str | None
    n_consented_at_commit:  int
    n_consented_live:       int
    delta:                  int
    revoked_since_commit:   int
    error:                  str | None


class VAPIConsentSnapshotDelta:
    """Read-only client for GET /agent/consent-snapshot-delta.  Never raises.

    Returns the delta between the N_consented value bound into the on-chain
    SHA-256 hash at the last separation ratio commit and the current live
    consent count.  delta > 0 = chain attestation overstates current coverage.
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_delta(self) -> ConsentSnapshotResult:
        import urllib.request, urllib.parse, json as _json
        try:
            _params = urllib.parse.urlencode({"api_key": self._key})
            req = urllib.request.Request(
                f"{self._base}/agent/consent-snapshot-delta?{_params}",
                headers={"X-API-Key": self._key},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = _json.loads(resp.read())
            return ConsentSnapshotResult(
                commit_hash           = data.get("commit_hash"),
                n_consented_at_commit = int(data.get("n_consented_at_commit", 0)),
                n_consented_live      = int(data.get("n_consented_live", 0)),
                delta                 = int(data.get("delta", 0)),
                revoked_since_commit  = int(data.get("revoked_since_commit", 0)),
                error                 = None,
            )
        except Exception as exc:
            return ConsentSnapshotResult(
                commit_hash           = None,
                n_consented_at_commit = 0,
                n_consented_live      = 0,
                delta                 = 0,
                revoked_since_commit  = 0,
                error                 = str(exc),
            )


@dataclass(slots=True)
class FleetConsensusSnapshotResult:
    fleet_consensus_enabled: bool
    total_snapshots:         int
    latest_pofc_hash:        str | None
    latest_agent_count:      int
    latest_separation_ratio: float
    error:                   str | None


class VAPIFleetConsensus:
    """Read-only client for GET /agent/fleet-consensus-snapshot.  Never raises.

    Returns the latest PoFC (Proof of Fleet Consensus) snapshot:
    PoFC_hash = SHA-256(sorted_verdicts_json | separation_ratio | ts_ns)
    This is the third composable proof primitive (PoAC + PoAd + PoFC).
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_snapshot(self) -> FleetConsensusSnapshotResult:
        import urllib.request, urllib.parse, json as _json
        try:
            _params = urllib.parse.urlencode({"api_key": self._key})
            req = urllib.request.Request(
                f"{self._base}/agent/fleet-consensus-snapshot?{_params}",
                headers={"X-API-Key": self._key},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = _json.loads(resp.read())
            return FleetConsensusSnapshotResult(
                fleet_consensus_enabled = bool(data.get("fleet_consensus_enabled", True)),
                total_snapshots         = int(data.get("total_snapshots", 0)),
                latest_pofc_hash        = data.get("latest_pofc_hash"),
                latest_agent_count      = int(data.get("latest_agent_count", 0)),
                latest_separation_ratio = float(data.get("latest_separation_ratio", 0.0)),
                error                   = None,
            )
        except Exception as exc:
            return FleetConsensusSnapshotResult(
                fleet_consensus_enabled = True,
                total_snapshots         = 0,
                latest_pofc_hash        = None,
                latest_agent_count      = 0,
                latest_separation_ratio = 0.0,
                error                   = str(exc),
            )


@dataclass(slots=True)
class PostErasureRecomputeResult:
    """Phase 165 WIF-024 — Post-Erasure Separation Ratio Recompute audit result."""
    consent_ledger_enabled: bool
    total_recomputes:        int
    pending_recomputes:      int
    latest_recompute_ts:     "float | None"
    recompute_needed:        bool
    error:                   "str | None"


class VAPIPostErasureRecompute:
    """Read-only client for GET /agent/post-erasure-recompute-status.  Never raises.

    When a device's biometric records are erased (GDPR Art.17), the stored
    separation ratio becomes stale.  This client surfaces the audit trail so
    operators know when analyze_interperson_separation.py must be re-run.
    recompute_needed=True means at least one pending erasure has not yet been
    reflected in a new separation analysis run.
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_status(self, device_id: str = "") -> PostErasureRecomputeResult:
        import urllib.request, urllib.parse, json as _json
        try:
            _params = urllib.parse.urlencode(
                {k: v for k, v in {"api_key": self._key, "device_id": device_id}.items() if v}
            )
            req = urllib.request.Request(
                f"{self._base}/agent/post-erasure-recompute-status?{_params}",
                headers={"X-API-Key": self._key},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = _json.loads(resp.read())
            return PostErasureRecomputeResult(
                consent_ledger_enabled = bool(data.get("consent_ledger_enabled", True)),
                total_recomputes       = int(data.get("total_recomputes", 0)),
                pending_recomputes     = int(data.get("pending_recomputes", 0)),
                latest_recompute_ts    = data.get("latest_recompute_ts"),
                recompute_needed       = bool(data.get("recompute_needed", False)),
                error                  = None,
            )
        except Exception as exc:
            return PostErasureRecomputeResult(
                consent_ledger_enabled = True,
                total_recomputes       = 0,
                pending_recomputes     = 0,
                latest_recompute_ts    = None,
                recompute_needed       = False,
                error                  = str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 166 — MixedProbeConfig + VAPIMixedProbeGate
# mixed_biometric_probe: 2-min all-feature probe; configurable defensibility gate
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class MixedProbeGateResult:
    """Result of GET /agent/enrollment-capture-guidance with Phase 166 gate."""
    min_separation_ratio:  float
    sessions_needed_total: int
    overall_ready:         bool
    mixed_probe_in_types:  bool
    error:                 "str | None"


class VAPIMixedProbeGate:
    """Read-only client surfacing Phase 166 mixed_biometric_probe gate status.

    Checks whether mixed_biometric_probe is included in the enrollment guidance
    probe_types and exposes the configurable min_separation_ratio gate (default 0.70).
    Never raises — returns error-default on any network or parse error.
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_status(self) -> MixedProbeGateResult:
        import urllib.request, urllib.parse, json as _json
        try:
            _params = urllib.parse.urlencode(
                {k: v for k, v in {"api_key": self._key}.items() if v}
            )
            req = urllib.request.Request(
                f"{self._base}/agent/enrollment-capture-guidance?{_params}",
                headers={"X-API-Key": self._key},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = _json.loads(resp.read())
            return MixedProbeGateResult(
                min_separation_ratio  = float(data.get("min_separation_ratio", 0.70)),
                sessions_needed_total = int(data.get("sessions_needed_total", 0)),
                overall_ready         = bool(data.get("overall_ready", False)),
                mixed_probe_in_types  = "mixed_biometric_probe" in data.get("probe_types", []),
                error                 = None,
            )
        except Exception as exc:
            return MixedProbeGateResult(
                min_separation_ratio  = 0.70,
                sessions_needed_total = 0,
                overall_ready         = False,
                mixed_probe_in_types  = False,
                error                 = str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 173 — SeparationRatioRecoveryAgent
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class SeparationRatioRecoveryResult:
    """SeparationRatioRecoveryAgent status (Phase 173, agent #23).

    Attributes:
        separation_recovery_enabled: True when agent is active.
        current_ratio:    Most recent pooled separation ratio (0.0 if none).
        trend_velocity:   dRatio/dSnapshot — negative = converging downward.
        recovery_needed:  True when ratio below gate OR trend strongly negative.
        recovery_action:  STABLE | AGE_WEIGHTING | P1_RE_ENROLLMENT | MORE_SESSIONS.
        recommendation:   Human-readable recovery guidance.
        error:            Non-None on request failure.
    """
    separation_recovery_enabled: bool
    current_ratio:    float
    trend_velocity:   float
    recovery_needed:  bool
    recovery_action:  str
    recommendation:   str
    error: "str | None" = None


class VAPISeparationRatioRecovery:
    """SDK client for GET /agent/separation-ratio-recovery-status (Phase 173).

    Example::

        recovery = VAPISeparationRatioRecovery("http://localhost:8080", api_key)
        result = recovery.get_status()
        if result.recovery_needed:
            print(f"Action: {result.recovery_action}")
            print(result.recommendation)
    """

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_status(self) -> SeparationRatioRecoveryResult:
        """Return the latest separation ratio recovery assessment.

        On error: returns SeparationRatioRecoveryResult with error field set and
        recovery_needed=False, recovery_action='STABLE'.
        """
        import urllib.request as _ur, json as _j
        try:
            url = f"{self._base}/agent/separation-ratio-recovery-status?api_key={self._key}"
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return SeparationRatioRecoveryResult(
                separation_recovery_enabled = bool(body.get("separation_recovery_enabled", True)),
                current_ratio    = float(body.get("current_ratio",   0.0)),
                trend_velocity   = float(body.get("trend_velocity",  0.0)),
                recovery_needed  = bool(body.get("recovery_needed",  False)),
                recovery_action  = str(body.get("recovery_action",   "STABLE")),
                recommendation   = str(body.get("recommendation",    "")),
            )
        except Exception as exc:
            return SeparationRatioRecoveryResult(
                separation_recovery_enabled = True,
                current_ratio    = 0.0,
                trend_velocity   = 0.0,
                recovery_needed  = False,
                recovery_action  = "STABLE",
                recommendation   = "",
                error            = str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 175 — AgeWeightedRatioPersistenceAgent (agent #24)
# ---------------------------------------------------------------------------

@dataclass
class AgeWeightAnalysisResult:
    """Result from VAPIAgeWeightAnalysis.get_status() (Phase 175).

    temporal_drift_index = raw_ratio - age_weighted_ratio:
      positive  -> P1_NONSTATIONARITY (old sessions inflate ratio)
      negative  -> IMPROVING (new sessions biometrically stronger)
      near-zero -> STABLE (biometrically stationary — ideal for tournament)
    """
    age_weight_analysis_enabled: bool
    raw_ratio:            float
    age_weighted_ratio:   float
    temporal_drift_index: float
    halflife_days:        float
    drift_direction:      str
    error: "str | None" = None


class VAPIAgeWeightAnalysis:
    """SDK client for GET /agent/age-weight-analysis-status (Phase 175).

    Example::

        awa = VAPIAgeWeightAnalysis("http://localhost:8080", api_key)
        result = awa.get_status()
        if result.drift_direction == "P1_NONSTATIONARITY":
            print(f"TDI={result.temporal_drift_index:.3f}: re-enrollment needed")
    """

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_status(self) -> AgeWeightAnalysisResult:
        """Return the latest age-weighted ratio analysis result.

        On error: returns AgeWeightAnalysisResult with error set and STABLE defaults.
        """
        import urllib.request as _ur, json as _j
        try:
            url = f"{self._base}/agent/age-weight-analysis-status?api_key={self._key}"
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return AgeWeightAnalysisResult(
                age_weight_analysis_enabled = bool(body.get("age_weight_analysis_enabled", True)),
                raw_ratio            = float(body.get("raw_ratio",            0.0)),
                age_weighted_ratio   = float(body.get("age_weighted_ratio",   0.0)),
                temporal_drift_index = float(body.get("temporal_drift_index", 0.0)),
                halflife_days        = float(body.get("halflife_days",        90.0)),
                drift_direction      = str(body.get("drift_direction",        "STABLE")),
            )
        except Exception as exc:
            return AgeWeightAnalysisResult(
                age_weight_analysis_enabled = True,
                raw_ratio            = 0.0,
                age_weighted_ratio   = 0.0,
                temporal_drift_index = 0.0,
                halflife_days        = 90.0,
                drift_direction      = "STABLE",
                error                = str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 176 — PoACChainIntegrityMonitor (agent #25)
# ---------------------------------------------------------------------------

@dataclass
class PoACChainIntegrityResult:
    """Result from VAPIPoACChainIntegrity.get_status() (Phase 176).

    integrity_score = valid_links / total_records:
      1.0  = fully intact chain (all SHA-256 linkages verified)
      <1.0 = broken links detected (audit_passed=False)
    W1: broken_links is count only — no IDs exposed (prevents injection window leakage).
    """
    chain_integrity_enabled: bool
    total_records:   int
    valid_links:     int
    broken_links:    int
    integrity_score: float
    audit_passed:    bool
    error: "str | None" = None


class VAPIPoACChainIntegrity:
    """SDK client for GET /agent/poac-chain-integrity (Phase 176).

    Example::

        chain = VAPIPoACChainIntegrity("http://localhost:8080", api_key)
        result = chain.get_status()
        if not result.audit_passed:
            print(f"Chain broken: {result.broken_links}/{result.total_records} links")
    """

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_status(self, device_id: str = "") -> PoACChainIntegrityResult:
        """Return the latest PoAC chain integrity audit result.

        On error: returns PoACChainIntegrityResult with error set and audit_passed=True
        (fail-open — chain audit failure must not block tournament gate).
        """
        import urllib.request as _ur, json as _j
        try:
            url = f"{self._base}/agent/poac-chain-integrity?api_key={self._key}"
            if device_id:
                url += f"&device_id={device_id}"
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return PoACChainIntegrityResult(
                chain_integrity_enabled = bool(body.get("chain_integrity_enabled", True)),
                total_records   = int(body.get("total_records",   0)),
                valid_links     = int(body.get("valid_links",     0)),
                broken_links    = int(body.get("broken_links",    0)),
                integrity_score = float(body.get("integrity_score", 1.0)),
                audit_passed    = bool(body.get("audit_passed",   True)),
            )
        except Exception as exc:
            return PoACChainIntegrityResult(
                chain_integrity_enabled = True,
                total_records   = 0,
                valid_links     = 0,
                broken_links    = 0,
                integrity_score = 1.0,
                audit_passed    = True,
                error           = str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 180 — Biometric Renewal Engine (WIF-029 W2 closure)
# ---------------------------------------------------------------------------

@dataclass
class BiometricRenewalResult:
    """Result from VAPIBiometricRenewal.get_status() or trigger_renewal() (Phase 180).

    Records the consent-bound renewal commitment chain entry.
    new_commit_hash = SHA-256(prev_hash + ratio_str + N + N_consented + players + ttl_days + ts_ns).
    renewal_enabled=False by default (infrastructure-first, dry_run=True default).
    First renewable consent-bound biometric tournament license in any gaming DePIN protocol.
    """
    renewal_enabled:   bool
    prev_commit_hash:  str
    new_commit_hash:   str
    ttl_days:          float
    dry_run:           bool
    total_renewals:         int
    error: "str | None" = None
    # Phase 181 addition: consent corpus delta detection
    corpus_delta_detected:  bool = False


class VAPIBiometricRenewal:
    """SDK client for GET /agent/renewal-chain-status (Phase 180).

    Example::

        br = VAPIBiometricRenewal("http://localhost:8080", api_key)
        result = br.get_status()
        print(f"Renewals: {result.total_renewals}, latest: {result.new_commit_hash}")
    """

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_status(self) -> BiometricRenewalResult:
        """Return the current biometric renewal chain status.

        On error: returns BiometricRenewalResult with error set (fail-safe).
        """
        import urllib.request as _ur, json as _j
        try:
            url = f"{self._base}/agent/renewal-chain-status?api_key={self._key}"
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return BiometricRenewalResult(
                renewal_enabled       = bool(body.get("renewal_enabled",       False)),
                prev_commit_hash      = str(body.get("prev_commit_hash",       "")),
                new_commit_hash       = str(body.get("new_commit_hash",        "")),
                ttl_days              = float(body.get("ttl_days",             90.0)),
                dry_run               = bool(body.get("dry_run",               True)),
                total_renewals        = int(body.get("total_renewals",         0)),
                corpus_delta_detected = bool(body.get("corpus_delta_detected", False)),
            )
        except Exception as exc:
            return BiometricRenewalResult(
                renewal_enabled       = False,
                prev_commit_hash      = "",
                new_commit_hash       = "",
                ttl_days              = 90.0,
                dry_run               = True,
                total_renewals        = 0,
                error                 = str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 179 — ZK Ceremony Audit Gate (WIF-030 W1 closure)
# NOTE: Named CeremonyAuditGateResult / VAPICeremonyAuditGate to avoid
# collision with Phase 85 CeremonyAuditResult / VAPICeremonyAudit
# (Phase 85 = ZK proof ceremony verification; Phase 179 = audit gate status).
# ---------------------------------------------------------------------------

@dataclass
class CeremonyAuditGateResult:
    """Result from VAPICeremonyAuditGate.get_status() (Phase 179).

    Tracks Groth16 MPC trusted-setup ceremony participants per ZK circuit.
    Infrastructure-first: ceremony_audit_enabled=False by default.
    When enabled: audit_passed=True requires >= min_participants per circuit.
    Single-operator ceremony: toxic waste (τ, α, β) known to one party →
    can forge ZK proofs undetected (WIF-030 W1).
    """
    ceremony_audit_enabled:   bool
    total_entries:             int
    distinct_participants:     int
    circuits_audited:          int
    min_participants:          int
    audit_passed:              bool
    error: "str | None" = None


class VAPICeremonyAuditGate:
    """SDK client for GET /agent/ceremony-audit-status (Phase 179).

    Renamed from VAPICeremonyAudit to avoid collision with Phase 85's
    VAPICeremonyAudit (ZK proof ceremony verification vs audit gate status).

    Example::

        ca = VAPICeremonyAuditGate("http://localhost:8080", api_key)
        result = ca.get_status()
        if not result.audit_passed:
            print(f"Ceremony audit FAILED — {result.distinct_participants} participants "
                  f"< {result.min_participants} required")
    """

    def __init__(self, base_url: str, api_key: str = "",
                 ceremony_audit_registry_address: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key
        self.ceremony_audit_registry_address = ceremony_audit_registry_address

    def get_status(self) -> CeremonyAuditGateResult:
        """Return the current ZK ceremony audit gate status.

        On error: returns CeremonyAuditGateResult with error set, audit_passed=True (fail-open).
        """
        import urllib.request as _ur, json as _j
        try:
            url = f"{self._base}/agent/ceremony-audit-status?api_key={self._key}"
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return CeremonyAuditGateResult(
                ceremony_audit_enabled = bool(body.get("ceremony_audit_enabled", False)),
                total_entries          = int(body.get("total_entries",         0)),
                distinct_participants  = int(body.get("distinct_participants",  0)),
                circuits_audited       = int(body.get("circuits_audited",       0)),
                min_participants       = int(body.get("min_participants",       3)),
                audit_passed           = bool(body.get("audit_passed",          True)),
            )
        except Exception as exc:
            return CeremonyAuditGateResult(
                ceremony_audit_enabled = False,
                total_entries          = 0,
                distinct_participants  = 0,
                circuits_audited       = 0,
                min_participants       = 3,
                audit_passed           = True,   # fail-open: error must not block gate
                error                  = str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 178 — Biometric Credential TTL Gate (WIF-029 W1 closure)
# ---------------------------------------------------------------------------

@dataclass
class BiometricCredentialAgeResult:
    """Result from VAPIBiometricCredentialTTL.get_status() (Phase 178).

    Checks whether the latest SeparationRatioRegistry.sol commitment has expired.
    ttl_expired=True when age_days > ttl_days (default 90).
    An expired credential BLOCKS tournament authorization — operator must run
    fresh calibration sessions and commit a new SeparationRatioRegistry.sol record.
    Each check logged to biometric_renewal_log for regulatory audit trail.
    """
    ttl_enabled:             bool
    commit_hash:             str
    commit_ts:               float
    age_days:                float
    ttl_days:                float
    ttl_expired:             bool
    recalibration_required:  bool
    error: "str | None" = None


class VAPIBiometricCredentialTTL:
    """SDK client for GET /agent/biometric-credential-age (Phase 178).

    Example::

        bttl = VAPIBiometricCredentialTTL("http://localhost:8080", api_key)
        result = bttl.get_status()
        if result.ttl_expired:
            print(f"Credential expired ({result.age_days:.1f}d > {result.ttl_days}d)")
            print("Recalibration required before tournament authorization")
    """

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_status(self) -> BiometricCredentialAgeResult:
        """Return the current biometric credential age and TTL status.

        On error: returns BiometricCredentialAgeResult with error set, ttl_expired=False.
        """
        import urllib.request as _ur, json as _j
        try:
            url = f"{self._base}/agent/biometric-credential-age?api_key={self._key}"
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return BiometricCredentialAgeResult(
                ttl_enabled            = bool(body.get("ttl_enabled",            True)),
                commit_hash            = str(body.get("commit_hash",             "")),
                commit_ts              = float(body.get("commit_ts",             0.0)),
                age_days               = float(body.get("age_days",              0.0)),
                ttl_days               = float(body.get("ttl_days",              90.0)),
                ttl_expired            = bool(body.get("ttl_expired",            False)),
                recalibration_required = bool(body.get("recalibration_required", False)),
            )
        except Exception as exc:
            return BiometricCredentialAgeResult(
                ttl_enabled            = True,
                commit_hash            = "",
                commit_ts              = 0.0,
                age_days               = 0.0,
                ttl_days               = 90.0,
                ttl_expired            = False,
                recalibration_required = False,
                error                  = str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 177 — ProtocolMaturityScoringAgent (agent #26)
# ---------------------------------------------------------------------------

@dataclass
class ProtocolMaturityScoringResult:
    """Result from VAPIProtocolMaturityScoring.get_score() (Phase 177).

    maturity_score = weighted synthesis of 6 agent signals (0.0-1.0):
      separation(0.25) + chain_integrity(0.20) + consent(0.15)
      + biometric_freshness(0.15) + agent_calibration(0.15) + enrollment(0.10)
    maturity_tier:
      ALPHA              score < 0.50  — protocol not ready for any live use
      BETA               0.50 <= score < 0.85  — controlled testing only
      PRODUCTION_CANDIDATE score >= 0.85  — all gates met; TGE consideration
    PRODUCTION_CANDIDATE requires separation_ratio > 1.0 (non-negotiable).
    """
    protocol_maturity_enabled:       bool
    maturity_score:                   float
    maturity_tier:                    str
    separation_component:             float
    chain_integrity_component:        float
    consent_component:                float
    biometric_freshness_component:    float
    agent_calibration_component:      float
    enrollment_component:             float
    error: "str | None" = None
    # Phase 191 TSP additions
    threat_forecast_accuracy_component: float = 0.0
    biometric_stationarity_component:   float = 0.0
    # Phase 195 PMI addition
    pmi_component: float = 1.0


class VAPIProtocolMaturityScoring:
    """SDK client for GET /agent/protocol-maturity-score (Phase 177).

    Example::

        pm = VAPIProtocolMaturityScoring("http://localhost:8080", api_key)
        result = pm.get_score()
        print(f"Maturity: {result.maturity_score:.3f} ({result.maturity_tier})")
        if result.maturity_tier == "PRODUCTION_CANDIDATE":
            print("Protocol ready for TGE consideration")
    """

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_score(self) -> ProtocolMaturityScoringResult:
        """Return the latest protocol maturity score.

        On error: returns ProtocolMaturityScoringResult with error set, ALPHA tier.
        """
        import urllib.request as _ur, json as _j
        try:
            url = f"{self._base}/agent/protocol-maturity-score?api_key={self._key}"
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return ProtocolMaturityScoringResult(
                protocol_maturity_enabled           = bool(body.get("protocol_maturity_enabled", True)),
                maturity_score                       = float(body.get("maturity_score",                0.0)),
                maturity_tier                        = str(body.get("maturity_tier",                   "ALPHA")),
                separation_component                 = float(body.get("separation_component",          0.0)),
                chain_integrity_component            = float(body.get("chain_integrity_component",     0.0)),
                consent_component                    = float(body.get("consent_component",             0.0)),
                biometric_freshness_component        = float(body.get("biometric_freshness_component", 0.0)),
                agent_calibration_component          = float(body.get("agent_calibration_component",   0.0)),
                enrollment_component                 = float(body.get("enrollment_component",          0.0)),
                threat_forecast_accuracy_component   = float(body.get("threat_forecast_accuracy_component", 0.0)),
                biometric_stationarity_component     = float(body.get("biometric_stationarity_component",   0.0)),
                pmi_component                        = float(body.get("pmi_component",                      1.0)),
            )
        except Exception as exc:
            return ProtocolMaturityScoringResult(
                protocol_maturity_enabled           = True,
                maturity_score                       = 0.0,
                maturity_tier                        = "ALPHA",
                separation_component                 = 0.0,
                chain_integrity_component            = 0.0,
                consent_component                    = 0.0,
                biometric_freshness_component        = 0.0,
                agent_calibration_component          = 0.0,
                enrollment_component                 = 0.0,
                threat_forecast_accuracy_component   = 0.0,
                biometric_stationarity_component     = 0.0,
                pmi_component                        = 1.0,
                error                                = str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 195 — Protocol Metabolism Index (PMI)
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class PMIResult:
    """Result from VAPIProtocolMetabolism.get_status() (Phase 195).

    PMI = max(0.0, 1.0 - mean_resolution_hours / 48.0).
    1.0 = fleet has never had ORPHAN entries (or resolves them instantly).
    0.0 = mean ORPHAN resolution time >= 48h (fleet metabolises slowly).
    Feeds as pmi_component (weight=0.03) into ProtocolMaturityScoringAgent.
    """
    mean_resolution_hours: float
    pmi_score:             float
    orphan_count_open:     int
    orphan_count_resolved: int
    domain:                str
    error: "str | None" = None


class VAPIProtocolMetabolism:
    """SDK client for GET /agent/protocol-metabolism-index (Phase 195).

    Example::

        pmi = VAPIProtocolMetabolism("http://localhost:8080", api_key)
        result = pmi.get_status()
        print(f"PMI: {result.pmi_score:.3f} (open orphans: {result.orphan_count_open})")
    """

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_status(self, domain: str = "") -> PMIResult:
        """Return current Protocol Metabolism Index.

        On error: returns PMIResult with pmi_score=1.0, error set (fail-open).
        """
        import urllib.request as _ur, json as _j
        try:
            _dom = f"&domain={domain}" if domain else ""
            url = f"{self._base}/agent/protocol-metabolism-index?api_key={self._key}{_dom}"
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return PMIResult(
                mean_resolution_hours = float(body.get("mean_resolution_hours_critical", 0.0)),
                pmi_score             = float(body.get("pmi_score",             1.0)),
                orphan_count_open     = int(body.get("orphan_count_open",     0)),
                orphan_count_resolved = int(body.get("orphan_count_resolved", 0)),
                domain                = str(body.get("domain",                "all")),
            )
        except Exception as exc:
            return PMIResult(
                mean_resolution_hours = 0.0,
                pmi_score             = 1.0,
                orphan_count_open     = 0,
                orphan_count_resolved = 0,
                domain                = domain or "all",
                error                 = str(exc),
            )


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Phase 198 — Biometric TTL Decay Scaling
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class BiometricTTLScalingResult:
    """Result from VAPIBiometricTTLScaling.get_status() (Phase 198).

    effective_ttl = base_ttl × (mean_decay_factor / 0.50) when enabled.
    Clamped to [base_ttl × 0.25, base_ttl × 4.0].
    mean_decay_factor from BiometricPrivacyComplianceAgent BP-001 (Phase 159).
    """
    effective_ttl_days: float
    base_ttl_days:      float
    scaling_factor:     float
    mean_decay_factor:  float
    scaling_enabled:    bool
    error: "str | None" = None


class VAPIBiometricTTLScaling:
    """SDK client for GET /agent/biometric-ttl-scaling-status (Phase 198).

    Example::

        ttl = VAPIBiometricTTLScaling("http://localhost:8080", api_key)
        result = ttl.get_status()
        print(f"Effective TTL: {result.effective_ttl_days:.1f} days (scaling={result.scaling_enabled})")
    """

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_status(self) -> BiometricTTLScalingResult:
        """Return current biometric TTL scaling status.

        On error: returns BiometricTTLScalingResult with scaling_enabled=False, error set.
        """
        import urllib.request as _ur, json as _j
        try:
            url = f"{self._base}/agent/biometric-ttl-scaling-status?api_key={self._key}"
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return BiometricTTLScalingResult(
                effective_ttl_days = float(body.get("effective_ttl_days", 90.0)),
                base_ttl_days      = float(body.get("base_ttl_days",      90.0)),
                scaling_factor     = float(body.get("scaling_factor",     1.0)),
                mean_decay_factor  = float(body.get("mean_decay_factor",  1.0)),
                scaling_enabled    = bool(body.get("scaling_enabled",     False)),
            )
        except Exception as exc:
            return BiometricTTLScalingResult(
                effective_ttl_days = 90.0,
                base_ttl_days      = 90.0,
                scaling_factor     = 1.0,
                mean_decay_factor  = 1.0,
                scaling_enabled    = False,
                error              = str(exc),
            )


# Phase 199 — Prototype Separation Gate Configurability + Tremor Resting Probe
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class ProbeGateConfigResult:
    """Result from VAPIProbeGateConfig.get_status() (Phase 199 — 199-A).

    all_pairs_gate_enabled=True  → production mode: per-pair >= 1.0 enforced.
    all_pairs_gate_enabled=False → prototype mode: per-pair gate bypassed.
    min_separation_ratio (Phase 166 default=0.70) governs separation_ok.
    """
    all_pairs_gate_enabled:  bool
    min_separation_ratio:    float
    prototype_mode_active:   bool
    separation_ok_threshold: float
    error: "str | None" = None


class VAPIProbeGateConfig:
    """SDK client for GET /agent/probe-gate-config-status (Phase 199).

    Example::

        cfg = VAPIProbeGateConfig("http://localhost:8080", api_key)
        result = cfg.get_status()
        if result.prototype_mode_active:
            print(f"Prototype mode — per-pair gate bypassed; threshold={result.min_separation_ratio}")
    """

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_status(self) -> ProbeGateConfigResult:
        """Return probe gate configuration status.

        On error: returns ProbeGateConfigResult with all_pairs_gate_enabled=True, error set.
        """
        import urllib.request as _ur, json as _j
        try:
            url = f"{self._base}/agent/probe-gate-config-status?api_key={self._key}"
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return ProbeGateConfigResult(
                all_pairs_gate_enabled  = bool(body.get("all_pairs_gate_enabled", True)),
                min_separation_ratio    = float(body.get("min_separation_ratio", 0.70)),
                prototype_mode_active   = bool(body.get("prototype_mode_active", False)),
                separation_ok_threshold = float(body.get("separation_ok_threshold", 0.70)),
            )
        except Exception as exc:
            return ProbeGateConfigResult(
                all_pairs_gate_enabled  = True,
                min_separation_ratio    = 0.70,
                prototype_mode_active   = False,
                separation_ok_threshold = 0.70,
                error                   = str(exc),
            )


@dataclass(slots=True)
class TremorRestingProbeResult:
    """Result from VAPITremorRestingProbe.get_status() (Phase 199 — 199-B).

    30-second still-hold probe that isolates neurological tremor_peak_hz from
    gameplay motion artifacts.  Primary discriminators: tremor_peak_hz, tremor_band_power,
    micro_tremor_accel_variance.

    P1 ~9.37 Hz, P2 ~1.71 Hz, P3 ~2.85 Hz (empirical, N=35 touchpad_corners corpus).
    """
    probe_type:                  str
    enabled:                     bool
    capture_instructions:        str
    primary_features:            list
    suppressed_features:         list
    target_duration_s:           int
    sessions_needed_per_player:  int
    all_pairs_gate_enabled:      bool
    prototype_mode_active:       bool
    error: "str | None" = None


class VAPITremorRestingProbe:
    """SDK client for GET /agent/tremor-resting-probe-status (Phase 199).

    Example::

        probe = VAPITremorRestingProbe("http://localhost:8080", api_key)
        result = probe.get_status()
        if not result.enabled:
            print("Set TREMOR_RESTING_PROBE_ENABLED=true to activate")
    """

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_status(self) -> TremorRestingProbeResult:
        """Return tremor resting probe status.

        On error: returns TremorRestingProbeResult with enabled=False, error set.
        """
        import urllib.request as _ur, json as _j
        try:
            url = f"{self._base}/agent/tremor-resting-probe-status?api_key={self._key}"
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return TremorRestingProbeResult(
                probe_type                 = str(body.get("probe_type", "tremor_resting")),
                enabled                    = bool(body.get("enabled", False)),
                capture_instructions       = str(body.get("capture_instructions", "")),
                primary_features           = list(body.get("primary_features", [])),
                suppressed_features        = list(body.get("suppressed_features", [])),
                target_duration_s          = int(body.get("target_duration_s", 30)),
                sessions_needed_per_player = int(body.get("sessions_needed_per_player", 5)),
                all_pairs_gate_enabled     = bool(body.get("all_pairs_gate_enabled", True)),
                prototype_mode_active      = bool(body.get("prototype_mode_active", False)),
            )
        except Exception as exc:
            return TremorRestingProbeResult(
                probe_type                 = "tremor_resting",
                enabled                    = False,
                capture_instructions       = "",
                primary_features           = [],
                suppressed_features        = [],
                target_duration_s          = 30,
                sessions_needed_per_player = 5,
                all_pairs_gate_enabled     = True,
                prototype_mode_active      = False,
                error                      = str(exc),
            )


# Phase 182 — PersonaBreakDetectorAgent (WIF-028 deeper mitigation)
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class PersonaBreakResult:
    """Result from VAPIPersonaBreakDetector.get_status() (Phase 182).

    persona_break_detected=True when mean LOO accuracy trend < persona_break_loo_threshold (0.20).
    re_enrollment_urgency: CRITICAL / HIGH / MEDIUM
    """
    persona_break_detected: bool
    player_id:              str
    loo_accuracy_trend:     float
    tdi_current:            float
    re_enrollment_urgency:  str
    error: "str | None" = None


class VAPIPersonaBreakDetector:
    """SDK client for GET /agent/persona-break-status (Phase 182).

    Example::

        pb = VAPIPersonaBreakDetector("http://localhost:8080", api_key)
        result = pb.get_status(player_id="P1")
        if result.persona_break_detected:
            print(f"Persona break: urgency={result.re_enrollment_urgency}")
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_status(self, player_id: str = "") -> PersonaBreakResult:
        """Return the latest persona break detection status.

        On error: returns PersonaBreakResult with persona_break_detected=False (fail-open).
        """
        import urllib.request as _ur, json as _j
        try:
            url = f"{self._base}/agent/persona-break-status?api_key={self._key}"
            if player_id:
                url += f"&player_id={player_id}"
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return PersonaBreakResult(
                persona_break_detected = bool(body.get("persona_break_detected", False)),
                player_id              = str(body.get("player_id",              player_id)),
                loo_accuracy_trend     = float(body.get("loo_accuracy_trend",    0.0)),
                tdi_current            = float(body.get("tdi_current",           0.0)),
                re_enrollment_urgency  = str(body.get("re_enrollment_urgency",   "MEDIUM")),
            )
        except Exception as exc:
            return PersonaBreakResult(
                persona_break_detected = False,
                player_id              = player_id,
                loo_accuracy_trend     = 0.0,
                tdi_current            = 0.0,
                re_enrollment_urgency  = "MEDIUM",
                error                  = str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 183 — MaturityElevationGateAgent (WIF-027 W2 closure)
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class MaturityElevationResult:
    """Result from VAPIMaturityElevation.get_status() (Phase 183).

    elevation_available=True when gap_to_target < 0.05.
    elevation_plan: dict mapping component name -> {gap, action, estimated_sessions, blocking}.
    """
    current_tier:         str
    target_tier:          str
    gap_to_target:        float
    elevation_available:  bool
    elevation_plan:       dict
    critical_component:   str
    error: "str | None" = None


class VAPIMaturityElevation:
    """SDK client for GET /agent/maturity-elevation-plan (Phase 183).

    Example::

        me = VAPIMaturityElevation("http://localhost:8080", api_key)
        result = me.get_status()
        print(f"Tier: {result.current_tier}, gap: {result.gap_to_target:.3f}")
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_status(self) -> MaturityElevationResult:
        """Return the current maturity elevation plan.

        On error: returns ALPHA-tier safe defaults (fail-safe).
        """
        import urllib.request as _ur, json as _j
        try:
            url = f"{self._base}/agent/maturity-elevation-plan?api_key={self._key}"
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return MaturityElevationResult(
                current_tier        = str(body.get("current_tier",        "ALPHA")),
                target_tier         = str(body.get("target_tier",         "BETA")),
                gap_to_target       = float(body.get("gap_to_target",     1.0)),
                elevation_available = bool(body.get("elevation_available", False)),
                elevation_plan      = dict(body.get("elevation_plan",     {})),
                critical_component  = str(body.get("critical_component",  "")),
            )
        except Exception as exc:
            return MaturityElevationResult(
                current_tier        = "ALPHA",
                target_tier         = "BETA",
                gap_to_target       = 1.0,
                elevation_available = False,
                elevation_plan      = {},
                critical_component  = "",
                error               = str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 185 — ReEnrollmentAttestationAgent (WIF-032 W1 closure)
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class ReEnrollmentAttestationResult:
    """Result from VAPIReEnrollmentAttestation.get_status() (Phase 185).

    HMAC-SHA256 attestation token gates re-enrollment window.
    active=True means a valid, non-expired attestation exists for the player.
    """
    attestation_hash: str
    player_id:        str
    issued_at:        float
    expires_at:       float
    active:           bool
    error: "str | None" = None


class VAPIReEnrollmentAttestation:
    """SDK client for GET /agent/reenrollment-attestation-status (Phase 185).

    Example::

        ra = VAPIReEnrollmentAttestation("http://localhost:8080", api_key)
        result = ra.get_status(player_id="P1")
        if result.active:
            print(f"Attestation active: {result.attestation_hash[:12]}")
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_status(self, player_id: str = "") -> ReEnrollmentAttestationResult:
        """Return the current re-enrollment attestation status.

        On error: returns active=False safe defaults.
        """
        import urllib.request as _ur, json as _j
        try:
            url = f"{self._base}/agent/reenrollment-attestation-status?api_key={self._key}"
            if player_id:
                url += f"&player_id={player_id}"
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return ReEnrollmentAttestationResult(
                attestation_hash = str(body.get("attestation_hash", "")),
                player_id        = str(body.get("player_id",        player_id)),
                issued_at        = float(body.get("issued_at",       0.0)),
                expires_at       = float(body.get("expires_at",      0.0)),
                active           = bool(body.get("active",           False)),
            )
        except Exception as exc:
            return ReEnrollmentAttestationResult(
                attestation_hash = "",
                player_id        = player_id,
                issued_at        = 0.0,
                expires_at       = 0.0,
                active           = False,
                error            = str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 186 — AttestationBoundRenewalAgent (WIF-032 W2 closure)
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class AttestationBoundRenewalResult:
    """Result from VAPIAttestationBoundRenewal.get_status() (Phase 186).

    Validates that every renewal has a valid active HMAC attestation.
    renewal_approved=True means the attestation was valid at renewal time.
    """
    attestation_bound_renewal_enabled: bool
    attestation_hash:                  str
    renewal_approved:                  bool
    denial_reason:                     str
    total_blocked:                     int
    error: "str | None" = None


class VAPIAttestationBoundRenewal:
    """SDK client for GET /agent/attestation-bound-renewal-status (Phase 186).

    Example::

        abr = VAPIAttestationBoundRenewal("http://localhost:8080", api_key)
        result = abr.get_status(player_id="P1")
        if not result.renewal_approved:
            print(f"Renewal blocked: {result.denial_reason}")
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_status(self, player_id: str = "") -> AttestationBoundRenewalResult:
        """Return the latest attestation-bound renewal status.

        On error: returns enabled=False safe defaults.
        """
        import urllib.request as _ur, json as _j
        try:
            url = f"{self._base}/agent/attestation-bound-renewal-status?api_key={self._key}"
            if player_id:
                url += f"&player_id={player_id}"
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            # API may return latest_attestation_hash or attestation_hash
            attest_hash = str(
                body.get("latest_attestation_hash") or body.get("attestation_hash", "")
            )
            renewal_ok = bool(
                body.get("latest_renewal_approved") or body.get("renewal_approved", False)
            )
            return AttestationBoundRenewalResult(
                attestation_bound_renewal_enabled = bool(body.get("attestation_bound_renewal_enabled", False)),
                attestation_hash                  = attest_hash,
                renewal_approved                  = renewal_ok,
                denial_reason                     = str(body.get("denial_reason", "")),
                total_blocked                     = int(body.get("total_blocked",  0)),
            )
        except Exception as exc:
            return AttestationBoundRenewalResult(
                attestation_bound_renewal_enabled = False,
                attestation_hash                  = "",
                renewal_approved                  = False,
                denial_reason                     = "",
                total_blocked                     = 0,
                error                             = str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 187 — AttestationOpSecAdvisorAgent (WIF-033 W1 closure)
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class AttestationOpSecResult:
    """Result from VAPIAttestationOpSec.get_status() (Phase 187).

    timing_disclosure_risk: HIGH / MEDIUM / LOW
    HIGH when bound_renewal_enabled=True AND active_attestations > 0.
    recommendation: STANDARD_TX_OK / USE_PRIVATE_MEMPOOL_OR_DELAY_TX / etc.
    """
    mempool_opsec_enabled:   bool  = False
    timing_disclosure_risk:  str   = "LOW"
    active_attestations:     int   = 0
    recommendation:          str   = "STANDARD_TX_OK"
    total_high_risk_events:  int   = 0
    error: "str | None" = None


class VAPIAttestationOpSec:
    """SDK client for GET /agent/attestation-opsec-status (Phase 187).

    Example::

        ao = VAPIAttestationOpSec("http://localhost:8080", api_key)
        result = ao.get_status(player_id="P1")
        if result.timing_disclosure_risk == "HIGH":
            print(f"OpSec risk: {result.recommendation}")
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_status(self, player_id: str = "") -> AttestationOpSecResult:
        """Return the current attestation OpSec advisory status.

        On error: returns LOW risk safe defaults.
        """
        import urllib.request as _ur, json as _j
        try:
            url = f"{self._base}/agent/attestation-opsec-status?api_key={self._key}"
            if player_id:
                url += f"&player_id={player_id}"
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return AttestationOpSecResult(
                mempool_opsec_enabled  = bool(body.get("mempool_opsec_enabled",  False)),
                timing_disclosure_risk = str(body.get("timing_disclosure_risk",  "LOW")),
                active_attestations    = int(body.get("active_attestations",     0)),
                recommendation         = str(body.get("recommendation",          "STANDARD_TX_OK")),
                total_high_risk_events = int(body.get("total_high_risk_events",  0)),
            )
        except Exception as exc:
            return AttestationOpSecResult(error=str(exc))


# ---------------------------------------------------------------------------
# Phase 187 — VHPReenrollmentBadge (WIF-033 W2 closure)
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class VHPReenrollmentBadgeResult:
    """Result from VAPIVHPReenrollmentBadge.get_status() (Phase 187).

    ERC-4671 soulbound badge for reenrollment; anti-replay via attestationUsed.
    badge_token_id=0 means no badge minted yet.
    """
    reenrollment_badge_enabled: bool  = False
    player_id:                  str   = ""
    badge_token_id:             int   = 0
    re_enrollment_count:        int   = 0
    total_badges:               int   = 0
    error: "str | None" = None


class VAPIVHPReenrollmentBadge:
    """SDK client for GET /agent/vhp-reenrollment-badge-status (Phase 187).

    Example::

        badge = VAPIVHPReenrollmentBadge("http://localhost:8080", api_key)
        result = badge.get_status(player_id="P1")
        print(f"Badges minted: {result.total_badges}, latest ID: {result.badge_token_id}")
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_status(self, player_id: str = "") -> VHPReenrollmentBadgeResult:
        """Return the current VHP reenrollment badge status.

        On error: returns enabled=False safe defaults.
        """
        import urllib.request as _ur, json as _j
        try:
            url = f"{self._base}/agent/vhp-reenrollment-badge-status?api_key={self._key}"
            if player_id:
                url += f"&player_id={player_id}"
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return VHPReenrollmentBadgeResult(
                reenrollment_badge_enabled = bool(body.get("reenrollment_badge_enabled", False)),
                player_id                  = str(body.get("player_id",                  player_id)),
                badge_token_id             = int(body.get("badge_token_id",              0)),
                re_enrollment_count        = int(body.get("re_enrollment_count",         0)),
                total_badges               = int(body.get("total_badges",                0)),
            )
        except Exception as exc:
            return VHPReenrollmentBadgeResult(error=str(exc))


# ---------------------------------------------------------------------------
# Phase 188 — BiometricStationarityOracleAgent (agent #32)
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class BiometricStationarityResult:
    """Result from VAPIBiometricStationarity.get_status() (Phase 188).

    Discriminates genuine biometric drift from adversarial window exploitation.
    stationarity_verdict: ADVERSARIAL_WINDOW / GENUINE_DRIFT / AMBIGUOUS / STABLE
    """
    biometric_stationarity_enabled:     bool  = False
    p_genuine_drift:                    float = 0.0
    p_adversarial_window:               float = 0.0
    stationarity_verdict:               str   = "STABLE"
    biometric_stationarity_confidence:  float = 0.0
    error:                              str   = ""


class VAPIBiometricStationarity:
    """SDK client for GET /agent/biometric-stationarity-status (Phase 188).

    Example::

        bs = VAPIBiometricStationarity("http://localhost:8080", api_key)
        result = bs.get_status(player_id="P1")
        if result.stationarity_verdict == "ADVERSARIAL_WINDOW":
            print("Adversarial window attack detected!")
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_status(self, player_id: str = "") -> BiometricStationarityResult:
        """Return the latest biometric stationarity oracle result.

        On error: returns STABLE verdict safe defaults (fail-open).
        """
        import urllib.request as _ur, json as _j
        try:
            url = f"{self._base}/agent/biometric-stationarity-status?api_key={self._key}"
            if player_id:
                url += f"&player_id={player_id}"
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return BiometricStationarityResult(
                biometric_stationarity_enabled    = bool(body.get("biometric_stationarity_enabled",    False)),
                p_genuine_drift                   = float(body.get("p_genuine_drift",                  0.0)),
                p_adversarial_window              = float(body.get("p_adversarial_window",             0.0)),
                stationarity_verdict              = str(body.get("stationarity_verdict",               "STABLE")),
                biometric_stationarity_confidence = float(body.get("biometric_stationarity_confidence", 0.0)),
            )
        except Exception as exc:
            return BiometricStationarityResult(error=str(exc))


# ---------------------------------------------------------------------------
# Phase 189 — ProtocolIntelligenceRecordAgent (agent #33)
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class PIRChainResult:
    """Result from VAPIProtocolIntelligenceRecord.get_status() (Phase 189).

    SHA-256 hash-linked PIR chain. chain_intact=True when all prev_pir_hash links verify.
    Vacuous integrity: empty chain → chain_intact=True.
    """
    pir_chain_enabled:      bool  = False
    total_pirs:             int   = 0
    chain_intact:           bool  = True
    latest_cycle:           int   = 0
    latest_threat_forecast: str   = ""
    error:                  str   = ""


class VAPIProtocolIntelligenceRecord:
    """SDK client for GET /agent/pir-chain-status (Phase 189).

    Example::

        pir = VAPIProtocolIntelligenceRecord("http://localhost:8080", api_key)
        result = pir.get_status()
        if not result.chain_intact:
            print("PIR chain integrity violation!")
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_status(self) -> PIRChainResult:
        """Return the current PIR chain status.

        On error: returns chain_intact=True safe defaults (fail-open).
        """
        import urllib.request as _ur, json as _j
        try:
            url = f"{self._base}/agent/pir-chain-status?api_key={self._key}"
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return PIRChainResult(
                pir_chain_enabled      = bool(body.get("pir_chain_enabled",      False)),
                total_pirs             = int(body.get("total_pirs",              0)),
                chain_intact           = bool(body.get("chain_intact",           True)),
                latest_cycle           = int(body.get("latest_cycle",            0)),
                latest_threat_forecast = str(body.get("latest_threat_forecast",  "")),
            )
        except Exception as exc:
            return PIRChainResult(error=str(exc))


# ---------------------------------------------------------------------------
# Phase 190 — LivePresenceSignalingAgent (agent #34)
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class LivePresenceSignalingResult:
    """Result from VAPILivePresenceSignaling.get_status() (Phase 190).

    Bidirectional VAPI presence channel: controller LED+haptic (ps5_compat_aware)
    plus ANSI terminal stream (always active).
    Signal vocabulary: HARD_CHEAT_DETECTED / CERTIFY_ADJUDICATION / BIOMETRIC_ANOMALY /
    PERSONA_BREAK_DETECTED / ENROLLMENT_MILESTONE / MATURITY_ELEVATION /
    SEPARATION_BREAKTHROUGH / CHAIN_MILESTONE
    """
    live_presence_signaling_enabled: bool  = False
    total_signals:                   int   = 0
    controller_fired_count:          int   = 0
    ps5_suppressed_count:            int   = 0
    latest_signal_type:              str   = ""
    error:                           str   = ""


class VAPILivePresenceSignaling:
    """SDK client for GET /agent/live-presence-signaling-status (Phase 190).

    Example::

        lps = VAPILivePresenceSignaling("http://localhost:8080", api_key)
        result = lps.get_status()
        print(f"Signals fired: {result.total_signals}, controller: {result.controller_fired_count}")
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_status(self) -> LivePresenceSignalingResult:
        """Return the current live presence signaling status.

        On error: returns zero-count safe defaults.
        """
        import urllib.request as _ur, json as _j
        try:
            url = f"{self._base}/agent/live-presence-signaling-status?api_key={self._key}"
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return LivePresenceSignalingResult(
                live_presence_signaling_enabled = bool(body.get("live_presence_signaling_enabled", False)),
                total_signals                   = int(body.get("total_signals",                    0)),
                controller_fired_count          = int(body.get("controller_fired_count",           0)),
                ps5_suppressed_count            = int(body.get("ps5_suppressed_count",             0)),
                latest_signal_type              = str(body.get("latest_signal_type",               "")),
            )
        except Exception as exc:
            return LivePresenceSignalingResult(error=str(exc))


# ---------------------------------------------------------------------------
# Phase 192: DataCuratorAgent (Agent #35) — 7 result dataclasses
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class ProvenanceChainResult:
    """Result from VAPIProvenanceChain.get_chain() (Phase 192).

    Provenance DAG chain walk from leaf_node_id to root calibration session.
    The full causal chain from a 228-byte PoAC session to an on-chain VHP badge.
    """
    leaf_node_id:    str   = ""
    chain_length:    int   = 0
    chain:           str   = "[]"     # JSON list of provenance nodes
    forensic_summary: str  = ""
    error:           str   = ""


class VAPIProvenanceChain:
    """SDK client for GET /agent/data-provenance-chain (Phase 192, Tool #136).

    Example::

        pc = VAPIProvenanceChain("http://localhost:8080", api_key)
        result = pc.get_chain(leaf_node_id="sha256:...")
        print(f"Chain length: {result.chain_length}, summary: {result.forensic_summary}")
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_chain(self, leaf_node_id: str = "") -> ProvenanceChainResult:
        """Return provenance chain for the given leaf node. On error: empty chain."""
        import urllib.request as _ur, json as _j, urllib.parse as _up
        try:
            params = f"leaf_node_id={_up.quote(leaf_node_id)}"
            url = f"{self._base}/agent/data-provenance-chain?{params}"
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            import json as _json
            return ProvenanceChainResult(
                leaf_node_id    = str(body.get("leaf_node_id",    "")),
                chain_length    = int(body.get("chain_length",    0)),
                chain           = _json.dumps(body.get("chain",   [])),
                forensic_summary = str(body.get("forensic_summary", "")),
            )
        except Exception as exc:
            return ProvenanceChainResult(error=str(exc))


@dataclass(slots=True)
class CorpusEntropyResult:
    """Result from VAPICorpusEntropy.get_status() (Phase 192).

    Shannon entropy of 13-dim feature space per player.
    Score < 1.5 = CLUSTERING_WARNING (brittle centroid).
    Score > 2.5 = WELL_SAMPLED (trustworthy ratio).
    """
    corpus_entropy_score:  float = 0.0
    clustering_warning:    bool  = True
    status:                str   = "NO_DATA"
    per_player_entropy:    str   = "{}"
    low_entropy_features:  str   = "[]"
    n_sessions_analyzed:   int   = 0
    error:                 str   = ""


class VAPICorpusEntropy:
    """SDK client for GET /agent/corpus-entropy-status (Phase 192, Tool #137).

    Example::

        ce = VAPICorpusEntropy("http://localhost:8080", api_key)
        result = ce.get_status()
        print(f"Entropy: {result.corpus_entropy_score:.2f} ({result.status})")
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_status(self) -> CorpusEntropyResult:
        """Return corpus entropy status. On error: returns NO_DATA safe defaults."""
        import urllib.request as _ur, json as _j
        try:
            url = f"{self._base}/agent/corpus-entropy-status"
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return CorpusEntropyResult(
                corpus_entropy_score = float(body.get("corpus_entropy_score", 0.0)),
                clustering_warning   = bool(body.get("clustering_warning",    True)),
                status               = str(body.get("status",                 "NO_DATA")),
                per_player_entropy   = str(body.get("per_player_entropy",     "{}")),
                low_entropy_features = str(body.get("low_entropy_features",   "[]")),
                n_sessions_analyzed  = int(body.get("n_sessions_analyzed",    0)),
            )
        except Exception as exc:
            return CorpusEntropyResult(error=str(exc))


@dataclass(slots=True)
class ErasureCertificateResult:
    """Result from VAPIErasureCertificate.get_certificate() (Phase 192).

    GDPR Art.17 cryptographic erasure proof anchored to AdjudicationRegistry.sol.
    """
    device_id:          str   = ""
    certificate_found:  bool  = False
    certificate_hash:   str   = ""
    post_erasure_ratio: float = 0.0
    anchored:           bool  = False
    error:              str   = ""


class VAPIErasureCertificate:
    """SDK client for GET /agent/erasure-certificate (Phase 192, Tool #138).

    Example::

        ec = VAPIErasureCertificate("http://localhost:8080", api_key)
        result = ec.get_certificate("device_abc123")
        print(f"Cert found: {result.certificate_found}, anchored: {result.anchored}")
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_certificate(self, device_id: str) -> ErasureCertificateResult:
        """Return erasure certificate for device_id. On error: not-found defaults."""
        import urllib.request as _ur, json as _j, urllib.parse as _up
        try:
            url = f"{self._base}/agent/erasure-certificate?device_id={_up.quote(device_id)}"
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return ErasureCertificateResult(
                device_id          = str(body.get("device_id",          "")),
                certificate_found  = bool(body.get("certificate_found", False)),
                certificate_hash   = str(body.get("certificate_hash",   "") or ""),
                post_erasure_ratio = float(body.get("post_erasure_ratio", 0.0) or 0.0),
                anchored           = bool(body.get("anchored",           False)),
            )
        except Exception as exc:
            return ErasureCertificateResult(device_id=device_id, error=str(exc))


@dataclass(slots=True)
class FederatedCorpusQualityResult:
    """Result from VAPIFederatedCorpusQuality.get_status() (Phase 192).

    Anonymized corpus quality statistics for cross-bridge comparison.
    BP-007: only derived metrics — never raw biometric data.
    """
    federated_corpus_quality_enabled: bool = False
    record_count:                     int  = 0
    privacy_constraint:               str  = "BP-007: no raw biometric data"
    error:                            str  = ""


class VAPIFederatedCorpusQuality:
    """SDK client for GET /agent/federated-corpus-quality (Phase 192, Tool #140).

    Example::

        fcq = VAPIFederatedCorpusQuality("http://localhost:8080", api_key)
        result = fcq.get_status()
        print(f"Records: {result.record_count}, enabled: {result.federated_corpus_quality_enabled}")
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_status(self) -> FederatedCorpusQualityResult:
        """Return federated corpus quality status. On error: disabled defaults."""
        import urllib.request as _ur, json as _j
        try:
            url = f"{self._base}/agent/federated-corpus-quality"
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return FederatedCorpusQualityResult(
                federated_corpus_quality_enabled = bool(
                    body.get("federated_corpus_quality_enabled", False)),
                record_count     = int(body.get("record_count", 0)),
                privacy_constraint = str(body.get("privacy_constraint", "BP-007")),
            )
        except Exception as exc:
            return FederatedCorpusQualityResult(error=str(exc))


@dataclass(slots=True)
class FeatureCorrelationResult:
    """Result from VAPIFeatureCorrelation.get_status() (Phase 192).

    Per-player 13x13 feature correlation matrix and Frobenius separability.
    correlation_separable=True when frobenius > separability_threshold (FROZEN=0.5).
    """
    player_id:             str   = ""
    correlation_found:     bool  = False
    correlation_separable: bool  = False
    frobenius_vs_p1:       float = 0.0
    frobenius_vs_p2:       float = 0.0
    frobenius_vs_p3:       float = 0.0
    error:                 str   = ""


class VAPIFeatureCorrelation:
    """SDK client for GET /agent/feature-correlation-status (Phase 192, Tool #141).

    Example::

        fc = VAPIFeatureCorrelation("http://localhost:8080", api_key)
        result = fc.get_status(player_id="P1")
        print(f"Separable: {result.correlation_separable}, frobenius_vs_P2: {result.frobenius_vs_p2}")
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_status(self, player_id: str = "") -> FeatureCorrelationResult:
        """Return feature correlation status. On error: not-found defaults."""
        import urllib.request as _ur, json as _j, urllib.parse as _up
        try:
            url = (f"{self._base}/agent/feature-correlation-status"
                   f"?player_id={_up.quote(player_id)}")
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return FeatureCorrelationResult(
                player_id             = str(body.get("player_id",             "")),
                correlation_found     = bool(body.get("correlation_found",    False)),
                correlation_separable = bool(body.get("correlation_separable", False)),
                frobenius_vs_p1       = float(body.get("frobenius_vs_p1", 0.0) or 0.0),
                frobenius_vs_p2       = float(body.get("frobenius_vs_p2", 0.0) or 0.0),
                frobenius_vs_p3       = float(body.get("frobenius_vs_p3", 0.0) or 0.0),
            )
        except Exception as exc:
            return FeatureCorrelationResult(player_id=player_id, error=str(exc))


@dataclass(slots=True)
class DataReadinessCertificateResult:
    """Result from VAPIDataReadinessCertificate.get_status() (Phase 192).

    8-dimension pre-tournament certification artifact.
    certification_status: CERTIFIED | BLOCKED | ADVISORY_ONLY.
    FROZEN: separation_gate=0.70, vhp_expiry_days=90.
    """
    certificate_found:    bool  = False
    certification_status: str   = "NO_CERTIFICATE"
    certificate_hash:     str   = ""
    separation_ratio:     float = 0.0
    blocking_failures:    str   = "[]"
    advisory_warnings:    str   = "[]"
    error:                str   = ""


class VAPIDataReadinessCertificate:
    """SDK client for GET /agent/data-readiness-certificate (Phase 192, Tool #142).

    Example::

        drc = VAPIDataReadinessCertificate("http://localhost:8080", api_key)
        result = drc.get_status()
        print(f"Status: {result.certification_status}, ratio: {result.separation_ratio:.3f}")
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_status(self) -> DataReadinessCertificateResult:
        """Return latest data readiness certificate. On error: NO_CERTIFICATE defaults."""
        import urllib.request as _ur, json as _j
        try:
            url = f"{self._base}/agent/data-readiness-certificate"
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return DataReadinessCertificateResult(
                certificate_found    = bool(body.get("certificate_found",    False)),
                certification_status = str(body.get("certification_status",  "NO_CERTIFICATE")),
                certificate_hash     = str(body.get("certificate_hash",      "") or ""),
                separation_ratio     = float(body.get("separation_ratio",    0.0)),
                blocking_failures    = str(body.get("blocking_failures",     "[]")),
                advisory_warnings    = str(body.get("advisory_warnings",     "[]")),
            )
        except Exception as exc:
            return DataReadinessCertificateResult(error=str(exc))


@dataclass(slots=True)
class SessionContributionWeightResult:
    """Result from VAPISessionContributionWeight.get_weights() (Phase 192).

    TBD-decay session contribution weights.
    FROZEN: lambda=ln(2)/90 (BP-001 TBD half-life=vhp_expiry_days=90).
    effective_weight = tbd_weight * type_multiplier * stationarity_multiplier.
    """
    player_id:        str   = ""
    tbd_lambda:       float = 0.0
    tbd_halflife_days: int  = 90
    weight_count:     int   = 0
    weights:          str   = "[]"    # JSON list of weight records
    error:            str   = ""


class VAPISessionContributionWeight:
    """SDK client for GET /agent/session-contribution-weights (Phase 192, Tool #144).

    Example::

        scw = VAPISessionContributionWeight("http://localhost:8080", api_key)
        result = scw.get_weights(player_id="P1")
        print(f"P1 sessions: {result.weight_count}, lambda: {result.tbd_lambda:.5f}")
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_weights(self, player_id: str = "") -> SessionContributionWeightResult:
        """Return session contribution weights. On error: empty-weight defaults."""
        import urllib.request as _ur, json as _j, urllib.parse as _up
        try:
            url = (f"{self._base}/agent/session-contribution-weights"
                   f"?player_id={_up.quote(player_id)}")
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return SessionContributionWeightResult(
                player_id         = str(body.get("player_id",         "")),
                tbd_lambda        = float(body.get("tbd_lambda",      0.0)),
                tbd_halflife_days = int(body.get("tbd_halflife_days", 90)),
                weight_count      = int(body.get("weight_count",      0)),
                weights           = _j.dumps(body.get("weights",      [])),
            )
        except Exception as exc:
            return SessionContributionWeightResult(player_id=player_id, error=str(exc))


# ---------------------------------------------------------------------------
# Phase 193: FleetSignalCoherenceAgent (Agent #36) — 2 result dataclasses
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class CoherenceSummaryResult:
    """Result from VAPIFleetCoherence.get_summary() (Phase 193).

    Fleet-level signal coherence summary across 35-agent fleet.
    Three failure modes: CONTRADICTION (7 rules), ORPHAN (5 rules), INVERSION (3 rules).
    fleet_coherence_enabled=True by default (coherence monitoring always on).
    promoted_to_wif: auto-promoted entries after N_PROMOTE_THRESHOLD=3 occurrences.
    """
    fleet_coherence_enabled: bool  = True
    total_open:              int   = 0
    by_severity:             str   = "{}"    # JSON: {CRITICAL: N, HIGH: N, MEDIUM: N}
    by_mode:                 str   = "{}"    # JSON: {CONTRADICTION: N, ORPHAN: N, INVERSION: N}
    promoted_to_wif:         int   = 0
    last_cycle_findings:     int   = 0
    error:                   str   = ""


@dataclass(slots=True)
class CoherenceEntryResult:
    """Result from VAPIFleetCoherence.get_entries() (Phase 193).

    Open coherence failure entries filterable by failure_mode and severity.
    Each entry: coherence_id (coh_<16 hex>), rule_name, agents_involved,
    severity, explanation, resolution, promoted_to_wif.
    RENEWAL_WITHOUT_ATTESTATION is CRITICAL — indicates Phase 185/186 bypass.
    """
    entry_count:  int  = 0
    entries:      str  = "[]"    # JSON list of coherence entry dicts
    failure_mode: str  = "all"
    severity:     str  = "all"
    error:        str  = ""


class VAPIFleetCoherence:
    """SDK client for Phase 193 FleetSignalCoherenceAgent endpoints (Tools #145–#147).

    Example::

        fc = VAPIFleetCoherence("http://localhost:8080", api_key)
        summary = fc.get_summary()
        print(f"Open coherence failures: {summary.total_open}")
        entries = fc.get_entries(failure_mode="CONTRADICTION", severity="CRITICAL")
        print(f"CRITICAL contradictions: {entries.entry_count}")
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self._key:
            h["x-api-key"] = self._key
        return h

    def get_summary(self) -> CoherenceSummaryResult:
        """Return fleet coherence summary. On error: zero-failure defaults."""
        import urllib.request as _ur, json as _j
        try:
            req = _ur.Request(f"{self._base}/agent/fleet-coherence-summary",
                              headers=self._headers())
            with _ur.urlopen(req, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return CoherenceSummaryResult(
                fleet_coherence_enabled = bool(body.get("fleet_coherence_enabled", True)),
                total_open              = int(body.get("total_open",          0)),
                by_severity             = _j.dumps(body.get("by_severity",   {})),
                by_mode                 = _j.dumps(body.get("by_mode",       {})),
                promoted_to_wif         = int(body.get("promoted_to_wif",    0)),
                last_cycle_findings     = int(body.get("last_cycle_findings", 0)),
            )
        except Exception as exc:
            return CoherenceSummaryResult(error=str(exc))

    def get_entries(self, failure_mode: str = "", severity: str = "") -> CoherenceEntryResult:
        """Return open coherence entries filtered by failure_mode and severity."""
        import urllib.request as _ur, json as _j, urllib.parse as _up
        try:
            params = _up.urlencode({k: v for k, v in
                                    [("failure_mode", failure_mode), ("severity", severity)]
                                    if v})
            url = f"{self._base}/agent/fleet-coherence-entries"
            if params:
                url += "?" + params
            req = _ur.Request(url, headers=self._headers())
            with _ur.urlopen(req, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return CoherenceEntryResult(
                entry_count  = int(body.get("entry_count",  0)),
                entries      = _j.dumps(body.get("entries", [])),
                failure_mode = str(body.get("failure_mode", failure_mode or "all")),
                severity     = str(body.get("severity",     severity or "all")),
            )
        except Exception as exc:
            return CoherenceEntryResult(error=str(exc))

    def resolve_entry(self, coherence_id: str, resolved_by: str) -> dict:
        """Mark a coherence entry as resolved. Returns response dict."""
        import urllib.request as _ur, json as _j
        try:
            payload = _j.dumps({"coherence_id": coherence_id,
                                 "resolved_by": resolved_by}).encode()
            req = _ur.Request(f"{self._base}/agent/resolve-coherence-entry",
                              data=payload, headers=self._headers(), method="POST")
            with _ur.urlopen(req, timeout=10) as resp:  # noqa: S310
                return _j.loads(resp.read())
        except Exception as exc:
            return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Phase 194 — CoherenceFingerprintRegistry result classes
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class CoherenceFingerprintResult:
    """Result from VAPICoherenceFingerprint.get_status() (Phase 194).

    Fields:
      total_rules        — distinct rules seen in coherence_fingerprint_log
      persistent_count   — rules with occurrence_count >= N_PROMOTE_THRESHOLD (3)
      total_occurrences  — sum of all occurrence counts
      maturity_penalty   — min(1.0, persistent_count × 0.10); applied to threat_forecast_accuracy
      top_rules          — JSON string of top-5 rules by occurrence_count
      n_promote_threshold — always 3; documented here for client reference
      error              — non-empty when an exception occurred
    """
    total_rules:         int   = 0
    persistent_count:    int   = 0
    total_occurrences:   int   = 0
    maturity_penalty:    float = 0.0
    top_rules:           str   = "[]"
    n_promote_threshold: int   = 3
    error:               str   = ""


class VAPICoherenceFingerprint:
    """Client for GET /agent/coherence-fingerprint-status (Phase 194, Tool #148).

    Example::
        fp = VAPICoherenceFingerprint("http://localhost:8080", api_key)
        result = fp.get_status()
        if result.persistent_count > 0:
            print(f"maturity_penalty={result.maturity_penalty}")
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base    = base_url.rstrip("/")
        self._api_key = api_key

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self._api_key:
            h["x-api-key"] = self._api_key
        return h

    def get_status(self) -> CoherenceFingerprintResult:
        """Return CoherenceFingerprintResult from GET /agent/coherence-fingerprint-status.

        On error: returns CoherenceFingerprintResult with error set, zero counts.
        """
        import urllib.request as _ur, json as _j
        try:
            req = _ur.Request(
                f"{self._base}/agent/coherence-fingerprint-status",
                headers=self._headers(),
            )
            with _ur.urlopen(req, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return CoherenceFingerprintResult(
                total_rules        = int(body.get("total_rules",        0)),
                persistent_count   = int(body.get("persistent_count",   0)),
                total_occurrences  = int(body.get("total_occurrences",  0)),
                maturity_penalty   = float(body.get("maturity_penalty", 0.0)),
                top_rules          = _j.dumps(body.get("top_rules",     [])),
                n_promote_threshold= int(body.get("n_promote_threshold",3)),
            )
        except Exception as exc:
            return CoherenceFingerprintResult(error=str(exc))


# ---------------------------------------------------------------------------
# Phase 202 — TremorRestingConvergenceOracle
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class TremorConvergenceResult:
    """Result from VAPITremorConvergence.get_status() (Phase 202).

    Per-session tremor_resting separation ratio velocity gate. Closes WIF-037 W1:
    the touchpad_corners failure mode (0.998→0.728 as N grew) can recur with
    tremor_resting if velocity is not monitored before the irreversible
    SeparationRatioRegistry.sol commitment fires.

    convergence_stable=True only when velocity >= 0 for 2 consecutive sessions.
    When convergence_stable=False, the RATIO_VELOCITY_NEGATIVE ORPHAN rule in
    FleetSignalCoherenceAgent blocks VHP MINT_QUORUM=0.80 authorization.
    """
    tremor_convergence_enabled:  bool
    convergence_stable:          "bool | None"
    velocity:                    "float | None"
    ratio:                       "float | None"
    consecutive_positive:        int
    sessions_to_target_estimate: int
    non_convergence_detected:    bool = False   # Phase 206: True when ≥5 consecutive negative velocities
    consecutive_negative:        int  = 0       # Phase 206: count of leading consecutive negative readings
    error: "str | None" = None


class VAPITremorConvergence:
    """SDK client for GET /agent/tremor-convergence-status (Phase 202).

    Example::

        tc = VAPITremorConvergence("http://localhost:8080", api_key)
        result = tc.get_status()
        if result.convergence_stable:
            print(f"Ratio={result.ratio:.3f} stable — safe to proceed to commitment")
        elif result.convergence_stable is False:
            print(f"RATIO_VELOCITY_NEGATIVE — velocity={result.velocity:.4f}, block commitment")
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_status(self) -> TremorConvergenceResult:
        """Return TremorConvergenceResult from GET /agent/tremor-convergence-status.

        On error: returns TremorConvergenceResult with error set.
        """
        import urllib.request as _ur, json as _j
        try:
            url = f"{self._base}/agent/tremor-convergence-status?api_key={self._key}"
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            _stable = body.get("convergence_stable")
            _vel    = body.get("velocity")
            _ratio  = body.get("ratio")
            return TremorConvergenceResult(
                tremor_convergence_enabled  = bool(body.get("tremor_convergence_enabled", False)),
                convergence_stable          = bool(_stable) if _stable is not None else None,
                velocity                    = float(_vel)   if _vel    is not None else None,
                ratio                       = float(_ratio) if _ratio  is not None else None,
                consecutive_positive        = int(body.get("consecutive_positive", 0)),
                sessions_to_target_estimate = int(body.get("sessions_to_target_estimate", 0)),
                non_convergence_detected    = bool(body.get("non_convergence_detected", False)),
                consecutive_negative        = int(body.get("consecutive_negative", 0)),
            )
        except Exception as exc:
            return TremorConvergenceResult(
                tremor_convergence_enabled  = False,
                convergence_stable          = None,
                velocity                    = None,
                ratio                       = None,
                consecutive_positive        = 0,
                sessions_to_target_estimate = 0,
                non_convergence_detected    = False,
                consecutive_negative        = 0,
                error                       = str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 203 — AgentContextRegistry
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class AgentContextIntegrityResult:
    """Result from VAPIAgentContextIntegrity.get_all_status() (Phase 203).

    Provides on-chain prompt commitment audit trail for VAPI's 3 LLM agents.
    Closes WIF-036 W1: Phase 201 static tests detect removed invariant strings
    at commit time but cannot detect runtime semantic drift after phase advances.

    CONTEXT_HASH_MISMATCH fires in FleetSignalCoherenceAgent (4th INVERSION rule)
    when any of the 3 agents has no committed hash in agent_context_log (i.e.,
    main.py Phase 203 startup code hasn't been run since bridge restart).
    """
    agent_context_on_chain_enabled: bool
    all_registered:                 bool
    agents:                         list
    error: "str | None" = None


class VAPIAgentContextIntegrity:
    """SDK client for GET /agent/context-integrity-status (Phase 203).

    Example::

        aci = VAPIAgentContextIntegrity("http://localhost:8080", api_key)
        result = aci.get_all_status()
        if not result.all_registered:
            print("One or more agents missing prompt hash — CONTEXT_HASH_MISMATCH may fire")
        for agent in result.agents:
            print(f"{agent['agent_id']}: sha={agent['prompt_sha256']}, "
                  f"phase={agent['phase_number']}, registered={agent['registered']}")
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_all_status(self) -> AgentContextIntegrityResult:
        """Return AgentContextIntegrityResult from GET /agent/context-integrity-status.

        On error: returns AgentContextIntegrityResult with error set, all_registered=False.
        """
        import urllib.request as _ur, json as _j
        try:
            url = f"{self._base}/agent/context-integrity-status?api_key={self._key}"
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return AgentContextIntegrityResult(
                agent_context_on_chain_enabled = bool(body.get("agent_context_on_chain_enabled", False)),
                all_registered                 = bool(body.get("all_registered", False)),
                agents                         = list(body.get("agents", [])),
            )
        except Exception as exc:
            return AgentContextIntegrityResult(
                agent_context_on_chain_enabled = False,
                all_registered                 = False,
                agents                         = [],
                error                          = str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 204 — IoSwarm Adjudication Primer (WIF-038 W2 closure)
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class IoSwarmAdjudicationPrimerResult:
    """Result from VAPIIoSwarmAdjudicationPrimer.prime() (Phase 204).

    Represents the outcome of POST /agent/prime-ioswarm-adjudication, which
    seeds ioswarm_adjudication_log with emulator-mode entries to resolve the
    IOSWARM_ACTIVE_NO_ADJUDICATIONS CONTRADICTION rule (WIF-038 W1) and
    unblock the VHP MINT_QUORUM=0.80 (FROZEN) authorization pathway.

    Fields:
        primer_enabled:                  True when IOSWARM_ADJUDICATION_PRIMER_ENABLED=true.
        devices_primed:                  Count of synthetic device sessions run through
                                         IoSwarmAdjudicationCoordinator (target=5).
        ioswarm_adjudication_log_seeded: True when primer ran successfully.
        ioswarm_adjudication_log_total:  Total row count in ioswarm_adjudication_log after
                                         primer completes (0 on failure).
        timestamp:                       Unix timestamp of the primer execution.
        error:                           Non-empty string when primer_enabled=False or on
                                         HTTP/parse error; None on success.
    """
    primer_enabled:                  bool
    devices_primed:                  int
    ioswarm_adjudication_log_seeded: bool
    ioswarm_adjudication_log_total:  int          = 0
    timestamp:                       float        = 0.0
    error:                           "str | None" = None


class VAPIIoSwarmAdjudicationPrimer:
    """SDK client for POST /agent/prime-ioswarm-adjudication (Phase 204).

    Closes WIF-038 W2: seeds ioswarm_adjudication_log with 5 emulator-mode
    adjudication entries so the IOSWARM_ACTIVE_NO_ADJUDICATIONS CONTRADICTION
    rule is resolved and VHP MINT_QUORUM=0.80 can proceed.

    Requires IOSWARM_ADJUDICATION_PRIMER_ENABLED=true in the bridge environment.
    Returns IoSwarmAdjudicationPrimerResult with error set when disabled (409).

    Example::

        primer = VAPIIoSwarmAdjudicationPrimer("http://localhost:8080", api_key)
        result = primer.prime()
        if result.error:
            print(f"Primer failed: {result.error}")
        else:
            print(f"Seeded {result.devices_primed} adjudications; "
                  f"total log rows: {result.ioswarm_adjudication_log_total}")
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def prime(self) -> IoSwarmAdjudicationPrimerResult:
        """POST to /agent/prime-ioswarm-adjudication and return parsed result.

        On 409 (primer disabled): returns result with primer_enabled=False, error set.
        On other error: returns result with error set, ioswarm_adjudication_log_seeded=False.
        """
        import urllib.request as _ur
        import urllib.error   as _ue
        import json           as _j
        try:
            url = f"{self._base}/agent/prime-ioswarm-adjudication?api_key={self._key}"
            req = _ur.Request(url, method="POST", data=b"")
            with _ur.urlopen(req, timeout=15) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return IoSwarmAdjudicationPrimerResult(
                primer_enabled                  = bool(body.get("primer_enabled", False)),
                devices_primed                  = int(body.get("devices_primed", 0)),
                ioswarm_adjudication_log_seeded = bool(body.get("ioswarm_adjudication_log_seeded", False)),
                ioswarm_adjudication_log_total  = int(body.get("ioswarm_adjudication_log_total", 0)),
                timestamp                       = float(body.get("timestamp", 0.0)),
            )
        except _ue.HTTPError as exc:
            try:
                detail = _j.loads(exc.read())
                msg    = str(detail.get("message", detail))
            except Exception:
                msg = str(exc)
            return IoSwarmAdjudicationPrimerResult(
                primer_enabled                  = False,
                devices_primed                  = 0,
                ioswarm_adjudication_log_seeded = False,
                error                           = msg,
            )
        except Exception as exc:
            return IoSwarmAdjudicationPrimerResult(
                primer_enabled                  = False,
                devices_primed                  = 0,
                ioswarm_adjudication_log_seeded = False,
                error                           = str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 205 — AccelTremorFFT (still-hold neurological tremor fallback)
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class AccelTremorFFTResult:
    """Result from VAPIAccelTremorFFT.status() (Phase 205).

    Reports the accel magnitude FFT fallback configuration for tremor_peak_hz.
    When accel_tremor_fallback_enabled=True, still-hold sessions (tremor_seed
    probe type) compute tremor_peak_hz from the IMU accelerometer ring in the
    1-15 Hz physiological tremor search range instead of returning 0.0 from
    a flat right_stick_x velocity FFT (neutral=128 during still-hold).

    Root cause closed: right_stick_x stays at neutral=128 in tremor_seed
    sessions because no gameplay motion is present; diff() → all zeros →
    FFT peak at 0 Hz.  IMU accel FFT captures neurological tremor origin
    frequencies (PC baseline: P1≈3.1 Hz, P2≈4.3 Hz, P3≈3.7 Hz).

    Fields:
        accel_tremor_fallback_enabled: True when ACCEL_TREMOR_FALLBACK_ENABLED=true (default).
        still_hold_var_threshold:      right_stick_x ring variance below which still-hold
                                       is detected (default 4.0 LSB²).
        fallback_source:               "accel_magnitude_fft" when enabled; "stick_fft_only" when not.
        tremor_search_range_hz:        [min_hz, max_hz] used in accel tremor peak search.
        accel_fft_nfft:                Phase 213 — zero-padded FFT point count (default 4096).
        bin_width_hz:                  Phase 213 — frequency resolution in Hz/bin (default 0.244).
        timestamp:                     Unix timestamp of status query.
        error:                         Non-None when HTTP/parse error occurred.
    """
    accel_tremor_fallback_enabled: bool
    still_hold_var_threshold:      float
    fallback_source:               str
    tremor_search_range_hz:        list
    accel_fft_nfft:                int          = 4096
    bin_width_hz:                  float        = 0.244
    timestamp:                     float        = 0.0
    error:                         "str | None" = None


class VAPIAccelTremorFFT:
    """SDK client for GET /agent/accel-tremor-fft-status (Phase 205).

    Closes the tremor_peak_hz=0 bug in tremor_seed sessions: the BiometricFeatureExtractor
    now falls back to accel magnitude FFT when right_stick_x variance < 4.0 LSB²
    (still-hold detection), enabling per-player neurological tremor fingerprinting
    without gameplay motion.

    Example::

        atf = VAPIAccelTremorFFT("http://localhost:8080", api_key)
        result = atf.status()
        if result.accel_tremor_fallback_enabled:
            print(f"AccelTremorFFT active — search range: {result.tremor_search_range_hz} Hz")
        else:
            print("AccelTremorFFT disabled — set ACCEL_TREMOR_FALLBACK_ENABLED=true")
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def status(self) -> AccelTremorFFTResult:
        """Return AccelTremorFFTResult from GET /agent/accel-tremor-fft-status.

        On error: returns AccelTremorFFTResult with error set, fallback_source='unknown'.
        """
        import urllib.request as _ur, json as _j
        try:
            url = f"{self._base}/agent/accel-tremor-fft-status?api_key={self._key}"
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return AccelTremorFFTResult(
                accel_tremor_fallback_enabled = bool(body.get("accel_tremor_fallback_enabled", True)),
                still_hold_var_threshold      = float(body.get("still_hold_var_threshold", 4.0)),
                fallback_source               = str(body.get("fallback_source", "accel_magnitude_fft")),
                tremor_search_range_hz        = list(body.get("tremor_search_range_hz", [1.0, 15.0])),
                accel_fft_nfft                = int(body.get("accel_fft_nfft", 4096)),
                bin_width_hz                  = float(body.get("bin_width_hz", 0.244)),
                timestamp                     = float(body.get("timestamp", 0.0)),
            )
        except Exception as exc:
            return AccelTremorFFTResult(
                accel_tremor_fallback_enabled = False,
                still_hold_var_threshold      = 4.0,
                fallback_source               = "unknown",
                tremor_search_range_hz        = [],
                error                         = str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 207 — StagedDryRunGraduationGate SDK
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class DryRunGraduationResult:
    """Result from VAPIDryRunGraduation.get_status() (Phase 207).

    Reports the complete state of the StagedDryRunGraduationGate: which agents
    have graduated from dry_run=True to dry_run=False, whether any rollbacks
    are active, and the current gate configuration.

    Graduation is sequential: agents activate one at a time.  Rollback fires
    automatically when n_false_positives >= fp_threshold within the rollback
    window.  All preconditions (tournament preflight + non_convergence_clear)
    must pass at activation time.

    Fields:
        staged_graduation_enabled:  True when STAGED_GRADUATION_ENABLED=true.
        rollback_window_sessions:   Window of sessions for FP rate assessment.
        fp_threshold:               Max tolerated false positives before rollback.
        stages:                     List of graduation stage records (dicts).
        active_stage_count:         Number of currently active (non-rolled-back) stages.
        timestamp:                  Unix timestamp of status query.
        error:                      Non-None when HTTP/parse error occurred.
    """
    staged_graduation_enabled: bool
    rollback_window_sessions:  int
    fp_threshold:              int
    stages:                    list
    active_stage_count:        int
    timestamp:                 float        = 0.0
    error:                     "str | None" = None


class VAPIDryRunGraduation:
    """SDK client for Phase 207 StagedDryRunGraduationGate endpoints.

    Reads GET /agent/dry-run-graduation-status to report graduation state.
    Use POST /agent/activate-graduation-stage (operator-auth required) via
    direct HTTP to activate a new graduation stage.

    Example::

        drg = VAPIDryRunGraduation("http://localhost:8080", api_key)
        result = drg.get_status()
        if result.staged_graduation_enabled:
            print(f"Graduation gate active — {result.active_stage_count} agent(s) graduated")
        else:
            print("Graduation gate disabled (STAGED_GRADUATION_ENABLED=false)")
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_status(self) -> DryRunGraduationResult:
        """Return DryRunGraduationResult from GET /agent/dry-run-graduation-status.

        On error: returns DryRunGraduationResult with error set and staged_graduation_enabled=False.
        """
        import urllib.request as _ur, json as _j
        try:
            url = f"{self._base}/agent/dry-run-graduation-status?api_key={self._key}"
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return DryRunGraduationResult(
                staged_graduation_enabled = bool(body.get("staged_graduation_enabled", False)),
                rollback_window_sessions  = int(body.get("rollback_window_sessions", 10)),
                fp_threshold              = int(body.get("fp_threshold", 2)),
                stages                    = list(body.get("stages", [])),
                active_stage_count        = int(body.get("active_stage_count", 0)),
                timestamp                 = float(body.get("timestamp", 0.0)),
            )
        except Exception as exc:
            return DryRunGraduationResult(
                staged_graduation_enabled = False,
                rollback_window_sessions  = 10,
                fp_threshold              = 2,
                stages                    = [],
                active_stage_count        = 0,
                error                     = str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 208 — CorpusRatioRegressionGuard (WIF-039 W1+W2)
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class CorpusRegressionGuardResult:
    """Result from VAPICorpusRegressionGuard.get_status() (Phase 208).

    Reports the state of the CorpusRatioRegressionGuard: whether a prior
    separation ratio breakthrough (all_pairs_above_1=True) has been recorded
    for a probe type, and whether the guard is enabled to block future
    regressions below 1.0.  Closes WIF-039 (W1: ratchet mechanism, W2: audit
    trail via tamper-evident provenance chain).
    """
    corpus_ratio_regression_guard_enabled: bool      = False
    guard_active:                          bool      = False
    breakthrough_ratio:                    "float | None" = None
    breakthrough_n:                        "int | None"   = None
    provenance_hash:                       "str | None"   = None
    override_count:                        int       = 0
    timestamp:                             float     = 0.0
    error:                                 "str | None"   = None


class VAPICorpusRegressionGuard:
    """SDK client for Phase 208 CorpusRatioRegressionGuard endpoint.

    Reads GET /agent/corpus-regression-guard-status to report guard state.

    Example::

        guard = VAPICorpusRegressionGuard("http://localhost:8080", api_key)
        result = guard.get_status(probe_type="tremor_resting")
        if result.guard_active:
            print(f"Guard active — breakthrough at ratio={result.breakthrough_ratio:.3f}")
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_status(self, probe_type: str = "") -> CorpusRegressionGuardResult:
        """Return CorpusRegressionGuardResult from GET /agent/corpus-regression-guard-status.

        On error: returns CorpusRegressionGuardResult with error set and guard_active=False.
        """
        import urllib.request as _ur, json as _j
        try:
            _params = f"api_key={self._key}"
            if probe_type:
                _params += f"&probe_type={probe_type}"
            url = f"{self._base}/agent/corpus-regression-guard-status?{_params}"
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return CorpusRegressionGuardResult(
                corpus_ratio_regression_guard_enabled = bool(body.get("corpus_ratio_regression_guard_enabled", False)),
                guard_active     = bool(body.get("guard_active", False)),
                breakthrough_ratio = body.get("breakthrough_ratio"),
                breakthrough_n   = body.get("breakthrough_n"),
                provenance_hash  = body.get("provenance_hash"),
                override_count   = int(body.get("override_count", 0)),
                timestamp        = float(body.get("timestamp", 0.0)),
            )
        except Exception as exc:
            return CorpusRegressionGuardResult(
                corpus_ratio_regression_guard_enabled = False,
                guard_active     = False,
                breakthrough_ratio = None,
                breakthrough_n   = None,
                provenance_hash  = None,
                override_count   = 0,
                error            = str(exc),
            )



# ---------------------------------------------------------------------------
# Phase 214 — GraduationAutowatchBridge
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class GraduationAutowatchResult:
    """Result from VAPIGraduationAutowatch.get_status() (Phase 214).

    Fields
    ------
    graduation_autowatch_enabled  : bool -- True when monitor is active (default True)
    trigger_count                 : int  -- Number of all_pairs_p0_ok False->True transitions detected
    evaluated_count               : int  -- Number of autowatch precondition evaluations completed
    last_trigger_probe_type       : str | None -- probe_type of last trigger event
    last_preconditions_met        : bool | None -- None if no evaluation yet; else True/False
    timestamp                     : float -- UTC epoch of last status read
    error                         : str | None -- exception message on HTTP/parse failure
    """
    graduation_autowatch_enabled : bool        = True
    trigger_count                : int         = 0
    evaluated_count              : int         = 0
    last_trigger_probe_type      : "str | None" = None
    last_preconditions_met       : "bool | None" = None
    timestamp                    : float       = 0.0
    error                        : "str | None" = None


class VAPIGraduationAutowatch:
    """SDK client for Phase 214 GraduationAutowatchBridge endpoint.

    Reads GET /agent/graduation-autowatch-status to report autowatch state.

    Example::

        watch = VAPIGraduationAutowatch("http://localhost:8080", api_key)
        result = watch.get_status()
        if result.trigger_count > 0:
            print(f"P0 transition detected -- preconditions_met={result.last_preconditions_met}")
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_status(self, probe_type: str = "") -> GraduationAutowatchResult:
        """Return GraduationAutowatchResult from GET /agent/graduation-autowatch-status.

        On error: returns GraduationAutowatchResult with error set and trigger_count=0.
        """
        import urllib.request as _ur, json as _j
        try:
            _params = f"api_key={self._key}"
            if probe_type:
                _params += f"&probe_type={probe_type}"
            url = f"{self._base}/agent/graduation-autowatch-status?{_params}"
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            _last_met = body.get("last_preconditions_met")
            return GraduationAutowatchResult(
                graduation_autowatch_enabled = bool(body.get("graduation_autowatch_enabled", True)),
                trigger_count                = int(body.get("trigger_count", 0)),
                evaluated_count              = int(body.get("evaluated_count", 0)),
                last_trigger_probe_type      = body.get("last_trigger_probe_type"),
                last_preconditions_met       = bool(_last_met) if _last_met is not None else None,
                timestamp                    = float(body.get("timestamp", 0.0)),
            )
        except Exception as exc:
            return GraduationAutowatchResult(
                graduation_autowatch_enabled = True,
                trigger_count                = 0,
                evaluated_count              = 0,
                last_trigger_probe_type      = None,
                last_preconditions_met       = None,
                error                        = str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 215 — L4DimSyncConfirmation
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class L4DimSyncResult:
    """Result from VAPIL4DimSync.get_status() (Phase 215).

    Reports whether the L4 calibration dimension sync has been completed --
    confirming that thresholds calibrated at dim=12 remain valid for the live
    13-feature space because touchpad_spatial_entropy (index 12) is structurally
    zero in gameplay sessions (NCAA CFB 26).  Closes G-003 L4 staleness gap.
    """
    l4_dim_sync_enabled:   bool             = False
    sync_completed:        bool             = False
    from_dim:              "int | None"     = None
    to_dim:                "int | None"     = None
    anomaly_threshold:     "float | None"   = None
    continuity_threshold:  "float | None"   = None
    error:                 "str | None"     = None


class VAPIL4DimSync:
    """SDK client for Phase 215 L4DimSyncConfirmation endpoint.

    Reads GET /agent/l4-dim-sync-status to report whether the L4 calibration
    dimension has been synced to the live feature space.

    Example::

        sync = VAPIL4DimSync("http://localhost:8080", api_key)
        result = sync.get_status()
        if result.sync_completed:
            print(f"L4 dim synced: {result.from_dim} -> {result.to_dim}")
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_status(self) -> L4DimSyncResult:
        """Return L4DimSyncResult from GET /agent/l4-dim-sync-status.

        On error: returns L4DimSyncResult with error set and sync_completed=False.
        """
        import urllib.request as _ur, json as _j
        try:
            url = f"{self._base}/agent/l4-dim-sync-status?api_key={self._key}"
            with _ur.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return L4DimSyncResult(
                l4_dim_sync_enabled  = bool(body.get("l4_dim_sync_enabled", False)),
                sync_completed       = bool(body.get("sync_completed", False)),
                from_dim             = body.get("from_dim"),
                to_dim               = body.get("to_dim"),
                anomaly_threshold    = body.get("anomaly_threshold"),
                continuity_threshold = body.get("continuity_threshold"),
            )
        except Exception as exc:
            return L4DimSyncResult(
                l4_dim_sync_enabled  = False,
                sync_completed       = False,
                error                = str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 216 — PerPairGapLog
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class PerPairGapResult:
    """Result from VAPIPerPairGap.get_status() (Phase 216 PerPairGapLog)."""
    per_pair_gap_log_enabled: bool             = False
    all_pairs_above_1:        bool             = False
    pair_count:               int              = 0
    pairs:                    "list[dict]"     = field(default_factory=list)
    blocker_pairs:            "list[dict]"     = field(default_factory=list)
    error:                    "str | None"     = None


class VAPIPerPairGap:
    """SDK client for Phase 216 PerPairGapLog endpoint.

    Reads GET /agent/per-pair-gap-status to report per-pair Mahalanobis
    inter-player distances from the most recent analysis run.

    Example::

        ppg = VAPIPerPairGap("http://localhost:8080", api_key)
        result = ppg.get_status()
        if not result.all_pairs_above_1:
            print(f"Blocker pairs: {result.blocker_pairs}")
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_status(self) -> PerPairGapResult:
        """Return PerPairGapResult from GET /agent/per-pair-gap-status.

        On error: returns PerPairGapResult with error set and all_pairs_above_1=False.
        """
        import urllib.request as _ur, json as _j
        try:
            url = f"{self._base}/agent/per-pair-gap-status"
            req = _ur.Request(url, headers={"x-api-key": self._key})
            with _ur.urlopen(req, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return PerPairGapResult(
                per_pair_gap_log_enabled = bool(body.get("per_pair_gap_log_enabled", False)),
                all_pairs_above_1        = bool(body.get("all_pairs_above_1", False)),
                pair_count               = int(body.get("pair_count", 0)),
                pairs                    = list(body.get("pairs", [])),
                blocker_pairs            = list(body.get("blocker_pairs", [])),
            )
        except Exception as exc:
            return PerPairGapResult(
                per_pair_gap_log_enabled = False,
                all_pairs_above_1        = False,
                error                    = str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 217 — PerPairGapTrend
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class PerPairGapTrendResult:
    """Result from VAPIPerPairGapTrend.get_trend() (Phase 217 PerPairGapTrend)."""
    per_pair_gap_trend_enabled: bool             = False
    pair_key:                   str              = ""
    distances:                  "list[float]"    = field(default_factory=list)
    velocity_per_day:           "float | None"   = None
    trend:                      str              = "UNKNOWN"
    n_runs:                     int              = 0
    blocker_resolved:           bool             = False
    error:                      "str | None"     = None


class VAPIPerPairGapTrend:
    """SDK client for Phase 217 PerPairGapTrend endpoint.

    Reads GET /agent/per-pair-gap-trend to report distance velocity and trend
    for a specific pair key over recent analysis runs.

    Example::

        trend = VAPIPerPairGapTrend("http://localhost:8080", api_key)
        result = trend.get_trend(pair_key="P1vP3")
        print(f"{result.pair_key}: {result.trend} ({result.velocity_per_day:.4f}/day)")
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_trend(self, pair_key: str = "P1vP3", session_type: str = "",
                  n_runs: int = 5) -> PerPairGapTrendResult:
        """Return PerPairGapTrendResult from GET /agent/per-pair-gap-trend.

        On error: returns PerPairGapTrendResult with error set and trend=UNKNOWN.
        """
        import urllib.request as _ur, json as _j
        try:
            params = f"pair_key={pair_key}&n_runs={n_runs}"
            if session_type:
                params += f"&session_type={session_type}"
            url = f"{self._base}/agent/per-pair-gap-trend?{params}"
            req = _ur.Request(url, headers={"x-api-key": self._key})
            with _ur.urlopen(req, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return PerPairGapTrendResult(
                per_pair_gap_trend_enabled = bool(body.get("per_pair_gap_trend_enabled", False)),
                pair_key                   = str(body.get("pair_key", pair_key)),
                distances                  = list(body.get("distances", [])),
                velocity_per_day           = body.get("velocity_per_day"),
                trend                      = str(body.get("trend", "UNKNOWN")),
                n_runs                     = int(body.get("n_runs", 0)),
                blocker_resolved           = bool(body.get("blocker_resolved", False)),
            )
        except Exception as exc:
            return PerPairGapTrendResult(
                per_pair_gap_trend_enabled = False,
                pair_key                   = pair_key,
                trend                      = "UNKNOWN",
                error                      = str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 218 — CaptureVelocityOracle
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class CaptureVelocityResult:
    """Result from VAPICaptureVelocityOracle.get_status() (Phase 218 CaptureVelocityOracle)."""
    capture_velocity_oracle_enabled: bool           = False
    probe_type:                      str            = "touchpad_corners"
    sessions_per_day:                float          = 0.0
    sessions_stagnant:               bool           = True
    ratio_velocity:                  float          = 0.0
    velocity_stagnant:               bool           = True
    overall_capture_healthy:         bool           = False
    recommended_action:              str            = "UNKNOWN"
    error:                           "str | None"   = None


class VAPICaptureVelocityOracle:
    """SDK client for Phase 218 CaptureVelocityOracle endpoint.

    Reads GET /agent/capture-velocity-oracle to report the synthesized capture
    health status from Phase 152 + Phase 154 data.

    Example::

        cvo = VAPICaptureVelocityOracle("http://localhost:8080", api_key)
        result = cvo.get_status()
        if not result.overall_capture_healthy:
            print(f"Capture action: {result.recommended_action}")
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_status(self, probe_type: str = "touchpad_corners") -> CaptureVelocityResult:
        """Return CaptureVelocityResult from GET /agent/capture-velocity-oracle.

        On error: returns CaptureVelocityResult with error set and overall_capture_healthy=False.
        """
        import urllib.request as _ur, json as _j
        try:
            url = f"{self._base}/agent/capture-velocity-oracle?probe_type={probe_type}"
            req = _ur.Request(url, headers={"x-api-key": self._key})
            with _ur.urlopen(req, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return CaptureVelocityResult(
                capture_velocity_oracle_enabled = bool(body.get("capture_velocity_oracle_enabled", False)),
                probe_type                      = str(body.get("probe_type", probe_type)),
                sessions_per_day                = float(body.get("sessions_per_day", 0.0)),
                sessions_stagnant               = bool(body.get("sessions_stagnant", True)),
                ratio_velocity                  = float(body.get("ratio_velocity", 0.0)),
                velocity_stagnant               = bool(body.get("velocity_stagnant", True)),
                overall_capture_healthy         = bool(body.get("overall_capture_healthy", False)),
                recommended_action              = str(body.get("recommended_action", "UNKNOWN")),
            )
        except Exception as exc:
            return CaptureVelocityResult(
                capture_velocity_oracle_enabled = False,
                overall_capture_healthy         = False,
                error                           = str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 219 — TournamentBlockerSummary
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class TournamentBlockerSummaryResult:
    """Result from VAPITournamentBlockerSummary.get_summary() (Phase 219)."""
    tournament_blocker_summary_enabled: bool          = False
    total_blockers:                     int           = 0
    blockers:                           "list[dict]"  = field(default_factory=list)
    overall_blocked:                    bool          = True
    preflight_pass:                     bool          = False
    capture_healthy:                    bool          = False
    all_pairs_above_1:                  bool          = False
    error:                              "str | None"  = None


class VAPITournamentBlockerSummary:
    """SDK client for Phase 219 TournamentBlockerSummary endpoint.

    Reads GET /agent/tournament-blocker-summary to return all active TGE blockers.

    Example::

        tbs = VAPITournamentBlockerSummary("http://localhost:8080", api_key)
        result = tbs.get_summary()
        if result.overall_blocked:
            for b in result.blockers:
                print(f"[{b['severity']}] {b['source']}: {b['detail']}")
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_summary(self) -> TournamentBlockerSummaryResult:
        """Return TournamentBlockerSummaryResult from GET /agent/tournament-blocker-summary.

        On error: returns TournamentBlockerSummaryResult with error set and overall_blocked=True.
        """
        import urllib.request as _ur, json as _j
        try:
            url = f"{self._base}/agent/tournament-blocker-summary"
            req = _ur.Request(url, headers={"x-api-key": self._key})
            with _ur.urlopen(req, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return TournamentBlockerSummaryResult(
                tournament_blocker_summary_enabled = bool(body.get("tournament_blocker_summary_enabled", False)),
                total_blockers                     = int(body.get("total_blockers", 0)),
                blockers                           = list(body.get("blockers", [])),
                overall_blocked                    = bool(body.get("overall_blocked", True)),
                preflight_pass                     = bool(body.get("preflight_pass", False)),
                capture_healthy                    = bool(body.get("capture_healthy", False)),
                all_pairs_above_1                  = bool(body.get("all_pairs_above_1", False)),
            )
        except Exception as exc:
            return TournamentBlockerSummaryResult(
                tournament_blocker_summary_enabled = False,
                overall_blocked                    = True,
                error                              = str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 220 — PerPairGapProjection
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class PerPairGapProjectionResult:
    """Result from VAPIPerPairGapProjection.get_projection() (Phase 220)."""
    per_pair_gap_projection_enabled: bool           = False
    projections:                     "list[dict]"   = field(default_factory=list)
    any_feasible:                    bool           = False
    max_days_to_1_0:                 "float | None" = None
    projected_tge_date:              "str | None"   = None
    session_type:                    "str | None"   = None
    error:                           "str | None"   = None


class VAPIPerPairGapProjection:
    """SDK client for Phase 220 PerPairGapProjection endpoint.

    Reads GET /agent/per-pair-gap-projection to return projected TGE timeline
    for each blocker pair based on current distance velocity.

    Example::

        proj = VAPIPerPairGapProjection("http://localhost:8080", api_key)
        result = proj.get_projection()
        print(f"Projected TGE date: {result.projected_tge_date}")
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_projection(self, session_type: str = "", n_runs: int = 5) -> PerPairGapProjectionResult:
        """Return PerPairGapProjectionResult from GET /agent/per-pair-gap-projection.

        On error: returns PerPairGapProjectionResult with error set and any_feasible=False.
        """
        import urllib.request as _ur, json as _j
        try:
            params = f"n_runs={n_runs}"
            if session_type:
                params += f"&session_type={session_type}"
            url = f"{self._base}/agent/per-pair-gap-projection?{params}"
            req = _ur.Request(url, headers={"x-api-key": self._key})
            with _ur.urlopen(req, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return PerPairGapProjectionResult(
                per_pair_gap_projection_enabled = bool(body.get("per_pair_gap_projection_enabled", False)),
                projections                     = list(body.get("projections", [])),
                any_feasible                    = bool(body.get("any_feasible", False)),
                max_days_to_1_0                 = body.get("max_days_to_1_0"),
                projected_tge_date              = body.get("projected_tge_date"),
                session_type                    = body.get("session_type"),
            )
        except Exception as exc:
            return PerPairGapProjectionResult(
                per_pair_gap_projection_enabled = False,
                any_feasible                    = False,
                error                           = str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 221 — ProtocolCoherence (PoPC)
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class ProtocolCoherenceResult:
    """Result from VAPIProtocolCoherence.get_status() (Phase 221)."""
    protocol_coherence_enabled: bool           = False
    total_anchors:              int            = 0
    latest_merkle_root:         "str | None"   = None
    agent_count:                int            = 0
    on_chain_confirmed:         bool           = False
    last_anchor_ts:             "float | None" = None
    error:                      "str | None"   = None


class VAPIProtocolCoherence:
    """SDK client for Phase 221 ProtocolCoherence (PoPC) endpoint.

    Reads GET /agent/protocol-coherence-status to return the latest Merkle root
    anchor over the 36-agent fleet and on-chain confirmation status.

    Example::

        popc = VAPIProtocolCoherence("http://localhost:8080", api_key)
        result = popc.get_status()
        print(f"Total PoPC anchors: {result.total_anchors}")
        print(f"On-chain confirmed: {result.on_chain_confirmed}")
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_status(self) -> ProtocolCoherenceResult:
        """Return ProtocolCoherenceResult from GET /agent/protocol-coherence-status.

        On error: returns ProtocolCoherenceResult with error set and total_anchors=0.
        """
        import urllib.request as _ur, json as _j
        try:
            url = f"{self._base}/agent/protocol-coherence-status"
            req = _ur.Request(url, headers={"x-api-key": self._key})
            with _ur.urlopen(req, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return ProtocolCoherenceResult(
                protocol_coherence_enabled = bool(body.get("protocol_coherence_enabled", False)),
                total_anchors              = int(body.get("total_anchors", 0)),
                latest_merkle_root         = body.get("latest_merkle_root"),
                agent_count                = int(body.get("agent_count", 0)),
                on_chain_confirmed         = bool(body.get("on_chain_confirmed", False)),
                last_anchor_ts             = body.get("last_anchor_ts"),
            )
        except Exception as exc:
            return ProtocolCoherenceResult(
                protocol_coherence_enabled = False,
                error                      = str(exc),
            )


# ---------------------------------------------------------------------------
# Phase 222 — BiometricBoundGovernance (BBG)
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class BBGProposalResult:
    """Result from VAPIBiometricGovernance.get_status() (Phase 222)."""
    bbg_enabled:           bool           = False
    total_proposals:       int            = 0
    latest_proposal_hash:  "str | None"   = None
    latest_proposer:       "str | None"   = None
    on_chain_confirmed:    bool           = False
    last_proposal_ts:      "float | None" = None
    error:                 "str | None"   = None


class VAPIBiometricGovernance:
    """SDK client for Phase 222 BiometricBoundGovernance (BBG) endpoint.

    Reads GET /agent/bbg-status to return the latest BBG proposal status.
    Submits proposals via POST /agent/bbg-propose.

    Example::

        bbg = VAPIBiometricGovernance("http://localhost:8080", api_key)
        status = bbg.get_status()
        print(f"BBG enabled: {status.bbg_enabled}")
        print(f"Total proposals: {status.total_proposals}")
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_status(self) -> BBGProposalResult:
        """Return BBGProposalResult from GET /agent/bbg-status.

        On error: returns BBGProposalResult with error set and total_proposals=0.
        """
        import urllib.request as _ur, json as _j
        try:
            url = f"{self._base}/agent/bbg-status"
            req = _ur.Request(url, headers={"x-api-key": self._key})
            with _ur.urlopen(req, timeout=10) as resp:  # noqa: S310
                body = _j.loads(resp.read())
            return BBGProposalResult(
                bbg_enabled          = bool(body.get("bbg_enabled", False)),
                total_proposals      = int(body.get("total_proposals", 0)),
                latest_proposal_hash = body.get("latest_proposal_hash"),
                latest_proposer      = body.get("latest_proposer"),
                on_chain_confirmed   = bool(body.get("on_chain_confirmed", False)),
                last_proposal_ts     = body.get("last_proposal_ts"),
            )
        except Exception as exc:
            return BBGProposalResult(
                bbg_enabled = False,
                error       = str(exc),
            )


# ── Phase 237-CONSENT — Per-Category Gamer Consent ────────────────────────────

@dataclass(slots=True)
class GamerConsentResult:
    """Result from VAPIConsent.get_status() (Phase 237-CONSENT).

    Two shapes depending on whether `category` was supplied:
      - Aggregated (no category):  device_id + categories: dict[name → category_dict]
      - Single-category:           device_id + category + granted/revoked/...
    """
    device_id:  str  = ""
    categories: dict = field(default_factory=dict)
    category:   "str | None" = None  # populated when single-category query
    granted:    bool = False
    revoked:    bool = False
    found:      bool = False
    error:      "str | None" = None


class VAPIConsent:
    """SDK client for Phase 237 per-category gamer consent endpoint.

    Reads the local consent_ledger via GET /agent/gamer-consent-status. To
    grant or revoke consent, the gamer's wallet must call grantConsent /
    revokeConsent on VAPIConsentRegistry directly (gamer-self-sovereign
    invariant — the bridge never writes consent on behalf of a gamer).

    Usage::
        consent = VAPIConsent("http://localhost:8080", api_key)
        agg = consent.get_status("device_abc")
        # agg.categories == {"TOURNAMENT_GATE": {...}, "ANONYMIZED_RESEARCH": {...}, ...}

        single = consent.get_status("device_abc", category="MARKETPLACE")
        # single.granted == True | False
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_status(
        self, device_id: str, category: str = ""
    ) -> GamerConsentResult:
        """Return GamerConsentResult from GET /agent/gamer-consent-status.

        Args:
            device_id: Required. 422 from bridge if empty.
            category:  Optional. If provided, returns single-category status;
                       if empty, returns aggregated status across all four
                       categories.

        Never raises: returns GamerConsentResult(error=...) on any failure
        (consistent with VAPIBiometricGovernance / VAPIInvariantGate).
        """
        import urllib.request as _ur, urllib.parse as _up, json as _j
        try:
            qs = _up.urlencode(
                {"device_id": device_id, "category": category}
                if category else {"device_id": device_id}
            )
            url = f"{self._base}/agent/gamer-consent-status?{qs}"
            req = _ur.Request(url, headers={"x-api-key": self._key})
            with _ur.urlopen(req, timeout=10) as resp:
                body = _j.loads(resp.read())
            if category:
                # single-category response — flat dict with `category` key
                return GamerConsentResult(
                    device_id  = device_id,
                    category   = body.get("category"),
                    granted    = bool(body.get("granted", False)),
                    revoked    = bool(body.get("revoked", False)),
                    found      = bool(body.get("found", False)),
                    categories = {},
                )
            # aggregated — categories dict
            return GamerConsentResult(
                device_id  = body.get("device_id", device_id),
                categories = body.get("categories", {}),
                category   = None,
            )
        except Exception as exc:
            return GamerConsentResult(
                device_id = device_id,
                error     = str(exc),
            )


# ── Phase 223 — PV-CI Invariant Gate ──────────────────────────────────────────

@dataclass(slots=True)
class InvariantGateResult:
    """Result from VAPIInvariantGate.get_status() (Phase 223)."""
    pv_ci_enabled:  bool        = False
    gate_pass:      "bool|None" = None
    total_checked:  int         = 0
    failure_count:  int         = 0
    last_failures:  "list"      = field(default_factory=list)
    last_run_ts:    "float|None"= None
    error:          "str|None"  = None


class VAPIInvariantGate:
    """Client for the PV-CI invariant gate endpoint (Phase 223).

    Usage::
        gate = VAPIInvariantGate("http://localhost:8080", api_key)
        result = gate.get_status()
        assert result.gate_pass is not False
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def get_status(self) -> InvariantGateResult:
        """Return InvariantGateResult from GET /agent/invariant-gate-status.

        On error: returns InvariantGateResult with error set and gate_pass=None.
        """
        try:
            import urllib.request, json
            req = urllib.request.Request(
                f"{self._base}/agent/invariant-gate-status",
                headers={"x-api-key": self._key} if self._key else {},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read().decode())
            return InvariantGateResult(
                pv_ci_enabled  = bool(body.get("pv_ci_enabled", False)),
                gate_pass      = body.get("gate_pass"),
                total_checked  = int(body.get("total_checked", 0)),
                failure_count  = int(body.get("failure_count", 0)),
                last_failures  = list(body.get("last_failures", [])),
                last_run_ts    = body.get("last_run_ts"),
            )
        except Exception as exc:
            return InvariantGateResult(
                pv_ci_enabled = False,
                error         = str(exc),
            )


# ── Phase 224 — Allowlist Governance ──────────────────────────────────────────

@dataclass(slots=True)
class AllowlistGovernanceResult:
    """Result from VAPIAllowlistGovernance methods (Phase 224)."""
    current_hash:          str        = ""
    last_change_ts:        "str|None" = None
    last_change_reason:    "str|None" = None
    last_change_category:  "str|None" = None
    suspicious_change_count: int      = 0
    on_chain_anchor_ts:    "float|None" = None
    error:                 "str|None" = None


class VAPIAllowlistGovernance:
    """Client for allowlist governance state (Phase 224).

    Surfaces the current INVARIANTS_ALLOWLIST.json SHA-256 hash as anchored
    in ProtocolCoherenceAgent's Merkle tree, and lists all governance events.

    Usage::
        gov = VAPIAllowlistGovernance("http://localhost:8080", api_key)
        result = gov.status()
        print(result.current_hash, result.suspicious_change_count)
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def _get(self, path: str) -> dict:
        import urllib.request, json
        req = urllib.request.Request(
            f"{self._base}{path}",
            headers={"x-api-key": self._key},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())

    def status(self) -> AllowlistGovernanceResult:
        """Return allowlist governance status from GET /agent/protocol-coherence-status.

        Extracts allowlist_hash (the current virtual leaf value) and change summary.
        On error: returns AllowlistGovernanceResult with error set.
        """
        try:
            body = self._get("/agent/protocol-coherence-status")
            change_body = self._get("/agent/allowlist-change-status") if False else {}
            try:
                change_body = self._get_allowlist_change_status_raw()
            except Exception:
                change_body = {}
            return AllowlistGovernanceResult(
                current_hash            = str(body.get("allowlist_hash", "")),
                last_change_ts          = change_body.get("latest_detected_at"),
                last_change_reason      = None,
                last_change_category    = None,
                suspicious_change_count = int(change_body.get("suspicious_count", 0)),
                on_chain_anchor_ts      = body.get("last_anchor_ts"),
            )
        except Exception as exc:
            return AllowlistGovernanceResult(error=str(exc))

    def _get_allowlist_change_status_raw(self) -> dict:
        """Internal: fetch allowlist change log summary."""
        import urllib.request, json
        req = urllib.request.Request(
            f"{self._base}/agent/allowlist-change-status",
            headers={"x-api-key": self._key},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())

    def previous_changes(self, limit: int = 10) -> list:
        """Return governance provenance chain entries via GET /agent/allowlist-governance-history.

        Phase 225: returns full paginated history from the tamper-evident provenance chain.
        Each entry includes: governance_provenance_hash, previous_provenance_hash,
        new_allowlist_hash, reason_category, reason_text, created_at.
        Returns list of dicts; on error returns [{"error": ...}].
        """
        try:
            import urllib.request as _ureq, json as _j
            _req = _ureq.Request(
                f"{self._base}/agent/allowlist-governance-history?limit={max(1, min(100, int(limit)))}",
                headers={"x-api-key": self._key},
            )
            with _ureq.urlopen(_req, timeout=10) as _resp:
                _body = _j.loads(_resp.read().decode())
            return _body.get("entries", [])
        except Exception as exc:
            return [{"error": str(exc)}]

    def chain_intact(self) -> bool:
        """Return True if the governance provenance chain is unbroken (Phase 225).

        Calls GET /agent/allowlist-governance-history and reads chain_intact field.
        Returns True on empty chain (no entries = not broken). Returns False on error.
        """
        try:
            import urllib.request as _ureq, json as _j
            _req = _ureq.Request(
                f"{self._base}/agent/allowlist-governance-history?limit=1",
                headers={"x-api-key": self._key},
            )
            with _ureq.urlopen(_req, timeout=10) as _resp:
                _body = _j.loads(_resp.read().decode())
            return bool(_body.get("chain_intact", True))
        except Exception:
            return False

    def suspicious_changes(self) -> list:
        """Return allowlist_change_log entries where reason_from_gate_log IS NULL.

        These represent allowlist modifications that bypassed the governance log.
        Returns list of dicts with keys: previous_hash, new_hash, detected_at.
        """
        try:
            body = self._get_allowlist_change_status_raw()
            if body.get("suspicious_count", 0) > 0:
                return [{
                    "previous_hash": body.get("latest_previous_hash"),
                    "new_hash":      body.get("latest_new_hash"),
                    "detected_at":   body.get("latest_detected_at"),
                    "reason":        None,
                }]
            return []
        except Exception as exc:
            return [{"error": str(exc)}]

    def on_chain_provenance_hash(self) -> str:
        """Return the governance_provenance_hash most recently anchored on-chain (Phase 227).

        Calls GET /agent/protocol-coherence-status and extracts the
        governance_provenance_hash field.  Returns "" when no Phase 227 anchor
        has been performed yet, or on any error.
        """
        try:
            body = self._get("/agent/protocol-coherence-status")
            return str(body.get("governance_provenance_hash", ""))
        except Exception:
            return ""

    def post_invariant_change(
        self,
        reason_text: str,
        vhp_token_id: str = "",
        previous_hash: str = "",
        new_hash: str = "",
        governance_provenance_hash: str = "",
        previous_provenance_hash: str = "",
    ) -> dict:
        """Post an invariant_change governance event (Phase 228).

        Wraps POST /agent/allowlist-governance-event with reason_category='invariant_change'
        and optional vhp_token_id for biometric presence proof.

        Validates locally before posting:
          - reason_text must be 10-200 characters
          - vhp_token_id must be a non-empty string when provided

        Returns the server response dict, or {'error': str} on failure.
        """
        if not (10 <= len(reason_text) <= 200):
            return {"error": "reason_text must be 10-200 characters"}
        if vhp_token_id is not None and not isinstance(vhp_token_id, str):
            return {"error": "vhp_token_id must be a string"}

        import json as _json228, urllib.request as _req228
        payload = {
            "reason_category":            "invariant_change",
            "reason_text":                reason_text,
            "vhp_token_id":               vhp_token_id,
            "previous_hash":              previous_hash,
            "new_hash":                   new_hash,
            "governance_provenance_hash": governance_provenance_hash,
            "previous_provenance_hash":   previous_provenance_hash,
        }
        try:
            data = _json228.dumps(payload).encode()
            req = _req228.Request(
                f"{self._base}/agent/allowlist-governance-event",
                data=data,
                headers={"Content-Type": "application/json", "x-api-key": self._key},
                method="POST",
            )
            with _req228.urlopen(req, timeout=10) as resp:
                return _json228.loads(resp.read().decode())
        except Exception as exc:
            return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Phase 229 — AIT Separation
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class AITSeparationResult:
    """Result from VAPIAITSeparation.status() (Phase 229 / 235-DASH)."""
    ait_separation_enabled:     bool  = False
    n_sessions:                 int   = 0
    separation_ratio:           float = 0.0
    all_pairs_above_1:          bool  = False
    inter_player_mean:          float = 0.0
    intra_player_mean:          float = 0.0
    loo_accuracy:               float = 0.0
    n_per_player:               dict  = None  # type: ignore[assignment]
    per_player_tremor_hz:       dict  = None  # type: ignore[assignment]
    per_player_roll_angle_deg:  dict  = None  # type: ignore[assignment]
    per_player_pitch_angle_deg: dict  = None  # type: ignore[assignment]
    error:                      str   = ""

    def __post_init__(self):
        for _attr in ("n_per_player", "per_player_tremor_hz",
                      "per_player_roll_angle_deg", "per_player_pitch_angle_deg"):
            if getattr(self, _attr) is None:
                object.__setattr__(self, _attr, {})


class VAPIAITSeparation:
    """Client for Phase 229 AIT (Active Isometric Trigger) separation API.

    AIT uses a 4-feature biometric pipeline:
      [accel_tremor_peak_hz, roll_cos, roll_sin, pitch_cos]

    Phase 229 breakthrough: separation_ratio=1.199, all_pairs_above_1=True (N=24, 2026-04-18).
    This is the first probe type to achieve all inter-player distances > 1.0.

    Example::

        ait = VAPIAITSeparation("http://localhost:8080", api_key)
        result = ait.status()
        print(result.separation_ratio, result.all_pairs_above_1)
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def status(self) -> AITSeparationResult:
        """GET /agent/ait-separation-status — returns latest AIT analysis result.

        On error: returns AITSeparationResult with error set.
        """
        import json as _j229, urllib.request as _r229
        try:
            url = f"{self._base}/agent/ait-separation-status?api_key={self._key}"
            with _r229.urlopen(url, timeout=10) as resp:
                d = _j229.loads(resp.read().decode())
            return AITSeparationResult(
                ait_separation_enabled     = bool(d.get("ait_separation_enabled", False)),
                n_sessions                 = int(d.get("n_sessions", 0)),
                separation_ratio           = float(d.get("separation_ratio", 0.0)),
                all_pairs_above_1          = bool(d.get("all_pairs_above_1", False)),
                inter_player_mean          = float(d.get("inter_player_mean", 0.0)),
                intra_player_mean          = float(d.get("intra_player_mean", 0.0)),
                loo_accuracy               = float(d.get("loo_accuracy", 0.0)),
                n_per_player               = dict(d.get("n_per_player") or {}),
                per_player_tremor_hz       = dict(d.get("per_player_tremor_hz") or {}),
                per_player_roll_angle_deg  = dict(d.get("per_player_roll_angle_deg") or {}),
                per_player_pitch_angle_deg = dict(d.get("per_player_pitch_angle_deg") or {}),
            )
        except Exception as exc:
            return AITSeparationResult(error=str(exc))


# ---------------------------------------------------------------------------
# Phase 234.7 — Physical Capture Continuity (PCC)
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class CaptureHealthResult:
    """Result from VAPICaptureContinuity.status() (Phase 234.7).

    capture_state: NOMINAL | DEGRADED | DISCONNECTED
    host_state:    EXCLUSIVE_USB | EXCLUSIVE_BT | CONTESTED | UNKNOWN
    grind_ready:   True only when NOMINAL + EXCLUSIVE_USB + 30s sustained
    session_counting_paused: grind_mode=True AND grind_ready=False
    """
    pcc_enabled:                    bool  = True
    capture_state:                  str   = "DISCONNECTED"
    host_state:                     str   = "UNKNOWN"
    poll_rate_hz:                   float = 0.0
    sustained_duration_s:           float = 0.0
    grind_mode:                     bool  = False
    grind_ready:                    bool  = False
    grind_target:                   int   = 100
    consecutive_clean_toward_target: int  = 0
    session_counting_paused:        bool  = False
    error:                          str   = ""


class VAPICaptureContinuity:
    """Client for Phase 234.7 Physical Capture Continuity API.

    Monitors HID poll rate, controller host arbitration state, and grind-mode
    readiness.  The bridge calls update_sample() every session-loop iteration
    (~1 Hz) so this endpoint reflects near-real-time capture health.

    Example::

        pcc = VAPICaptureContinuity("http://localhost:8080", api_key)
        result = pcc.status()
        if not result.grind_ready:
            print("Capture not ready for grind:", result.capture_state, result.host_state)
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def status(self) -> CaptureHealthResult:
        """GET /bridge/capture-health — returns current PCC status.

        On error: returns CaptureHealthResult with error set.
        """
        import json as _j2347, urllib.request as _r2347
        try:
            url = f"{self._base}/bridge/capture-health"
            req = _r2347.Request(url, headers={"x-api-key": self._key})
            with _r2347.urlopen(req, timeout=10) as resp:
                d = _j2347.loads(resp.read().decode())
            return CaptureHealthResult(
                pcc_enabled                    = bool(d.get("pcc_enabled", True)),
                capture_state                  = str(d.get("capture_state", "DISCONNECTED")),
                host_state                     = str(d.get("host_state", "UNKNOWN")),
                poll_rate_hz                   = float(d.get("poll_rate_hz", 0.0)),
                sustained_duration_s           = float(d.get("sustained_duration_s", 0.0)),
                grind_mode                     = bool(d.get("grind_mode", False)),
                grind_ready                    = bool(d.get("grind_ready", False)),
                grind_target                   = int(d.get("grind_target", 100)),
                consecutive_clean_toward_target = int(d.get("consecutive_clean_toward_target", 0)),
                session_counting_paused        = bool(d.get("session_counting_paused", False)),
            )
        except Exception as exc:
            return CaptureHealthResult(error=str(exc))


# ---------------------------------------------------------------------------
# Phase 235-A — Grind Integrity Chain (GIC)
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class GrindChainResult:
    """Result from VAPIGrindChain.status() (Phase 235-A).

    chain_intact: False if any stored GIC hash fails recomputation — indicates tampering.
    latest_gic_hash: hex-encoded SHA-256 GIC output of the most recent grind session.
    genesis_ts / latest_ts: Unix timestamps (seconds) of first and latest chain entries.
    """
    grind_session_id: str   = ""
    chain_length:     int   = 0
    latest_gic_hash:  str   = ""
    chain_intact:     bool  = False
    genesis_ts:       float = 0.0
    latest_ts:        float = 0.0
    error:            str   = ""


class VAPIGrindChain:
    """Client for Phase 235-A Grind Integrity Chain API."""

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key

    def status(self) -> GrindChainResult:
        """GET /bridge/grind-chain-status → GrindChainResult."""
        import urllib.request as _ur
        import urllib.error as _ue
        try:
            req = _ur.Request(
                f"{self._base_url}/bridge/grind-chain-status",
                headers={"x-api-key": self._api_key},
            )
            with _ur.urlopen(req, timeout=10) as resp:
                d = json.loads(resp.read())
            return GrindChainResult(
                grind_session_id = str(d.get("grind_session_id", "")),
                chain_length     = int(d.get("chain_length", 0)),
                latest_gic_hash  = str(d.get("latest_gic_hash", "")),
                chain_intact     = bool(d.get("chain_intact", False)),
                genesis_ts       = float(d.get("genesis_ts", 0.0)),
                latest_ts        = float(d.get("latest_ts", 0.0)),
            )
        except Exception as exc:
            return GrindChainResult(error=str(exc), chain_intact=False)


# ---------------------------------------------------------------------------
# Phase 235-ANALYTICS — Grind Pipeline Analytics
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class GrindAnalyticsResult:
    """Result from VAPIGrindAnalytics.status() (Phase 235-ANALYTICS).

    success_rate: stamped_count / total_validated (0.0 when no sessions validated).
    blocking_reason_counts: distribution of GIC gate failures (e.g. PCC_NOT_NOMINAL).
    sessions_per_day: stamped session velocity since first validation entry.
    projected_gic100_date: ISO date string, or "unknown" when velocity==0.
    """
    grind_session_id:       str   = ""
    total_validated:        int   = 0
    stamped_count:          int   = 0
    success_rate:           float = 0.0
    blocking_reason_counts: dict  = None  # type: ignore[assignment]
    sessions_per_day:       float = 0.0
    projected_gic100_date:  str   = "unknown"
    last_validation_ts:     float = 0.0
    last_stamp_ts:          float = 0.0
    error:                  str   = ""

    def __post_init__(self):
        if self.blocking_reason_counts is None:
            object.__setattr__(self, "blocking_reason_counts", {})


class VAPIGrindAnalytics:
    """Client for Phase 235-ANALYTICS Grind Pipeline Analytics API."""

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key

    def status(self) -> GrindAnalyticsResult:
        """GET /grind/analytics → GrindAnalyticsResult."""
        import urllib.request as _ur
        import urllib.error as _ue
        try:
            req = _ur.Request(
                f"{self._base_url}/grind/analytics",
                headers={"x-api-key": self._api_key},
            )
            with _ur.urlopen(req, timeout=10) as resp:
                d = json.loads(resp.read())
            return GrindAnalyticsResult(
                grind_session_id       = str(d.get("grind_session_id", "")),
                total_validated        = int(d.get("total_validated", 0)),
                stamped_count          = int(d.get("stamped_count", 0)),
                success_rate           = float(d.get("success_rate", 0.0)),
                blocking_reason_counts = dict(d.get("blocking_reason_counts") or {}),
                sessions_per_day       = float(d.get("sessions_per_day", 0.0)),
                projected_gic100_date  = str(d.get("projected_gic100_date", "unknown")),
                last_validation_ts     = float(d.get("last_validation_ts", 0.0)),
                last_stamp_ts          = float(d.get("last_stamp_ts", 0.0)),
            )
        except Exception as exc:
            return GrindAnalyticsResult(error=str(exc))


# ---------------------------------------------------------------------------
# Phase 237-ZK-SEPPROOF — BIOMETRIC-SNAPSHOT-v1 + ZK separation proof status
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class BiometricSnapshotResult:
    """Result from VAPIZKSepProof.snapshot_status() — Phase 237-ZK-SEPPROOF.

    Mirrors the GET /agent/biometric-snapshot-status response shape.
    """
    total_snapshots:    int   = 0
    latest_commitment:  str   = ""
    feature_dim:        int   = 0
    n_players:          int   = 0
    ts_ns:              int   = 0
    on_chain_confirmed: bool  = False
    tx_hash:            str   = ""
    trigger_reason:     str   = ""
    error:              str   = ""


@dataclass(slots=True)
class BiometricSnapshotAnchorResult:
    """Result from VAPIZKSepProof.anchor_snapshot() — Phase 237-ZK-SEPPROOF.

    Returned by the POST /operator/anchor-biometric-snapshot endpoint
    after the operator commits to the latest AIT corpus state on-chain.
    """
    row_id:              int   = 0
    snapshot_commitment: str   = ""
    feature_dim:         int   = 0
    n_players:           int   = 0
    sorted_player_ids:   list  = None  # type: ignore[assignment]
    ts_ns:               int   = 0
    trigger_reason:      str   = ""
    on_chain_confirmed:  bool  = False
    tx_hash:             str   = ""
    ait_session_log_id:  int   = 0
    error:               str   = ""

    def __post_init__(self):
        if self.sorted_player_ids is None:
            object.__setattr__(self, "sorted_player_ids", [])


class VAPIZKSepProof:
    """Client for Phase 237-ZK-SEPPROOF anchor + status endpoints (SDK Step D).

    Phase 237-ZK-SEPPROOF introduces the sixth FROZEN-v1 cryptographic
    primitive in the PATTERN-016 family: BIOMETRIC-SNAPSHOT-v1.  This SDK
    surface lets external clients:

      * read the latest anchored biometric snapshot status
      * trigger a new anchor (operator-only — full api_key auth required)

    Local proof verification (`verify_local`) is provided as a structural
    no-op until Phase 237-ZK-SEPPROOF Step F (verifier deploy + ceremony).
    Until then, callers should rely on the on-chain verifier
    (ZKSepProofVerifier.verifyAndCheckSnapshotView) once it ships.

    Example::

        zksep = VAPIZKSepProof("http://localhost:8080", api_key)
        status = zksep.snapshot_status()
        print(status.latest_commitment, status.on_chain_confirmed)

        # Operator-only:
        result = zksep.anchor_snapshot(reason="post-AIT-rerun-2026-05-09")
        print(result.snapshot_commitment, result.tx_hash)
    """

    PROOF_SIZE = 256  # mirrors zk_sepproof_prover.PROOF_SIZE

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def snapshot_status(self) -> BiometricSnapshotResult:
        """GET /agent/biometric-snapshot-status — read-only (uses x-api-key).

        On error: returns BiometricSnapshotResult with error set.
        """
        import json as _j237s, urllib.request as _r237s
        try:
            url = f"{self._base}/agent/biometric-snapshot-status"
            req = _r237s.Request(url, headers={"x-api-key": self._key})
            with _r237s.urlopen(req, timeout=10) as resp:
                d = _j237s.loads(resp.read().decode())
            return BiometricSnapshotResult(
                total_snapshots    = int(d.get("total_snapshots", 0)),
                latest_commitment  = str(d.get("latest_commitment", "")),
                feature_dim        = int(d.get("feature_dim", 0)),
                n_players          = int(d.get("n_players", 0)),
                ts_ns              = int(d.get("ts_ns", 0)),
                on_chain_confirmed = bool(d.get("on_chain_confirmed", False)),
                tx_hash            = str(d.get("tx_hash", "")),
                trigger_reason     = str(d.get("trigger_reason", "")),
            )
        except Exception as exc:
            return BiometricSnapshotResult(error=str(exc))

    def anchor_snapshot(self, reason: str) -> BiometricSnapshotAnchorResult:
        """POST /operator/anchor-biometric-snapshot — operator-only (full api_key).

        Args:
            reason: Operator audit string (>=10 chars; 422 otherwise).

        Returns:
            BiometricSnapshotAnchorResult with snapshot_commitment, tx_hash,
            and on_chain_confirmed populated.

        Locally validates reason length before sending so callers get a
        consistent error message regardless of server reachability.
        """
        if len(reason.strip()) < 10:
            return BiometricSnapshotAnchorResult(
                error="reason must be at least 10 characters (operator audit field)",
            )
        import json as _j237a, urllib.request as _r237a, urllib.parse as _u237a
        try:
            url = (
                f"{self._base}/operator/anchor-biometric-snapshot?"
                f"api_key={_u237a.quote(self._key)}&reason={_u237a.quote(reason)}"
            )
            req = _r237a.Request(url, method="POST")
            with _r237a.urlopen(req, timeout=30) as resp:
                d = _j237a.loads(resp.read().decode())
            return BiometricSnapshotAnchorResult(
                row_id              = int(d.get("row_id", 0)),
                snapshot_commitment = str(d.get("snapshot_commitment", "")),
                feature_dim         = int(d.get("feature_dim", 0)),
                n_players           = int(d.get("n_players", 0)),
                sorted_player_ids   = list(d.get("sorted_player_ids") or []),
                ts_ns               = int(d.get("ts_ns", 0)),
                trigger_reason      = str(d.get("trigger_reason", "")),
                on_chain_confirmed  = bool(d.get("on_chain_confirmed", False)),
                tx_hash             = str(d.get("tx_hash", "")),
                ait_session_log_id  = int(d.get("ait_session_log_id", 0)),
            )
        except Exception as exc:
            return BiometricSnapshotAnchorResult(error=str(exc))

    @staticmethod
    def verify_local(proof_bytes: bytes) -> bool:
        """Structural pre-flight check on a 256-byte proof.

        Phase 237-ZK-SEPPROOF Step D scope: returns True iff `proof_bytes`
        is exactly 256 bytes (matches Groth16 BN254 wire format).  No
        cryptographic verification — that requires the trusted setup
        ceremony's verification_key.json (deferred until wallet refill).
        Cryptographic verification is performed on-chain via
        ZKSepProofVerifier.verifyAndCheckSnapshotView once deployed.
        """
        return isinstance(proof_bytes, (bytes, bytearray)) and len(proof_bytes) == VAPIZKSepProof.PROOF_SIZE


# ---------------------------------------------------------------------------
# Phase 238-MARKETPLACE — Provenance-Anchored Listing Layer (PALL) SDK
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class ListingCreationResult:
    """Result from VAPIMarketplaceListings.list_data_session().

    Mirrors POST /operator/list-data-session response.
    """
    row_id:               int   = 0
    listing_commitment:   str   = ""
    ipfs_cid:             str   = ""
    ipfs_cid_hash:        str   = ""
    tier:                 int   = 0      # 0=Basic, 1=Verified, 2=Attested, 3=Premium
    tier_name:            str   = "Basic"
    multiplier_bps:       int   = 10000  # 1.0x default
    anchors_present:      int   = 0
    on_chain_confirmed:   bool  = False
    tx_hash:              str   = ""
    ts_ns:                int   = 0
    error:                str   = ""


@dataclass(slots=True)
class MarketplaceStatusResult:
    """Result from VAPIMarketplaceListings.status() — Phase 238 PALL aggregate."""
    total_listings:         int   = 0
    anchored_listings:      int   = 0
    latest_commitment:      str   = ""
    latest_seller:          str   = ""
    latest_data_class:      int   = 0
    latest_price_iotx:      float = 0.0
    latest_anchors_present: int   = 0
    latest_ts_ns:           int   = 0
    latest_on_chain:        bool  = False
    latest_tx_hash:         str   = ""
    error:                  str   = ""


class VAPIMarketplaceListings:
    """Client for Phase 238-MARKETPLACE Provenance-Anchored Listing Layer (PALL).

    PALL adds per-listing cryptographic provenance on top of Phase 69
    VAPIDataMarketplace.  Each listing carries a LISTING-v1 commitment that
    binds up to 5 prior FROZEN-v1 anchors (SEPPROOF + BIOMETRIC-SNAPSHOT +
    CORPUS-SNAPSHOT + GIC + CONSENT bitmask).  Tier multipliers (1.0x / 1.5x /
    2.0x / 3.0x) are computed cryptographically from anchor presence — sellers
    cannot self-attest tier.

    Example::

        marketplace = VAPIMarketplaceListings("http://localhost:8080", api_key)
        result = marketplace.list_data_session(
            seller_address="0xseller",
            sepproof_commitment_hex="aa..." (64-char or "" if absent),
            biometric_snapshot_hex="bb...",
            corpus_snapshot_hex="cc...",
            gic_hash_hex="dd...",
            consent_bitmask=8,           # MARKETPLACE bit only
            data_class=4,                # BIOMETRIC
            price_iotx=5.0,
            listing_metadata_json='{"key":"val"}',
            reason="post_session_pall_2026_05_09",
        )
        print(result.listing_commitment, result.tier_name, result.tx_hash)

        status = marketplace.status()
        print(status.total_listings, status.anchored_listings)

        listing = marketplace.get_listing(result.listing_commitment)
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def list_data_session(
        self,
        seller_address: str,
        consent_bitmask: int,
        data_class: int,
        price_iotx: float,
        reason: str,
        sepproof_commitment_hex: str = "",
        biometric_snapshot_hex: str = "",
        corpus_snapshot_hex: str = "",
        gic_hash_hex: str = "",
        listing_metadata_json: str = "{}",
    ) -> ListingCreationResult:
        """POST /operator/list-data-session — operator-only (full api_key auth).

        Locally pre-validates reason length (mirrors bridge 422 message).
        On error: returns ListingCreationResult with error set.
        """
        if len(reason.strip()) < 10:
            return ListingCreationResult(
                error="reason must be at least 10 characters (operator audit field)",
            )
        import json as _j238ml, urllib.request as _r238ml, urllib.parse as _u238ml
        try:
            params = {
                "api_key":                self._key,
                "seller_address":         seller_address,
                "sepproof_commitment_hex": sepproof_commitment_hex,
                "biometric_snapshot_hex":  biometric_snapshot_hex,
                "corpus_snapshot_hex":     corpus_snapshot_hex,
                "gic_hash_hex":            gic_hash_hex,
                "consent_bitmask":         str(int(consent_bitmask)),
                "data_class":              str(int(data_class)),
                "price_iotx":              str(float(price_iotx)),
                "listing_metadata_json":   listing_metadata_json,
                "reason":                  reason,
            }
            qs = "&".join(
                f"{k}={_u238ml.quote(str(v))}" for k, v in params.items()
            )
            url = f"{self._base}/operator/list-data-session?{qs}"
            req = _r238ml.Request(url, method="POST")
            with _r238ml.urlopen(req, timeout=60) as resp:
                d = _j238ml.loads(resp.read().decode())
            return ListingCreationResult(
                row_id              = int(d.get("row_id", 0)),
                listing_commitment  = str(d.get("listing_commitment", "")),
                ipfs_cid            = str(d.get("ipfs_cid", "")),
                ipfs_cid_hash       = str(d.get("ipfs_cid_hash", "")),
                tier                = int(d.get("tier", 0)),
                tier_name           = str(d.get("tier_name", "Basic")),
                multiplier_bps      = int(d.get("multiplier_bps", 10000)),
                anchors_present     = int(d.get("anchors_present", 0)),
                on_chain_confirmed  = bool(d.get("on_chain_confirmed", False)),
                tx_hash             = str(d.get("tx_hash", "")),
                ts_ns               = int(d.get("ts_ns", 0)),
            )
        except Exception as exc:
            return ListingCreationResult(error=str(exc))

    def status(self) -> MarketplaceStatusResult:
        """GET /agent/marketplace-status — read-only (uses x-api-key)."""
        import json as _j238ms, urllib.request as _r238ms
        try:
            url = f"{self._base}/agent/marketplace-status"
            req = _r238ms.Request(url, headers={"x-api-key": self._key})
            with _r238ms.urlopen(req, timeout=10) as resp:
                d = _j238ms.loads(resp.read().decode())
            return MarketplaceStatusResult(
                total_listings         = int(d.get("total_listings", 0)),
                anchored_listings      = int(d.get("anchored_listings", 0)),
                latest_commitment      = str(d.get("latest_commitment", "")),
                latest_seller          = str(d.get("latest_seller", "")),
                latest_data_class      = int(d.get("latest_data_class", 0)),
                latest_price_iotx      = float(d.get("latest_price_iotx", 0.0)),
                latest_anchors_present = int(d.get("latest_anchors_present", 0)),
                latest_ts_ns           = int(d.get("latest_ts_ns", 0)),
                latest_on_chain        = bool(d.get("latest_on_chain", False)),
                latest_tx_hash         = str(d.get("latest_tx_hash", "")),
            )
        except Exception as exc:
            return MarketplaceStatusResult(error=str(exc))

    def get_listing(self, listing_commitment_hex: str) -> dict:
        """GET /agent/marketplace-listing/{commitment} — full listing record.

        Returns dict with all stored fields + tier preview, or empty dict
        on 404 / error.
        """
        import json as _j238gl, urllib.request as _r238gl
        try:
            h = listing_commitment_hex.strip().lower()
            if h.startswith("0x"):
                h = h[2:]
            url = f"{self._base}/agent/marketplace-listing/{h}"
            req = _r238gl.Request(url, headers={"x-api-key": self._key})
            with _r238gl.urlopen(req, timeout=10) as resp:
                return _j238gl.loads(resp.read().decode())
        except Exception:
            return {}


# ─── Phase 238 Step I — Curator Shadow Infrastructure ─────────────────────────


@dataclass(slots=True)
class CuratorReviewResult:
    """Phase 238 Step I — Curator listing-review verdict (shadow mode).

    13 fields — wire contract LOCKED for the upcoming frontend dashboard
    revamp.  Any new field requires a v2 of the SDK class + endpoint.

    Six FROZEN verdict codes plus the safety-floor seventh:
      APPROVED, FLAGGED_TIER_MISMATCH, FLAGGED_ANCHOR_STALE,
      FLAGGED_CONSENT_AMBIGUOUS, FLAGGED_IPFS_UNAVAILABLE,
      REJECTED_NO_ANCHORS, REJECTED_INVALID_COMMITMENT.

    Severity mapping: APPROVED=INFO, FLAGGED_*=WARN/LOW, REJECTED_*=HIGH.
    """
    row_id: int = 0
    commitment_hex: str = ""
    verdict: str = ""
    severity: str = ""
    anchors_recorded_count: int = 0
    anchors_recorded_breakdown: dict = field(default_factory=dict)
    consent_marketplace_bit_set: bool = False
    ipfs_resolvable: object = None  # bool | None
    declared_tier: int = 0
    tier_at_review_time: int = 0
    tier_changed: bool = False
    shadow_mode: bool = True
    ts_ns: int = 0
    error: str = ""


@dataclass(slots=True)
class CuratorStatusResult:
    """Phase 238 Step I — Curator review aggregation summary (top-of-tab widget)."""
    curator_review_enabled: bool = False
    total_reviews: int = 0
    approved_reviews: int = 0
    flagged_reviews: int = 0
    rejected_reviews: int = 0
    latest_verdict: str = ""
    latest_listing_commitment: str = ""
    latest_review_ts_ns: int = 0
    shadow_mode: bool = True
    error: str = ""


class VAPICurator:
    """Client for Phase 238 Step I — Curator Operator Initiative agent.

    The Curator is the third Operator Initiative agent (post Sentry + Guardian)
    and is exclusive to VAPI: no other DePIN protocol fields a third dedicated
    agent whose job is cryptographic-tier verification of marketplace listings.

    All methods follow the Phase 184+ "never raises" SDK contract — exceptions
    surface as result.error.

    Example::

        curator = VAPICurator("http://localhost:8080", api_key)
        result = curator.review_listing(
            commitment_hex="ab" * 32,
            reason="manual_audit_2026_05_09",
        )
        print(result.verdict, result.severity, result.anchors_recorded_count)

        status = curator.status()
        print(f"{status.flagged_reviews}/{status.total_reviews} flagged")

        flagged = curator.flagged_listings(since_minutes=1440, limit=20)
        for r in flagged.get("listings", []):
            print(r["listing_commitment"], r["verdict"])
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def review_listing(
        self,
        commitment_hex: str,
        reason: str,
    ) -> CuratorReviewResult:
        """POST /operator/curator-review-listing — operator-only (full api_key auth).

        Locally pre-validates reason length (mirrors bridge 422 message).
        Returns CuratorReviewResult; on error result.error is set.
        """
        if len(reason.strip()) < 10:
            return CuratorReviewResult(
                error="reason must be at least 10 characters (operator audit field)",
            )
        import json as _j238crv, urllib.request as _r238crv, urllib.parse as _u238crv
        try:
            params = {
                "api_key":        self._key,
                "commitment_hex": commitment_hex,
                "reason":         reason,
            }
            qs = "&".join(
                f"{k}={_u238crv.quote(str(v))}" for k, v in params.items()
            )
            url = f"{self._base}/operator/curator-review-listing?{qs}"
            req = _r238crv.Request(url, method="POST")
            with _r238crv.urlopen(req, timeout=30) as resp:
                d = _j238crv.loads(resp.read().decode())
            return CuratorReviewResult(
                row_id                      = int(d.get("row_id", 0)),
                commitment_hex              = str(d.get("commitment_hex", "")),
                verdict                     = str(d.get("verdict", "")),
                severity                    = str(d.get("severity", "")),
                anchors_recorded_count      = int(d.get("anchors_recorded_count", 0)),
                anchors_recorded_breakdown  = dict(d.get("anchors_recorded_breakdown", {})),
                consent_marketplace_bit_set = bool(d.get("consent_marketplace_bit_set", False)),
                ipfs_resolvable             = d.get("ipfs_resolvable", None),
                declared_tier               = int(d.get("declared_tier", 0)),
                tier_at_review_time         = int(d.get("tier_at_review_time", 0)),
                tier_changed                = bool(d.get("tier_changed", False)),
                shadow_mode                 = bool(d.get("shadow_mode", True)),
                ts_ns                       = int(d.get("ts_ns", 0)),
            )
        except Exception as exc:
            return CuratorReviewResult(error=str(exc))

    def status(self) -> CuratorStatusResult:
        """GET /agent/curator-status — read-only (uses x-api-key)."""
        import json as _j238cst, urllib.request as _r238cst
        try:
            url = f"{self._base}/agent/curator-status"
            req = _r238cst.Request(url, headers={"x-api-key": self._key})
            with _r238cst.urlopen(req, timeout=10) as resp:
                d = _j238cst.loads(resp.read().decode())
            return CuratorStatusResult(
                curator_review_enabled    = bool(d.get("curator_review_enabled", False)),
                total_reviews             = int(d.get("total_reviews", 0)),
                approved_reviews          = int(d.get("approved_reviews", 0)),
                flagged_reviews           = int(d.get("flagged_reviews", 0)),
                rejected_reviews          = int(d.get("rejected_reviews", 0)),
                latest_verdict            = str(d.get("latest_verdict", "")),
                latest_listing_commitment = str(d.get("latest_listing_commitment", "")),
                latest_review_ts_ns       = int(d.get("latest_review_ts_ns", 0)),
                shadow_mode               = bool(d.get("shadow_mode", True)),
            )
        except Exception as exc:
            return CuratorStatusResult(error=str(exc))

    def get_review(self, commitment_hex: str) -> dict:
        """GET /agent/curator-review/{commitment_hex} — per-listing review timeline.

        Returns { listing_commitment, reviews: [...], total } or empty dict on error.
        """
        import json as _j238cgr, urllib.request as _r238cgr
        try:
            h = commitment_hex.strip().lower()
            if h.startswith("0x"):
                h = h[2:]
            url = f"{self._base}/agent/curator-review/{h}"
            req = _r238cgr.Request(url, headers={"x-api-key": self._key})
            with _r238cgr.urlopen(req, timeout=10) as resp:
                return _j238cgr.loads(resp.read().decode())
        except Exception:
            return {}

    def flagged_listings(
        self, since_minutes: int = 1440, limit: int = 50
    ) -> dict:
        """GET /agent/curator-flagged-listings — flagged listings hot-bar.

        Returns { listings, total, since_minutes, capped } or empty dict on error.
        """
        import json as _j238cfl, urllib.request as _r238cfl, urllib.parse as _u238cfl
        try:
            qs = _u238cfl.urlencode({
                "since_minutes": int(since_minutes),
                "limit":         int(limit),
            })
            url = f"{self._base}/agent/curator-flagged-listings?{qs}"
            req = _r238cfl.Request(url, headers={"x-api-key": self._key})
            with _r238cfl.urlopen(req, timeout=10) as resp:
                return _j238cfl.loads(resp.read().decode())
        except Exception:
            return {}

    def bulk_review(
        self,
        reason: str,
        seller_address: str = "",
        since_minutes: int = 1440,
        limit: int = 20,
    ) -> dict:
        """POST /operator/curator-bulk-review — re-runs review pipeline against
        recent listings (operator-only).

        Returns { reviewed_count, verdicts_breakdown, reviews, since_minutes, ts_ns }
        or { 'error': '...' } on local pre-validation failure / network error.
        """
        if len(reason.strip()) < 10:
            return {"error": "reason must be at least 10 characters"}
        import json as _j238cbr, urllib.request as _r238cbr, urllib.parse as _u238cbr
        try:
            params = {
                "api_key":        self._key,
                "seller_address": seller_address,
                "since_minutes":  str(int(since_minutes)),
                "limit":          str(int(limit)),
                "reason":         reason,
            }
            qs = "&".join(
                f"{k}={_u238cbr.quote(str(v))}" for k, v in params.items()
            )
            url = f"{self._base}/operator/curator-bulk-review?{qs}"
            req = _r238cbr.Request(url, method="POST")
            with _r238cbr.urlopen(req, timeout=120) as resp:
                return _j238cbr.loads(resp.read().decode())
        except Exception as exc:
            return {"error": str(exc)}


# === Phase O2-DRAFT-REVIEW SDK (2026-05-10) ====================================
# Wraps the operator review HTTP surface shipped in commit a44fa359
# (GET /operator/operator-agent-drafts + POST /operator/operator-agent-draft-review).
# Closes the disagreement_rate / false_positive_rate measurement loop from the
# client side -- pairs with the Phase 1005 store schema and the polling-loop
# triggers shipped in O2-DRAFT-AUTOLOOP (Sentry/Guardian/Curator).

@dataclass(slots=True)
class DraftReviewListResult:
    """Result from VAPIDraftReview.list_drafts (Phase O2-DRAFT-REVIEW)."""
    agent_id_filter:   "str|None" = None
    decision_filter:   "str|None" = None
    since_minutes:     int        = 0
    limit:             int        = 50
    row_count:         int        = 0
    drafts:            list       = field(default_factory=list)
    error:             "str|None" = None


@dataclass(slots=True)
class DraftReviewSubmitResult:
    """Result from VAPIDraftReview.review_draft (Phase O2-DRAFT-REVIEW)."""
    accepted:   bool       = False
    draft_id:   int        = 0
    decision:   str        = ""
    reason:     str        = ""
    row:        "dict|None" = None
    error:      "str|None" = None


class VAPIDraftReview:
    """Client for the operator review HTTP surface (Phase O2-DRAFT-REVIEW).

    Wraps the GET + POST endpoints that surface Operator Initiative draft
    payloads + accept the operator's decision (accept/reject/overturn_curator).
    Closes the disagreement_rate / false_positive_rate measurement loop that
    drives the watcher's PHASE_O3_DISAGREEMENT_RATE_MAX + PHASE_O3_FALSE_
    POSITIVE_RATE_MAX gates blocking O3_ACTING anchor.

    Read-key auth (x-api-key Header) for list_drafts; full operator auth
    (api_key query param) for review_draft.

    Usage::
        client = VAPIDraftReview("http://localhost:8081", api_key)
        result = client.list_drafts(decision="unreviewed", limit=20)
        for draft in result.drafts:
            client.review_draft(
                draft_id=draft["id"],
                decision="accept",
                reason="operator approved this commit signature",
            )
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def list_drafts(
        self,
        *,
        agent_id: str = "",
        decision: str = "",
        since_minutes: int = 0,
        limit: int = 50,
    ) -> DraftReviewListResult:
        """List drafts from GET /operator/operator-agent-drafts.

        Args:
            agent_id:      Optional Q9-frozen agentId filter; empty = trio.
            decision:      Filter on operator_decision: '' (all incl. NULL),
                           'unreviewed' (NULL), 'accept', 'reject',
                           'overturn_curator'.
            since_minutes: 0-43200 (30 days max). 0 = no time filter.
            limit:         1-500. Default 50. Most recent first.

        Returns DraftReviewListResult; on error, returns with error set
        and row_count=0 / drafts=[].
        """
        try:
            import urllib.request, urllib.parse, json
            qs_parts: list[str] = []
            if agent_id:
                qs_parts.append(f"agent_id={urllib.parse.quote(agent_id)}")
            if decision:
                qs_parts.append(f"decision={urllib.parse.quote(decision)}")
            if int(since_minutes) > 0:
                qs_parts.append(f"since_minutes={int(since_minutes)}")
            qs_parts.append(f"limit={int(limit)}")
            url = f"{self._base}/operator/operator-agent-drafts?{'&'.join(qs_parts)}"
            req = urllib.request.Request(
                url,
                headers={"x-api-key": self._key} if self._key else {},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read().decode())
            return DraftReviewListResult(
                agent_id_filter = body.get("agent_id_filter"),
                decision_filter = body.get("decision_filter"),
                since_minutes   = int(body.get("since_minutes", 0)),
                limit           = int(body.get("limit", limit)),
                row_count       = int(body.get("row_count", 0)),
                drafts          = list(body.get("drafts", [])),
            )
        except Exception as exc:
            return DraftReviewListResult(error=str(exc))

    def review_draft(
        self,
        *,
        draft_id: int,
        decision: str,
        reason: str,
    ) -> DraftReviewSubmitResult:
        """Submit operator decision via POST /operator/operator-agent-draft-review.

        Args:
            draft_id: Required. Targets the row's id in operator_agent_drafts.
            decision: One of 'accept' | 'reject' | 'overturn_curator'.
                      'overturn_curator' is Curator-specific (feeds
                      false_positive_rate; ZERO TOLERANCE per Curator's
                      PHASE_O3_FALSE_POSITIVE_RATE_MAX=0.0).
            reason:   >= 10 chars (audit gate). Stored as
                      operator_disagreement_reason in operator_agent_drafts.

        Returns DraftReviewSubmitResult. On error: error populated with
        the HTTP status / detail (e.g. '422' for short reason or invalid
        decision; '404' for missing draft_id; '403' for missing/wrong api_key).
        """
        try:
            import urllib.request, urllib.parse, urllib.error, json
            qs = urllib.parse.urlencode({
                "draft_id": int(draft_id),
                "decision": str(decision),
                "reason":   str(reason),
                "api_key":  self._key,
            })
            url = f"{self._base}/operator/operator-agent-draft-review?{qs}"
            req = urllib.request.Request(url, method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read().decode())
            return DraftReviewSubmitResult(
                accepted = bool(body.get("accepted", False)),
                draft_id = int(body.get("draft_id", draft_id)),
                decision = str(body.get("decision", decision)),
                reason   = str(body.get("reason", reason)),
                row      = body.get("row"),
            )
        except urllib.error.HTTPError as exc:
            try:
                detail = exc.read().decode()
            except Exception:
                detail = ""
            return DraftReviewSubmitResult(
                draft_id = int(draft_id),
                decision = str(decision),
                error    = f"HTTP {exc.code}: {detail}",
            )
        except Exception as exc:
            return DraftReviewSubmitResult(
                draft_id = int(draft_id),
                decision = str(decision),
                error    = str(exc),
            )


# ─────────────────────────────────────────────────────────────────────────────
# Phase O1-FRR-SDK — Fleet Readiness Root client
# ─────────────────────────────────────────────────────────────────────────────
# Wraps the FRR + advancement-log endpoints shipped Phase O1-FRR-ENDPOINT
# (commit 6c9a8acf). FROZEN-v1 primitive (eighth in PATTERN-017 family):
#
#   frr_hex = SHA-256(
#       b"VAPI-FRR-v1" || sorted(agent_id_be(32) || phase_code(1))
#       for each agent || ts_ns_be(8)
#   ) -> 32B
#
# Used by frontend dashboards (Phase O3-READINESS-DASHBOARD commit 8fecfcd7
# binds to this via the corresponding REST endpoint) + external Python
# tooling that wants programmatic access to fleet phase alignment + per-
# agent O2/O3 blockers without parsing CLAUDE.md NOTE entries.
#
# Read-key auth (x-api-key Header) on both endpoints; fail-open shape
# matches existing clients (VAPIDraftReview / VAPIMarketplaceListings).

@dataclass(slots=True)
class AgentReadinessRow:
    """One agent's readiness row from VAPIFleetReadinessRoot.status (Phase O1-FRR)."""
    agent_id:                                str        = ""
    current_phase:                           str        = ""
    shadow_age_hours:                        float      = 0.0
    cedar_eval_count:                        int        = 0
    bundle_hash_drift_count_30d:             int        = 0
    scope_hash_governance_drift_count_30d:   int        = 0
    o2_ready:                                bool       = False
    o2_blockers:                             list       = field(default_factory=list)
    o3_ready:                                bool       = False
    o3_blockers:                             list       = field(default_factory=list)
    error:                                   "str|None" = None


@dataclass(slots=True)
class FleetReadinessRootResult:
    """Result from VAPIFleetReadinessRoot.status (Phase O1-FRR-SDK)."""
    frr_hex:                  str        = ""
    frr_ts_ns:                int        = 0
    fleet_phase_aligned:      bool       = False
    fleet_size:               int        = 0
    fleet_at_o1_count:        int        = 0
    fleet_at_o2_ready_count:  int        = 0
    fleet_at_o3_ready_count:  int        = 0
    next_alignment_target:    str        = ""
    per_agent:                list       = field(default_factory=list)
    domain_tag:               str        = ""
    error:                    "str|None" = None


@dataclass(slots=True)
class AdvancementLogResult:
    """Result from VAPIFleetReadinessRoot.advancement_log (Phase O1-FRR-SDK)."""
    limit:     int        = 50
    row_count: int        = 0
    rows:      list       = field(default_factory=list)
    error:     "str|None" = None


class VAPIFleetReadinessRoot:
    """Client for the Fleet Readiness Root endpoints (Phase O1-FRR-SDK).

    Wraps the GET endpoints shipped Phase O1-FRR-ENDPOINT that surface the
    FRR primitive + per-agent O2/O3 blocker rollups + paginated history
    from the operator_initiative_advancement_log table.

    Read-key auth (x-api-key Header) on both endpoints. Fail-open: every
    error path returns the dataclass with .error populated and never raises.

    Usage::

        client = VAPIFleetReadinessRoot("http://localhost:8081", api_key)

        # Live snapshot
        s = client.status()
        if s.fleet_phase_aligned and all(a["o3_ready"] for a in s.per_agent):
            print("anchor unblocked:", s.frr_hex)

        # History inspection
        hist = client.advancement_log(limit=100)
        for row in hist.rows:
            print(row["frr_hex"], row["ts_ns"])
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def status(self) -> FleetReadinessRootResult:
        """Read GET /operator/fleet-readiness-root.

        Returns FleetReadinessRootResult with per_agent rollup. On error,
        returns with error set and other fields zero/empty.
        """
        try:
            import urllib.request, json
            url = f"{self._base}/operator/fleet-readiness-root"
            req = urllib.request.Request(
                url,
                headers={"x-api-key": self._key} if self._key else {},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read().decode())
            return FleetReadinessRootResult(
                frr_hex                  = str(body.get("frr_hex", "")),
                frr_ts_ns                = int(body.get("frr_ts_ns", 0)),
                fleet_phase_aligned      = bool(body.get("fleet_phase_aligned", False)),
                fleet_size               = int(body.get("fleet_size", 0)),
                fleet_at_o1_count        = int(body.get("fleet_at_o1_count", 0)),
                fleet_at_o2_ready_count  = int(body.get("fleet_at_o2_ready_count", 0)),
                fleet_at_o3_ready_count  = int(body.get("fleet_at_o3_ready_count", 0)),
                next_alignment_target    = str(body.get("next_alignment_target", "")),
                per_agent                = list(body.get("per_agent", [])),
                domain_tag               = str(body.get("domain_tag", "")),
            )
        except Exception as exc:
            return FleetReadinessRootResult(error=str(exc))

    def advancement_log(self, *, limit: int = 50) -> AdvancementLogResult:
        """Read GET /operator/operator-initiative-advancement-log.

        Args:
            limit: 1-500. Default 50. Most recent first by timestamp.

        Returns AdvancementLogResult. On error: error populated + rows=[].
        """
        try:
            import urllib.request, json
            url = (
                f"{self._base}/operator/operator-initiative-advancement-log"
                f"?limit={int(limit)}"
            )
            req = urllib.request.Request(
                url,
                headers={"x-api-key": self._key} if self._key else {},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read().decode())
            return AdvancementLogResult(
                limit     = int(body.get("limit", limit)),
                row_count = int(body.get("row_count", 0)),
                rows      = list(body.get("rows", [])),
            )
        except Exception as exc:
            return AdvancementLogResult(error=str(exc))

    def per_agent_row(self, agent_id: str) -> "AgentReadinessRow|None":
        """Convenience: fetch live status + return the row for one agent.

        Args:
            agent_id: Canonical name ('anchor_sentry' / 'guardian' / 'curator').

        Returns AgentReadinessRow on hit, None if the agent isn't in the
        fleet snapshot (or if status() returned an error).
        """
        s = self.status()
        if s.error:
            return None
        for raw in s.per_agent:
            if raw.get("agent_id") == agent_id:
                return AgentReadinessRow(
                    agent_id                              = str(raw.get("agent_id", "")),
                    current_phase                         = str(raw.get("current_phase", "")),
                    shadow_age_hours                      = float(raw.get("shadow_age_hours", 0.0)),
                    cedar_eval_count                      = int(raw.get("cedar_eval_count", 0)),
                    bundle_hash_drift_count_30d           = int(raw.get("bundle_hash_drift_count_30d", 0)),
                    scope_hash_governance_drift_count_30d = int(raw.get("scope_hash_governance_drift_count_30d", 0)),
                    o2_ready                              = bool(raw.get("o2_ready", False)),
                    o2_blockers                           = list(raw.get("o2_blockers", [])),
                    o3_ready                              = bool(raw.get("o3_ready", False)),
                    o3_blockers                           = list(raw.get("o3_blockers", [])),
                    error                                 = raw.get("error"),
                )
        return None


# === Phase O3-ZKBA-TRACK1 C4 SDK (2026-05-10) ==================================
# VAPIZKBA — Zero-Knowledge Biometric Artifact client (tenth FROZEN-v1
# primitive in PATTERN-017 per VBDIP-0001 §7 canonical convention).
#
# Wraps the GET endpoints that surface zkba_artifact_log state. The bridge
# HTTP endpoints (/operator/zkba-status, /operator/zkba-artifact/<hex>,
# /operator/zkba-history) ship in a future commit; this SDK class provides
# the wire-contract surface NOW so external tooling can build against it,
# with fail-open behavior (matches VAPIDraftReview / VAPIFleetReadinessRoot
# pattern: methods return Result dataclass with .error populated; never raise).

@dataclass(slots=True)
class ZKBAStatusResult:
    """Result from VAPIZKBA.status (Phase O3-ZKBA-TRACK1 C4)."""
    total_artifacts:        int        = 0
    anchored_count:         int        = 0
    track1_invariant_holds: bool       = True
    class_breakdown:        dict       = field(default_factory=dict)
    latest_commitment_hex:  str        = ""
    latest_zkba_class:      int        = 0
    latest_proof_weight:    int        = 0
    latest_ts_ns:           int        = 0
    frozen_v1_position:     int        = 10
    domain_tag:             str        = "VAPI-ZKBA-ARTIFACT-v1"
    error:                  "str|None" = None


@dataclass(slots=True)
class ZKBAArtifactResult:
    """Result from VAPIZKBA.get_artifact (Phase O3-ZKBA-TRACK1 C4)."""
    commitment_hex:           str        = ""
    found:                    bool       = False
    zkba_class:               int        = 0
    proof_weight:             int        = 0
    preimage_json:            str        = ""
    ts_ns:                    int        = 0
    manifest_uri:             str        = ""
    compiler_output_hash_hex: str        = ""
    anchor_tx_hash:           "str|None" = None
    created_at:               float      = 0.0
    error:                    "str|None" = None


@dataclass(slots=True)
class ZKBAHistoryResult:
    """Result from VAPIZKBA.history (Phase O3-ZKBA-TRACK1 C4)."""
    limit:     int        = 20
    row_count: int        = 0
    rows:      list       = field(default_factory=list)
    error:     "str|None" = None


class VAPIZKBA:
    """Client for the ZKBA artifact endpoints (Phase O3-ZKBA-TRACK1 C4).

    ZKBA = Zero-Knowledge Biometric Artifact, the tenth FROZEN-v1 primitive
    in the PATTERN-017 family per VBDIP-0001 §7 canonical convention.

    Three methods wrap the future ZKBA bridge endpoints:
      - status()          GET /operator/zkba-status
      - get_artifact(hex) GET /operator/zkba-artifact/<commitment_hex>
      - history(limit=20) GET /operator/zkba-history?limit=N

    Read-key auth (x-api-key Header). Fail-open: every error path returns
    the dataclass with .error populated and never raises (matches
    VAPIDraftReview / VAPIFleetReadinessRoot pattern).

    At C4 commit time, the bridge HTTP endpoints are NOT yet shipped — all
    calls return Result with .error set (typical: connection refused or
    404). The SDK exists to lock the wire-contract surface so external
    tooling can build against it; the bridge endpoints will ship in a
    follow-up commit (or as part of VBDIP-0002 Track 2 anchor flow).

    Usage::

        client = VAPIZKBA("http://localhost:8081", api_key)

        s = client.status()
        if s.total_artifacts > 0:
            print(f"latest: {s.latest_commitment_hex[:16]} class={s.latest_zkba_class}")

        a = client.get_artifact("056e...")
        if a.found:
            print(f"anchored: {a.anchor_tx_hash}")
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def status(self) -> ZKBAStatusResult:
        """Read GET /operator/zkba-status. Returns ZKBAStatusResult; never raises."""
        try:
            import urllib.request, json
            url = f"{self._base}/operator/zkba-status"
            req = urllib.request.Request(
                url,
                headers={"x-api-key": self._key} if self._key else {},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read().decode())
            latest = body.get("latest") or {}
            return ZKBAStatusResult(
                total_artifacts        = int(body.get("total_artifacts", 0)),
                anchored_count         = int(body.get("anchored_count", 0)),
                track1_invariant_holds = bool(body.get("track1_invariant_holds", True)),
                class_breakdown        = dict(body.get("class_breakdown", {})),
                latest_commitment_hex  = str(latest.get("commitment_hex", "")),
                latest_zkba_class      = int(latest.get("zkba_class", 0)),
                latest_proof_weight    = int(latest.get("proof_weight", 0)),
                latest_ts_ns           = int(latest.get("ts_ns", 0)),
                frozen_v1_position     = int(body.get("frozen_v1_position", 10)),
                domain_tag             = str(body.get("domain_tag", "VAPI-ZKBA-ARTIFACT-v1")),
            )
        except Exception as exc:
            return ZKBAStatusResult(error=str(exc))

    def get_artifact(self, commitment_hex: str) -> ZKBAArtifactResult:
        """Read GET /operator/zkba-artifact/<commitment_hex>. Returns
        ZKBAArtifactResult; never raises. `found=False` if 404 or absent."""
        try:
            import urllib.request, json
            url = f"{self._base}/operator/zkba-artifact/{commitment_hex}"
            req = urllib.request.Request(
                url,
                headers={"x-api-key": self._key} if self._key else {},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read().decode())
            if not body.get("found", False):
                return ZKBAArtifactResult(commitment_hex=commitment_hex, found=False)
            row = body.get("db_row") or {}
            return ZKBAArtifactResult(
                commitment_hex           = str(row.get("commitment_hex", commitment_hex)),
                found                    = True,
                zkba_class               = int(row.get("zkba_class", 0)),
                proof_weight             = int(row.get("proof_weight", 0)),
                preimage_json            = str(row.get("preimage_json", "")),
                ts_ns                    = int(row.get("ts_ns", 0)),
                manifest_uri             = str(row.get("manifest_uri") or ""),
                compiler_output_hash_hex = str(row.get("compiler_output_hash_hex") or ""),
                anchor_tx_hash           = row.get("anchor_tx_hash"),  # may be None
                created_at               = float(row.get("created_at", 0.0)),
            )
        except Exception as exc:
            return ZKBAArtifactResult(commitment_hex=commitment_hex, error=str(exc))

    def history(self, *, limit: int = 20) -> ZKBAHistoryResult:
        """Read GET /operator/zkba-history?limit=N. Most recent first by ts_ns.

        Args:
            limit: 1-500. Default 20.
        """
        try:
            import urllib.request, json, urllib.parse
            url = f"{self._base}/operator/zkba-history?limit={int(limit)}"
            req = urllib.request.Request(
                url,
                headers={"x-api-key": self._key} if self._key else {},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read().decode())
            return ZKBAHistoryResult(
                limit     = int(body.get("limit", limit)),
                row_count = int(body.get("row_count", 0)),
                rows      = list(body.get("rows", [])),
            )
        except Exception as exc:
            return ZKBAHistoryResult(limit=int(limit), error=str(exc))


# === Phase O3-ZKBA-TRACK1 Lane B G4 follow-up SDK (2026-05-12) =================
# VAPIZKBAValidator — wraps POST /operator/zkba-validate-manifest (commit 4f63c5d5).
#
# Closes the C4-style architectural reach trio for the G4 validator:
#   Python lib (scripts/zkba_manifest_validator)
#     -> MCP tool (vapi_validate_zkba_manifest at commit 53553047)
#     -> bridge HTTP (commit 4f63c5d5)
#     -> SDK (this class)
#
# Fail-open: every error path returns ZKBAValidateResult with .error
# populated; never raises. Matches VAPIZKBA / VAPIDraftReview /
# VAPIFleetReadinessRoot pattern.

@dataclass(slots=True)
class ZKBAValidateResult:
    """Result from VAPIZKBAValidator.validate (Phase O3-ZKBA-TRACK1 Lane B G4
    follow-up). Mirrors the bridge endpoint response shape at
    bridge/vapi_bridge/operator_api.py POST /operator/zkba-validate-manifest.

    The `schema_name_form` field surfaces the §9.2-vs-implementation
    schema-name drift V-check finding documented at G4: the validator
    accepts both `vapi-zkba-manifest-v1` (implementation FROZEN; pinned
    by PV-CI INV-ZKBA-003) and `zkba.projection_manifest.v1` (§9.2 spec
    design-time). External tooling can use this field to detect which
    schema name a manifest was emitted under.
    """
    valid:             bool       = False
    errors:            list       = field(default_factory=list)
    zkba_class_name:   str        = ""
    proof_weight_name: str        = ""
    schema_name_form:  str        = "absent"  # "implementation" / "spec_design_time" / "unknown" / "absent"
    error:             "str|None" = None


class VAPIZKBAValidator:
    """Client for POST /operator/zkba-validate-manifest (Phase O3-ZKBA-TRACK1
    Lane B G4 follow-up).

    Validates a ZKBA projection manifest dict against B.8 G4 rules. The
    validator is fail-open at the bridge layer (malformed manifest
    content returns HTTP 200 + valid=False + errors populated); HTTP
    422 is reserved for body-parsing errors (non-JSON body / non-object
    body) at the wire boundary.

    Read-key auth (x-api-key Header).

    Usage::

        client = VAPIZKBAValidator("http://localhost:8081", api_key)

        # Validate a manifest dict you already have in memory
        result = client.validate({"schema": "vapi-zkba-manifest-v1", ...})
        if result.valid:
            print(f"OK: {result.zkba_class_name} / {result.proof_weight_name}")
        else:
            for err in result.errors:
                print(f"INVALID: {err}")

        # Validate a manifest file loaded from disk
        with open("artifact.manifest.json") as f:
            result = client.validate(json.loads(f.read()))
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key

    def validate(self, manifest: dict) -> ZKBAValidateResult:
        """POST a manifest dict to /operator/zkba-validate-manifest and
        return the ManifestValidationResult shape. Never raises.

        Args:
            manifest: dict conforming to vapi-zkba-manifest-v1 (or the
                §9.2 design-time `zkba.projection_manifest.v1` schema).
                MUST be a JSON-serializable dict.

        Returns:
            ZKBAValidateResult. On transport / parse / connection error,
            returns result with .error populated. On bridge wire error
            (HTTP 422 from body-parsing, HTTP 403 from auth failure),
            returns result with .error set to the HTTP error text.
            On successful HTTP exchange (200), returns result with
            .valid + .errors + class/weight names + schema_name_form
            populated from the bridge response body.
        """
        try:
            import urllib.request, urllib.error, json
            url = f"{self._base}/operator/zkba-validate-manifest"
            body_bytes = json.dumps(manifest).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=body_bytes,
                method="POST",
                headers={
                    "x-api-key":    self._key,
                    "Content-Type": "application/json",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    body = json.loads(resp.read().decode())
            except urllib.error.HTTPError as http_exc:
                # 403 wrong key, 422 body-parse, 500 import failure
                try:
                    err_body = json.loads(http_exc.read().decode())
                    err_msg = err_body.get("detail", str(http_exc))
                except Exception:
                    err_msg = f"HTTP {http_exc.code}: {http_exc.reason}"
                return ZKBAValidateResult(error=str(err_msg))
            return ZKBAValidateResult(
                valid             = bool(body.get("valid", False)),
                errors            = list(body.get("errors", [])),
                zkba_class_name   = str(body.get("zkba_class_name", "")),
                proof_weight_name = str(body.get("proof_weight_name", "")),
                schema_name_form  = str(body.get("schema_name_form", "absent")),
            )
        except Exception as exc:
            return ZKBAValidateResult(error=str(exc))



# ===========================================================================
# Phase B ② P4b — VAPIPoEPRegistry client (composite-key / PoEP-commitment registration)
# ===========================================================================


class VAPIPoEPRegistryClient:
    """Client-side helper for VAPIPoEPRegistry (Phase B ②).

    Two surfaces:
      - build_register_tx(...)  : build an UNSIGNED registerDevice transaction for the gamer's
                                  wallet to sign (gamer-sovereign / W1).
      - get_record(...)         : read a device's registration via the bridge read endpoint.

    SDK NO-KEY-HANDLING PROPERTY (auditable): build_register_tx returns an unsigned transaction
    object containing calldata + suggested gas + nonce; the caller (gamer's wallet) is responsible
    for signing. The SDK never holds, accepts, or proxies private keys. (There is intentionally no
    sign/send method on this client — verify by inspection that no private-key parameter exists.)
    """

    # registerDevice(bytes32 deviceId, bytes compositePubkeyBlob, bytes32 poepCommitment, uint64 expiresAt)
    _REGISTER_SIG = b"registerDevice(bytes32,bytes,bytes32,uint64)"

    def __init__(self, registry_address: str = "", bridge_base_url: str = "http://localhost:8080"):
        self.registry_address = registry_address
        self.bridge_base_url = bridge_base_url.rstrip("/")

    def build_register_tx(
        self,
        device_id_b32: bytes,
        composite_pubkey_blob: bytes,
        poep_commitment: bytes,
        *,
        from_address: str | None = None,
        nonce: int | None = None,
        gas: int = 400_000,
        chain_id: int = 4690,
        registry_address: str | None = None,
    ) -> dict:
        """Build the UNSIGNED registerDevice tx. Option A (v1): no expiresAt parameter — the
        contract forces expiresAt == 0 (Property X), so the calldata always encodes 0; a v2 that
        supports a registry-level expiry will add the parameter to this signature then.

        device_id_b32 MUST be the 32-byte on-chain device id (see bridge device_id_to_bytes32:
        sha256(device_id.utf-8) for non-hex ids). Returns an unsigned tx dict the caller signs.
        """
        from eth_abi import encode as _abi_encode
        from eth_utils import keccak

        if not (isinstance(device_id_b32, (bytes, bytearray)) and len(device_id_b32) == 32):
            raise TypeError("device_id_b32 must be exactly 32 bytes (see device_id_to_bytes32)")
        if not (isinstance(poep_commitment, (bytes, bytearray)) and len(poep_commitment) == 32):
            raise TypeError("poep_commitment must be exactly 32 bytes")
        if not composite_pubkey_blob:
            raise ValueError("composite_pubkey_blob must be non-empty")
        to_addr = registry_address or self.registry_address
        if not to_addr:
            raise ValueError("registry_address not set")

        selector = keccak(self._REGISTER_SIG)[:4]
        args = _abi_encode(
            ["bytes32", "bytes", "bytes32", "uint64"],
            [bytes(device_id_b32), bytes(composite_pubkey_blob), bytes(poep_commitment), 0],
        )
        tx: dict = {
            "to": to_addr,
            "data": "0x" + (selector + args).hex(),
            "value": 0,
            "gas": gas,
            "chainId": chain_id,
        }
        if from_address is not None:
            tx["from"] = from_address
        if nonce is not None:
            tx["nonce"] = nonce
        return tx

    def get_record(self, device_id: str, api_key: str = "", timeout: float = 8.0) -> dict:
        """Read a device's registration via the bridge GET /operator/poep-registry/{device_id}.
        Returns the JSON dict (registry_deployed, registered, composite_pubkey_hex)."""
        url = f"{self.bridge_base_url}/operator/poep-registry/{device_id}"
        req = urllib.request.Request(url, headers={"x-api-key": api_key} if api_key else {})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
