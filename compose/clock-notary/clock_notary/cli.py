"""CLI: export envelope; wrap with optional consent."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from .envelope import ObservationEnvelope, envelope_from_recap
from .wrap import ConsentRecord, wrap_notary

def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))

def _write(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")

def cmd_export(args):
    env = envelope_from_recap(_load(Path(args.recap)))
    _write(Path(args.out), env.to_dict()); print(env.clock_commitment); return 0

def cmd_wrap(args):
    recap_or_env = _load(Path(args.envelope))
    if recap_or_env.get("schema") == "qoresence.observation-envelope.v0":
        env = ObservationEnvelope(recap_or_env["schema"], recap_or_env["session_id"], recap_or_env["plane"], recap_or_env.get("title_plane", "observation"), bool(recap_or_env.get("hid_on_console", True)), recap_or_env.get("ticks") or [], recap_or_env.get("sidecar_hashes") or {}, recap_or_env["clock_commitment"], recap_or_env.get("extras") or {})
    else:
        env = envelope_from_recap(recap_or_env)
    consent = None
    if args.consent:
        raw = _load(Path(args.consent))
        consent = ConsentRecord(raw.get("gamer") or "", bool(raw.get("granted")), raw.get("purpose") or "portcert", raw.get("signed_by") or "", raw.get("note") or "")
    result = wrap_notary(env, consent)
    _write(Path(args.out), result.to_dict()); print(result.status)
    if result.status != "SEALED":
        print(result.reason, file=sys.stderr); return 2
    return 0

def main(argv=None):
    parser = argparse.ArgumentParser(prog="clock-notary")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("export"); p.add_argument("--recap", required=True); p.add_argument("--out", default="observation-envelope.json"); p.set_defaults(func=cmd_export)
    w = sub.add_parser("wrap"); w.add_argument("--envelope", required=True); w.add_argument("--consent"); w.add_argument("--out", default="notary-wrap.json"); w.set_defaults(func=cmd_wrap)
    args = parser.parse_args(argv)
    return args.func(args)

if __name__ == "__main__":
    raise SystemExit(main())
