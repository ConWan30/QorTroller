/**
 * Evidence OS — VerificationReceipt
 *
 * Audit-grade panel summarising what was recomputed locally vs what
 * the protocol claimed. Designed as the "footer" of any forensic
 * replay view so the operator/public auditor has a single block to
 * cite when reporting an outcome.
 *
 * Item shape:
 *   {
 *     id:        string                       // unique key
 *     claim:     string                       // "GIC genesis hash for grind_…"
 *     protocol:  string                       // expected hash / value
 *     computed:  string                       // browser-recomputed value
 *     status:    'ok' | 'mismatch' | 'skipped' | 'pending' | 'error'
 *     source:    string                       // /public/... endpoint
 *     algorithm: string?                      // verifier function name
 *     reason:    string?                      // (for skipped/error)
 *     tsMs:      number?                      // when check ran
 *   }
 *
 * Discipline:
 *   - role='region' + aria-labelledby; status word is REDUNDANT to
 *     color — every row carries OK / MISMATCH / SKIPPED / PENDING / ERROR
 *   - protocol vs computed rendered as <code> blocks with explicit
 *     "Protocol claim:" / "Recomputed in this browser:" labels
 *     (operator brief — human-first copy)
 *   - long hex values wrap (word-break: break-all) so the receipt
 *     stays readable on narrow viewports
 *   - copy-to-clipboard button on the computed value so auditors
 *     can quote the receipt verbatim
 *   - empty state ('no checks executed') honestly reports zero
 *     verifications instead of falsely implying "all good"
 */
import { useId, useState, useCallback } from 'react'
import PropTypes from 'prop-types'
import DataBadge from './DataBadge'

const _MONO = 'JetBrains Mono, ui-monospace, monospace'

const _STATUS_BADGE = {
  ok:       'verified',
  mismatch: 'blocked',
  skipped:  'killswitch',
  pending:  'pending',
  error:    'blocked',
}

const _STATUS_LABEL = {
  ok:       'OK',
  mismatch: 'MISMATCH',
  skipped:  'SKIPPED',
  pending:  'PENDING',
  error:    'ERROR',
}

function _fmtTs(tsMs) {
  if (!tsMs) return ''
  try { return new Date(tsMs).toISOString().replace('T', ' ').slice(0, 19) + 'Z' }
  catch { return '' }
}

function _CopyButton({ text, label }) {
  const [copied, setCopied] = useState(false)
  const copy = useCallback(() => {
    if (!text) return
    if (!navigator?.clipboard?.writeText) return
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    }).catch(() => {})
  }, [text])
  return (
    <button
      type="button"
      onClick={copy}
      aria-label={`Copy ${label}`}
      style={{
        fontFamily: _MONO,
        fontSize: 'var(--os-text-min)',
        padding: '2px 8px',
        color: copied ? 'var(--os-status-live)' : 'var(--os-text-dim)',
        background: 'transparent',
        border: `1px solid ${copied ? 'var(--os-status-live)' : 'var(--os-border)'}`,
        borderRadius: 'var(--os-radius)',
        cursor: 'pointer',
      }}
    >{copied ? 'copied' : 'copy'}</button>
  )
}

_CopyButton.propTypes = { text: PropTypes.string, label: PropTypes.string }

function _ReceiptRow({ item }) {
  const status = item.status || 'skipped'
  const badge = _STATUS_BADGE[status] || 'dormant'
  const label = _STATUS_LABEL[status] || 'UNKNOWN'
  const isOk = status === 'ok'
  const isBad = status === 'mismatch' || status === 'error'

  return (
    <li
      data-os-receipt-row={item.id}
      data-os-receipt-status={status}
      style={{
        display:       'flex',
        flexDirection: 'column',
        gap:           6,
        padding:       '10px 12px',
        background:    'var(--os-panel)',
        border:        '1px solid var(--os-border)',
        borderLeft:    `3px solid ${
          isOk  ? 'var(--os-status-live)'
            : isBad ? 'var(--os-status-blocked)'
              : 'var(--os-status-killswitch)'
        }`,
        borderRadius:  'var(--os-radius)',
      }}
    >
      <div style={{
        display:        'flex',
        alignItems:     'center',
        justifyContent: 'space-between',
        gap:            12,
        flexWrap:       'wrap',
      }}>
        <div style={{
          fontSize: 'var(--os-text-label)',
          fontWeight: 600,
          color: 'var(--os-text)',
          flex: 1, minWidth: 0,
        }}>{item.claim}</div>
        <DataBadge status={badge} label={label}/>
      </div>

      {/* Protocol claim — what the bridge / chain says is true */}
      {item.protocol && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          <span style={{
            fontSize: 'var(--os-text-min)',
            color: 'var(--os-text-faint)',
          }}>Protocol claim</span>
          <code style={{
            fontFamily: _MONO,
            fontSize: 'var(--os-text-min)',
            color: 'var(--os-text-dim)',
            wordBreak: 'break-all',
            whiteSpace: 'pre-wrap',
            padding: '4px 6px',
            background: 'var(--os-bg)',
            border: '1px solid var(--os-border-soft)',
            borderRadius: 'var(--os-radius)',
          }}>{item.protocol}</code>
        </div>
      )}

      {/* Recomputed — what THIS browser produced */}
      {item.computed && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          <div style={{
            display:        'flex',
            alignItems:     'center',
            justifyContent: 'space-between',
          }}>
            <span style={{
              fontSize: 'var(--os-text-min)',
              color: 'var(--os-text-faint)',
            }}>Recomputed in this browser</span>
            <_CopyButton text={item.computed} label="recomputed value"/>
          </div>
          <code style={{
            fontFamily: _MONO,
            fontSize: 'var(--os-text-min)',
            color: isOk ? 'var(--os-status-live)' : isBad ? 'var(--os-status-blocked)' : 'var(--os-text-dim)',
            wordBreak: 'break-all',
            whiteSpace: 'pre-wrap',
            padding: '4px 6px',
            background: 'var(--os-bg)',
            border: '1px solid var(--os-border-soft)',
            borderRadius: 'var(--os-radius)',
          }}>{item.computed}</code>
        </div>
      )}

      {/* Reason — skipped / error context */}
      {item.reason && (
        <div style={{
          fontSize: 'var(--os-text-min)',
          color: 'var(--os-text-faint)',
        }}>
          reason: <span style={{ color: 'var(--os-text-dim)' }}>{item.reason}</span>
        </div>
      )}

      {/* Provenance — algorithm + source endpoint + timestamp */}
      <div style={{
        display: 'flex', gap: 14, flexWrap: 'wrap',
        fontSize: 'var(--os-text-min)',
        color: 'var(--os-text-faint)',
        marginTop: 2,
      }}>
        {item.algorithm && (
          <span>algorithm: <code style={{ color: 'var(--os-text-dim)' }}>{item.algorithm}</code></span>
        )}
        {item.source && (
          <span>source: <code style={{ color: 'var(--os-text-dim)' }}>{item.source}</code></span>
        )}
        {item.tsMs && (
          <span>ran at: <code style={{ color: 'var(--os-text-dim)' }}>{_fmtTs(item.tsMs)}</code></span>
        )}
      </div>
    </li>
  )
}

_ReceiptRow.propTypes = {
  item: PropTypes.object.isRequired,
}

export default function VerificationReceipt({ items = [], title = 'Verification receipt' }) {
  const headingId = useId()
  return (
    <section
      role="region"
      aria-labelledby={headingId}
      data-os-verification-receipt
      style={{
        display:       'flex',
        flexDirection: 'column',
        gap:           10,
        padding:       '14px 16px',
        background:    'var(--os-panel-soft)',
        border:        '1px solid var(--os-border)',
        borderRadius:  'var(--os-radius)',
        fontFamily:    _MONO,
      }}
    >
      <header style={{
        display:        'flex',
        alignItems:     'center',
        justifyContent: 'space-between',
        gap:            12,
      }}>
        <h3 id={headingId} style={{
          margin: 0,
          fontSize: 'var(--os-text-h3)',
          fontWeight: 700,
          color: 'var(--os-text)',
          letterSpacing: '0.04em',
        }}>{title}</h3>
        <span style={{
          fontSize: 'var(--os-text-min)',
          color: 'var(--os-text-faint)',
        }}>{items.length} check{items.length === 1 ? '' : 's'}</span>
      </header>

      {items.length === 0 ? (
        <div style={{
          padding: '12px 14px',
          color: 'var(--os-text-faint)',
          fontSize: 'var(--os-text-base)',
          textAlign: 'center',
          border: '1px dashed var(--os-border)',
          borderRadius: 'var(--os-radius)',
        }}>
          No verifications executed yet. This receipt is honest:
          it does not imply "OK" when nothing has been checked.
        </div>
      ) : (
        <ul role="list" style={{
          listStyle: 'none', padding: 0, margin: 0,
          display: 'flex', flexDirection: 'column', gap: 8,
        }}>
          {items.map(it => <_ReceiptRow key={it.id} item={it}/>)}
        </ul>
      )}
    </section>
  )
}

VerificationReceipt.propTypes = {
  title: PropTypes.string,
  items: PropTypes.arrayOf(PropTypes.shape({
    id:        PropTypes.string.isRequired,
    claim:     PropTypes.string.isRequired,
    status:    PropTypes.oneOf(['ok', 'mismatch', 'skipped', 'pending', 'error']),
    protocol:  PropTypes.string,
    computed:  PropTypes.string,
    source:    PropTypes.string,
    algorithm: PropTypes.string,
    reason:    PropTypes.string,
    tsMs:      PropTypes.number,
  })),
}
