import { useState, useRef } from 'react'
import { FONTS } from '../shared/design/tokens'

const S = {
  wrapper: {
    position: 'relative',
    display: 'inline-flex',
    alignItems: 'center',
    gap: 3,
    cursor: 'help',
  },
  dot: {
    width: 5,
    height: 5,
    borderRadius: '50%',
    background: 'rgba(74,158,255,0.5)',
    flexShrink: 0,
  },
  tooltip: {
    position: 'absolute',
    bottom: 'calc(100% + 8px)',
    left: '50%',
    transform: 'translateX(-50%)',
    zIndex: 9999,
    background: 'rgba(4,8,16,0.97)',
    border: '1px solid rgba(74,158,255,0.3)',
    borderRadius: 4,
    padding: '8px 10px',
    minWidth: 200,
    maxWidth: 320,
    backdropFilter: 'blur(8px)',
    boxShadow: '0 4px 24px rgba(0,0,0,0.6)',
    pointerEvents: 'none',
    animation: 'vapi-enter 0.12s ease-out',
  },
  row: {
    display: 'flex',
    gap: 8,
    marginBottom: 4,
    fontFamily: FONTS.mono,
    fontSize: 10,
  },
  label: { color: 'rgba(74,158,255,0.6)', flexShrink: 0, width: 60 },
  value: { color: '#d4e8ff', wordBreak: 'break-all' },
  arrow: {
    position: 'absolute',
    top: '100%',
    left: '50%',
    transform: 'translateX(-50%)',
    width: 0,
    height: 0,
    borderLeft: '5px solid transparent',
    borderRight: '5px solid transparent',
    borderTop: '5px solid rgba(74,158,255,0.3)',
  },
}

export function ProvenanceTooltip({ children, agentId, phase, invariant, commitment }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  return (
    <span
      ref={ref}
      style={S.wrapper}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      {children}
      <span style={S.dot} />
      {open && (
        <span style={S.tooltip}>
          {agentId   && <span style={S.row}><span style={S.label}>agent</span>   <span style={S.value}>{agentId}</span></span>}
          {phase     && <span style={S.row}><span style={S.label}>phase</span>   <span style={S.value}>Phase {phase}</span></span>}
          {invariant && <span style={S.row}><span style={S.label}>invariant</span><span style={S.value}>{invariant}</span></span>}
          {commitment && <span style={S.row}><span style={S.label}>on-chain</span><span style={S.value}>{commitment.slice(0, 16)}…</span></span>}
          <span style={S.arrow} />
        </span>
      )}
    </span>
  )
}
