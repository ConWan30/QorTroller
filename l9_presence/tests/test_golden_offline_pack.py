"""Golden offline authored pack (P0 #2) discipline tests.

Pins the HONEST-SCOPE rail mechanically: the golden set is bounded-lag ONLY -- M18 (>4 s lag,
honest 0) must NEVER be promoted into the golden set, or "run this -> authored>0" becomes
aspirational rather than true. Also pins the RP pad (4000 ms) and the fail-open MISSING path (a
missing local archive is never a silent pass). The build/verify logic itself is covered by
test_kas_deferred; this file guards the pack's framing so a future edit can't quietly widen the
claim.
"""
from __future__ import annotations

import importlib.util
import os

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SPEC = importlib.util.spec_from_file_location(
    "golden_offline_authored", os.path.join(_REPO, "scripts", "golden_offline_authored.py"))
gold = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(gold)


def test_registry_well_formed():
    assert gold.GOLDEN, "golden set must be non-empty"
    for g in gold.GOLDEN:
        assert {"label", "archive", "scan", "kas"} <= set(g)
        assert g["archive"].startswith("retina_kf_archive/")


def test_e3_every_golden_states_measured_lag():
    """Checklist bar E3: any golden MUST document its measured fire->kill lag + why it fits the
    pad budget. Mechanically: a non-empty lag_note on every entry (content quality is review)."""
    for g in gold.GOLDEN:
        assert isinstance(g.get("lag_note"), str) and len(g["lag_note"].strip()) > 20, \
            f"golden {g['label']!r} missing a substantive lag_note (bar E3)"


def test_c_exit_semantics_missing_never_exit0():
    """Checklist bars C + F: FAIL of a present golden dominates (1, never hidden behind missing);
    ANY missing golden -> 2 (F rejects exit 0 with missing>0); only all-present all-pass -> 0."""
    assert gold.pack_exit(2, 0, 0) == 0          # all present, all pass
    assert gold.pack_exit(1, 1, 0) == 1          # present regression -> FAIL
    assert gold.pack_exit(1, 1, 1) == 1          # regression dominates missing
    assert gold.pack_exit(1, 0, 1) == 2          # F reject rule: exit 0 with missing>0 impossible
    assert gold.pack_exit(0, 0, 2) == 2          # nothing on disk
    assert gold.pack_exit(0, 0, 0) == 2          # degenerate empty -> never a silent pass


def test_no_m18_honest_scope_rail():
    """M18 (>4 s lag) is an honest 0 -- it must never be promoted into the golden set (the pad
    recovered only 3/8 of its kills; a looser pad would paper over the limit, not fix it)."""
    joined = " ".join(v for g in gold.GOLDEN for v in g.values()).lower()
    assert "m18" not in joined and "match18" not in joined


def test_pad_is_rp_4000():
    assert gold.PAD_MS == 4000.0


def test_missing_archive_is_not_a_pass():
    status, _ = gold.run_one({"label": "bogus", "archive": "retina_kf_archive/does_not_exist",
                              "scan": "audits/nope.json", "kas": "audits/nope.json"})
    assert status == "MISSING"          # absent local archive -> MISSING, never a silent PASS
