/**
 * Phase O4-VPM-INT Stream C.6 — VpmFilterChips
 *
 * Filter chip strip for the VPM Registry. Two chip rows:
 *   - vpm_id chips: All / HONESTY-BOARD / AGENT-REVIEW / CDRR-DAG /
 *                   GIC-LEDGER-BETA / DISPUTE-PACKET / MARKET-LISTING
 *   - visual_state chips: All / live / dry-run / emulated /
 *                         frozen-disabled / revoked / unverified
 *
 * Mirrors the DraftReviewPanel filter chip pattern. Controlled component;
 * parent owns state.
 */
import { FONTS } from '../shared/design/tokens'

// FROZEN VPM enums mirrored from scripts/vpm_visual_grammar.py + the
// Phase O4 Stream B _VPM_COMPILER_REGISTRY. Hard-coded here (not
// fetched) because the chip set is design-time-bound to the FROZEN
// compiler enum — if the enum changes, this file must be updated
// atomically with the audit harness.
const VPM_ID_CHIPS = [
  { value: '',                    label: 'ALL' },
  { value: 'HONESTY-BOARD-v1',    label: 'HONESTY-BOARD' },
  { value: 'AGENT-REVIEW-v1',     label: 'AGENT-REVIEW' },
  { value: 'CDRR-DAG-v1',         label: 'CDRR-DAG' },
  { value: 'GIC-LEDGER-BETA-v1',  label: 'GIC-BETA' },
  { value: 'DISPUTE-PACKET-v1',   label: 'DISPUTE' },
  { value: 'MARKET-LISTING-v1',   label: 'MARKET' },
  { value: 'MLGA-SESSION-v1',     label: 'MLGA' },
]

const VISUAL_STATE_CHIPS = [
  { value: '',                label: 'ALL',         color: '#7a8a9b' },
  { value: 'live',            label: 'LIVE',        color: '#5bd6a3' },
  { value: 'dry-run',         label: 'DRY-RUN',     color: '#f0a868' },
  { value: 'emulated',        label: 'EMULATED',    color: '#607a93' },
  { value: 'frozen-disabled', label: 'FROZEN',      color: '#1a2a40' },
  { value: 'revoked',         label: 'REVOKED',     color: '#d65b78' },
  { value: 'unverified',      label: 'UNVERIFIED',  color: '#d65b78' },
]

function ChipRow({ label, options, selected, onSelect, accent = '#f0a868' }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
      <span style={{
        fontFamily:    FONTS.mono,
        fontSize:      9,
        color:         'rgba(74,158,255,0.5)',
        letterSpacing: '0.08em',
        minWidth:      56,
      }}>{label}</span>
      {options.map((opt) => {
        const active = opt.value === selected
        const color = opt.color || accent
        return (
          <button
            key={opt.value || '__all'}
            data-vpm-filter-chip={opt.value || 'all'}
            onClick={() => onSelect(opt.value)}
            style={{
              background:   active ? `${color}1a` : 'transparent',
              border:       `1px solid ${active ? color : 'rgba(255,255,255,0.10)'}`,
              borderRadius: 12,
              padding:      '2px 10px',
              fontFamily:   FONTS.mono,
              fontSize:     10,
              fontWeight:   active ? 600 : 400,
              color:        active ? color : 'rgba(200,216,232,0.7)',
              cursor:       'pointer',
              letterSpacing: '0.05em',
              transition:   'all 0.15s ease',
            }}
          >
            {opt.label}
          </button>
        )
      })}
    </div>
  )
}

export function VpmFilterChips({
  vpmId,
  visualState,
  onVpmIdChange,
  onVisualStateChange,
}) {
  return (
    <div data-vpm-filter-chips style={{
      display:       'flex',
      flexDirection: 'column',
      gap:           6,
      padding:       '10px 12px',
      borderBottom:  '1px solid rgba(240,168,104,0.10)',
      background:    'rgba(2,4,8,0.6)',
    }}>
      <ChipRow
        label="VPM ID"
        options={VPM_ID_CHIPS}
        selected={vpmId}
        onSelect={onVpmIdChange}
      />
      <ChipRow
        label="STATE"
        options={VISUAL_STATE_CHIPS}
        selected={visualState}
        onSelect={onVisualStateChange}
      />
    </div>
  )
}

// Exported for unit tests + the grammar verifier to share the canonical
// FROZEN enum (matches scripts/vpm_visual_grammar.py VISUAL_STATES).
export const VPM_VISUAL_STATES_FROZEN = Object.freeze([
  'live',
  'dry-run',
  'emulated',
  'frozen-disabled',
  'revoked',
  'unverified',
])

export const VPM_ID_OPTIONS = VPM_ID_CHIPS
export const VISUAL_STATE_OPTIONS = VISUAL_STATE_CHIPS
