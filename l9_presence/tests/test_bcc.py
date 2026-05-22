"""Tests for the Behavioral Capture Chain (no hardware)."""
import os

from l9_presence.bcc import (
    BCCConfig, BCCHarvester, BCCStore, canonical_digest, compute_bcc_hash, genesis_bcc,
)


def test_genesis_and_hash_deterministic_and_sensitive():
    g = genesis_bcc()
    assert g == genesis_bcc() and len(g) == 64
    a = compute_bcc_hash(g, "ab" * 32, 1, 1, 1000)
    assert a == compute_bcc_hash(g, "ab" * 32, 1, 1, 1000)
    assert compute_bcc_hash(g, "ab" * 32, 1, 1, 1001) != a       # ts changes hash
    assert compute_bcc_hash(g, "cd" * 32, 1, 1, 1000) != a       # payload changes hash


def test_canonical_digest_order_independent():
    assert canonical_digest({"a": 1, "b": 2}) == canonical_digest({"b": 2, "a": 1})
    assert canonical_digest({"a": 1}) != canonical_digest({"a": 2})


def test_store_chain_appends_and_verifies(tmp_path):
    s = BCCStore(str(tmp_path / "lane"))
    r0 = s.append({"type": "l9", "features": [0.1]}, 1, 1)
    r1 = s.append({"type": "l9", "features": [0.2]}, 1, 1)
    assert r0["prev_hash"] == genesis_bcc()
    assert r1["prev_hash"] == r0["bcc_hash"] and r1["seq"] == 1
    assert s.verify() is True


def test_store_tamper_detected(tmp_path):
    s = BCCStore(str(tmp_path / "lane"))
    s.append({"type": "l9", "features": [0.1]}, 1, 1)
    s.append({"type": "l9", "features": [0.2]}, 1, 1)
    # corrupt the first record's payload in place
    with open(s.path, encoding="utf-8") as fh:
        lines = fh.readlines()
    lines[0] = lines[0].replace("0.1", "9.9")
    with open(s.path, "w", encoding="utf-8") as fh:
        fh.writelines(lines)
    assert s.verify() is False


def test_monotonic_ts_guard(tmp_path):
    s = BCCStore(str(tmp_path / "lane"))
    a = s.append({"x": 1}, 1, 1, ts_ns=5000)
    b = s.append({"x": 2}, 1, 1, ts_ns=4000)        # backwards ts
    assert b["ts_ns"] == a["ts_ns"] + 1 and s.verify() is True


def test_harvester_dormant_by_default(tmp_path):
    h = BCCHarvester(BCCConfig(out_dir=str(tmp_path / "lane")))      # enabled=False
    assert h.record_l9([0.3, 1.2, 0.6]) is None
    assert h.record_poep({"delta": 0.6}) is None
    assert not os.path.exists(os.path.join(str(tmp_path / "lane"), "bcc_chain.jsonl"))  # wrote nothing


def test_harvester_records_when_enabled_and_gated(tmp_path):
    h = BCCHarvester(BCCConfig(enabled=True, out_dir=str(tmp_path / "lane")))
    assert h.record_l9([0.3, 1.2, 0.6]) is not None          # sub-lane A on
    assert h.record_l9([0.3], nominal=False) is None         # PCC/GAD fail-closed
    assert h.record_poep({"delta": 0.6}) is None             # sub-lane B needs its own flag
    h.cfg.sublane_b_enabled = True
    assert h.record_poep({"delta": 0.6}) is not None
    st = h.status()
    assert st["sub_lane_a"] == 1 and st["sub_lane_b"] == 1 and st["chain_intact"] is True


def test_isolation_writes_only_its_own_lane(tmp_path):
    lane = str(tmp_path / "lane")
    h = BCCHarvester(BCCConfig(enabled=True, out_dir=lane))
    h.record_l9([0.3, 1.2, 0.6])
    assert os.listdir(lane) == ["bcc_chain.jsonl"]            # nothing but its own chain file
