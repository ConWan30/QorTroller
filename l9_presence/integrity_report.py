"""UC-10 -- Tournament integrity report (qortroller-integrity-report-v0).

Per-event rollup of the pilot's per-match artifacts: N matches certified, verdict distributions,
anchored/VHR coverage -- the organizer's post-event "integrity report". REFERENCE-AND-BIND, same
discipline as UC-2 skill-strata: the report cites every match certificate by path+sha256, every
aggregate is a PURE, DETERMINISTIC function of the cited certs, and the verifier is simply
re-derivation (reload the cited certs, hash-compare, recompute, byte-compare).

CEILING (test-pinned): describes CERTIFICATE OUTCOMES only. The pilot ceilings ride along verbatim
-- advisory, never-ban, no player identification, no cross-event comparison. An integrity report
says "N matches at this event carried these verdict classes", never "player X cheated" and never
"this event is cleaner than that event". Gate honesty: structure ships NOW; a real pilot fills it
(>=N certs); a rollup over 1 cert is honestly labeled n_certs=1.

Pure stdlib; I/O (loading cert files) is injected, mirroring skill_strata.verify_strata_report.
"""
from __future__ import annotations

import hashlib
import json

SCHEMA = "qortroller-integrity-report-v0"

CEILING = {
    "scope": "certificate outcomes only",
    "advisory": True,
    "never_ban": "reports never gate players; adjudication stays with the organizer's process",
    "no_player_identification": "no gamer identity, no per-player rows — session/match level only",
    "no_cross_event_comparison": "one event per report; league tables re-enter the population gate",
}


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _cert_row(cert: dict, *, path: str, digest: str) -> dict:
    """One match-certificate row: verdict classes + coverage flags, nothing player-shaped."""
    surfaces = cert.get("surfaces") or {}
    kas = (surfaces.get("kas") or {})
    posp = (surfaces.get("posp") or {})
    vhr = surfaces.get("vhr") or None
    anchor = surfaces.get("anchor") or None
    return {
        "path": path,
        "sha256": digest,
        "schema": cert.get("schema"),
        "session_id": cert.get("session_id"),
        "kas_verdict": kas.get("verdict"),
        "posp_verdict": posp.get("verdict"),
        "vhr_present": bool(vhr),
        "anchored": bool(anchor and (anchor.get("tx") or anchor.get("block"))),
        "advisory": bool(cert.get("advisory", True)),
    }


def build_integrity_report(certs: list[tuple[str, bytes]], *, event_label: str = "",
                           generated_at: str = "") -> dict:
    """Assemble the per-event rollup from (path, raw_bytes) cert files. Unparseable certs are
    counted honestly as invalid rows, never silently dropped."""
    rows: list[dict] = []
    invalid: list[dict] = []
    kas_dist: dict[str, int] = {}
    posp_dist: dict[str, int] = {}
    n_vhr = 0
    n_anchored = 0
    for path, raw in certs:
        digest = sha256_bytes(raw)
        try:
            cert = json.loads(raw.decode("utf-8"))
        except Exception:  # noqa: BLE001
            invalid.append({"path": path, "sha256": digest, "reason": "unparseable"})
            continue
        row = _cert_row(cert, path=path, digest=digest)
        rows.append(row)
        kv = row["kas_verdict"] or "ABSENT"
        pv = row["posp_verdict"] or "ABSENT"
        kas_dist[kv] = kas_dist.get(kv, 0) + 1
        posp_dist[pv] = posp_dist.get(pv, 0) + 1
        if row["vhr_present"]:
            n_vhr += 1
        if row["anchored"]:
            n_anchored += 1

    n = len(rows)
    return {
        "schema": SCHEMA,
        "event_label": event_label,
        "generated_at": generated_at,
        "ceiling": dict(CEILING),
        "n_certs": n,
        "n_invalid": len(invalid),
        "kas_verdict_distribution": dict(sorted(kas_dist.items())),
        "posp_verdict_distribution": dict(sorted(posp_dist.items())),
        "vhr_coverage": {"n": n_vhr, "rate": round(n_vhr / n, 4) if n else 0.0},
        "anchor_coverage": {"n": n_anchored, "rate": round(n_anchored / n, 4) if n else 0.0},
        "certificates": rows,
        "invalid_certificates": invalid,
        "notes": [
            "REFERENCE-AND-BIND: every aggregate re-derives from the cited certs (path+sha256)",
            "certificate outcomes only — no player identification, no cross-event comparison",
            "a real pilot fills this structure; small n is reported honestly, never extrapolated",
        ],
    }


def verify_integrity_report(report: dict, load_bytes) -> dict:
    """Re-derivation verifier (fail-closed): every cited cert must exist + hash-match, and
    recomputing the rollup over the cited bytes must reproduce every row + distribution.
    `load_bytes(path) -> bytes|None` injected (I/O stays in the runner)."""
    checks: list = []

    def _chk(name: str, ok: bool, note: str = "") -> bool:
        checks.append({"name": name, "ok": bool(ok), "note": note})
        return bool(ok)

    ok = _chk("schema", report.get("schema") == SCHEMA, f"schema={report.get('schema')!r}")
    ok &= _chk("ceiling_verbatim", report.get("ceiling") == CEILING,
               "ceiling must match CEILING exactly (advisory/never-ban rail)")

    certs: list[tuple[str, bytes]] = []
    all_present = True
    for row in (report.get("certificates") or []) + (report.get("invalid_certificates") or []):
        raw = load_bytes(row.get("path")) if row.get("path") else None
        if raw is None:
            all_present = _chk(f"cert_present:{row.get('path')}", False, "cited cert missing") and all_present
            continue
        if sha256_bytes(raw) != row.get("sha256"):
            all_present = _chk(f"cert_sha256:{row.get('path')}", False, "hash mismatch (tamper rail)") and all_present
            continue
        certs.append((row["path"], raw))
    ok &= _chk("all_certs_present_and_hashed", all_present, "")
    if not all_present:
        return {"ok": False, "checks": checks}

    rederived = build_integrity_report(certs, event_label=report.get("event_label", ""),
                                       generated_at=report.get("generated_at", ""))
    for field in ("n_certs", "n_invalid", "kas_verdict_distribution", "posp_verdict_distribution",
                  "vhr_coverage", "anchor_coverage", "certificates"):
        ok &= _chk(f"rederive:{field}", rederived.get(field) == report.get(field),
                   "must re-derive from cited certs")
    return {"ok": bool(ok), "checks": checks}
