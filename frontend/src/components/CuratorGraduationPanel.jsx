// Phase O4 post-backlog-closure — Curator O2 → O3 graduation readiness panel.
//
// Binds GET /operator/curator-graduation-readiness (bridge endpoint shipped at
// commit 0f2d10fa; wraps scripts/curator_graduation_readiness_audit.py).
// Consolidates 4 sub-audits (G7 + Operator Initiative watcher + CFSS lane
// authority + on-chain anchor state) into a single READY/BLOCKED/FAIL/ERROR
// verdict (priority: ERROR > FAIL > BLOCKED > READY).
//
// When verdict=READY appears, the operator may fire parallel_o3_act_anchor.py
// --confirm with operator three-factor authorization at PowerShell terminal.

import { FONTS, DEVELOPER } from '../shared/design/tokens'
import { useCuratorGraduationReadiness } from '../api/bridgeApi'

const VERDICT_TINT = {
  READY:   DEVELOPER.green,
  BLOCKED: DEVELOPER.amber,
  FAIL:    DEVELOPER.red,
  ERROR:   DEVELOPER.red,
  UNKNOWN: DEVELOPER.bd,
}

const SECTION_TINT = {
  PASS:    DEVELOPER.green,
  BLOCKED: DEVELOPER.amber,
  FAIL:    DEVELOPER.red,
  ERROR:   DEVELOPER.red,
}

function SectionRow({ label, verdictClass }) {
  const tint = SECTION_TINT[verdictClass] || DEVELOPER.bd
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8,
                  fontFamily: FONTS.mono, fontSize: 10 }}>
      <div style={{ flex: 1, color: DEVELOPER.fg2 }}>{label}</div>
      <div style={{
        color: tint,
        background: `${tint}22`,
        border: `1px solid ${tint}66`,
        borderRadius: 2,
        padding: '1px 6px',
        fontSize: 9, fontWeight: 700, letterSpacing: '0.1em',
      }}>
        {verdictClass || '—'}
      </div>
    </div>
  )
}

export function CuratorGraduationPanel({ enabled = true }) {
  const { data, isLoading } = useCuratorGraduationReadiness({ enabled })

  if (isLoading || !data) {
    return (
      <div style={{ padding: 16, color: DEVELOPER.fg2, fontFamily: FONTS.mono, fontSize: 11 }}>
        Loading Curator graduation readiness…
      </div>
    )
  }

  const s1 = data.section_1_g7_acceptance_gate || {}
  const s2 = data.section_2_operator_initiative_watcher || {}
  const s3 = data.section_3_cfss_lane_authority || {}
  const s4 = data.section_4_on_chain_anchor_state || {}
  const s5 = data.section_5_consolidated_verdict || {}
  const verdict = s5.verdict || 'UNKNOWN'
  const tint = VERDICT_TINT[verdict] || DEVELOPER.bd

  return (
    <div style={{ padding: '12px 16px', display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{
          fontFamily: FONTS.display, fontSize: 10, fontWeight: 700,
          letterSpacing: '0.18em', color: DEVELOPER.orange,
          textTransform: 'uppercase',
        }}>
          Curator Graduation — O2 → O3
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

      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        <SectionRow label="① G7 acceptance gate"        verdictClass={s1.verdict_class} />
        <SectionRow label="② Operator initiative watcher" verdictClass={s2.verdict_class} />
        <SectionRow label="③ CFSS lane authority"        verdictClass={s3.verdict_class} />
        <SectionRow label="④ On-chain anchor state"      verdictClass={s4.verdict_class} />
      </div>

      {s5.reason && (
        <div style={{
          marginTop: 4, padding: 8,
          background: `${tint}11`,
          border: `1px solid ${tint}44`,
          borderRadius: 3,
          fontFamily: FONTS.mono, fontSize: 9, color: DEVELOPER.fg2,
          lineHeight: 1.4,
        }}>
          {s5.reason}
        </div>
      )}

      {verdict === 'READY' && (
        <div style={{ fontFamily: FONTS.mono, fontSize: 9, color: DEVELOPER.green,
                      lineHeight: 1.4 }}>
          ✓ All 4 sections cleared. Operator may fire
          parallel_o3_act_anchor.py --confirm (~0.18–0.23 IOTX testnet).
        </div>
      )}
    </div>
  )
}
