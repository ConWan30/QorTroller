"""Capture-session labeler for the Phase 2 consistency experiment.

Frictionless session tagging during real capture. Maintains a `sessions.json`
manifest (the exact format `run_consistency_experiment.py --real --sessions` reads)
plus a sidecar `.open` marker for the currently-recording session.

Workflow:
    # rigged classes (you know the label at setup time):
    python scripts/capture_session_labeler.py start --device <id> --class HUMAN_AIM_ASSIST
    ...play...
    python scripts/capture_session_labeler.py stop

    # human ranked play you must label AFTER the fact by performance (protocol section 0):
    python scripts/capture_session_labeler.py start --device <id> --pending
    ...play a ranked session...
    python scripts/capture_session_labeler.py stop
    # later, by performance metrics -- NOT by intention:
    python scripts/capture_session_labeler.py relabel --index 3 --class PRO_SKILL

    python scripts/capture_session_labeler.py list
    python scripts/capture_session_labeler.py validate     # all entries label-resolved + sane?

Honesty rail: the post-hoc relabel path exists precisely so PRO_SKILL vs
HUMAN_CLEAN is decided by measured performance, not by playing "for the camera"
(the single-subject confound in protocol section 0).

Stdlib only. No bridge import.
"""
from __future__ import annotations

import argparse
import json
import os
import time

_VALID_CLASSES = {
    "HUMAN_CLEAN", "BOT_FULL", "HUMAN_AIM_ASSIST", "HUMAN_RELAY", "PRO_SKILL",
}
_PENDING = "PENDING"
DEFAULT_MANIFEST = "audits/consistency-sessions.json"
DEFAULT_FRESHNESS_S = 30.0


def _open_path(manifest: str) -> str:
    return manifest + ".open"


def _load(manifest: str) -> list:
    if not os.path.exists(manifest):
        return []
    return json.loads(open(manifest, encoding="utf-8").read())


def _save(manifest: str, entries: list) -> None:
    os.makedirs(os.path.dirname(manifest) or ".", exist_ok=True)
    with open(manifest, "w", encoding="utf-8") as f:
        f.write(json.dumps(entries, indent=2) + "\n")


# --- testable core ---------------------------------------------------------

def start_session(manifest: str, device_id: str, class_label: str,
                  freshness_s: float = DEFAULT_FRESHNESS_S, now: float | None = None) -> dict:
    op = _open_path(manifest)
    if os.path.exists(op):
        raise RuntimeError("a session is already open; call stop first")
    if class_label != _PENDING and class_label not in _VALID_CLASSES:
        raise ValueError(f"invalid class {class_label!r}; one of {sorted(_VALID_CLASSES)} or PENDING")
    marker = {
        "device_id": device_id,
        "class_label": class_label,
        "t_start": float(now if now is not None else time.time()),
        "presence_freshness_s": float(freshness_s),
    }
    os.makedirs(os.path.dirname(op) or ".", exist_ok=True)
    with open(op, "w", encoding="utf-8") as f:
        f.write(json.dumps(marker) + "\n")
    return marker


def stop_session(manifest: str, now: float | None = None) -> dict:
    op = _open_path(manifest)
    if not os.path.exists(op):
        raise RuntimeError("no session open; call start first")
    marker = json.loads(open(op, encoding="utf-8").read())
    entry = {
        "device_id": marker["device_id"],
        "t_start": marker["t_start"],
        "t_end": float(now if now is not None else time.time()),
        "class_label": marker["class_label"],
        "presence_freshness_s": marker.get("presence_freshness_s", DEFAULT_FRESHNESS_S),
    }
    entries = _load(manifest)
    entries.append(entry)
    _save(manifest, entries)
    os.remove(op)
    return entry


def relabel(manifest: str, index: int, class_label: str) -> dict:
    if class_label not in _VALID_CLASSES:
        raise ValueError(f"invalid class {class_label!r}; one of {sorted(_VALID_CLASSES)}")
    entries = _load(manifest)
    if not (0 <= index < len(entries)):
        raise IndexError(f"index {index} out of range (0..{len(entries) - 1})")
    entries[index]["class_label"] = class_label
    _save(manifest, entries)
    return entries[index]


def validate(manifest: str) -> list[str]:
    """Return a list of issues; empty list == manifest is run-ready."""
    issues = []
    for i, e in enumerate(_load(manifest)):
        cl = e.get("class_label")
        if cl == _PENDING:
            issues.append(f"[{i}] PENDING — relabel by performance (PRO_SKILL/HUMAN_CLEAN) before running")
        elif cl not in _VALID_CLASSES:
            issues.append(f"[{i}] invalid class_label {cl!r}")
        if float(e.get("t_end", 0)) <= float(e.get("t_start", 0)):
            issues.append(f"[{i}] t_end <= t_start")
        if not e.get("device_id"):
            issues.append(f"[{i}] missing device_id")
    return issues


# --- CLI -------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Phase 2 capture-session labeler")
    ap.add_argument("--manifest", default=DEFAULT_MANIFEST)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("start", help="begin recording a session")
    s.add_argument("--device", required=True)
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--class", dest="klass", choices=sorted(_VALID_CLASSES))
    g.add_argument("--pending", action="store_true", help="human ranked play; label post-hoc")
    s.add_argument("--freshness", type=float, default=DEFAULT_FRESHNESS_S)

    sub.add_parser("stop", help="finalize the open session into the manifest")

    r = sub.add_parser("relabel", help="set the class of a finalized session by performance")
    r.add_argument("--index", type=int, required=True)
    r.add_argument("--class", dest="klass", required=True, choices=sorted(_VALID_CLASSES))

    sub.add_parser("list", help="show manifest entries")
    sub.add_parser("validate", help="check the manifest is run-ready")

    args = ap.parse_args(argv)
    mf = args.manifest

    if args.cmd == "start":
        cl = _PENDING if args.pending else args.klass
        m = start_session(mf, args.device, cl, args.freshness)
        print(f"[labeler] START {cl} device={args.device[:8]}.. t_start={m['t_start']:.0f}")
    elif args.cmd == "stop":
        e = stop_session(mf)
        dur = e["t_end"] - e["t_start"]
        print(f"[labeler] STOP  {e['class_label']} dur={dur:.0f}s -> {mf}")
        if e["class_label"] == _PENDING:
            print("[labeler] NOTE: session is PENDING — relabel by performance before running.")
    elif args.cmd == "relabel":
        e = relabel(mf, args.index, args.klass)
        print(f"[labeler] RELABEL [{args.index}] -> {e['class_label']}")
    elif args.cmd == "list":
        for i, e in enumerate(_load(mf)):
            print(f"  [{i}] {e['class_label']:<17} dur={e['t_end'] - e['t_start']:.0f}s "
                  f"device={e['device_id'][:8]}..")
    elif args.cmd == "validate":
        issues = validate(mf)
        if not issues:
            print(f"[labeler] OK — {len(_load(mf))} entries, manifest is run-ready.")
        else:
            print(f"[labeler] {len(issues)} issue(s):")
            for it in issues:
                print("  " + it)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
