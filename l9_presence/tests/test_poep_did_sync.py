"""POEP-DID-SYNC (identity/provenance attach) — tests that make grok r03 bars 1-2 MECHANICAL.

Bars: (1) overclaim scan — no field/string implies the DID names the silicon; (2) lane-leak scan —
nothing implies the candidate got stronger; (3) presence model byte-untouched; (4) flags stay False;
(5) non-goals honored. These tests pin 1-4 mechanically (5 is structural: option 3/4 absent by design).
"""
import hashlib
import json
from pathlib import Path

import pytest

from l9_presence.poep_did_sync import (
    ATTACH_SCHEMA, CLAIM_CEILING, IDENTITY_LANE,
    attach_session_identity, compute_live_seal_v2,
)
from l9_presence.poep_gameplay_live import compute_live_seal  # v0 — must stay byte-unchanged
from l9_presence.controller_presence import SYNCHRONIZED_CONTROLLER, IDENTITY_ONLY

# ── live ioID ceremony constants (91449f41) ───────────────────────────────────
DEV = "581a836c98b3a1b6c0f598bfca88e6a3cc3bd7c34591b506692cb40ddf66a9f8"
OWNER_DID = "did:io:0x0cf36db57fc4680bcdfc65d1aff96993c57a4692"
TBA = "0xFCee237789FA91a141781aFB574ADAbcA2660e7b"
REG_TX = "0xab4d041b8ffeab257178e04dddd69e1033912766842803e0386c3640468e9b1f"
VMDR_PKH = "0x235a2c04de3319661dd637ad296e37b59c23b0fe1f78509965f77bc5d9247802"
NFT = "0x93b77eB6D8F9e12A801aC06b81bb6E37b7dcdE55"

_BANNED = [
    "device_did", "edge-did", "edge's did", "sovereign-device",
    "sovereign identity of the device", "stronger liveness",
]


def _summary(*, device_id=DEV, session_id="sid_abc", candidate=True):
    """A summarize_session-v0.1-shaped presence summary (only the fields the attach reads)."""
    return {
        "schema": "qortroller-poep-gameplay-session-v0.1",
        "session_id": session_id,
        "device_id": device_id,
        "mode": "live" if candidate else "dry",
        "presence_session_candidate_ok": candidate,
        "dry_plumbing_ok": True,
        "effective_live": candidate,
    }


def _attach(summary):
    return attach_session_identity(
        presence_summary=summary, owner_did=OWNER_DID, ioid_token_id=498, tba_address=TBA,
        registration_tx=REG_TX, device_id=DEV, vmdr_pubkey_hash=VMDR_PKH, controller_nft=NFT,
        controller_nft_token_id=1)


def _walk_keys(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield str(k)
            yield from _walk_keys(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk_keys(v)


def _walk_strings(o):
    if isinstance(o, dict):
        for v in o.values():
            yield from _walk_strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk_strings(v)
    elif isinstance(o, str):
        yield o


# ── wrap-schema, not flat-merge ───────────────────────────────────────────────
def test_wraps_not_flat_merges():
    out = _attach(_summary())
    assert out["schema"] == ATTACH_SCHEMA
    # presence stays a nested surface with its own v0.1 schema — identity did not grow it
    assert out["presence_summary"]["schema"] == "qortroller-poep-gameplay-session-v0.1"
    assert "identity" in out and "owner_did" in out["identity"]
    # identity material is NOT flat on the presence summary
    assert "owner_did" not in out["presence_summary"]


# ── bar 1: no field NAME implies the DID names the silicon ─────────────────────
def test_no_device_did_key_anywhere_and_explicit_subject():
    out = _attach(_summary())
    keys = [k.lower() for k in _walk_keys(out)]
    assert not any("device_did" in k for k in keys)          # never a device_did key
    assert "owner_did" in keys                                # the DID is named as the OWNER's
    assert out["identity"]["did_subject"] == "gamer_wallet"   # explicit machine subject
    assert out["identity"]["did_names_silicon"] is False
    # the link a stranger walks carries NO key named `did`
    link = out["identity"]["device_to_owner_link"]
    assert not any("did" in k.lower() for k in link)
    assert set(link) == {"device_id", "vmdr_pubkey_hash", "controller_nft",
                         "controller_nft_token_id", "tba_address"}


# ── bars 1+2 mechanical: token denylist on JSON (keys + values) AND source ─────
def test_token_denylist_json_and_module_source():
    out = _attach(_summary())
    blob = json.dumps(out, ensure_ascii=False).lower()
    for tok in _BANNED:
        assert tok not in blob, f"banned token {tok!r} in emitted JSON"
    src = (Path(__file__).resolve().parents[1] / "poep_did_sync.py").read_text(encoding="utf-8").lower()
    for tok in _BANNED:
        assert tok not in src, f"banned token {tok!r} in module source"


# ── the ceiling ships verbatim, byte-equal to the r01 open ────────────────────
def test_claim_ceiling_byte_equal_r01_open():
    out = _attach(_summary())
    assert out["claim_ceiling"] == CLAIM_CEILING
    r01 = (Path(__file__).resolve().parents[2] / "docs" / "a2a" / "poep"
           / "round-did-sync-01-claude-open.md").read_text(encoding="utf-8")
    para = " ".join(ln[2:].rstrip() for ln in r01.splitlines() if ln.startswith("> "))
    assert para == CLAIM_CEILING, "claim_ceiling drifted from the r01 pinned paragraph"


# ── bar 4: nothing advances flags/candidate ───────────────────────────────────
def test_advances_nothing():
    out = _attach(_summary())
    assert out["advances_poep_enabled"] is False
    assert out["advances_presence_session_candidate"] is False
    assert out["advisory"] is True
    assert out["identity_lane"] == IDENTITY_LANE
    assert out["controller_presence"]["advances_poep_enabled"] is False
    assert out["controller_presence"]["advances_presence_session_candidate"] is False


# ── bar 3: presence model byte-untouched (pass-through + no mutation) ──────────
def test_presence_passthrough_and_no_mutation():
    s = _summary(candidate=True)
    before = json.dumps(s, sort_keys=True)
    out = _attach(s)
    # the nested copy equals the input exactly (candidate/plumbing bits never re-scored)
    assert out["presence_summary"] == s
    assert out["presence_summary"]["presence_session_candidate_ok"] is True
    assert out["presence_summary"]["dry_plumbing_ok"] is True
    # the INPUT object is untouched (deep copy)
    assert json.dumps(s, sort_keys=True) == before
    out["presence_summary"]["presence_session_candidate_ok"] = "MUTATED"
    assert s["presence_session_candidate_ok"] is True   # input isolated from the returned copy


# ── guard: identity must describe the same Edge ───────────────────────────────
def test_device_mismatch_refused():
    other = _summary(device_id="ff" * 32)
    with pytest.raises(ValueError, match="SAME Edge"):
        _attach(other)


# ── composes on controller_presence (dual-bit verdict, never OR-merged) ───────
def test_composes_synchronized_vs_identity_only():
    sync = _attach(_summary(candidate=True))["controller_presence"]
    assert sync["verdict"] == SYNCHRONIZED_CONTROLLER
    assert sync["identity_bound"] is True and sync["presence_candidate"] is True
    ident = _attach(_summary(candidate=False))["controller_presence"]
    assert ident["verdict"] == IDENTITY_ONLY
    assert ident["identity_bound"] is True and ident["presence_candidate"] is False


# ── seal v0 byte-unchanged (golden preimage) ──────────────────────────────────
def test_seal_v0_byte_unchanged_golden():
    expect = hashlib.sha256(
        b"QORTROLLER-POEP-GAMEPLAY-LIVESEAL-v0-CANDIDATE|sid|dev|1000|nonce").hexdigest()
    assert compute_live_seal("sid", "dev", 1000, "nonce") == expect


# ── seal v0.2: new domain + CUSTODY-sensitive (grok r02 H2 fix) ───────────────
def test_seal_v02_new_domain_and_custody_sensitive():
    a = compute_live_seal_v2("sid", "dev", 1000, "nonce", NFT, 1, TBA)
    # distinct from v0 (new domain)
    assert a != compute_live_seal("sid", "dev", 1000, "nonce")
    # deterministic
    assert a == compute_live_seal_v2("sid", "dev", 1000, "nonce", NFT, 1, TBA)
    # CUSTODY-sensitive: a DIFFERENT TBA (custody transfer) => a different seal (the H2 property)
    b = compute_live_seal_v2("sid", "dev", 1000, "nonce", NFT, 1, "0x" + "aa" * 20)
    assert a != b
    # (tokenId alone stable is not the epoch signal — the TBA is; both bound so both move it)
    with pytest.raises(ValueError):
        compute_live_seal_v2("sid", "dev", 1000, "nonce", NFT, 1, "")


def test_missing_session_device_refused():
    """grok r03 residual closed: a session with NO device_id can't be bound to an identity."""
    s = _summary()
    s.pop("device_id", None)
    with pytest.raises(ValueError, match="no device_id"):
        _attach(s)
