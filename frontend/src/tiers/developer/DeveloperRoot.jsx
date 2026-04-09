// src/tiers/developer/DeveloperRoot.jsx
import React, { useState } from 'react'
import { motion } from 'framer-motion'
import {
  BridgeStatusBar, DemoModeBanner, Panel, ErrorBoundary, ChainAddressLink,
} from '../../shared/components'
import {
  useTournamentReadinessScore, usePreflightStatus, useSupervisorStatus,
  useCampaignStatus, useProtocolIntelligence, useSeparationRatio,
  useEdgeAIProfile, useL4CalibrationStatus,
} from '../../shared/api/hooks'
import { useAuthStore } from '../../shared/store/authStore'
import { FONTS, DEVELOPER } from '../../shared/design/tokens'
import { PAGE_ENTER, STAGGER_CONTAINER, STAGGER_ITEM, GAUGE_FILL } from '../../shared/design/animations'

const NAV_ITEMS = [
  'Tournament Scorecard',
  'Gate Tester',
  'Pipeline Health',
  'Separation Status',
  'SDK Quickstart',
]

export default function DeveloperRoot() {
  const [activePage, setActivePage] = useState(0)
  const apiKey = useAuthStore(s => s.apiKey)
  const setApiKey = useAuthStore(s => s.setApiKey)
  const [keyInput, setKeyInput] = useState(apiKey)

  return (
    <div style={{ minHeight: '100vh', background: DEVELOPER.bg }}>
      <nav style={{
        display: 'flex', alignItems: 'center', height: 48,
        padding: '0 1.25rem', background: '#030508',
        borderBottom: `1px solid ${DEVELOPER.bd}`, gap: 0,
      }}>
        <div onClick={() => window.location.href='/'} style={{
          fontFamily: FONTS.display, fontSize: 19, fontWeight: 700,
          letterSpacing: 4, color: DEVELOPER.orange, marginRight: 20,
          cursor: 'pointer', flexShrink: 0,
        }}>
          VAPI<span style={{ color: DEVELOPER.t3, fontWeight: 400, fontSize: 13 }}> · DEVELOPER</span>
        </div>

        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10 }}>
          <BridgeStatusBar tier="developer" />
          <input
            value={keyInput}
            onChange={e => setKeyInput(e.target.value)}
            onBlur={() => setApiKey(keyInput)}
            placeholder="api_key ..."
            style={{
              fontFamily: FONTS.mono, fontSize: 9, padding: '4px 10px',
              background: DEVELOPER.bg1, border: `1px solid ${DEVELOPER.bd}`,
              borderRadius: 4, color: DEVELOPER.orange,
              letterSpacing: '0.8px', width: 140,
              outline: 'none',
            }}
          />
        </div>
      </nav>

      <DemoModeBanner dryRun tier="developer" />

      <div style={{
        display: 'grid', gridTemplateColumns: '220px 1fr',
        gap: '1.25rem', padding: '1.25rem', alignItems: 'start',
      }}>
        {/* Sidebar nav */}
        <div style={{
          background: DEVELOPER.bg1, border: `1px solid ${DEVELOPER.bd}`,
          borderRadius: 8, overflow: 'hidden',
        }}>
          {NAV_ITEMS.map((item, i) => (
            <div
              key={item}
              onClick={() => setActivePage(i)}
              style={{
                padding: '10px 14px',
                display: 'flex', alignItems: 'center', gap: 8,
                cursor: 'pointer',
                borderBottom: `1px solid ${DEVELOPER.bd2}`,
                borderLeft: i === activePage ? `2px solid ${DEVELOPER.orange}` : '2px solid transparent',
                background: i === activePage ? `${DEVELOPER.orange}0a` : 'transparent',
                color: i === activePage ? DEVELOPER.orange : DEVELOPER.t3,
                fontFamily: FONTS.body, fontSize: 11,
                transition: 'all .12s',
              }}
            >
              <span style={{
                width: 4, height: 4, borderRadius: '50%',
                background: 'currentColor', flexShrink: 0,
              }} />
              {item}
            </div>
          ))}

          {/* Live endpoints */}
          <div style={{ padding: '10px 14px' }}>
            <div style={{
              fontFamily: FONTS.display, fontSize: 8, letterSpacing: '2px',
              textTransform: 'uppercase', color: '#1a0e05', marginBottom: 8,
            }}>Live Endpoints</div>
            {[
              'GET /agent/tournament-readiness-score',
              'GET /agent/preflight-status',
              'GET /agent/supervisor-status',
              'GET /agent/separation-ratio-status',
              'GET /gate/{device_id}',
              'WebSocket /ws/records',
            ].map(ep => (
              <div key={ep} style={{
                fontFamily: FONTS.mono, fontSize: 8, color: '#3a1a08',
                lineHeight: 2.2,
              }}>{ep}</div>
            ))}
          </div>
        </div>

        {/* Content */}
        <div>
          <ErrorBoundary accent={DEVELOPER.orange}>
            {activePage === 0 && <TournamentScorecardPage />}
            {activePage === 1 && <GateTesterPage />}
            {activePage === 2 && <PipelineHealthPage />}
            {activePage === 3 && <SeparationStatusPage />}
            {activePage === 4 && <SDKQuickstartPage />}
          </ErrorBoundary>
        </div>
      </div>
    </div>
  )
}

// ─── TOURNAMENT SCORECARD ─────────────────────────────────────
function TournamentScorecardPage() {
  const { data: scoreData }    = useTournamentReadinessScore()
  const { data: preflightData } = usePreflightStatus()
  const { data: l4Data }        = useL4CalibrationStatus()

  const score = scoreData?.score ?? 0.61
  const components = [
    { key: 'Separation ratio',  value: scoreData?.separation_score ?? 0.30, weight: 0.30 },
    { key: 'L4 freshness',      value: l4Data?.stale ? 0 : 0.20,           weight: 0.20 },
    { key: 'Dual gate',         value: scoreData?.dual_gate_score ?? 0.15,  weight: 0.15 },
    { key: 'Epoch window p95',  value: scoreData?.epoch_score ?? 0.15,      weight: 0.15 },
    { key: 'ioSwarm',           value: 0,                                    weight: 0.10, emulated: true },
    { key: 'dry_run cleared',   value: 0,                                    weight: 0.10 },
  ]

  const preflight = [
    { key: 'separation_ratio_gte_1', value: preflightData?.separation_ok,    label: '1.261 >= 1.0 (Phase 143)' },
    { key: 'l4_calibration_fresh',   value: preflightData?.l4_fresh,         label: 'stale (12 feat->13 feat)' },
    { key: 'dry_run_cleared',        value: preflightData?.dry_run_cleared,  label: 'N=0/100' },
    { key: 'governance_hardened',    value: true,                             label: 'PASS' },
    { key: 'vhp_demonstrated',       value: null,                             label: 'PARTIAL' },
  ]

  return (
    <motion.div {...PAGE_ENTER} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.875rem' }}>
        {[
          { label: 'Readiness Score', val: score.toFixed(2), sub: 'of 1.0 · 6-signal', col: DEVELOPER.orange },
          { label: 'Separation Ratio', val: '1.261', sub: 'Phase 143 diagonal · class=63.6%', col: DEVELOPER.green },
          { label: 'PMI Level', val: '0', sub: 'dry_run=True', col: '#ff9500' },
        ].map(c => (
          <div key={c.label} style={{
            background: DEVELOPER.bg1, border: `1px solid ${DEVELOPER.bd}`,
            borderRadius: 7, padding: '0.875rem',
          }}>
            <div style={{
              fontFamily: FONTS.display, fontSize: 8, letterSpacing: '1.5px',
              textTransform: 'uppercase', color: '#3a1a08', marginBottom: 4,
            }}>{c.label}</div>
            <div style={{
              fontFamily: FONTS.mono, fontSize: 22, fontWeight: 500, color: c.col,
            }}>{c.val}</div>
            <div style={{ fontFamily: FONTS.body, fontSize: 9, color: DEVELOPER.t3, marginTop: 2 }}>
              {c.sub}
            </div>
          </div>
        ))}
      </div>

      {/* 6-signal breakdown */}
      <Panel title="Readiness Score Breakdown · 6-Signal Weighted"
        bg={DEVELOPER.bg1} bd={DEVELOPER.bd}>
        <div style={{ padding: '0.75rem 1rem' }}>
          {components.map(c => (
            <div key={c.key} style={{
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '5px 0', borderBottom: `1px solid ${DEVELOPER.bd2}`,
            }}>
              <span style={{
                fontFamily: FONTS.mono, fontSize: 9, color: DEVELOPER.t2,
                width: 160, flexShrink: 0,
              }}>{c.key}</span>
              <span style={{
                fontFamily: FONTS.mono, fontSize: 9, color: DEVELOPER.t3,
                width: 36, flexShrink: 0,
              }}>{(c.weight * 100).toFixed(0)}%</span>
              <div style={{
                flex: 1, height: 5, background: DEVELOPER.bd,
                borderRadius: 3, overflow: 'hidden',
              }}>
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${c.value / c.weight * 100}%` }}
                  transition={{ duration: 1, ease: 'easeOut', delay: 0.1 }}
                  style={{
                    height: '100%', borderRadius: 3,
                    background: c.emulated ? '#ff9500' : DEVELOPER.orange,
                  }}
                />
              </div>
              {c.emulated && (
                <span style={{
                  fontFamily: FONTS.mono, fontSize: 8,
                  color: '#ff9500', flexShrink: 0,
                }}>emulated</span>
              )}
            </div>
          ))}
        </div>
      </Panel>

      {/* Preflight */}
      <Panel title="Preflight · P0 Conditions" badge="BLOCKING" badgeColor="#ff3b5c"
        bg={DEVELOPER.bg1} bd={DEVELOPER.bd}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <tbody>
            {preflight.map(row => {
              const color = row.value === true ? DEVELOPER.t2
                          : row.value === false ? '#ff3b5c'
                          : '#ff9500'
              const valText = row.value === true ? 'PASS'
                            : row.value === false ? row.label
                            : row.label
              return (
                <tr key={row.key} style={{ borderBottom: `1px solid ${DEVELOPER.bd2}` }}>
                  <td style={{
                    padding: '8px 14px',
                    fontFamily: FONTS.mono, fontSize: 10, color: DEVELOPER.t2,
                  }}>{row.key}</td>
                  <td style={{
                    padding: '8px 14px',
                    fontFamily: FONTS.mono, fontSize: 10, color,
                    textAlign: 'right',
                  }}>{valText}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </Panel>
    </motion.div>
  )
}

// ─── GATE TESTER ─────────────────────────────────────────────
// Auth: VAPI bridge uses ?api_key= query param (NOT X-API-Key header)
function GateTesterPage() {
  const [deviceId, setDeviceId] = useState('')
  const [result, setResult]     = useState(null)
  const [loading, setLoading]   = useState(false)
  const apiKey = useAuthStore(s => s.apiKey)

  const test = async () => {
    if (!deviceId) return
    setLoading(true)
    try {
      const url = apiKey
        ? `/gate/${deviceId}?api_key=${encodeURIComponent(apiKey)}`
        : `/gate/${deviceId}`
      const res = await fetch(url)
      setResult(await res.json())
    } catch (e) {
      setResult({ error: e.message })
    } finally {
      setLoading(false)
    }
  }

  return (
    <motion.div {...PAGE_ENTER} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <Panel title="Gate Tester · GET /gate/{device_id}" bg={DEVELOPER.bg1} bd={DEVELOPER.bd}>
        <div style={{ padding: '1rem', display: 'flex', gap: 8 }}>
          <input
            value={deviceId}
            onChange={e => setDeviceId(e.target.value)}
            placeholder="Enter device_id hash (0x...)"
            style={{
              flex: 1, fontFamily: FONTS.mono, fontSize: 10, padding: '6px 10px',
              background: DEVELOPER.bg, border: `1px solid ${DEVELOPER.bd}`,
              borderRadius: 4, color: DEVELOPER.t1, outline: 'none',
            }}
          />
          <button
            onClick={test}
            disabled={loading || !deviceId}
            style={{
              fontFamily: FONTS.mono, fontSize: 9, padding: '6px 16px',
              background: loading ? DEVELOPER.bg : `${DEVELOPER.orange}15`,
              border: `1px solid ${DEVELOPER.orange}35`,
              borderRadius: 4, color: DEVELOPER.orange, cursor: 'pointer',
              letterSpacing: '0.5px',
            }}
          >
            {loading ? 'QUERYING...' : 'RUN GATE'}
          </button>
        </div>
        {result && (
          <div style={{
            margin: '0 1rem 1rem', background: DEVELOPER.bg,
            border: `1px solid ${DEVELOPER.bd}`, borderRadius: 6, padding: '0.875rem',
          }}>
            <pre style={{
              fontFamily: FONTS.mono, fontSize: 10,
              color: result.eligible ? DEVELOPER.t1 : '#ff3b5c',
              whiteSpace: 'pre-wrap', lineHeight: 1.7,
            }}>
              {JSON.stringify(result, null, 2)}
            </pre>
          </div>
        )}
      </Panel>
    </motion.div>
  )
}

// ─── PIPELINE HEALTH ─────────────────────────────────────────
function PipelineHealthPage() {
  const { data: supervisor }   = useSupervisorStatus()
  const { data: campaign }     = useCampaignStatus()
  const { data: intelligence } = useProtocolIntelligence()
  const { data: edgeProfile }  = useEdgeAIProfile()

  const AGENT_NAMES = [
    'SessionAdjudicator','CalibrationIntel','SepRatioMonitor','PoAdAnchorAgent',
    'ClassJDetector','RulingEnforcement','VHPRenewalAgent','CalibWatcher',
    'ProactiveMonitor','InsightSynth','FederationBus','TournamentChain',
    'EnrollmentManager','IoSwarm·Renewal','IoSwarm·Adjudication','IoSwarm·Mint',
  ]

  return (
    <motion.div {...PAGE_ENTER} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {/* Fleet */}
      <Panel title="Agent Fleet · 16 Agents" bg={DEVELOPER.bg1} bd={DEVELOPER.bd}>
        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)',
          gap: 4, padding: '0.75rem',
        }}>
          {AGENT_NAMES.map((name) => {
            const isSwarm = name.includes('IoSwarm')
            return (
              <div key={name} style={{
                background: DEVELOPER.bg, border: `1px solid ${DEVELOPER.bd}`,
                borderRadius: 5, padding: '5px 7px',
                display: 'flex', alignItems: 'center', gap: 5,
              }}>
                <span style={{
                  width: 4, height: 4, borderRadius: '50%', flexShrink: 0,
                  background: isSwarm ? '#1a0e05' : DEVELOPER.t2,
                  animation: !isSwarm ? 'vapi-pulse 2s infinite' : 'none',
                }} />
                <span style={{
                  fontFamily: FONTS.body, fontSize: 9,
                  color: isSwarm ? '#1a0e05' : DEVELOPER.t2,
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1,
                }}>{name}</span>
              </div>
            )
          })}
        </div>
      </Panel>

      {/* Intelligence score */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
        <Panel title="Protocol Intelligence" bg={DEVELOPER.bg1} bd={DEVELOPER.bd}>
          <div style={{ padding: '0.875rem' }}>
            <div style={{
              fontFamily: FONTS.mono, fontSize: 32, fontWeight: 500,
              color: DEVELOPER.orange, marginBottom: 4,
            }}>
              {intelligence?.score ?? 61}
            </div>
            <div style={{ fontFamily: FONTS.body, fontSize: 9, color: DEVELOPER.t3 }}>
              {intelligence?.bottleneck ?? 'separation_ratio < 1.0'}
            </div>
            <div style={{
              height: 4, background: DEVELOPER.bd, borderRadius: 2,
              overflow: 'hidden', marginTop: 10,
            }}>
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${intelligence?.score ?? 61}%` }}
                transition={{ duration: 1.2, ease: 'easeOut' }}
                style={{ height: '100%', background: DEVELOPER.orange, borderRadius: 2 }}
              />
            </div>
          </div>
        </Panel>

        <Panel title="Campaign Status" bg={DEVELOPER.bg1} bd={DEVELOPER.bd}>
          <div style={{ padding: '0.875rem' }}>
            {[
              { label: 'Consecutive clean', val: campaign?.consecutive_clean ?? 47 },
              { label: 'Divergence rate',   val: `${(campaign?.divergence_rate ?? 0.02 * 100).toFixed(1)}%` },
              { label: 'Gate N',            val: campaign?.gate_n ?? 'N/A' },
            ].map(r => (
              <div key={r.label} style={{
                display: 'flex', justifyContent: 'space-between',
                padding: '4px 0', borderBottom: `1px solid ${DEVELOPER.bd2}`,
                fontSize: 10, fontFamily: FONTS.mono,
              }}>
                <span style={{ color: DEVELOPER.t3 }}>{r.label}</span>
                <span style={{ color: DEVELOPER.t1 }}>{r.val}</span>
              </div>
            ))}
          </div>
        </Panel>
      </div>
    </motion.div>
  )
}

// ─── SEPARATION STATUS ───────────────────────────────────────
function SeparationStatusPage() {
  const { data } = useSeparationRatio()
  // Phase 143 honest: 1.261 (diagonal, N=11 touchpad_corners, proper LOO, class=63.6%)
  const ratio    = data?.pooled_ratio ?? 1.261

  return (
    <motion.div {...PAGE_ENTER} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <Panel title="Separation Ratio · Inter-Person Biometric Discriminability"
        badge={ratio >= 1.0 ? 'GATE OPEN (TESTNET)' : 'TOURNAMENT BLOCKER'}
        badgeColor={ratio >= 1.0 ? DEVELOPER.green : '#ff3b5c'}
        bg={DEVELOPER.bg1} bd={DEVELOPER.bd}>
        <div style={{ padding: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: 12 }}>
            <div style={{ fontFamily: FONTS.mono, fontSize: 36, fontWeight: 500, color: ratio >= 1.0 ? DEVELOPER.green : DEVELOPER.orange }}>
              {ratio.toFixed(3)}
            </div>
            <div>
              <div style={{ fontFamily: FONTS.body, fontSize: 11, color: DEVELOPER.t2 }}>
                diagonal covariance (N=11, touchpad_corners, 3 players)
              </div>
              <div style={{ fontFamily: FONTS.body, fontSize: 10, color: DEVELOPER.t3, marginTop: 3 }}>
                Phase 143 proper LOO · classification 63.6% · target &gt; 1.0
              </div>
            </div>
          </div>

          <div style={{ height: 6, background: DEVELOPER.bd, borderRadius: 3, overflow: 'hidden', marginBottom: 4 }}>
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${Math.min(ratio * 100, 100)}%` }}
              transition={{ duration: 1.6, ease: 'easeOut' }}
              style={{ height: '100%', background: ratio >= 1.0 ? DEVELOPER.green : DEVELOPER.orange, borderRadius: 3 }}
            />
          </div>

          <div style={{ fontFamily: FONTS.body, fontSize: 10, color: DEVELOPER.t3, lineHeight: 1.7 }}>
            Phase 142 auto-fallback: N/p=1.375 &lt; 3.0 triggers diagonal covariance (full Tikhonov
            suppressed P1 vs P3 to 0.127 — 97% suppression artifact).<br/>
            Blocking: classification 63.6% &lt; 80% threshold for live tournament gate.
            True fix: touchpad recapture N&gt;30/player + widen tremor FFT window.
          </div>
        </div>
      </Panel>
    </motion.div>
  )
}

// ─── SDK QUICKSTART ───────────────────────────────────────────
function SDKQuickstartPage() {
  const CODE_TS = `import { VAPIClient } from '@vapi-protocol/sdk'

const vapi = new VAPIClient({
  rpc: 'https://babel-api.testnet.iotex.io'
})

// Single call — all 16 agents, 13-feature Mahalanobis
const eligible = await vapi.isFullyEligible(deviceIdHash)

// Dual-primitive: PoAC (physiological) + PoAd (adjudication)
const dual = await vapi.isDualEligible(deviceIdHash, poadHash)
// -> { eligible: true, poac_valid: true, poad_valid: true }`

  const CODE_SOL = `interface IVAPIProtocolLens {
  function isFullyEligible(
    bytes32 deviceIdHash
  ) external view returns (bool);

  function isDualEligible(
    bytes32 deviceIdHash,
    bytes32 poadHash
  ) external view returns (bool, bool, bool);
}

modifier onlyVerified(bytes32 deviceId) {
  require(vapi.isFullyEligible(deviceId), "VAPI: not eligible");
  _;
}`

  return (
    <motion.div {...PAGE_ENTER} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {[
        { lang: 'TypeScript', code: CODE_TS },
        { lang: 'Solidity',   code: CODE_SOL },
      ].map(c => (
        <div key={c.lang} style={{
          background: '#020305', border: `1px solid ${DEVELOPER.bd}`,
          borderRadius: 8, overflow: 'hidden',
        }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '7px 14px', borderBottom: `1px solid ${DEVELOPER.bd}`,
            background: DEVELOPER.bg1,
          }}>
            <span style={{
              fontFamily: FONTS.mono, fontSize: 8, padding: '2px 7px',
              borderRadius: 3, background: `${DEVELOPER.orange}15`,
              color: DEVELOPER.orange, border: `1px solid ${DEVELOPER.orange}30`,
            }}>{c.lang}</span>
            <span style={{ fontFamily: FONTS.body, fontSize: 10, color: DEVELOPER.t3 }}>
              VAPITournamentGate integration
            </span>
          </div>
          <pre style={{
            padding: '0.875rem', fontFamily: FONTS.mono, fontSize: 10,
            lineHeight: 1.75, color: '#d4b898', whiteSpace: 'pre', overflowX: 'auto',
          }}>
            {c.code}
          </pre>
        </div>
      ))}
    </motion.div>
  )
}
