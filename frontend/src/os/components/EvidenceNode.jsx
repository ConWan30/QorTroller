/**
 * Evidence OS — EvidenceNode
 *
 * One DAG node card. Renders:
 *   - layer label (HID / PoAC / GIC / APOP / PCC / AIT / VHP / ZKBA / VPM / Curator / On-chain)
 *   - one-line mythology translation (operator-readable; Mythos-derived)
 *   - DataBadge with current status
 *   - source endpoint or hook (operator-debuggable provenance)
 *   - last timestamp (human-relative; "—" when N/A)
 *
 * Semantic: rendered as <article> for screen-reader navigability; the
 * inner badge is role="status". No clickable divs; if a node needs to
 * link to a detail route, parent wraps EvidenceNode in <Link>.
 *
 * Honesty discipline: when status='mock', text remains readable + the
 * mock badge is unmistakable. When status='killswitch', the source
 * line is appended with "(awaiting kill-switch lift)".
 */
import PropTypes from 'prop-types'
import DataBadge from './DataBadge'

function fmtRelative(tsMs) {
  if (!tsMs || tsMs <= 0) return '—'
  const deltaS = Math.max(0, Math.floor((Date.now() - tsMs) / 1000))
  if (deltaS < 60) return `${deltaS}s ago`
  if (deltaS < 3600) return `${Math.floor(deltaS / 60)}m ago`
  if (deltaS < 86400) return `${Math.floor(deltaS / 3600)}h ago`
  return `${Math.floor(deltaS / 86400)}d ago`
}

export default function EvidenceNode({
  layer, mythology, status, source, lastTsMs,
  detail, accent, onClickAction, ariaLabel,
}) {
  const Tag = onClickAction ? 'button' : 'article'
  const tagProps = onClickAction
    ? { onClick: onClickAction, type: 'button' }
    : {}
  return (
    <Tag
      {...tagProps}
      data-os-evidence-node={layer}
      aria-label={ariaLabel || `${layer}: ${mythology}`}
      style={{
        display:        'flex',
        flexDirection:  'column',
        gap:            8,
        padding:        '14px 16px',
        background:     'var(--os-panel)',
        border:         `1px solid var(--os-border)`,
        borderRadius:   'var(--os-radius)',
        borderLeft:     `3px solid ${accent || 'var(--os-accent)'}`,
        textAlign:      'left',
        cursor:         onClickAction ? 'pointer' : 'default',
        color:          'var(--os-text)',
        minWidth:       240,
        maxWidth:       360,
        fontFamily:     'JetBrains Mono, ui-monospace, monospace',
        transition:     'border-color 0.15s, transform 0.15s',
        position:       'relative',
      }}
      onMouseEnter={onClickAction ? (e) => {
        e.currentTarget.style.borderColor = 'var(--os-accent)'
      } : undefined}
      onMouseLeave={onClickAction ? (e) => {
        e.currentTarget.style.borderColor = 'var(--os-border)'
      } : undefined}
    >
      {/* Header row: layer label + status badge */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span style={{
          fontSize:       'var(--os-text-h3)',
          fontWeight:     700,
          letterSpacing:  '0.04em',
          color:          'var(--os-text)',
          flex:           1,
        }}>{layer}</span>
        <DataBadge status={status} />
      </div>

      {/* Mythology line — the human translation */}
      <div style={{
        fontSize:    'var(--os-text-base)',
        color:       'var(--os-text-dim)',
        lineHeight:  1.5,
        fontStyle:   'normal',
      }}>{mythology}</div>

      {/* Optional detail row (counts, hashes, etc.) */}
      {detail && (
        <div style={{
          fontSize:    'var(--os-text-min)',
          color:       'var(--os-text-faint)',
          lineHeight:  1.5,
        }}>{detail}</div>
      )}

      {/* Footer: source + timestamp */}
      <div style={{
        display:        'flex',
        gap:            12,
        marginTop:      'auto',
        paddingTop:     8,
        borderTop:      `1px solid var(--os-border-soft)`,
        fontSize:       'var(--os-text-min)',
        color:          'var(--os-text-faint)',
      }}>
        <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis' }}>
          <span aria-hidden="true">↳ </span>
          <code style={{ color: 'var(--os-text-dim)' }}>{source}</code>
          {status === 'killswitch' && (
            <span style={{ marginLeft: 6, color: 'var(--os-status-killswitch)', fontStyle: 'italic' }}>
              (awaiting kill-switch lift)
            </span>
          )}
        </span>
        <span style={{ whiteSpace: 'nowrap' }}>{fmtRelative(lastTsMs)}</span>
      </div>
    </Tag>
  )
}

EvidenceNode.propTypes = {
  layer:     PropTypes.string.isRequired,
  mythology: PropTypes.string.isRequired,
  status:    PropTypes.string,
  source:    PropTypes.string,
  lastTsMs:  PropTypes.number,
  detail:    PropTypes.node,
  accent:    PropTypes.string,
  onClickAction: PropTypes.func,
  ariaLabel: PropTypes.string,
}
