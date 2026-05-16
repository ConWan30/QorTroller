/**
 * Evidence OS — QueueItem
 *
 * One row in the operator's decision queue. Renders as a semantic
 * <button> when item.openable === true (operator can drill in via
 * keyboard); otherwise <article>. Critical severity (CRITICAL / BLOCKED)
 * shows a left-border tick mark + the word CRITICAL, so visual
 * urgency is never color-only.
 *
 * Item shape (consumed by both QueueItem and QueueDetailPanel):
 *   {
 *     id:               string            // stable key
 *     kind:             string            // 'draft' | 'curator' | 'drift' |
 *                                         //   'o3-blocker' | 'invariant-fail'
 *     title:            string            // human-readable headline
 *     protocolTerm:     string            // protocol-side label
 *     source:           string            // /endpoint or hook name
 *     severity:         'info'|'warn'|'critical'
 *     ageLabel:         string            // "12m ago", "—"
 *     recommendation:   string            // recommended next action
 *     actionLabel:      string?           // button label when actionable
 *     actionGuardReason: string?          // why action is disabled
 *     onAction:         function?         // click handler when enabled
 *     openable:         boolean           // expand into detail panel
 *   }
 */
import PropTypes from 'prop-types'
import DataBadge from './DataBadge'
import ActionGuardBadge from './ActionGuardBadge'

const _MONO = 'JetBrains Mono, ui-monospace, monospace'

const _SEVERITY_BADGE = {
  info:     'live',
  warn:     'pending',
  critical: 'blocked',
}

const _SEVERITY_LABEL = {
  info:     'INFO',
  warn:     'WARN',
  critical: 'CRITICAL',
}

export default function QueueItem({ item, onOpen, isSelected = false }) {
  const sevBadge = _SEVERITY_BADGE[item.severity] || 'dormant'
  const sevLabel = _SEVERITY_LABEL[item.severity] || 'INFO'
  const isCritical = item.severity === 'critical'

  const Tag = item.openable ? 'button' : 'article'
  const interactive = item.openable && typeof onOpen === 'function'
  // Mythos audit H4 — queue row is a disclosure widget (expand/hide
  // detail panel), so aria-expanded + aria-controls are the correct
  // pattern, NOT aria-pressed (toggle button).
  const detailPanelId = `queue-detail-${item.id}`

  return (
    <Tag
      type={Tag === 'button' ? 'button' : undefined}
      onClick={interactive ? () => onOpen(item) : undefined}
      data-os-queue-item={item.kind}
      data-os-severity={item.severity}
      aria-expanded={interactive ? isSelected : undefined}
      aria-controls={interactive ? detailPanelId : undefined}
      aria-label={`${sevLabel} · ${item.title}`}
      style={{
        textAlign:      'left',
        display:        'grid',
        gridTemplateColumns: 'minmax(0, 1fr) auto',
        gap:            '4px 12px',
        padding:        '12px 14px',
        background:     isSelected
          ? `color-mix(in srgb, var(--os-accent) 6%, var(--os-panel))`
          : 'var(--os-panel)',
        border:         `1px solid var(--os-border)`,
        borderLeft:     isCritical
          ? `4px solid var(--os-status-blocked)`
          : item.severity === 'warn'
            ? `4px solid var(--os-status-pending)`
            : `4px solid var(--os-border)`,
        borderRadius:   'var(--os-radius)',
        fontFamily:     _MONO,
        color:          'var(--os-text)',
        cursor:         interactive ? 'pointer' : 'default',
        width:          '100%',
      }}
    >
      {/* Row 1: title + severity word + age */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10, minWidth: 0,
      }}>
        {/* Visual urgency tick (no color-only) */}
        {isCritical && (
          <span aria-hidden="true" style={{
            color: 'var(--os-status-blocked)',
            fontWeight: 700, fontSize: 14,
          }}>!</span>
        )}
        <span style={{
          fontSize: 'var(--os-text-label)',
          fontWeight: 600,
          color: 'var(--os-text)',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          minWidth: 0,
        }}>{item.title}</span>
      </div>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        justifySelf: 'end',
      }}>
        <DataBadge status={sevBadge} label={sevLabel}/>
        <span style={{
          fontSize: 'var(--os-text-min)',
          color: 'var(--os-text-faint)',
        }}>{item.ageLabel || '—'}</span>
      </div>

      {/* Row 2: protocol term + source */}
      <div style={{
        gridColumn: '1 / -1',
        display: 'flex', gap: 14, flexWrap: 'wrap',
        fontSize: 'var(--os-text-min)',
        color: 'var(--os-text-faint)',
      }}>
        <span>
          protocol: <code style={{ color: 'var(--os-text-dim)' }}>{item.protocolTerm}</code>
        </span>
        <span>
          source: <code style={{ color: 'var(--os-text-dim)' }}>{item.source}</code>
        </span>
      </div>

      {/* Row 3: recommendation + action control or guard */}
      <div style={{
        gridColumn: '1 / -1',
        display: 'flex', alignItems: 'center', gap: 10,
        marginTop: 4,
        fontSize: 'var(--os-text-base)',
        color: 'var(--os-text-dim)',
      }}>
        <span style={{ flex: 1, minWidth: 0 }}>
          <span style={{ color: 'var(--os-text-faint)' }}>recommended: </span>
          {item.recommendation}
        </span>
        {item.actionLabel && (
          item.actionGuardReason || !item.onAction
            ? <ActionGuardBadge reason={item.actionGuardReason || 'no-mutation'} />
            : (
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); item.onAction(item) }}
                aria-label={`${item.actionLabel} for ${item.title}`}
                style={{
                  fontFamily: _MONO,
                  fontSize: 'var(--os-text-min)',
                  fontWeight: 600,
                  letterSpacing: '0.06em',
                  textTransform: 'uppercase',
                  padding: '6px 12px',
                  color: 'var(--os-accent)',
                  background: 'transparent',
                  border: '1px solid var(--os-accent)',
                  borderRadius: 'var(--os-radius)',
                  cursor: 'pointer',
                }}
              >{item.actionLabel}</button>
            )
        )}
      </div>
    </Tag>
  )
}

QueueItem.propTypes = {
  item: PropTypes.shape({
    id:                PropTypes.string.isRequired,
    kind:              PropTypes.string.isRequired,
    title:             PropTypes.string.isRequired,
    protocolTerm:      PropTypes.string,
    source:            PropTypes.string,
    severity:          PropTypes.oneOf(['info', 'warn', 'critical']),
    ageLabel:          PropTypes.string,
    recommendation:    PropTypes.string,
    actionLabel:       PropTypes.string,
    actionGuardReason: PropTypes.string,
    onAction:          PropTypes.func,
    openable:          PropTypes.bool,
  }).isRequired,
  onOpen:     PropTypes.func,
  isSelected: PropTypes.bool,
}
