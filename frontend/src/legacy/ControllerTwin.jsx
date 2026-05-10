import { useRef, useState, useEffect, useCallback, useMemo, Suspense } from 'react'
import { createRoot } from 'react-dom/client'
import { Canvas, useFrame } from '@react-three/fiber'
import { Physics } from '@react-three/rapier'
import { OrbitControls, Sparkles, useGLTF, Environment, ContactShadows } from '@react-three/drei'
import * as THREE from 'three'
import QRCode from 'qrcode'
// Phase 238-FRONTEND-V3 — SSE consumer for /agent/twin-stream cryptographic events.
// Aliased on import so the legacy WebSocket-based useTwinStream local function
// (line ~81) is not shadowed.
import { useTwinStream as useTwinSSEStream } from '../api/twinStream'

const VOID_BG = '#030507'
const ORANGE  = '#ff6b00'
const CYAN    = '#00d4ff'
const GREEN   = '#00ff88'
const RED     = '#ff2d55'
const DIM     = '#3d5060'

// 13-feature names (indices 0 and 10 are structurally zero — excluded from L4)
// Index 12 added Phase 81: temporal_state_transition_entropy_variance (Class J discriminator)
const BIO_FEATURES = [
  'Trigger Rate',   // 0 — structurally zero
  'L2 Onset Vel',   // 1
  'R2 Onset Vel',   // 2
  'Micro Tremor',   // 3
  'Grip Asymm',     // 4
  'Autocorr L1',    // 5
  'Autocorr L5',    // 6
  'Tremor Hz',      // 7
  'Tremor Power',   // 8
  'Spectral Ent',   // 9
  'Touch Var',      // 10 — structurally zero (pending recapture)
  'IBI Jitter',     // 11 — Phase 57
  'Entropy Var',    // 12 — Phase 81: Class J HMM discriminator (human >0.15, bot <0.02)
]

// Per-feature max expected human value (for radar normalization)
// Index 12: entropy_variance human range ~0.15–0.35, normalize against 0.30
const BIO_NORM = [1, 5000, 5000, 600000, 1, 1, 1, 50, 1, 9, 1, 0.06, 0.30]
const FEATURE_ZERO_IDX = new Set([0, 10])

const params     = new URLSearchParams(window.location.search)
const DEVICE_ID  = params.get('device') || ''
// Use IPv4 literal — Node/browser on Windows resolves "localhost" to IPv6 ::1
// first, but the bridge binds IPv4 only (0.0.0.0:8080). Direct fetches from
// this iframe bypass the Vite proxy, so we hit the resolver issue head-on.
// 127.0.0.1 sidesteps it entirely. Override via ?bridge=... query param.
const BRIDGE_URL = params.get('bridge') || '127.0.0.1:8080'
// Phase 235-GAMER-REDESIGN — `?minimal=1` drops every overlay (header, side
// panels, footer, status pills) so only the 3D Canvas renders.  Used by
// GamerView's iframe so the controller has the full viewport.
const MINIMAL    = params.get('minimal') === '1'

// ---------------------------------------------------------------------------
// useAutoDiscover — resolves device_id from URL param or bridge /api/v1/devices
// ---------------------------------------------------------------------------
function useAutoDiscover(initial) {
  const [deviceId, setDeviceId] = useState(initial)
  useEffect(() => {
    if (deviceId) return
    const poll = () => {
      fetch(`http://${BRIDGE_URL}/api/v1/devices`)
        .then(r => r.json())
        .then(devs => {
          const first = devs?.[0]?.device_id
          if (!first) return
          setDeviceId(first)
          const u = new URL(window.location)
          u.searchParams.set('device', first)
          window.history.replaceState({}, '', u)
        })
        .catch(() => {})
    }
    poll()
    const t = setInterval(poll, 3000)
    return () => clearInterval(t)
  }, [deviceId])
  return deviceId
}

// ---------------------------------------------------------------------------
// useTwinStream — live /ws/twin/{device_id} fusion WebSocket
// ---------------------------------------------------------------------------
function useTwinStream(deviceId) {
  const [frame,  setFrame]  = useState(null)
  const [record, setRecord] = useState(null)
  const [mode,   setMode]   = useState('OFFLINE')

  useEffect(() => {
    if (!deviceId) return
    let ws, timer
    const delay = { v: 3000 }
    function connect() {
      ws = new WebSocket(`ws://${BRIDGE_URL}/ws/twin/${deviceId}`)
      ws.onopen  = () => { delay.v = 3000; setMode('LIVE') }
      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data)
          if (msg.type === 'frame')  setFrame(msg.data)
          if (msg.type === 'record') setRecord(msg.data)
        } catch {}
      }
      ws.onclose = () => {
        setMode('OFFLINE')
        delay.v = Math.min(delay.v * 2, 30000)
        timer = setTimeout(connect, delay.v)
      }
      ws.onerror = () => {}
    }
    connect()
    return () => { ws?.close(); clearTimeout(timer) }
  }, [deviceId])

  return { frame, record, mode }
}

// ---------------------------------------------------------------------------
// useTwinSnapshot — REST snapshot + chain lock points
// ---------------------------------------------------------------------------
function useTwinSnapshot(deviceId) {
  const [snap,  setSnap]  = useState(null)
  const [chain, setChain] = useState([])

  useEffect(() => {
    if (!deviceId) return
    fetch(`http://${BRIDGE_URL}/controller/twin/${deviceId}`)
      .then(r => r.json()).then(setSnap).catch(() => {})
    fetch(`http://${BRIDGE_URL}/controller/twin/${deviceId}/chain?limit=50`)
      .then(r => r.json()).then(setChain).catch(() => {})
  }, [deviceId])

  return { snap, chain }
}

// ---------------------------------------------------------------------------
// useReplayMode — Phase 61: session replay hook
// ---------------------------------------------------------------------------
function useReplayMode(deviceId) {
  const [replayFrames,  setReplayFrames]  = useState([])
  const [replayIdx,     setReplayIdx]     = useState(0)
  const [replayActive,  setReplayActive]  = useState(false)
  const [checkpointSet, setCheckpointSet] = useState(new Set())
  const intervalRef = useRef(null)

  // Load checkpoint set on mount
  useEffect(() => {
    if (!deviceId) return
    fetch(`http://${BRIDGE_URL}/controller/twin/${deviceId}/checkpoints?limit=200`)
      .then(r => r.json())
      .then(d => setCheckpointSet(new Set(d.checkpoints || [])))
      .catch(() => {})
  }, [deviceId])

  const startReplay = useCallback((recordHash) => {
    fetch(`http://${BRIDGE_URL}/controller/twin/${deviceId}/replay?record_hash=${recordHash}`)
      .then(r => r.json())
      .then(d => {
        if (!d.frames?.length) return
        setReplayFrames(d.frames)
        setReplayIdx(0)
        setReplayActive(true)
      }).catch(() => {})
  }, [deviceId])

  const stopReplay = useCallback(() => {
    setReplayActive(false)
    setReplayFrames([])
    setReplayIdx(0)
    clearInterval(intervalRef.current)
  }, [])

  // Advance playback at 20 Hz
  useEffect(() => {
    if (!replayActive || !replayFrames.length) return
    intervalRef.current = setInterval(() => {
      setReplayIdx(i => {
        if (i + 1 >= replayFrames.length) {
          setReplayActive(false)
          return 0
        }
        return i + 1
      })
    }, 50)
    return () => clearInterval(intervalRef.current)
  }, [replayActive, replayFrames.length])

  const currentReplayFrame = replayActive ? replayFrames[replayIdx] : null
  const replayProgress = replayFrames.length ? replayIdx / replayFrames.length : 0

  return {
    currentReplayFrame, replayActive, startReplay, stopReplay,
    replayProgress, replayIdx, replayTotal: replayFrames.length, checkpointSet,
  }
}

// ---------------------------------------------------------------------------
// useFeatureHistory — Phase 61: device feature vector history for scatter
// ---------------------------------------------------------------------------
function useFeatureHistory(deviceId) {
  const [history, setHistory] = useState([])
  useEffect(() => {
    if (!deviceId) return
    fetch(`http://${BRIDGE_URL}/controller/twin/${deviceId}/features?limit=50`)
      .then(r => r.json()).then(setHistory).catch(() => {})
  }, [deviceId])
  return history
}

// ---------------------------------------------------------------------------
// useAgentStatus — Phase 79–81: polls validation gate, live-mode, federation
// ---------------------------------------------------------------------------
function useAgentStatus(enabled) {
  const [gate,       setGate]    = useState(null)
  const [liveMode,   setLiveMode] = useState(null)
  const [federation, setFed]     = useState(null)
  useEffect(() => {
    if (!enabled) return
    const safe = async url => {
      try { const r = await window.fetch(`http://${BRIDGE_URL}${url}`); return r.ok ? r.json() : null }
      catch { return null }
    }
    const poll = async () => {
      const [g, l, f] = await Promise.all([
        safe('/agent/validation-gate'),
        safe('/agent/live-mode-status'),
        safe('/federation/peers'),
      ])
      if (g) setGate(g)
      if (l) setLiveMode(l)
      if (f) setFed(f)
    }
    poll()
    const id = setInterval(poll, 15000)
    return () => clearInterval(id)
  }, [enabled])
  return { gate, liveMode, federation }
}

// ---------------------------------------------------------------------------
// useLatestRuling — Phase 81: polls /agent/rulings for Class J evidence
// ---------------------------------------------------------------------------
function useLatestRuling(deviceId, enabled) {
  const [ruling, setRuling] = useState(null)
  useEffect(() => {
    if (!enabled || !deviceId) return
    const poll = async () => {
      try {
        const r = await window.fetch(`http://${BRIDGE_URL}/agent/rulings/${deviceId}`)
        if (!r.ok) return
        const data = await r.json()
        const rulings = Array.isArray(data.rulings) ? data.rulings
          : Array.isArray(data) ? data : []
        if (!rulings.length) return
        const latest = { ...rulings[0] }
        if (typeof latest.evidence_summary === 'string') {
          try { latest.evidence_summary = JSON.parse(latest.evidence_summary) } catch {}
        }
        setRuling(latest)
      } catch {}
    }
    poll()
    const id = setInterval(poll, 30000)
    return () => clearInterval(id)
  }, [deviceId, enabled])
  return ruling
}

// ---------------------------------------------------------------------------
// BiometricGlobe — glowing energy orb shaped by 12 L4 biometric features.
// Bot = near-perfect sphere. Human = unique lumpy plasma blob.
// Vertex displacement per azimuthal sector driven by feature[i] / BIO_NORM[i].
// ---------------------------------------------------------------------------
function BiometricGlobe({ frame, record, snap }) {
  const groupRef  = useRef()
  const coreRef   = useRef()
  const shellRef  = useRef()
  const midRef    = useRef()
  const outerRef  = useRef()
  const lightRef  = useRef()

  // History ring buffers for orbiting energy arc trails (50 frames each)
  const histRef = useRef({
    l2:  new Array(50).fill(0),
    r2:  new Array(50).fill(0),
    acc: new Array(50).fill(0),
  })

  // Biometric mean vector — parsed once per snap change, not per frame
  const mvRef = useRef(null)
  useEffect(() => {
    const mj = snap?.biometric_fingerprint?.mean_json
    try { mvRef.current = mj ? JSON.parse(mj) : null } catch { mvRef.current = null }
  }, [snap?.biometric_fingerprint?.mean_json])

  // Pre-allocated color objects — avoid GC pressure in 60 Hz loop
  const _redC   = useMemo(() => new THREE.Color(RED),   [])
  const _greenC = useMemo(() => new THREE.Color(GREEN), [])
  const _hc     = useMemo(() => new THREE.Color(),      [])

  // ── Geometries (created once) ──────────────────────────────────────────────
  const globe = useMemo(() => {
    const g = new THREE.SphereGeometry(1.1, 52, 52)
    g.userData.orig = new Float32Array(g.attributes.position.array)
    return g
  }, [])
  const coreGeo  = useMemo(() => new THREE.SphereGeometry(0.62, 24, 18),  [])
  const midGeo   = useMemo(() => new THREE.SphereGeometry(1.45, 18, 12),  [])
  const outerGeo = useMemo(() => new THREE.SphereGeometry(1.95, 16, 10),  [])
  const l2Geo    = useMemo(() => new THREE.BufferGeometry(), [])
  const r2Geo    = useMemo(() => new THREE.BufferGeometry(), [])
  const accGeo   = useMemo(() => new THREE.BufferGeometry(), [])

  useFrame((state, delta) => {
    if (!shellRef.current) return
    const t = state.clock.elapsedTime

    const l2Raw    = (frame?.l2_trigger   ?? 0) / 255
    const r2Raw    = (frame?.r2_trigger   ?? 0) / 255
    const accelMag = Math.hypot(frame?.accel_x ?? 0, frame?.accel_y ?? 0) / 32767
    const gyroX    = frame?.gyro_x ?? 0
    const gyroY    = frame?.gyro_y ?? 0
    const humanity = record?.humanity_prob ?? 0.5

    // Roll history buffers
    const H = histRef.current
    H.l2.push(l2Raw);     H.l2.shift()
    H.r2.push(r2Raw);     H.r2.shift()
    H.acc.push(accelMag); H.acc.shift()

    // Human color: RED (bot) → GREEN (human)
    const humanColor = _hc.lerpColors(_redC, _greenC, humanity)

    // ── Vertex displacement ────────────────────────────────────────────────
    const mv   = mvRef.current
    const pos  = globe.attributes.position
    const orig = globe.userData.orig
    for (let i = 0, n = pos.count; i < n; i++) {
      const ox = orig[i*3], oy = orig[i*3+1], oz = orig[i*3+2]
      // Map azimuthal angle to one of 13 feature sectors (Phase 81: +entropy_variance)
      const fIdx = Math.floor(((Math.atan2(oz, ox) + Math.PI) / (2 * Math.PI)) * 13) % 13
      const feat = FEATURE_ZERO_IDX.has(fIdx) ? 0
        : mv && mv[fIdx] != null ? Math.min(Math.abs(mv[fIdx]) / BIO_NORM[fIdx], 1) : 0
      const r = 1.1
        + feat  * 0.44                                   // biometric signature
        + 0.055 * Math.sin(t * 2.1 + fIdx * 0.72)       // living wobble
        + (l2Raw + r2Raw) * 0.06                         // trigger pulse
      const len = Math.sqrt(ox*ox + oy*oy + oz*oz) || 1
      pos.setXYZ(i, ox/len * r, oy/len * r, oz/len * r)
    }
    pos.needsUpdate = true
    globe.computeVertexNormals()

    // ── Globe rotation — slow self-spin + physical gyro feedback ──────────
    if (groupRef.current) {
      groupRef.current.rotation.y += delta * (0.22 + gyroX * 0.08)
      groupRef.current.rotation.x += delta * gyroY * 0.04
    }

    // ── Material updates ───────────────────────────────────────────────────
    const pulse = 0.5 + 0.4 * Math.sin(t * 2.8)   // breathing pulse

    if (coreRef.current?.material) {
      coreRef.current.material.color.copy(humanColor)
      coreRef.current.material.emissive.copy(humanColor)
      coreRef.current.material.emissiveIntensity = 1.4 + pulse * 0.8 + (l2Raw + r2Raw) * 1.5
      coreRef.current.material.opacity = 0.55 + pulse * 0.15
    }
    if (shellRef.current?.material) {
      shellRef.current.material.emissive.copy(humanColor)
      shellRef.current.material.emissiveIntensity = 0.55 + r2Raw * 0.9 + pulse * 0.2
    }
    if (midRef.current?.material) {
      midRef.current.material.color.copy(humanColor)
      midRef.current.material.emissive.copy(humanColor)
      midRef.current.material.emissiveIntensity = 0.28 + pulse * 0.12
      midRef.current.material.opacity = 0.06 + pulse * 0.025
    }
    if (outerRef.current?.material) {
      outerRef.current.material.color.copy(humanColor)
      outerRef.current.material.emissive.copy(humanColor)
      outerRef.current.material.emissiveIntensity = 0.12 + pulse * 0.06
      outerRef.current.material.opacity = 0.028 + pulse * 0.01
    }
    if (lightRef.current) {
      lightRef.current.color.copy(humanColor)
      lightRef.current.intensity = 2.5 + pulse * 2.0 + (l2Raw + r2Raw) * 4.0
    }

    // ── Energy arc ribbon trails ───────────────────────────────────────────
    const arc = (hist, yBias, angSpeed, phase, amp) =>
      hist.map((v, k) => {
        const a = (k / hist.length) * Math.PI * 2 + angSpeed * t + phase
        const rr = 1.52 + v * amp
        return new THREE.Vector3(Math.cos(a) * rr, yBias + v * 0.26, Math.sin(a) * rr)
      })
    if (H.l2.length  > 1) l2Geo.setFromPoints(arc(H.l2,  0.32,  0.55, 0,            0.32))
    if (H.r2.length  > 1) r2Geo.setFromPoints(arc(H.r2, -0.32, -0.45, 0,            0.32))
    if (H.acc.length > 1) accGeo.setFromPoints(arc(H.acc, 0.00,  0.38, Math.PI*0.7, 0.22))
  })

  const humanity0   = record?.humanity_prob ?? 0.5
  const humanColor0 = new THREE.Color().lerpColors(new THREE.Color(RED), new THREE.Color(GREEN), humanity0)
  const l6pFlag     = record?.l6p_flag ?? false
  const anomalyThr  = snap?.calibration?.anomaly_threshold ?? 6.726

  return (
    <group ref={groupRef}>

      {/* Dynamic point light at globe centre — drives scene lighting */}
      <pointLight ref={lightRef} intensity={2.5} color={humanColor0} distance={8} decay={2} />

      {/* Innermost core — bright glowing nucleus */}
      <mesh ref={coreRef} geometry={coreGeo}>
        <meshStandardMaterial
          color={humanColor0} emissive={humanColor0} emissiveIntensity={1.4}
          transparent opacity={0.55} depthWrite={false}
          blending={THREE.AdditiveBlending}
        />
      </mesh>

      {/* Biometric shell — vertex displaced by L4 feature magnitudes */}
      <mesh ref={shellRef} geometry={globe} castShadow>
        <meshStandardMaterial
          color="#0d1f30" roughness={0.28} metalness={0.72}
          emissive={humanColor0} emissiveIntensity={0.55}
          transparent opacity={0.82}
        />
      </mesh>

      {/* Mid glow layer — additive outer haze */}
      <mesh ref={midRef} geometry={midGeo}>
        <meshStandardMaterial
          color={humanColor0} emissive={humanColor0} emissiveIntensity={0.28}
          transparent opacity={0.06} depthWrite={false}
          side={THREE.BackSide} blending={THREE.AdditiveBlending}
        />
      </mesh>

      {/* Outer corona — large diffuse glow envelope */}
      <mesh ref={outerRef} geometry={outerGeo}>
        <meshStandardMaterial
          color={humanColor0} emissive={humanColor0} emissiveIntensity={0.12}
          transparent opacity={0.028} depthWrite={false}
          side={THREE.BackSide} blending={THREE.AdditiveBlending}
        />
      </mesh>

      {/* L2 trigger energy arc (ORANGE, upper orbital plane) */}
      <line geometry={l2Geo}>
        <lineBasicMaterial color={ORANGE} transparent opacity={0.75}
          blending={THREE.AdditiveBlending} depthWrite={false} />
      </line>

      {/* R2 trigger energy arc (CYAN, lower orbital plane) */}
      <line geometry={r2Geo}>
        <lineBasicMaterial color={CYAN} transparent opacity={0.75}
          blending={THREE.AdditiveBlending} depthWrite={false} />
      </line>

      {/* Accel magnitude arc (GREEN, equatorial) */}
      <line geometry={accGeo}>
        <lineBasicMaterial color={GREEN} transparent opacity={0.50}
          blending={THREE.AdditiveBlending} depthWrite={false} />
      </line>

      {/* L6 passive challenge — pulsing equatorial ring */}
      {l6pFlag && (
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[1.72, 0.022, 8, 72]} />
          <meshStandardMaterial color={CYAN} emissive={CYAN}
            emissiveIntensity={2.5} transparent opacity={0.8}
            blending={THREE.AdditiveBlending} depthWrite={false} />
        </mesh>
      )}

      {/* Anomaly sparkles */}
      <Sparkles
        count={record?.pitl_l4_distance > anomalyThr ? 60 : 18}
        scale={[3.8, 3.8, 3.8]} size={0.7}
        color={record?.inference === 0x30 ? RED : humanColor0}
        speed={0.35} opacity={0.55}
      />
    </group>
  )
}

// ---------------------------------------------------------------------------
// ButtonGlow — emissive sphere overlay, pulses on real HID press
// ---------------------------------------------------------------------------
function ButtonGlow({ position, active, color, radius = 0.10 }) {
  const ref = useRef()
  useFrame((state) => {
    if (!ref.current?.material) return
    const t = state.clock.elapsedTime
    ref.current.material.emissiveIntensity = active
      ? 3.8 + Math.sin(t * 16) * 1.2
      : 0.04
    ref.current.material.opacity = active ? 0.92 : 0.13
  })
  return (
    <mesh ref={ref} position={position}>
      <sphereGeometry args={[radius, 10, 10]} />
      <meshStandardMaterial
        color={color} emissive={color}
        emissiveIntensity={active ? 3.8 : 0.04}
        transparent opacity={active ? 0.92 : 0.13}
        blending={THREE.AdditiveBlending} depthWrite={false}
      />
    </mesh>
  )
}

// ---------------------------------------------------------------------------
// DualShockEdgeTwin — Phase 69: actual GLB DualShock Edge CFI-ZCP1 model.
// Replaces the procedural orb with the real controller geometry.
//
// VAPI-exclusive live biometric animations (all driven by bridge WebSocket):
//   • Humanity probe (0→1): emissive color RED→GREEN on all body meshes
//   • L2/R2 triggers: orbital energy arc trails (real 1000Hz polling trace)
//   • L4 Mahalanobis distance: orange anomaly corona + particle storm
//   • Gyro XY: natural tilt rotation (not spinning — controller grip physics)
//   • IBI rhythm: breathing pulse intensity synced to press_timing_jitter_variance
//   • L6 passive: pulsing CYAN equatorial ring when l6p_flag active
//   • Inference code: floating holographic badge above controller
//   • Accel magnitude: equatorial arc (green, bottom orbital plane)
// ---------------------------------------------------------------------------
function DualShockEdgeTwin({ frame, record, snap, pulseRef, pccRimRef }) {
  const groupRef  = useRef()
  const lightRef  = useRef()
  const haloRef   = useRef()
  const coronaRef = useRef()

  // Energy arc geometries — L2 (orange), R2 (cyan), accel (green)
  const l2Geo  = useMemo(() => new THREE.BufferGeometry(), [])
  const r2Geo  = useMemo(() => new THREE.BufferGeometry(), [])
  const accGeo = useMemo(() => new THREE.BufferGeometry(), [])

  // History ring buffers — 50 frames at 60 Hz ≈ 0.83s trail
  const histRef = useRef({
    l2:  new Array(50).fill(0),
    r2:  new Array(50).fill(0),
    acc: new Array(50).fill(0),
  })

  // Biometric mean vector (12-elem) — used for fingerprint badge coloring
  const mvRef = useRef(null)
  useEffect(() => {
    const mj = snap?.biometric_fingerprint?.mean_json
    try { mvRef.current = mj ? JSON.parse(mj) : null } catch { mvRef.current = null }
  }, [snap?.biometric_fingerprint?.mean_json])

  // Load the real DualShock Edge GLB model
  const { scene: controllerScene } = useGLTF('/assets/controller.glb')

  // Clone once so we can mutate materials without corrupting the GLTF cache
  const clonedScene = useMemo(() => {
    const clone = controllerScene.clone(true)
    clone.traverse(node => {
      if (!node.isMesh) return
      node.castShadow = true
      node.receiveShadow = true
      if (node.material) {
        node.material = node.material.clone()
        // Ensure emissive channel is active
        if (!node.material.emissive) node.material.emissive = new THREE.Color(0, 0, 0)
        node.material.needsUpdate = true
      }
    })
    return clone
  }, [controllerScene])

  // Pre-allocated color objects — no GC pressure in 60 Hz loop
  const _redC    = useMemo(() => new THREE.Color(RED),    [])
  const _greenC  = useMemo(() => new THREE.Color(GREEN),  [])
  const _orangeC = useMemo(() => new THREE.Color(ORANGE), [])
  const _cyanC   = useMemo(() => new THREE.Color(CYAN),   [])
  const _hc      = useMemo(() => new THREE.Color(),       [])

  useFrame((state, delta) => {
    const t = state.clock.elapsedTime

    // ── Raw sensor values ────────────────────────────────────────────────────
    const l2Raw    = (frame?.l2_trigger   ?? 0) / 255
    const r2Raw    = (frame?.r2_trigger   ?? 0) / 255
    const accelMag = Math.hypot(
      frame?.accel_x ?? 0, frame?.accel_y ?? 0, frame?.accel_z ?? 0
    ) / 56754   // ~sqrt(3) * 32767 — full-scale diagonal
    const gyroX    = (frame?.gyro_x ?? 0) / 32767
    const gyroY    = (frame?.gyro_y ?? 0) / 32767
    const humanity = record?.humanity_prob ?? 0.5
    const l4Dist   = record?.pitl_l4_distance ?? 0
    const jitter   = record?.pitl_features?.[11] ?? 0   // IBI jitter index 11
    const anomThr  = snap?.calibration?.anomaly_threshold ?? 7.009
    const isAnomaly = l4Dist > anomThr

    // ── History ring-buffer update ───────────────────────────────────────────
    const H = histRef.current
    H.l2.push(l2Raw);     H.l2.shift()
    H.r2.push(r2Raw);     H.r2.shift()
    H.acc.push(accelMag); H.acc.shift()

    // Smooth RED→GREEN based on humanity
    _hc.lerpColors(_redC, _greenC, humanity)

    // ── Phase 238-FRONTEND-V3 — SSE pulse layer (additive) ──────────────────
    // Every Twin pulse maps to a verifiable backend event. pulseRef is mutated
    // by the page-level useEffect on lastEvent; we read it once per frame and
    // compute a 0→1 decay factor.  Effects ADD to the existing animation
    // values rather than overriding them, except for BLOCK verdicts which
    // briefly freeze rotation drift.
    const pulse = pulseRef?.current
    let pulseFactor = 0
    let pulseColorObj = null
    let pulseIsBlock = false
    if (pulse?.kind && pulse.durationMs > 0) {
      const elapsed = (performance.now() / 1000) - pulse.startTime
      const dur = pulse.durationMs / 1000
      if (elapsed < dur) {
        pulseFactor = 1 - (elapsed / dur)
        pulseColorObj = new THREE.Color(pulse.color || CYAN)
        pulseIsBlock = pulse.kind === 'gic' && pulse.label === 'BLOCK'
      } else {
        // expire one-shot pulse so subsequent frames are no-ops
        pulse.kind = null
      }
    }

    // ── Natural gyro-driven tilt (NOT full rotation — it's a controller) ────
    if (groupRef.current) {
      const targetRX = gyroY * 0.18 + Math.sin(t * 0.25) * 0.012
      const targetRY = gyroX * 0.18 + t * 0.06        // very slow drift-spin
      const targetRZ = (l2Raw - r2Raw) * 0.04          // trigger asymmetry tilt
      groupRef.current.rotation.x += (targetRX - groupRef.current.rotation.x) * 0.06
      // BLOCK verdict: clamp drift-spin during the pulse window (visual freeze)
      if (!pulseIsBlock) {
        groupRef.current.rotation.y += delta * 0.06 + (targetRY - groupRef.current.rotation.y) * 0.02
      }
      groupRef.current.rotation.z += (targetRZ - groupRef.current.rotation.z) * 0.04
    }

    // ── Dynamic point light — humanity color + trigger burst ─────────────────
    if (lightRef.current) {
      lightRef.current.color.copy(_hc)
      lightRef.current.intensity = 2.8
        + (l2Raw + r2Raw) * 6.0        // trigger press = light burst
        + Math.sin(t * 2.1 + jitter * 20) * 0.7   // IBI jitter = breathing
        + pulseFactor * 4.0             // SSE pulse — additive
    }

    // ── Per-mesh emissive — body glows humanity color on trigger/motion ─────
    const emissiveBase = 0.05 + (l2Raw + r2Raw) * 0.35 + Math.sin(t * 1.8) * 0.03
    clonedScene.traverse(node => {
      if (!node.isMesh || !node.material?.emissive) return
      node.material.emissive.copy(_hc)
      node.material.emissiveIntensity = emissiveBase + (isAnomaly ? 0.15 : 0) + pulseFactor * 0.3
    })

    // ── Anomaly halo — orange corona when L4 distance > threshold ───────────
    // Phase 238-FRONTEND-V3: SSE pulse can OVERRIDE the halo color while
    // active (pulseFactor lerps from pulse color back to humanity/anomaly base
    // as the pulse decays).  Steady-state PCC rim color from pccRimRef takes
    // precedence over the humanity base when not anomalous and no pulse.
    if (haloRef.current?.material) {
      const baseHaloColor = isAnomaly ? _orangeC : _hc
      let haloColor = baseHaloColor
      const pccRim = pccRimRef?.current
      if (pccRim && pccRim !== 'default' && !isAnomaly && pulseFactor === 0) {
        haloColor = new THREE.Color(pccRim)
      }
      if (pulseColorObj) {
        // Lerp halo toward pulse color in proportion to pulseFactor
        haloColor = baseHaloColor.clone().lerp(pulseColorObj, pulseFactor)
      }
      haloRef.current.material.color.copy(haloColor)
      haloRef.current.material.emissive.copy(haloColor)
      if (isAnomaly) {
        haloRef.current.material.emissiveIntensity = 0.7 + Math.sin(t * 5.5) * 0.5
        haloRef.current.material.opacity           = 0.14 + Math.sin(t * 5.5) * 0.07
      } else if (pccRim === RED) {
        // CONTESTED — fast red rim flicker
        haloRef.current.material.emissiveIntensity = 0.4 + Math.sin(t * 7.0) * 0.4
        haloRef.current.material.opacity           = 0.08 + Math.sin(t * 7.0) * 0.05
      } else {
        haloRef.current.material.emissiveIntensity = 0.12 + Math.sin(t * 1.5) * 0.06 + pulseFactor * 0.6
        haloRef.current.material.opacity           = 0.035 + Math.sin(t * 1.5) * 0.012 + pulseFactor * 0.15
      }
    }

    // ── Energy arc ribbon trails (orbital planes around controller) ──────────
    const arc = (hist, yBias, angSpeed, phase, amp, radius) =>
      hist.map((v, k) => {
        const a = (k / hist.length) * Math.PI * 2 + angSpeed * t + phase
        const rr = radius + v * amp
        return new THREE.Vector3(
          Math.cos(a) * rr,
          yBias + v * 0.4,
          Math.sin(a) * rr,
        )
      })

    if (H.l2.length  > 1) l2Geo.setFromPoints(arc(H.l2,   0.80,  0.65,  0,            0.55, 2.8))
    if (H.r2.length  > 1) r2Geo.setFromPoints(arc(H.r2,  -0.80, -0.52,  0,            0.55, 2.8))
    if (H.acc.length > 1) accGeo.setFromPoints(arc(H.acc,  0.00,  0.40,  Math.PI*0.7, 0.38, 2.4))
  })

  // Static derived values (used in JSX — stable between renders)
  const humanity0  = record?.humanity_prob ?? 0.5
  const l4Dist0    = record?.pitl_l4_distance ?? 0
  const anomThr0   = snap?.calibration?.anomaly_threshold ?? 7.009
  const isAnomaly0 = l4Dist0 > anomThr0
  const l6pFlag    = record?.l6p_flag ?? false
  const infCode    = record?.inference ?? 0x20

  const humanColor0 = new THREE.Color().lerpColors(
    new THREE.Color(RED), new THREE.Color(GREEN), humanity0
  )

  // Inference badge text
  const INF_LABEL = {
    0x20: ['PASS',           GREEN  ],
    0x28: ['DRIVER INJECT',  RED    ],
    0x29: ['WALLHACK',       RED    ],
    0x2A: ['AIMBOT',         RED    ],
    0x2B: ['TEMPORAL BOT',   ORANGE ],
    0x30: ['BIO ANOMALY',    ORANGE ],
    0x31: ['IMU DECOUPLED',  CYAN   ],
    0x32: ['STICK DECOUPLED',CYAN   ],
  }
  const [infText, infColor] = INF_LABEL[infCode] ?? ['UNKNOWN', DIM]

  return (
    <group ref={groupRef}>

      {/* Primary humanity-driven point light — above and in front */}
      <pointLight
        ref={lightRef}
        intensity={2.8} color={humanColor0}
        distance={12} decay={2}
        position={[0, 2.0, 1.5]}
      />
      {/* Subtle fill light — always-on rim from below */}
      <pointLight
        intensity={0.8} color={CYAN}
        distance={6} decay={2}
        position={[0, -2.0, -0.5]}
      />

      {/* The real DualShock Edge CFI-ZCP1 model */}
      <primitive
        object={clonedScene}
        scale={[2.4, 2.4, 2.4]}
        position={[0, -0.15, 0]}
        rotation={[-0.08, 0, 0]}
      />

      {/* Outer halo — anomaly corona / humanity aura */}
      <mesh ref={haloRef}>
        <sphereGeometry args={[4.2, 18, 12]} />
        <meshStandardMaterial
          color={humanColor0} emissive={humanColor0} emissiveIntensity={0.12}
          transparent opacity={0.035} depthWrite={false}
          side={THREE.BackSide} blending={THREE.AdditiveBlending}
        />
      </mesh>

      {/* L2 trigger orbital arc — ORANGE, upper plane */}
      <line geometry={l2Geo}>
        <lineBasicMaterial color={ORANGE} transparent opacity={0.85}
          blending={THREE.AdditiveBlending} depthWrite={false} />
      </line>

      {/* R2 trigger orbital arc — CYAN, lower plane */}
      <line geometry={r2Geo}>
        <lineBasicMaterial color={CYAN} transparent opacity={0.85}
          blending={THREE.AdditiveBlending} depthWrite={false} />
      </line>

      {/* Accel magnitude arc — GREEN, equatorial */}
      <line geometry={accGeo}>
        <lineBasicMaterial color={GREEN} transparent opacity={0.55}
          blending={THREE.AdditiveBlending} depthWrite={false} />
      </line>

      {/* L6 Passive: pulsing CYAN equatorial ring — active only when l6p_flag */}
      {l6pFlag && (
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[3.6, 0.030, 8, 80]} />
          <meshStandardMaterial
            color={CYAN} emissive={CYAN} emissiveIntensity={3.0}
            transparent opacity={0.9}
            blending={THREE.AdditiveBlending} depthWrite={false}
          />
        </mesh>
      )}

      {/* Anomaly particle storm — scales with L4 Mahalanobis distance */}
      <Sparkles
        count={isAnomaly0 ? 90 : 20}
        scale={[5.0, 5.0, 5.0]}
        size={isAnomaly0 ? 1.1 : 0.7}
        color={isAnomaly0 ? ORANGE : humanColor0}
        speed={isAnomaly0 ? 0.9 : 0.35}
        opacity={0.65}
      />

      {/* Holographic inference code badge — floats above controller */}
      <mesh position={[0, 2.2, 0]} rotation={[0, 0, 0]}>
        <planeGeometry args={[1.8, 0.28]} />
        <meshBasicMaterial
          color={infColor} transparent opacity={0.08}
          side={THREE.DoubleSide} depthWrite={false}
        />
      </mesh>

      {/* Button glow overlays — lit by real HID bitmask press state */}
      {(() => {
        const b0   = frame?.buttons_0 ?? 0
        const b1   = frame?.buttons_1 ?? 0
        const l2On = (frame?.l2_trigger ?? 0) > 20
        const r2On = (frame?.r2_trigger ?? 0) > 20
        const defs = [
          { pos: [-2.05, 1.38, 0.72], color: ORANGE,    active: l2On },               // L2
          { pos: [ 2.05, 1.38, 0.72], color: CYAN,      active: r2On },               // R2
          { pos: [-1.78, 1.15, 0.52], color: CYAN,      active: !!((b1>>0)&1) },      // L1
          { pos: [ 1.78, 1.15, 0.52], color: ORANGE,    active: !!((b1>>1)&1) },      // R1
          { pos: [ 1.74, 0.08,-0.24], color: CYAN,      active: !!((b0>>5)&1) },      // Cross
          { pos: [ 2.08, 0.26, 0.06], color: RED,       active: !!((b0>>6)&1) },      // Circle
          { pos: [ 1.34, 0.26, 0.06], color: '#b040ff', active: !!((b0>>4)&1) },      // Square
          { pos: [ 1.74, 0.48, 0.15], color: GREEN,     active: !!((b0>>7)&1) },      // Triangle
        ]
        return defs.map((d, i) => (
          <ButtonGlow key={i} position={d.pos} active={d.active} color={d.color} />
        ))
      })()}

      {/* Floor ground shadow */}
      <ContactShadows
        position={[0, -2.8, 0]}
        opacity={0.40} scale={12} blur={3.0} far={4}
        color="#000000"
      />
    </group>
  )
}

// Preload GLB at module init — avoids loading spinner on first mount
useGLTF.preload('/assets/controller.glb')

// ---------------------------------------------------------------------------
// IBIHeartbeat — canvas showing organic IBI rhythm vs bot mechanical grid
// ---------------------------------------------------------------------------
function IBIHeartbeat({ ibiSnapshot }) {
  const canvasRef = useRef()

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !ibiSnapshot) return
    const ctx = canvas.getContext('2d')
    const W = canvas.width, H = canvas.height
    ctx.clearRect(0, 0, W, H)

    ctx.strokeStyle = 'rgba(255,45,85,0.25)'
    ctx.setLineDash([3, 6])
    ctx.lineWidth = 0.8
    const gridStep = W / 8
    for (let x = gridStep; x < W; x += gridStep) {
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke()
    }
    ctx.setLineDash([])

    const buttonOrder = ['r2', 'cross', 'l2', 'triangle']
    const colors = [ORANGE, CYAN, '#00ff88', '#ff9500']
    const rowH = H / 4 - 4

    buttonOrder.forEach((btn, bi) => {
      const ibis = ibiSnapshot[btn] || []
      if (!ibis.length) return
      const maxIBI = Math.max(...ibis, 500)
      const y0 = bi * (rowH + 4) + 2
      ibis.forEach((ibi, i) => {
        const x = (i / ibis.length) * W
        const h = (ibi / maxIBI) * rowH
        ctx.fillStyle = colors[bi] + 'cc'
        ctx.fillRect(x, y0 + rowH - h, W / ibis.length - 1, h)
      })
    })

    ctx.fillStyle = '#5a6a74'
    ctx.font = '8px JetBrains Mono, monospace'
    ctx.fillText('IBI BIOMETRIC HEARTBEAT', 4, H - 4)
  }, [ibiSnapshot])

  return (
    <canvas ref={canvasRef} width={300} height={120}
      style={{ width: '100%', display: 'block', borderTop: `1px solid rgba(255,107,0,0.2)` }} />
  )
}

// ---------------------------------------------------------------------------
// BiometricRadar — Phase 60A: 12-spoke fingerprint radar chart
// ---------------------------------------------------------------------------
function BiometricRadar({ meanJson }) {
  const canvasRef = useRef()

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    const W = canvas.width, H = canvas.height
    const cx = W / 2, cy = H / 2 + 4
    const R = Math.min(cx, cy) - 28
    const N = 13   // Phase 81: +entropy_variance at index 12
    ctx.clearRect(0, 0, W, H)

    // Reference rings
    for (let ri = 1; ri <= 4; ri++) {
      ctx.beginPath()
      for (let i = 0; i < N; i++) {
        const angle = (i / N) * Math.PI * 2 - Math.PI / 2
        const x = cx + Math.cos(angle) * R * (ri / 4)
        const y = cy + Math.sin(angle) * R * (ri / 4)
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)
      }
      ctx.closePath()
      ctx.strokeStyle = `rgba(0,212,255,${0.06 + ri * 0.03})`
      ctx.lineWidth = 0.5
      ctx.stroke()
    }

    // Spokes and labels
    for (let i = 0; i < N; i++) {
      const angle = (i / N) * Math.PI * 2 - Math.PI / 2
      const isZero = FEATURE_ZERO_IDX.has(i)
      const x1 = cx + Math.cos(angle) * R
      const y1 = cy + Math.sin(angle) * R
      ctx.beginPath()
      ctx.moveTo(cx, cy)
      ctx.lineTo(x1, y1)
      ctx.strokeStyle = isZero ? 'rgba(61,80,96,0.3)' : 'rgba(0,212,255,0.12)'
      ctx.lineWidth = 0.8
      ctx.stroke()
      const lx = cx + Math.cos(angle) * (R + 10)
      const ly = cy + Math.sin(angle) * (R + 10)
      ctx.fillStyle = isZero ? '#2a3540' : '#4a5a64'
      ctx.font = '6px JetBrains Mono, monospace'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(BIO_FEATURES[i].slice(0, 9), lx, ly)
    }

    // Player fingerprint polygon
    const vals = meanJson ? JSON.parse(meanJson) : null
    if (vals && vals.length >= 12) {
      ctx.beginPath()
      let started = false
      for (let i = 0; i < N; i++) {
        const angle = (i / N) * Math.PI * 2 - Math.PI / 2
        const norm = FEATURE_ZERO_IDX.has(i) ? 0 : Math.min(Math.abs(vals[i]) / BIO_NORM[i], 1)
        const x = cx + Math.cos(angle) * R * norm
        const y = cy + Math.sin(angle) * R * norm
        if (!started) { ctx.moveTo(x, y); started = true } else ctx.lineTo(x, y)
      }
      ctx.closePath()
      ctx.fillStyle = 'rgba(255,107,0,0.12)'
      ctx.fill()
      ctx.strokeStyle = ORANGE
      ctx.lineWidth = 1.5
      ctx.stroke()

      // Dot at each active spoke tip
      for (let i = 0; i < N; i++) {
        if (FEATURE_ZERO_IDX.has(i)) continue
        const angle = (i / N) * Math.PI * 2 - Math.PI / 2
        const norm = Math.min(Math.abs(vals[i]) / BIO_NORM[i], 1)
        const x = cx + Math.cos(angle) * R * norm
        const y = cy + Math.sin(angle) * R * norm
        ctx.beginPath()
        ctx.arc(x, y, 2, 0, Math.PI * 2)
        ctx.fillStyle = ORANGE
        ctx.fill()
      }
    } else {
      // No data placeholder
      ctx.fillStyle = DIM
      ctx.font = '8px JetBrains Mono, monospace'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText('NO FINGERPRINT DATA', cx, cy)
      ctx.fillStyle = '#2a3540'
      ctx.font = '7px JetBrains Mono, monospace'
      ctx.fillText('(requires ≥5 calibrated sessions)', cx, cy + 14)
    }

    ctx.fillStyle = '#3d5060'
    ctx.font = '7px JetBrains Mono, monospace'
    ctx.textAlign = 'left'
    ctx.textBaseline = 'top'
    ctx.fillText('BIOMETRIC FINGERPRINT · 13 FEATURES · 11 ACTIVE', 4, 2)
  }, [meanJson])

  return (
    <canvas ref={canvasRef} width={300} height={260}
      style={{ width: '100%', display: 'block' }} />
  )
}

// ---------------------------------------------------------------------------
// L5RhythmOverlay — Phase 60A: temporal rhythm oracle visualization
// ---------------------------------------------------------------------------
function L5RhythmOverlay({ record }) {
  const l5Cv      = record?.pitl_l5_cv
  const l5Entropy = record?.pitl_l5_entropy
  const l5Quant   = record?.pitl_l5_quant
  const humanity  = record?.l5_rhythm_humanity

  // L5 thresholds (N=74 calibration)
  const CV_THRESH      = 0.08
  const ENTROPY_THRESH = 1.0

  const buttons    = ['r2', 'cross', 'l2', 'triangle']
  const btnColors  = [ORANGE, CYAN, GREEN, '#ff9500']
  const btnLabels  = ['R2 (SPRINT)', 'CROSS', 'L2', 'TRIANGLE']

  const isCvDict = l5Cv && typeof l5Cv === 'object' && !Array.isArray(l5Cv)

  return (
    <div style={{ padding: '8px 10px', fontFamily: 'JetBrains Mono, monospace' }}>
      <div style={{ fontSize: 8, color: CYAN, marginBottom: 8, letterSpacing: '0.1em' }}>
        L5 TEMPORAL RHYTHM ORACLE
      </div>

      {/* Entropy gauge */}
      <div style={{ marginBottom: 8 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
          <span style={{ fontSize: 7, color: DIM }}>IPI ENTROPY</span>
          <span style={{ fontSize: 7, color: l5Entropy != null && l5Entropy < ENTROPY_THRESH ? RED : '#c4cdd6' }}>
            {l5Entropy != null ? l5Entropy.toFixed(3) + ' bits' : '—'}
            {l5Entropy != null && l5Entropy < ENTROPY_THRESH && <span style={{ color: RED }}> ▼BOT</span>}
          </span>
        </div>
        <div style={{ background: '#0d1a24', height: 7, borderRadius: 2, overflow: 'hidden', position: 'relative' }}>
          <div style={{
            width: `${Math.min((l5Entropy ?? 0) / 3 * 100, 100)}%`,
            height: '100%',
            background: l5Entropy != null && l5Entropy < ENTROPY_THRESH ? RED : GREEN,
            transition: 'width 0.6s ease',
          }} />
          {/* Threshold marker */}
          <div style={{
            position: 'absolute', top: 0, bottom: 0,
            left: `${ENTROPY_THRESH / 3 * 100}%`,
            width: 1, background: ORANGE, opacity: 0.6,
          }} />
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 6, color: '#2a3540', marginTop: 1 }}>
          <span>0</span><span style={{ color: '#3d5060' }}>▲{ENTROPY_THRESH}</span><span>3 bits</span>
        </div>
      </div>

      {/* Per-button CV bars */}
      <div style={{ fontSize: 7, color: DIM, marginBottom: 4 }}>INTER-PRESS INTERVAL CV</div>
      {buttons.map((btn, bi) => {
        const cv = isCvDict ? l5Cv[btn] : (bi === 0 && l5Cv != null ? Number(l5Cv) : null)
        if (cv == null) return (
          <div key={btn} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
            <span style={{ fontSize: 6, color: btnColors[bi], width: 52, flexShrink: 0 }}>{btnLabels[bi]}</span>
            <span style={{ fontSize: 6, color: '#2a3540' }}>—</span>
          </div>
        )
        const anomaly = cv < CV_THRESH
        return (
          <div key={btn} style={{ marginBottom: 4 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ fontSize: 6, color: btnColors[bi], width: 52, flexShrink: 0 }}>{btnLabels[bi]}</span>
              <div style={{ flex: 1, background: '#0d1a24', height: 5, borderRadius: 2, overflow: 'hidden', position: 'relative' }}>
                <div style={{
                  width: `${Math.min(cv / 2 * 100, 100)}%`,
                  height: '100%',
                  background: anomaly ? RED : btnColors[bi],
                  transition: 'width 0.6s ease',
                }} />
                <div style={{
                  position: 'absolute', top: 0, bottom: 0,
                  left: `${CV_THRESH / 2 * 100}%`,
                  width: 1, background: '#5a6a74', opacity: 0.5,
                }} />
              </div>
              <span style={{ fontSize: 6, color: anomaly ? RED : '#c4cdd6', width: 32, textAlign: 'right', flexShrink: 0 }}>
                {cv.toFixed(3)}
              </span>
            </div>
          </div>
        )
      })}

      {/* Status flags */}
      <div style={{ marginTop: 6, borderTop: `1px solid ${DIM}22`, paddingTop: 6 }}>
        <div style={{ display: 'flex', gap: 12 }}>
          <div style={{ fontSize: 7, color: l5Quant ? RED : DIM }}>
            {l5Quant ? '● QUANT DETECT' : '○ QUANT CLEAN'}
          </div>
          {humanity != null && (
            <div style={{ fontSize: 7, color: '#c4cdd6' }}>
              L5 HUMAN: <span style={{ color: humanity > 0.5 ? GREEN : RED }}>
                {(humanity * 100).toFixed(0)}%
              </span>
            </div>
          )}
        </div>
        <div style={{ fontSize: 7, color: DIM, marginTop: 3 }}>
          PRIORITY: R2 &gt; CROSS &gt; L2 &gt; TRIANGLE (ncaa_cfb_26)
        </div>
        <div style={{ fontSize: 7, color: DIM }}>
          THRESHOLD: CV &lt; {CV_THRESH} | ENTROPY &lt; {ENTROPY_THRESH} bits
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// BiometricScatter — Phase 60A/61: 2D feature cross-section + history dots
// ---------------------------------------------------------------------------
function BiometricScatter({ snap, history = [] }) {
  const canvasRef  = useRef()
  const meanJson   = snap?.biometric_fingerprint?.mean_json
  const nSessions  = snap?.biometric_fingerprint?.n_sessions ?? 0

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    const W = canvas.width, H = canvas.height
    const MARGIN = 28
    const W_ = W - MARGIN * 2
    const H_ = H - MARGIN * 2

    // Feature axes: X = micro_tremor_accel_variance (idx 3), Y = IBI jitter (idx 11)
    // Calibration stats from N=74 hardware sessions:
    //   micro_tremor mean ~278k LSB², human range 50k–600k
    //   IBI jitter human 0.001–0.05 s²
    const X_MAX = 650000
    const Y_MAX = 0.06
    const toX = v => MARGIN + Math.min(Math.max(v / X_MAX, 0), 1) * W_
    const toY = v => H - MARGIN - Math.min(Math.max(v / Y_MAX, 0), 1) * H_

    ctx.clearRect(0, 0, W, H)

    // Grid lines
    ctx.strokeStyle = 'rgba(0,212,255,0.07)'
    ctx.lineWidth = 0.5
    for (let i = 1; i <= 4; i++) {
      ctx.beginPath(); ctx.moveTo(toX(X_MAX * i / 4), MARGIN); ctx.lineTo(toX(X_MAX * i / 4), H - MARGIN); ctx.stroke()
      ctx.beginPath(); ctx.moveTo(MARGIN, toY(Y_MAX * i / 4)); ctx.lineTo(W - MARGIN, toY(Y_MAX * i / 4)); ctx.stroke()
    }

    // Axes
    ctx.strokeStyle = 'rgba(61,80,96,0.5)'
    ctx.lineWidth = 0.8
    ctx.beginPath(); ctx.moveTo(MARGIN, H - MARGIN); ctx.lineTo(W - MARGIN, H - MARGIN); ctx.stroke()
    ctx.beginPath(); ctx.moveTo(MARGIN, MARGIN); ctx.lineTo(MARGIN, H - MARGIN); ctx.stroke()

    // Bot zone (near-zero both axes: macro-timed bot has no tremor and no IBI jitter)
    const botZoneR = W_ * 0.09
    ctx.fillStyle = 'rgba(255,45,85,0.07)'
    ctx.beginPath(); ctx.arc(toX(X_MAX * 0.04), toY(Y_MAX * 0.02), botZoneR, 0, Math.PI * 2); ctx.fill()
    ctx.strokeStyle = 'rgba(255,45,85,0.3)'
    ctx.lineWidth = 0.8
    ctx.setLineDash([2, 4])
    ctx.beginPath(); ctx.arc(toX(X_MAX * 0.04), toY(Y_MAX * 0.02), botZoneR, 0, Math.PI * 2); ctx.stroke()
    ctx.setLineDash([])
    ctx.fillStyle = '#5a2030'
    ctx.font = '6px JetBrains Mono, monospace'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'top'
    ctx.fillText('BOT', toX(X_MAX * 0.04), toY(Y_MAX * 0.02) + botZoneR + 2)

    // Human calibration ellipse (N=74, centroid approximated from hardware session stats)
    // L4 dist_mean=2.083, dist_std=1.642 — ellipse represents ~2σ human zone
    const calCx = X_MAX * 0.43, calCy = Y_MAX * 0.38
    const eW = W_ * 0.40, eH = H_ * 0.44
    ctx.strokeStyle = 'rgba(0,255,136,0.3)'
    ctx.lineWidth = 1
    ctx.setLineDash([3, 5])
    ctx.beginPath(); ctx.ellipse(toX(calCx), toY(calCy), eW / 2, eH / 2, 0, 0, Math.PI * 2); ctx.stroke()
    ctx.setLineDash([])
    ctx.fillStyle = 'rgba(0,255,136,0.05)'
    ctx.beginPath(); ctx.ellipse(toX(calCx), toY(calCy), eW / 2, eH / 2, 0, 0, Math.PI * 2); ctx.fill()
    ctx.fillStyle = 'rgba(0,255,136,0.45)'
    ctx.font = '6px JetBrains Mono, monospace'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'bottom'
    ctx.fillText('HUMAN 2σ  (N=74)', toX(calCx), toY(calCy) - eH / 2 - 2)

    // Player fingerprint dot
    if (meanJson) {
      const vals = JSON.parse(meanJson)
      if (vals.length >= 12) {
        const px = vals[3]   // micro_tremor_accel_variance
        const py = vals[11]  // press_timing_jitter_variance
        const dotX = toX(px), dotY = toY(py)
        // Glow ring
        const grad = ctx.createRadialGradient(dotX, dotY, 0, dotX, dotY, 14)
        grad.addColorStop(0, ORANGE + 'aa')
        grad.addColorStop(1, ORANGE + '00')
        ctx.fillStyle = grad
        ctx.beginPath(); ctx.arc(dotX, dotY, 14, 0, Math.PI * 2); ctx.fill()
        // Dot
        ctx.fillStyle = ORANGE
        ctx.beginPath(); ctx.arc(dotX, dotY, 4.5, 0, Math.PI * 2); ctx.fill()
        // Label
        ctx.fillStyle = ORANGE
        ctx.font = '7px JetBrains Mono, monospace'
        ctx.textAlign = 'left'
        ctx.textBaseline = 'middle'
        ctx.fillText(`PLAYER (${nSessions}s)`, dotX + 7, dotY)
      }
    } else {
      ctx.fillStyle = DIM
      ctx.font = '8px JetBrains Mono, monospace'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText('NO FINGERPRINT — NEEDS SESSIONS', W / 2, H / 2)
    }

    // Phase 61: history dots — actual device DB records (cyan, semi-transparent)
    if (history.length) {
      history.forEach((rec) => {
        if (!rec.features || rec.features.length < 12) return
        const hx = toX(rec.features[3])   // micro_tremor_accel_variance
        const hy = toY(rec.features[11])  // press_timing_jitter_variance
        ctx.fillStyle = CYAN + '66'
        ctx.beginPath(); ctx.arc(hx, hy, 2.5, 0, Math.PI * 2); ctx.fill()
      })
      ctx.fillStyle = CYAN + '88'
      ctx.font = '6px JetBrains Mono, monospace'
      ctx.textAlign = 'right'
      ctx.textBaseline = 'top'
      ctx.fillText(`\u25cf ${history.length} DEVICE RECORDS`, W - MARGIN, MARGIN + 8)
    }

    // Axis labels
    ctx.fillStyle = '#3d5060'
    ctx.font = '6px JetBrains Mono, monospace'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'bottom'
    ctx.fillText('MICRO TREMOR VARIANCE (idx 3) →', W / 2, H - 1)
    ctx.save()
    ctx.translate(8, H / 2)
    ctx.rotate(-Math.PI / 2)
    ctx.textBaseline = 'top'
    ctx.fillText('IBI JITTER VAR (idx 11) →', 0, 0)
    ctx.restore()

    // Corner note
    ctx.fillStyle = '#2a3540'
    ctx.font = '6px JetBrains Mono, monospace'
    ctx.textAlign = 'right'
    ctx.textBaseline = 'top'
    ctx.fillText('sep ratio 0.362 — intra-player only', W - 2, 2)
  }, [meanJson, nSessions, history])

  return (
    <canvas ref={canvasRef} width={300} height={220}
      style={{ width: '100%', display: 'block' }} />
  )
}

// ---------------------------------------------------------------------------
// ProofShareQR — Phase 60A: QR code modal for sharing proof deeplink
// ---------------------------------------------------------------------------
function ProofShareQR({ record, deviceId: propDeviceId }) {
  const [showQR,  setShowQR]  = useState(false)
  const [qrUrl,   setQrUrl]   = useState(null)
  const [copied,  setCopied]  = useState(false)

  const txHash      = record?.tx_hash
  const explorerUrl = txHash
    ? `https://testnet.iotexscan.io/action/${txHash}`
    : null
  const twinUrl = `${window.location.origin}${window.location.pathname}?device=${propDeviceId || DEVICE_ID}`

  useEffect(() => {
    if (!showQR) return
    const target = explorerUrl || twinUrl
    QRCode.toDataURL(target, {
      width: 160, margin: 1,
      color: { dark: '#ff6b00', light: '#030507' },
    }).then(setQrUrl).catch(() => setQrUrl(null))
  }, [showQR, explorerUrl, twinUrl])

  const handleCopy = () => {
    navigator.clipboard.writeText(twinUrl).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <>
      <button onClick={() => setShowQR(true)}
        style={{ width: '100%', fontSize: 8, background: 'none',
                 border: `1px solid ${ORANGE}44`, borderRadius: 2,
                 color: ORANGE, padding: '4px 0', cursor: 'pointer',
                 fontFamily: 'JetBrains Mono, monospace',
                 letterSpacing: '0.1em', marginTop: 8 }}>
        SHARE PROOF ↗
      </button>

      {showQR && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(3,5,7,0.93)',
                      zIndex: 200, display: 'flex', alignItems: 'center',
                      justifyContent: 'center' }}
          onClick={() => setShowQR(false)}>
          <div style={{ background: '#080f14', border: `1px solid ${ORANGE}44`,
                        borderRadius: 6, padding: 20, width: 300,
                        fontFamily: 'JetBrains Mono, monospace' }}
            onClick={e => e.stopPropagation()}>
            <div style={{ color: ORANGE, fontSize: 11, letterSpacing: '0.15em', marginBottom: 12 }}>
              VAPI PROOF SHARE
            </div>

            {/* QR Code */}
            {qrUrl ? (
              <img src={qrUrl} style={{ width: 160, height: 160, display: 'block',
                                        margin: '0 auto 12px', imageRendering: 'pixelated' }} alt="QR" />
            ) : (
              <div style={{ width: 160, height: 160, margin: '0 auto 12px', background: '#0d1a24',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            fontSize: 8, color: DIM }}>
                GENERATING…
              </div>
            )}

            {/* IoTeX chain link */}
            {explorerUrl && (
              <div style={{ marginBottom: 8 }}>
                <div style={{ fontSize: 7, color: CYAN, marginBottom: 3 }}>IoTeX CHAIN RECORD</div>
                <a href={explorerUrl} target="_blank" rel="noopener noreferrer"
                  style={{ fontSize: 7, color: ORANGE, wordBreak: 'break-all', textDecoration: 'none' }}>
                  {explorerUrl}
                </a>
              </div>
            )}

            {/* Record hash */}
            {record?.record_hash && (
              <div style={{ marginBottom: 8 }}>
                <div style={{ fontSize: 7, color: CYAN, marginBottom: 2 }}>SHA-256 RECORD HASH</div>
                <div style={{ fontSize: 7, color: '#c4cdd6', wordBreak: 'break-all', lineHeight: 1.4 }}>
                  {record.record_hash}
                </div>
              </div>
            )}

            {/* Humanity */}
            {record && (
              <div style={{ fontSize: 8, color: '#c4cdd6', marginBottom: 12 }}>
                HUMANITY: <span style={{ color: (record.humanity_prob ?? 0) > 0.5 ? GREEN : RED }}>
                  {((record.humanity_prob ?? 0) * 100).toFixed(1)}%
                </span>
                {' · '}L4: {record.pitl_l4_distance?.toFixed(3) ?? '—'}
              </div>
            )}

            <button onClick={handleCopy}
              style={{ width: '100%', fontSize: 8, background: 'none',
                       border: `1px solid ${ORANGE}44`, borderRadius: 2,
                       color: copied ? GREEN : ORANGE, padding: '5px 0',
                       cursor: 'pointer', fontFamily: 'inherit', marginBottom: 6 }}>
              {copied ? 'COPIED ✓' : 'COPY TWIN PAGE URL'}
            </button>
            <button onClick={() => setShowQR(false)}
              style={{ width: '100%', fontSize: 8, background: 'none',
                       border: `1px solid ${DIM}`, borderRadius: 2,
                       color: DIM, padding: '5px 0', cursor: 'pointer',
                       fontFamily: 'inherit' }}>
              CLOSE
            </button>
          </div>
        </div>
      )}
    </>
  )
}

// ---------------------------------------------------------------------------
// AgentIntelPanel — Phase 79–81: live agent intelligence status
// Shows: Class J ML-bot risk, Validation Gate progress, LiveMode checklist, Federation
// ---------------------------------------------------------------------------
function AgentIntelPanel({ gate, liveMode, federation, ruling, mode }) {
  const ev        = ruling?.evidence_summary ?? {}
  const classJRisk = ev.class_j_ml_bot_risk ?? null
  const classJEntr = ev.class_j_entropy_variance ?? null
  const mlBotCand  = ev.ml_bot_candidate ?? false

  const riskColor = classJRisk === 'HIGH' ? RED
    : classJRisk === 'MEDIUM' ? ORANGE
    : classJRisk === 'LOW' ? GREEN : DIM

  const gateN     = gate?.gate_n ?? 100
  const gateClean = gate?.consecutive_clean ?? 0
  const gatePass  = gate?.gate_passed ?? false
  const divRate   = gate?.divergence_rate ?? null

  const liveModeReady = liveMode?.ready_for_live_mode ?? false
  const isDryRun      = liveMode?.current_dry_run ?? true
  const conditions    = liveMode?.conditions ?? {}
  const condKeys      = Object.keys(conditions)

  const peerCount = Array.isArray(federation) ? federation.length
    : (federation?.peers ? federation.peers.length : 0)

  return (
    <div style={{
      position: 'absolute', right: 12, top: 390,
      width: 248,
      background: 'rgba(5,9,14,0.97)',
      border: `1px solid ${mlBotCand ? RED : CYAN}1e`,
      borderLeft: `2px solid ${mlBotCand ? RED : CYAN}55`,
      borderRadius: 5,
      fontFamily: 'JetBrains Mono, monospace',
      overflow: 'hidden',
      boxShadow: `0 0 32px rgba(0,0,0,0.55)`,
      animation: 'fadeIn 0.5s ease',
    }}>

      {/* Header */}
      <div style={{
        padding: '6px 10px', background: `${CYAN}08`,
        borderBottom: `1px solid ${CYAN}18`,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <span style={{ fontSize: 7, color: CYAN, letterSpacing: '0.14em', fontWeight: 700 }}>
          AGENT INTELLIGENCE · 28 ACTIVE
        </span>
        <span style={{ fontSize: 6, color: isDryRun ? ORANGE : GREEN }}>
          {isDryRun ? 'DRY-RUN MODE' : '● LIVE ENFORCE'}
        </span>
      </div>

      {/* Class J ML-Bot Risk (Phase 81) */}
      <div style={{ padding: '5px 10px 5px', borderBottom: `1px solid rgba(61,80,96,0.12)` }}>
        <div style={{ fontSize: 6, color: '#3d5060', letterSpacing: '0.1em', marginBottom: 3 }}>
          CLASS J ML-BOT RISK · PHASE 81
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{
            fontSize: 9, color: riskColor, fontWeight: 700,
            textShadow: classJRisk === 'HIGH' ? `0 0 8px ${RED}` : 'none',
          }}>
            {classJRisk ?? (mode === 'LIVE' ? 'POLLING…' : '—')}
          </span>
          {classJEntr != null && (
            <span style={{ fontSize: 6.5, color: '#5a6a74' }}>
              EV {classJEntr.toFixed(4)}
            </span>
          )}
          {mlBotCand && (
            <span style={{
              fontSize: 5.5, color: RED, padding: '1px 4px',
              border: `1px solid ${RED}55`, borderRadius: 2,
            }}>
              ML-BOT CANDIDATE
            </span>
          )}
        </div>
        <div style={{ fontSize: 5.5, color: '#2a3540', marginTop: 2 }}>
          human &gt;0.15 · ambiguous 0.05–0.15 · GaussianHMM bot &lt;0.02
        </div>
      </div>

      {/* Validation Gate (Phase 75–78) */}
      <div style={{ padding: '5px 10px 5px', borderBottom: `1px solid rgba(61,80,96,0.12)` }}>
        <div style={{ fontSize: 6, color: '#3d5060', letterSpacing: '0.1em', marginBottom: 4 }}>
          VALIDATION GATE · PHASE 75–78
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
          <span style={{ fontSize: 8, color: gatePass ? GREEN : ORANGE, fontWeight: 700 }}>
            {gatePass ? 'PASSED' : `${gateClean} / ${gateN}`}
          </span>
          {divRate != null && (
            <span style={{ fontSize: 6.5, color: divRate > 0.10 ? RED : '#5a6a74' }}>
              DIV {(divRate * 100).toFixed(1)}%
            </span>
          )}
        </div>
        <div style={{ height: 3, background: '#0d1a24', borderRadius: 2, overflow: 'hidden' }}>
          <div style={{
            width: `${Math.min(gateClean / gateN, 1) * 100}%`,
            height: '100%',
            background: gatePass ? GREEN : ORANGE,
            transition: 'width 0.6s ease',
            boxShadow: `0 0 4px ${gatePass ? GREEN : ORANGE}66`,
          }} />
        </div>
        <div style={{ fontSize: 5.5, color: '#2a3540', marginTop: 2 }}>
          N≥{gateN} consecutive non-divergent · divergence_rate ≤ max
        </div>
      </div>

      {/* Live Mode Checklist (Phase 79) */}
      <div style={{ padding: '5px 10px 5px', borderBottom: `1px solid rgba(61,80,96,0.12)` }}>
        <div style={{ fontSize: 6, color: '#3d5060', letterSpacing: '0.1em', marginBottom: 4 }}>
          LIVE MODE CHECKLIST · PHASE 79
        </div>
        {condKeys.length > 0 ? condKeys.map(k => (
          <div key={k} style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 2 }}>
            <span style={{ fontSize: 7.5, color: conditions[k] ? GREEN : ORANGE, width: 10, flexShrink: 0 }}>
              {conditions[k] ? '✓' : '✗'}
            </span>
            <span style={{ fontSize: 6, color: conditions[k] ? '#5a6a74' : '#8a7a4a' }}>
              {k.replace(/_/g, ' ')}
            </span>
          </div>
        )) : (
          <div style={{ fontSize: 6, color: '#2a3540' }}>
            {mode === 'LIVE' ? 'POLLING…' : '— offline'}
          </div>
        )}
        {condKeys.length > 0 && (
          <div style={{
            fontSize: 6, marginTop: 4,
            color: liveModeReady ? GREEN : '#3d5060',
            fontWeight: liveModeReady ? 700 : 400,
          }}>
            {liveModeReady
              ? 'READY — operator action required'
              : 'NOT READY — conditions pending'}
          </div>
        )}
      </div>

      {/* Federation (Phase 80) */}
      <div style={{ padding: '5px 10px 6px' }}>
        <div style={{ fontSize: 6, color: '#3d5060', letterSpacing: '0.1em', marginBottom: 3 }}>
          FEDERATION · PHASE 80
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 8, color: peerCount > 0 ? CYAN : DIM }}>
            {peerCount > 0 ? `${peerCount} PEER${peerCount > 1 ? 'S' : ''}` : 'ISOLATED'}
          </span>
          <span style={{ fontSize: 5.5, color: '#3d5060' }}>
            &lt;100ms BLOCK broadcast · 150× speedup
          </span>
        </div>
        <div style={{ fontSize: 5.5, color: '#2a3540', marginTop: 2 }}>
          HMAC-SHA256 · FederatedThreatRegistry.sol LIVE
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// ProofOfHumannessCard — Phase 81 W2: streamable 400×120 broadcast overlay
// Canvas compositing: mini humanity arc + PoAC chain tail + inference badge
// Designed for stream capture / broadcast embedding
// ---------------------------------------------------------------------------
function ProofOfHumannessCard({ record, chain }) {
  const canvasRef = useRef()
  const humanity  = record?.humanity_prob ?? null
  const l4d       = record?.pitl_l4_distance ?? null
  const inf       = record?.inference ?? 0x20
  const recentChain = chain.slice(0, 8)

  const INF_SHORT = {
    0x20: ['PASS',   GREEN  ],
    0x28: ['INJECT', RED    ],
    0x29: ['WALL',   RED    ],
    0x2A: ['AIMBOT', RED    ],
    0x2B: ['T-BOT',  ORANGE ],
    0x30: ['BIO',    ORANGE ],
    0x31: ['IMU',    CYAN   ],
    0x32: ['STICK',  CYAN   ],
  }
  const [infShort, infColor] = INF_SHORT[inf] ?? [`0x${inf?.toString(16).toUpperCase()}`, DIM]

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    const W = 400, H = 120
    ctx.clearRect(0, 0, W, H)

    // Background
    ctx.fillStyle = 'rgba(3,5,7,0.97)'
    ctx.fillRect(0, 0, W, H)

    // Left accent bar — color by humanity
    const barColor = humanity == null ? DIM
      : humanity < 0.40 ? RED : humanity < 0.65 ? ORANGE : GREEN
    ctx.fillStyle = barColor
    ctx.fillRect(0, 0, 3, H)

    // ── Mini humanity arc ────────────────────────────────────────────────
    const cx = 68, cy = 72, R = 40
    const toRad = d => d * Math.PI / 180
    const arcPt = (deg, r = R) => ({ x: cx + r * Math.cos(toRad(deg)), y: cy + r * Math.sin(toRad(deg)) })
    const START = 150, SWEEP = 240
    const pct = Math.max(0, Math.min(1, humanity ?? 0.5))
    const bgS = arcPt(START)
    const fillEnd = arcPt(START + pct * SWEEP)
    const arcColor = (humanity ?? 0.5) < 0.40 ? RED : (humanity ?? 0.5) < 0.65 ? ORANGE : GREEN

    // BG track
    ctx.beginPath()
    ctx.arc(cx, cy, R, toRad(START), toRad(START + SWEEP), false)
    ctx.strokeStyle = '#0a141c'; ctx.lineWidth = 10; ctx.lineCap = 'round'; ctx.stroke()

    // Fill arc
    if (pct > 0.003) {
      ctx.beginPath()
      ctx.arc(cx, cy, R, toRad(START), toRad(START + pct * SWEEP), false)
      ctx.strokeStyle = arcColor; ctx.lineWidth = 10
      ctx.shadowColor = arcColor; ctx.shadowBlur = 8; ctx.stroke(); ctx.shadowBlur = 0
    }

    // Percentage readout
    ctx.fillStyle = humanity != null ? arcColor : DIM
    ctx.font = 'bold 24px JetBrains Mono, monospace'
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle'
    ctx.fillText(humanity != null ? `${(pct * 100).toFixed(0)}` : '—', cx, cy - 10)
    ctx.font = '7px JetBrains Mono, monospace'; ctx.fillStyle = '#3d5060'
    ctx.fillText('HUMAN', cx, cy + 10)

    // ── Center info block ────────────────────────────────────────────────
    const infoX = 132
    ctx.fillStyle = ORANGE
    ctx.font = 'bold 15px Rajdhani, sans-serif'
    ctx.textAlign = 'left'; ctx.textBaseline = 'top'
    ctx.fillText('VAPI', infoX, 10)

    ctx.fillStyle = '#3d5060'; ctx.font = '7px JetBrains Mono, monospace'
    ctx.fillText('PROOF OF HUMANNESS', infoX, 30)

    ctx.fillStyle = '#1e3048'; ctx.font = '6px JetBrains Mono, monospace'
    ctx.fillText('DualShock Edge CFI-ZCP1 · N=74 · 13-feature L4', infoX, 43)
    ctx.fillText(`L4 dist ${l4d?.toFixed(3) ?? '—'} · thr 7.009 · MPC 3×3 ✓`, infoX, 53)

    // Inference badge
    ctx.fillStyle = infColor + '20'
    ctx.fillRect(infoX, 65, 74, 17)
    ctx.strokeStyle = infColor + '55'; ctx.lineWidth = 0.8; ctx.strokeRect(infoX, 65, 74, 17)
    ctx.fillStyle = infColor; ctx.font = 'bold 7.5px JetBrains Mono, monospace'
    ctx.textBaseline = 'middle'; ctx.fillText(infShort, infoX + 4, 73.5)

    ctx.fillStyle = '#1a2840'; ctx.font = '6px JetBrains Mono, monospace'
    ctx.textBaseline = 'top'; ctx.fillText('IoTeX testnet · CeremonyRegistry LIVE', infoX, 88)

    // ── PoAC chain tail (last 8 records) ────────────────────────────────
    const chainX = 270, chainY = 52, dotR = 6.5, dotGap = 16
    ctx.fillStyle = '#3d5060'; ctx.font = '5.5px JetBrains Mono, monospace'
    ctx.textAlign = 'center'; ctx.textBaseline = 'top'
    ctx.fillText('PoAC CHAIN TAIL', chainX + 3.5 * dotGap, 12)
    ctx.fillStyle = '#1e3048'; ctx.fillText('(last 8 records)', chainX + 3.5 * dotGap, 21)

    recentChain.forEach((r, i) => {
      const dot = r.inference === 0x20 ? GREEN : r.inference === 0x30 ? ORANGE : RED
      const x = chainX + i * dotGap; const y = chainY
      // Chain link to next
      if (i < recentChain.length - 1) {
        ctx.beginPath(); ctx.moveTo(x + dotR, y); ctx.lineTo(x + dotGap - dotR, y)
        ctx.strokeStyle = '#1e2c38'; ctx.lineWidth = 1; ctx.stroke()
      }
      ctx.beginPath(); ctx.arc(x, y, dotR, 0, Math.PI * 2)
      ctx.fillStyle = dot + '28'; ctx.fill()
      ctx.beginPath(); ctx.arc(x, y, dotR, 0, Math.PI * 2)
      ctx.strokeStyle = dot; ctx.lineWidth = 1.5; ctx.stroke()
    })
    if (!recentChain.length) {
      ctx.fillStyle = '#2a3540'; ctx.font = '7px JetBrains Mono, monospace'
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle'
      ctx.fillText('AWAITING CHAIN', chainX + 3 * dotGap, chainY)
    }

    // ── AgentMessageBus event indicators ────────────────────────────────
    const busItems = [
      ['ceremon', CYAN   ],
      ['gate',    GREEN  ],
      ['block',   ORANGE ],
      ['class_j', RED    ],
    ]
    busItems.forEach(([label, color], i) => {
      const bx = chainX + i * 30; const by = 80
      ctx.beginPath(); ctx.arc(bx, by, 4, 0, Math.PI * 2)
      ctx.fillStyle = color + '33'; ctx.fill()
      ctx.beginPath(); ctx.arc(bx, by, 4, 0, Math.PI * 2)
      ctx.strokeStyle = color + '66'; ctx.lineWidth = 0.8; ctx.stroke()
      ctx.fillStyle = color + '77'; ctx.font = '5px JetBrains Mono, monospace'
      ctx.textAlign = 'center'; ctx.textBaseline = 'top'
      ctx.fillText(label, bx, by + 6)
    })
    ctx.fillStyle = '#2a3540'; ctx.font = '5.5px JetBrains Mono, monospace'
    ctx.textAlign = 'left'; ctx.textBaseline = 'top'
    ctx.fillText('AgentMessageBus events', chainX, 97)

    // BROADCAST watermark
    ctx.save(); ctx.globalAlpha = 0.04
    ctx.fillStyle = ORANGE; ctx.font = 'bold 26px Rajdhani, sans-serif'
    ctx.textAlign = 'right'; ctx.textBaseline = 'bottom'
    ctx.fillText('BROADCAST', W - 5, H - 4)
    ctx.restore()

    // Outer frame
    ctx.strokeStyle = 'rgba(255,107,0,0.14)'; ctx.lineWidth = 1
    ctx.strokeRect(0.5, 0.5, W - 1, H - 1)
  }, [humanity, l4d, inf, recentChain.length])

  return (
    <div style={{
      position: 'absolute',
      left: 340,
      bottom: 54,
      animation: 'fadeIn 0.6s ease',
    }}>
      <div style={{
        fontSize: 6, color: '#2a3540', fontFamily: 'JetBrains Mono, monospace',
        marginBottom: 3, letterSpacing: '0.1em',
      }}>
        STREAM OVERLAY · 400×120 · BROADCAST READY
      </div>
      <canvas ref={canvasRef} width={400} height={120}
        style={{ display: 'block', borderRadius: 3 }} />
    </div>
  )
}

// ---------------------------------------------------------------------------
// PoACHelix — DNA helix from chain records
// ---------------------------------------------------------------------------
function PoACHelix({ chain }) {
  const points = chain.slice(0, 30).map((r, i) => {
    const t = i / 30
    const angle = t * Math.PI * 4
    return new THREE.Vector3(
      Math.cos(angle) * (1.8 + 0.1 * i),
      t * 3 - 1.5,
      Math.sin(angle) * (1.8 + 0.1 * i),
    )
  })
  if (!points.length) return null
  return (
    <group>
      {chain.slice(0, 29).map((r, i) => {
        const color = r.inference === 0x20 ? GREEN : r.inference === 0x30 ? '#ff9500' : RED
        return (
          <mesh key={r.record_hash || i} position={points[i]}>
            <sphereGeometry args={[0.04, 8, 8]} />
            <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.8} />
          </mesh>
        )
      })}
    </group>
  )
}

// ---------------------------------------------------------------------------
// ProofAnchorPanel — top-right HTML overlay (with SHARE PROOF button)
// ---------------------------------------------------------------------------
function ProofAnchorPanel({ snap, record, mode, deviceId }) {
  if (!snap) return null
  const { ioid, passport, audit_log, anomaly_trend, calibration } = snap
  const trendColor = { IMPROVING: GREEN, STABLE: CYAN, DEGRADING: RED }[anomaly_trend] || DIM

  return (
    <div style={{
      position: 'absolute', right: 12, top: 62, width: 248,
      background: 'rgba(5,9,14,0.97)',
      border: `1px solid ${ORANGE}1e`,
      borderLeft: `2px solid ${CYAN}55`,
      borderRadius: 5,
      fontFamily: 'JetBrains Mono, monospace',
      overflow: 'hidden',
      boxShadow: `0 0 40px rgba(0,0,0,0.6), inset 0 0 0 1px rgba(255,255,255,0.018)`,
      animation: 'fadeIn 0.5s ease',
    }}>
      {/* Panel header */}
      <div style={{
        padding: '7px 12px', background: `${CYAN}08`,
        borderBottom: `1px solid ${CYAN}18`,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <span style={{ fontSize: 7.5, color: CYAN, letterSpacing: '0.16em', fontWeight: 700 }}>
          PROOF ANCHOR
        </span>
        <span style={{ fontSize: 6.5, color: mode === 'LIVE' ? GREEN : DIM }}>
          {mode === 'LIVE' ? '● LIVE' : '○ OFFLINE'}
        </span>
      </div>

      {/* Device Identity */}
      <div className="twin-section-label">DEVICE IDENTITY</div>
      <div style={{ padding: '4px 12px 8px', color: '#c4cdd6', fontSize: 8, wordBreak: 'break-all', lineHeight: 1.5 }}>
        {ioid?.did || <span style={{ color: DIM }}>— not registered</span>}
      </div>

      {/* ZK Passport */}
      <div className="twin-section-label">ZK PASSPORT</div>
      <div style={{ padding: '4px 12px 8px' }}>
        {passport?.issued ? (
          <div style={{ fontSize: 7.5, color: GREEN, lineHeight: 1.5 }}>
            ISSUED {passport.on_chain ? '· ON-CHAIN ✓' : '· LOCAL'}
            <div style={{ color: DIM, wordBreak: 'break-all', marginTop: 2 }}>
              {passport.passport_hash?.slice(0, 22)}…
            </div>
          </div>
        ) : (
          <div style={{ fontSize: 7.5, color: DIM }}>PENDING</div>
        )}
      </div>

      {/* L4 Profile */}
      <div className="twin-section-label">L4 BIOMETRIC PROFILE</div>
      <div style={{ padding: '4px 12px 8px', fontSize: 7.5, color: '#c4cdd6', lineHeight: 1.7 }}>
        <span style={{ color: DIM }}>THRESHOLD </span>{calibration?.anomaly_threshold?.toFixed(3) ?? '—'}<br />
        <span style={{ color: DIM }}>SESSIONS  </span>{calibration?.session_count ?? 0}<br />
        <span style={{ color: DIM }}>TREND     </span><span style={{ color: trendColor }}>{anomaly_trend ?? '—'}</span>
      </div>

      {/* Live Record */}
      {record && (
        <>
          <div className="twin-section-label">LIVE RECORD</div>
          <div style={{ padding: '4px 12px 8px', fontSize: 7.5, color: '#c4cdd6', lineHeight: 1.7 }}>
            <span style={{ color: DIM }}>L4 DIST  </span>{record.pitl_l4_distance?.toFixed(3) ?? '—'}<br />
            <span style={{ color: DIM }}>HUMANITY </span>
            <span style={{ color: (record.humanity_prob ?? 0) > 0.65 ? GREEN : (record.humanity_prob ?? 0) > 0.40 ? ORANGE : RED }}>
              {((record.humanity_prob ?? 0) * 100).toFixed(1)}%
            </span><br />
            <span style={{ color: DIM }}>HASH     </span>{record.record_hash?.slice(0, 14)}…
          </div>
        </>
      )}

      {/* Proof Queries */}
      {audit_log?.length > 0 && (
        <>
          <div className="twin-section-label">PROOF QUERIES ({audit_log.length})</div>
          <div style={{ padding: '4px 12px 8px' }}>
            {audit_log.slice(0, 3).map((e, i) => (
              <div key={i} style={{ fontSize: 6.5, color: DIM, marginBottom: 2, lineHeight: 1.5 }}>
                <span style={{ color: e.outcome === 'success' ? GREEN : ORANGE }}>
                  {e.outcome.toUpperCase()}
                </span> · {e.endpoint.replace('/operator/passport', '/passport')}
              </div>
            ))}
          </div>
        </>
      )}

      {/* Disclaimer */}
      <div style={{
        padding: '5px 12px 6px', fontSize: 6.5, color: '#2a3540', lineHeight: 1.5,
        borderTop: `1px solid rgba(61,80,96,0.12)`,
      }}>
        L4 intra-player only · separation ratio 0.362 · §8.6
      </div>

      {/* QR share button */}
      <div style={{ padding: '4px 12px 10px' }}>
        <ProofShareQR record={record} deviceId={deviceId} />
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// HumanityArcGauge — Phase 69: SVG arc speedometer (0–100% humanity)
// ---------------------------------------------------------------------------
function HumanityArcGauge({ humanity = 0.5, record }) {
  const W = 320, H = 170
  const cx = 160, cy = 108, R = 78
  // Arc: START=150° (lower-left) → SWEEP=240° clockwise → END=30° (lower-right)
  // At 50% needle is at 270° (straight up). Classic speedometer layout.
  const START = 150, SWEEP = 240
  const pct      = Math.max(0, Math.min(1, humanity))
  const fillSweep = pct * SWEEP
  const needleDeg = START + fillSweep
  const rad = d => d * Math.PI / 180
  const pt  = (deg, r = R) => ({
    x: (cx + r * Math.cos(rad(deg))).toFixed(2),
    y: (cy + r * Math.sin(rad(deg))).toFixed(2),
  })
  const bgS   = pt(START)
  const bgE   = pt(START + SWEEP)
  const fillE = pt(needleDeg)
  const needleTip = pt(needleDeg, R - 10)
  const fillLarge = fillSweep > 180 ? 1 : 0
  const color = pct < 0.40 ? RED : pct < 0.65 ? ORANGE : GREEN
  const l4d   = record?.pitl_l4_distance
  const inf   = record?.inference ?? 0x20
  const infLabel = { 0x20:'PASS', 0x28:'DRIVER INJECT', 0x29:'WALLHACK', 0x2A:'AIMBOT',
                     0x2B:'TEMPORAL BOT', 0x30:'BIO ANOMALY', 0x31:'IMU DECOUPLED', 0x32:'STICK DECOUPLED' }
  // Tri-color track segments: RED zone (0–33%), ORANGE (33–66%), GREEN (66–100%)
  const segs = [
    { from: 0,    to: 0.33, c: RED    + '40' },
    { from: 0.33, to: 0.66, c: ORANGE + '40' },
    { from: 0.66, to: 1.00, c: GREEN  + '40' },
  ]
  return (
    <svg width={W} height={H} style={{ display:'block', flexShrink:0 }}>
      {/* Background track */}
      <path d={`M ${bgS.x} ${bgS.y} A ${R} ${R} 0 1 1 ${bgE.x} ${bgE.y}`}
        fill="none" stroke="#0a141c" strokeWidth={15} strokeLinecap="round" />
      {/* Tri-color segment underlays */}
      {segs.map((s,i) => {
        const ss = pt(START + s.from * SWEEP)
        const se = pt(START + s.to   * SWEEP)
        const sw = (s.to - s.from) * SWEEP
        return <path key={i}
          d={`M ${ss.x} ${ss.y} A ${R} ${R} 0 ${sw>180?1:0} 1 ${se.x} ${se.y}`}
          fill="none" stroke={s.c} strokeWidth={15} strokeLinecap="round" />
      })}
      {/* Filled progress arc */}
      {pct > 0.003 && (
        <path d={`M ${bgS.x} ${bgS.y} A ${R} ${R} 0 ${fillLarge} 1 ${fillE.x} ${fillE.y}`}
          fill="none" stroke={color} strokeWidth={15} strokeLinecap="round" opacity={0.92}
          style={{ filter: `drop-shadow(0 0 6px ${color}88)` }} />
      )}
      {/* Tick marks at 25% intervals */}
      {[0, 0.25, 0.5, 0.75, 1.0].map((f,i) => {
        const a = START + f * SWEEP
        const inner = pt(a, R - 9)
        const outer = pt(a, R + 4)
        return <line key={i} x1={inner.x} y1={inner.y} x2={outer.x} y2={outer.y}
          stroke={f === 0 || f === 1 ? '#3d5060' : '#1e2c38'} strokeWidth={f === 0.5 ? 1.5 : 1} />
      })}
      {/* Needle */}
      <line x1={cx} y1={cy} x2={needleTip.x} y2={needleTip.y}
        stroke={color} strokeWidth={2.5} strokeLinecap="round"
        style={{ filter: `drop-shadow(0 0 3px ${color})` }} />
      {/* Center pivot */}
      <circle cx={cx} cy={cy} r={5} fill={color}
        style={{ filter: `drop-shadow(0 0 4px ${color})` }} />
      <circle cx={cx} cy={cy} r={2.5} fill="#030507" />
      {/* Main percentage readout */}
      <text x={cx} y={cy - 22} textAnchor="middle"
        fill={color} fontSize="38" fontFamily="JetBrains Mono, monospace" fontWeight="700"
        style={{ filter: `drop-shadow(0 0 8px ${color}66)` }}>
        {(pct * 100).toFixed(0)}
      </text>
      <text x={cx} y={cy - 7} textAnchor="middle"
        fill={DIM} fontSize="7.5" fontFamily="JetBrains Mono, monospace" letterSpacing="3">
        HUMANITY %
      </text>
      {/* L4 + inference badge */}
      <text x={cx} y={cy + 9} textAnchor="middle"
        fill="#3d5060" fontSize="7" fontFamily="JetBrains Mono, monospace">
        L4 {l4d?.toFixed(3) ?? '—'} · {infLabel[inf] ?? `0x${inf?.toString(16).toUpperCase()}`}
      </text>
      {/* Scale labels */}
      <text x={Number(bgS.x) - 7} y={Number(bgS.y) + 5} textAnchor="end"
        fill="#2a3540" fontSize="6.5" fontFamily="JetBrains Mono, monospace">0</text>
      <text x={cx} y={cy - R - 10} textAnchor="middle"
        fill="#2a3540" fontSize="6.5" fontFamily="JetBrains Mono, monospace">50</text>
      <text x={Number(bgE.x) + 7} y={Number(bgE.y) + 5} textAnchor="start"
        fill="#2a3540" fontSize="6.5" fontFamily="JetBrains Mono, monospace">100</text>
    </svg>
  )
}

// ---------------------------------------------------------------------------
// PITLLayerStack — Phase 69: 6-row live PITL layer status bars
// ---------------------------------------------------------------------------
function PITLLayerStack({ record, snap }) {
  const l4d    = record?.pitl_l4_distance ?? null
  const anomThr = snap?.calibration?.anomaly_threshold ?? 7.009
  const l5E    = record?.pitl_l5_entropy
  const l5Cv   = record?.pitl_l5_cv
  const l2bActive = record?.pitl_l2b_active
  const l6pFlag   = record?.l6p_flag
  const inf    = record?.inference ?? null
  const getL5CvVal = () => {
    if (l5Cv == null) return null
    if (typeof l5Cv === 'object' && !Array.isArray(l5Cv))
      return l5Cv.r2 ?? l5Cv.cross ?? Object.values(l5Cv)[0] ?? null
    return Number(l5Cv)
  }
  const cvVal = getL5CvVal()
  const layers = [
    { id:'L4',   label:'L4  MAHALANOBIS', bar: l4d != null ? Math.min(l4d/(anomThr*1.6),1) : 0,
      status: l4d==null?'WAIT': l4d>anomThr?'ANOMALY':'NOMINAL',
      val: l4d!=null?l4d.toFixed(3):'—',
      color: l4d==null?DIM: l4d>anomThr?RED:GREEN },
    { id:'L5E',  label:'L5  ENTROPY',    bar: l5E!=null?Math.min(l5E/3,1):0,
      status: l5E==null?'WAIT': l5E<1.0?'BOT':'HUMAN',
      val: l5E!=null?l5E.toFixed(3)+'b':'—',
      color: l5E==null?DIM: l5E<1.0?RED:GREEN },
    { id:'L5CV', label:'L5  RHYTHM CV',  bar: cvVal!=null?Math.min(cvVal/0.5,1):0,
      status: cvVal==null?'WAIT': cvVal<0.08?'BOT':'HUMAN',
      val: cvVal!=null?cvVal.toFixed(3):'—',
      color: cvVal==null?DIM: cvVal<0.08?RED:GREEN },
    { id:'L2B',  label:'L2B IMU CAUSAL', bar: l2bActive?0.78:0.12,
      status: l2bActive==null?'WAIT': l2bActive?'COUPLED':'DECOUPLED',
      val: l2bActive==null?'—': l2bActive?'ACTIVE':'INACTIVE',
      color: l2bActive==null?DIM: l2bActive?GREEN:RED },
    { id:'L2C',  label:'L2C STICK-IMU',  bar: 0,
      status:'DEAD ZONE', val:'(ncaa_cfb_26)', color:'#3d5060' },
    { id:'L6',   label:'L6  HAPTIC',     bar: l6pFlag?0.82:0,
      status: l6pFlag?'FLAGGED':'PASSIVE', val: l6pFlag?'TRIGGERED':'OFF',
      color: l6pFlag?ORANGE:DIM },
  ]
  return (
    <div style={{ padding:'7px 12px 8px', fontFamily:'JetBrains Mono, monospace' }}>
      <div style={{ display:'flex', justifyContent:'space-between', marginBottom:7 }}>
        <span style={{ fontSize:7.5, color:CYAN, letterSpacing:'0.1em' }}>PITL LAYER STATUS</span>
        {inf != null && (
          <span style={{ fontSize:7, color:'#5a6a74' }}>
            {`0x${inf.toString(16).toUpperCase().padStart(2,'0')}`}
          </span>
        )}
      </div>
      {layers.map(l => (
        <div key={l.id} style={{ marginBottom:5 }}>
          <div style={{ display:'flex', alignItems:'center', gap:6, marginBottom:2 }}>
            <span style={{ fontSize:6.5, color:l.color, width:88, flexShrink:0,
                           letterSpacing:'0.04em' }}>{l.label}</span>
            <span style={{ fontSize:6.5, color:l.color, width:62, flexShrink:0 }}>{l.status}</span>
            <span style={{ fontSize:6, color:'#3d5060', marginLeft:'auto', flexShrink:0 }}>{l.val}</span>
          </div>
          <div style={{ height:3.5, background:'#070e14', borderRadius:2, overflow:'hidden' }}>
            <div style={{
              width:`${l.bar*100}%`, height:'100%', background:l.color,
              transition:'width 0.45s ease',
              boxShadow: l.bar>0.05 ? `0 0 5px ${l.color}66` : 'none',
            }} />
          </div>
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// TriggerOscilloscope — Phase 69: rolling L2/R2 waveform (~3s window)
// ---------------------------------------------------------------------------
function TriggerOscilloscope({ frame }) {
  const canvasRef = useRef()
  const histRef   = useRef({ l2: new Array(200).fill(0), r2: new Array(200).fill(0) })
  const rafRef    = useRef()

  // Push new frame data into ring buffers
  useEffect(() => {
    const H = histRef.current
    H.l2.push((frame?.l2_trigger ?? 0) / 255);  H.l2.shift()
    H.r2.push((frame?.r2_trigger ?? 0) / 255);  H.r2.shift()
  }, [frame])

  // RAF draw loop — independent of React renders
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const draw = () => {
      const ctx = canvas.getContext('2d')
      const W = canvas.width, H = canvas.height
      const { l2, r2 } = histRef.current
      ctx.clearRect(0, 0, W, H)
      ctx.fillStyle = '#030810'
      ctx.fillRect(0, 0, W, H)
      // Grid
      ctx.strokeStyle = 'rgba(0,212,255,0.05)'
      ctx.lineWidth = 0.5
      for (let i = 1; i < 4; i++) {
        ctx.beginPath(); ctx.moveTo(0, H*i/4); ctx.lineTo(W, H*i/4); ctx.stroke()
      }
      for (let i = 1; i < 5; i++) {
        ctx.beginPath(); ctx.moveTo(W*i/5, 0); ctx.lineTo(W*i/5, H); ctx.stroke()
      }
      // Threshold line at 50%
      ctx.strokeStyle = `${ORANGE}22`; ctx.setLineDash([3,5])
      ctx.beginPath(); ctx.moveTo(0, H*0.5); ctx.lineTo(W, H*0.5); ctx.stroke()
      ctx.setLineDash([])
      // L2 wave (orange)
      const drawWave = (data, stroke) => {
        ctx.beginPath()
        data.forEach((v, i) => {
          const x = (i / (data.length-1)) * W
          const y = H - 3 - v * (H - 7)
          i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)
        })
        ctx.strokeStyle = stroke; ctx.lineWidth = 1.8
        ctx.shadowColor = stroke; ctx.shadowBlur = 5
        ctx.stroke(); ctx.shadowBlur = 0
        // Fill under curve
        ctx.lineTo(W, H); ctx.lineTo(0, H); ctx.closePath()
        ctx.fillStyle = stroke + '18'; ctx.fill()
      }
      drawWave(l2, ORANGE)
      drawWave(r2, CYAN)
      // Legend
      ctx.font = '7px JetBrains Mono, monospace'
      ctx.shadowBlur = 0
      ctx.fillStyle = ORANGE + 'cc'; ctx.textAlign = 'left'; ctx.fillText('L2', 5, H-5)
      ctx.fillStyle = CYAN + 'cc';   ctx.fillText('R2', 22, H-5)
      ctx.fillStyle = '#2a3540'; ctx.textAlign = 'right'
      ctx.fillText('~3s  1000Hz', W-5, H-5)
      rafRef.current = requestAnimationFrame(draw)
    }
    rafRef.current = requestAnimationFrame(draw)
    return () => cancelAnimationFrame(rafRef.current)
  }, [])

  return (
    <div>
      <div style={{ padding:'5px 12px 3px', fontSize:7.5, color:CYAN,
                    fontFamily:'JetBrains Mono, monospace', letterSpacing:'0.08em' }}>
        TRIGGER OSCILLOSCOPE · ANALOG L2 / R2
      </div>
      <canvas ref={canvasRef} width={320} height={72} style={{ width:'100%', display:'block' }} />
    </div>
  )
}

// ---------------------------------------------------------------------------
// VAPIConsolePanel — Phase 69: replaces tab panel with 3-section neural console
// ---------------------------------------------------------------------------
function VAPIConsolePanel({ frame, record, snap }) {
  const humanity = record?.humanity_prob ?? 0.5
  const mode     = record ? 'LIVE' : 'WAIT'
  return (
    <div style={{
      position:'absolute', bottom:50, left:12, width:320,
      background:'rgba(5,9,14,0.97)',
      border:`1px solid ${ORANGE}2e`,
      borderRadius:7,
      overflow:'hidden',
      boxShadow:`0 0 40px rgba(255,107,0,0.06), 0 4px 80px rgba(0,0,0,0.7), inset 0 0 0 1px rgba(255,255,255,0.02)`,
    }}>
      {/* Header bar — dashboard-aligned */}
      <div style={{
        padding: '7px 12px',
        background: `linear-gradient(90deg, ${ORANGE}0a 0%, transparent 60%)`,
        borderBottom: `1px solid ${ORANGE}1e`,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
          <span style={{
            fontFamily: 'Rajdhani, sans-serif', fontSize: 13, fontWeight: 700,
            letterSpacing: '0.16em', color: ORANGE,
          }}>VAPI</span>
          <span style={{
            fontFamily: 'JetBrains Mono, monospace', fontSize: 7, color: DIM,
            letterSpacing: '0.12em',
          }}>NEURAL CONSOLE</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{
            width: 5, height: 5, borderRadius: '50%',
            background: mode === 'LIVE' ? GREEN : DIM,
            animation: mode === 'LIVE' ? 'statusPulse 2s ease-in-out infinite' : 'none',
            flexShrink: 0,
          }} />
          <span style={{
            fontFamily: 'JetBrains Mono, monospace', fontSize: 6.5,
            color: mode === 'LIVE' ? GREEN : DIM, letterSpacing: '0.08em',
          }}>
            {mode === 'LIVE' ? 'LIVE' : 'WAIT'}
          </span>
        </div>
      </div>

      {/* Section 1: Humanity Arc Gauge */}
      <HumanityArcGauge humanity={humanity} record={record} />

      {/* Divider */}
      <div style={{ height:1, background:`linear-gradient(90deg, transparent, ${ORANGE}22, transparent)` }} />

      {/* Section 2: PITL Layer Stack */}
      <PITLLayerStack record={record} snap={snap} />

      {/* Divider */}
      <div style={{ height:1, background:`linear-gradient(90deg, transparent, ${CYAN}18, transparent)` }} />

      {/* Section 3: Trigger Oscilloscope */}
      <TriggerOscilloscope frame={frame} />
    </div>
  )
}

// ---------------------------------------------------------------------------
// ControllerTwinPage — main component
// ---------------------------------------------------------------------------
function ControllerTwinPage() {
  const deviceId = useAutoDiscover(DEVICE_ID)

  const { frame, record, mode } = useTwinStream(deviceId)
  const { snap, chain }         = useTwinSnapshot(deviceId)
  const [chainIdx, setChainIdx] = useState(0)

  // Phase 61: session replay
  const {
    currentReplayFrame, replayActive, startReplay, stopReplay,
    replayProgress, replayIdx, replayTotal, checkpointSet,
  } = useReplayMode(deviceId)

  // Phase 79–81: agent intelligence hooks
  const { gate, liveMode, federation } = useAgentStatus(mode === 'LIVE')
  const latestRuling = useLatestRuling(deviceId, mode === 'LIVE')
  const classJRisk = latestRuling?.evidence_summary?.class_j_ml_bot_risk ?? null

  // Phase 238-FRONTEND-V3 — SSE event subscription for layered cryptographic
  // animations.  pulseRef carries one-shot transient effects (poac/gic/curator/
  // anchor); pccRimRef carries a sticky rim-light color (host_state).  Both are
  // refs so useFrame() can read latest state without re-rendering the scene.
  const { lastEvent: sseEvent, connected: sseConnected } = useTwinSSEStream({ backfill: 0 })
  const pulseRef  = useRef({ kind: null, color: null, startTime: 0, durationMs: 0, label: null })
  const pccRimRef = useRef('default')

  useEffect(() => {
    if (!sseEvent) return
    const { type, data } = sseEvent
    const tNow = performance.now() / 1000
    if (type === 'poac_chain_link') {
      pulseRef.current = { kind: 'poac', color: CYAN, startTime: tNow, durationMs: 200, label: 'POAC' }
    } else if (type === 'gic_verdict') {
      const v = data?.verdict
      const color = v === 'CERTIFY' ? ORANGE : v === 'FLAG' ? '#f59e0b' : v === 'BLOCK' ? RED : CYAN
      pulseRef.current = { kind: 'gic', color, startTime: tNow, durationMs: 800, label: v || 'GIC' }
    } else if (type === 'pcc_state_change') {
      const host = data?.host_state
      pccRimRef.current =
        host === 'EXCLUSIVE_USB' ? CYAN :
        host === 'CONTESTED'     ? RED  :
        host === 'DEGRADED'      ? '#f59e0b' :
        host === 'DISCONNECTED'  ? DIM  :
        'default'
    } else if (type === 'curator_verdict') {
      const v = data?.verdict
      const color = v === 'APPROVED' ? CYAN
                  : (typeof v === 'string' && v.startsWith('FLAGGED_')) ? '#f59e0b'
                  : (typeof v === 'string' && v.startsWith('REJECTED_')) ? RED
                  : CYAN
      pulseRef.current = { kind: 'curator', color, startTime: tNow, durationMs: 800, label: v || 'CURATOR' }
    } else if (type === 'anchor_confirmed') {
      pulseRef.current = { kind: 'anchor', color: ORANGE, startTime: tNow, durationMs: 1200, label: data?.primitive_type || 'ANCHOR' }
    }
  }, [sseEvent])

  const lockedRecord = chain[chainIdx] || record
  const activeFrame  = currentReplayFrame || frame   // replay overrides live

  const verdictInf   = lockedRecord?.inference ?? null
  const [vWord, vColor] = verdictInf === 0x20 ? ['CERTIFIED', GREEN]
    : (verdictInf === 0x28 || verdictInf === 0x29 || verdictInf === 0x2A) ? ['BLOCKED', RED]
    : verdictInf != null ? ['FLAGGED', ORANGE]
    : mode === 'LIVE' ? ['AWAITING', DIM] : ['DEMO', '#ff9500']

  return (
    <div style={{ width: '100vw', height: '100vh', background: VOID_BG,
                  fontFamily: 'Rajdhani, sans-serif', overflow: 'hidden' }}>

      {/* Keyframe animations + font import — dashboard-aligned */}
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;500;600;700&family=JetBrains+Mono:wght@400;700&display=swap');
        @keyframes statusPulse {
          0%, 100% { opacity: 1; }
          50%       { opacity: 0.35; }
        }
        @keyframes headerGlow {
          0%, 100% { text-shadow: 0 0 20px rgba(255,107,0,0.45), 0 0 60px rgba(255,107,0,0.12); }
          50%       { text-shadow: 0 0 30px rgba(255,107,0,0.65), 0 0 80px rgba(255,107,0,0.22); }
        }
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(5px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        .twin-section-label {
          font-family: 'JetBrains Mono', monospace;
          font-size: 7px;
          letter-spacing: 0.14em;
          color: #3d5060;
          padding: 5px 12px 4px;
          border-bottom: 1px solid rgba(255,107,0,0.07);
          text-transform: uppercase;
        }
      `}</style>

      {/* ── Header — dashboard-aligned ──────────────────────────────────── */}
      {!MINIMAL && (
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, zIndex: 10,
        padding: '11px 24px',
        background: 'rgba(3,5,7,0.94)',
        borderBottom: `1px solid ${ORANGE}28`,
        backdropFilter: 'blur(12px)',
        display: 'flex', alignItems: 'center', gap: 18,
      }}>
        {/* Brand */}
        <div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
            <span style={{
              fontFamily: 'Rajdhani, sans-serif',
              fontSize: 21, fontWeight: 700, letterSpacing: '0.15em', color: ORANGE,
              animation: 'headerGlow 4s ease-in-out infinite',
            }}>VAPI</span>
            <span style={{
              fontFamily: 'JetBrains Mono, monospace',
              fontSize: 8, color: DIM, letterSpacing: '0.1em',
            }}>MY CONTROLLER</span>
          </div>
          <div style={{
            fontFamily: 'JetBrains Mono, monospace', fontSize: 6.5, color: '#1e3048',
            marginTop: 2, letterSpacing: '0.08em',
          }}>
            DualShock Edge CFI-ZCP1 · {deviceId ? deviceId.slice(0, 22) + '…' : 'DISCOVERING…'}
          </div>
        </div>

        {/* Divider */}
        <div style={{ width: 1, height: 30, background: `${ORANGE}18`, flexShrink: 0 }} />

        {/* Status badges */}
        <div style={{ display: 'flex', gap: 7, alignItems: 'center' }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 5, padding: '4px 10px',
            border: `1px solid ${mode === 'LIVE' ? 'rgba(0,255,136,0.28)' : 'rgba(255,149,0,0.28)'}`,
            borderRadius: 2,
            background: mode === 'LIVE' ? 'rgba(0,255,136,0.04)' : 'rgba(255,149,0,0.04)',
          }}>
            <span style={{
              width: 6, height: 6, borderRadius: '50%', flexShrink: 0,
              background: mode === 'LIVE' ? GREEN : '#ff9500',
              animation: mode === 'LIVE' ? 'statusPulse 2s ease-in-out infinite' : 'none',
            }} />
            <span style={{
              fontFamily: 'JetBrains Mono, monospace', fontSize: 7.5,
              color: mode === 'LIVE' ? GREEN : '#ff9500',
            }}>
              {mode === 'LIVE' ? 'LIVE · TWIN ACTIVE' : 'DEMO · BRIDGE OFFLINE'}
            </span>
          </div>
          {/* Phase 238-FRONTEND-V3 — SSE cryptographic-event stream status */}
          <div
            title={sseConnected ? 'SSE: LIVE — cryptographic events streaming' : 'SSE: OFFLINE'}
            style={{
              display: 'flex', alignItems: 'center', gap: 5, padding: '4px 8px',
              border: `1px solid ${sseConnected ? CYAN + '44' : DIM + '44'}`,
              borderRadius: 2,
              background: sseConnected ? `${CYAN}06` : 'transparent',
            }}
          >
            <span style={{
              width: 5, height: 5, borderRadius: '50%', flexShrink: 0,
              background: sseConnected ? CYAN : DIM,
              boxShadow: sseConnected ? `0 0 6px ${CYAN}` : 'none',
            }} />
            <span style={{
              fontFamily: 'JetBrains Mono, monospace', fontSize: 7,
              color: sseConnected ? CYAN : DIM, letterSpacing: '0.08em',
            }}>SSE</span>
          </div>
          <span style={{
            fontFamily: 'JetBrains Mono, monospace', fontSize: 7, color: DIM,
            padding: '4px 8px', borderRadius: 2, border: '1px solid rgba(61,80,96,0.25)',
          }}>Phase 199</span>
          <span style={{
            fontFamily: 'JetBrains Mono, monospace', fontSize: 7, color: GREEN,
            padding: '4px 8px', borderRadius: 2,
            border: `1px solid ${GREEN}40`, background: `${GREEN}07`,
          }}>MPC 3×3 ✓</span>
          <span style={{
            fontFamily: 'JetBrains Mono, monospace', fontSize: 7, color: GREEN,
            padding: '4px 8px', borderRadius: 2,
            border: `1px solid ${GREEN}40`, background: `${GREEN}07`,
          }}>ioSwarm ●</span>
          <span style={{
            fontFamily: 'JetBrains Mono, monospace', fontSize: 7, color: '#ff9500',
            padding: '4px 8px', borderRadius: 2,
            border: '1px solid rgba(255,149,0,0.3)', background: 'rgba(255,149,0,0.05)',
          }}>sep 0.728 · prototype</span>
          {classJRisk === 'HIGH' && (
            <span style={{
              fontFamily: 'JetBrains Mono, monospace', fontSize: 7, color: RED,
              padding: '4px 8px', borderRadius: 2,
              border: `1px solid ${RED}44`, background: `${RED}10`,
              animation: 'statusPulse 0.9s ease-in-out infinite',
            }}>CLASS J !</span>
          )}
        </div>

        {/* Live verdict badge */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8, padding: '4px 12px',
          border: `1px solid ${vColor}3a`,
          borderRadius: 2, background: `${vColor}07`,
          animation: 'fadeIn 0.4s ease',
        }}>
          <span style={{
            width: 7, height: 7, borderRadius: '50%', background: vColor,
            boxShadow: `0 0 7px ${vColor}`, flexShrink: 0,
            animation: (verdictInf === 0x28 || verdictInf === 0x29 || verdictInf === 0x2A)
              ? 'statusPulse 0.7s ease-in-out infinite'
              : verdictInf != null && verdictInf !== 0x20 ? 'statusPulse 2s ease-in-out infinite' : 'none',
          }} />
          <span style={{
            fontFamily: 'JetBrains Mono, monospace', fontSize: 9, color: vColor,
            fontWeight: 700, letterSpacing: '0.1em',
          }}>{vWord}</span>
          {lockedRecord && (
            <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 7, color: DIM }}>
              {((lockedRecord.humanity_prob ?? 0) * 100).toFixed(0)}% HUMAN
            </span>
          )}
        </div>

        {/* Back to dashboard */}
        <a href="/" style={{
          marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: 5,
          padding: '5px 14px',
          border: `1px solid ${ORANGE}44`,
          borderRadius: 2, background: `${ORANGE}08`,
          fontFamily: 'JetBrains Mono, monospace', fontSize: 8,
          color: ORANGE, textDecoration: 'none', letterSpacing: '0.1em',
        }}>
          ← DASHBOARD
        </a>
      </div>
      )}

      {/* Three.js Canvas — Phase 69: real CFI-ZCP1 GLB model.
          Phase 235-GAMER-REDESIGN: in MINIMAL mode the Canvas takes the
          full viewport (top:0) since the header is suppressed. */}
      <Canvas shadows camera={{ position: [0, 0.3, 7.2], fov: 36 }}
        gl={{ antialias: true, toneMapping: THREE.ACESFilmicToneMapping, toneMappingExposure: 1.1 }}
        style={{ position: 'absolute', top: MINIMAL ? 0 : 62, left: 0, right: 0, bottom: 0 }}>
        <color attach="background" args={[VOID_BG]} />
        <ambientLight intensity={0.08} />
        <OrbitControls
          enablePan={false}
          minDistance={2.5} maxDistance={9}
          target={[0, 0, 0]}
          enableDamping dampingFactor={0.07}
        />
        {/* Studio environment — reflections on controller surfaces */}
        <Environment preset="city" background={false} />
        <Suspense fallback={null}>
          {/* Phase 69: DualShock Edge GLB twin with VAPI biometric animations */}
          <DualShockEdgeTwin
            frame={activeFrame}
            record={lockedRecord}
            snap={snap}
            pulseRef={pulseRef}
            pccRimRef={pccRimRef}
          />
          <PoACHelix chain={chain} />
        </Suspense>
      </Canvas>

      {/* Phase 235-GAMER-REDESIGN: every overlay below is suppressed in
          MINIMAL mode so the Canvas owns the entire viewport. */}
      {!MINIMAL && (
      <>
      {/* Proof Anchor Panel (top-right) */}
      <ProofAnchorPanel snap={snap} record={lockedRecord} mode={mode} deviceId={deviceId} />

      {/* Phase 69: VAPI Neural Console — replaces Phase 60A tab panel */}
      <VAPIConsolePanel frame={activeFrame} record={lockedRecord} snap={snap} />

      {/* Phase 61: Replay status bar */}
      {replayActive && (
        <div style={{ position: 'absolute', bottom: 50, right: 12,
                      fontFamily: 'JetBrains Mono, monospace', fontSize: 8,
                      color: CYAN, background: 'rgba(5,9,14,0.97)',
                      border: `1px solid ${CYAN}40`, padding: '5px 10px', borderRadius: 3,
                      backdropFilter: 'blur(8px)' }}>
          &#9654; REPLAY {replayIdx}/{replayTotal}
          <button onClick={stopReplay}
            style={{ marginLeft: 8, color: RED, background: 'none',
                     border: 'none', cursor: 'pointer', fontSize: 8 }}>
            &#9632; STOP
          </button>
          <div style={{ height: 2, background: '#0d1a24', marginTop: 3 }}>
            <div style={{ width: `${replayProgress * 100}%`, height: '100%', background: CYAN }} />
          </div>
        </div>
      )}

      {/* Phase 79–81: Agent Intelligence Panel (right side, below ProofAnchorPanel) */}
      <AgentIntelPanel
        gate={gate} liveMode={liveMode} federation={federation}
        ruling={latestRuling} mode={mode}
      />

      {/* Phase 81 W2: Proof of Humanness broadcast overlay (center-bottom) */}
      <ProofOfHumannessCard record={lockedRecord} chain={chain} />

      {/* Chain Timeline Scrubber — dashboard-aligned */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0,
        background: 'rgba(5,9,14,0.97)',
        borderTop: `1px solid ${ORANGE}22`,
        backdropFilter: 'blur(8px)',
        padding: '6px 16px 8px',
      }}>
        <div style={{
          fontFamily: 'JetBrains Mono, monospace', fontSize: 6.5,
          color: DIM, marginBottom: 4, letterSpacing: '0.1em',
          display: 'flex', alignItems: 'center', gap: 10,
        }}>
          <span style={{ color: ORANGE }}>PoAC CHAIN</span>
          <span>{chain.length} LOCK POINTS · CLICK TO INSPECT</span>
          {checkpointSet.size > 0 && (
            <span style={{ color: CYAN }}>
              &#9654; {checkpointSet.size} REPLAYABLE
            </span>
          )}
        </div>
        <div style={{ display: 'flex', gap: 2, overflowX: 'auto' }}>
          {chain.map((r, i) => {
            const color = r.inference === 0x20 ? GREEN : r.inference === 0x30 ? '#ff9500' : RED
            const hasCheckpoint = checkpointSet.has(r.record_hash)
            return (
              <div key={r.record_hash || i}
                onClick={() => {
                  setChainIdx(i)
                  if (hasCheckpoint) startReplay(r.record_hash)
                }}
                title={`${r.record_hash?.slice(0, 16)}… | L4: ${r.pitl_l4_distance?.toFixed(2)}${hasCheckpoint ? ' | REPLAYABLE' : ''}`}
                style={{ width: 10, height: 18, background: color,
                         opacity: chainIdx === i ? 1 : 0.4, cursor: 'pointer',
                         flexShrink: 0, borderRadius: 1,
                         border: chainIdx === i
                           ? `1px solid ${ORANGE}`
                           : hasCheckpoint ? `1px solid ${CYAN}88` : 'none' }} />
            )
          })}
        </div>
      </div>
      </>
      )}
    </div>
  )
}

createRoot(document.getElementById('root')).render(<ControllerTwinPage />)
