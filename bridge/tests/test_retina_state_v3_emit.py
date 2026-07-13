"""TRA-1 T6.6a tests - session-close v3 emit (daemon hook, default-off, fail-open).

Verifies the flag gating, conformant-event filtering, the self-verifying record write, the honest
null on no conformant events, the retina_event_log read, and the fail-open daemon hook - all with
synthetic session data (no card, no live daemon). Poseidon mocked via the module hook.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from bridge.vapi_bridge import retina_events_root as rer
from bridge.vapi_bridge.retina_event_std import make_event
from bridge.vapi_bridge.retina_state_v3_record import verify_retina_state_v3_record
import retina_state_v3_emit as emit


def _mock_chain(elems):
    return hashlib.sha256(",".join(str(x) for x in elems).encode()).digest()


@pytest.fixture(autouse=True)
def _mock_poseidon():
    rer.set_poseidon_chain_fn(_mock_chain)
    yield
    rer.set_poseidon_chain_fn(None)


def _events():
    return [make_event("x_qortroller.kill", 1.0, "retina.killfeed", killer="Qortrola30", victim="A"),
            make_event("x_qortroller.kill", 2.0, "retina.killfeed", killer="rosa sparks", victim="B")]


def _seed_db(path: Path, created_at: float) -> None:
    con = sqlite3.connect(str(path))
    con.execute("CREATE TABLE retina_event_log (id INTEGER PRIMARY KEY, created_at REAL, "
                "events_json TEXT, record_hash_hex TEXT)")
    con.execute("INSERT INTO retina_event_log (created_at, events_json, record_hash_hex) VALUES (?,?,?)",
                (created_at, json.dumps(_events()), "abc"))
    con.commit()
    con.close()


def test_emit_enabled_flag(monkeypatch):
    monkeypatch.delenv("RETINA_STATE_V3_EMIT_ENABLED", raising=False)
    assert not emit.emit_enabled()
    monkeypatch.setenv("RETINA_STATE_V3_EMIT_ENABLED", "true")
    assert emit.emit_enabled()


def test_conformant_events_filters():
    good = make_event("x_qortroller.kill", 1.0, "cam", killer="Q", victim="V")
    bad = {"type": "x_q.kill", "t": 1.0, "src": "cam", "verdict": "OWN"}   # asserting -> dropped
    junk = {"nope": 1}                                                      # missing required -> dropped
    assert emit.conformant_events([good, bad, junk]) == [good]


def test_emit_writes_self_verifying_record(tmp_path):
    out = emit.emit_session_v3_record(_events(), device_id="aa" * 32, ts_ns=111,
                                      label="testsess", out_dir=tmp_path)
    assert out is not None and out.exists()
    rec = json.loads(out.read_text(encoding="utf-8"))
    assert rec["schema"] == "qortroller-retina-state-v3" and rec["n_events"] == 2
    assert verify_retina_state_v3_record(rec)


def test_emit_honest_null_no_conformant(tmp_path):
    assert emit.emit_session_v3_record([{"nope": 1}], device_id="aa" * 32, ts_ns=1,
                                       label="x", out_dir=tmp_path) is None


def test_read_session_events_from_db(tmp_path):
    db = tmp_path / "s.db"
    _seed_db(db, created_at=100.0)
    got = emit.read_session_events(str(db), 50.0, 150.0)
    assert len(got) == 2 and got[0]["killer"] == "Qortrola30"


def test_read_session_events_failopen_missing_db():
    assert emit.read_session_events("/no/such/db.sqlite", 0.0, 1e12) == []


def test_maybe_emit_flag_off_is_noop(monkeypatch):
    monkeypatch.delenv("RETINA_STATE_V3_EMIT_ENABLED", raising=False)
    assert emit.maybe_emit_session_v3("x", 100.0, {"session_id": "s"}, None) is None


def test_read_killfeed_event_sink_dedup(tmp_path):
    # the lingering feed repeats each kill across ticks -> dedup to distinct (killer, victim)
    lines = [_events()[0], _events()[0], _events()[1], _events()[0], _events()[1]]
    (tmp_path / "killfeed_events.jsonl").write_text(
        "\n".join(json.dumps(e) for e in lines), encoding="utf-8")
    got = emit.read_killfeed_event_sink(str(tmp_path))
    assert len(got) == 2
    assert {(e["killer"], e["victim"]) for e in got} == {("Qortrola30", "A"), ("rosa sparks", "B")}


def test_read_killfeed_event_sink_missing():
    assert emit.read_killfeed_event_sink("/no/such/dir") == []


def test_maybe_emit_flag_on_reads_killfeed_sink(tmp_path, monkeypatch):
    (tmp_path / "killfeed_events.jsonl").write_text(
        "\n".join(json.dumps(e) for e in _events()), encoding="utf-8")
    monkeypatch.setenv("RETINA_STATE_V3_EMIT_ENABLED", "1")
    monkeypatch.setenv("RETINA_KILLFEED_CAPTURE_DIR", str(tmp_path))
    out = emit.maybe_emit_session_v3("livesess", 1000.0,
                                     {"device_id": "aa" * 32, "session_id": "s"}, None, out_dir=tmp_path)
    assert out is not None and out.exists()
    rec = json.loads(out.read_text(encoding="utf-8"))
    assert rec["n_events"] == 2 and verify_retina_state_v3_record(rec)
