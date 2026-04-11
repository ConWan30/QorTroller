"""
Phase 193 SDK tests — FleetSignalCoherenceAgent result classes.

Tests (4 total):
  T193S-1: CoherenceSummaryResult has fleet_coherence_enabled/total_open/by_severity/
           by_mode/promoted_to_wif/last_cycle_findings/error slots;
           fleet_coherence_enabled=True (always-on default)
  T193S-2: CoherenceEntryResult has entry_count/entries/failure_mode/severity/error slots;
           safe zero defaults
  T193S-3: VAPIFleetCoherence.get_summary() maps API body correctly;
           by_severity and by_mode returned as JSON strings
  T193S-4: VAPIFleetCoherence.get_entries() maps failure_mode + severity filters correctly
"""

from __future__ import annotations

import json
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_sdk import (  # noqa: E402
    CoherenceSummaryResult,
    CoherenceEntryResult,
    VAPIFleetCoherence,
)


# ---------------------------------------------------------------------------
# T193S-1: CoherenceSummaryResult slots and fleet_coherence_enabled=True
# ---------------------------------------------------------------------------

def test_t193s_1_coherence_summary_result_slots():
    """T193S-1: CoherenceSummaryResult has all expected slots; fleet_coherence_enabled=True."""
    r = CoherenceSummaryResult()
    expected = [
        "fleet_coherence_enabled",
        "total_open",
        "by_severity",
        "by_mode",
        "promoted_to_wif",
        "last_cycle_findings",
        "error",
    ]
    for slot in expected:
        assert hasattr(r, slot), f"CoherenceSummaryResult missing {slot}"

    # fleet_coherence_enabled=True: coherence monitoring always on (unlike most agents)
    assert r.fleet_coherence_enabled is True
    assert r.total_open == 0
    assert r.promoted_to_wif == 0
    assert r.last_cycle_findings == 0
    assert r.error == ""
    # JSON defaults
    assert r.by_severity == "{}"
    assert r.by_mode == "{}"


# ---------------------------------------------------------------------------
# T193S-2: CoherenceEntryResult slots and safe zero defaults
# ---------------------------------------------------------------------------

def test_t193s_2_coherence_entry_result_slots():
    """T193S-2: CoherenceEntryResult has expected slots; safe zero defaults."""
    r = CoherenceEntryResult()
    expected = ["entry_count", "entries", "failure_mode", "severity", "error"]
    for slot in expected:
        assert hasattr(r, slot), f"CoherenceEntryResult missing {slot}"

    assert r.entry_count == 0
    assert r.entries == "[]"
    assert r.failure_mode == "all"
    assert r.severity == "all"
    assert r.error == ""


# ---------------------------------------------------------------------------
# T193S-3: VAPIFleetCoherence.get_summary() maps API body correctly
# ---------------------------------------------------------------------------

def test_t193s_3_get_summary_maps_body():
    """T193S-3: VAPIFleetCoherence.get_summary() maps by_severity/by_mode as JSON strings."""
    client = VAPIFleetCoherence("http://localhost:9999", api_key="test")

    api_body = {
        "fleet_coherence_enabled": True,
        "total_open":          3,
        "by_severity":         {"CRITICAL": 1, "HIGH": 2},
        "by_mode":             {"CONTRADICTION": 2, "ORPHAN": 1},
        "promoted_to_wif":     1,
        "last_cycle_findings": 3,
        "last_checked_at":     "2026-04-11T12:00:00",
        "timestamp":           1744382400.0,
    }

    class _FakeResp:
        def read(self):
            return json.dumps(api_body).encode()
        def __enter__(self):
            return self
        def __exit__(self, *a):
            pass

    with patch("urllib.request.urlopen", return_value=_FakeResp()):
        result = client.get_summary()

    assert isinstance(result, CoherenceSummaryResult)
    assert result.fleet_coherence_enabled is True
    assert result.total_open == 3
    assert result.promoted_to_wif == 1
    assert result.last_cycle_findings == 3
    assert result.error == ""
    # by_severity and by_mode stored as JSON strings
    sev = json.loads(result.by_severity)
    assert sev.get("CRITICAL") == 1
    assert sev.get("HIGH") == 2
    mode = json.loads(result.by_mode)
    assert mode.get("CONTRADICTION") == 2
    assert mode.get("ORPHAN") == 1


# ---------------------------------------------------------------------------
# T193S-4: VAPIFleetCoherence.get_entries() maps failure_mode + severity
# ---------------------------------------------------------------------------

def test_t193s_4_get_entries_maps_filters():
    """T193S-4: VAPIFleetCoherence.get_entries() maps filters and returns CoherenceEntryResult."""
    client = VAPIFleetCoherence("http://localhost:9999", api_key="test")

    api_body = {
        "entry_count": 1,
        "entries": [
            {
                "coherence_id":    "coh_abcdef1234567890",
                "failure_mode":    "CONTRADICTION",
                "rule_name":       "RENEWAL_WITHOUT_ATTESTATION",
                "agents_involved": json.dumps(["AttestationBoundRenewalAgent",
                                               "ReEnrollmentAttestationAgent"]),
                "severity":        "CRITICAL",
                "explanation":     "Renewal without attestation token.",
                "resolution":      "Ensure attestation fires before renewal.",
                "promoted_to_wif": False,
                "wif_entry_id":    None,
            }
        ],
        "failure_mode": "CONTRADICTION",
        "severity":     "CRITICAL",
        "timestamp":    1744382400.0,
    }

    class _FakeResp:
        def read(self):
            return json.dumps(api_body).encode()
        def __enter__(self):
            return self
        def __exit__(self, *a):
            pass

    with patch("urllib.request.urlopen", return_value=_FakeResp()):
        result = client.get_entries(failure_mode="CONTRADICTION", severity="CRITICAL")

    assert isinstance(result, CoherenceEntryResult)
    assert result.entry_count == 1
    assert result.failure_mode == "CONTRADICTION"
    assert result.severity == "CRITICAL"
    assert result.error == ""
    # entries stored as JSON string
    entries = json.loads(result.entries)
    assert len(entries) == 1
    assert entries[0]["rule_name"] == "RENEWAL_WITHOUT_ATTESTATION"
    assert entries[0]["severity"] == "CRITICAL"
