// src/tiers/gamer/GamerRoot.jsx
import React, { useState, useEffect, useRef } from 'react'
import { Routes, Route, useNavigate, NavLink } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useAccount } from 'wagmi'
import {
  BridgeStatusBar, WalletConnectButton, DemoModeBanner,
  Panel, ErrorBoundary,
} from '../../shared/components'
import { useWebSocket } from '../../shared/api/hooks/useWebSocket'
import {
  useEnrollmentStatus, useVHPStatus, useProof,
  usePlayerCredential, useSeparationRatio,
} from '../../shared/api/hooks'
import { useAuthStore } from '../../shared/store/authStore'
import { FONTS, GAMER } from '../../shared/design/tokens'
import { PAGE_ENTER, PITL_CONTAINER, PITL_ROW } from '../../shared/design/animations'

const GAMER_NAV = [
  { label: 'Live Session',     path: '/gamer' },
  { label: 'Enrollment',       path: '/gamer/enrollment' },
  { label: 'Proof Share',      path: '/gamer/proof' },
  { label: 'Controller Twin',  path: '/gamer/twin' },
]

// PITL layer definitions — Phase 147 PITL stack (L0–L7)
const PITL_LAYERS = [
  { id: 'L0',  name: 'HID device binding',           type: 'structural' },
  { id: 'L1',  name: 'PoAC chain integrity',          type: 'structural' },
  { id: 'L2',  name: 'IMU/HID discrepancy',           type: 'hard' },
  { id: 'L2B', name: 'IMU-button causal latency',     type: 'advisory' },
  { id: 'L3',  name: 'TinyML behavioral classifier',  type: 'hard' },
  { id: 'L4',  name: 'Mahalanobis biometric · 13-feat', type: 'advisory' },
  { id: 'L5',  name: 'Temporal rhythm CV/entropy',    type: 'advisory' },
  { id: 'L6',  name: 'Haptic challenge-response',     type: 'advisory', disabled: true },
  { id: 'L7',  name: 'GSR physiological',             type: 'advisory', disabled: true },
]

// Fixed demo percentages — no Math.random (prevents re-render flicker)
const DEMO_PCT = { L2: 100, L2B: 96, L3: 100, L5: 93 }

export default function GamerRoot() {
  const { address } = useAccount()
  const deviceId    = useAuthStore(s => s.deviceId)
  const [feedItems, setFeedItems] = useState([])
  const feedRef = useRef([])

  const { status: wsStatus } = useWebSocket({
    enabled: true,
    onMessage: (data) => {
      const item = {
        id:        Date.now() + Math.random(),
        ts:        new Date().toLocaleTimeString('en-US', { hour12: false }),
        tag:       data.inference_result === 0 ? 'n'
                 : data.inference_result === 1 ? 'a' : 'b',
        msg:       data.summary || `record_hash ${data.record_hash?.slice(0,10)}···`,
        conf:      data.confidence ? (data.confidence / 255).toFixed(2) : '—',
      }
      feedRef.current = [item, ...feedRef.current].slice(0, 8)
      setFeedItems([...feedRef.current])
    },
  })

  // Demo feed when WebSocket offline
  useEffect(() => {
    if (wsStatus === 'disconnected' || wsStatus === 'error') {
      const DEMO = [
        { tag: 'n', msg: 'L4 Mahalanobis Δ=4.21 NOMINAL', conf: '0.96' },
        { tag: 'n', msg: 'touchpad_spatial_entropy=0.742', conf: '0.97' },
        { tag: 'n', msg: 'gyro_std=0.0142 continuity=6.21', conf: '0.95' },
        { tag: 'a', msg: 'L4 continuity 4.89 advisory', conf: '0.81' },
        { tag: 'n', msg: 'PoAC #4821 anchored PITLRegistryV2', conf: '0.99' },
        { tag: 'n', msg: 'IMU-button latency 18ms NOMINAL', conf: '0.93' },
      ]
      let di = 0
      const timer = setInterval(() => {
        const d = DEMO[di % DEMO.length]; di++
        const item = {
          id:   Date.now() + Math.random(),
          ts:   new Date().toLocaleTimeString('en-US', { hour12: false }),
          ...d,
        }
        feedRef.current = [item, ...feedRef.current].slice(0, 8)
        setFeedItems([...feedRef.current])
      }, 1400)
      return () => clearInterval(timer)
    }
  }, [wsStatus])

  const { data: separationData } = useSeparationRatio()
  // Phase 143 honest value: 1.261 (diagonal covariance, N=11 touchpad_corners, proper LOO)
  const ratio = separationData?.pooled_ratio ?? 1.261

  return (
    <div style={{ minHeight: '100vh', background: GAMER.bg }}>
      {/* Nav */}
      <nav style={{
        display:        'flex',
        alignItems:     'center',
        height:         48,
        padding:        '0 1.25rem',
        background:     '#04070d',
        borderBottom:   `1px solid ${GAMER.bd}`,
        gap:            0,
      }}>
        <div onClick={() => window.location.href='/'} style={{
          fontFamily:    FONTS.display,
          fontSize:      19,
          fontWeight:    700,
          letterSpacing: 4,
          color:         GAMER.cyan,
          marginRight:   20,
          cursor:        'pointer',
          flexShrink:    0,
        }}>
          VAPI<span style={{ color: GAMER.t3, fontWeight: 400, fontSize: 13 }}> · GAMER</span>
        </div>

        {GAMER_NAV.map(n => (
          <NavLink key={n.path} to={n.path} end={n.path === '/gamer'}
            style={({ isActive }) => ({
              height:        48,
              padding:       '0 14px',
              display:       'flex',
              alignItems:    'center',
              fontFamily:    FONTS.display,
              fontSize:      10,
              fontWeight:    600,
              letterSpacing: '1.8px',
              textTransform: 'uppercase',
              textDecoration:'none',
              color:          isActive ? GAMER.cyan : GAMER.t3,
              borderBottom:  isActive ? `2px solid ${GAMER.cyan}` : '2px solid transparent',
              transition:    'all .15s',
            })}
          >
            {n.label}
          </NavLink>
        ))}

        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10 }}>
          <BridgeStatusBar tier="gamer" />
          <WalletConnectButton accent={GAMER.cyan} />
        </div>
      </nav>

      <DemoModeBanner dryRun tier="gamer" />

      <div style={{ padding: '1.25rem' }}>
        <Routes>
          <Route path="/" element={
            <LiveSessionPage
              feedItems={feedItems}
              wsStatus={wsStatus}
              ratio={ratio}
              deviceId={deviceId}
            />
          } />
          <Route path="enrollment" element={<EnrollmentPage deviceId={deviceId} />} />
          <Route path="proof"      element={<ProofSharePage deviceId={deviceId} />} />
          <Route path="twin"       element={<ControllerTwinPage deviceId={deviceId} />} />
        </Routes>
      </div>
    </div>
  )
}

// ─── CONTROLLER TWIN PAGE ─────────────────────────────────────
// Novel breakthrough: live 3D biometric twin driven by /ws/twin/{device_id}
// Uses the custom white-and-black DualShock Edge GLB at /assets/controller.glb
function ControllerTwinPage({ deviceId }) {
  const src = deviceId
    ? `/controller-twin.html?device=${encodeURIComponent(deviceId)}&bridge=localhost:8080`
    : '/controller-twin.html'

  return (
    <motion.div {...PAGE_ENTER} style={{ height: 'calc(100vh - 48px)' }}>
      <iframe
        src={src}
        style={{
          width:      '100%',
          height:     '100%',
          border:     'none',
          display:    'block',
          background: GAMER.bg,
        }}
        title="VAPI Controller Twin"
      />
    </motion.div>
  )
}

// ─── LIVE SESSION PAGE ────────────────────────────────────────
function LiveSessionPage({ feedItems, wsStatus, ratio, deviceId }) {
  return (
    <motion.div {...PAGE_ENTER}>
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 340px',
        gap: '1.25rem',
        alignItems: 'start',
      }}>
        {/* Left: PITL + Feed */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <ErrorBoundary accent={GAMER.cyan}>
            <Panel
              title="PITL Detection Stack · L0–L6"
              badge={wsStatus === 'live' ? 'LIVE' : 'DEMO MODE'}
              badgeColor={wsStatus === 'live' ? GAMER.green : GAMER.orange}
              bg={GAMER.bg1} bd={GAMER.bd}
            >
              <PITLLayerStack />
            </Panel>
          </ErrorBoundary>

          <ErrorBoundary accent={GAMER.cyan}>
            <Panel
              title="Live Session Feed · WebSocket /ws/records"
              badge={wsStatus === 'live' ? 'STREAMING' : 'DEMO DATA'}
              badgeColor={wsStatus === 'live' ? GAMER.cyan : GAMER.t3}
              bg={GAMER.bg1} bd={GAMER.bd}
            >
              <LiveFeed items={feedItems} />
            </Panel>
          </ErrorBoundary>
        </div>

        {/* Right: Credential + Ratio + Enrollment */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <VHPCredentialCard deviceId={deviceId} />
          <SeparationRatioPanel ratio={ratio} />
          <QuickEnrollmentStepper deviceId={deviceId} />
        </div>
      </div>
    </motion.div>
  )
}

// ─── PITL LAYER STACK ─────────────────────────────────────────
function PITLLayerStack() {
  const TAG_COLOR = { structural: GAMER.green, hard: GAMER.cyan, advisory: GAMER.t2 }

  return (
    <motion.div variants={PITL_CONTAINER} initial="initial" animate="animate">
      {PITL_LAYERS.map((layer) => {
        const pct = layer.disabled ? 0
                  : layer.type === 'structural' ? 100
                  : layer.id === 'L4' ? 82
                  : layer.id === 'L6' ? 43 / 50 * 100
                  : DEMO_PCT[layer.id] ?? 94
        const color = layer.disabled ? GAMER.t3
                    : TAG_COLOR[layer.type] || GAMER.cyan
        const valText = layer.disabled
          ? (layer.id === 'L6' ? 'N=43/50' : 'N=0')
          : layer.id === 'L4' ? 'Δ=4.21'
          : 'NOMINAL'

        return (
          <motion.div
            key={layer.id}
            variants={PITL_ROW}
            style={{
              display:     'flex',
              alignItems:  'center',
              gap:         10,
              padding:     '8px 14px',
              borderBottom:`1px solid ${GAMER.bd2}`,
              background:  layer.disabled ? 'transparent' : `${color}05`,
              opacity:     layer.disabled ? 0.35 : 1,
            }}
          >
            {/* live dot */}
            <span style={{
              width: 5, height: 5, borderRadius: '50%', flexShrink: 0,
              background:  layer.disabled ? '#1e3a4a' : color,
              animation:   !layer.disabled ? 'vapi-pulse 2s infinite' : 'none',
            }} />
            {/* layer id */}
            <span style={{
              fontFamily:    FONTS.display,
              fontSize:      9,
              fontWeight:    600,
              letterSpacing: '1px',
              width:         24,
              color:         GAMER.t3,
            }}>{layer.id}</span>
            {/* name */}
            <span style={{ fontFamily: FONTS.body, fontSize: 11, color: GAMER.t2, flex: 1 }}>
              {layer.name}
            </span>
            {/* bar */}
            <div style={{
              width: 60, height: 3, background: GAMER.bd,
              borderRadius: 2, overflow: 'hidden', flexShrink: 0,
            }}>
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${pct}%` }}
                transition={{ duration: 0.8, ease: 'easeOut' }}
                style={{ height: '100%', background: color, borderRadius: 2 }}
              />
            </div>
            {/* value */}
            <span style={{
              fontFamily: FONTS.mono,
              fontSize:   9,
              color,
              minWidth:   52,
              textAlign:  'right',
              flexShrink: 0,
            }}>
              {valText}
            </span>
          </motion.div>
        )
      })}
    </motion.div>
  )
}

// ─── LIVE FEED ────────────────────────────────────────────────
function LiveFeed({ items }) {
  const TAG_STYLES = {
    n: { bg: '#00ff8812', color: GAMER.green, border: '#00ff8830', text: 'NOMINAL' },
    a: { bg: '#ff950012', color: '#ff9500',   border: '#ff950030', text: 'ADVISORY' },
    b: { bg: '#ff3b5c12', color: '#ff3b5c',   border: '#ff3b5c30', text: 'BLOCK' },
  }
  return (
    <div>
      <AnimatePresence initial={false}>
        {items.map(item => {
          const ts = TAG_STYLES[item.tag] || TAG_STYLES.n
          return (
            <motion.div
              key={item.id}
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2 }}
              style={{
                display:     'flex',
                alignItems:  'center',
                gap:         8,
                padding:     '6px 14px',
                borderBottom:`1px solid #08101a`,
                fontFamily:  FONTS.mono,
                fontSize:    10,
              }}
            >
              <span style={{ color: GAMER.t3, width: 60, flexShrink: 0 }}>{item.ts}</span>
              <span style={{
                padding: '1px 7px', borderRadius: 2, fontSize: 8, letterSpacing: '.5px',
                background: ts.bg, color: ts.color, border: `1px solid ${ts.border}`,
                flexShrink: 0,
              }}>{ts.text}</span>
              <span style={{ color: '#3a7080', flex: 1 }}>{item.msg}</span>
              <span style={{ color: GAMER.cyan, flexShrink: 0 }}>{item.conf}</span>
            </motion.div>
          )
        })}
      </AnimatePresence>
    </div>
  )
}

// ─── VHP CREDENTIAL CARD ──────────────────────────────────────
function VHPCredentialCard({ deviceId }) {
  const { data } = useVHPStatus(deviceId || 'demo')

  const stats = [
    { label: 'Cert Level', value: data?.cert_level ?? 'L1', accent: GAMER.cyan },
    { label: 'Sessions',   value: data?.sessions ?? 177, accent: GAMER.t1 },
    { label: 'Confidence', value: data?.confidence_score
        ? `${data.confidence_score.toFixed(2)}x` : '0.74x', accent: '#ff9500' },
    { label: 'Consec. Clean', value: data?.consecutive_clean ?? 47, accent: GAMER.green },
  ]

  return (
    <Panel title="Verified Human Proof" badge="TESTNET" badgeColor="#ff9500"
      bg={GAMER.bg1} bd={GAMER.bd}>
      <div style={{ padding: '10px 14px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, marginBottom: 10 }}>
          {stats.map(s => (
            <div key={s.label} style={{
              background: GAMER.bg2, borderRadius: 5, padding: '7px 9px',
            }}>
              <div style={{
                fontFamily: FONTS.display, fontSize: 8, letterSpacing: '1.5px',
                textTransform: 'uppercase', color: GAMER.t3, marginBottom: 3,
              }}>{s.label}</div>
              <div style={{
                fontFamily: FONTS.mono, fontSize: 16, fontWeight: 500, color: s.accent,
              }}>{s.value}</div>
            </div>
          ))}
        </div>

        <div style={{ borderTop: `1px solid ${GAMER.bd}`, paddingTop: 8 }}>
          <div style={{ fontFamily: FONTS.mono, fontSize: 8, color: '#1e4050' }}>DEVICE ID</div>
          <div style={{ fontFamily: FONTS.mono, fontSize: 9, color: GAMER.t3, marginTop: 2 }}>
            {data?.device_id
              ? `${data.device_id.slice(0,12)}···${data.device_id.slice(-4)}`
              : '0xfCF4681e57C8de96···5EF1'}
          </div>
        </div>

        <div style={{
          marginTop: 8, paddingTop: 8,
          borderTop: `1px solid ${GAMER.bd}`,
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <span style={{ fontSize: 9, color: '#1e4050' }}>Expires</span>
          <span style={{ fontFamily: FONTS.mono, fontSize: 9, color: GAMER.cyan }}>
            {data?.expires_at ?? '2026-06-28 · 87 days'}
          </span>
        </div>
      </div>
    </Panel>
  )
}

// ─── SEPARATION RATIO PANEL ───────────────────────────────────
function SeparationRatioPanel({ ratio }) {
  // Phase 143: ratio >= 1.0 means the tournament gate is open
  const passed   = ratio >= 1.0
  const barColor = passed ? GAMER.green : GAMER.cyan
  const barWidth = Math.min(ratio * 100, 100)

  return (
    <div style={{
      background: GAMER.bg1, border: `1px solid ${GAMER.bd}`,
      borderRadius: 8, padding: '10px 14px',
    }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between',
        alignItems: 'center', marginBottom: 8,
      }}>
        <span style={{
          fontFamily: FONTS.display, fontSize: 9, fontWeight: 600,
          letterSpacing: '2px', textTransform: 'uppercase', color: GAMER.t3,
        }}>Separation Ratio</span>
        <span style={{ fontFamily: FONTS.mono, fontSize: 8, color: passed ? GAMER.green : '#ff9500' }}>
          {ratio.toFixed(3)} / 1.0 {passed ? '✓' : ''}
        </span>
      </div>

      <div style={{ height: 5, background: GAMER.bd, borderRadius: 3, overflow: 'hidden' }}>
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${barWidth}%` }}
          transition={{ duration: 1.6, ease: 'easeOut', delay: 0.3 }}
          style={{ height: '100%', background: barColor, borderRadius: 3 }}
        />
      </div>

      <div style={{
        display: 'flex', justifyContent: 'space-between',
        marginTop: 3, fontFamily: FONTS.mono, fontSize: 8, color: '#1e3a4a',
      }}>
        <span>0</span><span>0.25</span>
        <span style={{ color: '#ff9500' }}>0.50</span>
        <span>0.75</span><span style={{ color: passed ? GAMER.green : '#1e3a4a' }}>1.0 {passed ? '✓' : ''}</span>
      </div>

      <div style={{ marginTop: 8, fontSize: 9, color: '#1e4050', lineHeight: 1.6 }}>
        Phase 143 diagonal covariance (N=11, touchpad_corners, proper LOO).
        Classification: 63.6% (7/11) · testnet only.
      </div>
    </div>
  )
}

// ─── QUICK ENROLLMENT STEPPER ─────────────────────────────────
function QuickEnrollmentStepper({ deviceId }) {
  const { data } = useEnrollmentStatus(deviceId || 'demo')
  const status   = data?.status || 'minting'

  const steps = ['Enrolled', 'Eligible', 'Minting', 'Credentialed']
  const activeIdx = { pending: 0, enrolled: 0, eligible: 1, minting: 2, credentialed: 3 }[status] ?? 2

  return (
    <Panel title="Enrollment Status" bg={GAMER.bg1} bd={GAMER.bd}>
      <div style={{ padding: '10px 14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 0, marginBottom: 6 }}>
          {steps.map((step, i) => {
            const done   = i < activeIdx
            const active = i === activeIdx
            const color  = done || active ? GAMER.cyan : '#1e3a4a'
            return (
              <React.Fragment key={step}>
                <div style={{
                  width: 24, height: 24, borderRadius: '50%',
                  border: `1px solid ${color}`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontFamily: FONTS.mono, fontSize: 9,
                  color, background: active ? `${GAMER.cyan}15` : 'transparent',
                  animation: active ? 'vapi-pulse 2s infinite' : 'none',
                  flexShrink: 0,
                }}>
                  {i + 1}
                </div>
                {i < steps.length - 1 && (
                  <div style={{
                    flex: 1, height: 1,
                    background: done ? `${GAMER.cyan}40` : '#0e2535',
                  }} />
                )}
              </React.Fragment>
            )
          })}
        </div>
        <div style={{
          display: 'flex', justifyContent: 'space-between',
          fontFamily: FONTS.body, fontSize: 8, color: '#1e4050',
        }}>
          {steps.map((s, i) => (
            <span key={s} style={{ color: i === activeIdx ? GAMER.green : '#1e4050' }}>{s}</span>
          ))}
        </div>
      </div>
    </Panel>
  )
}

// ─── ENROLLMENT PAGE ──────────────────────────────────────────
function EnrollmentPage({ deviceId }) {
  const { data, isLoading } = useEnrollmentStatus(deviceId || 'demo')
  return (
    <motion.div {...PAGE_ENTER}>
      <Panel title="Player Eligibility" bg={GAMER.bg1} bd={GAMER.bd}>
        <div style={{ padding: '1rem' }}>
          {isLoading
            ? <div style={{ fontFamily: FONTS.mono, fontSize: 10, color: GAMER.t3 }}>Loading...</div>
            : <pre style={{ fontFamily: FONTS.mono, fontSize: 10, color: GAMER.t2, whiteSpace: 'pre-wrap' }}>
                {JSON.stringify(data ?? { status: 'minting', sessions: 177, consecutive_clean: 47 }, null, 2)}
              </pre>
          }
        </div>
      </Panel>
    </motion.div>
  )
}

// ─── PROOF SHARE PAGE ─────────────────────────────────────────
function ProofSharePage({ deviceId }) {
  const { data } = useProof(deviceId || 'demo')
  const { data: cred } = usePlayerCredential(deviceId || 'demo')

  return (
    <motion.div {...PAGE_ENTER}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
        <Panel title="Proof Record" bg={GAMER.bg1} bd={GAMER.bd}>
          <div style={{ padding: '1rem' }}>
            <pre style={{ fontFamily: FONTS.mono, fontSize: 10, color: GAMER.t2, whiteSpace: 'pre-wrap', overflow: 'auto' }}>
              {JSON.stringify(data ?? {
                device_id: '0xfCF4...5EF1',
                vhp_address: '0xD3B2...dcF',
                cert_level: 1,
                poac_chain_hash: 'SHA-256(raw[:164])',
                poad_hash: '0x44CF...',
                iotexscan: 'https://testnet.iotexscan.io/...',
              }, null, 2)}
            </pre>
          </div>
        </Panel>
        <Panel title="Credential · Share Link" bg={GAMER.bg1} bd={GAMER.bd}>
          <div style={{ padding: '1rem' }}>
            <div style={{ fontFamily: FONTS.mono, fontSize: 9, color: GAMER.cyan, marginBottom: 12 }}>
              testnet.iotexscan.io/address/0xD3B2E2...dcF
            </div>
            <div style={{ fontFamily: FONTS.body, fontSize: 11, color: GAMER.t3, lineHeight: 1.7 }}>
              This credential is soulbound — non-transferable ERC-4671.
              It expires in 90 days from issuance and auto-renews
              via VHPRenewalAgent (16-hour poll).
            </div>
          </div>
        </Panel>
      </div>
    </motion.div>
  )
}
