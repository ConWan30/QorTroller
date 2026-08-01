#!/usr/bin/env python3
"""Tests for scripts/sap_seal.py."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import qortroller_acp_gateway as gw
import sap_seal as seal


@pytest.fixture
def tmp_paths(tmp_path: Path):
    queue = tmp_path / "acp_devin_queue.jsonl"
    plans = tmp_path / "acp_plans.jsonl"
    results = tmp_path / "acp_devin_results.jsonl"
    seals = tmp_path / "acp_sap_seals.jsonl"
    return {"queue": queue, "plans": plans, "results": results, "seals": seals}


@pytest.fixture
def paths_with_known_job(tmp_paths: dict):
    job_id = "sap_knownjob123"
    gw._append_jsonl(tmp_paths["queue"], {"ts": 1, "job_id": job_id, "topic": "capture lag", "status": "queued"})
    return tmp_paths, job_id


def _run(tmp_paths: dict, *extra_args, job_id: str = "sap_knownjob123"):
    return seal.main(
        [
            "--path", str(tmp_paths["seals"]),
            "--job-id", job_id,
            *extra_args,
        ]
    )


def test_seal_refuses_unknown_job_id(tmp_paths: dict):
    rc = _run(tmp_paths, "--accept", job_id="sap_unknown")
    assert rc == 1
    assert not tmp_paths["seals"].exists()


def test_seal_accepts_known_job_id(paths_with_known_job):
    tmp_paths, job_id = paths_with_known_job
    # Patch the module-level path constants so _known_job_id sees the temp files.
    old_queue = seal.QUEUE_PATH
    old_plans = seal.PLANS_PATH
    old_results = seal.RESULTS_PATH
    seal.QUEUE_PATH = tmp_paths["queue"]
    seal.PLANS_PATH = tmp_paths["plans"]
    seal.RESULTS_PATH = tmp_paths["results"]
    try:
        rc = _run(tmp_paths, "--accept", "--ref", "https://github.com/ConWan30/QorTroller/pull/125", "--note", "lgtm", job_id=job_id)
        assert rc == 0
        lines = tmp_paths["seals"].read_text(encoding="utf-8").strip().splitlines()
        record = json.loads(lines[0])
        assert record["job_id"] == job_id
        assert record["verdict"] == "accept"
        assert record["ref"].endswith("/pull/125")
        assert record["note"] == "lgtm"
        assert record["operator"] == "local"
    finally:
        seal.QUEUE_PATH = old_queue
        seal.PLANS_PATH = old_plans
        seal.RESULTS_PATH = old_results


def test_seal_force_allows_unknown_job_id(tmp_paths: dict):
    rc = _run(tmp_paths, "--hold", "--force", job_id="sap_unknown")
    assert rc == 0
    lines = tmp_paths["seals"].read_text(encoding="utf-8").strip().splitlines()
    record = json.loads(lines[0])
    assert record["verdict"] == "hold"


def test_seal_rejects_invalid_job_id_prefix(tmp_paths: dict):
    rc = _run(tmp_paths, "--accept", "--force", job_id="notsap_123")
    assert rc == 2
    assert not tmp_paths["seals"].exists()


def test_seal_reject_path(tmp_paths: dict, monkeypatch):
    monkeypatch.setattr(seal, "_known_job_id", lambda _jid: True)
    rc = _run(tmp_paths, "--reject", job_id="sap_anyjob")
    assert rc == 0
    lines = tmp_paths["seals"].read_text(encoding="utf-8").strip().splitlines()
    record = json.loads(lines[0])
    assert record["verdict"] == "reject"
