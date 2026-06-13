"""QorTroller internal component-layout plate — CadQuery parametric starter.

A code-defined CAD model of the mainboard + every C1-C8 / A1 / A3 component as
labelled bounding-box blocks at nominal positions. This is the "internal blueprint"
half of the digital prototype: it shows what goes where, at real nominal sizes, and
exports to STEP (for manufacturers / Fusion import) and STL (for a quick print).

It is intentionally NOT the ergonomic outer shell (organic curves belong in Fusion).
It IS the honest, dimension-grounded skeleton you drop INTO the Fusion shell to check
fit, and the thing you explode for the pitch render.

Dimensions are the nominal blockout values from
`docs/cad/qortroller-cad-component-manifest.md`. Marked `# NOMINAL` — replace each
block with the real manufacturer STEP as you download it (in Fusion, not here).

------------------------------------------------------------------------------
SETUP (do this once):
    pip install cadquery
    # optional viewer:
    pip install cadquery cq-editor      # then: cq-editor cad/qortroller_layout_plate.py

RUN (headless export):
    python cad/qortroller_layout_plate.py
    # writes cad/out/qortroller_layout.step  and  cad/out/qortroller_layout.stl

The .step opens directly in Fusion 360 (Insert > Insert Derive / Upload), Onshape,
SolidWorks, FreeCAD. The .stl opens in any slicer.

STL CAVEAT (read before printing): the exported .stl is a MULTI-SHELL
VISUALIZATION mesh — it is the union of many separate, disconnected block solids
(one per component), NOT a single watertight printable body. It is intended for
on-screen layout review, not for slicing into a functional print. A real printable
part is the ergonomic SHELL (modeled separately in Fusion from primitives, per the
Fusion cowork guide) — not this skeleton. Slicers will load the multi-shell mesh but
treating it as a print-ready object is a category error.
------------------------------------------------------------------------------
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import cadquery as cq

# ─────────────────────────────────────────────────────────────────────────────
# Component table — (label, L, W, H in mm, x, y, z center offset on the board,
# bom_status). All dims NOMINAL per the CAD component manifest; swap for real
# STEP files before presenting any dimension as fact.
# Coordinate frame: board sits in the XY plane, +Z is "up" (toward the player's
# palms / face buttons side). Origin = board center.
# ─────────────────────────────────────────────────────────────────────────────

BOARD_L = 95.0   # NOMINAL E1 mainboard length (X)
BOARD_W = 55.0   # NOMINAL E1 mainboard width  (Y)
BOARD_T = 1.6    # NOMINAL 4-layer PCB thickness (Z)


@dataclass(frozen=True)
class Part:
    id: str
    label: str
    l: float
    w: float
    h: float
    x: float
    y: float
    z: float           # center Z relative to top face of board
    status: str        # BOM status code — travels onto the model for honesty


# Positions are illustrative nominal layout — adjust freely in Fusion once real
# parts land. The point is honest sizes + relative placement, not final layout.
PARTS: list[Part] = [
    # id            label                         L     W     H     x      y     z    status
    Part("C1",  "C1 ESP32-S3 MCU",              25.5, 18.0,  3.1,   0.0,   0.0,  2.0, "UNVERIFIED-EXTERNAL"),
    Part("C2",  "C2 ATECC608B SecureElem UDFN-8",  4.0,  3.0,  0.6,  18.0,  -8.0,  0.6, "UNVERIFIED-EXTERNAL"),  # canonical UDFN-8 (4x3x0.6); SOIC-8 is the larger dev-board variant
    Part("C3",  "C3 Left stick (Hall/TMR)",      20.0, 20.0, 22.0, -32.0,  12.0, 11.0, "MEASUREMENT-PENDING"),
    Part("C4",  "C4 Right stick (same fam)",     20.0, 20.0, 22.0,  32.0,  12.0, 11.0, "MEASUREMENT-PENDING"),
    Part("C5",  "C5 6-axis IMU",                  3.0,  3.0,  0.9,  -6.0,  -6.0,  0.9, "MEASUREMENT-PENDING"),
    Part("C6",  "C6 USB-C",                        9.0,  7.5,  3.2,   0.0, -26.0,  1.6, "UNVERIFIED-EXTERNAL"),
    Part("C7L", "C7 Adaptive trigger L",         18.0, 30.0, 25.0, -38.0, -22.0, 12.0, "MEASUREMENT-PENDING"),
    Part("C7R", "C7 Adaptive trigger R",         18.0, 30.0, 25.0,  38.0, -22.0, 12.0, "MEASUREMENT-PENDING"),
    Part("C8",  "C8 Touchpad (cap 12-bit)",      50.0, 30.0,  1.5,   0.0,  16.0,  1.0, "UNVERIFIED-EXTERNAL"),
    Part("A1",  "A1 Lightbar LED",               20.0,  4.0,  1.2,   0.0, -28.5,  1.0, "UNVERIFIED-EXTERNAL"),
    Part("A3",  "A3 Battery + PMIC",             50.0, 35.0,  6.0,   0.0,   2.0, -6.0, "UNVERIFIED-EXTERNAL"),
    # A2 microphone: DEFERRED — intentionally absent (TRACK1-LESSON-002/003).
]

# Color hint by status, so the exploded render reads honestly at a glance.
_STATUS_COLOR = {
    "UNVERIFIED-EXTERNAL": cq.Color(0.55, 0.75, 0.95),  # blue  = spec known, supplier pending
    "MEASUREMENT-PENDING": cq.Color(0.98, 0.70, 0.30),  # amber = gated on Stage A measurement
    "LIVE-SHORTLIST":      cq.Color(0.55, 0.85, 0.55),  # green = candidate identified
    "LIVE-SUPPLIED":       cq.Color(0.25, 0.70, 0.35),  # deep green = committed
}
_SECURE_ELEMENT_COLOR = cq.Color(0.85, 0.35, 0.85)      # magenta = the crypto story (C2)


def build_assembly() -> cq.Assembly:
    """Build the labelled component-layout assembly."""
    asm = cq.Assembly(name="QorTroller_Layout_v0_1")

    # E1 mainboard
    board = cq.Workplane("XY").box(BOARD_L, BOARD_W, BOARD_T)
    asm.add(board, name="E1_mainboard", loc=cq.Location(cq.Vector(0, 0, 0)),
            color=cq.Color(0.20, 0.45, 0.25))  # PCB green

    top_of_board = BOARD_T / 2.0
    for p in PARTS:
        block = cq.Workplane("XY").box(p.l, p.w, p.h)
        color = _SECURE_ELEMENT_COLOR if p.label.startswith("C2") else \
            _STATUS_COLOR.get(p.status, cq.Color(0.7, 0.7, 0.7))
        # z given as center-above-board-top; battery (negative z) hangs below.
        z_center = top_of_board + p.z if p.z >= 0 else -top_of_board + p.z
        asm.add(block, name=p.label.replace(" ", "_"),
                loc=cq.Location(cq.Vector(p.x, p.y, z_center)), color=color)
    return asm


def export(asm: cq.Assembly, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    step_path = os.path.join(out_dir, "qortroller_layout.step")
    stl_path = os.path.join(out_dir, "qortroller_layout.stl")
    asm.save(step_path)                         # STEP: manufacturers / Fusion
    # MULTI-SHELL visualization mesh — union of separate block solids, NOT a
    # single watertight printable body. For layout review only (see module docstring).
    compound = asm.toCompound()
    cq.exporters.export(compound, stl_path)     # STL: visualization only, NOT print-ready
    print(f"[wrote] {step_path}")
    print(f"[wrote] {stl_path}  (MULTI-SHELL visualization mesh — NOT a print-ready single body)")


def print_envelope() -> None:
    """Report the bounding envelope — tells you the printer bed you need."""
    asm = build_assembly()
    bb = asm.toCompound().BoundingBox()
    print(f"Assembly envelope (mm): "
          f"X={bb.xlen:.1f}  Y={bb.ylen:.1f}  Z={bb.zlen:.1f}")
    print("  (This is the INTERNAL skeleton envelope; the ergonomic shell will be "
          "larger. Use it to sanity-check printer bed + internal real-estate.)")


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    asm = build_assembly()
    export(asm, os.path.join(here, "out"))
    print_envelope()
    print("\nParts placed (label · status):")
    for p in PARTS:
        print(f"  {p.label:32s} {p.status}")
    print("  A2 microphone                    DEFERRED (intentionally absent)")
