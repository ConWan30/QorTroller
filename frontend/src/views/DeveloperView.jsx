import { useEffect, useRef, useMemo } from 'react'
import * as d3 from 'd3'
import {
  useTournamentBlockerSummary,
  usePerPairGapProjection,
  useTournamentPreflight,
  usePerPairGapStatus,
} from '../api/bridgeApi'
import { HeartbeatWaveform } from '../heartbeat/HeartbeatWaveform'
import { ProvenanceTag } from '../provenance/ProvenanceTag'
import { FONTS, DEVELOPER } from '../shared/design/tokens'

// D3 force-directed blocker graph
function BlockerGraph({ blockers = [] }) {
  const svgRef = useRef(null)

  const { nodes, links } = useMemo(() => {
    const center = { id: 'isFullyEligible()', type: 'gate' }
    const nodes = [center]
    const links = []

    blockers.forEach((b, i) => {
      const nodeId = `${b.source}_${b.key}`
      nodes.push({ id: nodeId, label: b.key, severity: b.severity, detail: b.detail, type: 'blocker' })
      links.push({
        source: 'isFullyEligible()',
        target: nodeId,
        weight: b.severity === 'P0' ? 1.0 : 0.5,
        severity: b.severity,
      })
    })

    // Add known static nodes for context
    const contextNodes = [
      { id: 'TournamentPreflight', type: 'context', label: 'Preflight' },
      { id: 'PerPairGate', type: 'context', label: 'Per-Pair P0' },
      { id: 'L4Calibration', type: 'context', label: 'L4 Thresh' },
    ]
    contextNodes.forEach((n) => {
      nodes.push(n)
      links.push({ source: 'isFullyEligible()', target: n.id, weight: 0.3, severity: 'INFO' })
    })

    return { nodes, links }
  }, [blockers])

  useEffect(() => {
    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()

    const W = svgRef.current.clientWidth  || 420
    const H = svgRef.current.clientHeight || 300

    const color = d3.scaleOrdinal()
      .domain(['P0', 'P1', 'INFO'])
      .range([DEVELOPER.red || '#ff3b5c', DEVELOPER.amber || '#ffaa44', 'rgba(200,216,232,0.2)'])

    const sim = d3.forceSimulation(nodes)
      .force('link',   d3.forceLink(links).id((d) => d.id).distance((d) => d.weight < 0.5 ? 90 : 70))
      .force('charge', d3.forceManyBody().strength(-220))
      .force('center', d3.forceCenter(W / 2, H / 2))
      .force('collide', d3.forceCollide(28))

    const g = svg.append('g')

    // Defs: arrow markers
    const defs = svg.append('defs')
    ;['P0','P1','INFO'].forEach((sev) => {
      defs.append('marker')
        .attr('id', `arrow-${sev}`)
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 22)
        .attr('markerWidth', 4)
        .attr('markerHeight', 4)
        .attr('orient', 'auto')
        .append('path')
        .attr('d', 'M0,-5L10,0L0,5')
        .attr('fill', color(sev))
    })

    const link = g.selectAll('.link')
      .data(links)
      .join('line')
      .attr('class', 'link')
      .attr('stroke', (d) => color(d.severity))
      .attr('stroke-width', (d) => d.weight * 1.5)
      .attr('stroke-opacity', 0.55)
      .attr('marker-end', (d) => `url(#arrow-${d.severity})`)

    const node = g.selectAll('.node')
      .data(nodes)
      .join('g')
      .attr('class', 'node')
      .call(d3.drag()
        .on('start', (ev, d) => { if (!ev.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y })
        .on('drag',  (ev, d) => { d.fx = ev.x; d.fy = ev.y })
        .on('end',   (ev, d) => { if (!ev.active) sim.alphaTarget(0); d.fx = null; d.fy = null })
      )

    // Gate node: hexagon
    node.filter((d) => d.type === 'gate').append('polygon')
      .attr('points', hexPoints(20))
      .attr('fill',   'rgba(255,107,0,0.12)')
      .attr('stroke', DEVELOPER.orange || '#ff6b00')
      .attr('stroke-width', 1.5)

    // Blocker nodes: circle
    node.filter((d) => d.type === 'blocker').append('circle')
      .attr('r', 16)
      .attr('fill', (d) => `${color(d.severity)}18`)
      .attr('stroke', (d) => color(d.severity))
      .attr('stroke-width', 1.5)

    // Context nodes: small square
    node.filter((d) => d.type === 'context').append('rect')
      .attr('x', -10).attr('y', -10).attr('width', 20).attr('height', 20)
      .attr('fill', 'rgba(200,216,232,0.04)')
      .attr('stroke', 'rgba(200,216,232,0.2)')
      .attr('stroke-width', 0.8)
      .attr('rx', 2)

    // Labels
    node.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', (d) => d.type === 'gate' ? 4 : (d.type === 'blocker' ? 4 : 4))
      .style('font-family', FONTS.mono)
      .style('font-size', (d) => d.type === 'gate' ? '8px' : '7px')
      .style('fill', (d) => d.type === 'gate' ? (DEVELOPER.orange || '#ff6b00') : (DEVELOPER.t1 || '#ffe8d4'))
      .style('pointer-events', 'none')
      .text((d) => d.label || d.id)

    sim.on('tick', () => {
      link
        .attr('x1', (d) => d.source.x)
        .attr('y1', (d) => d.source.y)
        .attr('x2', (d) => d.target.x)
        .attr('y2', (d) => d.target.y)
      node.attr('transform', (d) => `translate(${d.x},${d.y})`)
    })

    return () => sim.stop()
  }, [nodes, links])

  return (
    <svg
      ref={svgRef}
      style={{ width: '100%', height: '100%' }}
    />
  )
}

function hexPoints(r) {
  return Array.from({ length: 6 }, (_, i) => {
    const a = (Math.PI / 3) * i - Math.PI / 6
    return `${r * Math.cos(a)},${r * Math.sin(a)}`
  }).join(' ')
}

// TGE timeline bar chart
function TGETimeline({ projections = [] }) {
  const W = 100
  const maxDays = 365

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
      {projections.map((p) => {
        const days = p.days_to_1_0
        const pct  = days ? Math.min(1, days / maxDays) : null
        const color = p.trend === 'IMPROVING' ? '#ff6b00' : p.trend === 'WORSENING' ? '#ff3b5c' : 'rgba(200,216,232,0.25)'
        return (
          <div key={p.pair_key} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontFamily: FONTS.mono, fontSize: 8, color: 'rgba(200,216,232,0.5)', width: 40 }}>{p.pair_key}</span>
            <div style={{ flex: 1, height: 4, background: 'rgba(255,255,255,0.05)', borderRadius: 2, overflow: 'hidden' }}>
              {pct !== null
                ? <div style={{ width: `${(1 - pct) * 100}%`, height: '100%', background: color, borderRadius: 2, transition: 'width 0.5s' }} />
                : <div style={{ width: '100%', height: '100%', background: 'rgba(255,59,92,0.3)', borderRadius: 2 }} />
              }
            </div>
            <span style={{ fontFamily: FONTS.mono, fontSize: 7, color, width: 36, textAlign: 'right' }}>
              {days ? `${days}d` : p.trend}
            </span>
          </div>
        )
      })}
    </div>
  )
}

// PITL layer drill-down chip
function PITLChip({ code, label, type, active }) {
  const bg    = type === 'hard' ? 'rgba(255,59,92,0.12)' : 'rgba(255,170,68,0.08)'
  const border = type === 'hard' ? 'rgba(255,59,92,0.4)' : 'rgba(255,170,68,0.25)'
  const color  = type === 'hard' ? '#ff3b5c' : '#ffaa44'
  return (
    <div style={{
      padding: '3px 7px',
      background: active ? bg : 'rgba(255,255,255,0.03)',
      border: `1px solid ${active ? border : 'rgba(255,255,255,0.06)'}`,
      borderRadius: 3,
      fontFamily: FONTS.mono,
      fontSize: 8,
      color: active ? color : 'rgba(200,216,232,0.3)',
      display: 'inline-flex',
      gap: 4,
      alignItems: 'center',
    }}>
      <span style={{ opacity: 0.6 }}>{code}</span>
      <span>{label}</span>
    </div>
  )
}

export function DeveloperView() {
  const { data: blockerSummary }   = useTournamentBlockerSummary()
  const { data: gapProjection }    = usePerPairGapProjection()
  const { data: preflight }        = useTournamentPreflight()
  const { data: pairGap }          = usePerPairGapStatus()

  const blockers    = blockerSummary?.blockers ?? []
  const projections = gapProjection?.projections ?? []
  const overallPass = preflight?.overall_pass ?? false

  return (
    <div style={{ display: 'flex', height: '100%', background: DEVELOPER.bg }}>

      {/* Left: D3 blocker force graph */}
      <div style={{
        flex:         '0 0 46%',
        borderRight:  '1px solid rgba(255,107,0,0.08)',
        display:      'flex',
        flexDirection:'column',
      }}>
        <SectionHeader color={DEVELOPER.orange} label="TOURNAMENT BLOCKER GRAPH" />
        <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
          <BlockerGraph blockers={blockers} />
        </div>
        <div style={{
          padding:    '6px 10px',
          borderTop:  '1px solid rgba(255,107,0,0.06)',
          fontFamily: FONTS.mono,
          fontSize:   8,
          color:      overallPass ? '#00ff88' : '#ff3b5c',
          display:    'flex',
          alignItems: 'center',
          gap:        6,
        }}>
          <span style={{ fontSize: 6 }}>●</span>
          isFullyEligible() = {overallPass ? 'TRUE' : 'FALSE'}
          <span style={{ marginLeft: 'auto', color: 'rgba(200,216,232,0.3)' }}>
            {blockers.length} active blockers
          </span>
        </div>
      </div>

      {/* Right: TGE timeline + PITL + heartbeat */}
      <div style={{
        flex:          '1',
        display:       'flex',
        flexDirection: 'column',
        overflow:      'hidden',
      }}>

        {/* TGE timeline */}
        <div style={{ flex: '0 0 auto', padding: '8px 12px', borderBottom: '1px solid rgba(255,107,0,0.06)' }}>
          <SectionHeader color={DEVELOPER.orange} label="TGE TIMELINE PROJECTION" small />
          <div style={{ marginTop: 6 }}>
            <TGETimeline projections={projections} />
          </div>
          {gapProjection?.any_feasible === false && (
            <div style={{ marginTop: 5, fontFamily: FONTS.mono, fontSize: 8, color: '#ff3b5c' }}>
              ⚠ No feasible TGE date — WORSENING/STABLE pairs present
            </div>
          )}
        </div>

        {/* PITL layer drill-down */}
        <div style={{ flex: '0 0 auto', padding: '8px 12px', borderBottom: '1px solid rgba(255,107,0,0.06)' }}>
          <SectionHeader color={DEVELOPER.orange} label="PITL NINE-LEVEL STACK" small />
          <div style={{ marginTop: 5, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            <PITLChip code="L0"   label="HID presence"       type="info"     active />
            <PITLChip code="L1"   label="chain integrity"    type="info"     active />
            <PITLChip code="0x28" label="DRIVER_INJECT"      type="hard"     active />
            <PITLChip code="0x29" label="WALLHACK"           type="hard"     active />
            <PITLChip code="0x2A" label="AIMBOT"             type="hard"     active />
            <PITLChip code="0x31" label="IMU_PRESS"          type="advisory" active={false} />
            <PITLChip code="0x32" label="STICK_IMU"         type="advisory" active={false} />
            <PITLChip code="0x30" label="BIO_ANOMALY"        type="advisory" active />
            <PITLChip code="0x2B" label="TEMPORAL_BOT"      type="advisory" active />
            <PITLChip code="0x33" label="GSR_ABSENT"         type="advisory" active={false} />
          </div>
        </div>

        {/* Per-pair distances */}
        <div style={{ flex: '0 0 auto', padding: '8px 12px', borderBottom: '1px solid rgba(255,107,0,0.06)' }}>
          <SectionHeader color={DEVELOPER.orange} label="PER-PAIR MAHALANOBIS" small />
          <div style={{ marginTop: 5, display: 'flex', flexDirection: 'column', gap: 4 }}>
            {(pairGap?.pairs ?? []).map((p) => (
              <div key={p.pair_key} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ fontFamily: FONTS.mono, fontSize: 8, color: 'rgba(200,216,232,0.4)', width: 36 }}>{p.pair_key}</span>
                <div style={{ flex: 1, height: 3, background: 'rgba(255,255,255,0.05)', borderRadius: 2 }}>
                  <div style={{
                    width: `${Math.min(100, (p.distance / 2.0) * 100)}%`,
                    height: '100%',
                    background: p.above_1_0 ? '#00ff88' : '#ff3b5c',
                    borderRadius: 2,
                    transition: 'width 0.4s',
                  }} />
                </div>
                <ProvenanceTag
                  value={p.distance}
                  agentId="PerPairGapLog"
                  phase={216}
                  invariant="target >1.0 for tournament gate"
                  style={{ fontFamily: FONTS.mono, fontSize: 9, color: p.above_1_0 ? '#00ff88' : '#ff3b5c' }}
                />
              </div>
            ))}
          </div>
        </div>

        {/* Heartbeat */}
        <div style={{ flex: '0 0 auto', padding: '8px 12px' }}>
          <div style={{ fontFamily: FONTS.mono, fontSize: 8, color: 'rgba(255,107,0,0.4)', marginBottom: 3, letterSpacing: '0.1em' }}>
            228-BYTE PoAC HEARTBEAT
          </div>
          <HeartbeatWaveform accent={DEVELOPER.orange} height={32} />
        </div>
      </div>
    </div>
  )
}

function SectionHeader({ color, label, small = false }) {
  return (
    <div style={{
      fontFamily:    FONTS.mono,
      fontSize:      small ? 7 : 8,
      color:         color ? `${color}80` : 'rgba(200,216,232,0.35)',
      letterSpacing: '0.12em',
      paddingBottom: small ? 0 : 6,
      borderBottom:  small ? 'none' : `1px solid ${color}18`,
      padding:       small ? '0' : '6px 12px',
    }}>
      {label}
    </div>
  )
}
