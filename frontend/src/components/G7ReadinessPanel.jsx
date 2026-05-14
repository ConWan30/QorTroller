// Phase O4 post-backlog-closure — G7 Curator Review Readiness panel.
//
// Binds GET /operator/g7-curator-readiness (bridge endpoint shipped at
// commit 0f2d10fa; wraps scripts/g7_curator_review_readiness_audit.py).
// Closes the agent-actionable surface of VBDIP-0002 Appendix B §B.8 G7
// (7-day window, ≥9/10 acceptance gate).
//
// noMock:true on the underlying hook — G7 verdict is the gating signal
// for Curator O2 → O3 graduation; fabricated rows would mislead operator.

import { FONTS, DEVELOPER } from '../shared/design/tokens'
import { useG7CuratorReadiness } from '../api/bridgeApi'

const VERDICT_TINT = {
  PASS:                          DEVELOPER.green,
  BLOCKED:                       DEVELOPER.amber,
  FAIL:                          DEVELOPER.red,
  FAIL_ZERO_TOLERANCE_VIOLATION: DEVELOPER.red,
  NO_CURATOR_DRAFTS:             DEVELOPER.amber,
  ERROR:                         DEVELOPER.red,
  UNKNOWN:                       DEVELOPER.bd,
}

export function G7ReadinessPanel({ enabled = true }) {
  const { data, isLoading } = useG7CuratorReadiness({ enabled })

  if (isLoading || !data) {
    return (
      <div style={{ padding: 16, color: DEVELOPER.fg2, fontFamily: FONTS.mono, fontSize: 11 }}>
        Loading G7 readiness…
      </div>
    )
  }

  const verdict = data.final_verdict || data.verdict || 'UNKNOWN'
  const tint = VERDICT_TINT[verdict] || DEVELOPER.bd
  const s2 = data.section_2_window_counts || {}
  const s3 = data.section_3_last_n_breakdown || {}
  const s5 = data.section_5_zero_tolerance_invariant || {}

  return (
    <div style={{ padding: '12px 16px', display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{
          fontFamily: FONTS.display, fontSize: 10, fontWeight: 700,
          letterSpacing: '0.18em', color: DEVELOPER.orange,
          textTransform: 'uppercase',
        }}>
          G7 — Curator Review Readiness
        </div>
        <div style={{
          fontFamily: FONTS.mono, fontSize: 10, fontWeight: 700,
          color: tint,
          background: `${tint}22`,
          border: `1px solid ${tint}66`,
          borderRadius: 3,
          padding: '2px 8px',
        }}>
          {verdict}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6,
                    fontFamily: FONTS.mono, fontSize: 10, color: DEVELOPER.fg2 }}>
        <div>7-day reviewed:</div>
        <div style={{ color: DEVELOPER.fg }}>
          {s2.reviewed_in_window ?? '—'} / {s2.total_in_window ?? '—'}
        </div>
        <div>Last 10 accept:</div>
        <div style={{ color: (s3.n_accept >= 9 ? DEVELOPER.green : DEVELOPER.fg) }}>
          {s3.n_accept ?? '—'} / 10
        </div>
        <div>Last 10 reject:</div>
        <div style={{ color: DEVELOPER.fg }}>{s3.n_reject ?? '—'}</div>
        <div>Overturn curator:</div>
        <div style={{ color: (s3.n_overturn_curator > 0 ? DEVELOPER.red : DEVELOPER.fg) }}>
          {s3.n_overturn_curator ?? '—'}
        </div>
        <div>FP rate (30d):</div>
        <div style={{ color: (s5.zero_tolerance_ok === false ? DEVELOPER.red : DEVELOPER.green) }}>
          {s5.false_positive_rate !== undefined ? s5.false_positive_rate.toFixed(4) : '—'}
        </div>
      </div>

      {verdict === 'PASS' && (
        <div style={{ fontFamily: FONTS.mono, fontSize: 9, color: DEVELOPER.green,
                      lineHeight: 1.4, marginTop: 2 }}>
          ✓ Curator ready for O2_SUGGEST → O3_ACT graduation. Operator may fire
          parallel_o3_act_anchor.py --confirm when all other gates clear.
        </div>
      )}
      {verdict === 'BLOCKED' && (
        <div style={{ fontFamily: FONTS.mono, fontSize: 9, color: DEVELOPER.amber,
                      lineHeight: 1.4, marginTop: 2 }}>
          ⏳ Need ≥10 operator-reviewed drafts; current: {s2.reviewed_in_window ?? 0}
        </div>
      )}
    </div>
  )
}
