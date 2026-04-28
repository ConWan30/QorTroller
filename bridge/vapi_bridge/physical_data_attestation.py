"""Phase O0 Stream 3-prep Session 2 — PHYSICAL_DATA_ATTESTATION v1, the
seventh and final FROZEN-v1 primitive in the family.

PHYSICAL_DATA_ATTESTATION v1 binds an agent's claim about an off-chain
physical-data artifact (a biometric corpus snapshot, a PoAC chain root,
a tremor FFT feature vector, a fleet-coherence observation, or a
hardware-certification proof) into a 32-byte commitment that the agent
can anchor on AgentAdjudicationRegistry. It is the primitive by which
agents make verifiable, replay-protected claims about physical state
they did not produce themselves but observed and certified.

Origin and design lineage:

  Pass 2B Path 3 (commit fe4232e3) introduced PHYSICAL_DATA_ATTESTATION v1
    as the seventh FROZEN-v1 primitive after the V11 conceptual
    alignment finding. It addresses an architectural gap surfaced
    during the Operator Series review: the existing six primitives
    (GIC + WEC + VAME + CORPUS-SNAPSHOT + CONSENT + AGENT_COMMIT) all
    cover protocol-internal state changes; none of them anchor an
    agent's off-chain CERTIFICATION of independently-produced physical
    data. PDA v1 closes that gap.

  Pass 2C Section 4.2 (commit b9ddeeb2) ratified the hash formula,
    store table schema, chain wrapper signature, and PV-CI invariants
    to freeze. The Pass 2C example code carried two arithmetic comment
    typos (tag noted as "32 bytes", input noted as "136 bytes input");
    the actual byte counts are 33 and 137 respectively. The formula
    itself is correct; the implementation docstring carries the
    corrected counts (Finding 1, parallel to AGENT_COMMIT v1's
    "136 → 144" correction in Stream 3-prep Session 1).

  Decision T2 (Stream 3-prep Session 2) confirmed a single test file
    `bridge/tests/test_physical_data_attestation.py` over Pass 2C's
    anticipatory two-file split, matching Session 1's one-file
    precedent.

  Decision T3 (Stream 3-prep Session 2) confirmed the abbreviated
    chain wrapper name `anchor_pda_attestation` per Pass 2C explicit
    specification — a deliberate deviation from the full-name
    precedent (anchor_agent_commit, anchor_corpus_snapshot) chosen
    because the full primitive name is verbose and "PDA" aligns with
    Pass 2B Path 3 and on-chain enum value references.

  Decision T4 (Stream 3-prep Session 2) confirmed no record_*
    orchestrator function. compute_pda_hash is a pure function;
    insert_physical_data_attestation lives in store.py; caller
    composition handles workflow. Mirrors the AGENT_COMMIT v1
    separation exactly.

  Decision T5 (Stream 3-prep Session 2) confirmed keccak256 (via
    eth_utils.keccak) for attestation_type-string-to-bytes32 hashing,
    per Pass 2C Section 4.2. keccak256 is the canonical Solidity
    string-to-bytes32 convention; using it here keeps the canonical
    string vocabulary aligned with on-chain conventions even though
    the FROZEN formula's outer hash is SHA-256.

  DELTA2-Pass2C (Stream 3-prep Session 2) froze INV-PDA-002 as the
    domain tag literal pin, matching Phase 237.5 INV-CORPUS-002
    pattern and Stream 3-prep Session 1 INV-AGENT-COMMIT-002 pattern.
    The domain tag is the cryptographic identifier distinguishing
    PHYSICAL_DATA_ATTESTATION v1 hashes from other primitive hashes;
    modifying it would break every existing anchor's verifiability.

FROZEN FORMULA v1:

    pda_commitment = SHA-256(
        b"VAPI-PHYSICAL-DATA-ATTESTATION-v1"  (33 bytes)  — domain tag
        || hardware_data_hash                 (32 bytes)  — SHA-256 of physical data
        || agent_id                           (32 bytes)  — bytes32 of ioID DID + TBA
        || attestation_type_hash              (32 bytes)  — keccak256 of canonical type string
        || ts_ns_be                           (8 bytes)   — uint64 BE: attestation timestamp
    )                                       = 137 bytes input → SHA-256 → 32 bytes

  Note (Finding 1): Pass 2C Section 4.2 line 538 commented the tag as
  "32 bytes" and line 552 commented the input total as "136 bytes".
  The actual byte counts are 33 (tag) and 137 (input total). The
  formula is correct; only the comments in Pass 2C carried arithmetic
  typos. This module's docstring carries the corrected counts; no
  Pass 2C revision is needed.

attestation_type encoding (Decision T5):

    The on-chain `attestation_type` discriminator maps a canonical
    human-readable string (e.g. "BIOMETRIC_CORPUS_SNAPSHOT") to a
    32-byte commitment via keccak256 (NOT SHA-256). keccak256 is the
    canonical string-to-bytes32 hashing convention in Solidity/EVM
    contexts — the same hashing used by Solidity's `keccak256(bytes(s))`
    and ethers.js `id(s)`. Using keccak256 here keeps PDA v1's
    type-string vocabulary directly comparable to on-chain references
    in adjudication, governance, or audit contracts.

    The FROZEN formula's outer hash remains SHA-256 (consistent with
    every other FROZEN-v1 primitive in the family); only the inner
    string-to-bytes32 step uses keccak256. Both choices are part of
    the v1 freeze.

Recognized canonical attestation_type strings (Pass 2C Section 4.2):

    "BIOMETRIC_CORPUS_SNAPSHOT"    — agent attests a CORPUS-SNAPSHOT v1
                                      derived from biometric data
    "POAC_CHAIN_INTEGRITY"         — agent attests a PoAC chain root
    "TREMOR_FFT_FEATURE_VECTOR"    — agent attests a tremor FFT feature
                                      vector hash
    "FLEET_COHERENCE_OBSERVATION"  — agent attests a fleet-coherence
                                      finding from FleetSignalCoherenceAgent
    "HARDWARE_CERTIFICATION"       — agent attests a hardware-certification
                                      proof from a manufacturer-tier device

    The vocabulary is open in the sense that the SHA-256 outer hash
    accepts any 32-byte attestation_type_hash; auditors expect
    canonical-string preimages to be one of the five recognized
    values. New strings can be added without re-freezing the formula
    (the formula operates on the keccak256 hash, not the string), but
    consensus on new vocabulary entries is part of governance.

Anchor destination:

    The 32-byte pda_commitment is anchored on AgentAdjudicationRegistry
    via chain.anchor_pda_attestation(), which submits to
    anchorAgentAction with actionType=PHYSICAL_DATA_ATTESTATION (enum
    value 1). See chain.py for the chain wrapper.
    AgentAdjudicationRegistry's anti-replay tracker enforces global
    uniqueness — anchoring the same pda_commitment twice reverts.

Phase O0 status:

    Stream 3-prep Session 2 ships this module + chain wrapper as a
    deferred-activation stub. The chain wrapper returns (None, False)
    until Stream 2-deploy lands AgentAdjudicationRegistry on IoTeX
    testnet (gated on wallet funding to ≥3 IOTX per Pass 2A V8). Until
    then, physical_data_attestation.py hash computation is fully
    usable for off-chain audit work; the chain wrapper is dormant.

    PV-CI invariants INV-PDA-001 (hash determinism) and INV-PDA-002
    (domain tag literal pin) are tested in this session but allowlist
    activation is deferred to Stream 3-prep Session 3 (gate-extension
    session), which freezes INV-AGENT-COMMIT-001/002 and INV-PDA-001/002
    atomically with --confirm-governance.

Any change to byte order, domain tag, attestation_type encoding choice,
or field structure requires v2 + new tag. v1 is permanently frozen.

Seventh and final FROZEN-v1 primitive: PHYSICAL_DATA_ATTESTATION v1
completes the Phase O0 primitive expansion from five to seven, closing
the off-chain-physical-data-certification gap surfaced by Pass 2B V11
conceptual alignment.
"""
from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from typing import Optional

# Domain tag — FROZEN literal. INV-PDA-002 pins this byte string.
# Thirty-three bytes: "VAPI-PHYSICAL-DATA-ATTESTATION-v1".
# Pass 2C Section 4.2 line 538 commented this as "# 32 bytes"; actual
# length is 33 bytes (verified: len(_PDA_TAG) == 33). The formula in
# Pass 2C is correct; only the byte-count comment was off by one.
_PDA_TAG = b"VAPI-PHYSICAL-DATA-ATTESTATION-v1"


# Recognized canonical attestation_type strings per Pass 2C Section 4.2.
# The vocabulary is informational here; the FROZEN formula operates on
# the keccak256 hash of whatever string the caller passes. Auditors
# expect canonical-string preimages to be one of these five values.
RECOGNIZED_ATTESTATION_TYPES = (
    "BIOMETRIC_CORPUS_SNAPSHOT",
    "POAC_CHAIN_INTEGRITY",
    "TREMOR_FFT_FEATURE_VECTOR",
    "FLEET_COHERENCE_OBSERVATION",
    "HARDWARE_CERTIFICATION",
)


@dataclass(slots=True)
class PhysicalDataAttestation:
    """Canonical PHYSICAL_DATA_ATTESTATION v1 input fields.

    All bytes fields must be exact-length per the FROZEN formula:
      hardware_data_hash : 32 bytes  (SHA-256 of the off-chain physical data)
      agent_id           : 32 bytes  (Pass 2C Q9 agentId encoding)
      attestation_type   : str       (canonical type string; converted to
                                       bytes32 via keccak256 at hash time)
      ts_ns              : uint64    (0 <= ts_ns <= 0xFFFFFFFFFFFFFFFF)

    The computed hash is set after compute_pda_hash() runs;
    insert_physical_data_attestation() (in store.py) handles
    persistence of "compute hash + insert into physical_data_attestation_log".
    Caller composes the workflow (no record_* orchestrator —
    Decision T4, mirroring AGENT_COMMIT v1 Session 1 separation of
    pure-compute from store-insert concerns).
    """
    hardware_data_hash: bytes
    agent_id: bytes
    attestation_type: str
    ts_ns: int
    pda_commitment: Optional[bytes] = None  # populated by compute_pda_hash


def attestation_type_from_string(s: str) -> bytes:
    """Compute the 32-byte attestation_type hash from a canonical string.

    Uses keccak256 (NOT SHA-256) per Pass 2C Section 4.2 — matches
    Solidity's `keccak256(bytes(s))` and ethers.js `id(s)` conventions
    so the resulting bytes32 is directly comparable to on-chain
    references in adjudication, governance, or audit contracts.

    Args:
        s:  Canonical attestation_type string (UTF-8). One of
            RECOGNIZED_ATTESTATION_TYPES is recommended; the function
            does not enforce vocabulary restriction (the formula
            accepts any string's keccak256 output).

    Returns:
        32-byte keccak256 digest of the UTF-8 bytes of `s`.
    """
    # eth_utils is already a transitive dependency via the web3 stack;
    # importing inside the function keeps the module importable on
    # systems where the dep is missing (e.g. minimal audit-only setups
    # that only call compute_pda_hash with pre-computed bytes32 input).
    from eth_utils import keccak  # type: ignore[import-not-found]
    return keccak(text=s)


def compute_pda_hash(
    hardware_data_hash: bytes,
    agent_id: bytes,
    attestation_type_hash: bytes,
    ts_ns: int,
) -> bytes:
    """Compute the PHYSICAL_DATA_ATTESTATION v1 commitment — FROZEN formula.

    Args:
        hardware_data_hash:    32 bytes — SHA-256 of the off-chain
                                          physical data the agent is
                                          attesting to.
        agent_id:              32 bytes — Pass 2C Q9 agentId encoding.
        attestation_type_hash: 32 bytes — keccak256 of canonical type
                                          string (use
                                          attestation_type_from_string()
                                          to compute).
        ts_ns:                 uint64   — agent's claimed attestation
                                          timestamp in nanoseconds.

    Returns:
        32-byte SHA-256 digest (the pda_commitment).

    Raises:
        ValueError on malformed inputs (length mismatch or ts_ns out
        of uint64 range).

    Hash input total: 33 (tag) + 32 + 32 + 32 + 8 = 137 bytes.
    Pass 2C Section 4.2 commented this as "136 bytes input"; the
    actual count is 137 because the tag is 33 bytes (not 32 as the
    Pass 2C comment claimed). The formula itself is correct; only the
    byte-count comment in Pass 2C was off by one. See module docstring
    Finding 1.
    """
    if len(hardware_data_hash) != 32:
        raise ValueError(
            f"hardware_data_hash must be 32 bytes, got {len(hardware_data_hash)}"
        )
    if len(agent_id) != 32:
        raise ValueError(f"agent_id must be 32 bytes, got {len(agent_id)}")
    if len(attestation_type_hash) != 32:
        raise ValueError(
            f"attestation_type_hash must be 32 bytes, got {len(attestation_type_hash)}"
        )
    if not (0 <= int(ts_ns) <= 0xFFFFFFFFFFFFFFFF):
        raise ValueError(f"ts_ns out of uint64 range: {ts_ns}")

    return hashlib.sha256(
        _PDA_TAG
        + hardware_data_hash
        + agent_id
        + attestation_type_hash
        + struct.pack(">Q", int(ts_ns))
    ).digest()
