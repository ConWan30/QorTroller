// Phase O4 post-backlog-closure — CFSS Cedar-policy lane drift panel.
//
// Binds GET /operator/cfss-lane-drift-status (bridge endpoint shipped at
// commit 0f2d10fa; wraps scripts/cfss_lane_drift_sweep.py).
// Closes the data-layer / policy-layer enforcement asymmetry for Cedar
// v2 Cross-Fleet Skill Separation (CFSS).
//
// Companion to:
//   - Runtime cfss_drift_sweeper.py async task (60s cadence; opt-in)
//   - 27th FSCA rule CFSS_LANE_AUTHORITY_DRIFT (CRITICAL)
//
// Frontend usage: poll the HTTP endpoint as a snapshot view alongside
// the continuous bridge sweeper. When CFSS_VIOLATION appears here AND
// in the FSCA log, the operator knows both detection layers agree.

import { FONTS, DEVELOPER } from '../shared/design/tokens'
import { useCFSSLaneDriftStatus } from '../api/bridgeApi'

const VERDICT_TINT = {
  PASS:               DEVELOPER.green,
  CFSS_VIOLATION:     DEVELOPER.red,
  BUNDLE_LOAD_ERROR:  DEVELOPER.amber,
  CONFIG_ERROR:       DEVELOPER.amber,
  UNKNOWN:            DEVELOPER.bd,
}

export function CFSSLaneDriftPanel({ enabled = true }) {
  const { data, isLoading } = useCFSSLaneDriftStatus({ enabled })

  if (isLoading || !data) {
    return (
      <div style={{ padding: 16, color: DEVELOPER.fg2, fontFamily: FONTS.mono, fontSize: 11 }}>
        Loading CFSS lane authority status…
      </div>
    )
  }

  const verdict = data.verdict || 'UNKNOWN'
  const tint = VERDICT_TINT[verdict] || DEVELOPER.bd
  const violations = data.violations || []

  return (
    <div style={{ padding: '12px 16px', display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{
          fontFamily: FONTS.display, fontSize: 10, fontWeight: 700,
          letterSpacing: '0.18em', color: DEVELOPER.orange,
          textTransform: 'uppercase',
        }}>
          CFSS — Cedar Lane Authority
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
        <div>Expected rows:</div>
        <div style={{ color: DEVELOPER.fg }}>{data.expected_rows ?? 12}</div>
        <div>Rows evaluated:</div>
        <div style={{ color: DEVELOPER.fg }}>{(data.rows || []).length}</div>
        <div>Violations:</div>
        <div style={{ color: (violations.length > 0 ? DEVELOPER.red : DEVELOPER.green) }}>
          {violations.length}
        </div>
      </div>

      {violations.length > 0 && (
        <div style={{
          marginTop: 4, padding: 8,
          background: `${DEVELOPER.red}11`,
          border: `1px solid ${DEVELOPER.red}44`,
          borderRadius: 3,
          fontFamily: FONTS.mono, fontSize: 9, color: DEVELOPER.red,
        }}>
          {violations.slice(0, 4).map((v, i) => (
            <div key={i} style={{ marginBottom: 4 }}>
              <strong>{v.agent_id}</strong> · {v.action}
              <br />
              <span style={{ color: DEVELOPER.fg2 }}>
                {v.actual_effect} (expected {v.expected_effect})
              </span>
            </div>
          ))}
          {violations.length > 4 && (
            <div style={{ color: DEVELOPER.fg2 }}>
              … +{violations.length - 4} more
            </div>
          )}
        </div>
      )}

      {verdict === 'PASS' && (
        <div style={{ fontFamily: FONTS.mono, fontSize: 9, color: DEVELOPER.green,
                      lineHeight: 1.4 }}>
          ✓ All 12 lane-authority rows match EXPECTED_LANE_MATRIX.
          Cedar v2 bundles aligned with on-chain anchor (2026-05-12 ceremony).
        </div>
      )}
    </div>
  )
}
