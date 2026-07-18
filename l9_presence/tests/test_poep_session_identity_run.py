"""gp-identity runner tests - make grok r02/r03 bars MECHANICAL.

Bars: (1) dry/injected run is ALWAYS IDENTITY_ONLY, never SYNCHRONIZED (the fabricated-presence rail,
inherited from the sealed effective_live=all(GO.live_hardware)); (2) the live simulator (real_hardware
=True) DOES reach SYNCHRONIZED - documents the only path is a real fire; (3) source purity - the runner
never assigns the candidate/effective_live/live_hardware bits; (4) extended overclaim denylist on
artifact + module + CLI source; (5) seal v0.2 is a non-gating custody sidecar; (6) no HID import on the
dry path; (7) device chain resolves consistently; (8) flags/lane non-claims hold.
"""
import json
import re
import sys
from pathlib import Path

from l9_presence.poep_gameplay_live import FireResult, ImuWindow
from l9_presence.poep_gameplay_session import ChallengeKind
from l9_presence.poep_session_identity_run import (
    RUN_CLAIM_CEILING, RUN_SCHEMA, run_session_identity_attach,
)
from l9_presence.controller_presence import IDENTITY_ONLY, SYNCHRONIZED_CONTROLLER
from l9_presence.poep_did_sync import CLAIM_CEILING

_LIB = Path(__file__).resolve().parents[1] / "poep_session_identity_run.py"
_CLI = Path(__file__).resolve().parents[2] / "scripts" / "poep_session_identity_attach.py"

# ── live ioID ceremony constants (91449f41) ───────────────────────────────────
_DEV = "581a836c98b3a1b6c0f598bfca88e6a3cc3bd7c34591b506692cb40ddf66a9f8"
_IDENT = {
    "owner_did": "did:io:0x0cf36db57fc4680bcdfc65d1aff96993c57a4692",
    "ioid_token_id": 498,
    "tba_address": "0xFCee237789FA91a141781aFB574ADAbcA2660e7b",
    "registration_tx": "0xab4d041b8ffeab257178e04dddd69e1033912766842803e0386c3640468e9b1f",
    "vmdr_pubkey_hash": "0x235a2c04de3319661dd637ad296e37b59c23b0fe1f78509965f77bc5d9247802",
    "controller_nft": "0x93b77eB6D8F9e12A801aC06b81bb6E37b7dcdE55",
    "controller_nft_token_id": 1,
}

# grok r02: existing poep-did-sync denylist + the new orchestration overclaim tokens.
_BANNED = [
    "device_did", "edge-did", "edge's did", "sovereign-device",
    "sovereign identity of the device", "stronger liveness",
    "controller_identity", "identity_capture",
]


def _in_band_imu(t_fire_ns: int) -> ImuWindow:
    return ImuWindow(t_response_ns=int(t_fire_ns) + 250_000_000, latency_ms=250.0,
                     peak_lsb=3000.0, precursor_gap_ms=5.0)


def _dry_fire(amplitude: int, nonce: str) -> FireResult:
    return FireResult(fired=True, real_hardware=False, t_fire_ns=1_000 + amplitude, amplitude=amplitude)


def _sim_live_fire(amplitude: int, nonce: str) -> FireResult:
    # INTENTIONAL live-path simulator: the ONLY thing that mints candidate is real_hardware=True.
    return FireResult(fired=True, real_hardware=True, t_fire_ns=1_000 + amplitude, amplitude=amplitude)


def _active() -> dict:
    return {"gameplay_context": "ACTIVE_GAMEPLAY"}


def _pcc() -> dict:
    return {"capture_state": "NOMINAL", "host_state": "EXCLUSIVE_USB"}


def _run(fire_fn, *, include_custody_seal=True, device_id=_DEV, n_go=2):
    plan = [(ChallengeKind.GO, f"nonce_{i}") for i in range(n_go)]
    return run_session_identity_attach(
        device_id=device_id, player_label="P1", t_start_ns=1_000_000, process_nonce="pn_fixed",
        challenge_plan=plan, fire_fn=fire_fn, imu_capture_fn=_in_band_imu,
        activity_fetcher=_active, pcc_sampler=_pcc, ioid_identity=_IDENT,
        include_custody_seal=include_custody_seal,
    )


# ── bar 1: dry/injected is ALWAYS IDENTITY_ONLY (the fabricated-presence rail) ─────────────────
def test_dry_run_is_identity_only():
    out = _run(_dry_fire)
    assert out["controller_presence"]["verdict"] == IDENTITY_ONLY
    ps = out["presence_summary"]
    # plumbing proven, presence honestly absent (real_hardware=False -> candidate can't be True)
    assert ps["dry_plumbing_ok"] is True
    assert ps["presence_session_candidate_ok"] is False
    assert ps["live_hardware"] is False
    assert out["controller_presence"]["verdict"] != SYNCHRONIZED_CONTROLLER


# ── bar 2: the live simulator DOES reach SYNCHRONIZED (only real_hardware=True does) ───────────
def test_live_simulator_reaches_synchronized():
    out = _run(_sim_live_fire)
    assert out["controller_presence"]["verdict"] == SYNCHRONIZED_CONTROLLER
    ps = out["presence_summary"]
    assert ps["presence_session_candidate_ok"] is True
    assert ps["live_hardware"] is True
    assert out["controller_presence"]["identity_bound"] is True
    assert out["controller_presence"]["presence_candidate"] is True


# ── bar 3: source PURITY - the runner never assigns the candidate/live bits (grok FIX #2) ──────
def test_runner_never_assigns_candidate_bits():
    src = _LIB.read_text(encoding="utf-8")
    # an ASSIGNMENT to any of these three in the runner would be the one real fabrication path
    hit = re.search(r"(presence_session_candidate_ok|effective_live|live_hardware)[\"'\]\s]*=(?!=)", src)
    assert hit is None, f"runner assigns a sealed presence bit: {hit and hit.group(0)!r}"


# ── bar 4: extended overclaim denylist on artifact + module + CLI source ───────────────────────
def test_denylist_on_artifact_and_sources():
    blob = json.dumps(_run(_dry_fire), ensure_ascii=False).lower()
    for tok in _BANNED:
        assert tok not in blob, f"banned token {tok!r} in emitted artifact"
    for path in (_LIB, _CLI):
        src = path.read_text(encoding="utf-8").lower()
        for tok in _BANNED:
            assert tok not in src, f"banned token {tok!r} in {path.name}"


# ── bar 5: seal v0.2 is a NON-GATING custody sidecar under identity ────────────────────────────
def test_custody_seal_is_sidecar_not_gating():
    with_seal = _run(_dry_fire, include_custody_seal=True)
    without = _run(_dry_fire, include_custody_seal=False)
    # verdict identical with/without the seal (it never gates candidate)
    assert with_seal["controller_presence"]["verdict"] == without["controller_presence"]["verdict"]
    cs = with_seal["identity"]["custody_seal_v02"]
    assert cs["domain"] == "QORTROLLER-POEP-GAMEPLAY-LIVESEAL-v0.2-CANDIDATE"
    assert len(cs["seal"]) == 64 and int(cs["seal"], 16) >= 0   # sha256 hex
    assert "custody_seal_v02" not in without["identity"]
    # custody seal lives UNDER identity, never at top level
    assert "custody_seal_v02" not in with_seal


# ── bar 6: no HID import on the dry path ──────────────────────────────────────────────────────
def test_no_hid_import_on_dry_path():
    sys.modules.pop("bridge.controller.l6_trigger_driver", None)
    _run(_dry_fire)
    assert "bridge.controller.l6_trigger_driver" not in sys.modules


# ── bar 7: device chain resolves consistently (positive side of the anti-assertion guard) ──────
def test_device_flows_consistently():
    out = _run(_dry_fire)
    link = out["identity"]["device_to_owner_link"]
    assert link["device_id"] == _DEV
    assert out["presence_summary"]["device_id"] == _DEV
    assert out["controller_presence"]["ioid"]["registered_device_id"] == _DEV
    assert out["identity"]["did_subject"] == "gamer_wallet"
    assert out["identity"]["did_names_silicon"] is False


# ── bar 8: flags / lane non-claims + orchestration ceiling shipped, presence claim NOT overwritten
def test_flags_lane_and_ceilings():
    out = _run(_dry_fire)
    assert out["advances_poep_enabled"] is False
    assert out["advances_presence_session_candidate"] is False
    assert out["advisory"] is True
    assert out["identity_lane"] == "identity-provenance"
    assert out["presence_summary"]["poep_enabled"] is False
    # orchestration ceiling shipped as NEW keys; attach + presence claims untouched
    assert out["run_schema"] == RUN_SCHEMA
    assert out["run_claim_ceiling"] == RUN_CLAIM_CEILING
    assert out["claim_ceiling"] == CLAIM_CEILING           # attach ceiling intact
    assert "FLIP-A" in out["presence_summary"]["claim"]    # sealed presence claim not overwritten
