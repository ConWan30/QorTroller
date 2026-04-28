"""Phase O0 Stream 3-prep — AGENT_COMMIT v1, sixth FROZEN-v1 primitive.

The AGENT_COMMIT v1 primitive is the cryptographic anchor for git commits
produced by VAPI's Operator Agents (vapi-anchor-sentry, vapi-guardian).
Each commit produces a single 32-byte commitment that binds the agent's
identity, the commit's git SHA-1, the prior commit hash (chain semantics),
the repo URI, and a timestamp into a tamper-evident value anchored
on-chain via AgentAdjudicationRegistry.

Origin and design lineage:

  Pass 2A V10 (commit 6751bf9a) introduced AGENT_COMMIT v1 as the sixth
    FROZEN-v1 primitive after rejecting EAS deployment to IoTeX. The
    primitive emerged from EAS deferral specifically because git commits
    are the substrate of agent action — agents sign commits with KMS-backed
    GitHub App keys, and those commits become the protocol's record of
    what the agent did.

  Pass 2C Section 4.1 (commit b9ddeeb2) ratified the hash formula, store
    table schema, and chain wrapper signature. Sessions 5 (commit 7a4ae0d8)
    + Stream 3-prep Session 1 (this commit) implement the contract +
    bridge sides respectively.

  Decision T-Pass2C (Stream 3-prep Session 1) confirmed the
    git-commit-specific field set (agent_id, commit_sha, prev_commit_hash,
    repo_uri_sha, ts_ns) over the generic action fields language drift in
    that session's prompt. AGENT_COMMIT v1 is structurally bound to git's
    cryptographic primitives (SHA-1 commit hashes, parent-hash chain) by
    architectural intent.

  Decision DELTA-Pass2C froze INV-AGENT-COMMIT-002 as the domain tag
    literal pin (matching Phase 237.5 INV-CORPUS-002 pattern). The domain
    tag is the cryptographic identifier distinguishing AGENT_COMMIT v1
    hashes from other primitive hashes; modifying it would break every
    existing anchor's verifiability.

FROZEN FORMULA v1:

    commitment = SHA-256(
        b"VAPI-AGENT-COMMIT-v1"     (20 bytes)  — domain separation tag
        || agent_id                 (32 bytes)  — bytes32 of ioID DID + TBA binding
        || commit_sha               (20 bytes)  — git SHA-1 of the commit
        || prev_commit_hash         (32 bytes)  — chained ref; 32 zero bytes for genesis
        || repo_uri_sha             (32 bytes)  — SHA-256 of canonical repo URI
        || ts_ns_be                 (8 bytes)   — uint64 BE: agent's claimed commit ns timestamp
    )                            = 144 bytes input → SHA-256 → 32 bytes

agent_id encoding (Pass 2C Q9, FROZEN at first AgentRegistry registration):

    agent_id = keccak256(abi.encode(ioID_DID_address, ERC6551_TBA_address))

This module receives whatever bytes32 is provided; the canonical encoding
is enforced by AgentRegistry.registerAgent at agent registration time
(Phase O0 Section 6.4 work).

prev_commit_hash chain semantics:

The on-chain hash chain mirrors git's commit chain. Auditors verify that
the on-chain prev_commit_hash of commit N matches the AGENT_COMMIT v1
hash of commit N-1, providing tamper-evident commit history that an
attacker cannot rewrite without invalidating every subsequent on-chain
anchor. genesis_agent_commit() emits the first commit with
prev_commit_hash = 32 zero bytes.

Anchor destination:

The 32-byte commitment is anchored on AgentAdjudicationRegistry via
chain.anchor_agent_commit(), which submits to anchorAgentAction with
actionType=AGENT_COMMIT (enum value 0). See chain.py for the chain
wrapper. AgentAdjudicationRegistry's anti-replay tracker enforces global
uniqueness — anchoring the same commitment twice reverts.

Phase O0 status:

Stream 3-prep ships this module + chain wrapper as a deferred-activation
stub. The chain wrapper raises AgentAdjudicationRegistryNotDeployed until
Stream 2-deploy lands AgentAdjudicationRegistry on IoTeX testnet (gated on
wallet funding to ≥3 IOTX per Pass 2A V8). Until then, agent_commit.py
hash computation is fully usable for off-chain audit work; the chain
wrapper is dormant.

Any change to byte order, domain tag, or field structure requires v2 +
new tag. v1 is permanently frozen.
"""
from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from typing import Optional

# Domain tag — FROZEN literal. INV-AGENT-COMMIT-002 pins this byte string.
# Twenty bytes: "VAPI-AGENT-COMMIT-v1".
_AGENT_COMMIT_TAG = b"VAPI-AGENT-COMMIT-v1"

# Canonical repo URI for VAPI's main repo. Used by genesis_agent_commit() to
# compute repo_uri_sha. If/when VAPI's repo URL changes (or the protocol
# operates on a different repo), callers can pass an explicit repo_uri_sha
# to compute_agent_commit_hash() rather than relying on this default.
_VAPI_REPO_URI = b"https://github.com/ConWan30/vapi-prototype"


@dataclass(slots=True)
class AgentCommit:
    """Canonical AGENT_COMMIT v1 input fields.

    All bytes fields must be exact-length per the FROZEN formula:
      agent_id          : 32 bytes
      commit_sha        : 20 bytes (git SHA-1's native length)
      prev_commit_hash  : 32 bytes (32 zero bytes for genesis)
      repo_uri_sha      : 32 bytes
      ts_ns             : uint64 (0 <= ts_ns <= 0xFFFFFFFFFFFFFFFF)

    The computed hash is set after compute_agent_commit_hash() runs;
    use record_agent_commit() (in store.py) for the full lifecycle of
    "compute hash + insert into agent_commit_log + return AgentCommit
    with hash populated".
    """
    agent_id: bytes
    commit_sha: bytes
    prev_commit_hash: bytes
    repo_uri_sha: bytes
    ts_ns: int
    commit_hash: Optional[bytes] = None  # populated by compute_agent_commit_hash


def compute_agent_commit_hash(
    agent_id: bytes,
    commit_sha: bytes,
    prev_commit_hash: bytes,
    repo_uri_sha: bytes,
    ts_ns: int,
) -> bytes:
    """Compute the AGENT_COMMIT v1 commitment — FROZEN formula.

    Args:
        agent_id:          32 bytes — Pass 2C Q9 agentId encoding.
        commit_sha:        20 bytes — git SHA-1 of the commit.
        prev_commit_hash:  32 bytes — prior AGENT_COMMIT v1 hash, or
                                      32 zero bytes for genesis.
        repo_uri_sha:      32 bytes — SHA-256 of canonical repo URI.
        ts_ns:             uint64   — agent's claimed commit timestamp
                                      in nanoseconds.

    Returns:
        32-byte SHA-256 digest.

    Raises:
        ValueError on malformed inputs (length mismatch or ts_ns out of
        uint64 range).
    """
    if len(agent_id) != 32:
        raise ValueError(f"agent_id must be 32 bytes, got {len(agent_id)}")
    if len(commit_sha) != 20:
        raise ValueError(f"commit_sha must be 20 bytes (git SHA-1), got {len(commit_sha)}")
    if len(prev_commit_hash) != 32:
        raise ValueError(f"prev_commit_hash must be 32 bytes, got {len(prev_commit_hash)}")
    if len(repo_uri_sha) != 32:
        raise ValueError(f"repo_uri_sha must be 32 bytes, got {len(repo_uri_sha)}")
    if not (0 <= int(ts_ns) <= 0xFFFFFFFFFFFFFFFF):
        raise ValueError(f"ts_ns out of uint64 range: {ts_ns}")

    return hashlib.sha256(
        _AGENT_COMMIT_TAG
        + agent_id
        + commit_sha
        + prev_commit_hash
        + repo_uri_sha
        + struct.pack(">Q", int(ts_ns))
    ).digest()


def genesis_agent_commit(agent_id: bytes, ts_ns: int) -> bytes:
    """Compute the genesis (first-ever) AGENT_COMMIT v1 commitment.

    Genesis commit has commit_sha = 20 zero bytes (no actual git commit
    has been signed yet) and prev_commit_hash = 32 zero bytes (no prior
    chain link). repo_uri_sha is computed from the canonical VAPI repo URI.

    Genesis is the seed of the on-chain hash chain. Subsequent commits
    pass the genesis output as their prev_commit_hash, forming the
    chain.

    Args:
        agent_id:  32 bytes — bytes32 agentId of the agent making the
                              first commit.
        ts_ns:     uint64   — the agent's claimed genesis timestamp.

    Returns:
        32-byte SHA-256 digest.
    """
    return compute_agent_commit_hash(
        agent_id=agent_id,
        commit_sha=b"\x00" * 20,
        prev_commit_hash=b"\x00" * 32,
        repo_uri_sha=hashlib.sha256(_VAPI_REPO_URI).digest(),
        ts_ns=ts_ns,
    )


def repo_uri_sha_from_uri(repo_uri: str | bytes) -> bytes:
    """Compute the canonical repo_uri_sha for a given repo URI string.

    SHA-256 of the URI bytes. Convenience wrapper for callers that have
    a repo URI string and want the bytes32 digest required by
    compute_agent_commit_hash().

    Args:
        repo_uri:  Either str (utf-8 encoded internally) or bytes.

    Returns:
        32-byte SHA-256 digest of the URI bytes.
    """
    if isinstance(repo_uri, str):
        repo_uri = repo_uri.encode("utf-8")
    return hashlib.sha256(repo_uri).digest()
