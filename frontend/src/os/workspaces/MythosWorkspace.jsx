/**
 * Evidence OS — Mythos Audit Fleet Workspace  (/os/mythos)
 *
 * 15-cell geometric grid: one cell per Mythos audit variant.
 * Reads from GET /operator/mythos-findings (noMock).
 *
 * Aesthetic: NASA Goddard mission-control matrix — dark void-black panels,
 * each cell a bordered telemetry tile. Active findings pulse amber.
 * CRITICAL findings blaze red. CLEAN cells hold steady chain-green.
 * Zero data: cells render IDLE in slate — honest about the cadence engine
 * not having run yet.
 */
import { useState, useMemo } from 'react'
import WorkspaceHeader from '../components/WorkspaceHeader'
import { useMythosFindings } from '../../api/bridgeApi'

// ── Variant registry ────────────────────────────────────────────────────────

const VARIANTS = [
  { id: 'frozen_drift',             label: 'Frozen Drift',           short: 'FROZEN',    domain: 'Protocol' },
  { id: 'stability_sweep',          label: 'Stability Sweep',        short: 'STABILITY', domain: 'Bridge'   },
  { id: 'operator_initiative_audit',label: 'OpInit Audit',           short: 'OPINIT',    domain: 'Agents'   },
  { id: 'crypto_drift',             label: 'Crypto Drift (VAPI)',     short: 'CRYPTO',    domain: 'Protocol' },
  { id: 'qortroller_crypto_drift',  label: 'Crypto Drift (QT)',      short: 'QT-CRYPTO', domain: 'Protocol' },
  { id: 'methodology_drift',        label: 'Methodology Drift',      short: 'METHOD',    domain: 'Process'  },
  { id: 'ceremony_drift',           label: 'Ceremony Drift',         short: 'CEREMONY',  domain: 'Crypto'   },
  { id: 'live_gameplay_audit',      label: 'Live Gameplay',          short: 'GAMEPLAY',  domain: 'Grind'    },
  { id: 'post_o3_ceremony_audit',   label: 'Post-O3 Ceremony',       short: 'POST-O3',   domain: 'Agents'   },
  { id: 'corpus_drift',             label: 'Corpus Drift',           short: 'CORPUS',    domain: 'Data'     },
  { id: 'claude_md_curation',       label: 'CLAUDE.md Curation',     short: 'CLAUDE-MD', domain: 'Process'  },
  { id: 'doc_number_consistency',   label: 'Doc Numbers',            short: 'DOCS',      domain: 'Process'  },
  { id: 'curator_graduation_audit', label: 'Curator Graduation',     short: 'CURATOR',   domain: 'Agents'   },
  { id: 'spending_log_drift',       label: 'Spending Log',           short: 'SPENDING',  domain: 'Finance'  },
  { id: 'frontend_brand_drift',     label: 'Frontend Brand',         short: 'BRAND',     domain: 'Frontend' },
]

// ── Color tokens ─────────────────────────────────────────────────────────────

const C = {
  void:    '#04060a',
  border:  'rgba(200,216,232,0.10)',
  t1:      '#c8d8e8',
  t2:      '#8a9ab0',
  t3:      '#4a5a6e',
  green:   '#5bd6a3',
  amber:   '#f0a868',
  red:     '#e05c5c',
  cyan:    '#52c8f0',
  idle:    '#3a4a58',
}

const DOMAIN_COLOR = {
  Protocol: C.green,
  Bridge:   C.cyan,
  Agents:   C.amber,
  Crypto:   '#a78bfa',
  Process:  C.t2,
  Grind:    C.green,
  Data:     C.cyan,
  Finance:  C.amber,
  Frontend: '#f472b6',
}

const SEV_COLOR = {
  CRITICAL: C.red,
  HIGH:     '#f97316',
  MEDIUM:   C.amber,
  LOW:      '#84cc16',
  INFO:     C.t2,
}

// ── Cell component ────────────────────────────────────────────────────────────

function VariantCell({ variant, findings, selected, onClick }) {
  const myFindings = findings.filter((f) => f.variant === variant.id)
  const openFindings = myFindings.filter((f) => !f.resolved)
  const worstSev = openFindings.reduce((acc, f) => {
    const order = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1, INFO: 0 }
    return (order[f.severity] ?? -1) > (order[acc] ?? -1) ? f.severity : acc
  }, null)

  const state = openFindings.length === 0 ? 'CLEAN'
    : worstSev === 'CRITICAL' ? 'CRITICAL'
    : worstSev === 'HIGH' ? 'HIGH' : 'WARN'

  const accentColor = state === 'CLEAN' ? C.green
    : state === 'CRITICAL' ? C.red
    : state === 'HIGH' ? '#f97316' : C.amber

  const domainColor = DOMAIN_COLOR[variant.domain] || C.t2
  const lastRun = myFindings[0]?.created_at
    ? new Date(myFindings[0].created_at * 1000).toISOString().slice(11, 19) + 'Z'
    : null

  return (
    <button
      onClick={onClick}
      aria-pressed={selected}
      aria-label={`${variant.label}: ${openFindings.length} open findings`}
      style={{
        all: 'unset',
        cursor: 'pointer',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        padding: '12px 14px',
        background: selected ? `${accentColor}12` : `${C.void}cc`,
        border: `1px solid ${selected ? accentColor + '80' : openFindings.length > 0 ? accentColor + '44' : C.border}`,
        borderRadius: 6,
        minHeight: 90,
        transition: 'border-color 0.2s, background 0.2s',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Pulse bar — top edge, only when open findings exist */}
      {openFindings.length > 0 && (
        <div style={{
          position: 'absolute', top: 0, left: 0, right: 0, height: 2,
          background: accentColor,
          animation: state === 'CRITICAL' ? 'mythos-pulse 0.8s ease-in-out infinite alternate'
                   : state === 'HIGH'     ? 'mythos-pulse 1.4s ease-in-out infinite alternate'
                   : 'mythos-pulse 2.5s ease-in-out infinite alternate',
          opacity: 0.85,
        }} />
      )}

      {/* Header row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 4 }}>
        <div style={{
          fontFamily: "'JetBrains Mono', monospace", fontSize: 9, fontWeight: 600,
          letterSpacing: '0.14em', textTransform: 'uppercase',
          color: domainColor, whiteSpace: 'nowrap',
        }}>
          {variant.short}
        </div>
        <div style={{
          fontFamily: "'JetBrains Mono', monospace", fontSize: 9,
          color: openFindings.length > 0 ? accentColor : C.green,
          fontWeight: 700, letterSpacing: '0.08em',
        }}>
          {openFindings.length > 0 ? `▲ ${openFindings.length}` : '●'}
        </div>
      </div>

      {/* Label */}
      <div style={{
        fontFamily: "'Syne', system-ui, sans-serif", fontSize: 12,
        fontWeight: 600, color: C.t1, lineHeight: 1.2, marginTop: 4,
      }}>
        {variant.label}
      </div>

      {/* Footer row */}
      <div style={{
        fontFamily: "'JetBrains Mono', monospace", fontSize: 9,
        color: C.t3, marginTop: 6, letterSpacing: '0.06em',
        display: 'flex', justifyContent: 'space-between',
      }}>
        <span style={{ color: domainColor + '80' }}>{variant.domain}</span>
        {lastRun ? <span>{lastRun}</span> : <span style={{ color: C.idle }}>NO RUN</span>}
      </div>
    </button>
  )
}

// ── Finding row ───────────────────────────────────────────────────────────────

function FindingRow({ f }) {
  const ts = f.created_at
    ? new Date(f.created_at * 1000).toISOString().replace('T', ' ').slice(0, 19) + 'Z'
    : '—'

  return (
    <div style={{
      display: 'grid', gridTemplateColumns: '68px 64px 1fr 120px',
      gap: 10, alignItems: 'start',
      padding: '8px 0', borderBottom: `1px solid ${C.border}`,
    }}>
      <code style={{
        fontFamily: "'JetBrains Mono', monospace", fontSize: 10, fontWeight: 700,
        color: SEV_COLOR[f.severity] ?? C.t2,
        letterSpacing: '0.06em',
      }}>{f.severity}</code>
      <code style={{
        fontFamily: "'JetBrains Mono', monospace", fontSize: 10,
        color: f.resolved ? C.green : C.amber,
      }}>{f.resolved ? 'RESOLVED' : 'OPEN'}</code>
      <div>
        <div style={{
          fontFamily: "'Syne', system-ui, sans-serif", fontSize: 12,
          fontWeight: 600, color: C.t1, marginBottom: 2,
        }}>{f.title || f.finding_id}</div>
        {f.description && (
          <div style={{
            fontFamily: "'JetBrains Mono', monospace", fontSize: 10,
            color: C.t2, lineHeight: 1.5, maxWidth: 560,
          }}>{f.description}</div>
        )}
      </div>
      <code style={{
        fontFamily: "'JetBrains Mono', monospace", fontSize: 9,
        color: C.t3, textAlign: 'right',
      }}>{ts}</code>
    </div>
  )
}

// ── Main workspace ────────────────────────────────────────────────────────────

export default function MythosWorkspace() {
  const [selected, setSelected] = useState(null)
  const { data, isLoading, isError } = useMythosFindings({ limit: 500 })

  const findings = data?.findings ?? []
  const cadence  = data?.cadence  ?? {}

  // Counts for header readouts
  const openCount   = findings.filter((f) => !f.resolved).length
  const critCount   = findings.filter((f) => !f.resolved && f.severity === 'CRITICAL').length

  // Detail panel findings for selected variant
  const detailFindings = useMemo(
    () => selected ? findings.filter((f) => f.variant === selected) : [],
    [selected, findings],
  )
  const selectedVariant = VARIANTS.find((v) => v.id === selected)

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', flex: 1,
      background: C.void, color: C.t1, minHeight: 0,
      fontFamily: "'JetBrains Mono', monospace",
    }}>
      <style>{`
        @keyframes mythos-pulse {
          from { opacity: 0.4; }
          to   { opacity: 1.0; }
        }
      `}</style>

      {/* Workspace header */}
      <WorkspaceHeader
        title="Mythos Audit Fleet"
        description="15-variant self-audit matrix. Each cell is a live telemetry feed from the protocol's own integrity engine."
        right={
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            {isLoading && (
              <code style={{ fontSize: 10, color: C.t3 }}>loading…</code>
            )}
            {isError && (
              <code style={{ fontSize: 10, color: C.red }}>BRIDGE UNREACHABLE</code>
            )}
            {!isLoading && !isError && (
              <>
                <code style={{ fontSize: 11, color: critCount > 0 ? C.red : C.t3 }}>
                  {critCount > 0 ? `▲ ${critCount} CRITICAL` : '● CRITICAL 0'}
                </code>
                <code style={{ fontSize: 11, color: openCount > 0 ? C.amber : C.green }}>
                  {openCount} OPEN
                </code>
              </>
            )}
          </div>
        }
      />

      {/* Body: grid + optional detail panel */}
      <div style={{ flex: 1, display: 'flex', minHeight: 0, overflow: 'hidden' }}>

        {/* Left: 5×3 grid */}
        <div style={{
          flex: selected ? '0 0 55%' : '1 1 100%',
          padding: '20px 24px',
          overflowY: 'auto',
          transition: 'flex 0.2s',
        }}>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(5, 1fr)',
            gap: 10,
          }}>
            {VARIANTS.map((v) => (
              <VariantCell
                key={v.id}
                variant={v}
                findings={findings}
                selected={selected === v.id}
                onClick={() => setSelected(selected === v.id ? null : v.id)}
              />
            ))}
          </div>

          {/* Cadence footer */}
          {Object.keys(cadence.variants ?? {}).length > 0 && (
            <div style={{
              marginTop: 24, padding: '12px 0',
              borderTop: `1px solid ${C.border}`,
              display: 'flex', gap: 24, flexWrap: 'wrap',
            }}>
              <code style={{ fontSize: 9, color: C.t3, letterSpacing: '0.08em' }}>
                CADENCE ENGINE · VARIANTS OBSERVED: {Object.keys(cadence.variants ?? {}).length}
                · TOTAL RUNS: {cadence.total_runs ?? '—'}
                · TOTAL FINDINGS: {cadence.total_findings ?? '—'}
              </code>
            </div>
          )}
          {!isLoading && !isError && findings.length === 0 && (
            <div style={{
              marginTop: 32, textAlign: 'center',
              fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: C.t3,
              letterSpacing: '0.08em',
            }}>
              NO FINDINGS IN LOG — CADENCE ENGINE HAS NOT YET RUN OR ALL VARIANTS CLEAN
            </div>
          )}
        </div>

        {/* Right: detail panel */}
        {selected && (
          <div style={{
            flex: '0 0 45%',
            borderLeft: `1px solid ${C.border}`,
            display: 'flex', flexDirection: 'column', minHeight: 0,
          }}>
            {/* Panel header */}
            <div style={{
              padding: '16px 20px', borderBottom: `1px solid ${C.border}`,
              display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
            }}>
              <div>
                <div style={{
                  fontFamily: "'Syne', system-ui, sans-serif", fontSize: 15,
                  fontWeight: 700, color: C.t1,
                }}>{selectedVariant?.label}</div>
                <code style={{ fontSize: 10, color: C.t3 }}>
                  {selectedVariant?.domain} · {detailFindings.filter((f) => !f.resolved).length} open
                  · {detailFindings.length} total
                </code>
              </div>
              <button
                onClick={() => setSelected(null)}
                aria-label="Close detail panel"
                style={{
                  all: 'unset', cursor: 'pointer',
                  fontFamily: "'JetBrains Mono', monospace", fontSize: 11,
                  color: C.t3, letterSpacing: '0.06em',
                }}
              >✕ CLOSE</button>
            </div>

            {/* Finding rows */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '8px 20px' }}>
              {detailFindings.length === 0 ? (
                <div style={{
                  padding: '32px 0', textAlign: 'center',
                  fontSize: 11, color: C.t3, letterSpacing: '0.08em',
                }}>
                  NO FINDINGS FOR THIS VARIANT
                </div>
              ) : (
                detailFindings.map((f) => <FindingRow key={f.id ?? f.finding_id} f={f} />)
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
