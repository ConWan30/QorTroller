// src/tiers/manufacturer/ManufacturerRoot.jsx
// MANUFACTURER tier — certify hardware, data lineage, ioSwarm infra, VHP pipeline, federation
// Design: cool void #020408 + steel blue #4a9eff + Rajdhani 700 + JetBrains Mono

import React, { useState } from 'react'
import { Routes, Route, NavLink, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { MANUFACTURER, FONTS } from '../../shared/design/tokens'
import { useAuthStore } from '../../shared/store/authStore'
import { BridgeStatusBar, ChainAddressLink, Panel, StatCard } from '../../shared/components/index'
import {
  useDeviceCerts, useDeviceCert, useDataLineage, useOracleState,
  useIoSwarmStatus, useVHPDualGateLog, useEpochWindowAnalytics,
  useConfidenceMultiplier, useFederationPeers,
} from '../../shared/api/hooks/index'
import { apiFetch } from '../../shared/api/endpoints'

// ─── Design constants ──────────────────────────────────────────────────────────
const M = MANUFACTURER
const F = FONTS

// ─── Deployed contract addresses (correct, from contracts/deployed-addresses.json) ──
const DEPLOYED_ADDRESSES = [
  { label: 'VAPIVerifiedHumanProof', addr: '0xD3B2E259A4B69EF08e263e3A57B2507B7eac3dcF', gold: false },
  { label: 'VAPIDualPrimitiveGate',  addr: '0xd7b1465Aad8F815C67b24681c9c022CED24FB876', gold: false },
  { label: 'AdjudicationRegistry',   addr: '0x44CF981f46a52ADE56476Ce894255954a7776fb4', gold: false },
  { label: 'VAPIProtocolLens',       addr: '0x1972bf756aFE0FFCfaF9842e2FbBb2B084352EAf', gold: false },
  { label: 'VAPIToken',              addr: '0xaDD7C15f7C99961Bf09adE43e3f80E73aB1B2BBc', gold: true  },
  { label: 'ZK Ceremony Beacon',     addr: 'IoTeX block #41723255',                      gold: false },
]

const MFR_NAV = [
  { label: 'Devices',        path: '/manufacturer/devices'    },
  { label: 'Data Lineage',   path: '/manufacturer/data'       },
  { label: 'Infrastructure', path: '/manufacturer/infra'      },
  { label: 'VHP Pipeline',   path: '/manufacturer/vhp'        },
  { label: 'Federation',     path: '/manufacturer/federation' },
]

// ─── Shared sub-components ─────────────────────────────────────────────────────

function Mono({ children, color = M.blue, size = 9, ...rest }) {
  return (
    <span style={{ fontFamily: F.mono, fontSize: size, color, letterSpacing: '0.5px', ...rest }}>
      {children}
    </span>
  )
}

function SectionHeader({ children, accent = M.blue }) {
  return (
    <div style={{
      fontFamily:    F.display,
      fontSize:      11,
      fontWeight:    700,
      letterSpacing: 3,
      color:         accent,
      textTransform: 'uppercase',
      marginBottom:  10,
      borderBottom:  `1px solid ${accent}20`,
      paddingBottom: 6,
    }}>
      {children}
    </div>
  )
}

function Badge({ children, color = M.blue, bg }) {
  return (
    <span style={{
      fontFamily:    F.mono,
      fontSize:      8,
      color,
      background:    bg || `${color}18`,
      border:        `1px solid ${color}40`,
      borderRadius:  3,
      padding:       '2px 7px',
      letterSpacing: '0.5px',
    }}>
      {children}
    </span>
  )
}

function EmptyState({ msg = 'No data', sub }) {
  return (
    <div style={{ textAlign: 'center', padding: '2rem', color: M.t3 }}>
      <div style={{ fontFamily: F.mono, fontSize: 10, letterSpacing: 2 }}>{msg}</div>
      {sub && <div style={{ fontFamily: F.body, fontSize: 10, marginTop: 6, color: M.t3 }}>{sub}</div>}
    </div>
  )
}

function Loader({ accent = M.blue }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '1rem' }}>
      <div style={{
        width: 6, height: 6, borderRadius: '50%', background: accent,
        animation: 'vapi-pulse 1.2s ease-in-out infinite',
      }} />
      <Mono size={8} color={accent}>LOADING</Mono>
    </div>
  )
}

// ─── ADDRESS STRIP ─────────────────────────────────────────────────────────────
function AddressStrip() {
  return (
    <div style={{
      background:    M.bg2,
      borderTop:     `1px solid ${M.bd}`,
      padding:       '8px 20px',
      display:       'flex',
      flexWrap:      'wrap',
      gap:           '8px 20px',
      alignItems:    'center',
    }}>
      {DEPLOYED_ADDRESSES.map(({ label, addr, gold }) => (
        <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Mono size={7} color={M.t3}>{label}</Mono>
          <Mono size={7} color={gold ? M.gold : M.blue}>
            {addr.startsWith('0x') ? (
              <ChainAddressLink address={addr} accent={gold ? M.gold : M.blue} />
            ) : addr}
          </Mono>
        </div>
      ))}
    </div>
  )
}

// ─── API KEY INPUT ─────────────────────────────────────────────────────────────
function ApiKeyBar({ apiKey, setApiKey }) {
  return (
    <div style={{
      display:     'flex',
      alignItems:  'center',
      gap:         10,
      padding:     '6px 20px',
      background:  M.bg2,
      borderBottom:`1px solid ${M.bd}`,
    }}>
      <Mono size={8} color={M.t3}>OPERATOR KEY</Mono>
      <input
        type="password"
        value={apiKey}
        onChange={e => setApiKey(e.target.value)}
        placeholder="Enter operator api_key"
        style={{
          background:    'transparent',
          border:        `1px solid ${M.bd}`,
          borderRadius:  4,
          padding:       '3px 8px',
          fontFamily:    F.mono,
          fontSize:      9,
          color:         M.t1,
          outline:       'none',
          width:         220,
        }}
      />
      {apiKey && <Badge color={M.blue}>KEY SET</Badge>}
      {!apiKey && <Badge color={M.t3}>READ-ONLY MODE</Badge>}
    </div>
  )
}

// ─── PAGE: DEVICE CERTIFICATION ────────────────────────────────────────────────
function DeviceCertificationPage() {
  const { data: devicesData, isLoading, error } = useDeviceCerts()
  const [selectedId, setSelectedId] = useState(null)
  const { data: certData } = useDeviceCert(selectedId)

  const devices = devicesData?.profiles || devicesData?.devices || []

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      style={{ display: 'flex', gap: 16, height: 'calc(100vh - 160px)', overflow: 'hidden' }}
    >
      {/* Left panel — device list */}
      <div style={{
        width:         280,
        flexShrink:    0,
        overflowY:     'auto',
        background:    M.bg1,
        border:        `1px solid ${M.bd}`,
        borderRadius:  8,
      }}>
        <div style={{ padding: '12px 14px', borderBottom: `1px solid ${M.bd}` }}>
          <SectionHeader>Device Registry</SectionHeader>
          <Mono size={8} color={M.t3}>
            {devices.length} hardware profile{devices.length !== 1 ? 's' : ''} certified
          </Mono>
        </div>
        {isLoading && <Loader />}
        {error && <EmptyState msg="API UNAVAILABLE" sub="Bridge offline or no devices registered" />}
        {!isLoading && !error && devices.length === 0 && (
          <EmptyState msg="NO DEVICES" sub="Register hardware via POST /devices" />
        )}
        {devices.map((dev, i) => (
          <motion.div
            key={dev.profile_id || dev.device_id || i}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.04 }}
            onClick={() => setSelectedId(dev.profile_id || dev.device_id)}
            style={{
              padding:       '10px 14px',
              borderBottom:  `1px solid ${M.bd}`,
              cursor:        'pointer',
              background:    selectedId === (dev.profile_id || dev.device_id)
                               ? `${M.blue}12` : 'transparent',
              borderLeft:    selectedId === (dev.profile_id || dev.device_id)
                               ? `3px solid ${M.blue}` : '3px solid transparent',
            }}
          >
            <div style={{
              fontFamily: F.display,
              fontSize:   13,
              fontWeight: 700,
              color:      M.t1,
              marginBottom: 3,
            }}>
              {dev.model_name || dev.device_name || 'Unknown Device'}
            </div>
            <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
              {dev.cert_level != null && (
                <Badge color={dev.cert_level >= 2 ? M.gold : M.blue}>
                  CERT L{dev.cert_level}
                </Badge>
              )}
              <Mono size={7} color={M.t3}>
                {(dev.profile_id || dev.device_id || '').slice(0, 16)}…
              </Mono>
            </div>
          </motion.div>
        ))}
        {/* DualShock Edge reference entry always shown */}
        <motion.div
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.12 }}
          onClick={() => setSelectedId('dualshock_edge_cfi_zcp1')}
          style={{
            padding:      '10px 14px',
            borderBottom: `1px solid ${M.bd}`,
            cursor:       'pointer',
            background:   selectedId === 'dualshock_edge_cfi_zcp1' ? `${M.blue}12` : `${M.blue}06`,
            borderLeft:   selectedId === 'dualshock_edge_cfi_zcp1'
                            ? `3px solid ${M.blue}` : `3px solid ${M.blue}40`,
          }}
        >
          <div style={{ fontFamily: F.display, fontSize: 13, fontWeight: 700, color: M.t1, marginBottom: 3 }}>
            DualShock Edge CFI-ZCP1
          </div>
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <Badge color={M.gold}>CERT L1</Badge>
            <Badge color={M.blue}>REFERENCE HW</Badge>
          </div>
        </motion.div>
      </div>

      {/* Right panel — device detail */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {!selectedId ? (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            height: '100%', color: M.t3,
          }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontFamily: F.display, fontSize: 24, color: M.blue, marginBottom: 8 }}>
                SELECT DEVICE
              </div>
              <Mono size={9} color={M.t3}>Click a hardware profile to view certification detail</Mono>
            </div>
          </div>
        ) : selectedId === 'dualshock_edge_cfi_zcp1' ? (
          <DualShockEdgeDetail />
        ) : certData ? (
          <CertDetail cert={certData} />
        ) : (
          <Loader />
        )}
      </div>
    </motion.div>
  )
}

function DualShockEdgeDetail() {
  const rows = [
    ['Model',        'DualShock Edge CFI-ZCP1'],
    ['VID/PID',      '0x054C / 0x0DF2 (interface 3)'],
    ['USB Polling',  '1002 Hz'],
    ['Cert Level',   '1 (controller only)'],
    ['Cert Level 2', 'Pending GSR grip attachment'],
    ['Accel Margin', '14,000× injection margin'],
    ['Gyro Margin',  '10,000× injection margin'],
    ['Micro-tremor', '278,239 LSB² variance (Phase 57)'],
    ['ioID DID',     'did:io:0x0Cf36dB…92'],
    ['PITL Layers',  'L0–L6 (L7 advisory pending calibration)'],
    ['ZK Circuit',   'Groth16 BN254, 1,820 constraints'],
    ['Chain',        'IoTeX Testnet 4690'],
    ['Status',       'ACTIVE — Live Testnet'],
  ]
  return (
    <Panel
      title="DualShock Edge CFI-ZCP1"
      badge="CERT L1 · REFERENCE HARDWARE"
      badgeColor={M.gold}
      bg={M.bg1}
      bd={M.bd}
    >
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
        <StatCard label="Cert Level" value="L1" accent={M.gold} bg={M.bg2} />
        <StatCard label="PITL Layers" value="7 (L0–L6)" accent={M.blue} bg={M.bg2} />
        <StatCard label="USB Polling" value="1002 Hz" accent={M.blue} bg={M.bg2} />
        <StatCard label="Chain" value="IoTeX 4690" accent={M.blue} bg={M.bg2} />
      </div>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <tbody>
          {rows.map(([k, v]) => (
            <tr key={k} style={{ borderBottom: `1px solid ${M.bd}` }}>
              <td style={{ fontFamily: F.mono, fontSize: 9, color: M.t3, padding: '6px 10px', width: '35%' }}>{k}</td>
              <td style={{ fontFamily: F.mono, fontSize: 9, color: M.t1, padding: '6px 10px' }}>{v}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{ marginTop: 16 }}>
        <SectionHeader>Cert Level 2 Requirements</SectionHeader>
        <div style={{ fontFamily: F.body, fontSize: 11, color: M.t2, lineHeight: 1.7 }}>
          Cert Level 2 unlocks GSR biometric tier (L7 advisory layer). Requirements:
          ESP32-S3 BLE 5.0 grip module · Ag/AgCl dry electrodes (medial hypothenar)
          · INA128 instrumentation amp · BLE pair to bridge · N≥30 calibration sessions/player.
        </div>
        <div style={{ marginTop: 10, display: 'flex', gap: 8 }}>
          <Badge color={M.blue}>GSR_ENABLED=false</Badge>
          <Badge color={M.orange}>N=0 CALIBRATION SESSIONS</Badge>
          <Badge color={M.t3}>PHASE 99B OPEN GAP</Badge>
        </div>
      </div>
    </Panel>
  )
}

function CertDetail({ cert }) {
  return (
    <Panel title="Certification Detail" badge="LIVE" badgeColor={M.blue} bg={M.bg1} bd={M.bd}>
      <pre style={{
        fontFamily: F.mono, fontSize: 9, color: M.t1,
        background: M.bg2, padding: 14, borderRadius: 6,
        overflow: 'auto',
      }}>
        {JSON.stringify(cert, null, 2)}
      </pre>
    </Panel>
  )
}

// ─── PAGE: DATA SOVEREIGNTY ────────────────────────────────────────────────────
function DataSovereigntyPage() {
  const apiKey = useAuthStore(s => s.apiKey)
  const deviceId = useAuthStore(s => s.deviceId)
  const { data: lineageData, isLoading: lineageLoading, error: lineageErr } = useDataLineage(deviceId)
  const { data: oracleData, isLoading: oracleLoading } = useOracleState('HUMANITY')

  const TAXONOMY = [
    { level: 'SESSION',  desc: 'PoAC record — 228B signed body + ECDSA-P256',  color: M.blue  },
    { level: 'PROOF',    desc: 'ZK Groth16 proof + PITL score + humanity_prob', color: '#7ec8ff' },
    { level: 'RULING',   desc: 'Agent adjudication — CERTIFY / HOLD / BLOCK',  color: M.gold  },
    { level: 'TOKEN',    desc: 'VHP soulbound ERC-4671 — 90-day TTL',          color: M.green },
  ]

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {!apiKey && (
        <div style={{ background: `${M.gold}12`, border: `1px solid ${M.gold}40`, borderRadius: 8, padding: '10px 16px' }}>
          <Mono size={9} color={M.gold}>⚠ Operator api_key required for data lineage access</Mono>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>

        {/* Data Taxonomy Tree */}
        <Panel title="Data Taxonomy" badge="SESSION→PROOF→RULING→TOKEN" badgeColor={M.blue} bg={M.bg1} bd={M.bd}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {TAXONOMY.map((node, i) => (
              <motion.div
                key={node.level}
                initial={{ opacity: 0, x: -12 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.08 }}
                style={{
                  display:      'flex',
                  alignItems:   'center',
                  gap:          12,
                  background:   M.bg2,
                  border:       `1px solid ${node.color}25`,
                  borderLeft:   `3px solid ${node.color}`,
                  borderRadius: 6,
                  padding:      '10px 14px',
                }}
              >
                <div>
                  <div style={{ fontFamily: F.display, fontSize: 13, fontWeight: 700, color: node.color }}>
                    {node.level}
                  </div>
                  <div style={{ fontFamily: F.body, fontSize: 10, color: M.t2, marginTop: 2, lineHeight: 1.5 }}>
                    {node.desc}
                  </div>
                </div>
                {i < TAXONOMY.length - 1 && (
                  <div style={{ marginLeft: 'auto', color: M.t3, fontFamily: F.mono, fontSize: 10 }}>↓</div>
                )}
              </motion.div>
            ))}
          </div>
          <div style={{ marginTop: 12 }}>
            <Mono size={8} color={M.t3}>
              Data sovereignty pledges recorded on-chain in DataSovereigntyRegistry.
              3-tier licensing: MANUFACTURER / DEVELOPER / GAMER enforced per contract.
            </Mono>
          </div>
        </Panel>

        {/* Humanity Oracle State */}
        <Panel title="Humanity Oracle" badge="LIVE ON-CHAIN" badgeColor={M.blue} bg={M.bg1} bd={M.bd}>
          {!apiKey ? (
            <EmptyState msg="API KEY REQUIRED" sub="Provide operator api_key to query oracle state" />
          ) : oracleLoading ? (
            <Loader />
          ) : oracleData ? (
            <div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
                <StatCard label="Oracle" value="HUMANITY" accent={M.blue} bg={M.bg2} />
                <StatCard
                  label="Status"
                  value={oracleData.status || oracleData.is_valid ? 'VALID' : 'PENDING'}
                  accent={oracleData.is_valid ? M.green : M.orange}
                  bg={M.bg2}
                />
              </div>
              <pre style={{
                fontFamily: F.mono, fontSize: 9, color: M.t1,
                background: M.bg2, padding: 12, borderRadius: 6, overflow: 'auto',
              }}>
                {JSON.stringify(oracleData, null, 2)}
              </pre>
            </div>
          ) : (
            <EmptyState msg="NO ORACLE DATA" sub="POST /curator/oracle-state to seed" />
          )}
        </Panel>

      </div>

      {/* Data Lineage Viewer */}
      <Panel title="Data Lineage" badge={deviceId || 'NO DEVICE SELECTED'} badgeColor={M.gold} bg={M.bg1} bd={M.bd}>
        {!deviceId ? (
          <EmptyState msg="DEVICE ID REQUIRED" sub="Set device ID via authStore to view lineage" />
        ) : !apiKey ? (
          <EmptyState msg="API KEY REQUIRED" />
        ) : lineageLoading ? (
          <Loader />
        ) : lineageErr ? (
          <EmptyState msg="LINEAGE UNAVAILABLE" sub="Bridge offline or device not registered" />
        ) : lineageData ? (
          <div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 16 }}>
              <StatCard label="Sessions" value={lineageData.session_count ?? '—'} accent={M.blue} bg={M.bg2} />
              <StatCard label="Proofs" value={lineageData.proof_count ?? '—'} accent={M.blue} bg={M.bg2} />
              <StatCard label="Rulings" value={lineageData.ruling_count ?? '—'} accent={M.gold} bg={M.bg2} />
              <StatCard label="VHP Tokens" value={lineageData.vhp_count ?? '—'} accent={M.green} bg={M.bg2} />
            </div>
            <pre style={{
              fontFamily: F.mono, fontSize: 9, color: M.t1,
              background: M.bg2, padding: 12, borderRadius: 6, overflow: 'auto', maxHeight: 300,
            }}>
              {JSON.stringify(lineageData, null, 2)}
            </pre>
          </div>
        ) : (
          <EmptyState msg="NO LINEAGE DATA" sub="No sessions recorded for this device" />
        )}
      </Panel>
    </motion.div>
  )
}

// ─── PAGE: IOSWARM INFRASTRUCTURE ──────────────────────────────────────────────
function IoSwarmInfraPage() {
  const apiKey = useAuthStore(s => s.apiKey)
  const { data: swarmData, isLoading: swarmLoading } = useIoSwarmStatus()
  // poad-anchor-status and dual-primitive-status fetched inline
  const [poadData, setPoadData] = React.useState(null)
  const [dualData, setDualData] = React.useState(null)

  React.useEffect(() => {
    if (!apiKey) return
    apiFetch('/agent/poad-anchor-status', apiKey)
      .then(d => setPoadData(d))
      .catch(() => {})
    apiFetch('/agent/dual-primitive-status', apiKey)
      .then(d => setDualData(d))
      .catch(() => {})
  }, [apiKey])

  const swarmEnabled = swarmData?.ioswarm_enabled || false
  const consensusCount = swarmData?.consensus_count ?? 0
  const nodeCount = swarmData?.node_count ?? 5
  const taskRegistered = swarmData?.task_spec_registered ?? false

  const INFRA_NODES = [
    { name: 'ioSwarm Consensus',     status: swarmEnabled ? 'LIVE' : 'INFRASTRUCTURE ONLY',   color: swarmEnabled ? M.green : M.t3 },
    { name: 'PoAd On-Chain Anchor',  status: poadData?.poad_on_chain_enabled ? 'LIVE' : 'DISABLED', color: poadData?.poad_on_chain_enabled ? M.green : M.t3 },
    { name: 'Dual-Primitive Gate',   status: dualData?.dual_primitive_gate_enabled ? 'LIVE' : 'DISABLED', color: dualData?.dual_primitive_gate_enabled ? M.green : M.t3 },
    { name: 'VHP Mint Gate (Swarm)', status: 'INFRASTRUCTURE READY',  color: M.blue  },
    { name: 'Adjudication Swarm',    status: 'INFRASTRUCTURE READY',  color: M.blue  },
    { name: 'VHP Renewal Swarm',     status: 'INFRASTRUCTURE READY',  color: M.blue  },
  ]

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {!apiKey && (
        <div style={{ background: `${M.gold}12`, border: `1px solid ${M.gold}40`, borderRadius: 8, padding: '10px 16px' }}>
          <Mono size={9} color={M.gold}>⚠ Operator api_key required for infrastructure status</Mono>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
        <StatCard label="ioSwarm Mode" value={swarmEnabled ? 'LIVE' : 'EMULATOR'} accent={swarmEnabled ? M.green : M.t3} bg={M.bg1} />
        <StatCard label="Node Count"  value={nodeCount}  accent={M.blue} bg={M.bg1} />
        <StatCard label="Consensus"   value={consensusCount} accent={M.blue} bg={M.bg1} />
        <StatCard label="Task Spec"   value={taskRegistered ? 'REGISTERED' : 'PHASE 109A'} accent={taskRegistered ? M.green : M.orange} bg={M.bg1} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>

        {/* Node Infrastructure Panel */}
        <Panel title="Node Infrastructure" badge={swarmEnabled ? 'LIVE NODES' : 'EMULATOR MODE'} badgeColor={swarmEnabled ? M.green : M.t3} bg={M.bg1} bd={M.bd}>
          {swarmLoading ? <Loader /> : (
            <div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 16 }}>
                {INFRA_NODES.map((node, i) => (
                  <motion.div
                    key={node.name}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.06 }}
                    style={{
                      display:      'flex',
                      alignItems:   'center',
                      justifyContent: 'space-between',
                      background:   M.bg2,
                      border:       `1px solid ${M.bd}`,
                      borderRadius: 5,
                      padding:      '7px 12px',
                    }}
                  >
                    <Mono size={9} color={M.t2}>{node.name}</Mono>
                    <Badge color={node.color}>{node.status}</Badge>
                  </motion.div>
                ))}
              </div>
              <div style={{ fontFamily: F.body, fontSize: 10, color: M.t3, lineHeight: 1.6 }}>
                ioswarm_enabled=false until live operator nodes registered.
                BLOCK_QUORUM=0.67 · MINT_QUORUM=0.80 (fail-CLOSED).
                Phase 131+ infrastructure complete; activate when ioswarm_node_urls populated.
              </div>
            </div>
          )}
        </Panel>

        {/* Dual-Primitive Gate Status */}
        <Panel title="Dual-Primitive Gate" badge="PoAC + PoAd" badgeColor={M.blue} bg={M.bg1} bd={M.bd}>
          {!dualData ? (
            apiKey ? <Loader /> : <EmptyState msg="API KEY REQUIRED" />
          ) : (
            <div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
                <StatCard label="Gate Enabled" value={dualData.dual_primitive_gate_enabled ? 'YES' : 'NO'} accent={dualData.dual_primitive_gate_enabled ? M.green : M.t3} bg={M.bg2} />
                <StatCard label="Checks Total" value={dualData.checks_total ?? 0} accent={M.blue} bg={M.bg2} />
                <StatCard label="Eligible"     value={dualData.checks_eligible ?? 0} accent={M.green} bg={M.bg2} />
                <StatCard label="PoAd Pending" value={poadData?.pending_count ?? '—'} accent={M.orange} bg={M.bg2} />
              </div>
              <div style={{ marginBottom: 8 }}>
                <Mono size={8} color={M.t3}>VAPIDualPrimitiveGate</Mono>
                <ChainAddressLink address="0xd7b1465Aad8F815C67b24681c9c022CED24FB876" accent={M.blue} />
              </div>
              <div style={{ marginBottom: 8 }}>
                <Mono size={8} color={M.t3}>AdjudicationRegistry</Mono>
                <ChainAddressLink address="0x44CF981f46a52ADE56476Ce894255954a7776fb4" accent={M.blue} />
              </div>
              <div style={{ fontFamily: F.body, fontSize: 10, color: M.t3, lineHeight: 1.6, marginTop: 8 }}>
                isDualEligible() = isFullyEligible() (PoAC) AND isRecorded() (PoAd).
                First dual-proof composability gate in on-chain gaming.
              </div>
            </div>
          )}
        </Panel>

      </div>

      {/* W3bstream Applets */}
      <Panel title="W3bstream DePIN Applets" badge="INFRASTRUCTURE PHASE 99B" badgeColor={M.t3} bg={M.bg1} bd={M.bd}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          {[
            { name: 'validate_poac_record', desc: '228B PoAC → ECDSA-P256 → PITLSessionRegistryV2.submitProof()', status: 'STUB' },
            { name: 'process_gsr_packet',   desc: '48B GSR packet (magic 0x47535201) → VAPIGSRRegistry.recordSample()', status: 'STUB' },
          ].map(applet => (
            <div key={applet.name} style={{ background: M.bg2, border: `1px solid ${M.bd}`, borderRadius: 6, padding: '12px 14px' }}>
              <div style={{ fontFamily: F.mono, fontSize: 10, color: M.blue, marginBottom: 4 }}>{applet.name}</div>
              <div style={{ fontFamily: F.body, fontSize: 10, color: M.t2, marginBottom: 8, lineHeight: 1.5 }}>{applet.desc}</div>
              <Badge color={M.t3}>{applet.status}</Badge>
            </div>
          ))}
        </div>
      </Panel>
    </motion.div>
  )
}

// ─── PAGE: VHP MINT PIPELINE ───────────────────────────────────────────────────
function VHPMintPipelinePage() {
  const apiKey = useAuthStore(s => s.apiKey)
  const { data: gateLog,   isLoading: gateLoading  } = useVHPDualGateLog()
  const { data: epochData, isLoading: epochLoading } = useEpochWindowAnalytics()
  const { data: multData,  isLoading: multLoading  } = useConfidenceMultiplier()

  const recentLogs = gateLog?.recent_logs || []
  const dualGateEnabled = gateLog?.dual_primitive_gate_enabled ?? false
  const epochEnabled = epochData?.epoch_window_enabled ?? false
  const multEnabled = multData?.confidence_multiplier_enabled ?? false

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {!apiKey && (
        <div style={{ background: `${M.gold}12`, border: `1px solid ${M.gold}40`, borderRadius: 8, padding: '10px 16px' }}>
          <Mono size={9} color={M.gold}>⚠ Operator api_key required for VHP pipeline access</Mono>
        </div>
      )}

      {/* Summary stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
        <StatCard label="Dual Gate"    value={dualGateEnabled ? 'ACTIVE' : 'DISABLED'} accent={dualGateEnabled ? M.green : M.t3} bg={M.bg1} />
        <StatCard label="Epoch Window" value={epochEnabled ? 'ACTIVE' : 'DISABLED'}    accent={epochEnabled ? M.green : M.t3} bg={M.bg1} />
        <StatCard label="Conf Mult"    value={multEnabled ? 'ACTIVE' : 'DISABLED'}     accent={multEnabled ? M.green : M.t3} bg={M.bg1} />
        <StatCard label="Epoch p95"    value={epochData ? `${(epochData.p95 || 0).toFixed(0)}s` : '—'} accent={M.blue} bg={M.bg1} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 16 }}>

        {/* Gate log table */}
        <Panel title="Dual-Primitive Gate Log" badge="MINT PIPELINE" badgeColor={M.blue} bg={M.bg1} bd={M.bd}>
          {!apiKey ? (
            <EmptyState msg="API KEY REQUIRED" />
          ) : gateLoading ? (
            <Loader />
          ) : recentLogs.length === 0 ? (
            <EmptyState msg="NO GATE EVENTS" sub="Gate runs on POST /agent/mint-vhp" />
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontFamily: F.mono, fontSize: 8 }}>
                <thead>
                  <tr style={{ borderBottom: `1px solid ${M.bd}` }}>
                    {['Device', 'PoAC', 'PoAd', 'Mint', 'Epoch OK', 'Ts'].map(h => (
                      <th key={h} style={{ color: M.t3, padding: '4px 8px', textAlign: 'left', fontWeight: 400 }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {recentLogs.map((row, i) => (
                    <tr key={i} style={{ borderBottom: `1px solid ${M.bd}20` }}>
                      <td style={{ color: M.t2, padding: '5px 8px' }}>{(row.device_id || '').slice(0, 12)}…</td>
                      <td style={{ padding: '5px 8px' }}><Badge color={row.poac_valid ? M.green : M.red}>{row.poac_valid ? 'OK' : 'FAIL'}</Badge></td>
                      <td style={{ padding: '5px 8px' }}><Badge color={row.poad_valid ? M.green : M.red}>{row.poad_valid ? 'OK' : 'FAIL'}</Badge></td>
                      <td style={{ padding: '5px 8px' }}><Badge color={row.mint_allowed ? M.green : M.red}>{row.mint_allowed ? 'ALLOW' : 'BLOCK'}</Badge></td>
                      <td style={{ padding: '5px 8px' }}><Badge color={row.epoch_window_ok !== false ? M.green : M.orange}>{row.epoch_window_ok !== false ? 'OK' : 'STALE'}</Badge></td>
                      <td style={{ color: M.t3, padding: '5px 8px' }}>{(row.created_at || '').slice(11, 19)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {gateLog && (
            <div style={{ display: 'flex', gap: 16, marginTop: 12 }}>
              <div><Mono size={8} color={M.t3}>Total: </Mono><Mono size={8} color={M.t1}>{gateLog.total_checks ?? 0}</Mono></div>
              <div><Mono size={8} color={M.t3}>Eligible: </Mono><Mono size={8} color={M.green}>{gateLog.eligible_count ?? 0}</Mono></div>
              <div><Mono size={8} color={M.t3}>Mint Allowed: </Mono><Mono size={8} color={M.blue}>{gateLog.mint_allowed_count ?? 0}</Mono></div>
            </div>
          )}
        </Panel>

        {/* Confidence multiplier + epoch analytics */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <Panel title="Confidence Multiplier" badge="SEPARATION RATIO" badgeColor={M.gold} bg={M.bg1} bd={M.bd}>
            {!apiKey ? (
              <EmptyState msg="API KEY REQUIRED" />
            ) : multLoading ? (
              <Loader />
            ) : (
              <div>
                <StatCard label="Multiplier" value={multEnabled ? 'ACTIVE' : 'DISABLED'} accent={multEnabled ? M.green : M.t3} bg={M.bg2} />
                <div style={{ marginTop: 10, fontFamily: F.body, fontSize: 10, color: M.t2, lineHeight: 1.6 }}>
                  confidence_score × min(1.0, bt_strat_ratio).
                  <br />
                  ratio=1.261 (Phase 143 diagonal, N=11, touchpad_corners, proper LOO).
                  Classification: 63.6% (7/11) · testnet only.
                </div>
                {multData && (
                  <div style={{ marginTop: 8, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    <Badge color={M.blue}>floor={multData.confidence_multiplier_floor ?? 0.0}</Badge>
                    <Badge color={multEnabled ? M.green : M.t3}>{multEnabled ? 'ENABLED' : 'DISABLED'}</Badge>
                  </div>
                )}
              </div>
            )}
          </Panel>

          <Panel title="Epoch Window" badge="DUAL-PRIMITIVE TEMPORAL" badgeColor={M.blue} bg={M.bg1} bd={M.bd}>
            {!apiKey ? (
              <EmptyState msg="API KEY REQUIRED" />
            ) : epochLoading ? (
              <Loader />
            ) : epochData ? (
              <div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {[
                    ['Enabled',    epochData.epoch_window_enabled ? 'YES' : 'NO', epochData.epoch_window_enabled ? M.green : M.t3],
                    ['Window',     `${(epochData.epoch_window_seconds || 86400)} s`,   M.blue ],
                    ['n',          epochData.n ?? '—',  M.t1  ],
                    ['p50',        epochData.p50 != null ? `${epochData.p50.toFixed(0)}s` : '—', M.t2 ],
                    ['p95',        epochData.p95 != null ? `${epochData.p95.toFixed(0)}s` : '—', M.gold],
                    ['Rec. Window',epochData.recommended_window_seconds != null ? `${epochData.recommended_window_seconds}s` : '—', M.blue],
                  ].map(([k, v, c]) => (
                    <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: `1px solid ${M.bd}20` }}>
                      <Mono size={8} color={M.t3}>{k}</Mono>
                      <Mono size={8} color={c}>{v}</Mono>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <EmptyState msg="NO EPOCH DATA" />
            )}
          </Panel>
        </div>
      </div>

      {/* Dry run status */}
      <Panel title="Mint Gate Status" badge="POST /agent/mint-vhp" badgeColor={M.blue} bg={M.bg1} bd={M.bd}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 10 }}>
          {[
            { name: 'Gate 1 — Audit Valid',     color: M.blue },
            { name: 'Gate 2 — PITL Pass',       color: M.blue },
            { name: 'Gate 3 — Not Dry Run',     color: M.orange },
            { name: 'Gate 4 — IoSwarm Quorum',  color: M.t3 },
            { name: 'Gate 5 — Dual Primitive',  color: dualGateEnabled ? M.green : M.t3 },
          ].map((gate, i) => (
            <div key={i} style={{
              background:   M.bg2,
              border:       `1px solid ${gate.color}30`,
              borderTop:    `2px solid ${gate.color}`,
              borderRadius: 6,
              padding:      '8px 10px',
            }}>
              <div style={{ fontFamily: F.body, fontSize: 9, color: gate.color, lineHeight: 1.4 }}>
                {gate.name}
              </div>
            </div>
          ))}
        </div>
        <div style={{ marginTop: 10, fontFamily: F.body, fontSize: 10, color: M.t3, lineHeight: 1.6 }}>
          dry_run=True active — Gate 3 blocks all mint attempts until
          POST /agent/commit-activation with separation_ok AND l4_ok preflight pass.
        </div>
      </Panel>
    </motion.div>
  )
}

// ─── PAGE: FEDERATION ──────────────────────────────────────────────────────────
function FederationPage() {
  const apiKey = useAuthStore(s => s.apiKey)
  const { data: peersData, isLoading, error } = useFederationPeers()

  const peers = peersData?.peers || []
  const hasPeers = peers.length > 0

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

      {!apiKey && (
        <div style={{ background: `${M.gold}12`, border: `1px solid ${M.gold}40`, borderRadius: 8, padding: '10px 16px' }}>
          <Mono size={9} color={M.gold}>⚠ Operator api_key required for federation peer access</Mono>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
        <StatCard label="Peer Count" value={peers.length} accent={M.blue} bg={M.bg1} />
        <StatCard
          label="Network Status"
          value={hasPeers ? 'ACTIVE' : 'EXPANSION READY'}
          accent={hasPeers ? M.green : M.t3}
          bg={M.bg1}
        />
        <StatCard
          label="Broadcast Mode"
          value={peersData?.broadcast_enabled ? 'LIVE' : 'DISABLED'}
          accent={peersData?.broadcast_enabled ? M.green : M.t3}
          bg={M.bg1}
        />
      </div>

      <Panel
        title="Federation Peer Network"
        badge={hasPeers ? `${peers.length} PEERS CONNECTED` : 'NETWORK EXPANSION READY'}
        badgeColor={hasPeers ? M.green : M.t3}
        bg={M.bg1}
        bd={M.bd}
      >
        {!apiKey ? (
          <EmptyState msg="API KEY REQUIRED" sub="Provide operator api_key to view federation peers" />
        ) : isLoading ? (
          <Loader />
        ) : error ? (
          <EmptyState msg="FEDERATION UNAVAILABLE" sub="Bridge offline or federation_broadcast_enabled=False" />
        ) : !hasPeers ? (
          <div style={{ textAlign: 'center', padding: '2rem' }}>
            <div style={{
              fontFamily:   F.display,
              fontSize:     22,
              fontWeight:   700,
              color:        M.blue,
              marginBottom: 8,
              letterSpacing: 2,
            }}>
              NETWORK EXPANSION READY
            </div>
            <div style={{ fontFamily: F.body, fontSize: 11, color: M.t2, lineHeight: 1.7, maxWidth: 400, margin: '0 auto' }}>
              No federation peers registered yet. Configure{' '}
              <Mono size={9} color={M.blue}>FEDERATION_BROADCAST_PEERS</Mono>
              {' '}(comma-separated URLs) in bridge/.env.testnet.
              Once peers are active, BLOCK verdicts will be broadcast in real-time via
              HMAC-SHA256 authenticated POST requests.
            </div>
            <div style={{ marginTop: 16, display: 'flex', gap: 8, justifyContent: 'center' }}>
              <Badge color={M.blue}>POST /federation/threat-signal</Badge>
              <Badge color={M.blue}>GET /federation/peers</Badge>
              <Badge color={M.t3}>HMAC-SHA256 AUTH</Badge>
            </div>
          </div>
        ) : (
          <div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {peers.map((peer, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.05 }}
                  style={{
                    background:   M.bg2,
                    border:       `1px solid ${M.bd}`,
                    borderLeft:   `3px solid ${M.blue}`,
                    borderRadius: 6,
                    padding:      '10px 14px',
                    display:      'flex',
                    alignItems:   'center',
                    justifyContent: 'space-between',
                  }}
                >
                  <div>
                    <Mono size={10} color={M.t1}>{peer.url || peer.peer_url || `Peer ${i + 1}`}</Mono>
                    {peer.last_broadcast_at && (
                      <div style={{ marginTop: 3 }}>
                        <Mono size={7} color={M.t3}>last broadcast: </Mono>
                        <Mono size={7} color={M.t2}>{peer.last_broadcast_at}</Mono>
                      </div>
                    )}
                  </div>
                  <Badge color={peer.active !== false ? M.green : M.t3}>
                    {peer.active !== false ? 'ACTIVE' : 'INACTIVE'}
                  </Badge>
                </motion.div>
              ))}
            </div>
          </div>
        )}
      </Panel>

      {/* Federation architecture */}
      <Panel title="Architecture" badge="PHASE 80" badgeColor={M.blue} bg={M.bg1} bd={M.bd}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
          {[
            {
              title: 'FederationBroadcastAgent',
              desc:  'Event-driven: subscribes ruling_block_committed bus. <100ms peer delivery via HMAC-SHA256 HTTP POST.',
            },
            {
              title: 'FederatedThreatRegistry.sol',
              desc:  'addThreatSignal / revokeThreatSignal / isThreatSignaled(). UNIQUE active-flag anti-replay. 150× faster than Phase 34.',
            },
            {
              title: 'Startup Recovery',
              desc:  '_recover_unbroadcast() on boot — ensures no BLOCK verdict is missed if peer was offline during adjudication.',
            },
          ].map(card => (
            <div key={card.title} style={{
              background:   M.bg2,
              border:       `1px solid ${M.bd}`,
              borderRadius: 6,
              padding:      '12px 14px',
            }}>
              <div style={{ fontFamily: F.display, fontSize: 12, fontWeight: 700, color: M.blue, marginBottom: 6 }}>
                {card.title}
              </div>
              <div style={{ fontFamily: F.body, fontSize: 10, color: M.t2, lineHeight: 1.6 }}>
                {card.desc}
              </div>
            </div>
          ))}
        </div>
      </Panel>
    </motion.div>
  )
}

// ─── NAVIGATION ────────────────────────────────────────────────────────────────
function MfrNav() {
  return (
    <nav style={{
      display:      'flex',
      gap:          2,
      padding:      '8px 20px',
      borderBottom: `1px solid ${M.bd}`,
      background:   M.bg1,
      overflowX:    'auto',
    }}>
      {MFR_NAV.map(item => (
        <NavLink
          key={item.path}
          to={item.path}
          style={({ isActive }) => ({
            fontFamily:    F.display,
            fontSize:      11,
            fontWeight:    700,
            letterSpacing: 1.5,
            textDecoration:'none',
            padding:       '5px 14px',
            borderRadius:  5,
            color:         isActive ? M.bg : M.t3,
            background:    isActive ? M.blue : 'transparent',
            border:        `1px solid ${isActive ? M.blue : 'transparent'}`,
            transition:    'all .15s',
          })}
        >
          {item.label.toUpperCase()}
        </NavLink>
      ))}
    </nav>
  )
}

// ─── ROOT ──────────────────────────────────────────────────────────────────────
export default function ManufacturerRoot() {
  const navigate  = useNavigate()
  const apiKey    = useAuthStore(s => s.apiKey)
  const setApiKey = useAuthStore(s => s.setApiKey)

  return (
    <div style={{ minHeight: '100vh', background: M.bg, display: 'flex', flexDirection: 'column' }}>

      {/* Top bar */}
      <div style={{
        display:      'flex',
        alignItems:   'center',
        justifyContent:'space-between',
        padding:      '8px 20px',
        background:   M.bg1,
        borderBottom: `1px solid ${M.bd}`,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button
            onClick={() => navigate('/')}
            style={{
              background: 'none', border: `1px solid ${M.bd}`, borderRadius: 5,
              color: M.t3, fontFamily: F.mono, fontSize: 8, padding: '3px 10px',
              cursor: 'pointer', letterSpacing: 1,
            }}
          >
            ← TIERS
          </button>
          <div style={{
            fontFamily: F.display, fontSize: 18, fontWeight: 700,
            color: M.blue, letterSpacing: 3,
          }}>
            MANUFACTURER
          </div>
          <Mono size={8} color={M.t3}>Certify Hardware · Data Lineage · ioSwarm · VHP Pipeline</Mono>
        </div>
        <BridgeStatusBar accent={M.blue} />
      </div>

      {/* API key bar */}
      <ApiKeyBar apiKey={apiKey} setApiKey={setApiKey} />

      {/* Navigation */}
      <MfrNav />

      {/* Page content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px' }}>
        <AnimatePresence mode="wait">
          <Routes>
            <Route index                     element={<DeviceCertificationPage />} />
            <Route path="devices"            element={<DeviceCertificationPage />} />
            <Route path="data"               element={<DataSovereigntyPage />} />
            <Route path="infra"              element={<IoSwarmInfraPage />} />
            <Route path="vhp"                element={<VHPMintPipelinePage />} />
            <Route path="federation"         element={<FederationPage />} />
          </Routes>
        </AnimatePresence>
      </div>

      {/* Deployed addresses footer */}
      <AddressStrip />
    </div>
  )
}
