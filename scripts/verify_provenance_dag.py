#!/usr/bin/env python3
"""A2A-CDM build (2) - the gamer-sovereign provenance DAG, v0 (grok Q5-P5, grounded R03/R05).

The smallest shippable "sealed history of one agency": an index JSON binding one device_id
to its sessions' sealed artifacts (PoSP records, tri-plane manifests, WMP bundles), plus
this verifier that (a) checks every artifact's bytes against the index hash, (b) RE-RUNS
each artifact's own zero-trust verifier, and (c) checks device_id stability across
sessions. No chain, no token, no ioID required - a folder + a script.

Build the index over real artifacts, then verify it cold:

  python scripts/verify_provenance_dag.py --build --device-id <hex> \
      --session <session_id> <artifact.json> [...] --out dag_index.json
  python scripts/verify_provenance_dag.py dag_index.json

HONEST CEILINGS (printed with every verify - carry with every claim):
  * The index is PRODUCER-DECLARED: selective omission of bad sessions is NOT detected by
    v0 (the DAG's real attack - the Round-06 adversarial target).
  * device_id continuity proves SAME CERTIFIED CONTROLLER, never which human (no identity,
    no population stats, no FAR - per RP-7 claim-limiting rails).
  * N=1 / developer_self today: longitudinal is not broad.

ASCII-only output (cp1252-safe). Stdlib + repo verifiers only; no network.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

SCHEMA = "qortroller-provenance-dag-index-v0"

KIND_POSP = "posp"
KIND_MANIFEST = "tri_plane_manifest"
KIND_WMP_BUNDLE = "wmp_bundle"


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        txt = f.read()
    # .jsonl bundles: first line is the bundle record
    if path.endswith(".jsonl"):
        return json.loads(txt.splitlines()[0])
    return json.loads(txt)


def classify(doc: dict) -> str | None:
    """Kind detection by the artifact's own schema field - never by filename."""
    schema = str(doc.get("schema", ""))
    if schema.startswith("qortroller-posp"):
        return KIND_POSP
    if schema.startswith("qortroller-tri-plane-session"):
        return KIND_MANIFEST
    if schema.startswith("vapi-wmp-provenance-bundle"):
        return KIND_WMP_BUNDLE
    return None


def build_index(device_id: str, session_id: str, paths: list) -> dict:
    """v0 builder: one session per invocation (append sessions by re-running with the same
    --out; the builder merges). Artifacts are classified by their own schema field."""
    arts = []
    for p in paths:
        doc = _load_json(p)
        kind = classify(doc)
        if kind is None:
            raise SystemExit(f"[dag] REFUSED: {p} has no recognizable artifact schema")
        rel = os.path.relpath(os.path.abspath(p), _REPO).replace("\\", "/")
        arts.append({"path": rel, "kind": kind, "sha256": _sha256_file(p)})
    return {"session_id": session_id, "artifacts": arts}


# -- per-kind re-verification (the DAG re-runs each artifact's OWN verifier) -------------

def _verify_posp(doc: dict) -> tuple:
    from l9_presence.posp_verifier import verify_posp_record
    rep = verify_posp_record(doc)
    return rep.passed() or rep.overall == "PARTIAL", rep.overall


def _verify_manifest(doc: dict, session_docs: dict) -> tuple:
    from l9_presence.tri_plane_manifest import verify_tri_plane_manifest
    res = verify_tri_plane_manifest(doc,
                                    posp=session_docs.get(KIND_POSP),
                                    wmp_bundle=session_docs.get(KIND_WMP_BUNDLE))
    return bool(res["ok"]), "ok" if res["ok"] else "FAILED"


def _verify_bundle(doc: dict) -> tuple:
    from sdk.wmp_verify import verify_bundle
    res = verify_bundle(doc)   # offline defaults: stub/deferred paths, zero-trust logic
    return res.overall == "VERIFIED", res.overall


def verify_index(index: dict) -> int:
    print("=" * 78)
    print("QORTROLLER PROVENANCE DAG - verify (v0)")
    print("=" * 78)
    device_id = index.get("device_id", "")
    sessions = index.get("sessions", [])
    print(f"device_id: {device_id}")
    print(f"sessions : {len(sessions)}")
    failures = 0
    seen_device_ids = set()

    for s in sessions:
        sid = s.get("session_id", "?")
        print(f"\nSESSION {sid[:16]}...")
        session_docs = {}
        for a in s.get("artifacts", []):
            p = os.path.join(_REPO, a["path"])
            if not os.path.isfile(p):
                print(f"  [FAIL] {a['path']} - missing")
                failures += 1
                continue
            actual = _sha256_file(p)
            if actual != a["sha256"]:
                print(f"  [FAIL] {a['path']} - sha256 mismatch (bytes changed since sealing)")
                failures += 1
                continue
            doc = _load_json(p)
            session_docs[a["kind"]] = doc
        # re-run each artifact's own verifier (hash-clean ones only)
        for kind, doc in session_docs.items():
            if kind == KIND_POSP:
                okp, note = _verify_posp(doc)
                did = doc.get("device_id", "")
                seen_device_ids.add(did)
                if did != device_id:
                    print(f"  [FAIL] posp device_id {did[:12]}... != index device_id")
                    failures += 1
            elif kind == KIND_MANIFEST:
                okp, note = _verify_manifest(doc, session_docs)
            else:
                okp, note = _verify_bundle(doc)
            mark = "OK  " if okp else "FAIL"
            print(f"  [{mark}] {kind}: re-verified -> {note}")
            if not okp:
                failures += 1

    stable = seen_device_ids <= {device_id} and len(seen_device_ids) >= 1
    print(f"\ndevice_id stability: {'OK - single certified controller across all sealed sessions' if stable else 'FAIL - multiple device_ids in one agency index'}")
    if not stable:
        failures += 1

    print("-" * 78)
    print("CEILINGS: index is producer-declared (selective omission NOT detected - Round-06");
    print("target); device continuity != identity (no which-human/population/FAR claims);")
    print("N=1 developer_self today - longitudinal is not broad.")
    print("-" * 78)
    verdict = "DAG VERIFIED" if failures == 0 else f"DAG FAILED ({failures} failure(s))"
    print(f"VERDICT: {verdict}")
    return 0 if failures == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="QorTroller provenance-DAG index builder + verifier (v0)")
    ap.add_argument("index_or_artifacts", nargs="+")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--device-id", default="")
    ap.add_argument("--session", default="")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    if args.build:
        if not (args.device_id and args.session and args.out):
            raise SystemExit("[dag] --build requires --device-id, --session, --out")
        entry = build_index(args.device_id, args.session, args.index_or_artifacts)
        index = {"schema": SCHEMA, "device_id": args.device_id, "sessions": []}
        if os.path.isfile(args.out):
            index = _load_json(args.out)
            if index.get("device_id") != args.device_id:
                raise SystemExit("[dag] REFUSED: existing index binds a different device_id")
            index["sessions"] = [s for s in index["sessions"]
                                 if s.get("session_id") != args.session]
        index["sessions"].append(entry)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2)
        print(f"[dag] index written: {args.out} ({len(index['sessions'])} session(s))")
        return 0

    index = _load_json(args.index_or_artifacts[0])
    if index.get("schema") != SCHEMA:
        raise SystemExit(f"[dag] not a provenance-dag index (schema={index.get('schema')!r})")
    return verify_index(index)


if __name__ == "__main__":
    sys.exit(main())
