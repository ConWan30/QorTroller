"""
IoTeX Chain Client — Web3 contract interactions for PoAC verification.

Handles:
  - PoACVerifier.verifyPoAC() and verifyPoACBatch()
  - BountyMarket.submitEvidence()
  - DeviceRegistry.isDeviceActive() and getDevicePubkey()
  - ProgressAttestation.attestProgress()
  - TeamProofAggregator.createTeam() / submitTeamProof()
  - Gas estimation, nonce management, and transaction confirmation
"""

import asyncio
import functools
import hashlib
import logging
from typing import Sequence

from web3 import AsyncWeb3, AsyncHTTPProvider
from web3.exceptions import ContractLogicError, TransactionNotFound
from eth_account import Account

from .codec import PoACRecord
from .config import Config
from .zk_verifier import ZKVerifier

log = logging.getLogger(__name__)


# Phase 237.5.1 Path C+ kill-switch decorator — gates legacy chain submission
# methods that bypass the _send_tx chokepoint. Without this, setting
# CHAIN_SUBMISSION_PAUSED=true in bridge/.env only stops _send_tx callers
# (batcher, anchor_corpus_snapshot, anchor_agent_commit) but legacy methods
# (record_ruling_on_chain, record_adjudication, mint_vhp, etc.) still
# fire-and-forget on every call. On IoTeX testnet's broken P256 precompile
# these revert and consume gas anyway, draining the wallet (incident
# 2026-05-06: ~6.27 IOTX drained from 6.42 → 0.13 IOTX after rawTransaction
# fix re-enabled previously-broken submission paths).
#
# Apply @_gated_submission to every async method whose body calls
# self._w3.eth.send_raw_transaction. Returns "" sentinel (matches str return
# convention; callers already treat empty tx_hash as "not on chain").
def _gated_submission(fn):
    @functools.wraps(fn)
    async def wrapper(self, *args, **kwargs):
        if getattr(self._cfg, "chain_submission_paused", False):
            log.warning(
                "%s: chain_submission_paused=true — transaction skipped "
                "(CHAIN_SUBMISSION_PAUSED kill-switch active)",
                fn.__name__,
            )
            return ""
        return await fn(self, *args, **kwargs)
    return wrapper

# Minimal ABIs — only the functions the bridge calls.
# Generated from the exact Solidity signatures in the contracts.

VERIFIER_ABI = [
    {
        "name": "verifyPoAC",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "_deviceId", "type": "bytes32"},
            {"name": "_rawBody", "type": "bytes"},
            {"name": "_signature", "type": "bytes"},
        ],
        "outputs": [{"name": "recordHash", "type": "bytes32"}],
    },
    {
        "name": "verifyPoACBatch",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "_deviceIds", "type": "bytes32[]"},
            {"name": "_rawBodies", "type": "bytes[]"},
            {"name": "_signatures", "type": "bytes[]"},
        ],
        "outputs": [{"name": "recordHashes", "type": "bytes32[]"}],
    },
    {
        "name": "isRecordVerified",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "_recordHash", "type": "bytes32"}],
        "outputs": [{"name": "", "type": "bool"}],
    },
    {
        "name": "getVerifiedCount",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "_deviceId", "type": "bytes32"}],
        "outputs": [{"name": "count", "type": "uint32"}],
    },
    # --- Phase 12: Schema version + inference storage ---
    {
        "name": "verifyPoACWithSchema",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "_deviceId",      "type": "bytes32"},
            {"name": "_rawBody",       "type": "bytes"},
            {"name": "_signature",     "type": "bytes"},
            {"name": "_schemaVersion", "type": "uint8"},
        ],
        "outputs": [{"name": "recordHash", "type": "bytes32"}],
    },
    {
        "name": "getRecordSchema",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "_recordHash", "type": "bytes32"}],
        "outputs": [
            {"name": "schemaVersion", "type": "uint8"},
            {"name": "isSet",         "type": "bool"},
        ],
    },
    {
        "name": "recordInferences",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "", "type": "bytes32"}],
        "outputs": [{"name": "", "type": "uint8"}],
    },
]

BOUNTY_MARKET_ABI = [
    {
        "name": "submitEvidence",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "_bountyId", "type": "uint256"},
            {"name": "_deviceId", "type": "bytes32"},
            {"name": "_recordHash", "type": "bytes32"},
            {"name": "_latitude", "type": "int64"},
            {"name": "_longitude", "type": "int64"},
            {"name": "_timestampMs", "type": "int64"},
        ],
        "outputs": [],
    },
    {
        "name": "getBounty",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "_bountyId", "type": "uint256"}],
        "outputs": [
            {
                "name": "",
                "type": "tuple",
                "components": [
                    {"name": "bountyId", "type": "uint256"},
                    {"name": "creator", "type": "address"},
                    {"name": "reward", "type": "uint256"},
                    {"name": "sensorRequirements", "type": "uint16"},
                    {"name": "minSamples", "type": "uint16"},
                    {"name": "sampleIntervalS", "type": "uint32"},
                    {"name": "durationS", "type": "uint32"},
                    {"name": "deadlineMs", "type": "uint64"},
                    {"name": "zoneLatMin", "type": "int64"},
                    {"name": "zoneLatMax", "type": "int64"},
                    {"name": "zoneLonMin", "type": "int64"},
                    {"name": "zoneLonMax", "type": "int64"},
                    {"name": "vocThreshold", "type": "int256"},
                    {"name": "tempThresholdHi", "type": "int256"},
                    {"name": "tempThresholdLo", "type": "int256"},
                    {"name": "status", "type": "uint8"},
                    {"name": "createdAt", "type": "uint256"},
                ],
            },
        ],
    },
]

REGISTRY_ABI = [
    {
        "name": "isDeviceActive",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "_deviceId", "type": "bytes32"}],
        "outputs": [{"name": "", "type": "bool"}],
    },
    {
        "name": "getDevicePubkey",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "_deviceId", "type": "bytes32"}],
        "outputs": [{"name": "", "type": "bytes"}],
    },
    {
        "name": "getReputationScore",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "_deviceId", "type": "bytes32"}],
        "outputs": [{"name": "score", "type": "uint16"}],
    },
    {
        "name": "registerDevice",
        "type": "function",
        "stateMutability": "payable",
        "inputs": [{"name": "_pubkey", "type": "bytes"}],
        "outputs": [{"name": "deviceId", "type": "bytes32"}],
    },
    {
        "name": "minimumDeposit",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint256"}],
    },
    # --- Phase 7: TieredDeviceRegistry extensions ---
    {
        "name": "registerTieredDevice",
        "type": "function",
        "stateMutability": "payable",
        "inputs": [
            {"name": "_pubkey", "type": "bytes"},
            {"name": "_tier",   "type": "uint8"},
        ],
        "outputs": [{"name": "deviceId", "type": "bytes32"}],
    },
    {
        "name": "registerAttested",
        "type": "function",
        "stateMutability": "payable",
        "inputs": [
            {"name": "_pubkey",           "type": "bytes"},
            {"name": "_attestationProof", "type": "bytes"},
        ],
        "outputs": [{"name": "deviceId", "type": "bytes32"}],
    },
    {
        "name": "getDeviceTier",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "_deviceId", "type": "bytes32"}],
        "outputs": [{"name": "", "type": "uint8"}],
    },
    {
        "name": "getDeviceRewardWeightBps",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "_deviceId", "type": "bytes32"}],
        "outputs": [{"name": "", "type": "uint16"}],
    },
    {
        "name": "canClaimBounty",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "_deviceId", "type": "bytes32"}],
        "outputs": [{"name": "", "type": "bool"}],
    },
    {
        "name": "tierConfigs",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "", "type": "uint8"}],
        "outputs": [
            {"name": "depositWei",        "type": "uint256"},
            {"name": "rewardWeightBps",   "type": "uint16"},
            {"name": "canClaimBounties",  "type": "bool"},
            {"name": "canUseSkillOracle", "type": "bool"},
        ],
    },
    # --- Phase 9: Hardware attestation cert hash ---
    {
        "name": "registerAttestedWithCert",
        "type": "function",
        "stateMutability": "payable",
        "inputs": [
            {"name": "_pubkey",           "type": "bytes"},
            {"name": "_attestationProof", "type": "bytes"},
            {"name": "_certificateHash",  "type": "bytes32"},
        ],
        "outputs": [{"name": "deviceId", "type": "bytes32"}],
    },
    {
        "name": "setAttestationCertHash",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "_deviceId", "type": "bytes32"},
            {"name": "_certHash", "type": "bytes32"},
        ],
        "outputs": [],
    },
    {
        "name": "attestationCertificateHashes",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "", "type": "bytes32"}],
        "outputs": [{"name": "", "type": "bytes32"}],
    },
    # --- Phase 10: V2 attestation with manufacturer P256 key verification ---
    {
        "name": "registerAttestedV2",
        "type": "function",
        "stateMutability": "payable",
        "inputs": [
            {"name": "_pubkey",           "type": "bytes"},
            {"name": "_attestationProof", "type": "bytes"},
            {"name": "_manufacturer",     "type": "address"},
        ],
        "outputs": [{"name": "deviceId", "type": "bytes32"}],
    },
    {
        "name": "registerAttestedWithCertV2",
        "type": "function",
        "stateMutability": "payable",
        "inputs": [
            {"name": "_pubkey",           "type": "bytes"},
            {"name": "_attestationProof", "type": "bytes"},
            {"name": "_certificateHash",  "type": "bytes32"},
            {"name": "_manufacturer",     "type": "address"},
        ],
        "outputs": [{"name": "deviceId", "type": "bytes32"}],
    },
    {
        "name": "setManufacturerKey",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "_manufacturer", "type": "address"},
            {"name": "_pubkeyX",      "type": "bytes32"},
            {"name": "_pubkeyY",      "type": "bytes32"},
            {"name": "_name",         "type": "string"},
        ],
        "outputs": [],
    },
    {
        "name": "revokeManufacturerKey",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [{"name": "_manufacturer", "type": "address"}],
        "outputs": [],
    },
    {
        "name": "manufacturerKeys",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "", "type": "address"}],
        "outputs": [
            {"name": "pubkeyX", "type": "bytes32"},
            {"name": "pubkeyY", "type": "bytes32"},
            {"name": "active",  "type": "bool"},
            {"name": "name",    "type": "string"},
        ],
    },
    # --- Phase 12: getManufacturerKey view function + revocation event ---
    {
        "name": "getManufacturerKey",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "_manufacturer", "type": "address"}],
        "outputs": [
            {"name": "pubkeyX", "type": "bytes32"},
            {"name": "pubkeyY", "type": "bytes32"},
            {"name": "active",  "type": "bool"},
            {"name": "name",    "type": "string"},
        ],
    },
    {
        "name": "ManufacturerKeyRevoked",
        "type": "event",
        "anonymous": False,
        "inputs": [
            {"name": "manufacturer", "type": "address", "indexed": True},
        ],
    },
]

# --- Phase 7: Tier constants ---
TIER_VALUES = {"Emulated": 0, "Standard": 1, "Attested": 2}
TIER_NAMES  = {0: "Emulated", 1: "Standard", 2: "Attested"}


PROGRESS_ATTESTATION_ABI = [
    {
        "name": "attestProgress",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "_deviceId",       "type": "bytes32"},
            {"name": "_baselineHash",   "type": "bytes32"},
            {"name": "_currentHash",    "type": "bytes32"},
            {"name": "_metricType",     "type": "uint8"},
            {"name": "_improvementBps", "type": "uint32"},
        ],
        "outputs": [{"name": "attestationId", "type": "uint256"}],
    },
    {
        "name": "getDeviceAttestationCount",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "_deviceId", "type": "bytes32"}],
        "outputs": [{"name": "", "type": "uint256"}],
    },
]

TEAM_AGGREGATOR_ABI = [
    {
        "name": "createTeam",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "_teamId",    "type": "bytes32"},
            {"name": "_deviceIds", "type": "bytes32[]"},
        ],
        "outputs": [],
    },
    {
        "name": "submitTeamProof",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "_teamId",       "type": "bytes32"},
            {"name": "_recordHashes", "type": "bytes32[]"},
            {"name": "_merkleRoot",   "type": "bytes32"},
        ],
        "outputs": [{"name": "proofId", "type": "uint256"}],
    },
    {
        "name": "teamExists",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "", "type": "bytes32"}],
        "outputs": [{"name": "", "type": "bool"}],
    },
]

PHG_REGISTRY_ABI = [
    {
        "name": "commitCheckpoint",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "deviceId",      "type": "bytes32"},
            {"name": "scoreDelta",    "type": "uint256"},
            {"name": "count",         "type": "uint32"},
            {"name": "biometricHash", "type": "bytes32"},
        ],
        "outputs": [],
    },
    {
        "name": "cumulativeScore",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "", "type": "bytes32"}],
        "outputs": [{"name": "", "type": "uint256"}],
    },
    {
        "name": "isEligible",
        "type": "function",
        "stateMutability": "view",
        "inputs": [
            {"name": "deviceId", "type": "bytes32"},
            {"name": "minScore", "type": "uint256"},
        ],
        "outputs": [{"name": "", "type": "bool"}],
    },
    {
        "name": "getDeviceState",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "deviceId", "type": "bytes32"}],
        "outputs": [
            {"name": "score", "type": "uint256"},
            {"name": "count", "type": "uint32"},
            {"name": "head",  "type": "bytes32"},
        ],
    },
    # Phase 23: score inheritance (callable only by IdentityContinuityRegistry)
    {
        "name": "inheritScore",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "fromId", "type": "bytes32"},
            {"name": "toId",   "type": "bytes32"},
        ],
        "outputs": [],
    },
    {
        "name": "setIdentityRegistry",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [{"name": "reg", "type": "address"}],
        "outputs": [],
    },
    {
        "name": "identityRegistry",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "address"}],
    },
    # Phase 25: on-chain event + velocity view functions
    {
        "name": "PHGCheckpointCommitted",
        "type": "event",
        "inputs": [
            {"name": "deviceId",           "type": "bytes32", "indexed": True},
            {"name": "cumulativeScore",    "type": "uint256", "indexed": False},
            {"name": "recordCount",        "type": "uint32",  "indexed": False},
            {"name": "biometricHash",      "type": "bytes32", "indexed": False},
            {"name": "prevCheckpointHash", "type": "bytes32", "indexed": False},
            {"name": "blockNumber",        "type": "uint256", "indexed": False},
        ],
    },
    {
        "name": "scoreDeltaAt",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "", "type": "bytes32"}],
        "outputs": [{"name": "", "type": "uint256"}],
    },
    {
        "name": "getRecentVelocity",
        "type": "function",
        "stateMutability": "view",
        "inputs": [
            {"name": "deviceId",   "type": "bytes32"},
            {"name": "windowSize", "type": "uint256"},
        ],
        "outputs": [{"name": "velocity", "type": "uint256"}],
    },
]

PITL_SESSION_REGISTRY_ABI = [
    {
        "name": "submitPITLProof",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "deviceId",          "type": "bytes32"},
            {"name": "proof",             "type": "bytes"},
            {"name": "featureCommitment", "type": "uint256"},
            {"name": "humanityProbInt",   "type": "uint256"},
            {"name": "nullifierHash",     "type": "uint256"},
            {"name": "epoch",             "type": "uint256"},
        ],
        "outputs": [],
    },
    {
        "name": "latestHumanityProb",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "", "type": "bytes32"}],
        "outputs": [{"name": "", "type": "uint256"}],
    },
    {
        "name": "sessionCount",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "", "type": "bytes32"}],
        "outputs": [{"name": "", "type": "uint256"}],
    },
    {
        "name": "usedNullifiers",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "", "type": "bytes32"}],
        "outputs": [{"name": "", "type": "bool"}],
    },
    {
        "name": "PITLSessionProofSubmitted",
        "type": "event",
        "anonymous": False,
        "inputs": [
            {"name": "deviceId",          "type": "bytes32", "indexed": True},
            {"name": "humanityProbInt",   "type": "uint256", "indexed": False},
            {"name": "featureCommitment", "type": "uint256", "indexed": False},
            {"name": "epoch",             "type": "uint256", "indexed": True},
        ],
    },
    {
        "name": "PITLVerifierSet",
        "type": "event",
        "anonymous": False,
        "inputs": [
            {"name": "verifier", "type": "address", "indexed": True},
        ],
    },
]

# Phase B item ② P4b — minimal VAPIPoEPRegistry read ABI (view calls + the DeviceRegistered
# event the bridge consumes to resolve a device's composite pubkey). Read-only surface only.
_VAPI_POEP_REGISTRY_ABI = [
    {
        "name": "getCompositePubkeyHash", "type": "function", "stateMutability": "view",
        "inputs": [{"name": "gamer", "type": "address"}, {"name": "deviceId", "type": "bytes32"}],
        "outputs": [{"type": "bytes32"}],
    },
    {
        "name": "isRegistrationValid", "type": "function", "stateMutability": "view",
        "inputs": [{"name": "gamer", "type": "address"}, {"name": "deviceId", "type": "bytes32"}],
        "outputs": [{"type": "bool"}],
    },
    {
        "name": "DeviceRegistered", "type": "event", "anonymous": False,
        "inputs": [
            {"name": "gamer", "type": "address", "indexed": True},
            {"name": "deviceId", "type": "bytes32", "indexed": True},
            {"name": "compositePubkeyHash", "type": "bytes32", "indexed": True},
            {"name": "poepCommitment", "type": "bytes32", "indexed": False},
            {"name": "compositePubkeyBlob", "type": "bytes", "indexed": False},
            {"name": "expiresAt", "type": "uint64", "indexed": False},
            {"name": "blockNumber", "type": "uint256", "indexed": False},
        ],
    },
]

# Path A Arc 1 Commit 2 — VAPIManufacturerDeviceRegistry read-only ABI.
# Bridge consumes view calls + events ONLY; registerDevice/revokeDevice are operator/
# manufacturer-wallet calls, never bridge calls. Trust model is MANUFACTURER-
# AUTHORITATIVE (onlyOwner writes) — deliberate divergence from the gamer-sovereign
# VAPIPoEPRegistry. See VAPIManufacturerDeviceRegistry.sol NatSpec header for the
# full divergence rationale.
_VAPI_MANUFACTURER_DEVICE_REGISTRY_ABI = [
    {
        "name": "getSigningPath", "type": "function", "stateMutability": "view",
        "inputs":  [{"name": "deviceId", "type": "bytes32"}],
        "outputs": [{"type": "uint8"}],
    },
    {
        "name": "getProofTier", "type": "function", "stateMutability": "view",
        "inputs":  [{"name": "deviceId", "type": "bytes32"}],
        "outputs": [{"type": "uint8"}],
    },
    {
        "name": "isPathA", "type": "function", "stateMutability": "view",
        "inputs":  [{"name": "deviceId", "type": "bytes32"}],
        "outputs": [{"type": "bool"}],
    },
    {
        "name": "isActive", "type": "function", "stateMutability": "view",
        "inputs":  [{"name": "deviceId", "type": "bytes32"}],
        "outputs": [{"type": "bool"}],
    },
    {
        "name": "DeviceRegistered", "type": "event", "anonymous": False,
        "inputs": [
            {"name": "deviceId",        "type": "bytes32", "indexed": True},
            {"name": "controllerModel", "type": "bytes32", "indexed": False},
            {"name": "signingPath",     "type": "uint8",   "indexed": False},
            {"name": "proofTier",       "type": "uint8",   "indexed": False},
        ],
    },
    {
        "name": "DeviceRevoked", "type": "event", "anonymous": False,
        "inputs": [{"name": "deviceId", "type": "bytes32", "indexed": True}],
    },
    # Path A Arc 1 Commit 4 — extend MFG ABI with getDevice so the bridge can
    # read the full DeviceRegistration tuple (specifically controllerModel for
    # name reverse-lookup via controller_models.name_for_hash). Still views-
    # only; writers remain excluded from the bridge ABI.
    {
        "name": "getDevice", "type": "function", "stateMutability": "view",
        "inputs":  [{"name": "deviceId", "type": "bytes32"}],
        "outputs": [{
            "type": "tuple",
            "components": [
                {"name": "pubkeyHash",         "type": "bytes32"},
                {"name": "controllerModel",    "type": "bytes32"},
                {"name": "signingPath",        "type": "uint8"},
                {"name": "proofTier",          "type": "uint8"},
                {"name": "registeredAt",       "type": "uint64"},
                {"name": "birthCertHash",      "type": "bytes32"},
                {"name": "manufacturerWallet", "type": "address"},
                {"name": "active",             "type": "bool"},
            ],
        }],
    },
]


# Data Economy Arc 1 — VAPIBuyerRegistry read-only ABI. Views only; the bridge
# never issues/revokes credentials (that is the Curator's on-chain write path).
_VAPI_BUYER_REGISTRY_ABI = [
    {
        "name": "isValidCredential", "type": "function", "stateMutability": "view",
        "inputs":  [{"name": "buyerDID", "type": "bytes32"}, {"name": "categoryId", "type": "uint8"}],
        "outputs": [{"type": "bool"}],
    },
    {
        "name": "getCategory", "type": "function", "stateMutability": "view",
        "inputs":  [{"name": "buyerDID", "type": "bytes32"}],
        "outputs": [{"type": "uint8"}],
    },
]


# Data Economy Arc 2 — VAPIBuyerCategoryVerifier read-only ABI. Pure Groth16
# view verifier (snarkjs-generated): verifyProof is the only entrypoint and
# takes no state. The bridge calls it via staticcall to check a private
# buyer-category proof without learning the buyerDID. Views only — no writer.
_VAPI_BUYER_CATEGORY_VERIFIER_ABI = [
    {
        "name": "verifyProof", "type": "function", "stateMutability": "view",
        "inputs": [
            {"name": "_pA", "type": "uint256[2]"},
            {"name": "_pB", "type": "uint256[2][2]"},
            {"name": "_pC", "type": "uint256[2]"},
            {"name": "_pubSignals", "type": "uint256[5]"},
        ],
        "outputs": [{"type": "bool"}],
    },
]


# Path A Arc 1 Commit 4 — VAPIProtocolLensV2 read-only ABI. Replaces the
# inline 4-line ABI that lived in is_fully_eligible (commit dca29217). Adds
# the two new Path A entries (isFullyEligible_PathA + getDeviceTier).
_VAPI_PROTOCOL_LENS_V2_ABI = [
    {
        "name": "isFullyEligible", "type": "function", "stateMutability": "view",
        "inputs":  [{"name": "deviceId", "type": "bytes32"}],
        "outputs": [{"type": "bool"}],
    },
    {
        "name": "isFullyEligible_PathA", "type": "function", "stateMutability": "view",
        "inputs":  [{"name": "deviceId", "type": "bytes32"}],
        "outputs": [{"type": "bool"}],
    },
    {
        "name": "getDeviceTier", "type": "function", "stateMutability": "view",
        "inputs":  [{"name": "deviceId", "type": "bytes32"}],
        "outputs": [{"type": "uint8"}],
    },
]


IOID_REGISTRY_ABI = [
    {
        "name": "register",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "deviceId",      "type": "bytes32"},
            {"name": "deviceAddress", "type": "address"},
            {"name": "did",           "type": "string"},
        ],
        "outputs": [],
    },
    {
        "name": "incrementSession",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [{"name": "deviceId", "type": "bytes32"}],
        "outputs": [],
    },
    {
        "name": "getDID",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "deviceId", "type": "bytes32"}],
        "outputs": [{"name": "", "type": "string"}],
    },
    {
        "name": "isRegistered",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "deviceId", "type": "bytes32"}],
        "outputs": [{"name": "", "type": "bool"}],
    },
    {
        "name": "getDeviceCount",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint256"}],
    },
]

TOURNAMENT_PASSPORT_ABI = [
    {
        "name": "submitPassport",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "deviceId",       "type": "bytes32"},
            {"name": "proof",          "type": "bytes"},
            {"name": "nullifiers",     "type": "bytes32[5]"},
            {"name": "passportHash",   "type": "bytes32"},
            {"name": "ioidTokenId",    "type": "uint256"},
            {"name": "minHumanityInt", "type": "uint256"},
            {"name": "epoch",          "type": "uint256"},
        ],
        "outputs": [],
    },
    {
        "name": "getPassport",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "deviceId", "type": "bytes32"}],
        "outputs": [
            {
                "name": "",
                "type": "tuple",
                "components": [
                    {"name": "passportHash",   "type": "bytes32"},
                    {"name": "ioidTokenId",    "type": "uint256"},
                    {"name": "minHumanityInt", "type": "uint256"},
                    {"name": "issuedAt",       "type": "uint256"},
                    {"name": "active",         "type": "bool"},
                ],
            }
        ],
    },
    {
        "name": "hasPassport",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "deviceId", "type": "bytes32"}],
        "outputs": [{"name": "", "type": "bool"}],
    },
]

IDENTITY_REGISTRY_ABI = [
    {
        "name": "attestContinuity",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "oldDeviceId",        "type": "bytes32"},
            {"name": "newDeviceId",        "type": "bytes32"},
            {"name": "biometricProofHash", "type": "bytes32"},
        ],
        "outputs": [],
    },
    {
        "name": "isContinuationOf",
        "type": "function",
        "stateMutability": "view",
        "inputs": [
            {"name": "newId", "type": "bytes32"},
            {"name": "oldId", "type": "bytes32"},
        ],
        "outputs": [{"name": "", "type": "bool"}],
    },
    {
        "name": "getCanonicalRoot",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "deviceId", "type": "bytes32"}],
        "outputs": [{"name": "root", "type": "bytes32"}],
    },
    {
        "name": "claimed",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "", "type": "bytes32"}],
        "outputs": [{"name": "", "type": "bool"}],
    },
    {
        "name": "continuedFrom",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "", "type": "bytes32"}],
        "outputs": [{"name": "", "type": "bytes32"}],
    },
]

# Phase 28: PHG Credential soulbound registry
PHG_CREDENTIAL_ABI = [
    {
        "name": "mintCredential",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "deviceId",          "type": "bytes32"},
            {"name": "nullifierHash",     "type": "bytes32"},
            {"name": "featureCommitment", "type": "bytes32"},
            {"name": "humanityProbInt",   "type": "uint256"},
        ],
        "outputs": [{"name": "id", "type": "uint256"}],
    },
    {
        "name": "hasCredential",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "deviceId", "type": "bytes32"}],
        "outputs": [{"name": "", "type": "bool"}],
    },
    {
        "name": "credentialOf",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "deviceId", "type": "bytes32"}],
        "outputs": [{"name": "", "type": "uint256"}],
    },
    {
        "name": "CredentialMinted",
        "type": "event",
        "inputs": [
            {"name": "deviceId",      "type": "bytes32", "indexed": True},
            {"name": "credentialId",  "type": "uint256", "indexed": True},
            {"name": "humanityProbInt", "type": "uint256", "indexed": False},
            {"name": "blockNumber",   "type": "uint256", "indexed": False},
        ],
    },
    # Phase 37: Provisional enforcement
    {
        "name": "suspend",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "deviceId",         "type": "bytes32"},
            {"name": "evidenceHash",     "type": "bytes32"},
            {"name": "durationSeconds",  "type": "uint256"},
        ],
        "outputs": [],
    },
    {
        "name": "reinstate",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [{"name": "deviceId", "type": "bytes32"}],
        "outputs": [],
    },
    {
        "name": "isActive",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "deviceId", "type": "bytes32"}],
        "outputs": [{"name": "", "type": "bool"}],
    },
    {
        "name": "isSuspended",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "deviceId", "type": "bytes32"}],
        "outputs": [{"name": "", "type": "bool"}],
    },
    {
        "name": "CredentialSuspended",
        "type": "event",
        "inputs": [
            {"name": "deviceId",     "type": "bytes32", "indexed": True},
            {"name": "evidenceHash", "type": "bytes32", "indexed": False},
            {"name": "until",        "type": "uint256", "indexed": False},
        ],
    },
    {
        "name": "CredentialReinstated",
        "type": "event",
        "inputs": [
            {"name": "deviceId", "type": "bytes32", "indexed": True},
        ],
    },
]


# Phase 34: Federated Threat Registry (cross-bridge cluster anchoring)
FEDERATED_THREAT_REGISTRY_ABI = [
    {
        "name": "reportCluster",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [{"name": "clusterHash", "type": "bytes32"}],
        "outputs": [],
    },
    {
        "name": "getReportCount",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "clusterHash", "type": "bytes32"}],
        "outputs": [{"name": "", "type": "uint256"}],
    },
]


def _record_raw_body(record: PoACRecord) -> bytes:
    """Get the raw 164-byte body for on-chain submission.

    The contract now accepts the raw body directly (no struct re-serialization),
    ensuring the on-chain SHA-256 hash matches the firmware-computed hash exactly.
    """
    if record.raw_body and len(record.raw_body) == 164:
        return record.raw_body
    raise ValueError(
        f"PoACRecord missing raw_body (len={len(record.raw_body) if record.raw_body else 0})"
    )


class ChainClient:
    """Async Web3 client for IoTeX contract interactions."""

    def __init__(self, cfg: Config):
        self._cfg = cfg
        self._w3 = AsyncWeb3(AsyncHTTPProvider(cfg.iotex_rpc_url))
        # Phase 235.x-STABILITY-9 stage 12 2026-05-17: companion synchronous
        # Web3 client. Created alongside the async client so that callers
        # which want to offload blocking RPC reads to a worker thread (via
        # asyncio.to_thread) can do so without losing AsyncWeb3 cancellation
        # behavior for ordinary async paths. Rationale: on Windows
        # ProactorEventLoop the AsyncHTTPProvider socket read does not honor
        # asyncio.wait_for() cancellation cleanly — when IoTeX RPC stalls,
        # the event loop blocks for the full OS socket timeout (~20-50s)
        # regardless of any asyncio-level timeout. Routing the blocking
        # read through asyncio.to_thread(sync_w3.eth.<call>) confines the
        # blocked thread to a single ThreadPoolExecutor slot, leaving the
        # event loop heartbeat healthy. Lazy-imported to avoid hard
        # dependency at module import time.
        try:
            from web3 import Web3, HTTPProvider as _SyncHTTPProvider
            self._sync_w3 = Web3(_SyncHTTPProvider(cfg.iotex_rpc_url))
        except Exception as _sync_w3_exc:  # noqa: BLE001 — fail-open
            log.warning(
                "ChainClient: sync Web3 companion unavailable (%s); "
                "STAGE-12 chain-read offload will fall back to AsyncWeb3 path",
                _sync_w3_exc,
            )
            self._sync_w3 = None

        # Phase 11: Support encrypted keystore as an alternative to plaintext env key
        source = getattr(cfg, "bridge_private_key_source", "env")
        if source == "keystore":
            import json as _json
            import os as _os
            ks_path = getattr(cfg, "keystore_path", "")
            pw_env  = getattr(cfg, "keystore_password_env", "BRIDGE_KEYSTORE_PASSWORD")
            password = _os.environ.get(pw_env, "")
            if not password:
                raise ValueError(
                    f"Keystore password env var {pw_env!r} is not set. "
                    "Set it before starting the bridge."
                )
            with open(ks_path) as _f:
                keystore_json = _json.load(_f)
            private_key = Account.decrypt(keystore_json, password)
            self._account = Account.from_key(private_key)
            log.info("Bridge key loaded from keystore: %s (address=%s)", ks_path, self._account.address)
        else:
            # "env" source — only parse key when it is actually set
            if getattr(cfg, "bridge_private_key", ""):
                log.warning(
                    "BRIDGE_PRIVATE_KEY is a plaintext env var. "
                    "For mainnet, migrate to an encrypted keystore "
                    "(BRIDGE_PRIVATE_KEY_SOURCE=keystore)."
                )
                self._account = Account.from_key(cfg.bridge_private_key)
            else:
                # No key configured — acceptable for dry_run mode; chain writes will fail
                # gracefully if attempted (all writes are guarded by dry_run checks).
                self._account = None
                log.warning(
                    "BRIDGE_PRIVATE_KEY is not set — chain signing disabled. "
                    "The bridge will start in read-only mode. "
                    "Add BRIDGE_PRIVATE_KEY=<64-char hex private key> to bridge/.env "
                    "to enable on-chain writes."
                )

        self._nonce_lock = asyncio.Lock()
        self._nonce: int | None = None
        # Phase 12: Cache of revoked manufacturer addresses (lowercased)
        self._revoked_manufacturers: set[str] = set()

        # Initialize contracts
        if cfg.verifier_address:
            self._verifier = self._w3.eth.contract(
                address=self._w3.to_checksum_address(cfg.verifier_address),
                abi=VERIFIER_ABI,
            )
        else:
            self._verifier = None
            log.warning(
                "POAC_VERIFIER_ADDRESS not set — on-chain PoAC verification disabled. "
                "Add POAC_VERIFIER_ADDRESS to bridge/.env."
            )
        if cfg.bounty_market_address:
            self._bounty_market = self._w3.eth.contract(
                address=self._w3.to_checksum_address(cfg.bounty_market_address),
                abi=BOUNTY_MARKET_ABI,
            )
        else:
            self._bounty_market = None

        if cfg.device_registry_address:
            self._registry = self._w3.eth.contract(
                address=self._w3.to_checksum_address(cfg.device_registry_address),
                abi=REGISTRY_ABI,
            )
        else:
            self._registry = None

        progress_addr = getattr(cfg, "progress_attestation_address", "")
        if progress_addr:
            self._progress = self._w3.eth.contract(
                address=self._w3.to_checksum_address(progress_addr),
                abi=PROGRESS_ATTESTATION_ABI,
            )
        else:
            self._progress = None

        team_addr = getattr(cfg, "team_aggregator_address", "")
        if team_addr:
            self._team_agg = self._w3.eth.contract(
                address=self._w3.to_checksum_address(team_addr),
                abi=TEAM_AGGREGATOR_ABI,
            )
        else:
            self._team_agg = None

        # Phase 22: PHG Registry (optional)
        phg_addr = getattr(cfg, "phg_registry_address", "")
        if phg_addr:
            self._phg_registry = self._w3.eth.contract(
                address=self._w3.to_checksum_address(phg_addr),
                abi=PHG_REGISTRY_ABI,
            )
        else:
            self._phg_registry = None

        # Phase 23: Identity Continuity Registry (optional)
        identity_addr = getattr(cfg, "identity_registry_address", "")
        if identity_addr:
            self._identity_registry = self._w3.eth.contract(
                address=self._w3.to_checksum_address(identity_addr),
                abi=IDENTITY_REGISTRY_ABI,
            )
        else:
            self._identity_registry = None

        # Phase 26: PITL Session Registry (optional)
        pitl_addr = getattr(cfg, "pitl_session_registry_address", "")
        if pitl_addr:
            self._pitl_registry = self._w3.eth.contract(
                address=self._w3.to_checksum_address(pitl_addr),
                abi=PITL_SESSION_REGISTRY_ABI,
            )
        else:
            self._pitl_registry = None

        # Phase 28: PHG Credential soulbound registry (optional)
        cred_addr = getattr(cfg, "phg_credential_address", "")
        if cred_addr:
            self._phg_credential = self._w3.eth.contract(
                address=self._w3.to_checksum_address(cred_addr),
                abi=PHG_CREDENTIAL_ABI,
            )
        else:
            self._phg_credential = None

        # Phase 34: Federated Threat Registry (optional on-chain anchor)
        ftr_addr = getattr(cfg, "federated_threat_registry_address", "")
        if ftr_addr:
            self._federated_threat_registry = self._w3.eth.contract(
                address=self._w3.to_checksum_address(ftr_addr),
                abi=FEDERATED_THREAT_REGISTRY_ABI,
            )
        else:
            self._federated_threat_registry = None

        # Phase 55: ioID Device Identity Registry (optional)
        ioid_addr = getattr(cfg, "ioid_registry_address", "")
        if ioid_addr:
            self._ioid_registry = self._w3.eth.contract(
                address=self._w3.to_checksum_address(ioid_addr),
                abi=IOID_REGISTRY_ABI,
            )
        else:
            self._ioid_registry = None

        # Phase 62: PITLSessionRegistryV2 (Phase 62 C3 circuit — preferred over v1)
        pitl_v2_addr = getattr(cfg, "pitl_session_registry_v2_address", "")
        if pitl_v2_addr:
            self._pitl_registry_v2 = self._w3.eth.contract(
                address=self._w3.to_checksum_address(pitl_v2_addr),
                abi=PITL_SESSION_REGISTRY_ABI,
            )
        else:
            self._pitl_registry_v2 = None

        # Phase 56: Tournament Passport (optional)
        tp_addr = getattr(cfg, "tournament_passport_address", "")
        if tp_addr:
            self._tournament_passport = self._w3.eth.contract(
                address=self._w3.to_checksum_address(tp_addr),
                abi=TOURNAMENT_PASSPORT_ABI,
            )
        else:
            self._tournament_passport = None

        # Phase 68-B: ZKVerifier — local Groth16 pre-verification before chain submission
        vkey_path = getattr(cfg, "pitl_vkey_path", "")
        self._zk_verifier: ZKVerifier | None = ZKVerifier(vkey_path) if vkey_path else None
        self._zk_stats = {"accepted": 0, "rejected": 0, "skipped": 0, "errors": 0}
        log.info(
            "ZKVerifier: %s",
            f"enabled (vkey={vkey_path})" if self._zk_verifier else "disabled (no PITL_VKEY_PATH)",
        )

    @classmethod
    def generate_keystore(cls, output_path: str, password: str) -> str:
        """Encrypt the BRIDGE_PRIVATE_KEY env var to an Ethereum keystore JSON file.

        Usage (run once during setup):
            python -c "
            from vapi_bridge.chain import ChainClient
            addr = ChainClient.generate_keystore('/etc/vapi/bridge-keystore.json', 'your-password')
            print('Keystore written. Bridge address:', addr)
            print('Delete BRIDGE_PRIVATE_KEY from env after confirming keystore loads.')
            "

        Args:
            output_path: Where to write the keystore JSON file.
            password:    Encryption password (stored nowhere — you must remember this).

        Returns:
            The checksummed Ethereum address of the encrypted key.
        """
        import json as _json
        import os as _os
        private_key = _os.environ.get("BRIDGE_PRIVATE_KEY", "")
        if not private_key:
            raise ValueError("BRIDGE_PRIVATE_KEY env var is not set")
        account = Account.from_key(private_key)
        keystore = Account.encrypt(private_key, password)
        with open(output_path, "w") as f:
            _json.dump(keystore, f, indent=2)
        log.info("Keystore written to %s (address=%s)", output_path, account.address)
        return account.address

    @property
    def bridge_address(self) -> str:
        if self._account is None:
            return "0x0000000000000000000000000000000000000000"
        return self._account.address

    async def get_balance(self) -> float:
        """Get bridge wallet balance in IOTX."""
        if self._account is None:
            return 0.0
        wei = await self._w3.eth.get_balance(self._account.address)
        return float(self._w3.from_wei(wei, "ether"))

    async def _next_nonce(self) -> int:
        """Thread-safe nonce management."""
        if self._account is None:
            raise RuntimeError(
                "Bridge private key not set — cannot sign transactions (read-only mode). "
                "Add BRIDGE_PRIVATE_KEY to bridge/.env to enable on-chain writes."
            )
        async with self._nonce_lock:
            if self._nonce is None:
                self._nonce = await self._w3.eth.get_transaction_count(
                    self._account.address
                )
            else:
                self._nonce += 1
            return self._nonce

    async def _reset_nonce(self):
        """Reset nonce from chain (after error)."""
        async with self._nonce_lock:
            self._nonce = None

    async def _send_tx(
        self,
        tx_func,
        *args,
        value: int = 0,
        gas_buffer_multiplier: float = 1.2,
    ) -> str:
        """Build, sign, and send a transaction. Returns tx hash hex.

        gas_buffer_multiplier: scales the gas estimate.  Default 1.20 matches
        Phase 0 baseline used by all PoAC + adjudication paths.  Phase 237.5
        Path X established 1.25 for IoTeX-storage-heavy operations under
        elevated gas conditions; cedar_bundle_anchor passes 1.25 explicitly
        for the dual-anchor calls (Phase O1-FRR Stream D).
        """
        # Phase 237.5 Path C+ — global chain submission kill-switch.
        # When CHAIN_SUBMISSION_PAUSED=true in bridge/.env, every transaction
        # path that goes through this chokepoint short-circuits. Gates the
        # batcher's PoAC submissions, retry loop, and most chain.* methods
        # that wrap _send_tx. The high-frequency DualShock per-PITL-proof
        # path is gated separately at dualshock_integration.py:2324-2335
        # (it bypasses _send_tx via direct chain.* method calls).
        if getattr(self._cfg, "chain_submission_paused", False):
            log.warning(
                "_send_tx: chain_submission_paused=true — transaction "
                "suppressed (CHAIN_SUBMISSION_PAUSED kill-switch active)"
            )
            raise RuntimeError(
                "chain_submission_paused: on-chain transactions are paused "
                "via CHAIN_SUBMISSION_PAUSED=true in bridge/.env"
            )
        if self._account is None:
            raise RuntimeError(
                "Bridge private key not set — cannot sign transactions (read-only mode)."
            )
        nonce = await self._next_nonce()
        gas_price = await self._w3.eth.gas_price

        tx_overrides: dict = {
            "from": self._account.address,
            "nonce": nonce,
            "gasPrice": gas_price,
            "chainId": self._cfg.chain_id,
        }
        if value > 0:
            tx_overrides["value"] = value

        tx = await tx_func(*args).build_transaction(tx_overrides)

        # Estimate gas with caller-supplied buffer (default 1.20)
        try:
            gas_estimate = await self._w3.eth.estimate_gas(tx)
            buf = float(gas_buffer_multiplier) if gas_buffer_multiplier else 1.2
            tx["gas"] = int(gas_estimate * buf)
        except ContractLogicError as e:
            await self._reset_nonce()
            raise RuntimeError(f"Contract revert: {e}") from e

        signed = self._account.sign_transaction(tx)
        try:
            tx_hash = await self._w3.eth.send_raw_transaction(signed.raw_transaction)
        except Exception:
            await self._reset_nonce()  # Phase 54: reset stale nonce on send failure
            raise
        return tx_hash.hex()

    async def wait_for_receipt(self, tx_hash: str, timeout: int = 60) -> dict:
        """Wait for transaction receipt."""
        tx_bytes = bytes.fromhex(tx_hash.removeprefix("0x"))
        receipt = await self._w3.eth.wait_for_transaction_receipt(
            tx_bytes, timeout=timeout
        )
        return dict(receipt)

    # --- PoACVerifier ---

    async def verify_single(self, device_id: bytes, record: PoACRecord) -> str:
        """Submit a single PoAC record for verification. Returns tx hash."""
        raw_body = _record_raw_body(record)
        tx_hash = await self._send_tx(
            self._verifier.functions.verifyPoAC,
            device_id,
            raw_body,
            record.signature,
        )
        log.info(
            "Submitted verifyPoAC: device=%s counter=%d tx=%s",
            device_id.hex()[:16], record.monotonic_ctr, tx_hash[:16],
        )
        return tx_hash

    async def verify_batch(
        self,
        device_ids: Sequence[bytes],
        records: Sequence[PoACRecord],
    ) -> str:
        """Submit a batch of PoAC records for verification. Returns tx hash."""
        raw_bodies = [_record_raw_body(r) for r in records]
        signatures = [r.signature for r in records]
        tx_hash = await self._send_tx(
            self._verifier.functions.verifyPoACBatch,
            list(device_ids),
            raw_bodies,
            signatures,
        )
        log.info(
            "Submitted verifyPoACBatch: %d records, tx=%s",
            len(records), tx_hash[:16],
        )
        return tx_hash

    async def is_record_verified(self, record_hash: bytes) -> bool:
        return await self._verifier.functions.isRecordVerified(record_hash).call()

    async def get_verified_count(self, device_id: bytes) -> int:
        return await self._verifier.functions.getVerifiedCount(device_id).call()

    # --- BountyMarket ---

    async def submit_evidence(
        self,
        bounty_id: int,
        device_id: bytes,
        record: PoACRecord,
    ) -> str:
        """Submit bounty evidence for a verified record. Returns tx hash."""
        if not self._bounty_market:
            raise RuntimeError("BountyMarket address not configured")
        tx_hash = await self._send_tx(
            self._bounty_market.functions.submitEvidence,
            bounty_id,
            device_id,
            record.record_hash,
            record.lat_fixed,
            record.lon_fixed,
            record.timestamp_ms,
        )
        log.info(
            "Submitted evidence: bounty=%d device=%s tx=%s",
            bounty_id, device_id.hex()[:16], tx_hash[:16],
        )
        return tx_hash

    async def get_bounty(self, bounty_id: int) -> dict | None:
        if not self._bounty_market:
            return None
        try:
            result = await self._bounty_market.functions.getBounty(bounty_id).call()
            return {
                "bounty_id": result[0],
                "creator": result[1],
                "reward_wei": result[2],
                "status": result[15],
            }
        except ContractLogicError:
            return None

    # --- DeviceRegistry ---

    async def is_device_active(self, device_id: bytes) -> bool:
        if not self._registry:
            return True  # Assume active if registry not configured
        return await self._registry.functions.isDeviceActive(device_id).call()

    async def get_device_pubkey(self, device_id: bytes) -> bytes | None:
        """Fetch device public key from on-chain registry."""
        if not self._registry:
            return None
        try:
            pubkey = await self._registry.functions.getDevicePubkey(device_id).call()
            return bytes(pubkey) if pubkey else None
        except ContractLogicError:
            return None

    async def get_reputation(self, device_id: bytes) -> int:
        if not self._registry:
            return 0
        return await self._registry.functions.getReputationScore(device_id).call()

    async def register_device_tiered(
        self, pubkey_bytes: bytes, tier: str = "Standard",
        attestation_proof: bytes = b"",
        certificate_hash: bytes = b"",    # Phase 9: optional 32-byte cert hash
    ) -> str:
        """Register device with specific tier. Returns tx hash."""
        if not self._registry:
            raise RuntimeError("DeviceRegistry address not configured")
        tier_int = TIER_VALUES.get(tier)
        if tier_int is None:
            raise ValueError(f"Unknown tier: {tier!r}")
        tier_cfg = await self._registry.functions.tierConfigs(tier_int).call()
        deposit = tier_cfg[0]  # depositWei
        if self._account is None:
            raise RuntimeError("Bridge private key not set — cannot register device (read-only mode).")
        balance_wei = await self._w3.eth.get_balance(self._account.address)
        if balance_wei < deposit:
            raise RuntimeError(
                f"Insufficient balance for {tier} registration: "
                f"have {balance_wei} wei, need {deposit} wei"
            )
        if tier == "Attested":
            if len(attestation_proof) != 64:
                raise ValueError("Attested tier requires 64-byte attestation proof")
            if certificate_hash and len(certificate_hash) == 32:
                # Phase 9: call registerAttestedWithCert
                tx_hash = await self._send_tx(
                    self._registry.functions.registerAttestedWithCert,
                    pubkey_bytes, attestation_proof, certificate_hash,
                    value=deposit,
                )
            else:
                # Backward compat: 2-arg registerAttested
                tx_hash = await self._send_tx(
                    self._registry.functions.registerAttested,
                    pubkey_bytes, attestation_proof, value=deposit,
                )
        else:
            tx_hash = await self._send_tx(
                self._registry.functions.registerTieredDevice,
                pubkey_bytes, tier_int, value=deposit,
            )
        log.info(
            "Device registered: tier=%s pubkey=%s... deposit=%d wei tx=%s...",
            tier, pubkey_bytes.hex()[:16], deposit, tx_hash[:16],
        )
        return tx_hash

    async def register_device(self, pubkey_bytes: bytes) -> str:
        """Backward-compat wrapper: Standard tier registration."""
        return await self.register_device_tiered(pubkey_bytes, tier="Standard")

    async def ensure_device_registered_tiered(
        self, device_id: bytes, pubkey_bytes: bytes,
        tier: str = "Standard", attestation_proof: bytes = b"",
        certificate_hash: bytes = b"",    # Phase 9: optional 32-byte cert hash
    ) -> tuple[bool, "str | None"]:
        """
        Idempotent tiered registration: checks isDeviceActive first, then
        registers at the specified tier only if needed.
        Returns (success, tx_hash_or_None). Non-fatal.
        """
        if not self._registry:
            return False, None
        try:
            if await self._registry.functions.isDeviceActive(device_id).call():
                log.debug("Device already active: %s...", device_id.hex()[:16])
                return True, None
            tx_hash = await self.register_device_tiered(
                pubkey_bytes, tier, attestation_proof, certificate_hash
            )
            return True, tx_hash
        except Exception as exc:
            err_str = str(exc).lower()
            if any(p in err_str for p in ("insufficient funds", "out of gas", "f46a06ea",
                                           "execution reverted", "transaction reverted")):
                log.warning("ensure_device_registered_tiered: permanent gas/revert error (non-fatal): %s", exc)
            else:
                log.warning("ensure_device_registered_tiered failed (non-fatal, may retry): %s", exc)
            return False, None

    async def ensure_device_registered(
        self, device_id: bytes, pubkey_bytes: bytes
    ) -> tuple[bool, "str | None"]:
        """Backward-compat wrapper: Standard tier idempotent registration."""
        return await self.ensure_device_registered_tiered(
            device_id, pubkey_bytes, "Standard"
        )

    # --- ProgressAttestation ---

    async def attest_progress(
        self,
        device_id: bytes,
        baseline_hash: bytes,
        current_hash: bytes,
        metric_type: int,
        improvement_bps: int,
    ) -> str:
        """
        Submit a ProgressAttestation for measurable skill improvement.

        Args:
            device_id:       32-byte device ID (keccak256 of pubkey).
            baseline_hash:   SHA-256 of the pre-coaching PoAC body.
            current_hash:    SHA-256 of the post-coaching PoAC body.
            metric_type:     MetricType enum value (0=REACTION_TIME, 1=ACCURACY,
                             2=CONSISTENCY, 3=COMBO_EXECUTION).
            improvement_bps: Improvement in basis points (100 = 1%). Must be > 0.

        Returns:
            Transaction hash hex string.
        """
        if not self._progress:
            raise RuntimeError("PROGRESS_ATTESTATION_ADDRESS not configured")
        tx_hash = await self._send_tx(
            self._progress.functions.attestProgress,
            device_id,
            baseline_hash,
            current_hash,
            metric_type,
            improvement_bps,
        )
        log.info(
            "ProgressAttestation: device=%s metric=%d bps=%d tx=%s...",
            device_id.hex()[:16], metric_type, improvement_bps, tx_hash[:16],
        )
        return tx_hash

    # --- TeamProofAggregator ---

    async def create_team(self, team_id: bytes, device_ids: list[bytes]) -> str:
        """Register a team on-chain. Returns tx hash."""
        if not self._team_agg:
            raise RuntimeError("TEAM_AGGREGATOR_ADDRESS not configured")
        tx_hash = await self._send_tx(
            self._team_agg.functions.createTeam,
            team_id,
            device_ids,
        )
        log.info(
            "Team created: id=%s members=%d tx=%s...",
            team_id.hex()[:16], len(device_ids), tx_hash[:16],
        )
        return tx_hash

    async def submit_team_proof(
        self,
        team_id: bytes,
        record_hashes: list[bytes],
        merkle_root: bytes,
    ) -> str:
        """Submit aggregated team proof Merkle root. Returns tx hash."""
        if not self._team_agg:
            raise RuntimeError("TEAM_AGGREGATOR_ADDRESS not configured")
        tx_hash = await self._send_tx(
            self._team_agg.functions.submitTeamProof,
            team_id,
            record_hashes,
            merkle_root,
        )
        log.info(
            "TeamProof submitted: team=%s members=%d root=%s... tx=%s...",
            team_id.hex()[:16], len(record_hashes),
            merkle_root.hex()[:16], tx_hash[:16],
        )
        return tx_hash

    async def team_exists(self, team_id: bytes) -> bool:
        if not self._team_agg:
            return False
        return await self._team_agg.functions.teamExists(team_id).call()

    # --- Phase 12: Schema-aware verification + manufacturer V2 methods ---

    async def verify_poac(
        self,
        device_id: bytes,
        raw_body: bytes,
        signature: bytes,
        schema_version: int = 0,
    ) -> str:
        """Verify a single PoAC record on-chain.

        If schema_version > 0, calls verifyPoACWithSchema() so the record is
        tagged with its sensor commitment schema (1=v1 environmental, 2=v2 kinematic).
        If schema_version == 0 (default), calls the legacy verifyPoAC().

        Returns tx hash hex string.
        """
        if schema_version > 0:
            tx_hash = await self._send_tx(
                self._verifier.functions.verifyPoACWithSchema,
                device_id, raw_body, signature, schema_version,
            )
        else:
            tx_hash = await self._send_tx(
                self._verifier.functions.verifyPoAC,
                device_id, raw_body, signature,
            )
        log.info(
            "verify_poac: device=%s schema=%d tx=%s",
            device_id.hex()[:16], schema_version, tx_hash[:16],
        )
        return tx_hash

    async def register_device_attested_v2(
        self,
        pubkey: bytes,
        attestation_proof: bytes,
        manufacturer_addr: str,
    ) -> str:
        """Register an Attested-tier device via the V2 P256-verified path.

        Requires the manufacturer's P256 key to be registered via setManufacturerKey.
        When attestationEnforced=true, the signature is cryptographically verified
        against the manufacturer key via IoTeX precompile 0x0100.

        Returns tx hash hex string.
        """
        if not self._registry:
            raise RuntimeError("DeviceRegistry address not configured")
        tier_cfg = await self._registry.functions.tierConfigs(2).call()  # 2 = Attested
        deposit = tier_cfg[0]
        tx_hash = await self._send_tx(
            self._registry.functions.registerAttestedV2,
            pubkey,
            attestation_proof,
            self._w3.to_checksum_address(manufacturer_addr),
            value=deposit,
        )
        log.info(
            "registerAttestedV2: pubkey=%s manufacturer=%s tx=%s",
            pubkey.hex()[:16], manufacturer_addr[:16], tx_hash[:16],
        )
        return tx_hash

    async def get_manufacturer_key(self, manufacturer_addr: str) -> dict:
        """Fetch manufacturer P256 key from on-chain registry.

        Returns dict with keys: pubkeyX (bytes32), pubkeyY (bytes32), active (bool), name (str).
        """
        if not self._registry:
            raise RuntimeError("DeviceRegistry address not configured")
        result = await self._registry.functions.getManufacturerKey(
            self._w3.to_checksum_address(manufacturer_addr)
        ).call()
        return {
            "pubkeyX": result[0],
            "pubkeyY": result[1],
            "active":  result[2],
            "name":    result[3],
        }

    def is_manufacturer_revoked(self, manufacturer_addr: str) -> bool:
        """Check if a manufacturer address is in the local revocation cache.

        The cache is populated by watch_manufacturer_revocations(). Returns False
        if the address has never been seen as revoked (or the listener isn't running).
        """
        return manufacturer_addr.lower() in self._revoked_manufacturers

    async def watch_manufacturer_revocations(self, poll_interval: float = 30.0) -> None:
        """Background coroutine: poll ManufacturerKeyRevoked events and cache revocations.

        Intended to run as a long-lived background task:
            asyncio.create_task(chain.watch_manufacturer_revocations())

        Updates self._revoked_manufacturers set so is_manufacturer_revoked() reflects
        on-chain revocations without requiring per-call RPC queries.
        """
        if not self._registry:
            log.warning("watch_manufacturer_revocations: registry not configured")
            return
        try:
            event_filter = self._registry.events.ManufacturerKeyRevoked
        except Exception as exc:
            log.warning("watch_manufacturer_revocations: event unavailable (%s)", exc)
            return

        last_block = await self._w3.eth.block_number
        log.info("watch_manufacturer_revocations: polling every %.0fs from block %d", poll_interval, last_block)

        while True:
            await asyncio.sleep(poll_interval)
            try:
                current_block = await self._w3.eth.block_number
                if current_block <= last_block:
                    continue
                logs = await event_filter().get_logs(
                    from_block=last_block + 1, to_block=current_block
                )
                for entry in logs:
                    addr = entry["args"]["manufacturer"].lower()
                    self._revoked_manufacturers.add(addr)
                    log.info("ManufacturerKeyRevoked: %s cached as revoked", addr)
                last_block = current_block
            except Exception as exc:
                log.warning("watch_manufacturer_revocations poll error: %s", exc)

    # --- Phase 22: PHG Registry ---

    async def commit_phg_checkpoint(
        self,
        device_id: str,
        score_delta: int,
        count: int,
        biometric_hash: bytes,
    ) -> str:
        """Commit a PHG checkpoint to the on-chain registry. Returns tx hash.

        Called by the batcher after every N verified NOMINAL records.
        No-op (returns empty string) when PHG_REGISTRY_ADDRESS is not configured.
        """
        if not self._phg_registry:
            log.debug("commit_phg_checkpoint: PHG_REGISTRY_ADDRESS not configured, skipping")
            return ""
        device_id_bytes = bytes.fromhex(device_id)
        bio_hash_bytes32 = biometric_hash[:32].ljust(32, b"\x00") if biometric_hash else bytes(32)
        tx_hash = await self._send_tx(
            self._phg_registry.functions.commitCheckpoint,
            device_id_bytes,
            score_delta,
            count,
            bio_hash_bytes32,
        )
        log.info(
            "PHGCheckpoint committed: device=%s score_delta=%d count=%d tx=%s",
            device_id[:16], score_delta, count, tx_hash[:16],
        )
        return tx_hash

    async def get_phg_score(self, device_id: str) -> int:
        """Return the on-chain cumulative PHG score for a device. Returns 0 if unconfigured."""
        if not self._phg_registry:
            return 0
        return await self._phg_registry.functions.cumulativeScore(
            bytes.fromhex(device_id)
        ).call()

    async def get_phg_checkpoint_events(
        self, from_block: int, to_block: int
    ) -> list[dict]:
        """Fetch PHGCheckpointCommitted events from the PHGRegistry contract.

        Returns list of event dicts with keys: transactionHash, deviceId, cumulativeScore.
        Returns empty list if PHG_REGISTRY_ADDRESS is not configured or on error.
        """
        if not self._phg_registry:
            return []
        try:
            event_filter = self._phg_registry.events.PHGCheckpointCommitted
            events = await event_filter.get_logs(
                from_block=from_block, to_block=to_block
            )
            result = []
            for evt in events:
                result.append({
                    "transactionHash": evt["transactionHash"],
                    "deviceId":        evt["args"]["deviceId"].hex(),
                    "cumulativeScore": evt["args"]["cumulativeScore"],
                })
            return result
        except Exception as exc:
            log.warning("get_phg_checkpoint_events error: %s", exc)
            return []

    def get_phg_checkpoint_events_sync(
        self, from_block: int, to_block: int
    ) -> list[dict]:
        """Phase 235.x-STABILITY-9 stage 14 2026-05-18 — sync companion of
        get_phg_checkpoint_events for asyncio.to_thread offload via
        ChainReadGovernor.run_read(sync_fn=...).

        Stage 12 fixed block_number reads via sync_w3 + to_thread but
        left event-filter get_logs reads on the async (AsyncHTTPProvider)
        path. Stage 13 observation showed 15.86s peak STARVATION
        clustering at 10s = governor wait_for timeout + ~5.86s socket-
        cancellation residual = exact Windows ProactorEventLoop signature.
        This sync version uses self._sync_w3 to route the get_logs call
        through a blocking socket on a worker thread, avoiding the
        ProactorEventLoop cancellation gap.

        Returns same list-of-dicts contract as the async version.
        Fail-open on missing sync_w3 / missing _phg_registry / RPC error.
        """
        if self._sync_w3 is None:
            log.debug(
                "get_phg_checkpoint_events_sync: sync_w3 unavailable; "
                "returning empty (caller should fall back to async path)"
            )
            return []
        if not self._phg_registry:
            return []
        try:
            addr = self._sync_w3.to_checksum_address(self._cfg.phg_registry_address)
            sync_contract = self._sync_w3.eth.contract(
                address=addr,
                abi=PHG_REGISTRY_ABI,
            )
            event_filter = sync_contract.events.PHGCheckpointCommitted
            events = event_filter.get_logs(
                from_block=from_block, to_block=to_block
            )
            result = []
            for evt in events:
                result.append({
                    "transactionHash": evt["transactionHash"],
                    "deviceId":        evt["args"]["deviceId"].hex(),
                    "cumulativeScore": evt["args"]["cumulativeScore"],
                })
            return result
        except Exception as exc:  # noqa: BLE001 — fail-open
            log.warning("get_phg_checkpoint_events_sync error: %s", exc)
            return []

    # --- Phase B item ② P4b: VAPIPoEPRegistry read (resolves #8 W-1) ---

    def get_registered_composite_pubkey(self, device_id):
        """② P4b — SYNC, fail-open read of a device's registered composite pubkey blob.

        Returns the integrity-verified ① ``encode_pubkey`` blob (two-RPC pattern: event-log blob
        + on-chain hash view call, verified via poep_registry_handler.resolve_composite_pubkey), or
        None. **Fail-OPEN** when POEP_REGISTRY_ADDRESS is unset (v1; registry not deployed) or
        sync_w3 is unavailable — bridge readiness must not depend on the deploy (CONSENT precedent).
        **Fail-CLOSED** on integrity mismatch (handled inside resolve_composite_pubkey). The
        deployed read path is validated at the wallet-gated E2E.
        """
        from .consent_categories import device_id_to_bytes32
        from .poep_registry_handler import resolve_composite_pubkey

        addr_str = getattr(self._cfg, "poep_registry_address", "") or ""
        if not addr_str:
            return None  # fail-open: registry not deployed (v1 wallet-free)
        if self._sync_w3 is None:
            return None
        try:
            b32 = device_id_to_bytes32(device_id)
            addr = self._sync_w3.to_checksum_address(addr_str)
            contract = self._sync_w3.eth.contract(address=addr, abi=_VAPI_POEP_REGISTRY_ABI)
            # latest DeviceRegistered for this (indexed) deviceId → registering gamer + event blob.
            # from_block = registry deploy block (NOT 0): IoTeX's eth_getLogs caps wide ranges and
            # returns EMPTY for 0→~44M blocks, which would silently make this provider return None
            # (the dormant-blind closure would skip renewals for correctly-registered devices). The
            # deploy-block floor keeps the scan inside the RPC's range. Phase 3 (Path B) fix.
            _from_block = int(getattr(self._cfg, "poep_registry_deploy_block", 0) or 0)
            evs = contract.events.DeviceRegistered.get_logs(
                from_block=_from_block, argument_filters={"deviceId": b32}
            )
            if not evs:
                return None
            ev = evs[-1]
            gamer = ev["args"]["gamer"]
            event_blob = bytes(ev["args"]["compositePubkeyBlob"])

            class _ChainReader:  # two-call integrity surface over the deployed contract
                def is_registration_valid(self, g, d):
                    return bool(contract.functions.isRegistrationValid(g, d).call())
                def get_composite_pubkey_hash(self, g, d):
                    h = bytes(contract.functions.getCompositePubkeyHash(g, d).call())
                    return h if h and h != b"\x00" * 32 else None
                def get_registration_blob(self, g, d):
                    return event_blob

            return resolve_composite_pubkey(_ChainReader(), gamer, b32)
        except Exception as exc:  # noqa: BLE001 — fail-open on RPC/contract error
            log.warning("get_registered_composite_pubkey error (fail-open): %s", exc)
            return None

    # --- Path A Arc 1 Commit 2: VAPIManufacturerDeviceRegistry reads ---
    #
    # Four SYNC view-call methods + a 60s TTL cache. Fail-OPEN posture: when
    # MANUFACTURER_DEVICE_REGISTRY_ADDRESS is unset (Arc 1 pre-deploy) OR sync_w3
    # is unavailable OR the RPC call raises, return the dormant default (0 for
    # path/tier, False for booleans). Bridge readiness MUST NOT depend on the
    # registry deploy — same precedent as get_registered_composite_pubkey and
    # is_consent_valid. UI honesty is preserved upstream: GET /player/session-
    # status surfaces signing_path=null/"B" honestly when this returns 0/False.

    _VMDR_CACHE_TTL_S = 60.0

    def _vmdr_cache(self):
        # Lazy-init per-instance cache: {device_id_hex: (ts, {sig, tier, isA, isAct})}
        if not hasattr(self, "_vmdr_view_cache"):
            self._vmdr_view_cache = {}
        return self._vmdr_view_cache

    def _vmdr_read_views(self, device_id):
        """Read all 4 views in one shot + cache the bundle for 60s. Returns
        (signing_path:int, proof_tier:int, is_path_a:bool, is_active:bool). On
        any fault returns the dormant default (0, 0, False, False)."""
        import time as _t
        from .consent_categories import device_id_to_bytes32

        cache = self._vmdr_cache()
        now = _t.time()
        cached = cache.get(device_id)
        if cached and (now - cached[0] < self._VMDR_CACHE_TTL_S):
            return cached[1]

        dormant = (0, 0, False, False)

        addr_str = getattr(self._cfg, "manufacturer_device_registry_address", "") or ""
        if not addr_str or self._sync_w3 is None:
            cache[device_id] = (now, dormant)  # cache the dormant answer too — RPC isn't free
            return dormant

        try:
            b32 = device_id_to_bytes32(device_id)
            addr = self._sync_w3.to_checksum_address(addr_str)
            contract = self._sync_w3.eth.contract(
                address=addr, abi=_VAPI_MANUFACTURER_DEVICE_REGISTRY_ABI,
            )
            sig  = int(contract.functions.getSigningPath(b32).call())
            tier = int(contract.functions.getProofTier(b32).call())
            isA  = bool(contract.functions.isPathA(b32).call())
            isAct = bool(contract.functions.isActive(b32).call())
            bundle = (sig, tier, isA, isAct)
            cache[device_id] = (now, bundle)
            return bundle
        except Exception as exc:  # noqa: BLE001 — fail-open
            log.warning("VMDR view read error (fail-open dormant): %s", exc)
            cache[device_id] = (now, dormant)
            return dormant

    def get_device_signing_path(self, device_id) -> int:
        """Returns 1 (Path A silicon-rooted) / 2 (Path B host-held) / 0 (unregistered
        or registry unavailable). Fail-open dormant on any fault."""
        return self._vmdr_read_views(device_id)[0]

    def get_proof_tier(self, device_id) -> int:
        """Returns 1 (FULL — DualSense Edge CFI-ZCP1) / 2 (STANDARD — CFI-ZCT1) /
        3 (BASIC — third-party) / 0 (unregistered or registry unavailable)."""
        return self._vmdr_read_views(device_id)[1]

    def is_path_a(self, device_id) -> bool:
        """True iff registered + active + signingPath == SIGNING_PATH_A. False on
        any fault (fail-open dormant — honest default, not a false-positive Path A)."""
        return self._vmdr_read_views(device_id)[2]

    def is_active_in_mfg_registry(self, device_id) -> bool:
        """True iff registered + active in the manufacturer registry (regardless of
        signing path). Distinct from VHP / PoEP activity — this is hardware-birth
        activity. Named with _in_mfg_registry suffix to avoid clash with the future
        protocol-wide is_active concept."""
        return self._vmdr_read_views(device_id)[3]

    # --- Data Economy Arc 1: VAPIBuyerRegistry reads ---
    #
    # Two SYNC view-call methods + a 60s TTL cache. Fail-OPEN posture identical
    # to the VMDR block above: when buyer_registry_address is unset OR sync_w3 is
    # unavailable OR the RPC call raises, return the dormant default (False for
    # validity, 0 for category). The bridge only READS this registry — credential
    # issuance/revocation is the Curator's on-chain write via the bridge wallet
    # (curator_attestation module, Arc 1 Commit 2). buyerDID is normalised through
    # the project's device_id_to_bytes32 (generic bytes32 normaliser: 0x-hex used
    # directly, arbitrary DID string SHA-256'd) so the read path and the future
    # write path agree byte-for-byte on the on-chain key.

    _BUYER_CACHE_TTL_S = 60.0

    def _buyer_cache(self):
        # Lazy-init per-instance cache: {cache_key: (ts, value)}
        if not hasattr(self, "_buyer_view_cache"):
            self._buyer_view_cache = {}
        return self._buyer_view_cache

    def _buyer_contract(self):
        """Return (sync) VAPIBuyerRegistry contract handle, or None when the
        registry address is unset or sync_w3 is unavailable (fail-open)."""
        addr_str = getattr(self._cfg, "buyer_registry_address", "") or ""
        if not addr_str or self._sync_w3 is None:
            return None
        addr = self._sync_w3.to_checksum_address(addr_str)
        return self._sync_w3.eth.contract(address=addr, abi=_VAPI_BUYER_REGISTRY_ABI)

    def is_valid_buyer_credential(self, buyer_did: str, category_id: int) -> bool:
        """True iff the buyer holds a registered + active + unexpired credential
        for category_id (authoritative on-chain isValidCredential check). Fail-open
        False on any fault (registry unset / RPC error) — an unavailable registry
        must never grant a buyer access it does not hold on-chain."""
        import time as _t
        from .consent_categories import device_id_to_bytes32

        cache = self._buyer_cache()
        now = _t.time()
        key = ("valid", str(buyer_did), int(category_id))
        cached = cache.get(key)
        if cached and (now - cached[0] < self._BUYER_CACHE_TTL_S):
            return cached[1]

        contract = self._buyer_contract()
        if contract is None:
            cache[key] = (now, False)
            return False
        try:
            b32 = device_id_to_bytes32(buyer_did)
            valid = bool(contract.functions.isValidCredential(b32, int(category_id)).call())
            cache[key] = (now, valid)
            return valid
        except Exception as exc:  # noqa: BLE001 — fail-open False
            log.warning("is_valid_buyer_credential error (fail-open False): %s", exc)
            cache[key] = (now, False)
            return False

    def get_buyer_category(self, buyer_did: str) -> int:
        """Return the buyer's attested category id (1=ACADEMIC .. 4=BRAND), or 0
        when unregistered / registry unavailable. NOTE: getCategory returns the
        stored category regardless of active/expiry — use is_valid_buyer_credential
        for an authorization decision; this is for display/lookup only."""
        import time as _t
        from .consent_categories import device_id_to_bytes32

        cache = self._buyer_cache()
        now = _t.time()
        key = ("cat", str(buyer_did))
        cached = cache.get(key)
        if cached and (now - cached[0] < self._BUYER_CACHE_TTL_S):
            return cached[1]

        contract = self._buyer_contract()
        if contract is None:
            cache[key] = (now, 0)
            return 0
        try:
            b32 = device_id_to_bytes32(buyer_did)
            cat = int(contract.functions.getCategory(b32).call())
            cache[key] = (now, cat)
            return cat
        except Exception as exc:  # noqa: BLE001 — fail-open 0
            log.warning("get_buyer_category error (fail-open 0): %s", exc)
            cache[key] = (now, 0)
            return 0

    # --- Data Economy Arc 2: VAPIBuyerCategoryVerifier (ZK Groth16) ---

    def _buyer_category_verifier_contract(self):
        """Return (sync) VAPIBuyerCategoryVerifier contract handle, or None when
        the verifier address is unset or sync_w3 is unavailable (fail-open).
        Address is empty until the operator deploys the verifier on-chain."""
        addr_str = getattr(self._cfg, "buyer_category_verifier_address", "") or ""
        if not addr_str or self._sync_w3 is None:
            return None
        addr = self._sync_w3.to_checksum_address(addr_str)
        return self._sync_w3.eth.contract(
            address=addr, abi=_VAPI_BUYER_CATEGORY_VERIFIER_ABI
        )

    def verify_buyer_category_proof_onchain(self, pA, pB, pC, pub_signals) -> bool:
        """staticcall VAPIBuyerCategoryVerifier.verifyProof. Fail-open False when
        the verifier is undeployed (address unset) or the RPC raises — an
        unavailable verifier must never validate a proof it cannot check."""
        contract = self._buyer_category_verifier_contract()
        if contract is None:
            return False
        try:
            return bool(
                contract.functions.verifyProof(
                    list(pA), [list(pB[0]), list(pB[1])], list(pC), list(pub_signals)
                ).call()
            )
        except Exception as exc:  # noqa: BLE001 — fail-open False
            log.warning("verify_buyer_category_proof_onchain error (fail-open False): %s", exc)
            return False

    # --- Phase 23: Identity Continuity Registry ---

    async def attest_continuity(
        self,
        old_device_id: str,
        new_device_id: str,
        biometric_proof_hash: bytes,
    ) -> str:
        """Attest that new_device_id is the biometric continuation of old_device_id.

        Transfers the old device's PHG score to the new device on-chain.
        No-op (returns empty string) when IDENTITY_REGISTRY_ADDRESS is not configured.

        Args:
            old_device_id:        Source device identifier (hex string, 32 bytes).
            new_device_id:        Destination device identifier (hex string, 32 bytes).
            biometric_proof_hash: 32-byte SHA-256 proof of fingerprint proximity.

        Returns:
            Transaction hash hex string, or "" if registry not configured.
        """
        if not self._identity_registry:
            log.debug("attest_continuity: IDENTITY_REGISTRY_ADDRESS not configured, skipping")
            return ""
        old_bytes = bytes.fromhex(old_device_id)
        new_bytes = bytes.fromhex(new_device_id)
        proof_bytes32 = biometric_proof_hash[:32].ljust(32, b"\x00")
        tx_hash = await self._send_tx(
            self._identity_registry.functions.attestContinuity,
            old_bytes,
            new_bytes,
            proof_bytes32,
        )
        log.info(
            "ContinuityAttested: old=%s new=%s tx=%s",
            old_device_id[:16], new_device_id[:16], tx_hash[:16],
        )
        return tx_hash

    async def is_continuation_of(self, new_device_id: str, old_device_id: str) -> bool:
        """Return True if new_device_id inherited its score from old_device_id."""
        if not self._identity_registry:
            return False
        return await self._identity_registry.functions.isContinuationOf(
            bytes.fromhex(new_device_id),
            bytes.fromhex(old_device_id),
        ).call()

    async def get_canonical_root(self, device_id: str) -> str:
        """Walk the continuity chain and return the canonical root device ID (hex)."""
        if not self._identity_registry:
            return device_id
        root_bytes = await self._identity_registry.functions.getCanonicalRoot(
            bytes.fromhex(device_id)
        ).call()
        return root_bytes.hex()

    # --- Phase 26: PITL Session Registry ---

    async def submit_pitl_proof(
        self,
        device_id: str,
        proof_bytes: bytes,
        feature_commitment: int,
        humanity_prob_int: int,
        inference_code: int,
        nullifier_hash: int,
        epoch: int,
    ) -> str:
        """Submit a PITL ZK session proof to PITLSessionRegistry.

        Submits to PITLSessionRegistryV2 (Phase 62, PITL_SESSION_REGISTRY_V2_ADDRESS) if
        configured; falls back to v1 (PITL_SESSION_REGISTRY_ADDRESS). No-op if neither is set.

        Args:
            device_id:          64-char hex device identifier.
            proof_bytes:        256-byte Groth16 proof wire format.
            feature_commitment: Poseidon(8)(scaledFeatures[0..6], inferenceCodeFromBody) — Phase 62.
            humanity_prob_int:  l5_humanity × 1000 ∈ [0, 1000].
            inference_code:     8-bit VAPI inference result (e.g. 0x00 CLEAN, 0x30 L4 anomaly).
                                Circuit C2 enforces this ∉ [40, 42] — a proof with a hard
                                cheat code is ungenerable, so submission would never reach here.
            nullifier_hash:     Poseidon(deviceIdHash, epoch) as integer.
            epoch:              Block epoch (block.number / EPOCH_BLOCKS).

        Returns:
            Transaction hash hex string, or "" if registry not configured.
        """
        # Phase 62: prefer v2 (Phase 62 C3 circuit) if configured; fallback to v1
        registry = self._pitl_registry_v2 or self._pitl_registry
        registry_ver = "v2" if self._pitl_registry_v2 else "v1"
        if not registry:
            log.debug("submit_pitl_proof: no PITL registry configured, skipping")
            return ""

        # Phase 68-B: local ZK pre-verification — reject invalid proofs before gas spend
        if getattr(self, "_zk_verifier", None) is not None:
            proof_dict = {
                "pi_a": list(proof_bytes[:96]),
                "pi_b": list(proof_bytes[96:224]),
                "pi_c": list(proof_bytes[224:]),
                "protocol": "groth16",
                "curve": "bn128",
            }
            public_signals = [
                str(feature_commitment),
                str(humanity_prob_int),
                str(inference_code),
                str(nullifier_hash),
                str(epoch),
            ]
            _zk_stats = getattr(self, "_zk_stats", {"accepted": 0, "rejected": 0, "errors": 0})
            try:
                valid = await self._zk_verifier.verify_proof(proof_dict, public_signals)
            except Exception as exc:
                log.warning("ZKVerifier: unexpected error — skipping pre-verify: %s", exc)
                _zk_stats["errors"] += 1
                valid = True  # fail-open: never silently drop proofs on verifier error
            if valid:
                _zk_stats["accepted"] += 1
            else:
                _zk_stats["rejected"] += 1
                log.warning(
                    "ZKVerifier: rejected proof for device=%s — not submitted", device_id[:16]
                )
                raise ValueError(
                    f"ZK proof invalid: local pre-verification failed for device {device_id[:16]}"
                )
        else:
            getattr(self, "_zk_stats", {"skipped": 0})["skipped"] += 1

        device_id_bytes32 = bytes.fromhex(device_id)
        tx_hash = await self._send_tx(
            registry.functions.submitPITLProof,
            device_id_bytes32,
            proof_bytes,
            feature_commitment,
            humanity_prob_int,
            inference_code,
            nullifier_hash,
            epoch,
        )
        log.info(
            "PITLSessionProof submitted (%s): device=%s hp=%d inference=0x%02x tx=%s",
            registry_ver, device_id[:16], humanity_prob_int, inference_code, tx_hash[:16],
        )
        return tx_hash

    async def mint_phg_credential(
        self,
        device_id: str,
        nullifier_hash: str,
        feature_commitment: str,
        humanity_prob_int: int,
    ) -> str:
        """Mint a soulbound PHGCredential on-chain for the device.

        No-op (returns empty string) when PHG_CREDENTIAL_ADDRESS is not configured.

        Args:
            device_id:          Hex device identifier (40–64 chars, no 0x prefix).
            nullifier_hash:     Hex nullifier from PITLProver (with or without 0x).
            feature_commitment: Hex feature commitment from PITLProver (with or without 0x).
            humanity_prob_int:  humanity_prob × 1000, range [0, 1000].

        Returns:
            Transaction hash hex string, or "" if credential contract not configured.
        """
        if not self._phg_credential:
            log.debug("mint_phg_credential: PHG_CREDENTIAL_ADDRESS not configured, skipping")
            return ""
        dev_b32  = bytes.fromhex(device_id.replace("0x", "").ljust(64, "0"))[:32]
        null_b32 = bytes.fromhex(nullifier_hash.replace("0x", "").ljust(64, "0"))[:32]
        fc_b32   = bytes.fromhex(feature_commitment.replace("0x", "").ljust(64, "0"))[:32]
        tx_hash = await self._send_tx(
            self._phg_credential.functions.mintCredential,
            dev_b32,
            null_b32,
            fc_b32,
            humanity_prob_int,
        )
        log.info(
            "PHGCredential minted: device=%s hp_int=%d tx=%s",
            device_id[:16], humanity_prob_int, tx_hash[:16],
        )
        return tx_hash

    async def has_phg_credential(self, device_id: str) -> bool:
        """Returns True if device has a minted credential on-chain.

        Returns False when PHG_CREDENTIAL_ADDRESS is not configured.
        """
        if not self._phg_credential:
            return False
        dev_b32 = bytes.fromhex(device_id.replace("0x", "").ljust(64, "0"))[:32]
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._phg_credential.functions.hasCredential(dev_b32).call
        )

    # --- Phase 37: Credential Enforcement ---

    async def suspend_phg_credential(self, device_id: str,
                                      evidence_hash: bytes, duration_s: int) -> str:
        """Suspend a PHGCredential on-chain (Phase 37).

        No-op (returns empty string) when PHG_CREDENTIAL_ADDRESS is not configured.
        On-chain suspension failure is non-fatal — callers catch and log.
        """
        if not self._phg_credential:
            log.debug("suspend_phg_credential: PHG_CREDENTIAL_ADDRESS not configured, skipping")
            return ""
        dev_b32 = bytes.fromhex(device_id.replace("0x", "").ljust(64, "0"))[:32]
        ev_b32_raw = evidence_hash if len(evidence_hash) >= 32 else evidence_hash.ljust(32, b'\x00')
        ev_b32 = ev_b32_raw[:32]
        tx_hash = await self._send_tx(
            self._phg_credential.functions.suspend,
            dev_b32,
            ev_b32,
            duration_s,
        )
        log.info(
            "PHGCredential suspended: device=%s duration=%ds tx=%s",
            device_id[:16], duration_s, tx_hash[:16],
        )
        return tx_hash

    async def reinstate_phg_credential(self, device_id: str) -> str:
        """Reinstate a suspended PHGCredential on-chain (Phase 37).

        No-op (returns empty string) when PHG_CREDENTIAL_ADDRESS is not configured.
        On-chain reinstatement failure is non-fatal — callers catch and log.
        """
        if not self._phg_credential:
            log.debug("reinstate_phg_credential: PHG_CREDENTIAL_ADDRESS not configured, skipping")
            return ""
        dev_b32 = bytes.fromhex(device_id.replace("0x", "").ljust(64, "0"))[:32]
        tx_hash = await self._send_tx(self._phg_credential.functions.reinstate, dev_b32)
        log.info("PHGCredential reinstated: device=%s tx=%s", device_id[:16], tx_hash[:16])
        return tx_hash

    async def is_phg_credential_active(self, device_id: str) -> bool:
        """Returns True if device has an active (non-suspended) credential (Phase 37).

        Fails open: returns True when PHG_CREDENTIAL_ADDRESS is not configured,
        so unconfigured environments do not block tournament access.
        """
        if not self._phg_credential:
            return True
        dev_b32 = bytes.fromhex(device_id.replace("0x", "").ljust(64, "0"))[:32]
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._phg_credential.functions.isActive(dev_b32).call
        )

    # --- Phase 34: Federated Threat Registry ---

    async def report_federated_cluster(self, cluster_hash: str) -> str:
        """Anchor a cross-bridge confirmed cluster hash on-chain (Phase 34).

        No-op (returns empty string) when FEDERATED_THREAT_REGISTRY_ADDRESS is not configured.

        Args:
            cluster_hash: 16-char hex fingerprint from compute_cluster_hash().

        Returns:
            Transaction hash hex string, or "" if registry not configured.
        """
        if not self._federated_threat_registry:
            log.debug("report_federated_cluster: FEDERATED_THREAT_REGISTRY_ADDRESS not configured, skipping")
            return ""
        # Pad 16-char hex to full 32-byte bytes32
        padded = bytes.fromhex(cluster_hash.ljust(64, "0"))
        tx_hash = await self._send_tx(
            self._federated_threat_registry.functions.reportCluster,
            padded,
        )
        log.info("FederatedCluster anchored: hash=%s tx=%s", cluster_hash, tx_hash[:16])
        return tx_hash

    # --- Phase 55: ioID Device Identity Registry ---

    async def ensure_ioid_registered(self, device_id: str, store) -> str:
        """Ensure the device is registered in the ioID registry (Phase 55).

        Derives: device_address = last 20 bytes of device_id bytes32.
        DID = "did:io:" + checksum(device_address).
        Idempotent: if already registered on-chain, only updates local store.

        Args:
            device_id: 64-char hex device identifier.
            store:     Store instance for local persistence.

        Returns:
            DID string (e.g. "did:io:0x..."), or "" if registry not configured.
        """
        if not self._ioid_registry:
            log.debug("ensure_ioid_registered: IOID_REGISTRY_ADDRESS not configured, skipping")
            return ""

        # Derive device address = last 20 bytes of 32-byte device_id
        dev_bytes = bytes.fromhex(device_id.ljust(64, "0"))[:32]
        device_address = self._w3.to_checksum_address(("0x" + dev_bytes[-20:].hex()))
        did = f"did:io:{device_address}"

        # Check local store first (avoid unnecessary chain call)
        existing = store.get_ioid_device(device_id)
        if existing and existing.get("did"):
            log.debug("ensure_ioid_registered: device %s already in local store", device_id[:16])
            return existing["did"]

        # Check on-chain registration
        try:
            dev_b32 = dev_bytes
            is_reg = await self._w3.eth.call({
                "to": self._ioid_registry.address,
                "data": self._ioid_registry.encodeABI("isRegistered", [dev_b32]),
            })
            already_registered = bool(int(is_reg.hex() or "0", 16))
        except Exception as exc:
            log.debug("ensure_ioid_registered: isRegistered check failed: %s", exc)
            already_registered = False

        tx_hash = ""
        if not already_registered:
            try:
                tx_hash = await self._send_tx(
                    self._ioid_registry.functions.register,
                    dev_b32,
                    device_address,
                    did,
                )
                log.info(
                    "ioID registered: device=%s did=%s tx=%s",
                    device_id[:16], did, tx_hash[:16],
                )
            except Exception as exc:
                log.warning("ensure_ioid_registered: register tx failed: %s", exc)
        else:
            log.debug("ensure_ioid_registered: device %s already on-chain", device_id[:16])

        # Persist locally regardless of on-chain outcome (store the DID for future use)
        try:
            store.store_ioid_device(device_id, device_address, did, tx_hash)
        except Exception as exc:
            log.debug("ensure_ioid_registered: local store failed (non-fatal): %s", exc)

        return did

    async def ioid_increment_session(self, device_id: str) -> str:
        """Increment the session counter for a registered ioID device (Phase 55).

        No-op if registry not configured or device not registered.

        Args:
            device_id: 64-char hex device identifier.

        Returns:
            Transaction hash hex string, or "" if registry not configured.
        """
        if not self._ioid_registry:
            return ""
        try:
            dev_b32 = bytes.fromhex(device_id.ljust(64, "0"))[:32]
            tx_hash = await self._send_tx(
                self._ioid_registry.functions.incrementSession,
                dev_b32,
            )
            log.debug("ioID session incremented: device=%s tx=%s", device_id[:16], tx_hash[:16])
            return tx_hash
        except Exception as exc:
            log.debug("ioid_increment_session failed (non-fatal): %s", exc)
            return ""

    # --- Phase 56: Tournament Passport ---

    async def submit_tournament_passport(
        self,
        device_id: str,
        proof: bytes,
        nullifiers: list,
        passport_hash: bytes,
        ioid_token_id: int,
        min_humanity_int: int,
        epoch: int,
    ) -> str:
        """Submit a ZK tournament passport to PITLTournamentPassport (Phase 56).

        No-op (returns empty string) when TOURNAMENT_PASSPORT_ADDRESS is not configured.

        Args:
            device_id:        64-char hex device identifier.
            proof:            ZK proof bytes (256 bytes for real Groth16, empty for mock mode).
            nullifiers:       List of 5 bytes32 session nullifier hashes.
            passport_hash:    Poseidon(nullifiers) as bytes32.
            ioid_token_id:    ioID token ID (0 in mock mode).
            min_humanity_int: Minimum humanity_prob * 1000 across sessions.
            epoch:            Current epoch number.

        Returns:
            Transaction hash hex string, or "" if not configured.
        """
        if not self._tournament_passport:
            log.debug("submit_tournament_passport: TOURNAMENT_PASSPORT_ADDRESS not configured, skipping")
            return ""
        dev_b32 = bytes.fromhex(device_id.ljust(64, "0"))[:32]
        null_b32 = [bytes.fromhex(n.replace("0x", "").ljust(64, "0"))[:32] for n in nullifiers]
        ph_b32   = passport_hash if isinstance(passport_hash, bytes) else bytes.fromhex(str(passport_hash).replace("0x", "").ljust(64, "0"))[:32]
        tx_hash = await self._send_tx(
            self._tournament_passport.functions.submitPassport,
            dev_b32,
            proof,
            null_b32,
            ph_b32,
            ioid_token_id,
            min_humanity_int,
            epoch,
        )
        log.info(
            "TournamentPassport submitted: device=%s min_hp=%d tx=%s",
            device_id[:16], min_humanity_int, tx_hash[:16],
        )
        return tx_hash

    async def get_tournament_passport(self, device_id: str) -> dict:
        """Read a device's tournament passport from on-chain (Phase 56).

        Returns dict with passport fields, or empty dict if not configured / not found.
        """
        if not self._tournament_passport:
            return {}
        try:
            dev_b32 = bytes.fromhex(device_id.ljust(64, "0"))[:32]
            result = await self._tournament_passport.functions.getPassport(dev_b32).call()
            return {
                "passport_hash":    result[0].hex() if result[0] else "",
                "ioid_token_id":    result[1],
                "min_humanity_int": result[2],
                "issued_at":        result[3],
                "active":           result[4],
            }
        except Exception as exc:
            log.debug("get_tournament_passport chain call failed (non-fatal): %s", exc)
            return {}

    # --- Phase 66: RulingRegistry on-chain commitment ---

    @_gated_submission
    async def record_ruling_on_chain(
        self,
        commitment_hash_bytes: bytes,
        device_id_hex: str,
        verdict: str,
        confidence: float,
        timestamp_ns: int,
    ) -> str:
        """Submit ruling commitment_hash to RulingRegistry.sol (Phase 66).

        Returns tx_hash hex string. Raises RuntimeError when RULING_REGISTRY_ADDRESS
        is not configured or the transaction reverts.
        """
        registry_address = getattr(self._cfg, "ruling_registry_address", "")
        if not registry_address:
            raise RuntimeError("RULING_REGISTRY_ADDRESS not configured")

        VERDICT_MAP = {"FLAG": 0, "HOLD": 1, "BLOCK": 2, "CERTIFY": 3, "CLEAR": 4}
        device_bytes = bytes.fromhex(device_id_hex.replace("0x", ""))
        device_b32 = device_bytes.ljust(32, b"\x00")[:32]

        ruling_registry_abi = [
            {
                "name": "recordRuling",
                "type": "function",
                "stateMutability": "nonpayable",
                "inputs": [
                    {"name": "commitmentHash", "type": "bytes32"},
                    {"name": "deviceId",       "type": "bytes32"},
                    {"name": "verdict",        "type": "uint8"},
                    {"name": "confidence1000", "type": "uint16"},
                    {"name": "timestamp",      "type": "uint64"},
                ],
                "outputs": [],
            }
        ]
        contract = self._w3.eth.contract(
            address=self._w3.to_checksum_address(registry_address),
            abi=ruling_registry_abi,
        )
        nonce = await self._w3.eth.get_transaction_count(self._account.address)
        tx = await contract.functions.recordRuling(
            commitment_hash_bytes,
            device_b32,
            VERDICT_MAP.get(verdict, 0),
            int(confidence * 1000),
            timestamp_ns // 1_000_000_000,
        ).build_transaction({
            "from":  self._account.address,
            "nonce": nonce,
            "gas":   120_000,
        })
        signed  = self._account.sign_transaction(tx)
        tx_hash = await self._w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = await self._w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt.status != 1:
            raise RuntimeError(f"record_ruling_on_chain: tx reverted {tx_hash.hex()}")
        log.info("record_ruling_on_chain: tx=%s verdict=%s", tx_hash.hex()[:16], verdict)
        return tx_hash.hex()

    # --- Phase 67: CeremonyRegistry on-chain commitment ---

    @_gated_submission
    async def record_ceremony_on_chain(
        self,
        circuit_name: str,
        vkey_json_bytes: bytes,
        beacon_block_hash: bytes,
        beacon_block_number: int,
        contributor_hashes: list,
        ptau_source: str = "hermez-hez_final_15-2021",
    ) -> str:
        """Register MPC ceremony in CeremonyRegistry.sol (Phase 67).

        circuitId   = keccak256(circuit_name.encode())
        vkeyHash    = keccak256(vkey_json_bytes)
        Raises RuntimeError when CEREMONY_REGISTRY_ADDRESS not configured or tx reverts.
        Returns tx_hash hex string.
        """
        import hashlib
        registry_address = getattr(self._cfg, "ceremony_registry_address", "")
        if not registry_address:
            raise RuntimeError("CEREMONY_REGISTRY_ADDRESS not configured")

        circuit_id_bytes = hashlib.sha3_256(circuit_name.encode()).digest()
        vkey_hash_bytes  = hashlib.sha3_256(vkey_json_bytes).digest()
        contrib_bytes32  = [h if isinstance(h, bytes) else bytes.fromhex(h) for h in contributor_hashes]

        ceremony_registry_abi = [{
            "name": "registerCeremony",
            "type": "function",
            "stateMutability": "nonpayable",
            "inputs": [
                {"name": "circuitId",          "type": "bytes32"},
                {"name": "verifyingKeyHash",    "type": "bytes32"},
                {"name": "beaconBlockHash",     "type": "bytes32"},
                {"name": "beaconBlockNumber",   "type": "uint64"},
                {"name": "contributorHashes",   "type": "bytes32[]"},
                {"name": "ptauSource",          "type": "string"},
            ],
            "outputs": [],
        }]
        contract = self._w3.eth.contract(
            address=self._w3.to_checksum_address(registry_address),
            abi=ceremony_registry_abi,
        )
        nonce = await self._w3.eth.get_transaction_count(self._account.address)
        tx = await contract.functions.registerCeremony(
            circuit_id_bytes,
            vkey_hash_bytes,
            beacon_block_hash,
            beacon_block_number,
            contrib_bytes32,
            ptau_source,
        ).build_transaction({
            "from":  self._account.address,
            "nonce": nonce,
            "gas":   200_000,
        })
        signed  = self._account.sign_transaction(tx)
        tx_hash = await self._w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = await self._w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt.status != 1:
            raise RuntimeError(f"record_ceremony_on_chain: tx reverted {tx_hash.hex()}")
        log.info(
            "record_ceremony_on_chain: circuit=%s tx=%s",
            circuit_name, tx_hash.hex()[:16],
        )
        return tx_hash.hex()

    def get_zk_verifier_stats(self) -> dict:
        """Phase 68-B — Return ZKVerifier proof acceptance/rejection/skipped/error counters."""
        return {
            "enabled": self._zk_verifier is not None,
            "vkey_path": self._zk_verifier.vkey_path() if self._zk_verifier else None,
            **self._zk_stats,
        }

    # --- Phase 69: Native VAPI Oracle write methods ---

    def _device_b32(self, device_id_hex: str) -> bytes:
        """Convert hex device_id to padded bytes32."""
        raw = bytes.fromhex(device_id_hex.replace("0x", ""))
        return raw.ljust(32, b"\x00")[:32]

    @_gated_submission
    async def update_humanity_oracle(
        self,
        device_id_hex: str,
        inference_code: int,
        humanity_pct: int,
        l4_distance_x1000: int,
        l5_cv_x1000: int,
    ) -> str:
        """Publish humanity verdict to HumanityOracle.sol (Phase 69).

        Returns tx_hash hex. Raises RuntimeError if HUMANITY_ORACLE_ADDRESS not set.
        """
        addr = getattr(self._cfg, "humanity_oracle_address", "")
        if not addr:
            raise RuntimeError("HUMANITY_ORACLE_ADDRESS not configured")

        abi = [{
            "name": "updateVerdict", "type": "function", "stateMutability": "nonpayable",
            "inputs": [
                {"name": "deviceId",          "type": "bytes32"},
                {"name": "inferenceCode",     "type": "uint8"},
                {"name": "humanityPct",       "type": "uint16"},
                {"name": "l4DistanceX1000",   "type": "uint32"},
                {"name": "l5CvX1000",         "type": "uint32"},
            ],
            "outputs": [],
        }]
        contract = self._w3.eth.contract(
            address=self._w3.to_checksum_address(addr), abi=abi
        )
        nonce = await self._w3.eth.get_transaction_count(self._account.address)
        tx = await contract.functions.updateVerdict(
            self._device_b32(device_id_hex),
            inference_code & 0xFF,
            min(humanity_pct, 1000),
            l4_distance_x1000,
            l5_cv_x1000,
        ).build_transaction({"from": self._account.address, "nonce": nonce, "gas": 80_000})
        signed = self._account.sign_transaction(tx)
        tx_hash = await self._w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = await self._w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt.status != 1:
            raise RuntimeError(f"update_humanity_oracle: tx reverted {tx_hash.hex()}")
        log.info("update_humanity_oracle: tx=%s device=%s", tx_hash.hex()[:16], device_id_hex[:16])
        return tx_hash.hex()

    @_gated_submission
    async def update_ruling_oracle(
        self,
        device_id_hex: str,
        suspended: bool,
        flag_streak: int,
        hold_streak: int,
        suspended_until: int,
        last_commitment_hash: bytes,
    ) -> str:
        """Publish ruling state to RulingOracle.sol (Phase 69).

        Returns tx_hash hex. Raises RuntimeError if RULING_ORACLE_ADDRESS not set.
        """
        addr = getattr(self._cfg, "ruling_oracle_address", "")
        if not addr:
            raise RuntimeError("RULING_ORACLE_ADDRESS not configured")

        abi = [{
            "name": "updateRulingState", "type": "function", "stateMutability": "nonpayable",
            "inputs": [
                {"name": "deviceId",            "type": "bytes32"},
                {"name": "suspended",           "type": "bool"},
                {"name": "flagStreak",          "type": "uint32"},
                {"name": "holdStreak",          "type": "uint32"},
                {"name": "suspendedUntil",      "type": "uint64"},
                {"name": "lastCommitmentHash",  "type": "bytes32"},
            ],
            "outputs": [],
        }]
        last_b32 = last_commitment_hash.ljust(32, b"\x00")[:32]
        contract = self._w3.eth.contract(
            address=self._w3.to_checksum_address(addr), abi=abi
        )
        nonce = await self._w3.eth.get_transaction_count(self._account.address)
        tx = await contract.functions.updateRulingState(
            self._device_b32(device_id_hex),
            suspended,
            flag_streak,
            hold_streak,
            suspended_until,
            last_b32,
        ).build_transaction({"from": self._account.address, "nonce": nonce, "gas": 80_000})
        signed = self._account.sign_transaction(tx)
        tx_hash = await self._w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = await self._w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt.status != 1:
            raise RuntimeError(f"update_ruling_oracle: tx reverted {tx_hash.hex()}")
        log.info("update_ruling_oracle: tx=%s device=%s", tx_hash.hex()[:16], device_id_hex[:16])
        return tx_hash.hex()

    @_gated_submission
    async def update_passport_oracle(
        self,
        device_id_hex: str,
        issued: bool,
        on_chain: bool,
        passport_hash: bytes,
        session_count: int,
    ) -> str:
        """Publish passport state to PassportOracle.sol (Phase 69).

        Returns tx_hash hex. Raises RuntimeError if PASSPORT_ORACLE_ADDRESS not set.
        """
        addr = getattr(self._cfg, "passport_oracle_address", "")
        if not addr:
            raise RuntimeError("PASSPORT_ORACLE_ADDRESS not configured")

        abi = [{
            "name": "updatePassportState", "type": "function", "stateMutability": "nonpayable",
            "inputs": [
                {"name": "deviceId",      "type": "bytes32"},
                {"name": "issued",        "type": "bool"},
                {"name": "onChain",       "type": "bool"},
                {"name": "passportHash",  "type": "bytes32"},
                {"name": "sessionCount",  "type": "uint32"},
            ],
            "outputs": [],
        }]
        p_b32 = passport_hash.ljust(32, b"\x00")[:32]
        contract = self._w3.eth.contract(
            address=self._w3.to_checksum_address(addr), abi=abi
        )
        nonce = await self._w3.eth.get_transaction_count(self._account.address)
        tx = await contract.functions.updatePassportState(
            self._device_b32(device_id_hex),
            issued,
            on_chain,
            p_b32,
            session_count,
        ).build_transaction({"from": self._account.address, "nonce": nonce, "gas": 80_000})
        signed = self._account.sign_transaction(tx)
        tx_hash = await self._w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = await self._w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt.status != 1:
            raise RuntimeError(f"update_passport_oracle: tx reverted {tx_hash.hex()}")
        log.info("update_passport_oracle: tx=%s device=%s", tx_hash.hex()[:16], device_id_hex[:16])
        return tx_hash.hex()

    @_gated_submission
    async def publish_sovereignty_pledge(self, schema_hash_hex: str) -> str:
        """Commit the immutable data sovereignty pledge to DataSovereigntyRegistry.sol (Phase 69).

        schema_hash_hex = keccak256(all VAPI data schemas).
        Returns tx_hash. Raises RuntimeError if DATA_SOVEREIGNTY_REG_ADDRESS not set.
        """
        addr = getattr(self._cfg, "data_sovereignty_reg_address", "")
        if not addr:
            raise RuntimeError("DATA_SOVEREIGNTY_REG_ADDRESS not configured")

        declaration = (
            "VAPI (Verified Autonomous Physical Intelligence) asserts full sovereignty over "
            "all data derived from VAPI-certified DualShock Edge devices. This includes: "
            "PoAC records (228B), biometric feature vectors, ZK proofs, agent rulings, "
            "calibration state, and all data produced by the PITL 9-layer stack. "
            "Data access is exclusively gated to three authorized tiers: MANUFACTURER, "
            "DEVELOPER, and GAMER. No other entity may use, license, sell, or redistribute "
            "VAPI-produced data without explicit on-chain authorization recorded in "
            "VAPIDataMarketplace. This pledge is irrevocable."
        )

        schema_bytes = bytes.fromhex(schema_hash_hex.replace("0x", "").zfill(64))[:32]

        abi = [{
            "name": "pledge_", "type": "function", "stateMutability": "nonpayable",
            "inputs": [
                {"name": "schemaHash",  "type": "bytes32"},
                {"name": "declaration", "type": "string"},
            ],
            "outputs": [],
        }]
        contract = self._w3.eth.contract(
            address=self._w3.to_checksum_address(addr), abi=abi
        )
        nonce = await self._w3.eth.get_transaction_count(self._account.address)
        tx = await contract.functions.pledge_(
            schema_bytes, declaration
        ).build_transaction({"from": self._account.address, "nonce": nonce, "gas": 150_000})
        signed = self._account.sign_transaction(tx)
        tx_hash = await self._w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = await self._w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt.status != 1:
            raise RuntimeError(f"publish_sovereignty_pledge: tx reverted {tx_hash.hex()}")
        log.info("publish_sovereignty_pledge: tx=%s schema=%s...", tx_hash.hex()[:16], schema_hash_hex[:16])
        return tx_hash.hex()

    @_gated_submission
    async def record_gate_attestation_on_chain(
        self,
        attestation_hash_hex: str,
        consecutive_clean: int,
        gate_n: int,
        divergence_rate: float,
        timestamp_ns: int,
    ) -> str:
        """Publish gate readiness attestation to GateAttestationAnchor.sol (Phase 87).

        attestation_hash_hex — 64-char hex from compute_gate_attestation_hash(); same
                               value stored in gate_attestations SQLite row.
        divergence_rate      — float 0.0–1.0; encoded on-chain as uint32 millis
                               (int(divergence_rate * 1000)) to avoid float storage.
        timestamp_ns         — nanosecond epoch used when hashing; converted to uint64
                               seconds for on-chain storage.

        W1 invariant: callers MUST pass the attestation_hash_hex that was previously
        written to gate_attestations SQLite — never recompute from current config values
        at call time, as config may drift between SQLite write and chain call.

        Raises RuntimeError if anchor address not configured or tx reverts.
        Returns tx_hash hex.
        """
        addr = getattr(self._cfg, "gate_attestation_anchor_address", None)
        if not addr:
            raise RuntimeError(
                "record_gate_attestation_on_chain: gate_attestation_anchor_address not configured"
            )

        hash_bytes = bytes.fromhex(attestation_hash_hex.replace("0x", "").zfill(64))[:32]
        divergence_millis = int(divergence_rate * 1000)
        timestamp_s = int(timestamp_ns // 1_000_000_000)

        abi = [{
            "name": "recordGateAttestation", "type": "function", "stateMutability": "nonpayable",
            "inputs": [
                {"name": "attestationHash",      "type": "bytes32"},
                {"name": "consecutiveClean",     "type": "uint32"},
                {"name": "gateN",                "type": "uint32"},
                {"name": "divergenceRateMillis", "type": "uint32"},
                {"name": "timestamp",            "type": "uint64"},
            ],
            "outputs": [],
        }]
        contract = self._w3.eth.contract(
            address=self._w3.to_checksum_address(addr), abi=abi
        )
        nonce = await self._w3.eth.get_transaction_count(self._account.address)
        tx = await contract.functions.recordGateAttestation(
            hash_bytes,
            int(consecutive_clean),
            int(gate_n),
            divergence_millis,
            timestamp_s,
        ).build_transaction({"from": self._account.address, "nonce": nonce, "gas": 100_000})
        signed = self._account.sign_transaction(tx)
        tx_hash = await self._w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = await self._w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt.status != 1:
            raise RuntimeError(
                f"record_gate_attestation_on_chain: tx reverted {tx_hash.hex()}"
            )
        log.info(
            "record_gate_attestation_on_chain: tx=%s hash=%s... clean=%d gate_n=%d millis=%d",
            tx_hash.hex()[:16], attestation_hash_hex[:16],
            consecutive_clean, gate_n, divergence_millis,
        )
        return tx_hash.hex()

    @_gated_submission
    async def record_gsr_sample_on_chain(
        self,
        device_id_bytes32: bytes,
        arousal_millis: int,
        correlation_millis: int,
        timestamp: int,
    ) -> str:
        """Publish a GSR biometric sample to VAPIGSRRegistry.sol (Phase 99B).

        device_id_bytes32   — 32-byte device identifier (keccak256 of device_id string)
        arousal_millis      — sympathetic_arousal_index * 1000 (uint256)
        correlation_millis  — (correlation + 1.0) * 500, range 0–1000 (uint256)
        timestamp           — Unix seconds (uint256)

        Only called when cfg.gsr_enabled=True. Raises RuntimeError if address not
        configured or tx reverts.
        Returns tx_hash hex.
        """
        addr = getattr(self._cfg, "gsr_registry_address", None)
        if not addr:
            raise RuntimeError(
                "record_gsr_sample_on_chain: gsr_registry_address not configured"
            )

        # Pad to exactly 32 bytes
        if len(device_id_bytes32) < 32:
            device_id_bytes32 = device_id_bytes32.ljust(32, b"\x00")
        device_id_b32 = bytes(device_id_bytes32[:32])

        abi = [{
            "name": "recordSample", "type": "function", "stateMutability": "nonpayable",
            "inputs": [
                {"name": "deviceId",          "type": "bytes32"},
                {"name": "arousalMillis",      "type": "uint256"},
                {"name": "correlationMillis",  "type": "uint256"},
                {"name": "timestamp",          "type": "uint256"},
            ],
            "outputs": [],
        }]
        contract = self._w3.eth.contract(
            address=self._w3.to_checksum_address(addr), abi=abi
        )
        nonce = await self._w3.eth.get_transaction_count(self._account.address)
        tx = await contract.functions.recordSample(
            device_id_b32,
            int(arousal_millis),
            int(correlation_millis),
            int(timestamp),
        ).build_transaction({"from": self._account.address, "nonce": nonce, "gas": 80_000})
        signed = self._account.sign_transaction(tx)
        tx_hash = await self._w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = await self._w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt.status != 1:
            raise RuntimeError(f"record_gsr_sample_on_chain: tx reverted {tx_hash.hex()}")
        log.info(
            "record_gsr_sample_on_chain: tx=%s arousal=%d corr=%d ts=%d",
            tx_hash.hex()[:16], arousal_millis, correlation_millis, timestamp,
        )
        return tx_hash.hex()

    @_gated_submission
    async def record_adjudication(
        self,
        device_id: str,
        poad_hash_hex: str,
        dual_veto: bool,
    ) -> str:
        """Anchor a PoAd hash in AdjudicationRegistry.sol (Phase 112).
        device_id     — string device identifier; hashed to bytes32 via sha256
        poad_hash_hex — 64-char hex string (SHA-256 of sorted verdict bundle)
        dual_veto     — True if both ClassJ and Triage reached BLOCK quorum
        Raises RuntimeError if address not configured or tx reverts. Returns tx_hash hex.
        """
        addr = getattr(self._cfg, "adjudication_registry_address", "")
        if not addr:
            raise RuntimeError("record_adjudication: adjudication_registry_address not configured")
        import hashlib as _hl
        device_id_bytes32 = _hl.sha256(device_id.encode()).digest()   # 32 bytes
        poad_hash_bytes32 = bytes.fromhex(poad_hash_hex)              # 32 bytes
        _ABI = [{
            "name": "recordAdjudication", "type": "function",
            "stateMutability": "nonpayable",
            "inputs": [
                {"name": "deviceIdHash", "type": "bytes32"},
                {"name": "poadHash",     "type": "bytes32"},
                {"name": "dualVeto",     "type": "bool"},
            ],
            "outputs": [],
        }]
        contract = self._w3.eth.contract(
            address=self._w3.to_checksum_address(addr), abi=_ABI
        )
        nonce = await self._w3.eth.get_transaction_count(self._account.address)
        tx = await contract.functions.recordAdjudication(
            device_id_bytes32, poad_hash_bytes32, dual_veto,
        ).build_transaction({"from": self._account.address, "nonce": nonce, "gas": 80_000})
        signed = self._account.sign_transaction(tx)
        tx_hash = await self._w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = await self._w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt.status != 1:
            raise RuntimeError(f"record_adjudication: tx reverted {tx_hash.hex()}")
        log.info("record_adjudication: tx=%s device=%s poad=%s",
                 tx_hash.hex()[:16], device_id[:16], poad_hash_hex[:16])
        return tx_hash.hex()

    # ------------------------------------------------------------------
    # Phase 237.5 — CORPUS-SNAPSHOT on-chain anchoring (Path X)
    # ------------------------------------------------------------------
    # Pure addition. Never raises. Targets the LEGACY 3-arg
    # recordAdjudication(bytes32 deviceIdHash, bytes32 poadHash, bool dualVeto)
    # ABI which is what's actually present in the deployed AdjudicationRegistry
    # bytecode at 0x44CF98... (Phase 111 original deploy 2026-03-27). The
    # design-intent 2-arg anchorAdjudication(bytes32, string) is in repo source
    # but was never re-deployed; eth_getCode confirms selectors 0xae7cd267 +
    # 0x79dcce3f are NOT in deployed bytecode while 0x5fa83f4b (recordAdjudication)
    # IS. See wiki/phases/phase_237_5.md "Path X" section.
    #
    # CORPUS_SNAPSHOT attribution is carried by a constant deviceIdHash =
    # SHA-256(b"VAPI_CORPUS_SNAPSHOT_v1") that distinguishes corpus-snapshot
    # records from per-device PoAd records (which use SHA-256(device_id)).
    # ZK-SEPPROOF will filter on-chain records by this constant deviceIdHash.
    #
    # Phase 112's record_adjudication wrapper above (chain.py:2487-2529) targets
    # the same recordAdjudication function with per-device deviceIdHash — its
    # call path is UNAFFECTED (it's been code-complete-deferred since Phase 112
    # per deployed-addresses.json:80; Phase 237.5 doesn't touch it).
    _CORPUS_SNAPSHOT_DEVICE_ID = hashlib.sha256(b"VAPI_CORPUS_SNAPSHOT_v1").digest()
    # Phase 237-ZK-SEPPROOF — BIOMETRIC-SNAPSHOT attribution constant.
    # Underscores here intentional (chain attribution sourceType-like tag);
    # the FROZEN commitment domain tag uses hyphens (VAPI-BIOMETRIC-SNAPSHOT-v1).
    # Mirrors the corpus_snapshot pattern at Phase 237.5 Path X.
    _BIOMETRIC_SNAPSHOT_DEVICE_ID = hashlib.sha256(b"VAPI_BIOMETRIC_SNAPSHOT_v1").digest()
    # Phase 238-MARKETPLACE — LISTING-v1 attribution constant.
    # Same underscore-vs-hyphen asymmetry as the corpus + biometric snapshots.
    # The FROZEN commitment domain tag uses hyphens (VAPI-LISTING-v1).
    _LISTING_DEVICE_ID = hashlib.sha256(b"VAPI_LISTING_v1").digest()
    # Phase O3-ZKBA-TRACK1 Track 2 C7 — ZKBA artifact attribution constant.
    # Same underscore-vs-hyphen asymmetry as corpus + biometric + listing
    # snapshots. The FROZEN commitment domain tag uses HYPHENS (canonical
    # name: VAPI-ZKBA-ARTIFACT v1; PV-CI pinned by INV-ZKBA-002 in
    # bridge/vapi_bridge/zkba_artifact.py); the device-id-hash attribution
    # uses underscores per the byte literal below.
    _ZKBA_DEVICE_ID = hashlib.sha256(b"VAPI_ZKBA_v1").digest()

    async def anchor_corpus_snapshot(
        self,
        snapshot_commitment_hex: str,
    ) -> "tuple[str | None, bool]":
        """Anchor a CORPUS-SNAPSHOT commitment via legacy recordAdjudication ABI (Phase 237.5 Path X).

        Calls recordAdjudication(deviceIdHash, poadHash, dualVeto) on the deployed
        AdjudicationRegistry contract with:
          - deviceIdHash = self._CORPUS_SNAPSHOT_DEVICE_ID (constant; carries
            CORPUS_SNAPSHOT attribution as the design-intent sourceType would have)
          - poadHash     = the 32-byte snapshot_commitment from corpus_snapshot.py
          - dualVeto     = False (corpus snapshots are not adjudication verdicts)

        Returns (tx_hash_hex, True) on success; (None, False) on missing config /
        wallet error / tx revert / duplicate ("PoAd: already recorded"). Never
        raises — graceful degradation per Phase 237.5 D1.
        """
        # Phase 237.5 Path C+ kill-switch — short-circuit before any RPC call
        # when CHAIN_SUBMISSION_PAUSED=true is set in bridge/.env.
        if getattr(self._cfg, "chain_submission_paused", False):
            log.info(
                "anchor_corpus_snapshot: chain_submission_paused=true — "
                "snapshot will record on_chain_confirmed=False (kill-switch active)"
            )
            return (None, False)
        addr = getattr(self._cfg, "adjudication_registry_address", "")
        if not addr:
            log.warning(
                "anchor_corpus_snapshot: adjudication_registry_address not "
                "configured — snapshot will record on_chain_confirmed=False"
            )
            return (None, False)
        if self._account is None:
            log.warning(
                "anchor_corpus_snapshot: self._account is None (no bridge "
                "private key loaded) — snapshot will record on_chain_confirmed=False"
            )
            return (None, False)
        try:
            commitment_bytes32 = bytes.fromhex(snapshot_commitment_hex.lstrip("0x"))[:32]
            commitment_bytes32 = commitment_bytes32.ljust(32, b"\x00")
        except Exception as exc:
            log.warning("anchor_corpus_snapshot: bad commitment hex: %s", exc)
            return (None, False)
        _ABI = [{
            "name": "recordAdjudication", "type": "function",
            "stateMutability": "nonpayable",
            "inputs": [
                {"name": "deviceIdHash", "type": "bytes32"},
                {"name": "poadHash",     "type": "bytes32"},
                {"name": "dualVeto",     "type": "bool"},
            ],
            "outputs": [],
        }]
        try:
            contract = self._w3.eth.contract(
                address=self._w3.to_checksum_address(addr), abi=_ABI
            )
            nonce = await self._w3.eth.get_transaction_count(self._account.address)
            tx = await contract.functions.recordAdjudication(
                self._CORPUS_SNAPSHOT_DEVICE_ID, commitment_bytes32, False,
            ).build_transaction({
                "from": self._account.address, "nonce": nonce,
            })
            # Dynamic gas estimate with 25% safety buffer. IoTeX requires more
            # gas than naive Ethereum estimates suggest for storage-heavy ops
            # (live measurement: ~160k for recordAdjudication's two SSTORE +
            # array push + counter increment). Static 80k budget hits IoTeX
            # status=101 (out-of-gas).
            gas_estimate = await self._w3.eth.estimate_gas(tx)
            tx["gas"] = int(gas_estimate * 1.25)
            signed = self._account.sign_transaction(tx)
            tx_hash = await self._w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = await self._w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            if receipt["status"] != 1:
                log.warning(
                    "anchor_corpus_snapshot: tx reverted commitment=%s tx=%s",
                    snapshot_commitment_hex[:16], tx_hash.hex()[:16],
                )
                return (None, False)
            log.info(
                "anchor_corpus_snapshot: tx=%s commitment=%s",
                tx_hash.hex()[:16], snapshot_commitment_hex[:16],
            )
            return (tx_hash.hex(), True)
        except Exception as exc:
            _msg = str(exc)
            if "PoAd: already recorded" in _msg:
                log.info(
                    "anchor_corpus_snapshot: idempotent no-op — commitment=%s "
                    "already anchored",
                    snapshot_commitment_hex[:16],
                )
                return (None, False)
            log.warning(
                "anchor_corpus_snapshot: anchor failed commitment=%s err=%s",
                snapshot_commitment_hex[:16], _msg[:120],
            )
            return (None, False)

    # --- Phase O4-VPM-ANCHOR — VPM artifact anchor (dedicated VPMAnchorRegistry contract) ---

    # Frozen ABI literal for VPMAnchorRegistry.anchorVPM. Distinct from the
    # legacy recordAdjudication ABI used by anchor_corpus_snapshot /
    # anchor_zkba_artifact / etc. — this targets the dedicated Phase O4
    # contract at cfg.vpm_anchor_registry_address (immutable post-deploy;
    # constructor pins AdjudicationRegistry 0x44CF981f... for cross-
    # contract composition integrity check).
    _VPM_ANCHOR_ABI = [{
        "name": "anchorVPM", "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "zkbaManifestHash", "type": "bytes32"},
            {"name": "vpmManifestHash",  "type": "bytes32"},
            {"name": "tsNs",             "type": "uint64"},
        ],
        "outputs": [],
    }]

    async def anchor_vpm(
        self,
        zkba_manifest_hash_hex: str,
        vpm_manifest_hash_hex: str,
        ts_ns: int,
    ) -> "tuple[str | None, bool]":
        """Anchor a VPM artifact's manifest hash on-chain via VPMAnchorRegistry.

        Calls VPMAnchorRegistry.anchorVPM(zkbaManifestHash, vpmManifestHash, tsNs)
        on the deployed contract at cfg.vpm_anchor_registry_address.

        The contract enforces cross-contract integrity at write time:
        zkbaManifestHash MUST already be anchored in AdjudicationRegistry
        (Phase 111 LIVE at 0x44CF981f...). The bridge does NOT pre-check this
        — the chain reverts with 'VPM: zkba not anchored' if the upstream
        ZKBA artifact wasn't anchored first.

        Returns:
          (tx_hash_hex, True)  on successful tx receipt with status=1
          (None,         False) on missing config / kill-switch / wallet error /
                                 tx revert / 'VPM: already anchored' duplicate

        Never raises — graceful degradation per the kill-switch + missing-
        config + fail-open pattern shared with anchor_corpus_snapshot.

        FROZEN scopes:
          - cfg.vpm_anchor_registry_address (env: VPM_ANCHOR_REGISTRY_ADDRESS)
          - VPMAnchorRegistry.anchorVPM ABI literal at _VPM_ANCHOR_ABI
          - gas estimate × 1.25 buffer (matches Phase 237.5 IoTeX
            storage-heavy operation pattern)

        Kill-switch:
          When cfg.chain_submission_paused=True, short-circuits BEFORE any
          RPC contact and returns (None, False). The bridge wallet is never
          debited under the held kill-switch.
        """
        # Kill-switch — same pattern as anchor_corpus_snapshot.
        if getattr(self._cfg, "chain_submission_paused", False):
            log.info(
                "anchor_vpm: chain_submission_paused=true — "
                "tx suppressed; VPM will not anchor (kill-switch active)"
            )
            return (None, False)

        addr = getattr(self._cfg, "vpm_anchor_registry_address", "")
        if not addr:
            log.warning(
                "anchor_vpm: vpm_anchor_registry_address not configured — "
                "VPM will not anchor (fail-open; deploy ceremony pending)"
            )
            return (None, False)

        if self._account is None:
            log.warning(
                "anchor_vpm: self._account is None (no bridge private key "
                "loaded) — VPM will not anchor"
            )
            return (None, False)

        try:
            zkba_bytes32 = bytes.fromhex(
                zkba_manifest_hash_hex.lstrip("0x")
            )[:32].ljust(32, b"\x00")
            vpm_bytes32 = bytes.fromhex(
                vpm_manifest_hash_hex.lstrip("0x")
            )[:32].ljust(32, b"\x00")
        except Exception as exc:
            log.warning("anchor_vpm: bad hash hex: %s", exc)
            return (None, False)

        # Validate ts_ns is uint64.
        if not isinstance(ts_ns, int) or ts_ns < 0 or ts_ns > (2**64 - 1):
            log.warning("anchor_vpm: ts_ns must be uint64; got %r", ts_ns)
            return (None, False)

        # Reject zero hashes upfront (contract reverts on these — saves the
        # round-trip + gas estimate failure path).
        if zkba_bytes32 == b"\x00" * 32:
            log.warning(
                "anchor_vpm: zkbaManifestHash is zero — contract would "
                "revert with 'VPM: zero zkba hash'"
            )
            return (None, False)
        if vpm_bytes32 == b"\x00" * 32:
            log.warning(
                "anchor_vpm: vpmManifestHash is zero — contract would "
                "revert with 'VPM: zero vpm hash'"
            )
            return (None, False)

        try:
            contract = self._w3.eth.contract(
                address=self._w3.to_checksum_address(addr),
                abi=self._VPM_ANCHOR_ABI,
            )
            nonce = await self._w3.eth.get_transaction_count(
                self._account.address
            )
            tx = await contract.functions.anchorVPM(
                zkba_bytes32, vpm_bytes32, int(ts_ns),
            ).build_transaction({
                "from": self._account.address, "nonce": nonce,
            })
            # Gas estimate × 1.25 buffer (matches recordAdjudication +
            # IoTeX storage-heavy operation pattern).
            gas_estimate = await self._w3.eth.estimate_gas(tx)
            tx["gas"] = int(gas_estimate * 1.25)
            signed = self._account.sign_transaction(tx)
            tx_hash = await self._w3.eth.send_raw_transaction(
                signed.raw_transaction,
            )
            receipt = await self._w3.eth.wait_for_transaction_receipt(
                tx_hash, timeout=120,
            )
            if receipt["status"] != 1:
                log.warning(
                    "anchor_vpm: tx reverted vpm=%s zkba=%s tx=%s",
                    vpm_manifest_hash_hex[:16],
                    zkba_manifest_hash_hex[:16],
                    tx_hash.hex()[:16],
                )
                return (None, False)
            log.info(
                "anchor_vpm: tx=%s vpm=%s zkba=%s ts_ns=%d",
                tx_hash.hex()[:16],
                vpm_manifest_hash_hex[:16],
                zkba_manifest_hash_hex[:16],
                int(ts_ns),
            )
            return (tx_hash.hex(), True)
        except Exception as exc:
            # Match anchor_corpus_snapshot's "VPM: already anchored" /
            # "VPM: zkba not anchored" / generic-failure handling.
            err_text = str(exc)
            if "VPM: already anchored" in err_text:
                log.info(
                    "anchor_vpm: idempotent — vpm=%s already anchored",
                    vpm_manifest_hash_hex[:16],
                )
                return (None, False)
            if "VPM: zkba not anchored" in err_text:
                log.warning(
                    "anchor_vpm: cross-contract integrity check failed — "
                    "zkba=%s not anchored in AdjudicationRegistry yet; "
                    "anchor the underlying ZKBA artifact first",
                    zkba_manifest_hash_hex[:16],
                )
                return (None, False)
            log.error(
                "anchor_vpm: unexpected error vpm=%s: %s",
                vpm_manifest_hash_hex[:16], exc,
            )
            return (None, False)

    # --- Phase O3-ZKBA-TRACK1 Track 2 C7 — ZKBA artifact anchor (mirrors corpus + biometric + listing Path X) ---

    async def anchor_zkba_artifact(
        self,
        commitment_hex: str,
    ) -> "tuple[str | None, bool]":
        """Anchor a ZKBA artifact commitment via legacy recordAdjudication ABI.

        Calls recordAdjudication(deviceIdHash, poadHash, dualVeto) on the deployed
        AdjudicationRegistry contract with:
          - deviceIdHash = self._ZKBA_DEVICE_ID (constant; carries
            ZKBA attribution as the design-intent sourceType would have)
          - poadHash     = the 32-byte commitment from
                           bridge/vapi_bridge/zkba_artifact.compute_zkba_commitment()
          - dualVeto     = False (ZKBA artifacts are not adjudication verdicts)

        Returns (tx_hash_hex, True) on success; (None, False) on missing config /
        wallet error / tx revert / duplicate ("PoAd: already recorded"). Never
        raises — graceful degradation matching corpus_snapshot at Phase 237.5 D1.

        The tx_hash is permanent on-chain proof that the bridge committed to a
        specific ZKBA artifact (class + proof_weight + component hashes + ts_ns).
        Track 1 invariant of anchor_tx_hash IS NULL on zkba_artifact_log is
        LIFTED by this method's success path: caller updates the row with the
        returned tx_hash via store.update_zkba_artifact_anchor (Phase O3
        follow-up) once the anchor lands.

        Phase O3-ZKBA-TRACK1 Track 2 C7 (commit ships 2026-05-12 per Operator
        Decision Matrix D-TRACK2-C7 + plan §6 A3). Invoked by
        scripts/parallel_zkba_anchor.py when the operator's three-factor
        authorization fires the C8 ceremony.
        """
        # Phase 237.5 Path C+ kill-switch — short-circuit before any RPC call.
        if getattr(self._cfg, "chain_submission_paused", False):
            log.info(
                "anchor_zkba_artifact: chain_submission_paused=true — "
                "artifact will record on_chain_confirmed=False (kill-switch active)"
            )
            return (None, False)
        addr = getattr(self._cfg, "adjudication_registry_address", "")
        if not addr:
            log.warning(
                "anchor_zkba_artifact: adjudication_registry_address not "
                "configured — artifact will record on_chain_confirmed=False"
            )
            return (None, False)
        if self._account is None:
            log.warning(
                "anchor_zkba_artifact: self._account is None (no bridge "
                "private key loaded) — artifact will record on_chain_confirmed=False"
            )
            return (None, False)
        try:
            commitment_bytes32 = bytes.fromhex(commitment_hex.lstrip("0x"))[:32]
            commitment_bytes32 = commitment_bytes32.ljust(32, b"\x00")
        except Exception as exc:
            log.warning("anchor_zkba_artifact: bad commitment hex: %s", exc)
            return (None, False)
        _ABI = [{
            "name": "recordAdjudication", "type": "function",
            "stateMutability": "nonpayable",
            "inputs": [
                {"name": "deviceIdHash", "type": "bytes32"},
                {"name": "poadHash",     "type": "bytes32"},
                {"name": "dualVeto",     "type": "bool"},
            ],
            "outputs": [],
        }]
        try:
            contract = self._w3.eth.contract(
                address=self._w3.to_checksum_address(addr), abi=_ABI
            )
            nonce = await self._w3.eth.get_transaction_count(self._account.address)
            tx = await contract.functions.recordAdjudication(
                self._ZKBA_DEVICE_ID, commitment_bytes32, False,
            ).build_transaction({
                "from": self._account.address, "nonce": nonce,
            })
            # Dynamic gas estimate with 25% safety buffer; same pattern as
            # corpus_snapshot + biometric_snapshot for IoTeX storage-heavy ops.
            gas_estimate = await self._w3.eth.estimate_gas(tx)
            tx["gas"] = int(gas_estimate * 1.25)
            signed = self._account.sign_transaction(tx)
            tx_hash = await self._w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = await self._w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            if receipt["status"] != 1:
                log.warning(
                    "anchor_zkba_artifact: tx reverted commitment=%s tx=%s",
                    commitment_hex[:16], tx_hash.hex()[:16],
                )
                return (None, False)
            log.info(
                "anchor_zkba_artifact: tx=%s commitment=%s",
                tx_hash.hex()[:16], commitment_hex[:16],
            )
            return (tx_hash.hex(), True)
        except Exception as exc:
            _msg = str(exc)
            if "PoAd: already recorded" in _msg:
                log.info(
                    "anchor_zkba_artifact: idempotent no-op — commitment=%s "
                    "already anchored",
                    commitment_hex[:16],
                )
                return (None, False)
            log.warning(
                "anchor_zkba_artifact: anchor failed commitment=%s err=%s",
                commitment_hex[:16], _msg[:120],
            )
            return (None, False)

    # --- Phase 237-ZK-SEPPROOF — BIOMETRIC-SNAPSHOT-v1 anchor (mirrors corpus_snapshot Path X) ---

    async def anchor_biometric_snapshot(
        self,
        snapshot_commitment_hex: str,
    ) -> "tuple[str | None, bool]":
        """Anchor a BIOMETRIC-SNAPSHOT-v1 commitment via legacy recordAdjudication ABI.

        Calls recordAdjudication(deviceIdHash, poadHash, dualVeto) on the deployed
        AdjudicationRegistry contract with:
          - deviceIdHash = self._BIOMETRIC_SNAPSHOT_DEVICE_ID  (constant; carries
            BIOMETRIC_SNAPSHOT attribution as the design-intent sourceType would have)
          - poadHash     = the 32-byte snapshot_commitment from biometric_snapshot.py
          - dualVeto     = False (biometric snapshots are not adjudication verdicts)

        Returns (tx_hash_hex, True) on success; (None, False) on missing config /
        wallet error / tx revert / duplicate ("PoAd: already recorded"). Never
        raises — graceful degradation matching corpus_snapshot at Phase 237.5 D1.

        The tx_hash is permanent on-chain proof that the bridge committed to a
        specific (centroids, cov_inv, ts_ns) state. Future ZK-SEPPROOF circuits
        consume this commitment as a public input; verification asserts the
        anchor is recorded before accepting the proof.
        """
        # Phase 237.5 Path C+ kill-switch — short-circuit before any RPC call.
        if getattr(self._cfg, "chain_submission_paused", False):
            log.info(
                "anchor_biometric_snapshot: chain_submission_paused=true — "
                "snapshot will record on_chain_confirmed=False (kill-switch active)"
            )
            return (None, False)
        addr = getattr(self._cfg, "adjudication_registry_address", "")
        if not addr:
            log.warning(
                "anchor_biometric_snapshot: adjudication_registry_address not "
                "configured — snapshot will record on_chain_confirmed=False"
            )
            return (None, False)
        if self._account is None:
            log.warning(
                "anchor_biometric_snapshot: self._account is None (no bridge "
                "private key loaded) — snapshot will record on_chain_confirmed=False"
            )
            return (None, False)
        try:
            commitment_bytes32 = bytes.fromhex(snapshot_commitment_hex.lstrip("0x"))[:32]
            commitment_bytes32 = commitment_bytes32.ljust(32, b"\x00")
        except Exception as exc:
            log.warning("anchor_biometric_snapshot: bad commitment hex: %s", exc)
            return (None, False)
        _ABI = [{
            "name": "recordAdjudication", "type": "function",
            "stateMutability": "nonpayable",
            "inputs": [
                {"name": "deviceIdHash", "type": "bytes32"},
                {"name": "poadHash",     "type": "bytes32"},
                {"name": "dualVeto",     "type": "bool"},
            ],
            "outputs": [],
        }]
        try:
            contract = self._w3.eth.contract(
                address=self._w3.to_checksum_address(addr), abi=_ABI
            )
            nonce = await self._w3.eth.get_transaction_count(self._account.address)
            tx = await contract.functions.recordAdjudication(
                self._BIOMETRIC_SNAPSHOT_DEVICE_ID, commitment_bytes32, False,
            ).build_transaction({
                "from": self._account.address, "nonce": nonce,
            })
            # Same dynamic gas estimate pattern as anchor_corpus_snapshot —
            # IoTeX storage-heavy ops need 25% safety buffer above estimate.
            gas_estimate = await self._w3.eth.estimate_gas(tx)
            tx["gas"] = int(gas_estimate * 1.25)
            signed = self._account.sign_transaction(tx)
            tx_hash = await self._w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = await self._w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            if receipt["status"] != 1:
                log.warning(
                    "anchor_biometric_snapshot: tx reverted commitment=%s tx=%s",
                    snapshot_commitment_hex[:16], tx_hash.hex()[:16],
                )
                return (None, False)
            log.info(
                "anchor_biometric_snapshot: tx=%s commitment=%s",
                tx_hash.hex()[:16], snapshot_commitment_hex[:16],
            )
            return (tx_hash.hex(), True)
        except Exception as exc:
            _msg = str(exc)
            if "PoAd: already recorded" in _msg:
                log.info(
                    "anchor_biometric_snapshot: idempotent no-op — commitment=%s "
                    "already anchored",
                    snapshot_commitment_hex[:16],
                )
                return (None, False)
            log.warning(
                "anchor_biometric_snapshot: anchor failed commitment=%s err=%s",
                snapshot_commitment_hex[:16], _msg[:120],
            )
            return (None, False)

    # --- Phase 238-MARKETPLACE — LISTING-v1 anchor (mirrors biometric_snapshot Path X) ---

    async def anchor_listing_commitment(
        self,
        listing_commitment_hex: str,
    ) -> "tuple[str | None, bool]":
        """Anchor a LISTING-v1 commitment via legacy recordAdjudication ABI.

        Calls recordAdjudication(deviceIdHash, poadHash, dualVeto) on the deployed
        AdjudicationRegistry contract with:
          - deviceIdHash = self._LISTING_DEVICE_ID  (constant; carries
            LISTING attribution as the design-intent sourceType would have)
          - poadHash     = the 32-byte listing_commitment from listing_primitive.py
          - dualVeto     = False (listings are not adjudication verdicts)

        Returns (tx_hash_hex, True) on success; (None, False) on missing config /
        wallet error / tx revert / duplicate ("PoAd: already recorded"). Never
        raises — graceful degradation matching biometric_snapshot at Phase 237 Step A.

        The on-chain VAPIDataMarketplaceListings.sol extension contract reads
        AdjudicationRegistry.isRecorded(listing_commitment) to verify the
        listing's primitive composition before computing its multiplier tier.
        """
        # Phase 237.5 Path C+ kill-switch — short-circuit before any RPC call.
        if getattr(self._cfg, "chain_submission_paused", False):
            log.info(
                "anchor_listing_commitment: chain_submission_paused=true — "
                "listing will record on_chain_confirmed=False (kill-switch active)"
            )
            return (None, False)
        addr = getattr(self._cfg, "adjudication_registry_address", "")
        if not addr:
            log.warning(
                "anchor_listing_commitment: adjudication_registry_address not "
                "configured — listing will record on_chain_confirmed=False"
            )
            return (None, False)
        if self._account is None:
            log.warning(
                "anchor_listing_commitment: self._account is None (no bridge "
                "private key loaded) — listing will record on_chain_confirmed=False"
            )
            return (None, False)
        try:
            commitment_bytes32 = bytes.fromhex(listing_commitment_hex.lstrip("0x"))[:32]
            commitment_bytes32 = commitment_bytes32.ljust(32, b"\x00")
        except Exception as exc:
            log.warning("anchor_listing_commitment: bad commitment hex: %s", exc)
            return (None, False)
        _ABI = [{
            "name": "recordAdjudication", "type": "function",
            "stateMutability": "nonpayable",
            "inputs": [
                {"name": "deviceIdHash", "type": "bytes32"},
                {"name": "poadHash",     "type": "bytes32"},
                {"name": "dualVeto",     "type": "bool"},
            ],
            "outputs": [],
        }]
        try:
            contract = self._w3.eth.contract(
                address=self._w3.to_checksum_address(addr), abi=_ABI
            )
            nonce = await self._w3.eth.get_transaction_count(self._account.address)
            tx = await contract.functions.recordAdjudication(
                self._LISTING_DEVICE_ID, commitment_bytes32, False,
            ).build_transaction({
                "from": self._account.address, "nonce": nonce,
            })
            # Same dynamic gas estimate pattern as anchor_corpus_snapshot /
            # anchor_biometric_snapshot — IoTeX storage-heavy ops need 25%
            # safety buffer above estimate.
            gas_estimate = await self._w3.eth.estimate_gas(tx)
            tx["gas"] = int(gas_estimate * 1.25)
            signed = self._account.sign_transaction(tx)
            tx_hash = await self._w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = await self._w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            if receipt["status"] != 1:
                log.warning(
                    "anchor_listing_commitment: tx reverted commitment=%s tx=%s",
                    listing_commitment_hex[:16], tx_hash.hex()[:16],
                )
                return (None, False)
            log.info(
                "anchor_listing_commitment: tx=%s commitment=%s",
                tx_hash.hex()[:16], listing_commitment_hex[:16],
            )
            return (tx_hash.hex(), True)
        except Exception as exc:
            _msg = str(exc)
            if "PoAd: already recorded" in _msg:
                log.info(
                    "anchor_listing_commitment: idempotent no-op — commitment=%s "
                    "already anchored",
                    listing_commitment_hex[:16],
                )
                return (None, False)
            log.warning(
                "anchor_listing_commitment: anchor failed commitment=%s err=%s",
                listing_commitment_hex[:16], _msg[:120],
            )
            return (None, False)

    # --- Phase O0 Stream 3-prep Session 1 — AGENT_COMMIT v1 chain wrapper ---

    async def anchor_agent_commit(
        self,
        commit_hash_hex: str,
        agent_id_hex: str,
    ) -> "tuple[str | None, bool]":
        """Anchor an AGENT_COMMIT v1 commitment on AgentAdjudicationRegistry.

        Calls AgentAdjudicationRegistry.anchorAgentAction(agentId, actionType,
        actionHash) on the deployed contract with:
          - agentId    = bytes32 from agent_id_hex (Pass 2C Q9 encoding)
          - actionType = ActionType.AGENT_COMMIT (enum value 0 — sixth FROZEN-v1
                         primitive's slot in the four-entry vocabulary per
                         Pass 2C Section 4.3 + AgentAdjudicationRegistry.sol)
          - actionHash = bytes32 from commit_hash_hex (the SHA-256 output of
                         agent_commit.compute_agent_commit_hash())

        Stream 3-prep deferred-activation pattern:
          The contract address is read from cfg.agent_adjudication_registry_address.
          If the address is missing (Stream 2-deploy not yet completed because
          wallet is below the 3 IOTX threshold), this wrapper logs at INFO level
          and returns (None, False). The caller's record_agent_commit() proceeds
          to insert the row with on_chain_confirmed=False; the row remains
          locally durable and can be re-anchored once the contract is deployed.

        Honors the Phase 237.5 Path C+ chain_submission_paused kill-switch.
        Returns (tx_hash_hex, True) on success; (None, False) on missing
        config / wallet error / tx revert / duplicate (anti-replay enforced
        on-chain via AgentAdjudicationRegistry's _anchorIdByHash).

        Never raises — graceful degradation per the Phase 237.5 Path C+ pattern.
        """
        # Phase 237.5 Path C+ kill-switch — short-circuit before any RPC call
        # when CHAIN_SUBMISSION_PAUSED=true is set in bridge/.env.
        if getattr(self._cfg, "chain_submission_paused", False):
            log.info(
                "anchor_agent_commit: chain_submission_paused=true — "
                "commit will record on_chain_confirmed=False (kill-switch active)"
            )
            return (None, False)

        # Stream 3-prep deferred-activation: AgentAdjudicationRegistry is not
        # yet deployed (Stream 2-deploy gated on wallet ≥3 IOTX). When the
        # config field is empty, this is the expected Phase O0 state — log at
        # INFO and return (None, False) so the caller's local insert proceeds.
        addr = getattr(self._cfg, "agent_adjudication_registry_address", "")
        if not addr:
            log.info(
                "anchor_agent_commit: agent_adjudication_registry_address not "
                "configured (Stream 2-deploy pending) — commit will record "
                "on_chain_confirmed=False"
            )
            return (None, False)

        if self._account is None:
            log.warning(
                "anchor_agent_commit: self._account is None (no bridge "
                "private key loaded) — commit will record on_chain_confirmed=False"
            )
            return (None, False)

        try:
            commit_bytes32 = bytes.fromhex(commit_hash_hex.lstrip("0x"))[:32]
            commit_bytes32 = commit_bytes32.ljust(32, b"\x00")
            agent_bytes32 = bytes.fromhex(agent_id_hex.lstrip("0x"))[:32]
            agent_bytes32 = agent_bytes32.ljust(32, b"\x00")
        except Exception as exc:
            log.warning("anchor_agent_commit: bad hex input: %s", exc)
            return (None, False)

        # AgentAdjudicationRegistry ABI fragment for anchorAgentAction.
        # Signature: anchorAgentAction(bytes32 agentId, ActionType actionType,
        #                              bytes32 actionHash) returns (uint256 anchorId)
        # ActionType enum is uint8 on-chain.
        _ABI = [{
            "name": "anchorAgentAction", "type": "function",
            "stateMutability": "nonpayable",
            "inputs": [
                {"name": "agentId",    "type": "bytes32"},
                {"name": "actionType", "type": "uint8"},   # ActionType enum
                {"name": "actionHash", "type": "bytes32"},
            ],
            "outputs": [
                {"name": "anchorId", "type": "uint256"},
            ],
        }]
        _ACTION_TYPE_AGENT_COMMIT = 0  # AgentAdjudicationRegistry.ActionType.AGENT_COMMIT

        try:
            contract = self._w3.eth.contract(
                address=self._w3.to_checksum_address(addr), abi=_ABI
            )
            nonce = await self._w3.eth.get_transaction_count(self._account.address)
            tx = await contract.functions.anchorAgentAction(
                agent_bytes32, _ACTION_TYPE_AGENT_COMMIT, commit_bytes32,
            ).build_transaction({
                "from": self._account.address, "nonce": nonce,
            })
            # Dynamic gas estimate with 25% safety buffer per Phase 237.5 Path X
            # IoTeX gas-surprise mitigation.
            gas_estimate = await self._w3.eth.estimate_gas(tx)
            tx["gas"] = int(gas_estimate * 1.25)
            signed = self._account.sign_transaction(tx)
            tx_hash = await self._w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = await self._w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            if receipt["status"] != 1:
                log.warning(
                    "anchor_agent_commit: tx reverted commit_hash=%s tx=%s",
                    commit_hash_hex[:16], tx_hash.hex()[:16],
                )
                return (None, False)
            log.info(
                "anchor_agent_commit: tx=%s commit_hash=%s",
                tx_hash.hex()[:16], commit_hash_hex[:16],
            )
            return (tx_hash.hex(), True)
        except Exception as exc:
            _msg = str(exc)
            # AgentAdjudicationRegistry's DuplicateActionHash custom error
            # surfaces as a revert message in some web3 clients. Treat as
            # idempotent rather than failure.
            if "DuplicateActionHash" in _msg:
                log.info(
                    "anchor_agent_commit: idempotent no-op — commit_hash=%s "
                    "already anchored",
                    commit_hash_hex[:16],
                )
                return (None, False)
            log.warning(
                "anchor_agent_commit: anchor failed commit_hash=%s err=%s",
                commit_hash_hex[:16], _msg[:120],
            )
            return (None, False)

    async def anchor_pda_attestation(
        self,
        pda_commitment_hex: str,
        agent_id_hex: str,
        attestation_type: str,
    ) -> "tuple[str | None, bool]":
        """Anchor a PHYSICAL_DATA_ATTESTATION v1 commitment on
        AgentAdjudicationRegistry.

        Calls AgentAdjudicationRegistry.anchorAgentAction(agentId,
        actionType, actionHash) on the deployed contract with:
          - agentId    = bytes32 from agent_id_hex (Pass 2C Q9 encoding)
          - actionType = ActionType.PHYSICAL_DATA_ATTESTATION (enum value 1
                         — seventh FROZEN-v1 primitive's slot in the
                         four-entry vocabulary per Pass 2C Section 4.3 +
                         AgentAdjudicationRegistry.sol)
          - actionHash = bytes32 from pda_commitment_hex (the SHA-256
                         output of physical_data_attestation.compute_pda_hash())

        The `attestation_type` string parameter is informational at the
        chain wrapper layer — the on-chain discriminator is the uint8
        ActionType enum (= 1 for PHYSICAL_DATA_ATTESTATION). The
        canonical-string vocabulary distinguishing kinds of physical
        data within PDA records (BIOMETRIC_CORPUS_SNAPSHOT,
        POAC_CHAIN_INTEGRITY, TREMOR_FFT_FEATURE_VECTOR,
        FLEET_COHERENCE_OBSERVATION, HARDWARE_CERTIFICATION) is captured
        in the FROZEN PDA hash itself via attestation_type_hash and
        stored in physical_data_attestation_log.attestation_type for
        off-chain query convenience.

        Stream 3-prep deferred-activation pattern (mirrors Session 1):
          The contract address is read from cfg.agent_adjudication_registry_address.
          If the address is missing (Stream 2-deploy not yet completed
          because wallet is below the 3 IOTX threshold), this wrapper
          logs at INFO level and returns (None, False). The caller's
          insert_physical_data_attestation() proceeds to insert the row
          with on_chain_confirmed=False; the row remains locally
          durable and can be re-anchored once the contract is deployed.

        Honors the Phase 237.5 Path C+ chain_submission_paused
        kill-switch. Returns (tx_hash_hex, True) on success;
        (None, False) on missing config / wallet error / tx revert /
        duplicate (anti-replay enforced on-chain via
        AgentAdjudicationRegistry's _anchorIdByHash).

        Never raises — graceful degradation per the Phase 237.5 Path C+
        pattern.
        """
        # Phase 237.5 Path C+ kill-switch — short-circuit before any RPC call
        # when CHAIN_SUBMISSION_PAUSED=true is set in bridge/.env.
        if getattr(self._cfg, "chain_submission_paused", False):
            log.info(
                "anchor_pda_attestation: chain_submission_paused=true — "
                "attestation will record on_chain_confirmed=False (kill-switch active)"
            )
            return (None, False)

        # Stream 3-prep deferred-activation: AgentAdjudicationRegistry is not
        # yet deployed (Stream 2-deploy gated on wallet ≥3 IOTX). When the
        # config field is empty, this is the expected Phase O0 state — log at
        # INFO and return (None, False) so the caller's local insert proceeds.
        addr = getattr(self._cfg, "agent_adjudication_registry_address", "")
        if not addr:
            log.info(
                "anchor_pda_attestation: agent_adjudication_registry_address not "
                "configured (Stream 2-deploy pending) — attestation will record "
                "on_chain_confirmed=False (attestation_type=%s)",
                attestation_type,
            )
            return (None, False)

        if self._account is None:
            log.warning(
                "anchor_pda_attestation: self._account is None (no bridge "
                "private key loaded) — attestation will record on_chain_confirmed=False"
            )
            return (None, False)

        try:
            pda_bytes32 = bytes.fromhex(pda_commitment_hex.lstrip("0x"))[:32]
            pda_bytes32 = pda_bytes32.ljust(32, b"\x00")
            agent_bytes32 = bytes.fromhex(agent_id_hex.lstrip("0x"))[:32]
            agent_bytes32 = agent_bytes32.ljust(32, b"\x00")
        except Exception as exc:
            log.warning("anchor_pda_attestation: bad hex input: %s", exc)
            return (None, False)

        # AgentAdjudicationRegistry ABI fragment for anchorAgentAction.
        # Signature: anchorAgentAction(bytes32 agentId, ActionType actionType,
        #                              bytes32 actionHash) returns (uint256 anchorId)
        # ActionType enum is uint8 on-chain.
        _ABI = [{
            "name": "anchorAgentAction", "type": "function",
            "stateMutability": "nonpayable",
            "inputs": [
                {"name": "agentId",    "type": "bytes32"},
                {"name": "actionType", "type": "uint8"},   # ActionType enum
                {"name": "actionHash", "type": "bytes32"},
            ],
            "outputs": [
                {"name": "anchorId", "type": "uint256"},
            ],
        }]
        # AgentAdjudicationRegistry.ActionType.PHYSICAL_DATA_ATTESTATION
        _ACTION_TYPE_PHYSICAL_DATA_ATTESTATION = 1

        try:
            contract = self._w3.eth.contract(
                address=self._w3.to_checksum_address(addr), abi=_ABI
            )
            nonce = await self._w3.eth.get_transaction_count(self._account.address)
            tx = await contract.functions.anchorAgentAction(
                agent_bytes32,
                _ACTION_TYPE_PHYSICAL_DATA_ATTESTATION,
                pda_bytes32,
            ).build_transaction({
                "from": self._account.address, "nonce": nonce,
            })
            # Dynamic gas estimate with 25% safety buffer per Phase 237.5 Path X
            # IoTeX gas-surprise mitigation.
            gas_estimate = await self._w3.eth.estimate_gas(tx)
            tx["gas"] = int(gas_estimate * 1.25)
            signed = self._account.sign_transaction(tx)
            tx_hash = await self._w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = await self._w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            if receipt["status"] != 1:
                log.warning(
                    "anchor_pda_attestation: tx reverted pda=%s tx=%s",
                    pda_commitment_hex[:16], tx_hash.hex()[:16],
                )
                return (None, False)
            log.info(
                "anchor_pda_attestation: tx=%s pda=%s attestation_type=%s",
                tx_hash.hex()[:16], pda_commitment_hex[:16], attestation_type,
            )
            return (tx_hash.hex(), True)
        except Exception as exc:
            _msg = str(exc)
            # AgentAdjudicationRegistry's DuplicateActionHash custom error
            # surfaces as a revert message in some web3 clients. Treat as
            # idempotent rather than failure.
            if "DuplicateActionHash" in _msg:
                log.info(
                    "anchor_pda_attestation: idempotent no-op — pda=%s "
                    "already anchored",
                    pda_commitment_hex[:16],
                )
                return (None, False)
            log.warning(
                "anchor_pda_attestation: anchor failed pda=%s err=%s",
                pda_commitment_hex[:16], _msg[:120],
            )
            return (None, False)

    async def is_dual_eligible(
        self,
        device_id_hash_hex: str,
        poad_hash_hex: str,
    ) -> dict:
        """Query VAPIDualPrimitiveGate.isDualEligible() — Phase 113 view call (no gas).
        device_id_hash_hex — 64-char hex (sha256(device_id.encode()).hexdigest())
        poad_hash_hex      — 64-char hex (Phase 111 poad_registry_log.poad_hash)
        Returns {"eligible": bool, "poac_valid": bool, "poad_valid": bool}.
        Raises RuntimeError if dual_primitive_gate_address not configured.
        """
        addr = getattr(self._cfg, "dual_primitive_gate_address", "")
        if not addr:
            raise RuntimeError("is_dual_eligible: dual_primitive_gate_address not configured")
        _ABI = [{
            "name": "isDualEligible", "type": "function",
            "stateMutability": "view",
            "inputs": [
                {"name": "deviceIdHash", "type": "bytes32"},
                {"name": "poadHash",     "type": "bytes32"},
            ],
            "outputs": [
                {"name": "eligible",   "type": "bool"},
                {"name": "poac_valid", "type": "bool"},
                {"name": "poad_valid", "type": "bool"},
            ],
        }]
        contract = self._w3.eth.contract(
            address=self._w3.to_checksum_address(addr), abi=_ABI
        )
        device_id_bytes32 = bytes.fromhex(device_id_hash_hex)
        poad_hash_bytes32 = bytes.fromhex(poad_hash_hex)
        result = await contract.functions.isDualEligible(
            device_id_bytes32, poad_hash_bytes32
        ).call()
        log.debug("is_dual_eligible: device=%s poad=%s eligible=%s",
                  device_id_hash_hex[:16], poad_hash_hex[:16], result[0])
        return {
            "eligible":   bool(result[0]),
            "poac_valid": bool(result[1]),
            "poad_valid": bool(result[2]),
        }

    async def is_fully_eligible(self, device_id_bytes32_hex: str) -> bool:
        """Query VAPIProtocolLens.isFullyEligible(deviceId) — the composable single-call gate.

        Phase 3 Path B (Gameplay Workflow). Pure VIEW call (no gas, no transaction), so it is
        UNAFFECTED by CHAIN_SUBMISSION_PAUSED — the kill-switch only gates submissions, not reads.

        device_id_bytes32_hex — 64-char hex (bytes32). The lens composes PHGCredential active +
        not-suspended + no active BLOCK ruling (see bridge/vapi_bridge/KNOWN_EXTERNAL_BEHAVIORS.md
        for the four authoritative device states). Returns False (never reverts) for unknown or
        zero-padded device IDs — fail-closed by the contract's design.

        Raises RuntimeError if protocol_lens_address is not configured (caller fail-opens to an
        "unavailable" status rather than a misleading False).
        """
        addr = getattr(self._cfg, "protocol_lens_address", "")
        if not addr:
            raise RuntimeError("is_fully_eligible: protocol_lens_address not configured")
        # Path A Arc 1 C4 — inline single-function ABI superseded by the
        # module-level _VAPI_PROTOCOL_LENS_V2_ABI constant. v2 contains
        # isFullyEligible (byte-for-byte v1) + Path A additions; calling
        # the v1 function on v2 returns identical behavior.
        contract = self._w3.eth.contract(
            address=self._w3.to_checksum_address(addr), abi=_VAPI_PROTOCOL_LENS_V2_ABI,
        )
        device_id_bytes32 = bytes.fromhex(device_id_bytes32_hex)
        result = await contract.functions.isFullyEligible(device_id_bytes32).call()
        log.debug("is_fully_eligible: device=%s eligible=%s",
                  device_id_bytes32_hex[:16], bool(result))
        return bool(result)

    async def is_fully_eligible_path_a(self, device_id_bytes32_hex: str) -> bool:
        """Path A Arc 1 C4 — composable single-call Path A gate.

        Returns true iff: isFullyEligible(deviceId) AND device registered as
        Path A in the manufacturer registry AND device active. Pure VIEW
        (unaffected by CHAIN_SUBMISSION_PAUSED). Mirrors is_fully_eligible's
        async signature + fail-open posture: raises RuntimeError when the
        protocol_lens_address is unset (caller surfaces 'unavailable' rather
        than a misleading False)."""
        addr = getattr(self._cfg, "protocol_lens_address", "")
        if not addr:
            raise RuntimeError("is_fully_eligible_path_a: protocol_lens_address not configured")
        contract = self._w3.eth.contract(
            address=self._w3.to_checksum_address(addr), abi=_VAPI_PROTOCOL_LENS_V2_ABI,
        )
        device_id_bytes32 = bytes.fromhex(device_id_bytes32_hex)
        result = await contract.functions.isFullyEligible_PathA(device_id_bytes32).call()
        log.debug("is_fully_eligible_path_a: device=%s eligible=%s",
                  device_id_bytes32_hex[:16], bool(result))
        return bool(result)

    async def get_device_tier_from_lens(self, device_id_bytes32_hex: str) -> int:
        """Path A Arc 1 C4 — read the MFG-registered proof tier via the lens.
        Returns 0/1/2/3 (FROZEN per INV-MFG-002). Async + raises if lens
        unset (mirrors is_fully_eligible). Equivalent data to the SYNC
        chain.get_proof_tier (which reads MFG directly via the VMDR ABI) —
        this is the tournament-integrator convenience surface."""
        addr = getattr(self._cfg, "protocol_lens_address", "")
        if not addr:
            raise RuntimeError("get_device_tier_from_lens: protocol_lens_address not configured")
        contract = self._w3.eth.contract(
            address=self._w3.to_checksum_address(addr), abi=_VAPI_PROTOCOL_LENS_V2_ABI,
        )
        device_id_bytes32 = bytes.fromhex(device_id_bytes32_hex)
        return int(await contract.functions.getDeviceTier(device_id_bytes32).call())

    def get_device_controller_model(self, device_id) -> bytes | None:
        """Path A Arc 1 C4 — read the device's controllerModel bytes32 from
        VAPIManufacturerDeviceRegistry. SYNC (uses sync_w3 alongside the other
        VMDR view bundle). Returns None on any fault OR if address unset OR
        if the device is not registered. Caller reverse-looks-up the name
        via controller_models.name_for_hash()."""
        from .consent_categories import device_id_to_bytes32
        addr_str = getattr(self._cfg, "manufacturer_device_registry_address", "") or ""
        if not addr_str or self._sync_w3 is None:
            return None
        try:
            b32 = device_id_to_bytes32(device_id)
            addr = self._sync_w3.to_checksum_address(addr_str)
            contract = self._sync_w3.eth.contract(
                address=addr, abi=_VAPI_MANUFACTURER_DEVICE_REGISTRY_ABI,
            )
            record = contract.functions.getDevice(b32).call()
            # tuple order: pubkeyHash[0], controllerModel[1], signingPath[2],
            # proofTier[3], registeredAt[4], birthCertHash[5],
            # manufacturerWallet[6], active[7]
            cm = bytes(record[1])
            if cm == b"\x00" * 32:
                return None  # zero-init record = unregistered
            return cm
        except Exception as exc:  # noqa: BLE001 — fail-open
            log.debug("get_device_controller_model error (fail-open None): %s", exc)
            return None

    async def is_swarm_quorum_valid(self, node_addresses: list[str]) -> bool:
        """View call (no gas). Calls VAPISwarmOperatorGate.isQuorumValid(address[]).
        Raises RuntimeError if swarm_operator_gate_address not configured. Phase 130A."""
        gate_addr = getattr(self._cfg, "swarm_operator_gate_address", "")
        if not gate_addr:
            raise RuntimeError("is_swarm_quorum_valid: swarm_operator_gate_address not configured")
        _ABI = [{
            "name": "isQuorumValid", "type": "function",
            "stateMutability": "view",
            "inputs": [{"name": "nodes", "type": "address[]"}],
            "outputs": [{"type": "bool"}],
        }]
        contract = self._w3.eth.contract(
            address=self._w3.to_checksum_address(gate_addr), abi=_ABI
        )
        result = await contract.functions.isQuorumValid(node_addresses).call()
        return bool(result)

    @_gated_submission
    async def mint_vhp(
        self,
        to: str,
        device_id_hash: str,
        cert_level: int,
        consecutive_clean: int,
        confidence_score: int,
        mpc_ceremony_hash: str,
        ttl_days: int = 90,
    ) -> str:
        """Mint a VHP soulbound token on VAPIVerifiedHumanProof.sol (Phase 99C).

        Args:
            to: Recipient address (hex string)
            device_id_hash: SHA-256 of device_id as 0x-prefixed hex string
            cert_level: 1=controller, 2=controller+GSR
            consecutive_clean: Number of consecutive clean adjudications
            confidence_score: 0–10000 basis points (10000 = 100%)
            mpc_ceremony_hash: MPC ceremony hash as 0x-prefixed hex string
            ttl_days: Token TTL in days (default 90)

        Returns:
            tx_hash hex string

        Raises:
            RuntimeError if VHP_CONTRACT_ADDRESS not configured or tx reverts
        """
        import time as _time_c
        addr = getattr(self._cfg, "vhp_contract_address", "")
        if not addr:
            raise RuntimeError("mint_vhp: VHP_CONTRACT_ADDRESS not configured in bridge config")

        # Convert hex strings to bytes32
        device_id_b32 = bytes.fromhex(device_id_hash.removeprefix("0x").ljust(64, "0"))[:32]
        ceremony_b32 = bytes.fromhex(mpc_ceremony_hash.removeprefix("0x").ljust(64, "0"))[:32]

        issued_at = int(_time_c.time())
        expires_at = issued_at + ttl_days * 86400

        # VHPData struct: (bytes32, uint8, uint32, uint32, uint256, uint256, bytes32)
        abi = [{
            "name": "mint", "type": "function", "stateMutability": "nonpayable",
            "inputs": [
                {"name": "to", "type": "address"},
                {"name": "data", "type": "tuple", "components": [
                    {"name": "deviceIdHash",        "type": "bytes32"},
                    {"name": "certificationLevel",  "type": "uint8"},
                    {"name": "consecutiveClean",    "type": "uint32"},
                    {"name": "confidenceScore",     "type": "uint32"},
                    {"name": "issuedAt",            "type": "uint256"},
                    {"name": "expiresAt",           "type": "uint256"},
                    {"name": "mpcCeremonyHash",     "type": "bytes32"},
                ]},
            ],
            "outputs": [{"name": "tokenId", "type": "uint256"}],
        }]
        contract = self._w3.eth.contract(
            address=self._w3.to_checksum_address(addr), abi=abi
        )
        vhp_data = (
            device_id_b32,
            int(cert_level),
            int(consecutive_clean),
            int(confidence_score),
            issued_at,
            expires_at,
            ceremony_b32,
        )
        nonce = await self._w3.eth.get_transaction_count(self._account.address)
        tx = await contract.functions.mint(
            self._w3.to_checksum_address(to), vhp_data
        ).build_transaction({"from": self._account.address, "nonce": nonce})
        # Phase 237.5 Path X correction pattern + Session 3 VHP-mint live
        # validation 2026-05-09 (tx 0x7ebc7673... OOG'd at 150k static gas):
        # mint() writes 3 storage slots (vhpData struct + ownerOf + tokenOfAddress)
        # plus an indexed Transfer event + indexed VHPMinted event.  Real gas
        # usage measured ~155-180k including VHPData struct ABI encoding overhead.
        # Dynamic estimate × 1.25 matches the recordAdjudication / corpus_snapshot
        # pattern used elsewhere in this module.
        gas_estimate = await self._w3.eth.estimate_gas(tx)
        tx["gas"] = int(gas_estimate * 1.25)
        signed = self._account.sign_transaction(tx)
        tx_hash = await self._w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = await self._w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt.status != 1:
            raise RuntimeError(f"mint_vhp: tx reverted {tx_hash.hex()}")
        log.info(
            "mint_vhp: tx=%s to=%s cert_level=%d expires_at=%d",
            tx_hash.hex()[:16], to[:12], cert_level, expires_at,
        )
        return tx_hash.hex()

    @_gated_submission
    async def lock_stiotx_collateral(self, amount_wei: int) -> str:
        """Lock stIOTX in VAPIQuickSilverCollateral.sol (Phase 101).
        Returns tx_hash hex. Raises RuntimeError on revert.
        """
        addr = getattr(self._cfg, "quicksilver_collateral_address", None)
        if not addr:
            raise RuntimeError("quicksilver_collateral_address not configured")
        abi = [
            {"name": "lockCollateral", "type": "function",
             "inputs": [{"name": "amount", "type": "uint256"}],
             "outputs": [], "stateMutability": "nonpayable"}
        ]
        contract = self._w3.eth.contract(
            address=self._w3.to_checksum_address(addr), abi=abi
        )
        nonce = await self._w3.eth.get_transaction_count(self._account.address)
        tx = await contract.functions.lockCollateral(
            int(amount_wei)
        ).build_transaction({"from": self._account.address, "nonce": nonce, "gas": 120_000})
        signed = self._account.sign_transaction(tx)
        tx_hash = await self._w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = await self._w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt.status != 1:
            raise RuntimeError(f"lock_stiotx_collateral: tx reverted {tx_hash.hex()}")
        log.info("lock_stiotx_collateral: tx=%s amount=%d", tx_hash.hex()[:16], amount_wei)
        return tx_hash.hex()

    @_gated_submission
    async def unlock_stiotx_collateral(self) -> str:
        """Request unlock cooldown for stIOTX collateral (Phase 101)."""
        addr = getattr(self._cfg, "quicksilver_collateral_address", None)
        if not addr:
            raise RuntimeError("quicksilver_collateral_address not configured")
        abi = [
            {"name": "unlockCollateral", "type": "function",
             "inputs": [], "outputs": [], "stateMutability": "nonpayable"}
        ]
        contract = self._w3.eth.contract(
            address=self._w3.to_checksum_address(addr), abi=abi
        )
        nonce = await self._w3.eth.get_transaction_count(self._account.address)
        tx = await contract.functions.unlockCollateral(
        ).build_transaction({"from": self._account.address, "nonce": nonce, "gas": 80_000})
        signed = self._account.sign_transaction(tx)
        tx_hash = await self._w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = await self._w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt.status != 1:
            raise RuntimeError(f"unlock_stiotx_collateral: tx reverted {tx_hash.hex()}")
        log.info("unlock_stiotx_collateral: tx=%s", tx_hash.hex()[:16])
        return tx_hash.hex()

    async def is_active_stiotx_collateral(self, operator_address: str) -> bool:
        """Check if operator has active stIOTX collateral (Phase 101). Never raises."""
        addr = getattr(self._cfg, "quicksilver_collateral_address", None)
        if not addr:
            return False
        try:
            from web3 import Web3
            abi = [
                {"name": "isActiveCollateral", "type": "function",
                 "inputs": [{"name": "operator", "type": "address"}],
                 "outputs": [{"name": "", "type": "bool"}],
                 "stateMutability": "view"}
            ]
            contract = self._w3.eth.contract(
                address=self._w3.to_checksum_address(addr),
                abi=abi
            )
            return bool(await contract.functions.isActiveCollateral(
                self._w3.to_checksum_address(operator_address)
            ).call())
        except Exception:
            return False

    @_gated_submission
    async def commit_separation_ratio(
        self,
        ratio: float,
        n_sessions: int,
        n_players: int,
        players_sorted: str,
        n_consented: int,
        commit_hash_hex: str,
    ) -> str:
        """Call SeparationRatioRegistry.commitRatio(bytes32, uint256, uint32, uint32).
        Phase 163 WIF-022: commit_hash_hex already encodes n_consented in its preimage.
        Inline ABI matches Phase 153 SeparationRatioRegistry.sol commitRatio 4-arg signature.
        ~100k gas. Raises RuntimeError on missing address or revert.
        """
        _ABI = [
            {
                "inputs": [
                    {"internalType": "bytes32", "name": "commitHash",  "type": "bytes32"},
                    {"internalType": "uint256", "name": "ratioMillis", "type": "uint256"},
                    {"internalType": "uint32",  "name": "nSessions",   "type": "uint32"},
                    {"internalType": "uint32",  "name": "nPlayers",    "type": "uint32"},
                ],
                "name": "commitRatio",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function",
            }
        ]
        _addr = getattr(self._cfg, "separation_ratio_registry_address", "")
        if not _addr:
            raise RuntimeError("commit_separation_ratio: separation_ratio_registry_address not configured")
        _hash_bytes = bytes.fromhex(commit_hash_hex)[:32]
        _ratio_millis = int(ratio * 1000)
        contract = self._w3.eth.contract(
            address=self._w3.to_checksum_address(_addr),
            abi=_ABI,
        )
        acct = self._w3.eth.account.from_key(self._private_key)
        nonce = await self._w3.eth.get_transaction_count(acct.address)
        gas_price = await self._w3.eth.gas_price
        tx = contract.functions.commitRatio(
            _hash_bytes, _ratio_millis, int(n_sessions), int(n_players)
        ).build_transaction({
            "from": acct.address,
            "nonce": nonce,
            "gas": 100_000,
            "gasPrice": gas_price,
        })
        signed = acct.sign_transaction(tx)
        tx_hash = await self._w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = await self._w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt["status"] != 1:
            raise RuntimeError(f"commit_separation_ratio: tx reverted commit_hash={commit_hash_hex[:16]}…")
        return tx_hash.hex()

    @_gated_submission
    async def renew_separation_ratio_commitment(
        self,
        prev_hash_hex: str,
        new_hash_hex: str,
        ttl_days: int,
        ratio_millis: int,
        n_sessions: int,
        n_consented: int,
    ) -> str:
        """Call SeparationRatioRegistry.renewCommit(prevHash, newHash, ttlDays) (Phase 180).

        Phase 178 added renewCommit() to SeparationRatioRegistry.sol:
          - onlyOwner; ttlDays > 0 guard; anti-replay UNIQUE on newCommitHash
          - Inherits ratioMillis/nSessions/nPlayers from the previous commit
        Phase 180 new_hash preimage: SHA-256(prev_hash + ratio_str + N + N_consented + players + ttl_days + ts_ns)
        ~110k gas. Raises RuntimeError on missing address or tx revert.
        """
        _ABI = [
            {
                "inputs": [
                    {"internalType": "bytes32", "name": "prevCommitHash", "type": "bytes32"},
                    {"internalType": "bytes32", "name": "newCommitHash",  "type": "bytes32"},
                    {"internalType": "uint32",  "name": "ttlDays",        "type": "uint32"},
                ],
                "name": "renewCommit",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function",
            }
        ]
        _addr = getattr(self._cfg, "separation_ratio_registry_address", "")
        if not _addr:
            raise RuntimeError(
                "renew_separation_ratio_commitment: separation_ratio_registry_address not configured"
            )
        _prev_bytes = bytes.fromhex(prev_hash_hex.removeprefix("sha256:"))[:32]
        _new_bytes  = bytes.fromhex(new_hash_hex.removeprefix("sha256:"))[:32]
        contract = self._w3.eth.contract(
            address=self._w3.to_checksum_address(_addr),
            abi=_ABI,
        )
        acct = self._w3.eth.account.from_key(self._private_key)
        nonce = await self._w3.eth.get_transaction_count(acct.address)
        gas_price = await self._w3.eth.gas_price
        tx = contract.functions.renewCommit(
            _prev_bytes, _new_bytes, int(ttl_days)
        ).build_transaction({
            "from": acct.address,
            "nonce": nonce,
            "gas": 110_000,
            "gasPrice": gas_price,
        })
        signed = acct.sign_transaction(tx)
        tx_hash = await self._w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = await self._w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt["status"] != 1:
            raise RuntimeError(
                f"renew_separation_ratio_commitment: tx reverted new_hash={new_hash_hex[:16]}…"
            )
        return tx_hash.hex()

    @_gated_submission
    async def renew_vhp(self, token_id: int) -> str:
        """Call VAPIVerifiedHumanProof.renew(tokenId). Extends expiresAt +90 days. 60k gas.
        Phase 102: VHPRenewalAgent uses this to refresh expiring soulbound tokens.
        """
        _ABI = [
            {
                "inputs": [{"internalType": "uint256", "name": "tokenId", "type": "uint256"}],
                "name": "renew",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function",
            }
        ]
        vhp_addr = getattr(self._cfg, "vhp_contract_address", "")
        if not vhp_addr:
            raise RuntimeError("renew_vhp: vhp_contract_address not configured")
        contract = self._w3.eth.contract(
            address=self._w3.to_checksum_address(vhp_addr),
            abi=_ABI,
        )
        acct = self._w3.eth.account.from_key(self._private_key)
        nonce = await self._w3.eth.get_transaction_count(acct.address)
        gas_price = await self._w3.eth.gas_price
        tx = contract.functions.renew(token_id).build_transaction({
            "from": acct.address,
            "nonce": nonce,
            "gas": 60_000,
            "gasPrice": gas_price,
        })
        signed = acct.sign_transaction(tx)
        tx_hash = await self._w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = await self._w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt["status"] != 1:
            raise RuntimeError(f"renew_vhp: tx reverted token_id={token_id}")
        return tx_hash.hex()

    async def is_vhp_valid(self, token_id: int) -> bool:
        """Call VAPIVerifiedHumanProof.isValid(tokenId) → bool (Phase 228).

        Returns True when the token is not expired (block.timestamp < expiresAt).
        Returns False when the token is invalid or expired.
        Raises RuntimeError when vhp_contract_address is not configured.
        """
        _ABI = [
            {
                "inputs": [{"internalType": "uint256", "name": "tokenId", "type": "uint256"}],
                "name": "isValid",
                "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
                "stateMutability": "view",
                "type": "function",
            }
        ]
        vhp_addr = getattr(self._cfg, "vhp_contract_address", "")
        if not vhp_addr:
            raise RuntimeError("is_vhp_valid: vhp_contract_address not configured")
        contract = self._w3.eth.contract(
            address=self._w3.to_checksum_address(vhp_addr),
            abi=_ABI,
        )
        return bool(await contract.functions.isValid(token_id).call())

    @_gated_submission
    async def anchor_coherence(
        self,
        merkle_root_hex: str,
        agent_count: int,
        ts_ns: int,
    ) -> str:
        """Call ProtocolCoherenceRegistry.anchorCoherence(merkleRoot, agentCount, tsNs) (Phase 221).

        merkle_root_hex: 64-char hex string (no 0x prefix) of the Merkle root.
        agent_count:     Number of agents included in the Merkle tree.
        ts_ns:           Off-chain observation timestamp in nanoseconds.

        ~100k gas. Raises RuntimeError on missing address or tx revert.
        """
        _ABI = [
            {
                "inputs": [
                    {"internalType": "bytes32", "name": "merkleRoot",  "type": "bytes32"},
                    {"internalType": "uint256", "name": "agentCount",  "type": "uint256"},
                    {"internalType": "uint256", "name": "tsNs",        "type": "uint256"},
                ],
                "name": "anchorCoherence",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function",
            }
        ]
        _addr = getattr(self._cfg, "protocol_coherence_registry_address", "")
        if not _addr:
            raise RuntimeError(
                "anchor_coherence: protocol_coherence_registry_address not configured"
            )
        _root_bytes = bytes.fromhex(merkle_root_hex.lstrip("0x"))[:32]
        # Pad to 32 bytes if needed
        _root_bytes = _root_bytes.ljust(32, b'\x00')
        contract = self._w3.eth.contract(
            address=self._w3.to_checksum_address(_addr),
            abi=_ABI,
        )
        acct = self._w3.eth.account.from_key(self._private_key)
        nonce = await self._w3.eth.get_transaction_count(acct.address)
        gas_price = await self._w3.eth.gas_price
        tx = contract.functions.anchorCoherence(
            _root_bytes, int(agent_count), int(ts_ns)
        ).build_transaction({
            "from":     acct.address,
            "nonce":    nonce,
            "gas":      100_000,
            "gasPrice": gas_price,
        })
        signed = acct.sign_transaction(tx)
        tx_hash = await self._w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = await self._w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt["status"] != 1:
            raise RuntimeError(
                f"anchor_coherence: tx reverted root={merkle_root_hex[:16]}…"
            )
        return tx_hash.hex()

    async def get_latest_coherence(self) -> dict:
        """Call ProtocolCoherenceRegistry.getLatestCoherence() view (Phase 221).

        Returns dict with keys: root (hex str), ts (int), count (int).
        Raises RuntimeError when registry address is not configured.
        """
        _ABI = [
            {
                "inputs": [],
                "name": "getLatestCoherence",
                "outputs": [
                    {"internalType": "bytes32", "name": "root",  "type": "bytes32"},
                    {"internalType": "uint256", "name": "ts",    "type": "uint256"},
                    {"internalType": "uint256", "name": "count", "type": "uint256"},
                ],
                "stateMutability": "view",
                "type": "function",
            }
        ]
        _addr = getattr(self._cfg, "protocol_coherence_registry_address", "")
        if not _addr:
            raise RuntimeError(
                "get_latest_coherence: protocol_coherence_registry_address not configured"
            )
        contract = self._w3.eth.contract(
            address=self._w3.to_checksum_address(_addr),
            abi=_ABI,
        )
        root_bytes, ts_val, count_val = await contract.functions.getLatestCoherence().call()
        return {
            "root":  root_bytes.hex(),
            "ts":    int(ts_val),
            "count": int(count_val),
        }

    @_gated_submission
    async def anchor_coherence_with_provenance(
        self,
        merkle_root_hex: str,
        governance_provenance_hash_hex: str,
        agent_count: int,
        ts_ns: int,
    ) -> str:
        """Call ProtocolCoherenceRegistry.anchorCoherenceWithProvenance() (Phase 227).

        Anchors the fleet Merkle root alongside the latest governance provenance hash,
        enabling GOVERNANCE_PROVENANCE_ANCHOR_DRIFT cross-check in FSCA.

        merkle_root_hex:                64-char hex string (no 0x prefix) of the Merkle root.
        governance_provenance_hash_hex: 64-char hex string of latest governance provenance hash.
        agent_count:                    Number of agents included in the Merkle tree.
        ts_ns:                          Off-chain observation timestamp in nanoseconds.

        ~120k gas. Raises RuntimeError on missing address or tx revert.
        """
        _ABI = [
            {
                "inputs": [
                    {"internalType": "bytes32", "name": "merkleRoot",               "type": "bytes32"},
                    {"internalType": "bytes32", "name": "governanceProvenanceHash", "type": "bytes32"},
                    {"internalType": "uint256", "name": "agentCount",               "type": "uint256"},
                    {"internalType": "uint256", "name": "tsNs",                     "type": "uint256"},
                ],
                "name": "anchorCoherenceWithProvenance",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function",
            }
        ]
        _addr = getattr(self._cfg, "protocol_coherence_registry_address", "")
        if not _addr:
            raise RuntimeError(
                "anchor_coherence_with_provenance: protocol_coherence_registry_address not configured"
            )
        _root_bytes = bytes.fromhex(merkle_root_hex.lstrip("0x"))[:32].ljust(32, b'\x00')
        _prov_hex = governance_provenance_hash_hex.lstrip("0x")
        _prov_bytes = bytes.fromhex(_prov_hex.zfill(64))[:32]
        contract = self._w3.eth.contract(
            address=self._w3.to_checksum_address(_addr),
            abi=_ABI,
        )
        acct = self._w3.eth.account.from_key(self._private_key)
        nonce = await self._w3.eth.get_transaction_count(acct.address)
        gas_price = await self._w3.eth.gas_price
        tx = contract.functions.anchorCoherenceWithProvenance(
            _root_bytes, _prov_bytes, int(agent_count), int(ts_ns)
        ).build_transaction({
            "from":     acct.address,
            "nonce":    nonce,
            "gas":      120_000,
            "gasPrice": gas_price,
        })
        signed = acct.sign_transaction(tx)
        tx_hash = await self._w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = await self._w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt["status"] != 1:
            raise RuntimeError(
                f"anchor_coherence_with_provenance: tx reverted root={merkle_root_hex[:16]}…"
            )
        return tx_hash.hex()

    @_gated_submission
    async def bbg_propose(
        self,
        proposal_hash_hex: str,
        vhp_token_id: int,
    ) -> str:
        """Call VAPIBiometricGovernance.proposeWithVHP(proposalHash, vhpTokenId) (Phase 222).

        proposal_hash_hex: 64-char hex string (no 0x prefix) of the proposal SHA-256 hash.
        vhp_token_id:      Soulbound VHP token ID held by the deployer wallet.

        ~120k gas. Raises RuntimeError on missing address or tx revert.
        """
        _ABI = [
            {
                "inputs": [
                    {"internalType": "bytes32", "name": "proposalHash", "type": "bytes32"},
                    {"internalType": "uint256", "name": "vhpTokenId",   "type": "uint256"},
                ],
                "name": "proposeWithVHP",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function",
            }
        ]
        _addr = getattr(self._cfg, "bbg_contract_address", "")
        if not _addr:
            raise RuntimeError("bbg_propose: bbg_contract_address not configured")
        _hash_bytes = bytes.fromhex(proposal_hash_hex.lstrip("0x"))[:32]
        _hash_bytes = _hash_bytes.ljust(32, b'\x00')
        contract = self._w3.eth.contract(
            address=self._w3.to_checksum_address(_addr),
            abi=_ABI,
        )
        acct = self._w3.eth.account.from_key(self._private_key)
        nonce = await self._w3.eth.get_transaction_count(acct.address)
        gas_price = await self._w3.eth.gas_price
        tx = contract.functions.proposeWithVHP(
            _hash_bytes, int(vhp_token_id)
        ).build_transaction({
            "from":     acct.address,
            "nonce":    nonce,
            "gas":      120_000,
            "gasPrice": gas_price,
        })
        signed = acct.sign_transaction(tx)
        tx_hash = await self._w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = await self._w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt["status"] != 1:
            raise RuntimeError(
                f"bbg_propose: tx reverted proposal_hash={proposal_hash_hex[:16]}…"
            )
        return tx_hash.hex()

    async def bbg_check_proposal(self, proposal_hash_hex: str) -> bool:
        """Call VAPIBiometricGovernance.isProposed(proposalHash) view (Phase 222).

        Returns True if the proposal has already been submitted on-chain.
        Raises RuntimeError when bbg_contract_address is not configured.
        """
        _ABI = [
            {
                "inputs": [
                    {"internalType": "bytes32", "name": "proposalHash", "type": "bytes32"},
                ],
                "name": "isProposed",
                "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
                "stateMutability": "view",
                "type": "function",
            }
        ]
        _addr = getattr(self._cfg, "bbg_contract_address", "")
        if not _addr:
            raise RuntimeError("bbg_check_proposal: bbg_contract_address not configured")
        _hash_bytes = bytes.fromhex(proposal_hash_hex.lstrip("0x"))[:32]
        _hash_bytes = _hash_bytes.ljust(32, b'\x00')
        contract = self._w3.eth.contract(
            address=self._w3.to_checksum_address(_addr),
            abi=_ABI,
        )
        return bool(await contract.functions.isProposed(_hash_bytes).call())

    # --- Phase 237-CONSENT: VAPIConsentRegistry view calls ---
    #
    # Both methods FAIL-OPEN when consent_registry_address is unset:
    #   is_consent_valid()  → False
    #   get_consent_record() → empty dict
    # This deliberately diverges from the bbg_/dual_/swarm_ pattern (which
    # raises RuntimeError on missing address). The reason: the bridge is a
    # READER of consent state, not a writer; a missing on-chain registry
    # should not block the bridge from operating against the local
    # consent_ledger (Phase 160) which is the operational truth until deploy.

    _CONSENT_REGISTRY_ABI = [
        {
            "name": "isConsentValid",
            "type": "function",
            "stateMutability": "view",
            "inputs": [
                {"name": "gamer",    "type": "address"},
                {"name": "category", "type": "uint8"},
            ],
            "outputs": [{"name": "", "type": "bool"}],
        },
        {
            "name": "getConsentRecord",
            "type": "function",
            "stateMutability": "view",
            "inputs": [
                {"name": "gamer",    "type": "address"},
                {"name": "category", "type": "uint8"},
            ],
            "outputs": [
                {"components": [
                    {"name": "consentHash", "type": "bytes32"},
                    {"name": "grantedAt",   "type": "uint64"},
                    {"name": "expiresAt",   "type": "uint64"},
                    {"name": "revoked",     "type": "bool"},
                ], "name": "", "type": "tuple"},
            ],
        },
    ]

    async def is_consent_valid(self, gamer_address: str, category: int) -> bool:
        """Query VAPIConsentRegistry.isConsentValid(address, uint8) — Phase 237 view (no gas).

        Returns True iff the gamer has granted the category, it has not been
        revoked, and (if expiresAt != 0) the expiry has not yet passed.

        Fail-open: returns False when consent_registry_address is unset (no
        registry deployed yet) — caller must check the local consent_ledger
        as the operational truth.
        """
        addr = getattr(self._cfg, "consent_registry_address", "")
        if not addr:
            return False
        try:
            contract = self._w3.eth.contract(
                address=self._w3.to_checksum_address(addr),
                abi=self._CONSENT_REGISTRY_ABI,
            )
            checksum_gamer = self._w3.to_checksum_address(gamer_address)
            return bool(await contract.functions.isConsentValid(
                checksum_gamer, int(category)
            ).call())
        except Exception as e:
            log.debug("is_consent_valid call failed: %s", e)
            return False

    async def get_consent_record(self, gamer_address: str, category: int) -> dict:
        """Query VAPIConsentRegistry.getConsentRecord(address, uint8) — Phase 237 view.

        Returns dict {consent_hash_hex, granted_at, expires_at, revoked} or
        empty dict on missing record / unset address. Empty dict means
        "no on-chain consent state" — caller should check local consent_ledger.
        """
        addr = getattr(self._cfg, "consent_registry_address", "")
        if not addr:
            return {}
        try:
            contract = self._w3.eth.contract(
                address=self._w3.to_checksum_address(addr),
                abi=self._CONSENT_REGISTRY_ABI,
            )
            checksum_gamer = self._w3.to_checksum_address(gamer_address)
            tup = await contract.functions.getConsentRecord(
                checksum_gamer, int(category)
            ).call()
            return {
                "consent_hash_hex": tup[0].hex() if isinstance(tup[0], (bytes, bytearray)) else str(tup[0]),
                "granted_at":       int(tup[1]),
                "expires_at":       int(tup[2]),
                "revoked":          bool(tup[3]),
            }
        except Exception as e:
            log.debug("get_consent_record call failed: %s", e)
            return {}

    # --- Data Economy Arc 4: VAPIConsentManifestRegistry view call ---
    #
    # ADDITIVE to the Phase 237 bitmask surface above (separate contract,
    # separate address). Same fail-open contract as is_consent_valid /
    # get_consent_record: a missing manifest registry must NOT block the
    # bridge — the Curator packaging loop treats an absent manifest as
    # fail-closed at ITS layer (no listing), not as a chain error here.

    _CONSENT_MANIFEST_ABI = [
        {
            "name": "getManifest",
            "type": "function",
            "stateMutability": "view",
            "inputs": [{"name": "gamer", "type": "address"}],
            "outputs": [{"components": [
                {"name": "allowAggregateStats",          "type": "bool"},
                {"name": "allowSkillRankingProof",        "type": "bool"},
                {"name": "allowTrajectoryProof",          "type": "bool"},
                {"name": "allowContextPerformanceProof",  "type": "bool"},
                {"name": "allowFullSessionProof",         "type": "bool"},
                {"name": "allowAcademic",                 "type": "bool"},
                {"name": "allowGameDev",                  "type": "bool"},
                {"name": "allowEsports",                  "type": "bool"},
                {"name": "allowBrand",                    "type": "bool"},
                {"name": "allowAnonymous",                "type": "bool"},
                {"name": "minSessionsPerPackage",         "type": "uint16"},
                {"name": "coolingPeriodHours",            "type": "uint32"},
                {"name": "minPriceVapi",                  "type": "uint256"},
                {"name": "listingType",                   "type": "uint8"},
                {"name": "autonomyLevel",                 "type": "uint8"},
                # Dimension 8 (Arc 5) — VHR policy. Order must match the
                # Solidity struct declaration exactly; reordering silently
                # breaks ABI decoding of the getManifest tuple.
                {"name": "allowReplayProofs",             "type": "bool"},
                {"name": "replayHumanityThreshold",       "type": "uint8"},
                {"name": "replayQuantizationBits",        "type": "uint8"},
                {"name": "replayRequireVerdict",          "type": "bool"},
                {"name": "updatedAt",                     "type": "uint64"},
                {"name": "manifestHash",                  "type": "bytes32"},
            ], "name": "", "type": "tuple"}],
        },
        {
            "name": "hasManifest",
            "type": "function",
            "stateMutability": "view",
            "inputs": [{"name": "gamer", "type": "address"}],
            "outputs": [{"name": "", "type": "bool"}],
        },
    ]

    async def get_consent_manifest(self, gamer_address: str) -> dict:
        """Query VAPIConsentManifestRegistry.getManifest(address) — Arc 4 view (no gas).

        Returns the structured 7-dimension manifest as a dict, or an empty
        dict when the manifest registry is unset OR no manifest is stored
        (updatedAt == 0). The empty-dict case is fail-open at the chain
        layer; the Curator loop treats absence as fail-closed (no listing).
        """
        addr = getattr(self._cfg, "consent_manifest_registry_address", "")
        if not addr:
            return {}
        try:
            contract = self._w3.eth.contract(
                address=self._w3.to_checksum_address(addr),
                abi=self._CONSENT_MANIFEST_ABI,
            )
            checksum_gamer = self._w3.to_checksum_address(gamer_address)
            t = await contract.functions.getManifest(checksum_gamer).call()
            # Dimension 8 added 4 fields (indices 15-18) before updatedAt/hash,
            # shifting those to 19/20.
            if int(t[19]) == 0:  # updatedAt == 0 → no manifest set
                return {}
            mh = t[20]
            return {
                "allow_aggregate_stats":           bool(t[0]),
                "allow_skill_ranking_proof":       bool(t[1]),
                "allow_trajectory_proof":          bool(t[2]),
                "allow_context_performance_proof": bool(t[3]),
                "allow_full_session_proof":        bool(t[4]),
                "allow_academic":                  bool(t[5]),
                "allow_game_dev":                  bool(t[6]),
                "allow_esports":                   bool(t[7]),
                "allow_brand":                     bool(t[8]),
                "allow_anonymous":                 bool(t[9]),
                "min_sessions_per_package":        int(t[10]),
                "cooling_period_hours":            int(t[11]),
                "min_price_vapi":                  int(t[12]),
                "listing_type":                    int(t[13]),
                "autonomy_level":                  int(t[14]),
                # Dimension 8 (Arc 5) — VHR policy fields.
                "allow_replay_proofs":             bool(t[15]),
                "replay_humanity_threshold":       int(t[16]),
                "replay_quantization_bits":        int(t[17]),
                "replay_require_verdict":          bool(t[18]),
                "updated_at":                      int(t[19]),
                "manifest_hash":                   mh.hex() if isinstance(mh, (bytes, bytearray)) else str(mh),
            }
        except Exception as e:
            log.debug("get_consent_manifest call failed: %s", e)
            return {}

    # ------------------------------------------------------------------
    # Phase 238 Step I — Curator anchor verification view (zero gas)
    # ------------------------------------------------------------------
    #
    # The Curator Operator Initiative agent reads AdjudicationRegistry.isRecorded
    # to verify that each anchor referenced by a marketplace listing actually
    # exists on-chain — sellers cannot claim a Premium tier without all four
    # anchors recorded.  This is a pure view call (eth_call, no transaction,
    # no gas) and bypasses the chain_submission_paused kill-switch since it
    # is read-only.  Fail-open per Curator design: returns False when registry
    # address is unset or any RPC error occurs (Curator surfaces this as
    # "anchor not present" rather than blocking the review pipeline).
    #
    async def is_adjudication_recorded(self, commitment_hex: str) -> bool:
        """Query AdjudicationRegistry.isRecorded(bytes32) — view, no gas.

        Phase 238 Step I — Curator's read-only primitive for verifying that
        any of the seven prior FROZEN-v1 anchor types (GIC, WEC, VAME,
        CORPUS-SNAPSHOT, CONSENT, BIOMETRIC-SNAPSHOT, SEPPROOF, LISTING-v1)
        is recorded on the AdjudicationRegistry contract.

        Args:
            commitment_hex: 32-byte commitment hex string (with or without
                0x prefix).  Bad input → False (fail-open).

        Returns:
            bool — True iff isRecorded(bytes32) returned true.  False on:
              - adjudication_registry_address unset
              - bad hex input
              - RPC error
              - contract reverted
        """
        addr = getattr(self._cfg, "adjudication_registry_address", "")
        if not addr:
            return False
        try:
            commit_clean = commitment_hex[2:] if commitment_hex.startswith("0x") else commitment_hex
            commit_bytes = bytes.fromhex(commit_clean)
            if len(commit_bytes) != 32:
                return False
        except Exception:
            return False
        try:
            abi = [{
                "inputs": [{"name": "podHash", "type": "bytes32"}],
                "name": "isRecorded", "type": "function",
                "stateMutability": "view",
                "outputs": [{"name": "", "type": "bool"}],
            }]
            contract = self._w3.eth.contract(
                address=self._w3.to_checksum_address(addr),
                abi=abi,
            )
            return bool(await contract.functions.isRecorded(commit_bytes).call())
        except Exception as e:
            log.debug("is_adjudication_recorded call failed: %s", e)
            return False

    # ------------------------------------------------------------------
    # Phase O1 C1 — AgentScope (operational) + AgentRegistry (governance) anchors
    # ------------------------------------------------------------------
    #
    # Per V-checks 2026-05-03: deployed AgentScope at
    # 0xc694692a69bbf1cDAda87d5bc43D345C4579FF13 exposes:
    #   - getScopeRoot(bytes32 agentId) view returns (bytes32)        [selector 0xa8e82f6c]
    #   - setAgentScopeRoot(bytes32 agentId, bytes32 scopeRoot) onlyOwner  [selector 0x32a757fd]
    #   - event AgentScopeRootSet(bytes32 indexed agentId, bytes32 oldRoot, bytes32 newRoot, uint256 ts)
    #
    # Deployed AgentRegistry at 0x9548E9d17c2d40350629b1b88ff1D2c01B0414a4 exposes:
    #   - updateAgentScope(bytes32 agentId, bytes32 newScope) onlyOwner  [selector 0x906516f0]
    #   - event AgentScopeUpdated(bytes32 indexed agentId, bytes32 oldScope, bytes32 newScope)
    #
    # Per D4 + INV-OPERATOR-AGENT-001: cedar_bundle_anchor.anchor_bundle calls
    # set_agent_scope_root FIRST (operational layer), then
    # update_agent_scope_governance SECOND (governance layer).  Both inherit
    # the Phase 237.5 Path C+ chain_submission_paused kill-switch via
    # _send_tx; reads (get_agent_scope_root) bypass the kill-switch since
    # they're eth_call (no transaction).
    #
    # FAIL-CLOSED on missing address: Phase O1 cannot operate without scope
    # state, so unlike consent (read-only fail-open), these methods raise
    # RuntimeError when agent_scope_address / agent_registry_address are unset.

    _AGENT_SCOPE_ABI = [
        {
            "name": "owner", "type": "function", "stateMutability": "view",
            "inputs": [], "outputs": [{"name": "", "type": "address"}],
        },
        {
            "name": "getScopeRoot", "type": "function", "stateMutability": "view",
            "inputs": [{"name": "agentId", "type": "bytes32"}],
            "outputs": [{"name": "", "type": "bytes32"}],
        },
        {
            "name": "setAgentScopeRoot", "type": "function", "stateMutability": "nonpayable",
            "inputs": [
                {"name": "agentId",   "type": "bytes32"},
                {"name": "scopeRoot", "type": "bytes32"},
            ],
            "outputs": [],
        },
        {
            "anonymous": False, "type": "event", "name": "AgentScopeRootSet",
            "inputs": [
                {"indexed": True,  "name": "agentId", "type": "bytes32"},
                {"indexed": False, "name": "oldRoot", "type": "bytes32"},
                {"indexed": False, "name": "newRoot", "type": "bytes32"},
                {"indexed": False, "name": "ts",      "type": "uint256"},
            ],
        },
    ]

    _AGENT_REGISTRY_SCOPE_ABI = [
        {
            "name": "updateAgentScope", "type": "function", "stateMutability": "nonpayable",
            "inputs": [
                {"name": "agentId",  "type": "bytes32"},
                {"name": "newScope", "type": "bytes32"},
            ],
            "outputs": [],
        },
        {
            "anonymous": False, "type": "event", "name": "AgentScopeUpdated",
            "inputs": [
                {"indexed": True,  "name": "agentId",  "type": "bytes32"},
                {"indexed": False, "name": "oldScope", "type": "bytes32"},
                {"indexed": False, "name": "newScope", "type": "bytes32"},
            ],
        },
    ]

    @staticmethod
    def _agent_id_bytes32(agent_id_hex: str) -> bytes:
        """Accept 0x-prefixed 32-byte hex agentId; return raw bytes32."""
        s = agent_id_hex.lower()
        if s.startswith("0x"):
            s = s[2:]
        if len(s) != 64:
            raise RuntimeError(
                f"agent_id must be 32-byte (64 hex char) value, got {len(s)} chars"
            )
        return bytes.fromhex(s)

    async def get_agent_scope_root(self, agent_id_hex: str) -> bytes:
        """Phase O1 C1 — view: AgentScope.getScopeRoot(bytes32) → bytes32.

        Read-only; bypasses chain_submission_paused (no tx).  Fail-closed:
        raises RuntimeError if agent_scope_address is unset (Phase O1 cannot
        operate without scope state).  Returns 32 raw bytes (bytes32(0) if
        no scope set yet — agents at Phase O0 entry).
        """
        addr = getattr(self._cfg, "agent_scope_address", "")
        if not addr:
            raise RuntimeError(
                "get_agent_scope_root: agent_scope_address is not configured "
                "(Phase O1 cannot operate without on-chain scope state)"
            )
        agent_id_bytes = self._agent_id_bytes32(agent_id_hex)
        contract = self._w3.eth.contract(
            address=self._w3.to_checksum_address(addr),
            abi=self._AGENT_SCOPE_ABI,
        )
        result = await contract.functions.getScopeRoot(agent_id_bytes).call()
        return bytes(result)

    async def set_agent_scope_root(self, agent_id_hex: str, root_hex: str) -> dict:
        """Phase O1 C1 — owner-only: AgentScope.setAgentScopeRoot(bytes32, bytes32).

        OPERATIONAL layer (live read path used by AgentAdjudicationRegistry).
        Per INV-OPERATOR-AGENT-001, called BEFORE update_agent_scope_governance.

        Returns {tx_hash, block_number, status} on success.
        Inherits chain_submission_paused kill-switch via _send_tx chokepoint
        (Phase 237.5 Path C+).
        """
        addr = getattr(self._cfg, "agent_scope_address", "")
        if not addr:
            raise RuntimeError(
                "set_agent_scope_root: agent_scope_address is not configured"
            )
        agent_id_bytes = self._agent_id_bytes32(agent_id_hex)
        # Convert root hex (with or without 0x) to bytes32
        rs = root_hex.lower()
        if rs.startswith("0x"):
            rs = rs[2:]
        if len(rs) != 64:
            raise RuntimeError(f"root must be 32-byte hex, got {len(rs)} chars")
        root_bytes = bytes.fromhex(rs)
        contract = self._w3.eth.contract(
            address=self._w3.to_checksum_address(addr),
            abi=self._AGENT_SCOPE_ABI,
        )
        # _send_tx expects the function reference + args (not pre-constructed call).
        # Pattern matches verify_single (line 1127-1132).
        # 1.25 buffer per Phase 237.5 Path X — IoTeX testnet storage-heavy
        # patterns (mappings + structs) can exceed the 1.20 default under
        # elevated gas conditions (1000 → 2000 Gwei observed 2026-05-09).
        tx_hash_hex = await self._send_tx(
            contract.functions.setAgentScopeRoot,
            agent_id_bytes,
            root_bytes,
            gas_buffer_multiplier=1.25,
        )
        # _send_tx returns hex str; wait_for_transaction_receipt accepts hex str via to_bytes.
        receipt = await self._w3.eth.wait_for_transaction_receipt(
            bytes.fromhex(tx_hash_hex.removeprefix("0x"))
        )
        return {
            "tx_hash":      tx_hash_hex,
            "block_number": int(receipt["blockNumber"]),
            "status":       int(receipt["status"]),
        }

    async def update_agent_scope_governance(self, agent_id_hex: str, root_hex: str) -> dict:
        """Phase O1 C1 — owner-only: AgentRegistry.updateAgentScope(bytes32, bytes32).

        GOVERNANCE layer (slow, change-controlled audit commitment).  Per
        INV-OPERATOR-AGENT-001, called AFTER set_agent_scope_root.

        Returns {tx_hash, block_number, status} on success.
        """
        addr = getattr(self._cfg, "agent_registry_address", "")
        if not addr:
            raise RuntimeError(
                "update_agent_scope_governance: agent_registry_address is not configured"
            )
        agent_id_bytes = self._agent_id_bytes32(agent_id_hex)
        rs = root_hex.lower()
        if rs.startswith("0x"):
            rs = rs[2:]
        if len(rs) != 64:
            raise RuntimeError(f"root must be 32-byte hex, got {len(rs)} chars")
        root_bytes = bytes.fromhex(rs)
        contract = self._w3.eth.contract(
            address=self._w3.to_checksum_address(addr),
            abi=self._AGENT_REGISTRY_SCOPE_ABI,
        )
        # 1.25 buffer per Phase 237.5 Path X — see set_agent_scope_root above.
        tx_hash_hex = await self._send_tx(
            contract.functions.updateAgentScope,
            agent_id_bytes,
            root_bytes,
            gas_buffer_multiplier=1.25,
        )
        receipt = await self._w3.eth.wait_for_transaction_receipt(
            bytes.fromhex(tx_hash_hex.removeprefix("0x"))
        )
        return {
            "tx_hash":      tx_hash_hex,
            "block_number": int(receipt["blockNumber"]),
            "status":       int(receipt["status"]),
        }
