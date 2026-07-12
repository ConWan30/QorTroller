"""TRL-1 I2 - DA sidecar-pointer conformance for the scene / PoSP boundary.

Arc 7's law: bulky payloads live OFF-chain on the DA node; only a 32-byte
COMMITMENT (the pointer) crosses the on-chain / PoSP boundary. INV-ARC7-001 pins
the 228B PoAC frame; the alignment doc N2 extends the law to scene-stream data -
"scene payloads are DA-class, pointer-only at the boundary". This audits a boundary
record (a PoSP dict) for obedience:

  ROOTS-ARE-POINTERS   every events_roots value is a 32-byte commitment (64-hex,
                       optionally 0x-prefixed) or honestly None - never an inline
                       list / blob / oversized string.
  NO-INLINE-SCENE      no raw scene payload crosses the boundary - no forbidden
                       inline-payload key (frames / images / pixels / event blobs)
                       and no data-URI image value anywhere in the record.

Advisory conformance audit; pure stdlib; reads only. Does NOT touch the 228B PoAC
wire or any FROZEN primitive. A list of short hashes (e.g. fusion.record_hashes) is
provenance metadata (pointers), not a scene payload - not a violation.
"""
from __future__ import annotations

# Raw scene-payload key names that must NEVER cross the boundary inline (they belong
# on the DA node, referenced by a 32B commitment).
_INLINE_SCENE_PAYLOAD_KEYS = frozenset({
    "raw_frame", "raw_frames", "frame", "frames", "frame_b64", "frame_bytes",
    "image", "image_b64", "png", "png_b64", "jpeg", "jpeg_b64",
    "pixels", "scene_payload", "event_payload", "raw_events", "roi_crop", "crop_bytes",
})

CONFORMANT = "CONFORMANT"
VIOLATION = "VIOLATION"


def _is_pointer(v) -> bool:
    """A 32-byte commitment (64 hex, optional 0x prefix) or honestly None."""
    if v is None:
        return True
    if not isinstance(v, str):
        return False
    h = v[2:] if v.startswith("0x") else v
    return len(h) == 64 and all(c in "0123456789abcdefABCDEF" for c in h)


def check_roots_are_pointers(record: dict) -> list:
    """Violations: events_roots values that are not 32B commitments (inline blobs)."""
    out = []
    roots = record.get("events_roots")
    if roots is None:
        return out                       # no roots present is not a boundary violation
    if not isinstance(roots, dict):
        return [f"events_roots is {type(roots).__name__}, expected a dict of named roots"]
    for name, v in roots.items():
        if not _is_pointer(v):
            shape = type(v).__name__ + (f"[{len(v)}]" if isinstance(v, (list, str)) else "")
            out.append(f"events_roots.{name} is not a 32B commitment (got {shape}) - "
                       "inline payload crossing the boundary")
    return out


def check_no_inline_scene_payload(record: dict) -> list:
    """Violations: forbidden inline-payload keys or data-URI image values anywhere."""
    out = []

    def _walk(obj, path):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in _INLINE_SCENE_PAYLOAD_KEYS:
                    out.append(f"inline scene-payload key '{k}' at {path or '<root>'} - "
                               "belongs on the DA node, pointer-only at the boundary")
                _walk(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, it in enumerate(obj):
                _walk(it, f"{path}[{i}]")
        elif isinstance(obj, str) and obj[:11].lower() == "data:image/":
            out.append(f"data-URI image value at {path or '<root>'} - inline scene payload")

    _walk(record, "")
    return out


def assess_da_conformance(record: dict) -> dict:
    """Combined verdict. CONFORMANT iff no violations from either check."""
    violations = check_roots_are_pointers(record) + check_no_inline_scene_payload(record)
    return {
        "status": CONFORMANT if not violations else VIOLATION,
        "violations": violations,
        "law": "Arc 7 sidecar-pointer: bulk on DA, 32B commitment on the wire; scene "
               "payloads are DA-class, pointer-only at the boundary (alignment doc N2)",
        "advisory": True,
    }
