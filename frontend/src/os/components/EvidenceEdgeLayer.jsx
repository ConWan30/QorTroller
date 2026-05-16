/**
 * Evidence OS — EvidenceEdgeLayer (Stage 6, Option B)
 *
 * Measures real DOM positions of EvidenceNode cards inside a parent
 * container and draws SVG lines representing the protocol's actual
 * cryptographic / predicate-gate / derived-poll / kill-switch-ghost
 * relationships. Re-measures on ResizeObserver tick so edges stay
 * pinned across viewport / flex-wrap changes.
 *
 * Honesty discipline:
 *   - Edges that name a relationship the workspace DOES NOT have
 *     fresh data for render as ghost (translucent dashed) — never
 *     as solid live bindings
 *   - When the source OR target node is missing from the DOM (e.g.
 *     a future row not yet shipped), the edge is silently skipped
 *   - When the container is narrower than _NARROW_THRESHOLD_PX, the
 *     entire layer suppresses itself; cards stack vertically on
 *     mobile / tablet and edges between flex-wrapped neighbours
 *     would mislead. The accompanying text-summary remains
 *     screen-reader accessible regardless
 *
 * Input model:
 *   nodeSelector — function() → string  (CSS selector matched
 *                                        against children of
 *                                        containerRef.current; we
 *                                        use [data-os-evidence-node])
 *   edges        — array of {from, to, kind, dormant?}
 *                  kind ∈ 'chain' | 'predicate' | 'derived' | 'ghost'
 *                  dormant: true → force ghost styling regardless of kind
 *   containerRef — ref to the positioning ancestor (must be
 *                  position:relative)
 *
 * Accessibility:
 *   The <svg> is aria-hidden because the edge geometry is a visual
 *   layer; the same relationships are exposed to screen readers via
 *   the parent workspace's EvidenceRelationshipSummary component.
 */
import { useEffect, useState, useRef, useCallback } from 'react'
import PropTypes from 'prop-types'

const _NARROW_THRESHOLD_PX = 760  // below this, suppress (matches AppShell rail collapse)
const _NODE_DATA_ATTR      = 'data-os-evidence-node'

const _KIND_TO_CLASS = {
  chain:     'os-edge--solid',
  derived:   'os-edge--dotted',
  predicate: 'os-edge--dashed',
  ghost:     'os-edge--ghost',
}

/**
 * Compute the SVG-relative anchor point on a node's edge that faces
 * the other endpoint. Picks the closest of the four cardinal mid-
 * points (top, bottom, left, right) so the line attaches cleanly.
 */
function _anchorTowards(rect, other) {
  const cx = rect.x + rect.w / 2
  const cy = rect.y + rect.h / 2
  const ocx = other.x + other.w / 2
  const ocy = other.y + other.h / 2
  const dx = ocx - cx
  const dy = ocy - cy
  // Same row (or nearly) — go horizontal
  if (Math.abs(dy) < 24) {
    return dx >= 0
      ? { x: rect.x + rect.w, y: cy }   // right edge
      : { x: rect.x,          y: cy }   // left  edge
  }
  // Otherwise vertical (top/bottom)
  return dy >= 0
    ? { x: cx, y: rect.y + rect.h }     // bottom
    : { x: cx, y: rect.y }              // top
}

export default function EvidenceEdgeLayer({
  containerRef,
  edges,
  nodeDataAttr = _NODE_DATA_ATTR,
}) {
  const [size, setSize]           = useState({ w: 0, h: 0 })
  const [narrow, setNarrow]       = useState(false)
  const [computed, setComputed]   = useState([])
  const svgRef                    = useRef(null)
  const rafRef                    = useRef(null)

  // ── measure routine ──────────────────────────────────────────────
  const measure = useCallback(() => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current)
    rafRef.current = requestAnimationFrame(() => {
      const c = containerRef?.current
      if (!c) { setComputed([]); return }
      const cBox  = c.getBoundingClientRect()
      const isNarrow = cBox.width < _NARROW_THRESHOLD_PX
      setNarrow(isNarrow)
      setSize({ w: cBox.width, h: cBox.height })
      if (isNarrow) { setComputed([]); return }

      // Map every node in container by its data attribute
      const nodeEls = c.querySelectorAll(`[${nodeDataAttr}]`)
      const rectMap = new Map()
      nodeEls.forEach((el) => {
        const key = el.getAttribute(nodeDataAttr)
        const box = el.getBoundingClientRect()
        rectMap.set(key, {
          x: box.left - cBox.left,
          y: box.top  - cBox.top,
          w: box.width,
          h: box.height,
        })
      })

      // For each requested edge, only compute geometry if BOTH
      // endpoints exist in the rendered DOM. Skip silently otherwise
      // (missing endpoint = relationship not represented yet).
      const next = []
      edges.forEach((e, i) => {
        const a = rectMap.get(e.from)
        const b = rectMap.get(e.to)
        if (!a || !b) return
        const pa = _anchorTowards(a, b)
        const pb = _anchorTowards(b, a)
        next.push({
          key:   `${e.from}->${e.to}-${i}`,
          x1:    pa.x,
          y1:    pa.y,
          x2:    pb.x,
          y2:    pb.y,
          kind:  e.dormant ? 'ghost' : (e.kind || 'chain'),
          from:  e.from,
          to:    e.to,
        })
      })
      setComputed(next)
    })
  }, [containerRef, edges, nodeDataAttr])

  // ── lifecycle: measure on mount + ResizeObserver + window resize
  useEffect(() => {
    measure()
    if (typeof ResizeObserver === 'undefined') {
      // Fallback for environments without ResizeObserver (older jsdom)
      window.addEventListener('resize', measure)
      return () => window.removeEventListener('resize', measure)
    }
    const c = containerRef?.current
    if (!c) return undefined
    const ro = new ResizeObserver(() => measure())
    ro.observe(c)
    // Also watch each child since flex-wrap can change without
    // container resizing
    c.querySelectorAll(`[${nodeDataAttr}]`).forEach((el) => ro.observe(el))
    return () => ro.disconnect()
  }, [containerRef, edges, measure, nodeDataAttr])

  // ── render ───────────────────────────────────────────────────────
  if (narrow) {
    // Suppressed on mobile/tablet — honest degradation
    return (
      <div
        data-os-edge-layer="suppressed-narrow"
        aria-hidden="true"
        style={{ display: 'none' }}
      />
    )
  }

  return (
    <svg
      ref={svgRef}
      data-os-edge-layer={computed.length > 0 ? 'rendered' : 'empty'}
      aria-hidden="true"
      width={size.w}
      height={size.h}
      style={{
        position:      'absolute',
        inset:         0,
        pointerEvents: 'none',
        zIndex:        0,
        overflow:      'visible',
      }}
    >
      {computed.map(line => (
        <line
          key={line.key}
          x1={line.x1} y1={line.y1}
          x2={line.x2} y2={line.y2}
          className={_KIND_TO_CLASS[line.kind] || _KIND_TO_CLASS.chain}
          data-os-edge-from={line.from}
          data-os-edge-to={line.to}
          data-os-edge-kind={line.kind}
        />
      ))}
    </svg>
  )
}

EvidenceEdgeLayer.propTypes = {
  containerRef: PropTypes.shape({
    current: PropTypes.any,
  }).isRequired,
  edges: PropTypes.arrayOf(PropTypes.shape({
    from:    PropTypes.string.isRequired,
    to:      PropTypes.string.isRequired,
    kind:    PropTypes.oneOf(['chain', 'derived', 'predicate', 'ghost']),
    dormant: PropTypes.bool,
  })).isRequired,
  nodeDataAttr: PropTypes.string,
}
