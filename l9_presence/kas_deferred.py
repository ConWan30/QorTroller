"""Deferred-Attestation Tier (RP-2d) -- qortroller-kas-deferred-v0.

THE CLAIM: "N kill events in THIS session are attested post-hoc from the session's
manifest-committed crop archive, each preserving the live conjunction semantics
(own-handle-in-killer-slot DURING a live R2 window) wherever the window join holds."

WHY THIS TIER EXISTS (F-RP2-1, Match 14): Remote Play thins live crops-per-kill, so the
K=3 live promotion floor starves even when the dense archive read the kills cleanly. The
archive is not diagnostics -- it is manifest-committed live evidence (per-crop SHA-256s +
session_id sealed at daemon stop, referenced by PoSP). Attesting from it post-hoc is the
same evidence read later; at developer_self scope the trust boundary is identical (the
same rig witnesses both). The only thing live attestation adds is real-time-ness.

REFERENCE-AND-BIND (PoSP precedent, D-CERT-6 discipline): NO new domain tag, NO new
commitment primitive, NO FROZEN-v1 family. Schema string only. Integrity derives
entirely from what the record REFERENCES: the manifest's per-crop SHA-256s, the live
KAS record's commitment (QORTROLLER-KAS-v0), and the U1 session_id joining them.
A verifier re-hashes the referenced crops and re-checks the window intersections.

VERDICTS (closed enums, fail-closed):
  per-cluster:  DEFERRED_AUTHORED   size >= K AND cluster span intersects a live R2
                                    window (the conjunction held; evaluated post-hoc)
                DEFERRED_OBSERVED   size >= K but NO window overlap -- the kill row was
                                    on screen, the input conjunction is NOT established
  per-session:  DEFERRED_AUTHORED_SESSION  >= min_kills DEFERRED_AUTHORED clusters
                DEFERRED_OBSERVED_ONLY     evidence exists but no authored cluster
                UNVERIFIABLE               session-id mismatch / sha not in manifest /
                                           inherited hygiene failure / malformed inputs

NEVER-CONFLATED RAIL: the live verdict string "AUTHORED_SESSION" is NEVER emitted by
this module. Deferred is a distinct, honestly-labeled tier -- pinned by test.

PURE stdlib. No bridge/session/chain imports.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Optional

DEFERRED_SCHEMA = "qortroller-kas-deferred-v0"   # schema string ONLY -- not a domain tag

# per-cluster verdicts
DEFERRED_AUTHORED = "DEFERRED_AUTHORED"
DEFERRED_OBSERVED = "DEFERRED_OBSERVED"

# per-session verdicts
DEFERRED_AUTHORED_SESSION = "DEFERRED_AUTHORED_SESSION"
DEFERRED_OBSERVED_ONLY = "DEFERRED_OBSERVED_ONLY"
UNVERIFIABLE = "UNVERIFIABLE"

DEFAULT_K_FLOOR = 3          # mirrors killfeed_session_anchor.DEFAULT_K_CONSISTENCY
DEFAULT_MIN_KILLS = 2        # mirrors kill_authorship_session.DEFAULT_MIN_KILLS

# live KAS verdicts this tier inherits hygiene/verifiability from
_LIVE_HYGIENE_FAIL = "HYGIENE_FAIL"
_LIVE_UNVERIFIABLE = "UNVERIFIABLE"


@dataclass
class DeferredAttestationRecord:
    """One session's post-hoc authorship attestation over its manifest-committed archive."""
    schema: str
    verdict: str
    session_id: Optional[str]
    session_display: Optional[str]
    k_floor: int
    min_kills: int
    engine: Optional[str]
    deferred_authored: int
    deferred_observed: int
    unpromotable_clusters: int
    clusters: list = field(default_factory=list)     # per-cluster dicts (see _classify_cluster)
    windows_used: int = 0
    source_kas_commitment: Optional[str] = None      # the live KAS this defers FROM
    source_kas_verdict: Optional[str] = None
    hygiene_inherited: Optional[dict] = None
    manifest_count: Optional[int] = None
    notes: list = field(default_factory=list)
    advisory: bool = True                            # machine-readable: never a hard gate

    def to_dict(self) -> dict:
        return {
            "schema": self.schema, "verdict": self.verdict,
            "session_id": self.session_id, "session_display": self.session_display,
            "k_floor": self.k_floor, "min_kills": self.min_kills, "engine": self.engine,
            "deferred_authored": self.deferred_authored,
            "deferred_observed": self.deferred_observed,
            "unpromotable_clusters": self.unpromotable_clusters,
            "clusters": self.clusters, "windows_used": self.windows_used,
            "source_kas_commitment": self.source_kas_commitment,
            "source_kas_verdict": self.source_kas_verdict,
            "hygiene_inherited": self.hygiene_inherited,
            "manifest_count": self.manifest_count,
            "notes": self.notes, "advisory": self.advisory,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


def _spans_overlap(a0: float, a1: float, b0: float, b1: float) -> bool:
    return a0 <= b1 and b0 <= a1


def _cluster_span_ms(cluster: dict):
    """Cluster reads carry ts_ns (crop-filename nanoseconds -> wall ms)."""
    ts = [r.get("ts_ns") for r in (cluster.get("reads") or []) if r.get("ts_ns")]
    if not ts:
        return None
    return (min(ts) / 1e6, max(ts) / 1e6)


def _classify_cluster(cluster: dict, windows: list, k_floor: int,
                      manifest_shas: dict, notes: list):
    """Classify one scan cluster. Returns (cluster_out, verdict_or_None, poisoned).
    poisoned=True when a referenced crop's sha is absent/mismatched vs the manifest
    (anti-tamper -- the whole record fails, never papered over)."""
    reads = cluster.get("reads") or []
    size = int(cluster.get("size", len(reads)))

    # anti-tamper: every read's crop must exist in the manifest with the SAME sha
    for r in reads:
        fname, sha = r.get("file"), r.get("sha256")
        if not fname or manifest_shas.get(fname) != sha:
            notes.append(f"anti-tamper: crop {fname!r} sha not in manifest (or mismatch)")
            return None, None, True

    span = _cluster_span_ms(cluster)
    out = {
        "size": size, "texts": cluster.get("texts"),
        "crop_files": [r.get("file") for r in reads],
        "crop_shas": [r.get("sha256") for r in reads],
        "span_ms": [round(span[0], 1), round(span[1], 1)] if span else None,
    }

    if size < k_floor:
        out["verdict"] = None
        out["note"] = f"below K={k_floor} floor -- un-promotable, never attested"
        return out, None, False

    window_hit = None
    if span:
        for w in windows:
            if _spans_overlap(span[0], span[1], float(w[0]), float(w[1])):
                window_hit = [float(w[0]), float(w[1])]
                break
    if window_hit:
        out["verdict"] = DEFERRED_AUTHORED
        out["window_hit_ms"] = window_hit
        return out, DEFERRED_AUTHORED, False
    out["verdict"] = DEFERRED_OBSERVED
    out["window_hit_ms"] = None
    return out, DEFERRED_OBSERVED, False


def build_deferred_record(*, scan: dict, manifest: dict, windows,
                          kas_record: Optional[dict] = None,
                          k_floor: int = DEFAULT_K_FLOOR,
                          min_kills: int = DEFAULT_MIN_KILLS) -> DeferredAttestationRecord:
    """Fold a v2 scan + manifest + live R2 windows (+ the live KAS record) into a
    DeferredAttestationRecord. FAIL-CLOSED throughout (see module doc)."""
    notes: list = []
    session_id = (manifest or {}).get("session_id")
    session_display = (manifest or {}).get("session_display")

    def _unverifiable(reason: str) -> DeferredAttestationRecord:
        notes.append(f"unverifiable: {reason}")
        return DeferredAttestationRecord(
            schema=DEFERRED_SCHEMA, verdict=UNVERIFIABLE, session_id=session_id,
            session_display=session_display, k_floor=k_floor, min_kills=min_kills,
            engine=(scan or {}).get("engine"), deferred_authored=0, deferred_observed=0,
            unpromotable_clusters=0, notes=notes,
            source_kas_commitment=(kas_record or {}).get("commitment"),
            source_kas_verdict=(kas_record or {}).get("verdict"),
            manifest_count=(manifest or {}).get("count"))

    if not manifest or not session_id:
        return _unverifiable("no manifest / no session_id (the U1 join key)")
    if not scan or scan.get("scan_version") != "rp-ocr-precision-v2":
        return _unverifiable("scan missing or not v2 (per-read provenance required)")

    # session join: the scan's archive dir must be the manifest's archive (by display name)
    arch = str(scan.get("archive") or "")
    if session_display and session_display not in arch.replace("\\", "/"):
        return _unverifiable(f"scan archive {arch!r} does not match session_display "
                             f"{session_display!r} -- anti-assertion")

    # KAS join + hygiene inheritance
    hygiene = None
    if kas_record:
        kas_sid = kas_record.get("session_id")
        if kas_sid and str(kas_sid) != str(session_id):
            return _unverifiable("KAS session_id mismatch vs manifest -- anti-assertion")
        if kas_record.get("verdict") in (_LIVE_HYGIENE_FAIL, _LIVE_UNVERIFIABLE):
            return _unverifiable(f"live KAS verdict {kas_record.get('verdict')!r} inherited "
                                 "-- no deferred claim over a dirty/unverifiable capture")
        hygiene = kas_record.get("hygiene")

    win_list = [(float(w[0]), float(w[1])) for w in (windows or [])]
    if not win_list:
        notes.append("no live R2 windows supplied -- every K-floor cluster is "
                     "DEFERRED_OBSERVED (input conjunction cannot be established)")

    manifest_shas = {f.get("file"): f.get("sha256") for f in (manifest.get("files") or [])}

    clusters_out: list = []
    n_auth = n_obs = n_unprom = 0
    for cluster in (scan.get("clusters") or []):
        out, verdict, poisoned = _classify_cluster(cluster, win_list, k_floor,
                                                   manifest_shas, notes)
        if poisoned:
            return _unverifiable("cluster crop failed manifest sha check (anti-tamper)")
        clusters_out.append(out)
        if verdict == DEFERRED_AUTHORED:
            n_auth += 1
        elif verdict == DEFERRED_OBSERVED:
            n_obs += 1
        else:
            n_unprom += 1

    if n_auth >= min_kills:
        verdict = DEFERRED_AUTHORED_SESSION
    elif n_auth or n_obs:
        verdict = DEFERRED_OBSERVED_ONLY
        if n_auth:
            notes.append(f"{n_auth} authored cluster(s) below min_kills={min_kills}")
    else:
        verdict = UNVERIFIABLE
        notes.append("unverifiable: no K-floor clusters in the archive scan")

    return DeferredAttestationRecord(
        schema=DEFERRED_SCHEMA, verdict=verdict, session_id=session_id,
        session_display=session_display, k_floor=k_floor, min_kills=min_kills,
        engine=scan.get("engine"), deferred_authored=n_auth, deferred_observed=n_obs,
        unpromotable_clusters=n_unprom, clusters=clusters_out, windows_used=len(win_list),
        source_kas_commitment=(kas_record or {}).get("commitment"),
        source_kas_verdict=(kas_record or {}).get("verdict"),
        hygiene_inherited=hygiene, manifest_count=manifest.get("count"), notes=notes)


def slice_scan_by_spans(scan: dict, spans_ms) -> list:
    """Per-match evidence slicing (LUMEN-2 x RP-2d composition): split a v2 scan's
    clusters by match spans (from the match-state timeline) into per-match scan dicts,
    each feedable to build_deferred_record unchanged. A cluster belongs to the span its
    midpoint falls in; clusters outside every span are returned under the final
    "unassigned" entry (honest — post-match sightings etc. are never silently dropped).
    Returns [{"span_ms": [a,b], "scan": <scan-shaped dict>}, ...,
             {"span_ms": None, "scan": <unassigned>}]. Cores stay pure: this is
    composition, not a new verdict path."""
    spans = [(float(a), float(b)) for a, b in (spans_ms or [])]
    buckets = [[] for _ in spans]
    unassigned: list = []
    for c in (scan or {}).get("clusters") or []:
        ts = [r.get("ts_ns") for r in (c.get("reads") or []) if r.get("ts_ns")]
        if not ts:
            unassigned.append(c)
            continue
        mid = (min(ts) + max(ts)) / 2 / 1e6
        for i, (a, b) in enumerate(spans):
            if a <= mid <= b:
                buckets[i].append(c)
                break
        else:
            unassigned.append(c)

    def _sub(clusters):
        return {"scan_version": scan.get("scan_version"), "archive": scan.get("archive"),
                "engine": scan.get("engine"), "clusters": clusters}

    out = [{"span_ms": [a, b], "scan": _sub(cl)} for (a, b), cl in zip(spans, buckets)]
    out.append({"span_ms": None, "scan": _sub(unassigned)})
    return out


def verify_deferred_record(record: dict, manifest: dict, archive_dir: str) -> dict:
    """Offline verifier mirror: re-hash every referenced crop against BOTH the manifest
    and the record; re-check verdict arithmetic. Returns {ok, checks: [...]}."""
    checks: list = []

    def _chk(name, ok, note):
        checks.append({"name": name, "ok": bool(ok), "note": note})
        return ok

    ok = True
    ok &= _chk("schema", record.get("schema") == DEFERRED_SCHEMA,
               f"schema={record.get('schema')!r}")
    ok &= _chk("session_id_join", record.get("session_id") == manifest.get("session_id"),
               "record session_id == manifest session_id")
    ok &= _chk("never_live_verdict", record.get("verdict") != "AUTHORED_SESSION",
               "deferred record must never carry the LIVE verdict string")

    manifest_shas = {f.get("file"): f.get("sha256") for f in (manifest.get("files") or [])}
    n_auth = n_obs = 0
    for c in (record.get("clusters") or []):
        v = c.get("verdict")
        if v == DEFERRED_AUTHORED:
            n_auth += 1
        elif v == DEFERRED_OBSERVED:
            n_obs += 1
        if v not in (DEFERRED_AUTHORED, DEFERRED_OBSERVED):
            continue
        for fname, sha in zip(c.get("crop_files") or [], c.get("crop_shas") or []):
            if manifest_shas.get(fname) != sha:
                ok &= _chk(f"manifest_sha:{fname}", False, "sha not in manifest")
                continue
            path = os.path.join(archive_dir, fname)
            if os.path.isfile(path):
                h = hashlib.sha256(open(path, "rb").read()).hexdigest()
                ok &= _chk(f"disk_sha:{fname}", h == sha, "recomputed crop hash")
            else:
                ok &= _chk(f"disk_sha:{fname}", False, "crop file missing on disk")
    ok &= _chk("counts", n_auth == record.get("deferred_authored", -1)
               and n_obs == record.get("deferred_observed", -1),
               f"recount authored={n_auth} observed={n_obs}")
    expect = (DEFERRED_AUTHORED_SESSION if n_auth >= int(record.get("min_kills", 2))
              else (DEFERRED_OBSERVED_ONLY if (n_auth or n_obs) else UNVERIFIABLE))
    if record.get("verdict") != UNVERIFIABLE:
        ok &= _chk("verdict_arithmetic", record.get("verdict") == expect,
                   f"expected {expect} from recount")
    return {"ok": bool(ok), "checks": checks}
