/**
 * Phase 238 Frontend — TierBadge component.
 *
 * Displays a tier badge (Basic/Verified/Attested/Premium) with the FROZEN
 * VAPI tier color palette.  Tier is computed cryptographically from the
 * on-chain anchor count by VAPIDataMarketplaceListings.sol — sellers
 * cannot self-attest tier.  Optional legend tooltip on hover.
 */
import { motion } from 'framer-motion'

const TIER_NAMES = ['Basic', 'Verified', 'Attested', 'Premium']
const TIER_MULTIPLIERS = ['1.0×', '1.5×', '2.0×', '3.0×']
const TIER_CLASS = ['basic', 'verified', 'attested', 'premium']
const TIER_DESCRIPTIONS = [
  '1.0× — no anchors recorded on AdjudicationRegistry',
  '1.5× — exactly 1 of 4 anchors recorded',
  '2.0× — 2 or 3 anchors recorded',
  '3.0× — all 4 anchors recorded (SEPPROOF + BIOMETRIC + CORPUS + GIC)',
]

export function TierBadge({ tier = 0, showMultiplier = true, showTooltip = true, animated = false }) {
  const safeTier = Math.max(0, Math.min(3, Number(tier) | 0))
  const name = TIER_NAMES[safeTier]
  const mult = TIER_MULTIPLIERS[safeTier]
  const cls  = TIER_CLASS[safeTier]
  const description = TIER_DESCRIPTIONS[safeTier]

  const Component = animated ? motion.span : 'span'
  const motionProps = animated ? {
    initial: { opacity: 0, scale: 0.9 },
    animate: { opacity: 1, scale: 1 },
    transition: { duration: 0.2 },
  } : {}

  return (
    <Component
      className={`vapi-tier-badge vapi-tier-badge--${cls}`}
      title={showTooltip ? description : undefined}
      {...motionProps}
    >
      <span style={{ fontWeight: 700 }}>{name.toUpperCase()}</span>
      {showMultiplier && (
        <span style={{
          opacity: 0.75,
          fontSize: '9px',
          marginLeft: 2,
        }}>{mult}</span>
      )}
    </Component>
  )
}

/** TierLegend — always-visible reference for buyer/operator. */
export function TierLegend() {
  return (
    <div style={{
      display: 'flex',
      gap: 8,
      flexWrap: 'wrap',
      padding: '6px 0',
      fontFamily: "'JetBrains Mono', monospace",
      fontSize: 10,
    }}>
      {[0, 1, 2, 3].map((t) => (
        <TierBadge key={t} tier={t} showMultiplier showTooltip={false} />
      ))}
    </div>
  )
}
