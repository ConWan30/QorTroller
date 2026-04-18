import { Suspense, useRef, useMemo } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { Environment } from '@react-three/drei'
import * as THREE from 'three'
import {
  useInvariantGateStatus,
  useFleetCoherenceStatus,
  useTournamentPreflight,
} from '../api/bridgeApi'
import { useHeartbeatStore } from '../heartbeat/useHeartbeat'
import { HeartbeatWaveform } from '../heartbeat/HeartbeatWaveform'
import { ProvenanceTag } from '../provenance/ProvenanceTag'
import { FONTS, MANUFACTURER } from '../shared/design/tokens'

// Fibonacci sphere: place N points evenly on sphere surface
function fibonacciSphere(n, r) {
  const pts = []
  for (let i = 0; i < n; i++) {
    const phi   = Math.acos(-1 + (2 * i) / n)
    const theta = Math.sqrt(n * Math.PI) * phi
    pts.push(new THREE.Vector3(
      r * Math.cos(theta) * Math.sin(phi),
      r * Math.sin(theta) * Math.sin(phi),
      r * Math.cos(phi),
    ))
  }
  return pts
}

// 38-leaf Merkle sphere
function MerkleSphere({ agentCount = 38, magnitude = 0.5, onChain = false }) {
  const groupRef  = useRef()
  const meshRefs  = useRef([])

  // 38 leaf positions on sphere
  const positions = useMemo(() => fibonacciSphere(agentCount, 1.1), [agentCount])

  // Color by leaf index: first 37 = fleet agents, leaf 38 = virtual allowlist
  function leafColor(i) {
    if (i === agentCount - 1) return new THREE.Color('#ffd700')  // virtual allowlist leaf: gold
    if (i < 10)  return new THREE.Color(MANUFACTURER.blue)
    if (i < 20)  return new THREE.Color('#6ae0ff')
    if (i < 30)  return new THREE.Color('#00d4ff')
    return new THREE.Color('#4a9eff')
  }

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    if (groupRef.current) {
      groupRef.current.rotation.y = t * 0.08
      groupRef.current.rotation.x = Math.sin(t * 0.05) * 0.12
    }
    // Pulse each leaf with a phase offset
    meshRefs.current.forEach((m, i) => {
      if (!m) return
      const phase = (i / agentCount) * Math.PI * 2
      const s = 0.7 + 0.3 * (magnitude + Math.sin(t * 1.2 + phase) * 0.15)
      m.scale.setScalar(s)
    })
  })

  // Build connecting lines: each leaf → center
  const lineGeo = useMemo(() => {
    const pts = []
    positions.forEach((p) => { pts.push(new THREE.Vector3(0, 0, 0)); pts.push(p) })
    const geo = new THREE.BufferGeometry().setFromPoints(pts)
    return geo
  }, [positions])

  return (
    <group ref={groupRef}>
      {/* Central Merkle root sphere */}
      <mesh>
        <sphereGeometry args={[0.18, 16, 16]} />
        <meshStandardMaterial
          color={onChain ? '#00ff88' : MANUFACTURER.blue}
          emissive={onChain ? '#00ff88' : MANUFACTURER.blue}
          emissiveIntensity={0.6}
          roughness={0.2}
        />
      </mesh>

      {/* Connection lines */}
      <lineSegments geometry={lineGeo}>
        <lineBasicMaterial color={MANUFACTURER.blue} transparent opacity={0.12} />
      </lineSegments>

      {/* Leaf nodes */}
      {positions.map((pos, i) => (
        <mesh
          key={i}
          position={pos}
          ref={(el) => (meshRefs.current[i] = el)}
        >
          <octahedronGeometry args={[0.045, 0]} />
          <meshStandardMaterial
            color={leafColor(i)}
            emissive={leafColor(i)}
            emissiveIntensity={i === agentCount - 1 ? 0.8 : 0.4}
            roughness={0.3}
          />
        </mesh>
      ))}

      {/* Outer cage wireframe */}
      <mesh>
        <icosahedronGeometry args={[1.28, 1]} />
        <meshBasicMaterial color={MANUFACTURER.blue} transparent opacity={0.04} wireframe />
      </mesh>
    </group>
  )
}

// Invariant seal: each INV-NNN as a small badge
function InvariantSeal({ id, pass, label }) {
  const color = pass ? '#00ff88' : '#ff3b5c'
  return (
    <div style={{
      display:     'inline-flex',
      alignItems:  'center',
      gap:         4,
      padding:     '2px 6px',
      background:  `${color}0a`,
      border:      `1px solid ${color}30`,
      borderRadius: 3,
      fontFamily:  FONTS.mono,
      fontSize:    7.5,
      color,
    }}>
      <span style={{ fontSize: 6 }}>{pass ? '●' : '○'}</span>
      {id}
    </div>
  )
}

// Hardware cert tier badge
function CertTier({ tier, label, description }) {
  const colors = {
    ATTESTED:  { bg: 'rgba(74,158,255,0.08)',  border: 'rgba(74,158,255,0.3)',  text: '#4a9eff' },
    STANDARD:  { bg: 'rgba(200,216,232,0.05)', border: 'rgba(200,216,232,0.15)', text: 'rgba(200,216,232,0.6)' },
    UNCERTIFIED:{ bg: 'rgba(255,59,92,0.06)',  border: 'rgba(255,59,92,0.2)',   text: 'rgba(255,59,92,0.6)' },
  }
  const c = colors[tier] || colors.STANDARD
  return (
    <div style={{
      padding:      '5px 8px',
      background:   c.bg,
      border:       `1px solid ${c.border}`,
      borderRadius: 4,
      display:      'flex',
      flexDirection:'column',
      gap:          2,
    }}>
      <span style={{ fontFamily: FONTS.mono, fontSize: 8, color: c.text, fontWeight: 600 }}>{label}</span>
      <span style={{ fontFamily: FONTS.mono, fontSize: 7, color: 'rgba(200,216,232,0.35)' }}>{description}</span>
    </div>
  )
}

export function ManufacturerView() {
  const magnitude  = useHeartbeatStore((s) => s.magnitude)
  const merkleRoot = useHeartbeatStore((s) => s.merkleRoot)
  const onChain    = useHeartbeatStore((s) => s.onChainConfirmed)
  const agentCount = useHeartbeatStore((s) => s.agentCount)

  const { data: invariants }  = useInvariantGateStatus()
  const { data: coherence }   = useFleetCoherenceStatus()
  const { data: preflight }   = useTournamentPreflight()

  const totalChecked   = invariants?.total_checked   ?? 16
  const failureCount   = invariants?.failure_count   ?? 0
  const gatePass       = invariants?.gate_pass       ?? true
  const contradictions = coherence?.active_contradictions ?? 0
  const orphans        = coherence?.active_orphans ?? 0

  // Build INV-001..INV-016 seals
  const invSeals = useMemo(() => {
    return Array.from({ length: totalChecked }, (_, i) => ({
      id:   `INV-${String(i + 1).padStart(3, '0')}`,
      pass: failureCount === 0 || !(invariants?.last_failures ?? []).includes(`INV-${String(i + 1).padStart(3, '0')}`),
    }))
  }, [totalChecked, failureCount, invariants])

  return (
    <div style={{ display: 'flex', height: '100%', background: MANUFACTURER.bg }}>

      {/* Left: 38-leaf Merkle sphere canvas */}
      <div style={{
        flex:         '0 0 44%',
        borderRight:  '1px solid rgba(74,158,255,0.08)',
        display:      'flex',
        flexDirection:'column',
      }}>
        <div style={{
          flex:     '1',
          position: 'relative',
          overflow: 'hidden',
        }}>
          <div style={{
            position:   'absolute',
            top: 8, left: 10,
            zIndex:     2,
            fontFamily: FONTS.mono,
            fontSize:   8,
            color:      'rgba(74,158,255,0.45)',
            letterSpacing: '0.1em',
          }}>
            PROTOCOL COHERENCE REGISTRY
          </div>
          <div style={{
            position:   'absolute',
            top: 22, left: 10,
            zIndex:     2,
            fontFamily: FONTS.mono,
            fontSize:   8,
            color:      onChain ? '#00ff88' : '#ff9500',
          }}>
            {onChain ? '● ON-CHAIN ANCHORED' : '○ PENDING ANCHOR'}
          </div>

          <Canvas camera={{ position: [0, 0, 3.2], fov: 48 }} style={{ background: 'transparent' }}>
            <Suspense fallback={null}>
              <Environment preset="night" />
              <ambientLight intensity={0.3} />
              <pointLight position={[3, 2, 3]} intensity={0.7} color={MANUFACTURER.blue} />
              <pointLight position={[-2, -2, -2]} intensity={0.3} color={MANUFACTURER.gold} />
              <MerkleSphere agentCount={agentCount} magnitude={magnitude} onChain={onChain} />
            </Suspense>
          </Canvas>

          {/* Merkle root overlay */}
          {merkleRoot && (
            <div style={{
              position:   'absolute',
              bottom: 8, left: 0, right: 0,
              textAlign:  'center',
              fontFamily: FONTS.mono,
              fontSize:   8,
              color:      'rgba(74,158,255,0.35)',
              letterSpacing: '0.06em',
            }}>
              {merkleRoot}
            </div>
          )}
        </div>

        {/* Agent fleet stats */}
        <div style={{
          padding:   '8px 10px',
          borderTop: '1px solid rgba(74,158,255,0.06)',
          display:   'flex',
          gap:       16,
        }}>
          <FleetStat label="AGENTS" value={agentCount} color={MANUFACTURER.blue} />
          <FleetStat label="CONTRAD" value={contradictions} color={contradictions > 0 ? '#ff3b5c' : '#00ff88'} />
          <FleetStat label="ORPHANS" value={orphans} color={orphans > 0 ? '#ffaa44' : '#00ff88'} />
          <FleetStat label="LEAVES" value={agentCount} note="+1 virtual" color={MANUFACTURER.gold} />
        </div>

        {/* Heartbeat */}
        <div style={{ padding: '4px 10px 8px' }}>
          <HeartbeatWaveform accent={MANUFACTURER.blue} height={28} />
        </div>
      </div>

      {/* Right: invariant seals + cert tiers + coherence entries */}
      <div style={{
        flex:          '1',
        display:       'flex',
        flexDirection: 'column',
        overflow:      'hidden',
      }}>

        {/* Invariant seals */}
        <div style={{ flex: '0 0 auto', padding: '8px 12px', borderBottom: '1px solid rgba(74,158,255,0.06)' }}>
          <div style={{ fontFamily: FONTS.mono, fontSize: 7.5, color: 'rgba(74,158,255,0.45)', letterSpacing: '0.12em', marginBottom: 6 }}>
            PV-CI PROTOCOL INVARIANT GATE — {gatePass ? (
              <span style={{ color: '#00ff88' }}>PASS ({totalChecked}/{totalChecked})</span>
            ) : (
              <span style={{ color: '#ff3b5c' }}>FAIL ({totalChecked - failureCount}/{totalChecked})</span>
            )}
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {invSeals.map((s) => (
              <InvariantSeal key={s.id} id={s.id} pass={s.pass} />
            ))}
          </div>
        </div>

        {/* Hardware cert tiers */}
        <div style={{ flex: '0 0 auto', padding: '8px 12px', borderBottom: '1px solid rgba(74,158,255,0.06)' }}>
          <div style={{ fontFamily: FONTS.mono, fontSize: 7.5, color: 'rgba(74,158,255,0.45)', letterSpacing: '0.12em', marginBottom: 6 }}>
            HARDWARE CERTIFICATION TIERS
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <CertTier tier="ATTESTED"   label="LEVEL 2 — ATTESTED"   description="DualShock Edge CFI-ZCP1 · L0–L6 · 1002 Hz · BLE" />
            <CertTier tier="STANDARD"   label="LEVEL 1 — STANDARD"   description="Xbox / Switch · L0–L5 · 125–250 Hz · USB" />
            <CertTier tier="UNCERTIFIED" label="LEVEL 0 — UNCERTIFIED" description="Unregistered device · no biometric eligibility" />
          </div>
        </div>

        {/* Fleet coherence entries */}
        <div style={{ flex: '1', padding: '8px 12px', overflowY: 'auto' }}>
          <div style={{ fontFamily: FONTS.mono, fontSize: 7.5, color: 'rgba(74,158,255,0.45)', letterSpacing: '0.12em', marginBottom: 6 }}>
            FLEET SIGNAL COHERENCE
          </div>
          {(coherence?.entries ?? []).length === 0 ? (
            <div style={{ fontFamily: FONTS.mono, fontSize: 8, color: '#00ff88' }}>ALL CLEAR</div>
          ) : (
            (coherence?.entries ?? []).map((e) => (
              <div key={e.coherence_id} style={{
                marginBottom: 5,
                padding:      '4px 7px',
                background:   e.severity === 'HIGH' ? 'rgba(255,59,92,0.06)' : 'rgba(255,170,68,0.05)',
                border:       `1px solid ${e.severity === 'HIGH' ? 'rgba(255,59,92,0.25)' : 'rgba(255,170,68,0.2)'}`,
                borderRadius: 3,
              }}>
                <div style={{ fontFamily: FONTS.mono, fontSize: 8, color: e.severity === 'HIGH' ? '#ff3b5c' : '#ffaa44' }}>
                  {e.type} · {e.severity}
                </div>
                <div style={{ fontFamily: FONTS.mono, fontSize: 7, color: 'rgba(200,216,232,0.45)', marginTop: 2 }}>
                  {e.rule_name}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Separation ratio summary */}
        <div style={{ flex: '0 0 auto', padding: '6px 12px', borderTop: '1px solid rgba(74,158,255,0.06)' }}>
          <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
            <div>
              <div style={{ fontFamily: FONTS.mono, fontSize: 7, color: 'rgba(74,158,255,0.4)' }}>tremor_resting</div>
              <ProvenanceTag
                value={1.177}
                agentId="SeparationRatioMonitorAgent"
                phase={129}
                invariant="all_pairs_p0_ok=False (P1vP3=0.032)"
                style={{ fontFamily: FONTS.mono, fontSize: 13, color: '#ffaa44' }}
              />
            </div>
            <div>
              <div style={{ fontFamily: FONTS.mono, fontSize: 7, color: 'rgba(74,158,255,0.4)' }}>touchpad_corners</div>
              <ProvenanceTag
                value={0.728}
                agentId="SeparationRatioMonitorAgent"
                phase={143}
                invariant="N=35; target >1.0 TOURNAMENT BLOCKER"
                style={{ fontFamily: FONTS.mono, fontSize: 13, color: '#ff3b5c' }}
              />
            </div>
            <div style={{ marginLeft: 'auto' }}>
              <div style={{ fontFamily: FONTS.mono, fontSize: 7, color: 'rgba(74,158,255,0.4)' }}>TGE gate</div>
              <div style={{ fontFamily: FONTS.mono, fontSize: 9, color: '#ff3b5c' }}>BLOCKED</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function FleetStat({ label, value, color, note }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1 }}>
      <span style={{ fontFamily: FONTS.mono, fontSize: 15, fontWeight: 700, color }}>{value}</span>
      <span style={{ fontFamily: FONTS.mono, fontSize: 7, color: 'rgba(200,216,232,0.35)' }}>{label}</span>
      {note && <span style={{ fontFamily: FONTS.mono, fontSize: 6, color: 'rgba(200,216,232,0.2)' }}>{note}</span>}
    </div>
  )
}
