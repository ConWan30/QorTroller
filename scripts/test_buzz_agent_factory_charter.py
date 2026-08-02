#!/usr/bin/env python3
"""Charter v1 hire-bar / clause smoke tests for buzz_agent_factory (no relay)."""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

# Load factory without executing main
_spec = importlib.util.spec_from_file_location(
    "buzz_agent_factory", ROOT / "scripts" / "buzz_agent_factory.py"
)
assert _spec and _spec.loader
f = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(f)


def test_valid_clauses():
    assert f.VALID_CLAUSES == {
        "P-SOV",
        "P-ATT",
        "P-VSS",
        "P-WMP",
        "P-OPS",
        "P-FRM",
        "P-STU",
    }
    assert f._validate_clause("P-VSS") is True
    assert f._validate_clause("P-NOPE") is False


def test_parse_resume_semi_form():
    r = f._parse_resume("competence: a,b; forbidden: keys,shell; channels: #streams")
    assert r["competence"] == ["a", "b"]
    assert "keys" in r["forbidden"]
    assert "#streams" in r["channels"]


def test_hire_requires_competence(monkeypatch=None):
    # Without parent key / competence, hire_agent fails closed
    old = os.environ.pop("BUZZ_PRIVATE_KEY", None)
    try:
        assert f.hire_agent("x", "P-VSS", "forbidden: keys") is None  # no competence
        assert f.hire_agent("x", "P-NOPE", "competence: a") is None  # bad clause
        assert f.hire_agent("x", "P-VSS", "competence: flag-down") is None  # no key
    finally:
        if old is not None:
            os.environ["BUZZ_PRIVATE_KEY"] = old


def test_creation_approved_env():
    keys = ("BUZZ_CREATION_APPROVED", "BUZZ_AGENT_MINTERS", "BUZZ_MINTERS")
    saved = {k: os.environ.pop(k, None) for k in keys}
    try:
        assert f._creation_approved() is False
        os.environ["BUZZ_AGENT_MINTERS"] = "1"
        assert f._creation_approved() is True
        del os.environ["BUZZ_AGENT_MINTERS"]
        os.environ["BUZZ_CREATION_APPROVED"] = "1"
        assert f._creation_approved() is True
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_registry_json_loads():
    import json

    reg = json.loads((ROOT / "agents" / "registry.json").read_text(encoding="utf-8"))
    assert reg["version"] == "1.0.0"
    ids = {a["agent_id"] for a in reg["roster"]}
    for required in ("ea", "qort", "retina", "seatwarden", "attestor", "frameworks"):
        assert required in ids, required
    # Candidates must not pretend to be fully enabled without keys/seal where empty
    seat = next(a for a in reg["roster"] if a["agent_id"] == "seatwarden")
    assert seat["status"] == "candidate"
    assert "VSS OPEN" in seat["forbidden"]


if __name__ == "__main__":
    test_valid_clauses()
    test_parse_resume_semi_form()
    test_hire_requires_competence()
    test_creation_approved_env()
    test_registry_json_loads()
    print("PASS: charter factory smoke (5 checks)")
