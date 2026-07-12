"""Retina Phase 3 — Poseidon events_root (off-chain, ZK-prep).

Canonical event list → BN254 field elements → Poseidon-2 chain (circomlibjs
via ``retina_zk_artifacts/compute_retina_events_root.js``). Distinct from the
Phase 2 SHA-256 sorted-hash root in ``retina_state_commitment.compute_events_root``.

Full in-circuit Groth16 verification is deferred — this module pins the
off-chain commitment math that a future ``VAPIRetinaEventsRoot.circom`` would
prove.
"""
from __future__ import annotations

import hashlib
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

log = logging.getLogger(__name__)

EVENT_LINE_DOMAIN = b"VAPI-RETINA-EVENT-LINE-v1"
EVENTS_ROOT_SCHEME_POSEIDON_V1 = "poseidon_v1"
EVENTS_ROOT_SCHEME_SHA256_V1 = "sha256_v1"

BN254_PRIME = (
    21888242871839275222246405745257275088548364400416034343698204186575808495617
)

_ZK_ARTIFACTS_DIR = Path(__file__).resolve().parent / "retina_zk_artifacts"
_POSEIDON_CHAIN_SCRIPT = _ZK_ARTIFACTS_DIR / "compute_retina_events_root.js"

_PoseidonChainFn = Callable[[list[int]], bytes]


def canonical_event_lines(events: Sequence[Mapping[str, Any]]) -> list[str]:
    """Sorted canonical JSON lines — order-independent over the event list."""
    if not events:
        return []
    lines = [
        json.dumps(dict(e), sort_keys=True, separators=(",", ":"))
        for e in events
    ]
    lines.sort()
    return lines


def event_line_to_field_element(line: str) -> int:
    """Map one canonical event line to a BN254 field element (SHA-256 mod p)."""
    digest = hashlib.sha256(EVENT_LINE_DOMAIN + line.encode("utf-8")).digest()
    return int.from_bytes(digest, "big") % BN254_PRIME


def event_field_elements(events: Sequence[Mapping[str, Any]]) -> list[int]:
    """Field elements for Poseidon-2 chain input (empty → single zero element)."""
    lines = canonical_event_lines(events)
    if not lines:
        return [0]
    return [event_line_to_field_element(line) for line in lines]


def _resolve_node_executable() -> str:
    if sys.platform == "win32":
        for candidate in ("node.exe", "node"):
            try:
                subprocess.run(
                    [candidate, "--version"],
                    capture_output=True,
                    check=True,
                    timeout=5,
                )
                return candidate
            except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
                continue
        return "node"
    return "node"


def _default_poseidon_chain(field_elements: list[int]) -> bytes:
    node = _resolve_node_executable()
    payload = json.dumps(
        {"field_elements": [str(x) for x in field_elements]},
        separators=(",", ":"),
    )
    proc = subprocess.run(
        [node, str(_POSEIDON_CHAIN_SCRIPT)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=15,
        cwd=str(_ZK_ARTIFACTS_DIR),
        check=False,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()[:300]
        raise RuntimeError(f"Poseidon helper exit {proc.returncode}: {err}")
    out = json.loads(proc.stdout)
    return bytes.fromhex(str(out["events_root_hex"]))


# Module-level injectable backend (tests pin golden vectors without node).
_poseidon_chain_fn: _PoseidonChainFn | None = None


def set_poseidon_chain_fn(fn: _PoseidonChainFn | None) -> None:
    """Test hook — inject deterministic Poseidon chain backend."""
    global _poseidon_chain_fn
    _poseidon_chain_fn = fn


def compute_events_root_poseidon(
    events: Sequence[Mapping[str, Any]],
    *,
    chain_fn: _PoseidonChainFn | None = None,
) -> bytes:
    """32-byte Poseidon-2 chain root over canonical event field elements."""
    elems = event_field_elements(events)
    if not _POSEIDON_CHAIN_SCRIPT.is_file():
        raise RuntimeError(f"missing Poseidon helper: {_POSEIDON_CHAIN_SCRIPT}")
    fn = chain_fn or _poseidon_chain_fn or _default_poseidon_chain
    return fn(elems)


def ordered_event_field_elements(events: Sequence[Mapping[str, Any]]) -> list[int]:
    """Field elements in EMISSION ORDER (no sort) - the order-preserving variant for the
    replayable ``retina.event/0.1`` JSON-Lines stream (TRA-1 F-TRA0-1). Each event is
    canonicalized (sorted keys) individually, but the LIST order is preserved. Empty -> [0]."""
    if not events:
        return [0]
    return [
        event_line_to_field_element(
            json.dumps(dict(e), sort_keys=True, separators=(",", ":"))
        )
        for e in events
    ]


def compute_events_root_poseidon_ordered(
    events: Sequence[Mapping[str, Any]],
    *,
    chain_fn: _PoseidonChainFn | None = None,
) -> bytes:
    """Order-PRESERVING 32-byte Poseidon-2 chain root (TRA-1 F-TRA0-1): commits the events in
    emission order, matching the standard's replayable stream. Distinct from the
    order-independent ``compute_events_root_poseidon`` (which sorts to a set commitment).
    Only requires the node Poseidon helper when the default backend is actually used."""
    elems = ordered_event_field_elements(events)
    fn = chain_fn or _poseidon_chain_fn or _default_poseidon_chain
    if fn is _default_poseidon_chain and not _POSEIDON_CHAIN_SCRIPT.is_file():
        raise RuntimeError(f"missing Poseidon helper: {_POSEIDON_CHAIN_SCRIPT}")
    return fn(elems)


def events_root_hex(root: bytes) -> str:
    if len(root) != 32:
        raise ValueError(f"events_root must be 32 bytes, got {len(root)}")
    return root.hex()
