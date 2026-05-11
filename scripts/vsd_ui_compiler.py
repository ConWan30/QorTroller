"""Phase O3-ZKBA-TRACK1 Stream Z3 — Deterministic VSD UI Compiler skeleton.

VBDIP-0002 §9 deterministic compilation invariant:

    Given the same canonical inputs and compiler version, the output
    artifact hash must be stable. If any input changes, the output
    hash must change.

Hard constraints (Stream Z3 V-checks enforce):
  - No wall-clock: no `datetime`, no `time` (apart from `time.time`-free
    paths; we deliberately avoid `import time` to satisfy V-check via grep)
  - No randomness: no `random`
  - No network: no `urllib`, `requests`, `socket`, `http.client`
  - No mutable web fonts / external CDNs: caller-supplied HTML body MUST
    be self-contained
  - Sorted-key canonical JSON at every input boundary
  - Output file path is deterministic-from-inputs (commitment_hex-named)

Manifest schema string: `vapi-zkba-manifest-v1` (FROZEN at v1.0; pinned
by Stream Z8 INV-ZKBA-003).

Compiler version: 0.1.0 (pinned at v1.0; bump only with manifest schema
v2 transition).

This module is import-safe AND CLI-invocable (no top-level side effects).
The Z4 GIC Continuity Ledger artifact builder imports `compile_artifact`
and supplies a class-specific HTML renderer callback.

Author: VAPI Architect (bridge wallet 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692)
Date: 2026-05-10
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Callable

# Add bridge/ to sys.path so we can import the ZKBA primitive.  This is the
# only import dependency the compiler has on the VAPI codebase — the
# primitive defines ZKBAClass + ProofWeightClass which the manifest commits.
_BRIDGE_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "bridge"))
if _BRIDGE_DIR not in sys.path:
    sys.path.insert(0, _BRIDGE_DIR)

from vapi_bridge.zkba_artifact import ZKBAClass, ProofWeightClass  # noqa: E402


# ---------------------------------------------------------------------------
# Compiler constants — FROZEN at v1.0; do not modify without manifest v2 bump
# ---------------------------------------------------------------------------

_COMPILER_NAME = "vsd_ui_compiler"
_COMPILER_VERSION = "0.1.0"
_MANIFEST_SCHEMA = "vapi-zkba-manifest-v1"   # FROZEN; pinned by INV-ZKBA-003


@dataclass(frozen=True, slots=True)
class ZKBAManifest:
    """Projection manifest emitted alongside every compiled artifact.

    Frozen + slotted; serialized via canonical_json() into <commit>.manifest.json
    next to the artifact's <commit>.html.
    """
    schema:                str   # always _MANIFEST_SCHEMA
    zkba_class:            int   # ZKBAClass IntEnum value
    proof_weight:          int   # ProofWeightClass IntEnum value
    output_path:           str   # POSIX-style path under output_dir
    output_hash_hex:       str   # SHA-256 of HTML body bytes (64 lowercase hex)
    input_commitment_hex:  str   # SHA-256 of canonical_json(inputs)
    compiler_version:      str   # _COMPILER_VERSION
    ts_ns:                 int   # uint64; sourced from inputs (no wall-clock)


# ---------------------------------------------------------------------------
# Deterministic helpers
# ---------------------------------------------------------------------------

def canonical_json(obj) -> bytes:
    """Sorted-key UTF-8 JSON encoding for deterministic byte output.

    `separators=(",", ":")` removes whitespace. `sort_keys=True` removes
    dict-iteration-order dependency. `ensure_ascii=False` preserves Unicode
    in the output but the result is still deterministic per input.
    """
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def compute_input_commitment(inputs: dict) -> str:
    """SHA-256 of canonical_json(inputs) as a 64-char lowercase hex string."""
    return hashlib.sha256(canonical_json(inputs)).hexdigest()


# ---------------------------------------------------------------------------
# compile_artifact — public API
# ---------------------------------------------------------------------------

def compile_artifact(
    *,
    zkba_class: ZKBAClass,
    proof_weight: ProofWeightClass,
    inputs: dict,
    output_dir: Path,
    html_renderer: Callable[[dict], str],
) -> ZKBAManifest:
    """Compile a ZKBA visual projection artifact deterministically.

    The caller supplies an `html_renderer` callback that produces an HTML
    body string from the input dict. The renderer MUST be deterministic:
    same dict in -> same string out. No wall-clock reads, no random IDs,
    no network fetches. The compiler does not enforce this in v1.0; v1.1
    may add a wrapped-renderer sandbox.

    The compiler:
      1. Computes input_commitment_hex = SHA-256(canonical_json(inputs))
      2. Invokes html_renderer(inputs) -> str
      3. Writes UTF-8 HTML to `<output_dir>/<input_commit>.html`
      4. Computes output_hash_hex = SHA-256 of the HTML bytes
      5. Writes the projection manifest to `<output_dir>/<input_commit>.manifest.json`

    File naming is deterministic-from-inputs: the same inputs always write
    to the same path, so recompilation is idempotent at the filesystem level.

    Args:
        zkba_class:    Artifact class (1-of-7 per VBDIP-0002 §5).
        proof_weight:  Proof-weight class (1-of-6 per VBDIP-0002 §6).
        inputs:        Deterministic input dict; serialized via canonical_json.
                       Must contain a "ts_ns" key (int uint64).
        output_dir:    Directory under which the artifact + manifest are written.
                       Created if it does not exist.
        html_renderer: Deterministic callable(inputs: dict) -> str.

    Returns:
        ZKBAManifest describing the emitted artifact.

    Raises:
        TypeError:  if zkba_class or proof_weight is not the expected IntEnum.
        ValueError: if `inputs["ts_ns"]` is missing or not a uint64.
        OSError:    if the output directory cannot be created or written.
    """
    if not isinstance(zkba_class, ZKBAClass):
        raise TypeError(
            f"zkba_class must be ZKBAClass; got {type(zkba_class).__name__}"
        )
    if not isinstance(proof_weight, ProofWeightClass):
        raise TypeError(
            f"proof_weight must be ProofWeightClass; got {type(proof_weight).__name__}"
        )
    if not isinstance(inputs, dict):
        raise TypeError(
            f"inputs must be a dict; got {type(inputs).__name__}"
        )
    if "ts_ns" not in inputs:
        raise ValueError("inputs missing required key 'ts_ns'")
    ts_ns_val = inputs["ts_ns"]
    if not isinstance(ts_ns_val, int) or ts_ns_val < 0 or ts_ns_val > 0xFFFFFFFFFFFFFFFF:
        raise ValueError(
            f"inputs['ts_ns'] must be uint64; got {type(ts_ns_val).__name__} = {ts_ns_val!r}"
        )

    input_commit = compute_input_commitment(inputs)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Deterministic HTML body — caller-provided renderer
    html_body = html_renderer(inputs)
    if not isinstance(html_body, str):
        raise TypeError(
            f"html_renderer must return str; got {type(html_body).__name__}"
        )
    output_bytes = html_body.encode("utf-8")
    output_hash = hashlib.sha256(output_bytes).hexdigest()

    # Deterministic filenames keyed by input commitment
    output_path = output_dir / f"{input_commit}.html"
    output_path.write_bytes(output_bytes)

    manifest = ZKBAManifest(
        schema=_MANIFEST_SCHEMA,
        zkba_class=int(zkba_class),
        proof_weight=int(proof_weight),
        output_path=str(output_path).replace("\\", "/"),
        output_hash_hex=output_hash,
        input_commitment_hex=input_commit,
        compiler_version=_COMPILER_VERSION,
        ts_ns=int(ts_ns_val),
    )

    manifest_path = output_dir / f"{input_commit}.manifest.json"
    manifest_path.write_bytes(canonical_json(asdict(manifest)))

    return manifest


# ---------------------------------------------------------------------------
# CLI entry — no-op stub at v1.0 (Z4 + future artifact builders invoke
# compile_artifact() directly with class-specific renderers).
# ---------------------------------------------------------------------------

def _cli_main() -> int:
    """No-op CLI entry — print version and exit 0.  Future artifacts will
    register CLI subcommands here; Z3 ships skeleton only."""
    print(f"{_COMPILER_NAME} v{_COMPILER_VERSION}")
    print(f"manifest schema: {_MANIFEST_SCHEMA}")
    print("Z3 skeleton; invoke artifact-specific builders (e.g., "
          "scripts/zkba_compile_gic_ledger.py) for actual compilation.")
    return 0


if __name__ == "__main__":
    sys.exit(_cli_main())
