"""QorTroller internal-architecture diagram generator.

Produces a clean, labelled 2D pitch visual (PNG + SVG) of the controller's
internal components and the data-flow story — WITHOUT needing Fusion. Each
component is a rounded box, color-coded by BOM status (the same honesty
coding as the CAD skeleton), arranged in the trust-chain narrative:

   human input -> sensors -> MCU builds PoAC record -> secure element signs
   -> tamper-proof, gamer-owned data

Stdlib + matplotlib only.

RUN:
    pip install matplotlib          # if not already present
    python cad/qortroller_architecture_diagram.py
    # writes cad/out/qortroller_architecture.png and .svg
"""
from __future__ import annotations

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

# ── Honesty color coding (matches the CAD skeleton) ────────────────────────
C_PENDING = "#FBB24D"   # amber  = Stage-A measurement pending
C_SPEC = "#8CBFF2"      # blue   = spec known, supplier pending
C_SECURE = "#D95AD9"    # magenta= the C2 secure element (crypto story)
C_FLOW = "#2E7D46"      # green  = data-flow / output
C_INK = "#1A1A1A"
C_BG = "#0E0E12"        # void-black backdrop (brand)
C_PANEL = "#16161D"


def _box(ax, x, y, w, h, title, sub, fill, status=""):
    box = FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
        linewidth=1.4, edgecolor="white", facecolor=fill, alpha=0.95, zorder=3,
    )
    ax.add_patch(box)
    ax.text(x + w / 2, y + h * 0.62, title, ha="center", va="center",
            fontsize=10.5, fontweight="bold", color=C_INK, zorder=4)
    ax.text(x + w / 2, y + h * 0.30, sub, ha="center", va="center",
            fontsize=7.2, color=C_INK, zorder=4, wrap=True)
    if status:
        ax.text(x + w / 2, y - 0.12, status, ha="center", va="top",
                fontsize=6.0, color="#BBBBBB", style="italic", zorder=4)


def _arrow(ax, x1, y1, x2, y2, color=C_FLOW, label=""):
    arr = FancyArrowPatch(
        (x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=16,
        linewidth=2.0, color=color, zorder=2, shrinkA=4, shrinkB=4,
    )
    ax.add_patch(arr)
    if label:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.12, label, ha="center",
                va="bottom", fontsize=6.8, color=color, fontweight="bold", zorder=4)


def build(out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    fig, ax = plt.subplots(figsize=(13, 7.5))
    fig.patch.set_facecolor(C_BG)
    ax.set_facecolor(C_BG)
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 7.5)
    ax.axis("off")

    # Title
    ax.text(0.3, 7.15, "QorTroller — Internal Architecture & Trust Chain",
            fontsize=17, fontweight="bold", color="white")
    ax.text(0.3, 6.78,
            "V.A.P.I.-native reference controller · the physical input source IS the cryptographic agency-holder",
            fontsize=9, color="#FF7A1A")

    # ── Row 1: SENSORS (the physical input layer) ──────────────────────────
    ax.text(0.3, 6.05, "1 · PHYSICAL INPUT (sensors)", fontsize=9,
            fontweight="bold", color="#9fd0ff")
    _box(ax, 0.3, 4.5, 2.5, 1.3, "C7 Adaptive Triggers ×2",
         "force-curve liveness extraction\nstrongest signal · aspirational-primary", C_PENDING,
         "FTO + MEASUREMENT-PENDING")
    _box(ax, 3.1, 4.5, 2.3, 1.3, "C3 / C4 Sticks",
         "Hall/TMR · contactless\ndrift-free · L4 fingerprint", C_PENDING,
         "MEASUREMENT-PENDING")
    _box(ax, 5.7, 4.5, 2.1, 1.3, "C5 6-axis IMU",
         "gravity-postural biometric\nmotion injection-detect", C_PENDING,
         "MEASUREMENT-PENDING")
    _box(ax, 8.1, 4.5, 2.0, 1.3, "C8 Touchpad",
         "12-bit 2-point\nco-signal surface", C_SPEC, "spec known")
    _box(ax, 10.4, 4.5, 2.2, 1.3, "A1 Lightbar",
         "optical challenge-response\nwitness (privacy-preferred)", C_SPEC, "advisory")

    # ── Row 2: MCU (the brain) ─────────────────────────────────────────────
    ax.text(0.3, 3.95, "2 · COGNITION (builds the record)", fontsize=9,
            fontweight="bold", color="#9fd0ff")
    _box(ax, 3.4, 2.6, 3.0, 1.15, "C1 ESP32-S3 MCU",
         "polls every sensor at 1 kHz\nbuilds the 228-byte PoAC record", C_SPEC,
         "spec known")

    # ── Row 3: SECURE ELEMENT (signs) ──────────────────────────────────────
    ax.text(7.1, 3.95, "3 · ROOT OF TRUST (signs)", fontsize=9,
            fontweight="bold", color="#f3a6f3")
    _box(ax, 7.2, 2.6, 3.0, 1.15, "C2 Secure Element",
         "on-chip P-256 key, non-extractable\nsigns every record in silicon", C_SECURE,
         "ATECC608B-class")

    # ── Row 4: OUTPUT ──────────────────────────────────────────────────────
    _box(ax, 4.6, 0.7, 4.4, 1.05, "Tamper-proof, gamer-owned data",
         "228-byte signed Proof-of-Autonomous-Cognition · anchored on IoTeX · the gamer holds the key",
         C_FLOW)

    # ── Flow arrows ────────────────────────────────────────────────────────
    # sensors -> MCU
    for sx in (1.55, 4.25, 6.75):
        _arrow(ax, sx, 4.5, 4.9, 3.75, color="#9fd0ff")
    # MCU -> secure element
    _arrow(ax, 6.4, 3.17, 7.2, 3.17, color="white", label="record")
    # secure element -> output
    _arrow(ax, 8.7, 2.6, 7.0, 1.75, color=C_SECURE, label="signed")
    # MCU also feeds output context
    _arrow(ax, 4.9, 2.6, 6.0, 1.75, color="#9fd0ff")

    # ── Legend ─────────────────────────────────────────────────────────────
    lx, ly = 0.3, 1.4
    legend = [
        (C_PENDING, "Stage A measurement pending (candidate geometry)"),
        (C_SPEC, "Spec known · supplier pending"),
        (C_SECURE, "Secure element — the cryptographic root of trust"),
        (C_FLOW, "Signed output / data flow"),
    ]
    for i, (c, label) in enumerate(legend):
        yy = ly - i * 0.28
        ax.add_patch(FancyBboxPatch((lx, yy), 0.28, 0.18,
                     boxstyle="round,pad=0.01", facecolor=c, edgecolor="white",
                     linewidth=0.8))
        ax.text(lx + 0.4, yy + 0.09, label, fontsize=7, color="#DDDDDD", va="center")

    # Honesty footer
    ax.text(12.7, 0.15,
            "Amber = proposed/candidate, not yet measured. Honest by design.",
            fontsize=6.5, color="#888888", ha="right", style="italic")

    png = os.path.join(out_dir, "qortroller_architecture.png")
    svg = os.path.join(out_dir, "qortroller_architecture.svg")
    fig.savefig(png, dpi=200, facecolor=C_BG, bbox_inches="tight")
    fig.savefig(svg, facecolor=C_BG, bbox_inches="tight")
    plt.close(fig)
    print(f"[wrote] {png}")
    print(f"[wrote] {svg}")


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    build(os.path.join(here, "out"))
