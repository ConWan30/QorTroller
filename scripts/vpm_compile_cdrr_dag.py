"""Phase O4-VPM-INTEGRATION Stream A.1.c — CDRR DAG VPM compiler.

Third internal-projection VPM. Renders the **Cross-Domain Reasoning Record
DAG** — the artifact composition lattice across the 7 ZKBA classes — as an
inline SVG directed acyclic graph.

CDRR is named in `Phase_O4_VPM_Integration_Plan.md` §2.5; per the
VBDIP-0002A §10 registry discipline ("VPM ID becomes active only after
wrapper manifest, compiler target, test fixture, and governance approval"),
CDRR ships as a non-registered internal-only Test Fixture under the
HONESTY-BOARD-v1 registered identifier umbrella. It does NOT need its own
VBDIP-0002A §10 registry slot.

Registered VPM ID: `HONESTY-BOARD-v1` (umbrella; CDRR is a specialization)
Internal ID: `CDRR-DAG-v1` (only used in `data-cdrr-id` markers; not a §10 id)
Lifecycle status after this commit: `Test Fixture`
Owning agent lane: Sentry (writes to `zk_artifacts/`)

The DAG topology is FROZEN at the 7-class composition lattice known at Phase
O3-ZKBA-TRACK1 close:

  Nodes (7):     AIT, GIC, VHP, HARDWARE, CONSENT, TOURNAMENT, MARKET
  Edges (5):     TOURNAMENT -> VHP        (Tournament Card composes VHP state)
                 TOURNAMENT -> GIC        (Tournament Card composes GIC chain head)
                 TOURNAMENT -> HARDWARE   (Tournament Card composes device hash)
                 MARKET     -> CONSENT    (Marketplace listing composes MARKETPLACE consent)
                 MARKET     -> AIT        (Marketplace listing references AIT corpus snapshot)

The composition edges are CANONICAL and MUST match the per-artifact
documentation in `scripts/zkba_compile_tournament_card.py` and
`scripts/zkba_compile_marketplace_listing.py`. Any edge drift surfaces as a
test failure in T-VPM-CDRR-6 (composition lattice integrity).

Track 1 invariants: same as A.1.a/b.

Author: VAPI Architect (Phase O4 Commit 4)
Date: 2026-05-13
"""
from __future__ import annotations

import argparse
import html
import os
import sys
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_BRIDGE_DIR = os.path.normpath(os.path.join(_HERE, "..", "bridge"))
if _BRIDGE_DIR not in sys.path:
    sys.path.insert(0, _BRIDGE_DIR)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from vapi_bridge.zkba_artifact import ZKBAClass, ProofWeightClass  # noqa: E402
from vsd_ui_compiler import (  # noqa: E402
    VPMArtifactManifest,
    compile_vpm_artifact,
)
from vpm_visual_grammar import (  # noqa: E402
    VISUAL_STATES,
    assemble_vpm_head,
    integrity_label_html,
    visual_state_aria_block,
    visual_state_overlay,
    vpm_body_class,
)


# Internal-only ID (renderer marks `data-cdrr-id` for traceability;
# manifest still registers under HONESTY-BOARD-v1 umbrella).
_VPM_ID = "HONESTY-BOARD-v1"
_CDRR_INTERNAL_ID = "CDRR-DAG-v1"


# ---------------------------------------------------------------------------
# FROZEN DAG topology — must match per-artifact documentation
# ---------------------------------------------------------------------------

# Node IDs match ZKBAClass enum names.
CDRR_NODES = (
    "AIT", "GIC", "VHP", "HARDWARE", "CONSENT", "TOURNAMENT", "MARKET",
)

# Composition edges — tuples of (child, parent) — child commits to parent in
# its preimage. Sorted (child, parent) ascending for deterministic SVG layout.
CDRR_EDGES = (
    ("MARKET",     "AIT"),
    ("MARKET",     "CONSENT"),
    ("TOURNAMENT", "GIC"),
    ("TOURNAMENT", "HARDWARE"),
    ("TOURNAMENT", "VHP"),
)


# Deterministic SVG node coordinates (x, y) in a 7-column row layout
# arranged in two tiers: primary primitives on top, composite artifacts
# on the bottom. Choice of (x, y) is deterministic so two-build byte
# stability holds; layout was picked for visual clarity.
_NODE_COORDS = {
    # Top tier — primitives
    "AIT":        (80,  90),
    "CONSENT":    (200, 90),
    "GIC":        (320, 90),
    "VHP":        (440, 90),
    "HARDWARE":   (560, 90),
    # Bottom tier — composite artifacts
    "MARKET":     (140, 280),
    "TOURNAMENT": (440, 280),
}

# CFSS lane assignment per artifact (drives node color)
_NODE_LANES = {
    "AIT":        "sentry",
    "GIC":        "sentry",
    "VHP":        "sentry",
    "HARDWARE":   "sentry",
    "CONSENT":    "guardian",
    "TOURNAMENT": "sentry",
    "MARKET":     "curator",
}

_LANE_FILL = {
    "sentry":   "#5a8fb8",
    "guardian": "#d65b78",
    "curator":  "#f0a868",
}


# ---------------------------------------------------------------------------
# Deterministic SVG renderer
# ---------------------------------------------------------------------------

def _render_cdrr_svg() -> str:
    """Render the FROZEN 7-node 5-edge composition lattice as inline SVG.

    No xmlns attribute (HTML5 inline-SVG namespace inheritance per plan
    §3 Stream A.0 compiler discipline item 1 — keeps the `no https?://`
    guard clean). All coordinates compile-time-baked; deterministic.
    """
    nodes_svg_parts: list[str] = []
    for node_id in CDRR_NODES:
        x, y = _NODE_COORDS[node_id]
        lane = _NODE_LANES[node_id]
        fill = _LANE_FILL[lane]
        nodes_svg_parts.append(
            f'<g class="cdrr-node" data-cdrr-node="{node_id}" data-cdrr-lane="{lane}">\n'
            f'  <rect x="{x - 50}" y="{y - 20}" width="100" height="40" rx="6" '
            f'fill="{fill}" stroke="#020408" stroke-width="2"/>\n'
            f'  <text x="{x}" y="{y + 5}" text-anchor="middle" '
            f'fill="#020408" font-family="Courier New, monospace" '
            f'font-size="14" font-weight="bold">{node_id}</text>\n'
            '</g>'
        )

    edges_svg_parts: list[str] = []
    for child, parent in CDRR_EDGES:
        cx, cy = _NODE_COORDS[child]
        px, py = _NODE_COORDS[parent]
        # Edge goes from child top to parent bottom
        edges_svg_parts.append(
            f'<g class="cdrr-edge" data-cdrr-child="{child}" data-cdrr-parent="{parent}">\n'
            f'  <line x1="{cx}" y1="{cy - 20}" x2="{px}" y2="{py + 20}" '
            'stroke="#93a5b8" stroke-width="2" marker-end="url(#cdrr-arrowhead)"/>\n'
            '</g>'
        )

    return (
        '<svg class="cdrr-dag" width="640" height="360" '
        'viewBox="0 0 640 360" aria-label="CDRR DAG: 7-class composition lattice">\n'
        '<defs>\n'
        '  <marker id="cdrr-arrowhead" markerWidth="10" markerHeight="10" '
        'refX="8" refY="3" orient="auto" markerUnits="strokeWidth">\n'
        '    <path d="M0,0 L0,6 L9,3 z" fill="#93a5b8"/>\n'
        '  </marker>\n'
        '</defs>\n'
        '<rect x="0" y="0" width="640" height="360" fill="#0a0e14"/>\n'
        + '\n'.join(edges_svg_parts) + '\n'
        + '\n'.join(nodes_svg_parts) + '\n'
        '<text x="320" y="20" text-anchor="middle" fill="#5a8fb8" '
        'font-family="Courier New, monospace" font-size="12">'
        'CDRR DAG — 7 ZKBA classes × 5 composition edges</text>\n'
        '<text x="320" y="350" text-anchor="middle" fill="#607a93" '
        'font-family="Courier New, monospace" font-size="10">'
        'Sentry (blue) / Guardian (red) / Curator (amber)</text>\n'
        '</svg>'
    )


def _render_cdrr_dag_html(inputs: dict) -> str:
    """Render the CDRR DAG VPM HTML body deterministically."""
    state = inputs["visual_state"]
    head = assemble_vpm_head(
        title=f"VAPI CDRR DAG — {state.upper()}",
        visual_state=state,
        extra_style=(
            ".cdrr-dag { display: block; margin: 1em auto; "
            "max-width: 640px; border: 1px solid #1a2a40; }\n"
            ".cdrr-legend { color: #93a5b8; font-size: 0.85em; "
            "margin: 0.5em 0 1em 0; }\n"
        ),
    )

    overlay = visual_state_overlay(state)
    aria_block = visual_state_aria_block(state)
    integrity_block = integrity_label_html(inputs["integrity_label"])
    body_class = vpm_body_class(state)
    dag_svg = _render_cdrr_svg()
    ts_ns = int(inputs["ts_ns"])
    zkba_hash = html.escape(inputs["zkba_manifest_hash_hex"])

    # Render an edge list as <ul> for accessibility + grep-testability
    edge_items = "\n".join(
        f'    <li data-cdrr-edge="{child}-to-{parent}">'
        f'<code>{child}</code> &rarr; <code>{parent}</code>'
        '</li>'
        for child, parent in CDRR_EDGES
    )

    body = (
        '<body>\n'
        f'  <div class="{body_class}" data-cdrr-id="{_CDRR_INTERNAL_ID}">\n'
        f'  {overlay}\n'
        '  <h1>CDRR DAG — Cross-Domain Reasoning Record Lattice</h1>\n'
        f'  {aria_block}\n'
        '  <p class="cdrr-legend">7 ZKBA classes (FROZEN-v1 enum) connected '
        'by 5 composition edges. Edge direction: child &rarr; parent (the '
        'parent\'s output is committed in the child\'s preimage).</p>\n'
        f'  {dag_svg}\n'
        '  <h2>Composition Edges</h2>\n'
        '  <ul class="cdrr-edge-list">\n'
        f'{edge_items}\n'
        '  </ul>\n'
        '  <h2>Underlying ZKBA Projection</h2>\n'
        '  <div class="vpm-meta">\n'
        f'    <div>ZKBA manifest hash: <code>{zkba_hash}</code></div>\n'
        '  </div>\n'
        f'  {integrity_block}\n'
        '  <div class="vpm-footer">\n'
        f'    Internal ID: <code>{_CDRR_INTERNAL_ID}</code> (under '
        f'<code>{_VPM_ID}</code> umbrella per VBDIP-0002A §10 discipline). '
        f'Lifecycle: Test Fixture. Self-contained projection. compile-time '
        f'ts_ns: <code>{ts_ns}</code>.\n'
        '  </div>\n'
        '  </div>\n'
        '</body>\n'
    )

    return (
        '<!DOCTYPE html>\n'
        '<html lang="en">\n'
        f'{head}\n'
        f'{body}'
        '</html>\n'
    )


def build_cdrr_dag_artifact(
    *,
    integrity_label: dict,
    zkba_manifest_hash_hex: str,
    visual_state: str,
    capture_mode: str,
    output_dir: Path,
    ts_ns: int,
) -> VPMArtifactManifest:
    """Build a CDRR DAG VPM artifact deterministically.

    The DAG topology is FROZEN — no caller inputs control nodes or edges.
    This makes the CDRR DAG VPM byte-stable across protocol time as long as
    the ZKBA class enum + composition lattice are unchanged; if/when a new
    composition edge ships (e.g. a future cross-class reference), the
    constants in this module update and the CDRR DAG VPM's input commitment
    changes accordingly.

    ZKBA class context: HARDWARE (= 4) — CDRR DAG is conceptually grouped
    with the HARDWARE artifact's manufacturer-attestation family since both
    surface protocol-level architecture rather than per-session state.
    CHAIN_ONLY proof weight.
    """
    if visual_state not in VISUAL_STATES:
        raise ValueError(
            f"visual_state must be one of {VISUAL_STATES}; got {visual_state!r}"
        )

    inputs = {
        "visual_state":           str(visual_state),
        "integrity_label":        dict(integrity_label),
        "zkba_manifest_hash_hex": str(zkba_manifest_hash_hex),
        "ts_ns":                  int(ts_ns),
    }

    return compile_vpm_artifact(
        vpm_id=_VPM_ID,
        zkba_class=ZKBAClass.HARDWARE,
        proof_weight=ProofWeightClass.CHAIN_ONLY,
        visual_state=visual_state,
        capture_mode=capture_mode,
        integrity_label=integrity_label,
        zkba_manifest_hash_hex=zkba_manifest_hash_hex,
        inputs=inputs,
        output_dir=Path(output_dir),
        html_renderer=_render_cdrr_dag_html,
    )


def _cli_main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a CDRR DAG VPM artifact "
                    "(Phase O4-VPM-INTEGRATION Stream A.1.c)."
    )
    parser.add_argument("--zkba-manifest-hash-hex", required=True)
    parser.add_argument("--visual-state", default="live", choices=list(VISUAL_STATES))
    parser.add_argument("--capture-mode", default="live")
    parser.add_argument("--ts-ns", type=int, required=True)
    parser.add_argument(
        "--output-dir",
        default=os.path.normpath(os.path.join(
            _HERE, "..", "frontend", "src", "artifacts", "cdrr_dag",
        )),
    )
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    integrity_label = {
        "proof_type":             "VPM-CDRR-DAG",
        "capture_mode":           args.capture_mode,
        "raw_biometrics_exposed": False,
        "consent_active":         True,
        "zk_verified":            False,
        "on_chain_anchor":        False,
        "proof_weight":           "CHAIN_ONLY",
        "revocation_status":      "active",
        "limitations":            [
            "Topology-only projection; does not assert any specific artifact's validity",
        ],
    }

    manifest = build_cdrr_dag_artifact(
        integrity_label=integrity_label,
        zkba_manifest_hash_hex=args.zkba_manifest_hash_hex,
        visual_state=args.visual_state,
        capture_mode=args.capture_mode,
        output_dir=Path(args.output_dir),
        ts_ns=args.ts_ns,
    )
    print(f"CDRR DAG VPM compiled:")
    print(f"  output_path:           {manifest.output_path}")
    print(f"  output_hash_hex:       {manifest.output_hash_hex}")
    print(f"  input_commitment_hex:  {manifest.input_commitment_hex}")
    print(f"  visual_state:          {manifest.visual_state}")
    print(f"  nodes:                 {len(CDRR_NODES)}")
    print(f"  edges:                 {len(CDRR_EDGES)}")
    return 0


if __name__ == "__main__":
    sys.exit(_cli_main())
