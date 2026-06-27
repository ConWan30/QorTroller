"""Cycle-42 PoVCA integration tests — lock the honesty rails + persistence the integrator restored.

These cover the gaps the single-integrator pass caught in the parallel build:
  F1  structure_ok is TRI-STATE and NEVER fails open (no L4 -> abstain; anomalous -> False; never True
      without evidence). This is the GCAP-overclaim guard.
  F2  nqpv_cocapture_log persists the posca_* columns (the INSERT had them; the schema did not).
  F3  the commitment is the real, recomputable, deterministic one (not a fabricated string).
  F4  PoVCA is an ADVISORY field that does NOT move presence_score.
"""
import os
import tempfile

from vapi_bridge.posca_action_provenance import (
    _check_structure_ok, detect_author_actions, compute_posca_commitment,
    is_emulated_or_non_real, posca_verdict_from, L4_ANOMALY_THRESHOLD,
)
from vapi_bridge.retina_causal_coherence import TimedEvent
from vapi_bridge.retina_screen_lobe import ScreenEvent, EVT_DOWN_ADVANCED, is_input_caused
from vapi_bridge.novel_presence_fusion import NovelPresenceFusionOrchestrator
from vapi_bridge.store import Store


def _one_input(t=10.45):
    return [TimedEvent(kind="input", type="controller.trigger.onset", t=t)]


# ---- F1: tri-state structure, no fail-open ---------------------------------------------------------
def test_structure_ok_abstains_without_l4():
    assert _check_structure_ok(_one_input(), None) is None      # no L4 -> abstain, NOT True
    assert _check_structure_ok(_one_input(), {}) is None
    assert _check_structure_ok([], {"l4_distance": 3.0}) is None  # no authoring input -> abstain


def test_structure_ok_true_only_with_human_l4():
    assert _check_structure_ok(_one_input(), {"l4_distance": 4.3}) is True


def test_structure_ok_false_when_anomalous():
    assert _check_structure_ok(_one_input(), {"l4_distance": 159.0}) is False
    # exactly at the threshold is NOT < threshold -> anomalous -> False
    assert _check_structure_ok(_one_input(), {"l4_distance": L4_ANOMALY_THRESHOLD}) is False


def test_structure_ok_abstains_on_malformed_distance():
    assert _check_structure_ok(_one_input(), {"l4_distance": None}) is None
    assert _check_structure_ok(_one_input(), {"l4_distance": "nope"}) is None


# ---- verdict helper (single source of truth) -------------------------------------------------------
def test_verdict_emulated_is_unverifiable():
    assert posca_verdict_from(True, 0.9, None) == "UNVERIFIABLE"          # no CCO tier
    assert posca_verdict_from(True, 0.9, "FAIL") == "UNVERIFIABLE"
    assert posca_verdict_from(True, 0.9, "emulated-pad") == "UNVERIFIABLE"


def test_verdict_abstain_is_unverifiable():
    assert posca_verdict_from(None, 0.9, "P-T3") == "UNVERIFIABLE"        # no structure evidence


def test_verdict_authentic_requires_structure_and_coupling():
    assert posca_verdict_from(True, 0.9, "P-T3") == "AUTHENTIC"
    assert posca_verdict_from(True, 0.0, "P-T3") == "ORPHAN_OR_WEAK"      # weak coupling
    assert posca_verdict_from(False, 0.9, "P-T3") == "ORPHAN_OR_WEAK"     # anomalous structure


def test_is_emulated_or_non_real():
    assert is_emulated_or_non_real(None) is True
    assert is_emulated_or_non_real("FAIL") is True
    assert is_emulated_or_non_real("VIRTUAL-X") is True
    assert is_emulated_or_non_real("P-T3") is False


# ---- F3: recomputable, deterministic commitment ----------------------------------------------------
def test_commitment_is_deterministic_and_binds_inputs():
    action = {"type": "down_advanced", "t": 10.5, "structure_ok": True, "n_inputs_in_window": 2}
    a = compute_posca_commitment("dev1", action, "rh1", 0.4)
    assert a == compute_posca_commitment("dev1", action, "rh1", 0.4) and len(a) == 64
    assert compute_posca_commitment("dev2", action, "rh1", 0.4) != a                 # device binds
    assert compute_posca_commitment("dev1", action, "rh2", 0.4) != a                 # poac hash binds
    assert compute_posca_commitment("dev1", dict(action, structure_ok=False), "rh1", 0.4) != a  # structure binds


# ---- detector + binder reuse -----------------------------------------------------------------------
def test_detect_binds_action_and_abstains_without_l4():
    assert is_input_caused(EVT_DOWN_ADVANCED)
    se = [ScreenEvent(EVT_DOWN_ADVANCED, 10.5, True, {})]
    ie = _one_input(10.45)
    acts = detect_author_actions(se, ie, device_id="dev", poac_record_hash="rh")
    assert len(acts) == 1
    assert acts[0]["structure_ok"] is None            # no L4 -> abstain (NOT manufactured True)
    assert len(acts[0]["commitment"]) == 64           # real commitment minted at detection
    assert detect_author_actions([], ie) == [] and detect_author_actions(se, []) == []


def test_detect_structure_true_with_l4_present():
    se = [ScreenEvent(EVT_DOWN_ADVANCED, 10.5, True, {})]
    acts = detect_author_actions(se, _one_input(10.45), l4_features={"l4_distance": 3.0})
    assert acts and acts[0]["structure_ok"] is True
    assert acts[0]["commitment"] == ""                # no device/hash supplied -> no commitment


# ---- F4: PoVCA is advisory, never moves the certified score ----------------------------------------
def test_fuse_posca_is_advisory_not_scored():
    class _CCO:  # minimal cco_report with a non-emulated tier
        tier = "P-T3"
    orch = NovelPresenceFusionOrchestrator()
    common = dict(cco_report=_CCO(), poep_present=True, l4_l5_l6_ok=True, device_id="d", record_hash="r")
    base = orch.fuse(**common)
    withp = orch.fuse(**common, posca_structure_ok=True, posca_coupling_score=0.9,
                      posca_action_count=3, posca_commitment="abc")
    assert base.presence_score == withp.presence_score        # F4: posca does NOT move the score
    assert withp.posca_verdict == "AUTHENTIC"                 # surfaced as advisory field
    assert base.posca_verdict == "UNVERIFIABLE"               # abstain by default
    assert withp.posca_commitment == "abc"                    # pass-through, not fabricated
    assert "not scored" in withp.notes


def test_fuse_posca_abstains_on_emulated_even_if_structured():
    orch = NovelPresenceFusionOrchestrator()
    # no cco_report -> cco_tier None -> emulated gate -> UNVERIFIABLE even with structure_ok True
    p = orch.fuse(poep_present=True, l4_l5_l6_ok=True, device_id="d", record_hash="r",
                  posca_structure_ok=True, posca_coupling_score=0.9)
    assert p.posca_verdict == "UNVERIFIABLE"


# ---- F2: the posca columns actually persist --------------------------------------------------------
def test_store_persists_posca_columns():
    db = os.path.join(tempfile.mkdtemp(), "posca.db")
    s = Store(db)
    s.insert_nqpv_cocapture(
        device_id="dev", record_hash_hex="rh", nqpv_cco_tier="P-T3", nqpv_l4l5l6_ok=1,
        posca_verdict="AUTHENTIC", posca_commitment="c0ffee", posca_structure_ok=True,
        posca_coupling_score=0.42, posca_action_count=2,
    )
    rows = s.get_nqpv_cocapture_rows(limit=5)
    assert len(rows) == 1
    r = rows[0]
    assert r["posca_verdict"] == "AUTHENTIC"
    assert r["posca_commitment"] == "c0ffee"
    assert r["posca_structure_ok"] in (1, True)
    assert abs(float(r["posca_coupling_score"]) - 0.42) < 1e-9
    assert r["posca_action_count"] == 2
