// QorTroller Gamer View — the player-passport cockpit.
//
// Ported from the Claude Design artifact "Gamer View.dc.html"
//   (claude.ai/design project a007e7f0-727a-4f51-a823-c4009a1af000 — canonical source,
//    re-fetchable via the DesignSync MCP). The .dc.html runs on the design runtime; this is
//    the faithful React port wired to the LIVE bridge.
//
// Hero: a deterministic Humanity Sigil (inline mulberry32 crest) as an AURA behind a
// translucent Controller-Twin rectangle; five HUD zones (Grind / Tournament / Your Data /
// Sovereignty) ring it. Honesty-as-aesthetic: every color is driven by the server's
// visual_state + BCRA lane states — green is earned, degraded/unverified render amber, revoked/
// disconnected render rose. Nothing fakes a verdict.
//
// HONESTY PORT NOTES (where this diverges from the demo artifact, on purpose):
//   - State is the LIVE bridge only. The artifact's manual "Signal Override" dock (which could
//     fake `live`) is REMOVED; the dock keeps presentation-only controls (glow + vibe layers).
//   - The Sigil seeds from the REAL device_id = keccak256(pubkey) (session-status); label shows
//     the exact seed + "device-derived, not biometric" per the non-negotiable.
//   - Consent is read-only here: grant/revoke is wallet-signed in the Consent Cockpit (/consent),
//     never click-faked (the sovereignty invariant — the bridge never sets consent).
//   - All hooks are noMock where grind-critical; a bridge outage shows the honest banner.

import React from 'react'
import {
  useBridgeConnectivity, usePlayerSessionStatus, useGrindChain, useConsentStatus,
} from '../api/bridgeApi'
import { isMockActive } from '../api/mockBridge'

// ── palette (the design's amber-action / chain-green-earned / rose-blocked language) ──
const C = {
  bg: '#04060a', chain: '#5bd6a3', amber: '#f0a868', rose: '#d65b78',
  dormant: '#5a6675', faint: '#5a6675', dim: '#8a96a5', text: '#d4dde8',
  panel: '#0a0e14', line: '#1a2230', line2: '#243044',
}

// ── hashing + PRNG (inline mulberry32; same math as the artifact + brp/hash) ──
function fnv1a(str) { let h = 0x811c9dc5; for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 0x01000193) } return h >>> 0 }
function mulberry32(a) { return function () { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296 } }
function lerpHex(a, b, t) {
  const pa = [parseInt(a.slice(1, 3), 16), parseInt(a.slice(3, 5), 16), parseInt(a.slice(5, 7), 16)]
  const pb = [parseInt(b.slice(1, 3), 16), parseInt(b.slice(3, 5), 16), parseInt(b.slice(5, 7), 16)]
  const c = pa.map((v, i) => Math.round(v + (pb[i] - v) * t))
  return `rgb(${c[0]},${c[1]},${c[2]})`
}
function initGeom(seed) {
  const rng = mulberry32(seed)
  const k = 5 + Math.floor(rng() * 4)
  const ringCount = 4 + Math.floor(rng() * 2)
  const rings = []
  for (let r = 0; r < ringCount; r++) rings.push({ rad: 0.30 + r * (0.60 / ringCount) + rng() * 0.03, type: Math.floor(rng() * 5), amp: 0.035 + rng() * 0.085 })
  return { k, rings, coreSides: 3 + Math.floor(rng() * 5), spin: rng() < 0.5 ? -1 : 1, tickN: k * (2 + Math.floor(rng() * 2)), forceSeed: rng() * 1000, tremor: Array.from({ length: 22 }, () => 0.25 + rng() * 0.75) }
}

// ── honesty grammar ──
const VS_META = {
  'live': { word: 'LIVE', tone: 'live' }, 'dry-run': { word: 'DRY-RUN', tone: 'pending' },
  'emulated': { word: 'EMULATED', tone: 'pending' }, 'frozen-disabled': { word: 'FROZEN', tone: 'dormant' },
  'revoked': { word: 'REVOKED', tone: 'blocked' }, 'unverified': { word: 'UNVERIFIED', tone: 'pending' },
}
const LANE_META = {
  connected: { word: 'CONNECTED', tone: 'live' }, degraded: { word: 'DEGRADED', tone: 'pending' },
  disconnected: { word: 'DISCONNECTED', tone: 'blocked' }, unknown: { word: 'UNKNOWN', tone: 'dormant' },
}
const vsMeta = (vs) => VS_META[vs] || { word: String(vs || 'UNKNOWN').toUpperCase(), tone: 'pending' }
const laneMeta = (s) => LANE_META[s] || { word: 'UNKNOWN', tone: 'dormant' }
const toneColor = (t) => ({ live: C.chain, verified: C.chain, pending: C.amber, blocked: C.rose, mock: C.rose, dormant: C.dormant }[t] || C.dormant)
const mid = (h) => (h && h.length > 18 ? h.slice(0, 10) + '…' + h.slice(-8) : (h || '—'))

// ── canvas drawing (verbatim logic from the artifact) ──
function drawMotif(ctx, type, rr, a) {
  const y = -rr
  switch (type) {
    case 0: ctx.beginPath(); ctx.moveTo(0, y - a); ctx.lineTo(0, y + a); ctx.stroke(); break
    case 1: ctx.beginPath(); ctx.arc(0, 0, rr, -Math.PI / 2 - 0.16, -Math.PI / 2 + 0.16); ctx.stroke(); break
    case 2: for (let d = -1; d <= 1; d++) { ctx.beginPath(); ctx.arc(d * a * 0.85, y, 1.4, 0, Math.PI * 2); ctx.fill() } break
    case 3: ctx.beginPath(); ctx.moveTo(-a, y + a); ctx.lineTo(0, y - a); ctx.lineTo(a, y + a); ctx.stroke(); break
    case 4: ctx.beginPath(); ctx.moveTo(-a * 0.75, y); ctx.lineTo(0, y - a * 1.25); ctx.lineTo(a * 0.75, y); ctx.closePath(); ctx.stroke(); break
    default: break
  }
}
function drawSigil(cv, geom, col, proven, glow, t, reduced) {
  if (!cv) return
  const dpr = window.devicePixelRatio || 1
  const cw = cv.clientWidth || 320, ch = cv.clientHeight || 320
  if (cv.width !== Math.round(cw * dpr)) { cv.width = Math.round(cw * dpr); cv.height = Math.round(ch * dpr) }
  const ctx = cv.getContext('2d'); ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, cw, ch)
  const cx = cw / 2, cy = ch / 2, R = Math.min(cw, ch) * 0.44, g = geom
  ctx.save(); ctx.translate(cx, cy); ctx.lineCap = 'round'; ctx.lineJoin = 'round'
  ctx.strokeStyle = col; ctx.fillStyle = col; ctx.shadowColor = col; ctx.shadowBlur = (proven ? 24 : 11) * glow
  ctx.lineWidth = 1.5; ctx.globalAlpha = 0.92; ctx.beginPath(); ctx.arc(0, 0, R, 0, Math.PI * 2); ctx.stroke()
  ctx.lineWidth = 1; ctx.globalAlpha = 0.4; ctx.beginPath(); ctx.arc(0, 0, R * 0.92, 0, Math.PI * 2); ctx.stroke()
  ctx.globalAlpha = 0.55
  for (let i = 0; i < g.tickN; i++) { const a = (i / g.tickN) * Math.PI * 2, r0 = R * 0.93, r1 = R; ctx.beginPath(); ctx.moveTo(Math.cos(a) * r0, Math.sin(a) * r0); ctx.lineTo(Math.cos(a) * r1, Math.sin(a) * r1); ctx.stroke() }
  const spin = reduced ? 0 : (t * 0.00004 * g.spin); ctx.rotate(spin); ctx.lineWidth = 1.4
  for (const ring of g.rings) for (let i = 0; i < g.k; i++) { ctx.save(); ctx.rotate((i / g.k) * Math.PI * 2); ctx.globalAlpha = 0.85; drawMotif(ctx, ring.type, ring.rad * R, ring.amp * R); ctx.restore() }
  ctx.rotate(-spin * 1.6); ctx.globalAlpha = 0.95; ctx.lineWidth = 1.5
  const cr = R * 0.17, sides = g.coreSides; ctx.beginPath()
  for (let i = 0; i < sides; i++) { const a = -Math.PI / 2 + (i / sides) * Math.PI * 2, x = Math.cos(a) * cr, y = Math.sin(a) * cr; i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y) }
  ctx.closePath(); ctx.stroke(); ctx.beginPath(); ctx.arc(0, 0, R * 0.045, 0, Math.PI * 2); ctx.fill(); ctx.restore()
}
function drawSignals(forceCv, tremorCv, geom, active, col, t, reduced) {
  const ph = (reduced || !active) ? 0 : t * 0.0022
  if (forceCv) {
    const dpr = window.devicePixelRatio || 1, w = forceCv.clientWidth || 148, h = forceCv.clientHeight || 40
    if (forceCv.width !== Math.round(w * dpr)) { forceCv.width = Math.round(w * dpr); forceCv.height = Math.round(h * dpr) }
    const ctx = forceCv.getContext('2d'); ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, w, h)
    ctx.strokeStyle = C.line; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(0, h - 1.5); ctx.lineTo(w, h - 1.5); ctx.stroke()
    ctx.strokeStyle = col; ctx.lineWidth = 1.5; ctx.globalAlpha = active ? 0.95 : 0.5; ctx.beginPath()
    const fs = geom.forceSeed
    for (let x = 0; x <= w; x += 2) { const u = x / w, env = Math.pow(Math.sin(Math.min(Math.PI, u * Math.PI * 1.08)), 0.7), rip = 0.16 * Math.sin(u * 22 + fs + ph) * Math.sin(u * 7 + fs), v = Math.max(0, Math.min(1, env * 0.82 + rip)), yy = h - 2 - v * (h - 6); x === 0 ? ctx.moveTo(x, yy) : ctx.lineTo(x, yy) }
    ctx.stroke(); ctx.globalAlpha = 1
  }
  if (tremorCv) {
    const dpr = window.devicePixelRatio || 1, w = tremorCv.clientWidth || 120, h = tremorCv.clientHeight || 40
    if (tremorCv.width !== Math.round(w * dpr)) { tremorCv.width = Math.round(w * dpr); tremorCv.height = Math.round(h * dpr) }
    const ctx = tremorCv.getContext('2d'); ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, w, h)
    const bars = geom.tremor, n = bars.length, bw = w / n; ctx.fillStyle = col; ctx.globalAlpha = active ? 0.9 : 0.45
    for (let i = 0; i < n; i++) { const jit = active && !reduced ? 0.18 * Math.sin(t * 0.004 + i * 1.7) : 0, v = Math.max(0.06, Math.min(1, bars[i] + jit)), bh = v * (h - 3); ctx.fillRect(i * bw + 0.6, h - bh, bw - 1.4, bh) }
    ctx.globalAlpha = 1
  }
}

const FONT_MONO = "'JetBrains Mono', monospace"
const FONT_DISP = "'Syne', system-ui, sans-serif"

export function GamerView() {
  const conn = useBridgeConnectivity()
  const sess = usePlayerSessionStatus()
  const grindQ = useGrindChain()
  const consentQ = useConsentStatus()
  const mockActive = isMockActive()

  const visualState = conn.data?.visual_state || 'unverified'
  const L = conn.data?.lanes || {}
  const lanes = {
    controller: L.controller?.state || 'unknown', agents: L.agents?.state || 'unknown',
    chain: L.chain?.state || 'unknown', operational: L.operational?.state || 'unknown',
  }
  const humanity = typeof sess.data?.humanity_prob === 'number' ? sess.data.humanity_prob : null
  const deviceId = sess.data?.device_id || ''
  const latestGic = grindQ.data?.latest_gic_hash || ''
  const grind = {
    chain_length: grindQ.data?.chain_length ?? 0,
    grind_target: grindQ.data?.grind_target ?? 100,
    chain_intact: grindQ.data?.chain_intact,
  }
  const rawConsent = consentQ.data?.categories || consentQ.data?.granted || consentQ.data || {}

  return (
    <Cockpit
      visualState={visualState} lanes={lanes} humanity={humanity}
      deviceId={deviceId} latestGic={latestGic} grind={grind}
      consent={rawConsent} mockActive={mockActive}
    />
  )
}

class Cockpit extends React.Component {
  constructor(props) {
    super(props)
    this._reduced = (typeof window !== 'undefined' && window.matchMedia) ? window.matchMedia('(prefers-reduced-motion: reduce)').matches : false
    this.state = { glow: 0.5, scanOn: false, crtOn: false, grainOn: false, dockOpen: false }
    this.sigilRef = React.createRef(); this.forceRef = React.createRef(); this.tremorRef = React.createRef(); this.ribbonRef = React.createRef()
    this._t = (typeof performance !== 'undefined') ? performance.now() : 0
    this._settleStart = props.visualState === 'live' ? this._t : -1e9
    this._seedFrom(props.deviceId)
    this._loop = this._loop.bind(this)
  }
  _seedFrom(id) { this._seedSrc = id || 'QORTROLLER-AWAITING-CONTROLLER'; this._seed = fnv1a(this._seedSrc); this._geom = initGeom(this._seed) }
  componentDidMount() { this._buildRibbon(); if (this._reduced) this._drawAll(); else this._raf = requestAnimationFrame(this._loop) }
  componentDidUpdate(prev) {
    if (prev.deviceId !== this.props.deviceId) this._seedFrom(this.props.deviceId)
    if (prev.visualState !== 'live' && this.props.visualState === 'live') this._settleStart = (typeof performance !== 'undefined') ? performance.now() : 0
    this._buildRibbon(); if (this._reduced) this._drawAll()
  }
  componentWillUnmount() { if (this._raf) cancelAnimationFrame(this._raf) }
  _loop(ts) { this._t = ts; this._drawAll(); this._raf = requestAnimationFrame(this._loop) }
  _drawAll() {
    drawSigil(this.sigilRef.current, this._geom, this._sigilColor(), this.props.visualState === 'live', this.state.glow, this._t, this._reduced)
    const sig = this._signalState(); drawSignals(this.forceRef.current, this.tremorRef.current, this._geom, sig.active, sig.col, this._t, this._reduced)
  }
  _sigilColor() {
    const vs = this.props.visualState
    if (vs === 'revoked') return C.rose
    if (vs === 'live') { const p = this._reduced ? 1 : Math.min(1, Math.max(0, (this._t - this._settleStart) / 280)); return lerpHex(C.amber, C.chain, p) }
    return C.amber
  }
  _signalState() {
    const vs = this.props.visualState, ln = this.props.lanes.controller
    const active = ln === 'connected' && vs !== 'frozen-disabled' && vs !== 'revoked'
    return { active, col: !active ? C.faint : (vs === 'live' ? C.chain : C.amber) }
  }
  _grindTone() {
    const ci = this.props.grind.chain_intact, ln = this.props.lanes.chain, vs = this.props.visualState
    if (ci === false) return 'blocked'
    if (vs === 'revoked') return 'blocked'
    if (ln === 'disconnected') return 'blocked'
    if (ln === 'unknown' || vs === 'frozen-disabled') return 'dormant'
    if (ln === 'degraded' || vs !== 'live') return 'pending'
    return 'live'
  }
  _buildRibbon() {
    const host = this.ribbonRef.current; if (!host) return
    const col = toneColor(this._grindTone()), len = this.props.grind.chain_length, target = this.props.grind.grind_target || 100
    if (host.childNodes.length !== target) { host.textContent = ''; for (let i = 0; i < target; i++) host.appendChild(document.createElement('div')) }
    const cells = host.childNodes
    for (let i = 0; i < target; i++) {
      const cell = cells[i], filled = i < len, latest = filled && i === len - 1
      cell.style.flex = '1'; cell.style.minWidth = '3px'; cell.style.borderRadius = '1px'
      if (filled) { cell.style.background = col; cell.style.opacity = latest ? '1' : '0.7'; cell.style.boxShadow = latest ? `0 0 ${12 * this.state.glow}px ${col}, inset 0 0 ${8 * this.state.glow}px ${col}` : 'none'; cell.style.borderTop = cell.style.borderBottom = 'none' }
      else { cell.style.background = 'transparent'; cell.style.borderTop = `1px solid ${C.line2}`; cell.style.borderBottom = `1px solid ${C.line2}`; cell.style.opacity = '0.4'; cell.style.boxShadow = 'none' }
    }
  }

  render() {
    const { visualState: vs, lanes, humanity, deviceId, latestGic, grind, consent, mockActive } = this.props
    const s = this.state
    const vm = vsMeta(vs), proven = vs === 'live'

    // passport humanity
    let humanityWord, humanityColor
    if (proven) { humanityWord = 'PROVEN'; humanityColor = C.chain }
    else if (vs === 'revoked') { humanityWord = 'REVOKED'; humanityColor = C.rose }
    else if (vs === 'frozen-disabled') { humanityWord = 'FROZEN'; humanityColor = C.dormant }
    else { humanityWord = vm.word; humanityColor = C.amber }
    const humanityStr = humanity != null ? humanity.toFixed(2) : '—'
    const humanityPct = humanity != null ? Math.round(humanity * 100) + '%' : '0%'

    // on-chain (chain lane)
    const cm = laneMeta(lanes.chain)
    const onchainWord = lanes.chain === 'connected' ? 'ON-CHAIN' : lanes.chain === 'degraded' ? 'CHAIN DEGRADED' : lanes.chain === 'disconnected' ? 'CHAIN OFFLINE' : 'CHAIN UNKNOWN'
    const onchainColor = toneColor(cm.tone)
    const realActive = lanes.controller === 'connected' && proven
    const realityColor = realActive ? C.chain : (lanes.controller === 'disconnected' || vs === 'revoked') ? C.rose : (vs === 'frozen-disabled') ? C.dormant : C.amber

    // twin (controller lane)
    const ctrl = laneMeta(lanes.controller)
    const twinWord = lanes.controller === 'connected' ? 'CONNECTED · 1 kHz' : ctrl.word
    const twinColor = toneColor(ctrl.tone)

    // sigil verdict
    let sigilWord, sigilColor
    if (proven) { sigilWord = 'PROVEN'; sigilColor = C.chain }
    else if (vs === 'revoked') { sigilWord = 'REVOKED'; sigilColor = C.rose }
    else if (vs === 'frozen-disabled') { sigilWord = 'FROZEN'; sigilColor = C.dormant }
    else { sigilWord = vm.word; sigilColor = C.amber }

    // flag banner
    const notLive = vs !== 'live'
    const flagDesc = ({ 'dry-run': 'Inputs replayed — not anchored on-chain.', 'emulated': 'Synthetic controller input — humanity not proven.', 'frozen-disabled': 'Session frozen — counting suspended.', 'revoked': 'Attestation revoked — sovereignty controls only.', 'unverified': 'Humanity not yet proven this session.' }[vs] || '')

    // grind
    const grindTone = this._grindTone(), grindColor = toneColor(grindTone)
    const chainLen = grind.chain_length, grindTarget = grind.grind_target || 100, grindLevel = Math.floor(chainLen / 10)
    const grindWord = grindTone === 'live' ? 'INTACT' : grindTone === 'pending' ? (lanes.chain === 'degraded' ? 'CHAIN DEGRADED' : vm.word) : grindTone === 'blocked' ? (lanes.chain === 'disconnected' ? 'BRIDGE UNREACHABLE' : 'CHAIN BROKEN') : 'STALE'
    const grindSub = grindTone === 'live' ? `next milestone in ${10 - (chainLen % 10)} · ${grindTarget - chainLen} to GIC-100`
      : grindTone === 'pending' && lanes.chain === 'degraded' ? `Links beyond ${chainLen} pending re-anchor — not counted green until they chain.`
        : grindTone === 'blocked' ? 'Chain unverifiable — links shown rose, none counted as earned.'
          : 'Counting suspended — links held, not advancing.'

    // tournament
    const consGet = (k, alt) => !!(consent?.[k] ?? consent?.[alt])
    const consTournament = consGet('tournament', 'TOURNAMENT_GATE')
    const eligible = proven && lanes.chain === 'connected' && lanes.operational === 'connected' && consTournament
    let tournWord, tournColor = C.amber, tournSub, tournCode = 'isFullyEligible() = false'
    if (eligible) { tournWord = 'ELIGIBLE'; tournColor = C.chain; tournCode = 'isFullyEligible() ✓ on-chain'; tournSub = 'All gates passed — entry verified against chain.' }
    else if (!consTournament) { tournWord = 'CONSENT WITHHELD'; tournSub = 'You have not granted tournament consent — grant it in Sovereignty.' }
    else if (vs === 'revoked') { tournWord = 'REVOKED'; tournColor = C.rose; tournSub = 'Attestation revoked — eligibility cannot be asserted.' }
    else if (!proven) { tournWord = 'NOT ELIGIBLE'; tournSub = `Humanity ${vm.word.toLowerCase()} — prove a live session to qualify.` }
    else if (lanes.chain !== 'connected') { tournWord = 'NOT ELIGIBLE'; tournSub = `Chain ${laneMeta(lanes.chain).word.toLowerCase()} — gate cannot read eligibility.`; if (lanes.chain === 'disconnected') tournColor = C.rose }
    else { tournWord = 'NOT ELIGIBLE'; tournSub = `Operational lane ${laneMeta(lanes.operational).word.toLowerCase()}.` }

    // your data — tier multiplier ONLY, never fiat; muted until attested (no fabricated number)
    const attested = proven && lanes.chain === 'connected'
    let dataWord, dataColor, dataSub
    if (attested) { dataWord = 'ATTESTED'; dataColor = C.chain; dataSub = 'Marketplace dormant (testnet) · value not asserted.' }
    else if (vs === 'revoked') { dataWord = 'REVOKED'; dataColor = C.rose; dataSub = 'Attestation revoked · tier not assertable.' }
    else { dataWord = 'UNVERIFIED'; dataColor = C.amber; dataSub = 'Tier reads from the marketplace once a session is attested · no fiat value (testnet).' }

    const labels = { tournament: 'TOURNAMENT', research: 'RESEARCH', marketplace: 'MARKETPLACE', manufacturer_cert: 'MFR · CERT' }
    const aliases = { tournament: 'TOURNAMENT_GATE', research: 'ANONYMIZED_RESEARCH', marketplace: 'MARKETPLACE', manufacturer_cert: 'MANUFACTURER_CERT' }

    const mono = (size, color, ls = '.04em') => ({ fontFamily: FONT_MONO, fontSize: size, color, letterSpacing: ls })
    const chip = (color) => ({ display: 'inline-flex', alignItems: 'center', gap: 7, padding: '4px 9px', border: `1px solid ${color}`, borderRadius: 2, ...mono(11, color, '.06em'), fontWeight: 500, textTransform: 'uppercase', whiteSpace: 'nowrap', lineHeight: 1 })
    const dot = (color, sz = 6) => ({ width: sz, height: sz, borderRadius: '50%', background: color, boxShadow: `0 0 8px ${color}` })
    const panel = { background: C.panel, border: `1px solid ${C.line}`, borderRadius: 4 }
    const panelHead = { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px 11px', borderBottom: `1px solid ${C.line}` }
    const eyebrow = mono(10.5, C.faint, '.14em')

    return (
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'auto', background: C.bg, fontFamily: FONT_DISP, color: C.text }}>

        {/* PASSPORT STRIP */}
        <header style={{ display: 'flex', alignItems: 'center', gap: 22, minHeight: 62, flexShrink: 0, padding: '0 18px', borderBottom: `1px solid ${C.line}`, background: 'rgba(4,6,10,.94)', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 14 }}>
            <span style={{ fontFamily: FONT_DISP, fontWeight: 700, fontSize: 22, letterSpacing: '-.02em' }}>Qor<span style={{ fontWeight: 800, color: C.amber }}>T</span>roller</span>
            <span style={{ ...mono(10, C.faint, '.16em'), textTransform: 'uppercase', padding: '3px 7px', border: `1px solid ${C.line2}`, borderRadius: 2 }}>V.A.P.I.</span>
          </div>
          <div style={{ flex: 1, minWidth: 170, display: 'flex', flexDirection: 'column', gap: 5 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 10 }}>
              <span style={{ ...mono(10, C.faint, '.14em'), textTransform: 'uppercase' }}>Humanity</span>
              <span style={mono(13, humanityColor)}>{humanityStr} · {humanityWord}</span>
            </div>
            <div style={{ height: 3, background: '#131a24', borderRadius: 2, overflow: 'hidden' }}>
              <div style={{ height: '100%', width: humanityPct, background: humanityColor, borderRadius: 2, transition: 'width .28s, background .28s' }} />
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <span style={{ ...mono(11, onchainColor, '.12em'), textTransform: 'uppercase', display: 'inline-flex', alignItems: 'center', gap: 7 }}><span style={dot(onchainColor, 7)} />{onchainWord}</span>
            <span style={{ ...mono(11, C.faint, '.04em'), textTransform: 'uppercase' }}>merkle <span style={{ color: C.dim }}>{mid(latestGic)}</span></span>
            <span title="reality heartbeat" style={{ ...dot(realityColor, 8) }} />
          </div>
        </header>

        {/* MAIN COCKPIT */}
        <div style={{ flex: 1, minHeight: 0, display: 'grid', gridTemplateColumns: 'minmax(0,1.62fr) minmax(0,1fr)', gap: 14, padding: '14px' }} className="qt-cockpit-main">

          {/* CENTER STAGE */}
          <section style={{ position: 'relative', minHeight: 420, border: `1px solid ${C.line}`, borderRadius: 4, overflow: 'hidden', backgroundColor: C.bg, backgroundImage: 'linear-gradient(to right,#1a223044 1px,transparent 1px),linear-gradient(to bottom,#1a223044 1px,transparent 1px)', backgroundSize: '96px 96px,96px 96px' }}>
            {/* Sigil aura (z1, behind) */}
            <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', pointerEvents: 'none', zIndex: 1 }}>
              <canvas ref={this.sigilRef} style={{ width: 'min(54vh,448px)', height: 'min(54vh,448px)', maxWidth: '94%' }} />
            </div>
            {/* Twin rect (z2) — the LIVE 3D controller twin (transparent mode) so the Sigil aura
                (z1) glows through the controller's empty space; figure in front, halo behind. */}
            <div style={{ position: 'absolute', inset: 18, zIndex: 2, border: `1px dashed ${C.line2}`, borderRadius: 4, overflow: 'hidden', boxShadow: 'inset 0 0 64px 12px rgba(4,6,10,.45)' }}>
              <iframe
                title="Your controller — live 3D twin"
                src={`/controller-twin.html?minimal=1&transparent=1${deviceId ? `&device=${encodeURIComponent(deviceId)}` : ''}`}
                style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', border: 'none', background: 'transparent' }}
              />
              <span style={{ position: 'absolute', top: 12, left: 14, ...mono(10, C.faint, '.16em'), textTransform: 'uppercase', pointerEvents: 'none' }}>3D Controller Twin · live</span>
              <span style={{ position: 'absolute', top: 12, right: 14, ...mono(10, twinColor, '.12em'), textTransform: 'uppercase', pointerEvents: 'none' }}>● {twinWord}</span>
            </div>
            {/* honesty flag banner */}
            {notLive && (
              <div style={{ position: 'absolute', top: 16, left: '50%', transform: 'translateX(-50%)', zIndex: 6, display: 'flex', alignItems: 'center', gap: 10, padding: '7px 14px', background: 'rgba(10,14,20,.95)', border: `1px solid ${sigilColor}`, borderRadius: 3, maxWidth: '80%' }}>
                <span style={dot(sigilColor, 7)} />
                <span style={{ ...mono(11, sigilColor, '.1em'), fontWeight: 600, textTransform: 'uppercase' }}>{vm.word}</span>
                <span style={mono(10.5, C.dim, '.02em')}>{flagDesc}</span>
              </div>
            )}
            {/* stage vignette (z3) */}
            <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 3, background: 'radial-gradient(ellipse 76% 76% at center, transparent 46%, rgba(4,6,10,.5) 100%)' }} />
            {/* sigil verdict */}
            <div style={{ position: 'absolute', left: 0, right: 0, top: '50%', transform: 'translateY(28px)', zIndex: 4, textAlign: 'center', pointerEvents: 'none' }}>
              <span style={{ ...mono(11, sigilColor, '.18em'), fontWeight: 600, textTransform: 'uppercase' }}>Humanity Sigil · {sigilWord}</span>
            </div>
            {/* signals + identity */}
            <div style={{ position: 'absolute', left: 16, right: 16, bottom: 78, zIndex: 5, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 14, pointerEvents: 'none', flexWrap: 'wrap' }}>
              <div style={{ display: 'flex', gap: 14 }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                  <span style={{ ...mono(9.5, C.faint, '.12em'), textTransform: 'uppercase' }}>trigger force-curve</span>
                  <canvas ref={this.forceRef} style={{ width: 140, height: 38 }} />
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                  <span style={{ ...mono(9.5, C.faint, '.12em'), textTransform: 'uppercase' }}>tremor spectrum</span>
                  <canvas ref={this.tremorRef} style={{ width: 112, height: 38 }} />
                </div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 3, alignItems: 'flex-end', textAlign: 'right' }}>
                <span style={{ ...mono(9, C.faint, '.1em'), textTransform: 'uppercase' }}>seed · device_id = keccak256(pubkey)</span>
                <span style={mono(11, C.dim, '.02em')}>{deviceId ? mid(deviceId) : 'awaiting controller'}</span>
                <span style={{ ...mono(9, C.line2, '.06em'), textTransform: 'uppercase' }}>mulberry32 0x{this._seed.toString(16).padStart(8, '0')} · device-derived, not biometric</span>
              </div>
            </div>
            {/* grind ribbon */}
            <div style={{ position: 'absolute', left: 14, right: 14, bottom: 14, zIndex: 5, background: 'rgba(10,14,20,.93)', border: `1px solid ${grindColor}`, borderRadius: 4, padding: '11px 14px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 8 }}>
                <span style={{ ...eyebrow, textTransform: 'uppercase' }}>Grind · Integrity · Chain</span>
                <span style={mono(11, C.dim)}><span style={{ color: C.amber, fontSize: 14, fontWeight: 600 }}>{chainLen}</span><span style={{ color: C.faint }}> / {grindTarget} · </span><span style={{ color: grindColor }}>● {grindWord}</span></span>
              </div>
              <div ref={this.ribbonRef} style={{ display: 'flex', gap: 1, height: 16, background: '#131a24', padding: 1, borderRadius: 2 }} />
            </div>
          </section>

          {/* HUD COLUMN */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14, minHeight: 0 }}>
            {/* GRIND meta */}
            <article style={{ ...panel, flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
              <header style={panelHead}><span style={{ ...eyebrow, textTransform: 'uppercase' }}>Grind</span><span style={chip(grindColor)}><span style={dot(grindColor)} />{grindWord}</span></header>
              <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 14, flex: 1, justifyContent: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
                  <span style={{ fontFamily: FONT_DISP, fontWeight: 800, fontSize: 46, lineHeight: 1, color: C.amber }}>{chainLen}</span>
                  <span style={mono(14, C.faint)}>/ {grindTarget}</span>
                  <span style={{ ...mono(11, C.dim, '.06em'), textTransform: 'uppercase', marginLeft: 'auto' }}>lv.{grindLevel}</span>
                </div>
                <div style={{ ...mono(11.5, C.dim, '.02em'), lineHeight: 1.5 }}>{grindSub}</div>
              </div>
            </article>
            {/* TOURNAMENT */}
            <article style={panel}>
              <header style={panelHead}><span style={{ ...eyebrow, textTransform: 'uppercase' }}>Tournament</span><span style={chip(tournColor)}><span style={dot(tournColor)} />{tournWord}</span></header>
              <div style={{ padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 7 }}>
                <span style={mono(11.5, tournColor, '.02em')}>{tournCode}</span>
                <span style={{ ...mono(11, C.dim, '.02em'), lineHeight: 1.5 }}>{tournSub}</span>
              </div>
            </article>
            {/* YOUR DATA */}
            <article style={panel}>
              <header style={panelHead}><span style={{ ...eyebrow, textTransform: 'uppercase' }}>Your Data</span><span style={chip(dataColor)}><span style={dot(dataColor)} />{dataWord}</span></header>
              <div style={{ padding: '14px 16px', display: 'flex', alignItems: 'center', gap: 16 }}>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 3 }}>
                  <span style={{ fontFamily: FONT_DISP, fontWeight: 800, fontSize: 34, lineHeight: 1, color: attested ? dataColor : C.dormant }}>{attested ? '—' : '—'}</span>
                  <span style={mono(18, attested ? dataColor : C.dormant)}>×</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <span style={{ ...mono(11, C.dim, '.04em'), textTransform: 'uppercase' }}>tier multiplier</span>
                  <span style={{ ...mono(10.5, C.faint, '.02em'), lineHeight: 1.45 }}>{dataSub}</span>
                </div>
              </div>
            </article>
          </div>
        </div>

        {/* SOVEREIGNTY STRIP — read-only; granting is wallet-signed in /consent */}
        <footer style={{ flexShrink: 0, display: 'flex', alignItems: 'center', gap: 18, padding: '0 18px', minHeight: 58, borderTop: `1px solid ${C.line}`, background: 'rgba(4,6,10,.94)', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <span style={{ ...eyebrow, textTransform: 'uppercase' }}>Sovereignty</span>
            <a href="/consent" style={{ ...mono(9.5, C.amber, '.06em'), textTransform: 'uppercase', textDecoration: 'none' }}>you grant · you revoke →</a>
          </div>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            {Object.keys(labels).map((key) => {
              const granted = consGet(key, aliases[key]), color = granted ? C.chain : C.dormant
              return (
                <a key={key} href="/consent" style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '7px 11px', border: `1px solid ${granted ? C.line2 : C.line}`, background: granted ? '#0d1218' : 'transparent', borderRadius: 2, ...mono(10.5, granted ? C.text : C.faint, '.06em'), fontWeight: 500, textTransform: 'uppercase', textDecoration: 'none' }}>
                  <span style={dot(color, 6)} /><span>{labels[key]}</span><span style={{ opacity: 0.7 }}>{granted ? 'GRANTED' : 'WITHHELD'}</span>
                </a>
              )
            })}
          </div>
        </footer>

        {mockActive && (
          <div style={{ position: 'fixed', top: 70, left: '50%', transform: 'translateX(-50%)', zIndex: 130, ...mono(11, C.amber, '.08em'), border: `1px solid ${C.amber}55`, background: 'rgba(240,168,104,.1)', borderRadius: 6, padding: '6px 12px' }}>
            ● BRIDGE OFFLINE — placeholder, no live proof
          </div>
        )}

        {/* vibe overlays (opt-in, presentation only) */}
        {s.scanOn && <div style={{ position: 'fixed', inset: 0, pointerEvents: 'none', zIndex: 100, mixBlendMode: 'multiply', background: 'repeating-linear-gradient(to bottom,transparent 0,transparent 2px,rgba(0,0,0,.5) 2px,rgba(0,0,0,.5) 3px)' }} />}
        {s.crtOn && <div style={{ position: 'fixed', inset: 0, pointerEvents: 'none', zIndex: 101, background: 'radial-gradient(ellipse 110% 90% at center,transparent 55%,rgba(0,0,0,.55) 100%)' }} />}

        {/* DISPLAY dock — presentation only (NO state override; the bridge is the only truth source) */}
        <aside style={{ position: 'fixed', right: 14, bottom: 14, zIndex: 120, width: 230, background: 'rgba(10,14,20,.97)', border: `1px solid ${C.line2}`, borderRadius: 4, boxShadow: '0 10px 30px -10px #000d' }}>
          <button type="button" onClick={() => this.setState({ dockOpen: !s.dockOpen })} style={{ width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '9px 13px', background: 'transparent', border: 0, borderBottom: s.dockOpen ? `1px solid ${C.line}` : 0, cursor: 'pointer' }}>
            <span style={{ ...mono(10, C.amber, '.16em'), textTransform: 'uppercase' }}>◢ Display</span>
            <span style={mono(11, C.faint)}>{s.dockOpen ? '▾' : '▸'}</span>
          </button>
          {s.dockOpen && (
            <div style={{ padding: '12px 13px', display: 'flex', flexDirection: 'column', gap: 11 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ ...mono(9.5, C.faint, '.12em'), textTransform: 'uppercase' }}>glow</span>
                <span style={mono(10, C.amber)}>{Math.round(s.glow * 100)}%</span>
              </div>
              <input type="range" min="0" max="1" step="0.05" value={s.glow} onChange={(e) => this.setState({ glow: parseFloat(e.target.value) })} style={{ width: '100%', accentColor: C.amber, cursor: 'pointer' }} />
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4 }}>
                {[['Scan', 'scanOn'], ['CRT', 'crtOn']].map(([lbl, key]) => (
                  <button key={key} type="button" onClick={() => this.setState({ [key]: !s[key] })} style={{ padding: '6px 4px', border: `1px solid ${s[key] ? C.amber : C.line}`, background: s[key] ? 'rgba(240,168,104,.06)' : C.panel, borderRadius: 2, ...mono(9.5, s[key] ? C.amber : C.dim, '.04em'), textTransform: 'uppercase', cursor: 'pointer' }}>{lbl}</button>
                ))}
              </div>
            </div>
          )}
        </aside>
      </div>
    )
  }
}
