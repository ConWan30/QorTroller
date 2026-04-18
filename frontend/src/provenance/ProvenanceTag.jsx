import { ProvenanceTooltip } from './ProvenanceTooltip'

// Wrap any numeric value to attach provenance metadata shown on hover
// Usage: <ProvenanceTag value={1.177} unit="ratio" agentId="SeparationRatioMonitorAgent" phase={129} />
export function ProvenanceTag({ value, unit, agentId, phase, invariant, commitment, format, style }) {
  const display = format ? format(value) : (typeof value === 'number' ? value.toFixed(3) : value)
  return (
    <ProvenanceTooltip agentId={agentId} phase={phase} invariant={invariant} commitment={commitment}>
      <span style={style}>{display}{unit ? <span style={{ opacity: 0.5, fontSize: '0.8em', marginLeft: 2 }}>{unit}</span> : null}</span>
    </ProvenanceTooltip>
  )
}
