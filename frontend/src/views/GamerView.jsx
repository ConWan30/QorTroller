import { Suspense, useRef } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { Environment, MeshTransmissionMaterial, Float } from '@react-three/drei'
import * as THREE from 'three'
import { HeartbeatWaveform } from '../heartbeat/HeartbeatWaveform'
import { useHeartbeatStore } from '../heartbeat/useHeartbeat'
import { useSeparationDefensibility, useTournamentPreflight } from '../api/bridgeApi'
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

export function GamerView() {
  const magnitude  = useHeartbeatStore((s) => s.magnitude)
  const merkleRoot = useHeartbeatStore((s) => s.merkleRoot)
  const { data: defensibility } = useSeparationDefensibility()
  const { data: preflight }     = useTournamentPreflight()

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
