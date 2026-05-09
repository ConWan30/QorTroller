/**
 * Phase 238 Frontend — ConsentMatrix component.
 *
 * SINGLE component used in 6 surfaces across the dashboard:
 *   1. Marketplace listing creation form  — mode='edit',     onChange callback
 *   2. Listing detail drawer              — mode='display'
 *   3. Gamer settings drawer              — mode='edit',     onChange callback (POSTs)
 *   4. Twin controller HUD mini-pills     — mode='compact',  no labels
 *   5. Curator FLAGGED_CONSENT_AMBIGUOUS toast  — mode='display', highlights cleared bit
 *   6. FSCA CONSENT_REVOKED_BUT_DATA_FLOWING badge — mode='display', red affected bits
 *
 * Bit positions FROZEN per Phase 237 CONSENT primitive:
 *   bit 0  TOURNAMENT_GATE
 *   bit 1  ANONYMIZED_RESEARCH
 *   bit 2  MANUFACTURER_CERT
 *   bit 3  MARKETPLACE
 *
 * The MARKETPLACE bit is required for any active listing — Curator's
 * FLAGGED_CONSENT_AMBIGUOUS verdict fires when that bit is cleared
 * post-listing-creation (GDPR Art.17 candidate).
 */
import { motion } from 'framer-motion'

export const CONSENT_CATEGORIES = [
  { bit: 0, key: 'TOURNAMENT_GATE',     label: 'Tournament Gate',     description: 'Eligibility verification for competitive play' },
  { bit: 1, key: 'ANONYMIZED_RESEARCH', label: 'Anonymized Research', description: 'Aggregate biometric datasets for protocol R&D' },
  { bit: 2, key: 'MANUFACTURER_CERT',   label: 'Manufacturer Cert',   description: 'Hardware certification telemetry sharing' },
  { bit: 3, key: 'MARKETPLACE',         label: 'Marketplace',         description: 'Per-session data listing on Phase 238 PALL' },
]

const MARKETPLACE_BIT = 1 << 3

/**
 * @param {object} props
 * @param {number} props.bitmask        — uint32, FROZEN bit positions per Phase 237
 * @param {('edit'|'display'|'compact')} props.mode
 * @param {function?} props.onChange    — (newBitmask) => void; required when mode='edit'
 * @param {string[]?} props.highlightCleared  — list of category keys whose cleared state should glow red
 *                                              (e.g. ['MARKETPLACE'] when Curator fires
 *                                              FLAGGED_CONSENT_AMBIGUOUS)
 */
export function ConsentMatrix({
  bitmask = 0,
  mode = 'display',
  onChange = null,
  highlightCleared = [],
}) {
  const isCompact = mode === 'compact'
  const isEdit    = mode === 'edit'

  const toggle = (bit) => {
    if (!isEdit || typeof onChange !== 'function') return
    onChange(bitmask ^ (1 << bit))
  }

  return (
    <div style={{
      display:        'flex',
      flexDirection:  isCompact ? 'row' : 'column',
      gap:            isCompact ? 6 : 8,
      fontFamily:     "'JetBrains Mono', monospace",
      fontSize:       isCompact ? 9 : 11,
      letterSpacing:  '0.04em',
    }}>
      {CONSENT_CATEGORIES.map((cat) => {
        const isSet = Boolean(bitmask & (1 << cat.bit))
        const isHighlighted = highlightCleared.includes(cat.key) && !isSet
        const dotColor = isSet
          ? (cat.bit === 3 ? 'var(--vapi-orange)' : 'var(--vapi-cyan)')
          : (isHighlighted ? 'var(--vapi-block)' : 'var(--vapi-tier-basic)')
        const dotGlow = isSet
          ? (cat.bit === 3 ? 'var(--vapi-orange-glow)' : 'var(--vapi-cyan-glow)')
          : (isHighlighted ? 'var(--vapi-glow-block)' : 'none')

        if (isCompact) {
          return (
            <span
              key={cat.bit}
              title={`${cat.label} ${isSet ? '✓' : '✗'}: ${cat.description}`}
              style={{
                width:        10,
                height:       10,
                borderRadius: 5,
                background:   dotColor,
                boxShadow:    dotGlow,
                opacity:      isSet ? 1 : 0.45,
                transition:   'all 0.18s',
              }}
            />
          )
        }

        return (
          <motion.div
            key={cat.bit}
            initial={false}
            animate={isHighlighted ? { x: [0, -3, 3, -2, 2, 0] } : {}}
            transition={{ duration: 0.5 }}
            style={{
              display:        'flex',
              alignItems:     'center',
              gap:            10,
              padding:        '6px 10px',
              borderRadius:   3,
              background:     isHighlighted ? 'rgba(239,68,68,0.08)' : 'rgba(255,255,255,0.02)',
              border:         '1px solid',
              borderColor:    isHighlighted
                ? 'rgba(239,68,68,0.4)'
                : isSet ? 'rgba(34,211,238,0.25)' : 'rgba(125,133,144,0.2)',
              cursor:         isEdit ? 'pointer' : 'default',
              transition:     'all 0.18s',
            }}
            onClick={() => toggle(cat.bit)}
          >
            {/* Status dot */}
            <span style={{
              width:        12,
              height:       12,
              borderRadius: 6,
              background:   dotColor,
              boxShadow:    dotGlow,
              flexShrink:   0,
            }} />

            {/* Label + description */}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{
                color:    isSet ? 'var(--vapi-tier-verified)' : (isHighlighted ? 'var(--vapi-block)' : 'var(--vapi-tier-basic)'),
                fontWeight: isHighlighted ? 700 : 500,
                fontSize:   11,
              }}>
                {cat.label}
                {cat.bit === 3 && (
                  <span style={{ color: 'var(--vapi-orange)', marginLeft: 6, fontSize: 9 }}>
                    [REQUIRED FOR LISTING]
                  </span>
                )}
              </div>
              <div style={{
                color:        'rgba(125,133,144,0.7)',
                fontSize:     9,
                marginTop:    2,
                whiteSpace:   'nowrap',
                overflow:     'hidden',
                textOverflow: 'ellipsis',
              }}>
                {cat.description}
              </div>
            </div>

            {/* Toggle status text */}
            <span style={{
              color:    isSet ? 'var(--vapi-tier-verified)' : 'var(--vapi-tier-basic)',
              fontSize: 10,
              fontWeight: 600,
              minWidth: 32,
              textAlign: 'right',
            }}>
              {isSet ? 'GRANTED' : 'CLEARED'}
            </span>
          </motion.div>
        )
      })}

      {/* MARKETPLACE consent warning when listing context + bit cleared */}
      {!isCompact && !(bitmask & MARKETPLACE_BIT) && highlightCleared.includes('MARKETPLACE') && (
        <div style={{
          marginTop:  4,
          padding:    '6px 10px',
          borderLeft: '3px solid var(--vapi-block)',
          background: 'rgba(239,68,68,0.05)',
          color:      'var(--vapi-block)',
          fontSize:   10,
        }}>
          <strong>GDPR Art.17 Candidate</strong> — MARKETPLACE bit cleared while listing active.
          Curator FLAGGED_CONSENT_AMBIGUOUS surveillance triggered.
        </div>
      )}
    </div>
  )
}

ConsentMatrix.MARKETPLACE_BIT = MARKETPLACE_BIT
