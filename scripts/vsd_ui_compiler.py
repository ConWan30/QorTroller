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
import re
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
# Phase O4-VPM-INTEGRATION Stream A.0 — compile_vpm_artifact()
#
# Parallel public API to compile_artifact() above. Distinct in that:
#   1. Emits under a DISTINCT artifact schema `vapi-vpm-artifact-v1` — separate
#      from the existing `vapi-zkba-manifest-v1` (ZKBA projection) and from
#      the wrapper schema `vapi-vpm-manifest-v1` (VPM wrapper at
#      scripts/vsd_vpm_wrapper.py). Three distinct schemas in the Layer 7
#      stack: ZKBA manifest (compile_artifact output) → VPM wrapper (wraps
#      ZKBA manifest) → VPM artifact (compile_vpm_artifact output, references
#      both).
#   2. Enforces VBDIP-0002 Appendix B compiler discipline AT EMISSION TIME
#      via post-render static guards (no external resource loading, no
#      runtime network, no wall-clock, no randomness, inline-only).
#      Violations raise VPMComplianceError before the HTML is written to disk.
#   3. Verifies the 9-field Integrity Label per Appendix B §B.5 is visible
#      in the emitted DOM (presence + all 9 required field markers).
#   4. References the underlying ZKBA manifest hash so a downstream verifier
#      can confirm the VPM was compiled over the expected ZKBA projection.
#
# This is the foundation for the 4 internal projection compilers (Stream A.1)
# + 2 consumer-facing compilers (Stream A.2) + 4 draft manifests (Stream A.3)
# per Phase_O4_VPM_Integration_Plan.md §3.
# ---------------------------------------------------------------------------

_VPM_ARTIFACT_SCHEMA = "vapi-vpm-artifact-v1"  # FROZEN; distinct from ZKBA + VPM-wrapper schemas
_VPM_WRAPPER_SCHEMA_REF = "vapi-vpm-manifest-v1"  # reference to the wrapper schema this compiler composes with


# Required 9 fields per VBDIP-0002 Appendix B §B.5 / VBDIP-0002A §5 Integrity
# Nutrition Label. The compiler asserts each field marker appears in the
# emitted HTML; renderers MUST use the `data-vpm-field="<name>"` attribute on
# the element rendering each field's value.
_VPM_INTEGRITY_LABEL_FIELDS = (
    "proof_type",
    "capture_mode",
    "raw_biometrics_exposed",
    "consent_active",
    "zk_verified",
    "on_chain_anchor",
    "proof_weight",
    "revocation_status",
    "limitations",
)


# FROZEN VPM visual state values per VBDIP-0002 §B.5. The compile_vpm_artifact()
# entry-point validates `visual_state` against this set. Mirrors the same
# 6-element enum FROZEN at scripts/vsd_vpm_wrapper.py:VPMVisualState; reproduced
# here as plain strings so the compiler can run without importing the wrapper
# module (the compiler is a leaf dependency of the wrapper, not the reverse).
_VPM_VISUAL_STATES = (
    "live",
    "dry-run",
    "emulated",
    "frozen-disabled",
    "revoked",
    "unverified",
)


# FROZEN VPM capture mode values per VBDIP-0002A §4 wrapper draft schema +
# VPMCaptureMode in scripts/vsd_vpm_wrapper.py. 5-element enum.
_VPM_CAPTURE_MODES = (
    "live",
    "dry-run",
    "emulated",
    "demo",
    "frozen-disabled",
)


# HTML compiler-discipline static guards. These patterns are FORBIDDEN in
# emitted VPM HTML per Phase O4 plan §3 Stream A.0 compiler discipline items
# 1, 2, 5. Each entry is (regex, human-readable violation description).
_FORBIDDEN_HTML_PATTERNS = (
    (re.compile(r"https?://", re.IGNORECASE),
     "external URL (no https?:// in self-contained VPM)"),
    (re.compile(r"<link\b[^>]*\brel\s*=", re.IGNORECASE),
     "external resource <link rel=> tag"),
    (re.compile(r"<script\b[^>]*\bsrc\s*=", re.IGNORECASE),
     "external script src"),
    (re.compile(r"@import\b", re.IGNORECASE),
     "CSS @import (external stylesheet)"),
    (re.compile(r"<iframe\b[^>]*\bsrc\s*=", re.IGNORECASE),
     "iframe with src (VPMs are self-contained — no nested frames)"),
    (re.compile(r"<img\b[^>]*\bsrc\s*=\s*[\"']?(?!data:)", re.IGNORECASE),
     "img with non-data: src (must be inline data: URI)"),
    (re.compile(r"@font-face\b", re.IGNORECASE),
     "@font-face declaration (system-monospace only per Stream A.0 item 2)"),
)


# JavaScript compiler-discipline static guards. FORBIDDEN per Phase O4 plan
# §3 Stream A.0 items 3, 4, 5 (no wall-clock, no randomness, no network).
_FORBIDDEN_JS_PATTERNS = (
    (re.compile(r"\bfetch\s*\("),
     "fetch() call (no runtime network)"),
    (re.compile(r"\bXMLHttpRequest\b"),
     "XMLHttpRequest reference (no runtime network)"),
    (re.compile(r"\bnew\s+WebSocket\b"),
     "new WebSocket(...) (no runtime network)"),
    (re.compile(r"\bnew\s+EventSource\b"),
     "new EventSource(...) (no runtime network)"),
    (re.compile(r"\bMath\.random\s*\("),
     "Math.random() (no runtime randomness)"),
    (re.compile(r"\bcrypto\.getRandomValues\b"),
     "crypto.getRandomValues (no runtime randomness)"),
    (re.compile(r"\bDate\.now\s*\("),
     "Date.now() (no runtime wall-clock)"),
    (re.compile(r"\bnew\s+Date\s*\(\s*\)"),
     "new Date() with no arg (no runtime wall-clock)"),
    (re.compile(r"\bperformance\.now\s*\("),
     "performance.now() (no runtime wall-clock)"),
)


class VPMComplianceError(ValueError):
    """Raised when emitted VPM HTML violates compiler discipline per
    VBDIP-0002 Appendix B §B.5/B.6 + Phase O4 plan §3 Stream A.0 items 1-10.

    Surfaces a multi-line message enumerating all detected violations so the
    renderer author can fix them in one pass rather than iteratively.
    """


@dataclass(frozen=True, slots=True)
class VPMArtifactManifest:
    """VPM artifact projection manifest emitted alongside compiled VPM HTML.

    Companion to ZKBAManifest above: that one describes a raw ZKBA projection
    artifact; this one describes a VPM artifact (a stakeholder-facing wrapper
    over a ZKBA projection). Frozen + slotted; serialized via canonical_json()
    into `<input_commit>.vpm.manifest.json` next to the artifact's HTML.

    The `zkba_manifest_hash` field binds the VPM to a specific underlying
    ZKBA projection; downstream verifiers reproduce the ZKBA compile then
    confirm the SHA-256 of the ZKBA manifest's canonical bytes matches this
    field. This is the cryptographic composition link: VPM artifact →
    (vapi-vpm-manifest-v1 wrapper) → ZKBA manifest → ZKBA primitive.
    """
    schema:                   str   # always _VPM_ARTIFACT_SCHEMA
    vpm_id:                   str   # registered VPM identifier (VBDIP-0002A §10) or internal-only
    zkba_class:               int   # ZKBAClass IntEnum value of the underlying ZKBA projection
    proof_weight:             int   # ProofWeightClass IntEnum value
    visual_state:             str   # 1-of-6 _VPM_VISUAL_STATES
    capture_mode:             str   # 1-of-5 _VPM_CAPTURE_MODES
    integrity_label_hash_hex: str   # SHA-256 of canonical_json(integrity_label_dict)
    wrapper_schema:           str   # always _VPM_WRAPPER_SCHEMA_REF
    zkba_manifest_hash_hex:   str   # SHA-256 of the underlying ZKBA manifest's canonical bytes
    output_path:              str   # POSIX-style path under output_dir
    output_hash_hex:          str   # SHA-256 of HTML body bytes (64 lowercase hex)
    input_commitment_hex:     str   # SHA-256 of canonical_json(inputs)
    compiler_version:         str   # _COMPILER_VERSION (pinned)
    ts_ns:                    int   # uint64; sourced from inputs (no wall-clock)


def _enforce_vpm_compiler_discipline(html_body: str) -> None:
    """Static guard pass over emitted HTML. Raises VPMComplianceError on the
    first detected violation set (collects all violations into one error so
    the renderer author can fix the whole batch in one revision)."""
    violations: list[str] = []
    for pattern, description in _FORBIDDEN_HTML_PATTERNS:
        if pattern.search(html_body):
            violations.append(description)
    for pattern, description in _FORBIDDEN_JS_PATTERNS:
        if pattern.search(html_body):
            violations.append(description)
    if violations:
        raise VPMComplianceError(
            "Emitted VPM HTML violates compiler discipline (Phase O4 plan "
            "§3 Stream A.0 items 1-6):\n  - " + "\n  - ".join(violations)
        )


def _verify_integrity_label_in_dom(html_body: str) -> None:
    """Phase O4 plan §3 Stream A.0 item 9 — every VPM HTML MUST render a
    visible 9-field Integrity Label.

    Static enforcement:
      1. The string `class="vpm-integrity-label"` (or single-quoted form)
         must appear at least once.
      2. Each of the 9 required field markers (e.g. `data-vpm-field="proof_type"`)
         must appear at least once.

    Raises VPMComplianceError listing all missing markers."""
    # Marker 1: container present
    if ('class="vpm-integrity-label"' not in html_body
            and "class='vpm-integrity-label'" not in html_body):
        raise VPMComplianceError(
            "Emitted VPM HTML missing required Integrity Label container: "
            "expected <div class=\"vpm-integrity-label\"> (or single-quoted form). "
            "Per Phase O4 plan §3 Stream A.0 item 9 + VBDIP-0002 Appendix B §B.5."
        )
    # Marker 2: each of 9 fields present
    missing: list[str] = []
    for field_name in _VPM_INTEGRITY_LABEL_FIELDS:
        # Accept both double- and single-quoted attribute forms.
        marker_dq = f'data-vpm-field="{field_name}"'
        marker_sq = f"data-vpm-field='{field_name}'"
        if marker_dq not in html_body and marker_sq not in html_body:
            missing.append(field_name)
    if missing:
        raise VPMComplianceError(
            "Emitted VPM HTML missing required Integrity Label field "
            "marker(s) (per VBDIP-0002 Appendix B §B.5 9-field set):\n  - "
            + "\n  - ".join(f'data-vpm-field="{f}"' for f in missing)
        )


def compile_vpm_artifact(
    *,
    vpm_id: str,
    zkba_class: ZKBAClass,
    proof_weight: ProofWeightClass,
    visual_state: str,
    capture_mode: str,
    integrity_label: dict,
    zkba_manifest_hash_hex: str,
    inputs: dict,
    output_dir: Path,
    html_renderer: Callable[[dict], str],
) -> VPMArtifactManifest:
    """Compile a VPM (Verified Projection Media) artifact deterministically
    under strict Phase O4 compiler discipline.

    Sibling of compile_artifact() above. The compile_artifact() entry-point
    produces a raw ZKBA projection (manifest schema 'vapi-zkba-manifest-v1');
    this entry-point produces a VPM artifact (manifest schema
    'vapi-vpm-artifact-v1') that wraps a ZKBA projection with an Integrity
    Label, a declared visual state, and audience context.

    The compiler enforces (post-render, before disk write):
      1. The emitted HTML contains no external resource references
         (no https?://, no <link rel=>, no <script src=>, no @import,
         no <iframe src=>, no <img src> outside data: URIs, no @font-face).
      2. The emitted HTML contains no runtime network calls
         (no fetch, no XMLHttpRequest, no new WebSocket, no new EventSource).
      3. The emitted HTML contains no runtime randomness
         (no Math.random, no crypto.getRandomValues).
      4. The emitted HTML contains no runtime wall-clock reads
         (no Date.now, no new Date() with no arg, no performance.now).
      5. The emitted HTML contains a visible 9-field Integrity Label
         under `<... class="vpm-integrity-label">` with each of the 9
         required `data-vpm-field="<name>"` markers present.

    Two-build byte-stable determinism follows from the same canonical_json
    + caller-supplied ts_ns + deterministic html_renderer contract that
    compile_artifact() obeys.

    Args:
        vpm_id:                  Registered VPM identifier (VBDIP-0002A §10) or
                                 internal-only ID (e.g. 'HONESTY-BOARD-v1',
                                 'AGENT-REVIEW-v1', 'CDRR-DAG-v1').
        zkba_class:              ZKBAClass IntEnum value of the underlying ZKBA
                                 projection this VPM wraps.
        proof_weight:            ProofWeightClass IntEnum value.
        visual_state:            One of _VPM_VISUAL_STATES; declares the visual
                                 honesty state per VBDIP-0002 §B.5.
        capture_mode:            One of _VPM_CAPTURE_MODES; declares capture
                                 provenance per VBDIP-0002A §4.
        integrity_label:         Dict with the 9 Integrity Nutrition Label
                                 fields per VBDIP-0002 §B.5 (renderer is
                                 responsible for surfacing each one in the
                                 DOM with the data-vpm-field marker).
        zkba_manifest_hash_hex:  64-char lowercase hex SHA-256 of the
                                 underlying ZKBA manifest's canonical bytes;
                                 binds this VPM to a specific projection.
        inputs:                  Deterministic input dict; must contain
                                 "ts_ns" (uint64). Serialized into
                                 input_commitment_hex.
        output_dir:              Directory under which artifact + manifest
                                 written. Created if missing.
        html_renderer:           Deterministic callable(inputs) -> str.

    Returns:
        VPMArtifactManifest describing the emitted artifact.

    Raises:
        TypeError:           wrong type for zkba_class / proof_weight / inputs / html_renderer return.
        ValueError:          inputs missing 'ts_ns', or 'ts_ns' not uint64; bad vpm_id; bad visual_state; bad capture_mode; bad zkba_manifest_hash_hex.
        VPMComplianceError:  emitted HTML violates static-guard compiler discipline.
        OSError:             output directory cannot be created/written.
    """
    # ---- Type + value validation ----
    if not isinstance(zkba_class, ZKBAClass):
        raise TypeError(
            f"zkba_class must be ZKBAClass; got {type(zkba_class).__name__}"
        )
    if not isinstance(proof_weight, ProofWeightClass):
        raise TypeError(
            f"proof_weight must be ProofWeightClass; got {type(proof_weight).__name__}"
        )
    if not isinstance(vpm_id, str) or not vpm_id:
        raise ValueError(f"vpm_id must be non-empty str; got {vpm_id!r}")
    if visual_state not in _VPM_VISUAL_STATES:
        raise ValueError(
            f"visual_state must be one of {_VPM_VISUAL_STATES}; got {visual_state!r}"
        )
    if capture_mode not in _VPM_CAPTURE_MODES:
        raise ValueError(
            f"capture_mode must be one of {_VPM_CAPTURE_MODES}; got {capture_mode!r}"
        )
    if not isinstance(integrity_label, dict):
        raise TypeError(
            f"integrity_label must be dict; got {type(integrity_label).__name__}"
        )
    if not isinstance(zkba_manifest_hash_hex, str) or len(zkba_manifest_hash_hex) != 64:
        raise ValueError(
            "zkba_manifest_hash_hex must be 64-char lowercase hex string; "
            f"got {len(zkba_manifest_hash_hex) if isinstance(zkba_manifest_hash_hex, str) else type(zkba_manifest_hash_hex).__name__}"
        )
    # Hex sanity (no validation of 'is this hash of anything real' — that's
    # a verifier-side concern; here we only enforce shape).
    try:
        int(zkba_manifest_hash_hex, 16)
    except ValueError:
        raise ValueError(
            f"zkba_manifest_hash_hex not valid hex: {zkba_manifest_hash_hex!r}"
        )
    if not isinstance(inputs, dict):
        raise TypeError(f"inputs must be a dict; got {type(inputs).__name__}")
    if "ts_ns" not in inputs:
        raise ValueError("inputs missing required key 'ts_ns'")
    ts_ns_val = inputs["ts_ns"]
    if not isinstance(ts_ns_val, int) or ts_ns_val < 0 or ts_ns_val > 0xFFFFFFFFFFFFFFFF:
        raise ValueError(
            f"inputs['ts_ns'] must be uint64; got {type(ts_ns_val).__name__} = {ts_ns_val!r}"
        )

    # ---- Input commitment ----
    input_commit = compute_input_commitment(inputs)

    # ---- Integrity label hash (over canonical-JSON for deterministic bytes) ----
    integrity_label_hash = hashlib.sha256(canonical_json(integrity_label)).hexdigest()

    # ---- Render + enforce discipline ----
    html_body = html_renderer(inputs)
    if not isinstance(html_body, str):
        raise TypeError(
            f"html_renderer must return str; got {type(html_body).__name__}"
        )
    # Static guards — run BEFORE writing to disk so a noncompliant VPM never
    # lands on the filesystem.
    _enforce_vpm_compiler_discipline(html_body)
    _verify_integrity_label_in_dom(html_body)

    # ---- Write artifact + manifest sidecar ----
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_bytes = html_body.encode("utf-8")
    output_hash = hashlib.sha256(output_bytes).hexdigest()
    output_path = output_dir / f"{input_commit}.html"
    output_path.write_bytes(output_bytes)

    manifest = VPMArtifactManifest(
        schema=_VPM_ARTIFACT_SCHEMA,
        vpm_id=vpm_id,
        zkba_class=int(zkba_class),
        proof_weight=int(proof_weight),
        visual_state=visual_state,
        capture_mode=capture_mode,
        integrity_label_hash_hex=integrity_label_hash,
        wrapper_schema=_VPM_WRAPPER_SCHEMA_REF,
        zkba_manifest_hash_hex=zkba_manifest_hash_hex,
        output_path=str(output_path).replace("\\", "/"),
        output_hash_hex=output_hash,
        input_commitment_hex=input_commit,
        compiler_version=_COMPILER_VERSION,
        ts_ns=int(ts_ns_val),
    )

    # Sidecar filename distinct from the ZKBA `.manifest.json` sidecar so a
    # directory can hold both ZKBA + VPM manifests for the same projection
    # without name collision.
    manifest_path = output_dir / f"{input_commit}.vpm.manifest.json"
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
