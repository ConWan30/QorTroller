"""EVENT-BIND tests — the cryptographic per-event authorship binder.

Pins the novelty: a timestamp-aligned SPLICE (outcome anchor A + onset anchor B) PASSES a temporal
∩ but EVENT-BIND degrades it to TEMPORAL_PROTOTYPE (never RECORD_HASH_PRODUCTION); a genuine
co-capture (shared record_hash) binds crypto even when the onset is FAR in time (time-independent).
Plus: no-stamping fallback, UNBOUND, crypto-requires-both-anchors, all-or-nothing strong claim,
report math, honest banner, fail-open.
"""
from __future__ import annotations

from l9_presence.event_bind import (
    BIND_SCHEMA,
    EventBindMode,
    HidOnset,
    ScreenOutcome,
    bind_events,
)

_A = "a" * 64          # capture-A PoAC record_hash
_B = "b" * 64          # capture-B PoAC record_hash (a DIFFERENT session/record)
_C = "c" * 64          # a second distinct kill's own anchor (record_hash is unique per PoAC record)


def _co(t_ms, rh=None, **kw):
    return ScreenOutcome(t_ms=t_ms, record_hash=rh, **kw)


def _on(t_ms, rh=None, **kw):
    return HidOnset(t_ms=t_ms, record_hash=rh, **kw)


# ------------------------------------------------------------------- genuine co-capture (production)
def test_shared_anchor_binds_cryptographic():
    """Both lobes carry the SAME record_hash -> RECORD_HASH_PRODUCTION, splice-proof."""
    r = bind_events([_co(1000.0, _A)], [_on(1080.0, _A)])
    p = r.pairs[0]
    assert p.mode == EventBindMode.RECORD_HASH_PRODUCTION
    assert p.cryptographically_bound is True
    assert p.anchor_record_hash == _A
    assert r.binding_is_cryptographic is True
    assert r.crypto_coverage() == 1.0


def test_crypto_bind_is_time_independent():
    """A shared-anchor onset FAR outside the temporal window still binds crypto — the whole point:
    the cryptographic join needs no temporal proximity."""
    r = bind_events([_co(1000.0, _A)], [_on(999_000.0, _A)], window_ms=2000.0)  # ~998 s apart
    p = r.pairs[0]
    assert p.mode == EventBindMode.RECORD_HASH_PRODUCTION and p.cryptographically_bound


# ------------------------------------------------------------------- THE splice demonstration
def test_splice_passes_temporal_but_fails_crypto():
    """THE NOVELTY: a kill-outcome from capture A + a trigger-onset from capture B, timestamps
    ALIGNED (80 ms apart, well inside the window). A temporal ∩ would call this AUTHORED. EVENT-BIND
    refuses the crypto claim (anchors differ) and degrades to TEMPORAL_PROTOTYPE — honest, never
    RECORD_HASH_PRODUCTION. This is the class the temporal join provably cannot resist."""
    outcomes = [_co(1000.0, _A), _co(2000.0, _A), _co(3000.0, _A)]
    onsets = [_on(1080.0, _B), _on(2080.0, _B), _on(3080.0, _B)]   # aligned in time, WRONG anchor
    r = bind_events(outcomes, onsets)
    # temporally bound (the splice's timestamps line up) ...
    assert r.n_bound == 3
    # ... but NONE crypto-bound, and the strong claim is refused
    assert r.n_crypto == 0
    assert r.binding_is_cryptographic is False
    assert all(p.mode == EventBindMode.TEMPORAL_PROTOTYPE for p in r.pairs)
    assert all(not p.cryptographically_bound for p in r.pairs)


def test_same_events_shared_anchor_would_be_crypto():
    """Control for the splice test: the identical timing, but a SHARED anchor -> crypto. Proves the
    discriminator is the anchor, not the timing."""
    outcomes = [_co(1000.0, _A), _co(2000.0, _A), _co(3000.0, _A)]
    onsets = [_on(1080.0, _A), _on(2080.0, _A), _on(3080.0, _A)]    # same timing, RIGHT anchor
    r = bind_events(outcomes, onsets)
    assert r.n_crypto == 3 and r.binding_is_cryptographic is True


# ------------------------------------------------------------------- fallback / honesty
def test_no_stamping_falls_back_to_temporal():
    """Both anchors None (stamping not live yet) -> TEMPORAL_PROTOTYPE, honestly labeled."""
    r = bind_events([_co(1000.0)], [_on(1050.0)])
    p = r.pairs[0]
    assert p.mode == EventBindMode.TEMPORAL_PROTOTYPE and not p.cryptographically_bound
    assert p.anchor_record_hash is None
    assert r.binding_is_cryptographic is False


def test_crypto_requires_both_anchors_present():
    """Outcome carries an anchor but no onset shares it -> never crypto (degrades to temporal)."""
    r = bind_events([_co(1000.0, _A)], [_on(1050.0, None)])
    assert r.n_crypto == 0 and r.pairs[0].mode == EventBindMode.TEMPORAL_PROTOTYPE


def test_unbound_when_no_onset_in_window():
    r = bind_events([_co(1000.0, _A)], [_on(9000.0, _B)], window_ms=2000.0)
    p = r.pairs[0]
    assert p.mode == EventBindMode.UNBOUND and p.onset is None and not p.bound
    assert p.anchor_record_hash is None


def test_mixed_session_is_not_fully_cryptographic():
    """All-or-nothing strong claim: one temporal-only kill sinks binding_is_cryptographic.
    Realistic per-kill anchors: kill 1 co-captured (_A/_A -> crypto); kill 2 spliced
    (outcome _C, onset _B -> anchors differ -> temporal)."""
    r = bind_events([_co(1000.0, _A), _co(2000.0, _C)],
                    [_on(1050.0, _A), _on(2050.0, _B)])       # kill 2 is a splice
    assert r.n_crypto == 1 and r.n_temporal == 1
    assert r.binding_is_cryptographic is False


# ------------------------------------------------------------------- report / plumbing
def test_report_math_and_offsets():
    r = bind_events([_co(1000.0, _A), _co(2000.0, _A)], [_on(1080.0, _A), _on(2120.0, _A)])
    d = r.to_dict()
    assert d["schema"] == BIND_SCHEMA
    assert d["n_outcomes"] == 2 and d["n_crypto_bound"] == 2
    assert d["offset_stats_ms"]["min_ms"] == 80.0 and d["offset_stats_ms"]["max_ms"] == 120.0
    assert d["coverage"] == 1.0 and d["crypto_coverage"] == 1.0


def test_markdown_banner_cryptographic_vs_temporal():
    crypto = bind_events([_co(1000.0, _A)], [_on(1050.0, _A)]).to_markdown()
    assert "CRYPTOGRAPHIC BINDING (production)" in crypto
    temporal = bind_events([_co(1000.0, _A)], [_on(1050.0, _B)]).to_markdown()
    assert "TEMPORAL CORRELATION (prototype) — NOT a cryptographic proof" in temporal
    assert "a timestamp-aligned splice would pass" in temporal


def test_fail_open_empty_inputs():
    r = bind_events([], [])
    assert r.n_outcomes == 0 and r.binding_is_cryptographic is False
    assert r.to_dict()["coverage"] == 0.0


def test_crypto_prefers_shared_anchor_over_nearer_temporal():
    """A shared-anchor onset (far) beats a nearer wrong-anchor onset — crypto wins over proximity."""
    outcome = _co(1000.0, _A)
    onsets = [_on(1010.0, _B),        # very near, WRONG anchor
              _on(1900.0, _A)]        # farther, RIGHT anchor
    r = bind_events([outcome], onsets)
    p = r.pairs[0]
    assert p.mode == EventBindMode.RECORD_HASH_PRODUCTION
    assert p.onset.t_ms == 1900.0 and p.anchor_record_hash == _A
