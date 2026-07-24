"""UC-10 integrity-report tests. REFERENCE-AND-BIND rollup over match certificates: aggregates
re-derive from cited certs (verify = reload + hash + recompute), ceilings ride verbatim, tampering
fails closed. Small-n honesty pinned (structure ships now; a pilot fills it).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from l9_presence.integrity_report import (
    CEILING,
    SCHEMA,
    build_integrity_report,
    sha256_bytes,
    verify_integrity_report,
)


def _cert_bytes(session="m1", kas="AUTHORED_SESSION", posp="SYNCHRONIZED", vhr=True, anchor=True):
    doc = {
        "schema": "qortroller-match-certificate-v0",
        "session_id": session,
        "advisory": True,
        "surfaces": {
            "kas": {"verdict": kas},
            "posp": {"verdict": posp},
            "vhr": ({"proof_ref": "p.json"} if vhr else None),
            "anchor": ({"tx": "0xabc", "block": 1} if anchor else None),
        },
    }
    return json.dumps(doc).encode()


def _corpus():
    return [
        ("certs/m1.json", _cert_bytes("m1")),
        ("certs/m2.json", _cert_bytes("m2", kas="HYGIENE_FAIL", vhr=False, anchor=False)),
        ("certs/m3.json", _cert_bytes("m3", posp="PARTIAL_SURFACES")),
    ]


def test_rollup_aggregates_and_cites():
    r = build_integrity_report(_corpus(), event_label="pilot-1")
    assert r["schema"] == SCHEMA
    assert r["n_certs"] == 3 and r["n_invalid"] == 0
    assert r["kas_verdict_distribution"] == {"AUTHORED_SESSION": 2, "HYGIENE_FAIL": 1}
    assert r["posp_verdict_distribution"] == {"PARTIAL_SURFACES": 1, "SYNCHRONIZED": 2}
    assert r["vhr_coverage"] == {"n": 2, "rate": round(2 / 3, 4)}
    assert r["anchor_coverage"] == {"n": 2, "rate": round(2 / 3, 4)}
    # every row cites path + sha256 (REFERENCE-AND-BIND)
    for row in r["certificates"]:
        assert row["path"] and len(row["sha256"]) == 64


def test_unparseable_cert_counted_honestly():
    r = build_integrity_report([("certs/bad.json", b"not-json{{")])
    assert r["n_certs"] == 0 and r["n_invalid"] == 1
    assert r["invalid_certificates"][0]["reason"] == "unparseable"


def test_small_n_reported_honestly():
    r = build_integrity_report([("certs/only.json", _cert_bytes())])
    assert r["n_certs"] == 1                      # never extrapolated
    assert "never extrapolated" in " ".join(r["notes"])


def test_ceiling_rides_verbatim():
    r = build_integrity_report(_corpus())
    assert r["ceiling"] == CEILING
    assert r["ceiling"]["advisory"] is True
    assert "no gamer identity" in r["ceiling"]["no_player_identification"]


def test_verify_rederives_ok():
    corpus = dict(_corpus())
    r = build_integrity_report(list(corpus.items()), event_label="pilot-1")
    v = verify_integrity_report(r, lambda p: corpus.get(p))
    assert v["ok"] is True


def test_verify_fails_closed_on_tampered_cert():
    corpus = dict(_corpus())
    r = build_integrity_report(list(corpus.items()))
    corpus["certs/m1.json"] = _cert_bytes("m1", kas="HYGIENE_FAIL")   # tamper post-report
    v = verify_integrity_report(r, lambda p: corpus.get(p))
    assert v["ok"] is False


def test_verify_fails_closed_on_missing_cert():
    corpus = dict(_corpus())
    r = build_integrity_report(list(corpus.items()))
    del corpus["certs/m2.json"]
    v = verify_integrity_report(r, lambda p: corpus.get(p))
    assert v["ok"] is False


def test_verify_fails_closed_on_doctored_distribution():
    corpus = dict(_corpus())
    r = build_integrity_report(list(corpus.items()))
    r["kas_verdict_distribution"] = {"AUTHORED_SESSION": 3}           # inflate the clean count
    v = verify_integrity_report(r, lambda p: corpus.get(p))
    assert v["ok"] is False
