import { Suspense, useRef } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { Environment, MeshTransmissionMaterial, Float } from '@react-three/drei'
import * as THREE from 'three'
import { HeartbeatWaveform } from '../heartbeat/HeartbeatWaveform'
import { useHeartbeatStore } from '../heartbeat/useHeartbeat'
import { useSeparationDefensibility, useTournamentPreflight, useCaptureHealth, useGrindChain } from '../api/bridgeApi'
import { ProvenanceTag } from '../provenance/ProvenanceTag'
import { FONTS, GAMER } from '../shared/design/tokens'

// VHP physical object: floating glass octahedron representing the soulbound credential
function VHPObject({ magnitude = 0.5, blocked = true }) {
  const meshRef = useRef()
  const glowRef = useRef()

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    if (meshRef.current) {
      meshRef.current.rotation.y = t * 0.4
      meshRef.current.rotation.x = Math.sin(t * 0.3) * 0.2
      meshRef.current.position.y = Math.sin(t * 0.8) * 0.08
    }
    if (glowRef.current) {
      glowRef.current.material.opacity = 0.04 + magnitude * 0.12 + Math.sin(t * 2) * 0.02
    }
  })

  const color = blocked ? '#ff3b5c' : '#00ff88'

  return (
    <Float speed={1.5} rotationIntensity={0.3} floatIntensity={0.4}>
      <group>
        {/* Outer glow sphere */}
        <mesh ref={glowRef}>
          <sphereGeometry args={[0.72, 16, 16]} />
          <meshBasicMaterial color={color} transparent side={THREE.BackSide} opacity={0.06} />
        </mesh>
        {/* Glass octahedron: VHP credential */}
        <mesh ref={meshRef}>
          <octahedronGeometry args={[0.52, 0]} />
          <MeshTransmissionMaterial
            transmission={0.97}
            thickness={0.4}
            ior={1.52}
            roughness={0.06}
            metalness={0.0}
            color={blocked ? '#ff1a3a' : '#00d4ff'}
            emissive={blocked ? '#800015' : '#003366'}
            emissiveIntensity={0.3}
            chromaticAberration={0.04}
            distortionScale={0.15}
            temporalDistortion={0.05}
          />
        </mesh>
        {/* Inner crystal core */}
        <mesh scale={0.28}>
          <icosahedronGeometry args={[1, 0]} />
          <meshStandardMaterial
            color={blocked ? '#ff3b5c' : '#00d4ff'}
            emissive={blocked ? '#ff3b5c' : '#00d4ff'}
            emissiveIntensity={0.8}
            wireframe
          />
        </mesh>
      </group>
    </Float>
  )
}

// Touchpad heat gradient rendered as canvas overlay
function TouchpadHeatmap({ ratio }) {
  const pct = Math.min(1, Math.max(0, ratio ?? 0))
  const gradient = `linear-gradient(135deg,
    rgba(74,158,255,${0.08 + pct * 0.25}) 0%,
    rgba(0,212,255,${0.04 + pct * 0.18}) 50%,
    rgba(0,255,136,${pct * 0.15}) 100%)`
  return (
    <div style={{
      position:     'absolute',
      inset:        0,
      background:   gradient,
      borderRadius: 8,
      pointerEvents:'none',
      transition:   'background 1s ease',
    }} />
  )
}

// Tremor glow ring — glows brighter as tremor_peak_hz is more discriminative
function TremorGlowRing({ ratio }) {
  const pct = Math.min(1, Math.max(0, (ratio ?? 0) - 0.8) / 0.4)
  return (
    <div style={{
      position:     'absolute',
      inset:        -12,
      borderRadius: '50%',
      border:       `1px solid rgba(0,212,255,${0.1 + pct * 0.5})`,
      boxShadow:    `0 0 ${8 + pct * 24}px rgba(0,212,255,${0.1 + pct * 0.4})`,
      pointerEvents:'none',
      transition:   'all 0.6s ease',
    }} />
  )
}

// Phase 235-FINAL: Grind Integrity Panel
function GrindPanel({ captureHealth, grindChain }) {
  const cc      = captureHealth?.consecutive_clean_toward_target ?? 0
  const target  = captureHealth?.grind_target ?? 100
  const pct     = Math.min(1, cc / Math.max(1, target))
  const state   = captureHealth?.capture_state ?? '—'
  const host    = captureHealth?.host_state ?? '—'
  const ready   = captureHealth?.grind_ready ?? false
  const paused  = captureHealth?.session_counting_paused ?? false
  const gctx    = captureHealth?.latest_gameplay_context ?? null
  const chainLen  = grindChain?.chain_length ?? 0
  const intact    = grindChain?.chain_intact ?? true
  const sessionId = grindChain?.grind_session_id ?? '—'

  const hostColor = host === 'EXCLUSIVE_USB' ? GAMER.green
    : host === 'CONTESTED'    ? GAMER.red
    : host === 'DEGRADED'     ? '#ff9500'
    : 'rgba(200,216,232,0.4)'

  const stateColor = state === 'NOMINAL' ? GAMER.green
    : state === 'DEGRADED'    ? '#ff9500'
    : state === 'DISCONNECTED'? GAMER.red
    : 'rgba(200,216,232,0.4)'

  const gctxColor = gctx === 'ACTIVE_GAMEPLAY' ? GAMER.green
    : gctx === 'MENU_DETECTED' ? GAMER.red
    : 'rgba(200,216,232,0.4)'

  return (
    <div style={{
      border:       `1px solid rgba(0,212,255,0.12)`,
      borderRadius: 5,
      padding:      '7px 10px',
      background:   'rgba(0,212,255,0.03)',
      display:      'flex',
      flexDirection:'column',
      gap:          6,
    }}>
      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontFamily: FONTS.mono, fontSize: 7.5, color: 'rgba(0,212,255,0.45)', letterSpacing: '0.12em' }}>
          GRIND INTEGRITY CHAIN
        </span>
        <span style={{
          fontFamily: FONTS.mono,
          fontSize:   7,
          color:      intact ? GAMER.green : GAMER.red,
          background: intact ? 'rgba(0,255,136,0.06)' : 'rgba(255,59,92,0.08)',
          padding:    '1px 5px',
          borderRadius: 2,
          border:     `1px solid ${intact ? 'rgba(0,255,136,0.2)' : 'rgba(255,59,92,0.3)'}`,
        }}>
          {intact ? '● INTACT' : '⚠ BROKEN'}
        </span>
      </div>

      {/* Progress bar */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
          <span style={{ fontFamily: FONTS.mono, fontSize: 8, color: 'rgba(200,216,232,0.5)' }}>
            consecutive_clean
          </span>
          <span style={{ fontFamily: FONTS.mono, fontSize: 10, color: GAMER.cyan, fontWeight: 600 }}>
            {cc} / {target}
          </span>
        </div>
        <div style={{ height: 5, background: 'rgba(255,255,255,0.06)', borderRadius: 3, overflow: 'hidden' }}>
          <div style={{
            height:     '100%',
            width:      `${pct * 100}%`,
            background: pct >= 1 ? GAMER.green : `linear-gradient(90deg, ${GAMER.cyan}, #4a9eff)`,
            borderRadius: 3,
            transition: 'width 0.5s ease',
            boxShadow:  pct > 0 ? `0 0 6px rgba(0,212,255,0.4)` : 'none',
          }} />
        </div>
        {paused && (
          <div style={{ fontFamily: FONTS.mono, fontSize: 7, color: '#ff9500', marginTop: 2 }}>
            ⚠ COUNTING PAUSED — waiting for EXCLUSIVE_USB + NOMINAL
          </div>
        )}
      </div>

      {/* State row */}
      <div style={{ display: 'flex', gap: 12 }}>
        <MiniStat label="PCC" value={state} color={stateColor} />
        <MiniStat label="HOST" value={host} color={hostColor} />
        <MiniStat label="READY" value={ready ? 'YES' : 'NO'} color={ready ? GAMER.green : '#ff9500'} />
        <MiniStat label="CHAIN" value={`${chainLen} links`} color={GAMER.cyan} />
      </div>

      {/* GAD + session */}
      <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
        <MiniStat
          label="GAMEPLAY"
          value={gctx ?? 'NULL'}
          color={gctxColor}
        />
        <div style={{ marginLeft: 'auto', fontFamily: FONTS.mono, fontSize: 7, color: 'rgba(0,212,255,0.3)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 120 }}>
          {sessionId}
        </div>
      </div>
    </div>
  )
}

function MiniStat({ label, value, color }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
      <span style={{ fontFamily: FONTS.mono, fontSize: 6.5, color: 'rgba(200,216,232,0.3)', letterSpacing: '0.08em' }}>{label}</span>
      <span style={{ fontFamily: FONTS.mono, fontSize: 8, color: color || 'rgba(200,216,232,0.6)', fontWeight: 500 }}>{value}</span>
    </div>
  )
}

export function GamerView() {
  const magnitude  = useHeartbeatStore((s) => s.magnitude)
  const merkleRoot = useHeartbeatStore((s) => s.merkleRoot)
  const { data: defensibility }  = useSeparationDefensibility()
  const { data: preflight }      = useTournamentPreflight()
  const { data: captureHealth }  = useCaptureHealth()
  const { data: grindChain }     = useGrindChain()

  const ratio   = defensibility?.ratio ?? 1.177
  const blocked = !(preflight?.overall_pass ?? false)

  return (
    <div style={{ display: 'flex', height: '100%', gap: 0, background: GAMER.bg }}>

      {/* Left: controller twin iframe (preserved from Phase 59) */}
      <div style={{
        flex:        '0 0 52%',
        position:    'relative',
        borderRight: '1px solid rgba(0,212,255,0.08)',
        overflow:    'hidden',
      }}>
        <TouchpadHeatmap ratio={ratio} />
        <iframe
          src="/controller-twin.html"
          style={{
            width:        '100%',
            height:       '100%',
            border:       'none',
            background:   'transparent',
            position:     'relative',
            zIndex:       1,
          }}
          title="Controller Digital Twin"
        />
        <div style={{ position: 'absolute', top: 8, left: 12, zIndex: 2 }}>
          <TremorGlowRing ratio={ratio} />
        </div>
      </div>

      {/* Right: VHP object + stats */}
      <div style={{
        flex:           '1',
        display:        'flex',
        flexDirection:  'column',
        overflow:       'hidden',
      }}>

        {/* VHP 3D canvas */}
        <div style={{ flex: '0 0 55%', position: 'relative' }}>
          <div style={{
            position: 'absolute',
            top: 10, left: 12,
            fontFamily: FONTS.mono,
            fontSize: 9,
            color: 'rgba(0,212,255,0.5)',
            letterSpacing: '0.1em',
            zIndex: 2,
          }}>
            VHP CREDENTIAL — {blocked ? 'BLOCKED' : 'ELIGIBLE'}
          </div>
          <Canvas
            camera={{ position: [0, 0, 2.2], fov: 50 }}
            style={{ background: 'transparent' }}
          >
            <Suspense fallback={null}>
              <Environment preset="city" />
              <ambientLight intensity={0.4} />
              <pointLight position={[2, 2, 2]} intensity={0.8} color={GAMER.cyan} />
              <pointLight position={[-2, -1, -1]} intensity={0.4} color={blocked ? '#ff3b5c' : '#00ff88'} />
              <VHPObject magnitude={magnitude} blocked={blocked} />
            </Suspense>
          </Canvas>
        </div>

        {/* Stats panel */}
        <div style={{
          flex:       '1',
          padding:    '10px 14px',
          borderTop:  '1px solid rgba(0,212,255,0.08)',
          display:    'flex',
          flexDirection: 'column',
          gap:        8,
          overflowY:  'auto',
        }}>

          {/* Grind Integrity Panel — Phase 235-FINAL */}
          <GrindPanel captureHealth={captureHealth} grindChain={grindChain} />

          {/* Heartbeat waveform */}
          <div>
            <div style={{ fontFamily: FONTS.mono, fontSize: 8, color: 'rgba(0,212,255,0.4)', marginBottom: 3, letterSpacing: '0.1em' }}>
              228-BYTE PoAC HEARTBEAT
            </div>
            <HeartbeatWaveform accent={GAMER.cyan} height={36} />
          </div>

          {/* Separation ratio */}
          <StatRow
            label="tremor_resting ratio"
            value={<ProvenanceTag
              value={ratio}
              agentId="SeparationRatioMonitorAgent"
              phase={129}
              invariant="target >1.0 (TOURNAMENT BLOCKER)"
              style={{ color: ratio >= 1.0 ? GAMER.green : GAMER.orange, fontFamily: FONTS.mono, fontSize: 13, fontWeight: 600 }}
            />}
            note={ratio >= 1.0 ? 'P1vP3 UNRESOLVED' : 'BELOW TARGET'}
            noteColor={GAMER.orange}
          />

          {/* Merkle root */}
          <StatRow
            label="Merkle root"
            value={<span style={{ fontFamily: FONTS.mono, fontSize: 10, color: GAMER.cyan }}>
              {merkleRoot ? merkleRoot.slice(-16) : '—'}
            </span>}
            note="38-leaf fleet"
            noteColor={GAMER.t3}
          />

          {/* Eligibility gate */}
          <StatRow
            label="isFullyEligible()"
            value={<span style={{
              fontFamily: FONTS.mono,
              fontSize:   11,
              fontWeight: 700,
              color:      blocked ? GAMER.red : GAMER.green,
            }}>{blocked ? 'FALSE' : 'TRUE'}</span>}
            note={blocked ? 'per-pair P0 gate open' : 'tournament eligible'}
            noteColor={blocked ? GAMER.red : GAMER.green}
          />
        </div>
      </div>
    </div>
  )
}

function StatRow({ label, value, note, noteColor }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <div style={{ fontFamily: FONTS.mono, fontSize: 8, color: 'rgba(200,216,232,0.35)', letterSpacing: '0.08em' }}>{label}</div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
        {value}
        {note && <span style={{ fontFamily: FONTS.mono, fontSize: 8, color: noteColor || 'rgba(200,216,232,0.35)' }}>{note}</span>}
      </div>
    </div>
  )
}
