// Phase O5-MLGA Stage 4 — MlgaLivePanel
//
// Live-progression tile for the DeveloperView MLGA drawer. Renders:
//   - Header: live session state (open / closed) + running totals
//   - Artifact list: recent MLGA VPM artifacts compiled at session close
//
// Mirrors DriftFindingsPanel pattern: enabled gate, polling halts when
// drawer closed, clean-state rendering when empty. Composes existing
// Phase O4 VPM tooling via useMlgaArtifacts (thin wrapper over
// useVpmList filtered by vpm_id=MLGA-SESSION-v1).
//
// noMock:true on both hooks (set inside bridgeApi.js). Grind-critical
// — fabricated data would corrupt operator dashboards mid-session.

import { useState } from 'react'
import { FONTS, DEVELOPER } from '../shared/design/tokens'
import { useMlgaLiveSession, useMlgaArtifacts } from '../api/bridgeApi'

function _truncHex(hex, n = 12) {
  if (!hex || typeof hex !== 'string') return ''
  const s = hex.startsWith('0x') ? hex.slice(2) : hex
  return s.length > n ? s.slice(0, n) + '…' : s
}

function _fmtDuration(seconds) {
  if (!seconds || seconds <= 0) return '—'
  if (seconds < 60) return `${seconds.toFixed(0)}s`
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return `${m}m ${s}s`
}

function _fmtTs(tsNs) {
  if (!tsNs || tsNs <= 0) return '—'
  const ms = Math.floor(Number(tsNs) / 1_000_000)
  if (!Number.isFinite(ms) || ms <= 0) return '—'
  return new Date(ms).toISOString().replace('T', ' ').replace(/\.\d+Z$/, 'Z')
}

export function MlgaLivePanel({ enabled = true }) {
  const liveQ = useMlgaLiveSession({ enabled })
  const artifactsQ = useMlgaArtifacts({ enabled, limit: 25 })

  const live = liveQ.data
  const rows = artifactsQ.data?.rows || []
  const [selected, setSelected] = useState(null)

  // Live status section
  const liveSection = (() => {
    if (liveQ.isLoading) {
      return <div style={s.muted}>Loading live state…</div>
    }
    if (liveQ.error) {
      return (
        <div style={s.errBox}>
          <strong>Live status error.</strong> The bridge endpoint
          /agent/mlga-live-session-status may be unreachable.
        </div>
      )
    }
    if (!live) return <div style={s.muted}>No status returned.</div>

    if (!live.enabled) {
      return (
        <div style={s.muted}>
          MLGA tracker DISABLED. Set MLGA_SESSION_TRACKER_ENABLED=true
          in bridge/.env + restart bridge.
        </div>
      )
    }
    if (!live.tracker_wired) {
      return (
        <div style={s.muted}>
          MLGA tracker enabled but not yet wired (bridge starting up).
        </div>
      )
    }
    if (!live.has_open_session) {
      return (
        <div style={s.cleanBox}>
          <div style={s.cleanH}>No open session.</div>
          <div style={s.cleanD}>
            Plug DualSense Edge USB-C in → PCC reports NOMINAL → tracker
            opens a session within 30s. Total sessions persisted lifetime:
            <strong style={{ marginLeft: 6, color: DEVELOPER.t1 }}>
              {live.sessions_persisted_total || 0}
            </strong>
            {live.last_close_ts_ns > 0 && (
              <>
                <br />
                Last close:{' '}
                <code style={s.code}>{_fmtTs(live.last_close_ts_ns)}</code>
                {' '}({live.last_close_reason || '—'})
              </>
            )}
          </div>
        </div>
      )
    }

    // Live session open — show running totals
    const apop = live.apop_state_counts || {}
    const apopStates = Object.keys(apop).sort()
    return (
      <div style={s.liveBox}>
        <div style={s.liveHeader}>
          <span style={s.liveBadge}>LIVE</span>
          <code style={s.code}>{live.session_id}</code>
          <span style={s.muted}>
            duration {_fmtDuration(live.session_duration_s)}
          </span>
        </div>
        <div style={s.totalsGrid}>
          <div style={s.totalCell}>
            <span style={s.totalLabel}>poac records</span>
            <span style={s.totalVal}>{live.n_poac_records}</span>
          </div>
          <div style={s.totalCell}>
            <span style={s.totalLabel}>R2 pulls</span>
            <span style={s.totalVal}>{live.n_trigger_pulls_r2}</span>
          </div>
          <div style={s.totalCell}>
            <span style={s.totalLabel}>L2 pulls</span>
            <span style={s.totalVal}>{live.n_trigger_pulls_l2}</span>
          </div>
          <div style={s.totalCell}>
            <span style={s.totalLabel}>GIC advances</span>
            <span style={s.totalVal}>{live.gic_advances_in_session}</span>
          </div>
        </div>
        {apopStates.length > 0 && (
          <div style={s.apopStrip}>
            {apopStates.map((st) => (
              <span key={st} style={s.apopChip}>
                <span style={s.apopState}>{st}</span>
                <span style={s.apopCount}>{apop[st]}</span>
              </span>
            ))}
          </div>
        )}
        <div style={s.muted}>
          BT observability: {['Not observed', 'Observed', 'Held↔Placed'][live.bt_observability] || 'Unknown'}
          {' · '}
          Sessions persisted lifetime: {live.sessions_persisted_total || 0}
        </div>
      </div>
    )
  })()

  // Artifact list section
  const artifactsSection = (() => {
    if (artifactsQ.isLoading) {
      return <div style={s.muted}>Loading artifacts…</div>
    }
    if (artifactsQ.error) {
      return (
        <div style={s.errBox}>
          Artifact list unavailable. /operator/vpm-list may be unreachable.
        </div>
      )
    }
    if (rows.length === 0) {
      return (
        <div style={s.muted}>
          No MLGA artifacts yet. Each closed session compiles one
          deterministic HTML VPM artifact at close-time.
        </div>
      )
    }
    return (
      <div style={s.artifactList}>
        {rows.map((r) => {
          const isSel = selected === r.commitment_hex
          return (
            <button
              key={r.commitment_hex}
              onClick={() => setSelected(r.commitment_hex)}
              style={{
                ...s.artifactRow,
                background: isSel ? `${DEVELOPER.orange}22` : 'transparent',
                borderColor: isSel ? `${DEVELOPER.orange}88` : DEVELOPER.bd,
              }}
              title={r.commitment_hex}
            >
              <span style={s.rowCommit}>
                {_truncHex(r.commitment_hex, 16)}
              </span>
              <span style={s.rowMeta}>
                {r.visual_state}
                {' · '}
                {_fmtTs(r.ts_ns)}
              </span>
            </button>
          )
        })}
      </div>
    )
  })()

  return (
    <div style={s.panel}>
      <div style={s.section}>
        <div style={s.sectionH}>Live session</div>
        {liveSection}
      </div>
      <div style={{ ...s.section, flex: 1, minHeight: 0 }}>
        <div style={s.sectionH}>
          Recent artifacts {rows.length > 0 && (
            <span style={s.countChip}>{rows.length}</span>
          )}
        </div>
        {artifactsSection}
      </div>
    </div>
  )
}

const s = {
  panel: {
    display: 'flex',
    flexDirection: 'column',
    gap: 10,
    height: '100%',
    fontFamily: FONTS.mono,
    color: DEVELOPER.t1,
  },
  section: {
    display: 'flex',
    flexDirection: 'column',
    gap: 6,
  },
  sectionH: {
    fontFamily: FONTS.display,
    fontSize: 9,
    color: DEVELOPER.t3,
    letterSpacing: '0.18em',
    textTransform: 'uppercase',
    display: 'flex',
    alignItems: 'center',
    gap: 6,
  },
  countChip: {
    fontFamily: FONTS.mono,
    fontSize: 8,
    color: DEVELOPER.orange,
    background: `${DEVELOPER.orange}22`,
    padding: '1px 5px',
    borderRadius: 2,
  },
  muted: {
    fontSize: 11,
    color: DEVELOPER.t2,
  },
  code: {
    fontFamily: FONTS.mono,
    fontSize: 10,
    color: DEVELOPER.t1,
    background: DEVELOPER.bg2,
    padding: '1px 4px',
    borderRadius: 2,
  },
  errBox: {
    fontSize: 11,
    color: DEVELOPER.red,
    border: `1px solid ${DEVELOPER.red}66`,
    background: `${DEVELOPER.red}11`,
    borderRadius: 3,
    padding: 8,
  },
  cleanBox: {
    border: `1px solid ${DEVELOPER.bd}`,
    background: DEVELOPER.bg1,
    borderRadius: 3,
    padding: 10,
  },
  cleanH: {
    fontFamily: FONTS.display,
    fontSize: 11,
    color: DEVELOPER.t2,
    marginBottom: 4,
  },
  cleanD: {
    fontSize: 11,
    color: DEVELOPER.t3,
    lineHeight: 1.5,
  },
  liveBox: {
    border: `1px solid ${DEVELOPER.green}55`,
    background: `${DEVELOPER.green}11`,
    borderRadius: 3,
    padding: 10,
  },
  liveHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    marginBottom: 8,
    flexWrap: 'wrap',
  },
  liveBadge: {
    fontFamily: FONTS.mono,
    fontSize: 9,
    fontWeight: 700,
    color: '#000',
    background: DEVELOPER.green,
    padding: '2px 6px',
    borderRadius: 2,
    letterSpacing: '0.1em',
  },
  totalsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(4, 1fr)',
    gap: 6,
    marginBottom: 8,
  },
  totalCell: {
    display: 'flex',
    flexDirection: 'column',
    gap: 2,
    padding: 6,
    background: DEVELOPER.bg1,
    border: `1px solid ${DEVELOPER.bd}`,
    borderRadius: 3,
  },
  totalLabel: {
    fontSize: 8,
    color: DEVELOPER.t3,
    textTransform: 'uppercase',
    letterSpacing: '0.1em',
  },
  totalVal: {
    fontSize: 14,
    color: DEVELOPER.orange,
    fontWeight: 600,
  },
  apopStrip: {
    display: 'flex',
    gap: 4,
    flexWrap: 'wrap',
    marginBottom: 8,
  },
  apopChip: {
    display: 'inline-flex',
    gap: 4,
    fontSize: 9,
    padding: '2px 5px',
    border: `1px solid ${DEVELOPER.bd}`,
    background: DEVELOPER.bg1,
    borderRadius: 2,
  },
  apopState: {
    color: DEVELOPER.t2,
  },
  apopCount: {
    color: DEVELOPER.t1,
    fontWeight: 600,
  },
  artifactList: {
    display: 'flex',
    flexDirection: 'column',
    gap: 4,
    overflowY: 'auto',
    maxHeight: '100%',
  },
  artifactRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 8,
    padding: '6px 8px',
    border: `1px solid ${DEVELOPER.bd}`,
    borderRadius: 3,
    cursor: 'pointer',
    fontFamily: FONTS.mono,
    fontSize: 10,
    color: DEVELOPER.t1,
    textAlign: 'left',
  },
  rowCommit: {
    fontFamily: FONTS.mono,
    fontSize: 10,
    color: DEVELOPER.orange,
  },
  rowMeta: {
    fontSize: 9,
    color: DEVELOPER.t3,
  },
}
