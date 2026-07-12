"""TRL-1 I3 - W3bstream applet parity: mechanical-validation-only.

Rail 5 (alignment doc): the W3bstream sandbox VALIDATES events; it never CAPTURES
them. sandbox_config.json pins frame_grabbing=false / optical_capture=false; the
Rust applet must honor that - no frame-grab / camera / capture code, only payload
parsing + validation (block cadence, clean environment). This audits PARITY across
three surfaces:

  MECHANISMS   sandbox_config.json pins frame_grabbing=false AND optical_capture=false.
  APPLET       the applet source carries NO capture markers (VideoCapture / capture_frame
               / frame_grab / screenshot / ...) AND DOES carry a validation marker
               (ANCHOR_CADENCE / handle_poac_payload) - it validates, never captures.
  INVARIANTS   the W3S invariants are pinned in BOTH the gate and the allowlist.

Pure; source/config inspection only (no Rust build). Reads only; no chain, no spend.
"""
from __future__ import annotations

# Capture / frame-grab operations that must NEVER appear in a mechanical-validation applet.
_CAPTURE_MARKERS = ("VideoCapture", "capture_frame", "frame_grab", "grab_frame",
                    "screen_capture", "screenshot", "camera_open", "cv::VideoCapture")

# Proof the applet actually validates (at least one must be present).
_VALIDATION_MARKERS = ("ANCHOR_CADENCE", "handle_poac_payload")

_W3S_INVARIANTS = ("INV-W3S-001", "INV-W3S-002")

CONFORMANT = "CONFORMANT"
VIOLATION = "VIOLATION"


def check_sandbox_mechanisms(config: dict) -> list:
    """frame_grabbing and optical_capture must be pinned False."""
    out = []
    mech = config.get("mechanisms", config)
    if mech.get("frame_grabbing") is not False:
        out.append(f"sandbox frame_grabbing must be false (got {mech.get('frame_grabbing')!r})")
    if mech.get("optical_capture") is not False:
        out.append(f"sandbox optical_capture must be false (got {mech.get('optical_capture')!r})")
    return out


def check_applet_validation_only(applet_src: str) -> list:
    """No capture markers; at least one validation marker."""
    out = []
    for m in _CAPTURE_MARKERS:
        if m in applet_src:
            out.append(f"applet contains capture marker {m!r} - the sandbox must validate, not capture")
    if not any(m in applet_src for m in _VALIDATION_MARKERS):
        out.append("applet has no validation marker (ANCHOR_CADENCE / handle_poac_payload)")
    return out


def check_invariants_pinned(gate_src: str, allowlist_src: str,
                            invariants=_W3S_INVARIANTS) -> list:
    """Each W3S invariant must appear in BOTH the gate and the allowlist (parity)."""
    out = []
    for inv in invariants:
        if inv not in gate_src:
            out.append(f"{inv} missing from the invariant gate")
        if inv not in allowlist_src:
            out.append(f"{inv} missing from the allowlist")
    return out


def assess_w3s_parity(config: dict, applet_src: str, gate_src: str, allowlist_src: str,
                      invariants=_W3S_INVARIANTS) -> dict:
    """Combined verdict. CONFORMANT iff no violations across all three surfaces."""
    violations = (check_sandbox_mechanisms(config)
                  + check_applet_validation_only(applet_src)
                  + check_invariants_pinned(gate_src, allowlist_src, invariants))
    return {
        "status": CONFORMANT if not violations else VIOLATION,
        "violations": violations,
        "rail": "sandbox mechanical-validation-only: frame_grabbing=false / optical_capture=false; "
                "the applet validates (never captures); W3S invariants pinned in gate + allowlist",
        "advisory": True,
    }
