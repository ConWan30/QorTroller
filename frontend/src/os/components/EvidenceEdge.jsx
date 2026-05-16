/**
 * Evidence OS — EvidenceEdge
 *
 * One line shape per binding semantic (Mythos-derived):
 *   solid    — cryptographic binding (HID→PoAC ECDSA-P256; PoAC→GIC
 *              hash inclusion; GIC→VHP mint metadata)
 *   dotted   — derived/polled (PoAC→APOP/PCC/AIT via frame stream;
 *              VPM→Curator via 6h poll)
 *   dashed   — predicate gate (APOP/PCC/AIT→GIC: pcc_state=NOMINAL
 *              AND host_state in {USB,UNKNOWN} AND gameplay_ok)
 *   ghost    — kill-switch-paused (every on-chain edge while
 *              CHAIN_SUBMISSION_PAUSED=true)
 *
 * Rendered as inline SVG arrow between two anchor points. Accessibility:
 * decorative; aria-hidden. The kind label is surfaced via title for
 * pointer hover.
 *
 * For the first vertical slice we render edges as a small SVG ABOVE the
 * grid that overlays connecting lines between visually adjacent nodes.
 * Geometry is intentionally simple (straight lines between center anchors);
 * a future stage will swap to a layout-aware d3 graph.
 */
import PropTypes from 'prop-types'

const _KIND_LABEL = {
  solid:  'cryptographic',
  dotted: 'derived / polled',
  dashed: 'predicate gate',
  ghost:  'kill-switch paused',
}

export default function EvidenceEdge({
  kind = 'solid',
  from = { x: 0, y: 0 },
  to   = { x: 0, y: 0 },
  ariaHidden = true,
}) {
  const dx = to.x - from.x
  const dy = to.y - from.y
  const len = Math.hypot(dx, dy) || 1
  // shorten line by 6px on each end so it doesn't overlap node borders
  const ux = dx / len, uy = dy / len
  const x1 = from.x + ux * 6
  const y1 = from.y + uy * 6
  const x2 = to.x   - ux * 6
  const y2 = to.y   - uy * 6
  const dasharray =
    kind === 'dotted' ? '2 3' :
    kind === 'dashed' ? '6 4' :
    kind === 'ghost'  ? '1 4' : 'none'
  const stroke =
    kind === 'solid'  ? 'var(--os-chain)' :
    kind === 'dotted' ? 'var(--os-derived)' :
    kind === 'dashed' ? 'var(--os-predicate)' :
    'var(--os-ghost)'
  return (
    <line
      data-os-edge={kind}
      aria-hidden={ariaHidden}
      x1={x1} y1={y1} x2={x2} y2={y2}
      stroke={stroke}
      strokeWidth={kind === 'solid' ? 1.5 : 1.2}
      strokeDasharray={dasharray === 'none' ? undefined : dasharray}
      markerEnd="url(#os-edge-arrowhead)"
    >
      <title>{_KIND_LABEL[kind]}</title>
    </line>
  )
}

EvidenceEdge.propTypes = {
  kind: PropTypes.oneOf(['solid', 'dotted', 'dashed', 'ghost']),
  from: PropTypes.shape({ x: PropTypes.number, y: PropTypes.number }),
  to:   PropTypes.shape({ x: PropTypes.number, y: PropTypes.number }),
  ariaHidden: PropTypes.bool,
}

/** Arrowhead marker — include once at SVG root level. */
export function EvidenceEdgeArrowDefs() {
  return (
    <defs>
      <marker
        id="os-edge-arrowhead"
        viewBox="0 0 10 10"
        refX="9" refY="5"
        markerWidth="6" markerHeight="6"
        orient="auto-start-reverse"
      >
        <path d="M 0 0 L 10 5 L 0 10 z" fill="currentColor" opacity="0.5" />
      </marker>
    </defs>
  )
}
