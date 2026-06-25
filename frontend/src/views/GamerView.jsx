// QorTroller Gamer View — the player-passport cockpit, PROVING GROUND language.
//
// Ported from the Claude Design artifact "Gamer View.dc.html" (PROVING GROUND iteration,
//   claude.ai/design project a007e7f0 — canonical source, re-fetchable via the DesignSync MCP).
//   The .dc.html runs on the design runtime; this is the faithful React port wired to the LIVE bridge.
//
// Aesthetic — a FORGE: cold controller input is heated and STRUCK into an authenticated seal.
//   Forge-temperature honesty grammar: steel (unproven) → ember (proving) → struck gold (proven,
//   EARNED) → oxblood (revoked) → ash (dormant). The resting state is steel; gold exists ONLY where
//   the protocol struck it.
//
// HONESTY PORT NOTES (where this diverges from the design artifact, on purpose):
//   - State is the LIVE bridge ONLY. The artifact's PREVIEW state-override dock (which can render
//     gold by forcing visual_state) is REMOVED from production per operator decision 2026-06-25; the
//     dock keeps presentation-only controls (seal glow + scanlines). The full PREVIEW override stays
//     in the design artifact for demos. → gold is unreachable by any UI control.
//   - The seal seeds from the REAL device_id = keccak256(pubkey) (session-status); no controller →
//     cold steel + QORTROLLER-AWAITING-CONTROLLER.
//   - The arena's reserved rectangle holds the LIVE 3D twin iframe (transparent mode) so the Struck
//     Seal aura (z1) glows through it (halo-behind preserved); the artifact's SPECIMEN placeholder is gone.
//   - Consent is read-only here; grant/revoke is wallet-signed in /consent (sovereignty invariant).
//   - "Your Data" tier is "—×" until attested — never a number, never fiat.
//   - The internal Player/Funder/Maker/Archive strip is dropped (the app ViewSelector routes tabs);
//     the shared shell flips to PROVING GROUND during deck propagation.
//   - colorFor() is THE LAW: struck gold only when visual_state==='live' AND that lane is connected.

import React from 'react'
import {
  useBridgeConnectivity, usePlayerSessionStatus, useGrindChain, useConsentStatus, useCaptureHealth,
} from '../api/bridgeApi'
import { isMockActive } from '../api/mockBridge'
import { useViewEyebrow } from '../design/Eyebrow'

// ── forge palette ──
const PAL = {
  void0: '#060910', void1: '#0A1120', void2: '#111B2E',
  steel: '#6E8CA8', ember: '#E0743A', struck: '#F0C667', oxblood: '#B23A4C', ash: '#4A5260',
  bone: '#E9E2D2', boneDim: '#9AA4B2',
}
const DISP = "'Archivo', system-ui, sans-serif"
const BODY = "'Hanken Grotesk', system-ui, sans-serif"
const MONO = "'Martian Mono', ui-monospace, monospace"

// device-derived seed: real keccak256(pubkey) hex → int; awaiting → fnv1a of the awaiting label
function fnv1a(str) { let h = 0x811c9dc5; for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 0x01000193) } return h >>> 0 }
const mid = (h) => (h && h.length > 14 ? h.slice(0, 8) + '…' + h.slice(-6) : (h || '—'))
const mono = (size, color, ls = '0.04em') => ({ fontFamily: MONO, fontSize: size, ...(color ? { color } : {}), letterSpacing: ls })

export function GamerView() {
  // Minimal eyebrow — the cockpit keeps its own passport spine for live state, so the
  // eyebrow just names the surface (num + name; no status/readouts).
  useViewEyebrow({ num: '01', name: 'GAMER · COCKPIT' })
  const conn = useBridgeConnectivity()
  const sess = usePlayerSessionStatus()
  const grindQ = useGrindChain()
  const consentQ = useConsentStatus()
  const healthQ = useCaptureHealth()
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
  const consent = consentQ.data?.categories || consentQ.data?.granted || consentQ.data || {}
  const host = healthQ.data?.host_state || ''
  const pollHz = typeof healthQ.data?.poll_rate_hz === 'number' ? healthQ.data.poll_rate_hz : null

  return (
    <Cockpit
      visualState={visualState} lanes={lanes} humanity={humanity} deviceId={deviceId}
      latestGic={latestGic} grind={grind} consent={consent} mockActive={mockActive}
      host={host} pollHz={pollHz}
    />
  )
}

class Cockpit extends React.Component {
  constructor(props) {
    super(props)
    this.state = { glow: 0.6, grain: false, dockOpen: false, cornerLabels: true, motionStill: false }
    this.sealRef = React.createRef(); this.forceRef = React.createRef()
    this.tremorRef = React.createRef(); this.pulseRef = React.createRef()
    this._strikeStart = -99999; this._wasLive = false
    this.reduced = (typeof window !== 'undefined' && window.matchMedia)
      ? window.matchMedia('(prefers-reduced-motion: reduce)').matches : false
    this._loop = this._loop.bind(this)
  }

  // ── effective state = LIVE bridge only (no override path) ──
  evs() { return this.props.visualState }
  elane(k) { return this.props.lanes[k] || 'unknown' }
  isLive() { return this.evs() === 'live' }
  noController() { const l = this.elane('controller'); return l === 'disconnected' || l === 'unknown' }

  // ── THE LAW: struck gold only when live AND the relevant lane is connected ──
  colorFor(lane) {
    const vs = this.evs()
    if (vs === 'revoked') return PAL.oxblood
    if (vs === 'frozen-disabled') return PAL.ash
    if (vs === 'live') {
      const l = this.elane(lane)
      if (l === 'connected') return PAL.struck
      if (l === 'degraded') return PAL.ember
      if (l === 'disconnected') return PAL.oxblood
      return PAL.ash
    }
    return PAL.steel // dry-run / emulated / unverified
  }
  verdictWord() {
    const vs = this.evs()
    if (vs === 'live') return 'PROVEN'
    if (vs === 'frozen-disabled') return 'FROZEN'
    if (vs === 'revoked') return 'REVOKED'
    return 'UNPROVEN'
  }
  verdictColor() { return this.colorFor('controller') }
  sealColor() { return this.noController() ? PAL.steel : this.colorFor('controller') }
  bannerText() {
    const m = {
      'dry-run': 'DRY-RUN — counted locally, not proven on-chain.',
      'emulated': 'EMULATED INPUT — humanity not proven on this controller.',
      'unverified': 'UNVERIFIED — verifier has not returned OK.',
      'frozen-disabled': 'KILL-SWITCH FROZEN — session counting suspended at operator’s request.',
      'revoked': 'CONSENT REVOKED — session counting suspended.',
    }
    return m[this.evs()] || ''
  }

  // ── seeded geometry (device-derived, not biometric) ──
  seedInt() {
    const id = this.props.deviceId || ''
    if (!id) return fnv1a('QORTROLLER-AWAITING-CONTROLLER')
    const h = id.replace(/[^0-9a-f]/gi, '')
    return (parseInt(h.slice(0, 8) || '9f3c2ba3', 16) >>> 0) || 0x9f3c2ba3
  }
  mulberry(seed) { let a = seed >>> 0; return function () { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296 } }

  // ── color math ──
  rgb(hex) { if (hex[0] !== '#') return [110, 140, 168]; const n = parseInt(hex.slice(1), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255] }
  lerp(a, b, t) { const A = this.rgb(a), B = this.rgb(b); return [Math.round(A[0] + (B[0] - A[0]) * t), Math.round(A[1] + (B[1] - A[1]) * t), Math.round(A[2] + (B[2] - A[2]) * t)] }
  rgba(c, al) { const a = Array.isArray(c) ? c : this.rgb(c); return `rgba(${a[0]},${a[1]},${a[2]},${al})` }

  // the Strike: steel → ember → struck (the one earned moment)
  strikeColor(now) {
    const target = this.sealColor()
    if (this.calm() || !this.isLive() || this.noController()) return this.rgb(target)
    const dt = now - this._strikeStart
    if (dt < 0 || dt > 600) return this.rgb(target)
    if (dt < 280) return this.lerp(PAL.steel, PAL.ember, dt / 280)
    return this.lerp(PAL.ember, target, (dt - 280) / 320)
  }
  bloom(now) {
    if (this.calm() || !this.isLive()) return 0
    const dt = now - this._strikeStart
    if (dt >= 540 && dt < 1140) return 1 - (dt - 540) / 600
    return 0
  }

  fit(canvas) {
    if (!canvas) return null
    const dpr = window.devicePixelRatio || 1, w = canvas.clientWidth, h = canvas.clientHeight
    if (!w || !h) return null
    if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) { canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr) }
    const ctx = canvas.getContext('2d'); ctx.setTransform(dpr, 0, 0, dpr, 0, 0); return { ctx, w, h }
  }

  // the living crest
  drawSeal(ctx, cx, cy, R, rand, col, now, intensity, bloom) {
    const motion = this.isLive() && !this.calm() && !this.noController()
    const breath = motion ? (0.84 + 0.16 * (0.5 + 0.5 * Math.sin(now * 0.0016))) : 1 // tremor-freq breath
    const flick = motion ? (0.85 + 0.15 * Math.abs(Math.sin(now * 0.013))) : 1        // force-curve flicker
    intensity *= breath
    ctx.save(); ctx.translate(cx, cy)
    const halo = ctx.createRadialGradient(0, 0, R * 0.2, 0, 0, R * 1.9)
    halo.addColorStop(0, this.rgba(col, (0.12 + 0.20 * bloom) * intensity))
    halo.addColorStop(0.5, this.rgba(col, (0.05 + 0.08 * bloom) * intensity))
    halo.addColorStop(1, this.rgba(col, 0))
    ctx.beginPath(); ctx.arc(0, 0, R * 1.9, 0, Math.PI * 2); ctx.fillStyle = halo; ctx.fill()
    const spokes = 10 + Math.floor(rand() * 7)
    ctx.rotate(motion ? now * 0.00006 : 0)
    for (let i = 0; i < 3; i++) { const rr = R * (0.5 + i * 0.2); ctx.beginPath(); ctx.arc(0, 0, rr, 0, Math.PI * 2); ctx.strokeStyle = this.rgba(col, (0.10 + 0.05 * i) * intensity); ctx.lineWidth = 1; ctx.stroke() }
    for (let i = 0; i < spokes; i++) {
      const ang = (i / spokes) * Math.PI * 2, len = R * (0.42 + rand() * 0.5)
      const x = Math.cos(ang) * len, y = Math.sin(ang) * len
      ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(x, y); ctx.strokeStyle = this.rgba(col, 0.22 * intensity * flick); ctx.lineWidth = 1; ctx.stroke()
      const p = 0.5 + 0.5 * Math.sin(now * 0.002 + i)
      ctx.beginPath(); ctx.arc(x, y, 1.6 + p * 1.5, 0, Math.PI * 2); ctx.fillStyle = this.rgba(col, (0.5 + 0.4 * bloom) * intensity); ctx.fill()
    }
    ctx.beginPath()
    for (let i = 0; i <= spokes; i++) { const ang = (i / spokes) * Math.PI * 2, rr = R * (0.2 + 0.08 * Math.sin(ang * 3 + (motion ? now * 0.0011 : 0))); const x = Math.cos(ang) * rr, y = Math.sin(ang) * rr; i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y) }
    ctx.closePath(); ctx.strokeStyle = this.rgba(col, 0.6 * intensity); ctx.lineWidth = 1.5; ctx.stroke()
    const g = ctx.createRadialGradient(0, 0, 0, 0, 0, R * 0.34)
    g.addColorStop(0, this.rgba(col, (0.5 + 0.5 * bloom) * intensity)); g.addColorStop(1, this.rgba(col, 0))
    ctx.beginPath(); ctx.arc(0, 0, R * 0.34, 0, Math.PI * 2); ctx.fillStyle = g; ctx.fill()
    ctx.restore()
  }
  drawForce(now) {
    const f = this.fit(this.forceRef.current); if (!f) return; const { ctx, w, h } = f; ctx.clearRect(0, 0, w, h)
    const active = this.isLive() && this.elane('controller') === 'connected'
    const col = active ? this.sealColor() : PAL.steel
    ctx.strokeStyle = '#16203099'; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(0, h - 5); ctx.lineTo(w, h - 5); ctx.stroke()
    ctx.beginPath()
    for (let x = 0; x <= w; x += 2) {
      const p = x / w; let y
      if (active && !this.calm()) { const env = Math.exp(-Math.pow((p - 0.42) * 3.1, 2)); y = (h - 5) - env * (h - 11) * (0.72 + 0.28 * Math.sin(now * 0.004)) }
      else if (active) { const env = Math.exp(-Math.pow((p - 0.42) * 3.1, 2)); y = (h - 5) - env * (h - 11) * 0.9 }
      else { y = h - 5 - 1.4 * Math.sin(p * 8) }
      x === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)
    }
    ctx.strokeStyle = this.rgba(col, active ? 0.9 : 0.4); ctx.lineWidth = 1.5; ctx.stroke()
  }
  drawTremor(now) {
    const f = this.fit(this.tremorRef.current); if (!f) return; const { ctx, w, h } = f; ctx.clearRect(0, 0, w, h)
    const active = this.isLive() && this.elane('controller') === 'connected'
    const col = active ? this.sealColor() : PAL.steel
    const bars = 22, bw = w / bars
    for (let i = 0; i < bars; i++) {
      const base = Math.exp(-Math.pow((i / bars - 0.5) * 3, 2))
      const amp = (active && !this.calm()) ? (base * (0.4 + 0.6 * Math.abs(Math.sin(now * 0.003 + i * 0.7)))) : (active ? base * 0.85 : base * 0.12)
      const bh = Math.max(1, amp * (h - 5))
      ctx.fillStyle = this.rgba(col, active ? 0.8 : 0.32); ctx.fillRect(i * bw + 1, h - bh, bw - 2, bh)
    }
  }
  movePulse(now) {
    const el = this.pulseRef.current; if (!el) return
    if (this.calm() || !this.isLive()) { el.style.opacity = '0'; return }
    const dt = now - this._strikeStart
    if (dt < 0 || dt > 1200) { el.style.opacity = '0'; return }
    const prog = dt / 1200
    el.style.left = (prog * 100) + '%'
    el.style.opacity = String(0.85 * Math.sin(prog * Math.PI))
  }

  glowI() { return 0.55 + (this.state.glow != null ? this.state.glow : 0.6) * 0.85 }
  // motionMode tweak — "still" freezes breath/flicker/strike/pulse for streams + screenshots
  calm() { return this.reduced || this.state.motionStill }
  strike() { this._strikeStart = (typeof performance !== 'undefined') ? performance.now() : 0 }

  _loop(t) {
    const f = this.fit(this.sealRef.current)
    if (f) {
      const { ctx, w, h } = f; ctx.clearRect(0, 0, w, h)
      const cx = w / 2, cy = h * 0.44, R = Math.min(w * 0.5, h * 0.62) * 0.46
      this.drawSeal(ctx, cx, cy, R, this.mulberry(this.seedInt()), this.strikeColor(t), t, this.glowI(), this.bloom(t))
    }
    this.drawForce(t); this.drawTremor(t); this.movePulse(t)
    this._raf = requestAnimationFrame(this._loop)
  }
  componentDidMount() {
    if (this.isLive() && !this.noController()) this.strike()
    this._wasLive = this.isLive() && !this.noController()
    this._raf = requestAnimationFrame(this._loop)
  }
  // Instance-tracked previous live-state (arg-independent) — re-strike on any transition into proven.
  componentDidUpdate() {
    const nowLive = this.isLive() && !this.noController()
    if (nowLive && !this._wasLive) this.strike()
    this._wasLive = nowLive
  }
  componentWillUnmount() { if (this._raf) cancelAnimationFrame(this._raf) }

  render() {
    const { humanity, deviceId, latestGic, grind, consent, mockActive, host, pollHz } = this.props
    const s = this.state
    const vs = this.evs(), live = this.isLive()
    const vColor = this.verdictColor(), vWord = this.verdictWord()
    const chainColor = this.colorFor('chain')
    const noCtrl = this.noController()

    const humanityValue = humanity != null ? humanity.toFixed(2) : '—'
    const humanityPct = humanity != null ? Math.round(humanity * 100) + '%' : '0%'

    const onChainConn = live && this.elane('chain') === 'connected'
    const onchainColor = onChainConn ? PAL.struck : (vs === 'revoked' ? PAL.oxblood : PAL.steel)
    const onchainLabel = onChainConn ? 'ON-CHAIN' : 'PENDING'
    const realityColor = live ? vColor : this.sealColor()

    const frameColor = this.sealColor()
    const twinConn = noCtrl ? 'WS · OFFLINE' : (live ? 'WS · LIVE' : 'WS · IDLE')

    const showBanner = !live, bannerColor = this.sealColor(), bannerText = this.bannerText()

    // seed identity
    const seedLine = noCtrl ? 'QORTROLLER-AWAITING-CONTROLLER' : (deviceId || '—')
    const seedSub = noCtrl ? 'awaiting controller — seal cold' : 'mulberry32 · device-derived, not biometric'
    const seedColor = noCtrl ? PAL.steel : (live && this.elane('controller') === 'connected' ? PAL.struck : this.sealColor())

    // grind
    const cl = grind.chain_length, ct = grind.grind_target || 100, grindLevel = Math.floor(cl / 10)
    const chainVerdict = live ? (grind.chain_intact === false ? 'BROKEN' : 'INTACT') : (vs === 'revoked' || vs === 'frozen-disabled' ? 'SUSPENDED' : 'UNVERIFIED')
    const forgeCells = Array.from({ length: ct }, (_, i) => {
      const on = i < cl, struckGold = on && chainColor === PAL.struck
      return { bg: on ? chainColor : PAL.void2, glow: (struckGold && i >= cl - 3) ? ('0 0 8px ' + this.rgba(chainColor, 0.6)) : 'none' }
    })

    // consent (read-only) — accept both the friendly key and the FROZEN bitmask alias
    const consGet = (k, alt) => !!(consent?.[k] ?? consent?.[alt])
    const consTournament = consGet('tournament', 'TOURNAMENT_GATE')

    // tournament — eligible = live && chain conn && operational conn && tournament consent
    const eligible = live && this.elane('chain') === 'connected' && this.elane('operational') === 'connected' && consTournament
    const tournColor = eligible ? PAL.struck : (live ? this.colorFor('operational') : (vs === 'revoked' ? PAL.oxblood : PAL.steel))
    const tournVerdict = eligible ? 'ELIGIBLE' : (live ? 'NOT YET ELIGIBLE' : 'INELIGIBLE')
    let tournReason
    if (eligible) tournReason = 'live · chain + operational connected · tournament consent granted.'
    else if (live) {
      const miss = []
      if (this.elane('chain') !== 'connected') miss.push('chain lane ' + this.elane('chain'))
      if (this.elane('operational') !== 'connected') miss.push('operational lane ' + this.elane('operational'))
      if (!consTournament) miss.push('tournament consent withheld')
      tournReason = miss.length ? ('blocked by ' + miss.join(' · ') + '.') : 'gates pending.'
    } else tournReason = 'humanity not proven on this controller — pre-flight gate held.'

    // your data — "—×" until attested; never a number, never fiat
    const attested = live && this.elane('chain') === 'connected'
    const attestColor = attested ? PAL.struck : PAL.ash
    const attestLabel = attested ? 'ATTESTED' : 'PENDING'
    const tierNote = attested
      ? 'attested by bridge · marketplace dormant on testnet · value not minted — never fiat.'
      : 'awaiting attestation · marketplace dormant on testnet · never a number, never fiat.'

    // consent chips
    const cmap = [['TOURNAMENT', 'tournament', 'TOURNAMENT_GATE'], ['RESEARCH', 'research', 'ANONYMIZED_RESEARCH'], ['MARKETPLACE', 'marketplace', 'MARKETPLACE'], ['MFR · CERT', 'manufacturer_cert', 'MANUFACTURER_CERT']]
    const consentList = cmap.map(([lab, k, alt]) => { const g = consGet(k, alt); return { label: lab, status: g ? 'GRANTED' : 'WITHHELD', color: g ? PAL.bone : PAL.ash } })

    // footer telemetry — honest: host/poll real, success/sustained not exposed by bridge → "—"
    const hostLabel = host || '—'
    const pollLabel = pollHz != null ? Math.round(pollHz) + ' HZ' : '—'
    const merkleTail = mid(latestGic), gicTail = mid(latestGic)

    return (
      <div className="qt-cockpit-root" style={{ position: 'relative', height: '100%', display: 'flex', flexDirection: 'column', background: PAL.void0, color: PAL.bone, fontFamily: BODY, overflow: 'hidden' }}>
        <style>{`
          @keyframes pg-breath{0%,100%{opacity:.86}50%{opacity:1}}
          @media (prefers-reduced-motion: reduce){ .pg-anim{animation:none!important} }
          @media (max-width:920px){
            .qt-cockpit-root{ height:auto!important; min-height:100%; overflow-y:auto!important; }
            .qt-main-row{ flex-direction:column!important; }
            .qt-arena{ min-height:380px; }
            .qt-hud-col{ flex:0 0 auto!important; border-left:0!important; border-top:1px solid ${PAL.void2}!important; }
          }
        `}</style>

        {/* ░ PASSPORT SPINE ░ */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 20, minHeight: 60, padding: '0 24px', borderBottom: `1px solid ${PAL.void2}`, background: 'linear-gradient(to bottom,#0a1322,#0a1120)', flexShrink: 0, flexWrap: 'wrap' }}>
          <span style={{ ...mono(11, PAL.boneDim, '0.14em'), textTransform: 'uppercase' }}>HUMANITY</span>
          <div style={{ position: 'relative', width: 150, height: 7, border: `1px solid ${PAL.void2}`, borderRadius: 2, overflow: 'hidden', background: '#0a0f18' }}>
            <div style={{ position: 'absolute', inset: '0 auto 0 0', width: humanityPct, background: vColor, boxShadow: `0 0 12px ${vColor}`, transition: 'width .3s cubic-bezier(.2,.6,.2,1), background .3s linear' }} />
          </div>
          <span style={{ fontFamily: DISP, fontStretch: '125%', fontWeight: 800, fontSize: 22, letterSpacing: '0.01em', color: vColor }}>{humanityValue}</span>
          <span style={{ fontFamily: DISP, fontStretch: '125%', fontWeight: 900, fontSize: 18, letterSpacing: '0.02em', color: vColor }}>{vWord}</span>
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 22, flexWrap: 'wrap' }}>
            <span style={{ ...mono(11.5, onchainColor, '0.06em'), display: 'inline-flex', alignItems: 'center', gap: 7 }}><span style={{ width: 7, height: 7, borderRadius: 1, transform: 'rotate(45deg)', background: onchainColor, boxShadow: `0 0 8px ${onchainColor}` }} />{onchainLabel}</span>
            <span style={mono(11.5, PAL.boneDim, '0.02em')}>merkle&nbsp;{merkleTail}</span>
            <span className="pg-anim" title="reality heartbeat" style={{ width: 9, height: 9, borderRadius: '50%', background: realityColor, boxShadow: `0 0 10px ${realityColor}`, animation: 'pg-breath 2800ms ease-in-out infinite' }} />
          </div>
        </div>

        {/* ░ MAIN ROW ░ */}
        <div className="qt-main-row" style={{ flex: '1 1 auto', display: 'flex', minHeight: 0 }}>

          {/* ── ARENA ── */}
          <main className="qt-arena" style={{ position: 'relative', flex: '1 1 auto', minWidth: 0, overflow: 'hidden', background: 'radial-gradient(135% 105% at 50% 36%,#0c1424 0%,#070c16 56%,#050810 100%)' }}>
            {/* depth horizon */}
            <div style={{ position: 'absolute', left: 0, right: 0, top: '62%', height: 1, background: 'linear-gradient(to right,transparent,rgba(110,140,168,.22),transparent)' }} />
            <div style={{ position: 'absolute', left: 0, right: 0, top: '62%', height: 120, background: 'linear-gradient(to bottom,rgba(110,140,168,.05),transparent)' }} />

            {/* z1 · living Struck Seal (halo behind the twin) */}
            <canvas ref={this.sealRef} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', zIndex: 1, pointerEvents: 'none' }} />

            {/* z2 · LIVE 3D twin (transparent) — seal aura glows through the empty space */}
            <div style={{ position: 'absolute', zIndex: 2, left: '50%', top: '44%', transform: 'translate(-50%,-50%)', width: 'min(52%,500px)', aspectRatio: '400 / 240', borderRadius: 4, background: 'rgba(17,27,46,.20)', border: '1px solid rgba(110,140,168,.26)' }}>
              <iframe
                title="Your controller — live 3D twin"
                src={`/controller-twin.html?minimal=1&transparent=1${deviceId ? `&device=${encodeURIComponent(deviceId)}` : ''}`}
                style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', border: 'none', background: 'transparent' }}
              />
              {/* corner brackets (decorative — never block the twin) */}
              <span style={{ position: 'absolute', top: -8, left: -8, width: 16, height: 16, border: `1.5px solid ${frameColor}`, borderRight: 0, borderBottom: 0, pointerEvents: 'none' }} />
              <span style={{ position: 'absolute', top: -8, right: -8, width: 16, height: 16, border: `1.5px solid ${frameColor}`, borderLeft: 0, borderBottom: 0, pointerEvents: 'none' }} />
              <span style={{ position: 'absolute', bottom: -8, left: -8, width: 16, height: 16, border: `1.5px solid ${frameColor}`, borderRight: 0, borderTop: 0, pointerEvents: 'none' }} />
              <span style={{ position: 'absolute', bottom: -8, right: -8, width: 16, height: 16, border: `1.5px solid ${frameColor}`, borderLeft: 0, borderTop: 0, pointerEvents: 'none' }} />
              {/* labels relocated to the four OUTER corners — center stays clear for the live twin + seal */}
              {s.cornerLabels && (
                <>
                  <div style={{ position: 'absolute', top: -22, left: 2, ...mono(10, PAL.ash, '0.12em'), textTransform: 'uppercase', pointerEvents: 'none' }}>RESERVED RECTANGLE</div>
                  <div style={{ position: 'absolute', top: -22, right: 2, ...mono(10, frameColor, '0.1em'), textTransform: 'uppercase', pointerEvents: 'none' }}>{twinConn}</div>
                  <div style={{ position: 'absolute', bottom: -22, left: 2, ...mono(10, 'rgba(154,164,178,.7)', '0.12em'), textTransform: 'uppercase', pointerEvents: 'none' }}>3D CONTROLLER TWIN · LIVE</div>
                  <div style={{ position: 'absolute', bottom: -22, right: 2, ...mono(10, PAL.ash, '0.1em'), textTransform: 'uppercase', pointerEvents: 'none' }}>HALO-BEHIND · LIVE IFRAME</div>
                </>
              )}
            </div>

            {/* honesty banner when not live */}
            {showBanner && (
              <div style={{ position: 'absolute', zIndex: 4, top: 18, left: '50%', transform: 'translateX(-50%)', maxWidth: '84%', display: 'flex', alignItems: 'center', gap: 10, padding: '8px 14px', background: 'rgba(8,12,20,.92)', border: `1px solid ${bannerColor}`, borderRadius: 4 }}>
                <span style={{ width: 7, height: 7, borderRadius: '50%', background: bannerColor, boxShadow: `0 0 8px ${bannerColor}`, flex: '0 0 auto' }} />
                <span style={{ ...mono(11.5, bannerColor, '0.02em'), lineHeight: 1.45 }}>{bannerText}</span>
              </div>
            )}

            {/* hero caption */}
            <div style={{ position: 'absolute', zIndex: 3, left: '50%', bottom: 148, transform: 'translateX(-50%)', textAlign: 'center', pointerEvents: 'none' }}>
              <div style={{ ...mono(11, PAL.boneDim, '0.16em'), textTransform: 'uppercase' }}>THE STRUCK SEAL · <span style={{ color: vColor }}>{vWord}</span></div>
              <div style={{ marginTop: 6, fontFamily: DISP, fontStretch: '125%', fontWeight: 700, fontSize: 15, letterSpacing: '0.04em', color: PAL.boneDim }}>Cold input. Struck proof.</div>
            </div>

            {/* bottom-left: trigger force + tremor */}
            <div style={{ position: 'absolute', zIndex: 3, left: 18, bottom: 54, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <div style={{ background: 'rgba(8,12,20,.66)', border: `1px solid ${PAL.void2}`, borderRadius: 4, padding: '7px 9px' }}>
                <div style={{ ...mono(10, PAL.ash, '0.12em'), textTransform: 'uppercase', marginBottom: 5 }}>TRIGGER · FORCE</div>
                <canvas ref={this.forceRef} style={{ display: 'block', width: 144, height: 42 }} />
              </div>
              <div style={{ background: 'rgba(8,12,20,.66)', border: `1px solid ${PAL.void2}`, borderRadius: 4, padding: '7px 9px' }}>
                <div style={{ ...mono(10, PAL.ash, '0.12em'), textTransform: 'uppercase', marginBottom: 5 }}>TREMOR · 1&nbsp;kHz SPECTRUM</div>
                <canvas ref={this.tremorRef} style={{ display: 'block', width: 144, height: 42 }} />
              </div>
            </div>

            {/* bottom-right: seed identity */}
            <div style={{ position: 'absolute', zIndex: 3, right: 18, bottom: 54, maxWidth: 320, background: 'rgba(8,12,20,.66)', border: `1px solid ${PAL.void2}`, borderRadius: 4, padding: '9px 12px', textAlign: 'right' }}>
              <div style={{ ...mono(10, PAL.ash, '0.1em'), textTransform: 'uppercase' }}>seed · device_id = keccak256(pubkey)</div>
              <div style={{ ...mono(13, seedColor, '0.02em'), fontWeight: 500, marginTop: 3, wordBreak: 'break-all' }}>{seedLine}</div>
              <div style={{ ...mono(10, PAL.ash, '0.02em'), marginTop: 3 }}>{seedSub}</div>
            </div>

            {/* vignette */}
            <div style={{ position: 'absolute', inset: 0, zIndex: 3, pointerEvents: 'none', background: 'radial-gradient(125% 100% at 50% 44%,transparent 52%,rgba(3,5,9,.66) 100%)' }} />
            {/* optional scanlines (presentation only) */}
            {s.grain && <div style={{ position: 'absolute', inset: 0, zIndex: 5, pointerEvents: 'none', background: 'repeating-linear-gradient(to bottom,transparent 0,transparent 2px,rgba(0,0,0,.30) 3px,transparent 4px)', opacity: .5 }} />}
          </main>

          {/* ── HUD COLUMN ── */}
          <aside className="qt-hud-col" style={{ flex: '0 0 300px', borderLeft: `1px solid ${PAL.void2}`, background: PAL.void1, padding: 18, display: 'flex', flexDirection: 'column', gap: 14, overflowY: 'auto' }}>

            {/* GRIND */}
            <div style={{ background: '#0c1322', border: `1px solid ${PAL.void2}`, borderRadius: 4, padding: '15px 16px' }}>
              <div style={{ ...mono(11, PAL.boneDim, '0.14em'), textTransform: 'uppercase', marginBottom: 11 }}>GRIND · INTEGRITY CHAIN</div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 9 }}>
                <span style={{ fontFamily: DISP, fontStretch: '125%', fontWeight: 900, fontSize: 34, lineHeight: .9, color: chainColor }}>{cl}</span>
                <span style={mono(13, PAL.ash)}>/ {ct} · lv.{grindLevel}</span>
              </div>
              <div style={{ marginTop: 11, display: 'flex', alignItems: 'center', justifyContent: 'space-between', ...mono(11, PAL.boneDim, '0.04em') }}>
                <span>success —</span>
                <span style={{ color: chainColor, fontWeight: 500 }}>{chainVerdict}</span>
              </div>
            </div>

            {/* TOURNAMENT */}
            <div style={{ background: '#0c1322', border: `1px solid ${PAL.void2}`, borderRadius: 4, padding: '15px 16px' }}>
              <div style={{ ...mono(11, PAL.boneDim, '0.14em'), textTransform: 'uppercase', marginBottom: 11 }}>TOURNAMENT · PRE-FLIGHT</div>
              <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                <span style={{ width: 7, height: 7, borderRadius: '50%', background: tournColor, boxShadow: `0 0 8px ${tournColor}` }} />
                <span style={{ ...mono(14, tournColor, '0.03em'), fontWeight: 500 }}>{tournVerdict}</span>
              </div>
              <div style={{ marginTop: 8, fontFamily: BODY, fontSize: 12.5, lineHeight: 1.5, color: PAL.boneDim }}>{tournReason}</div>
            </div>

            {/* YOUR DATA */}
            <div style={{ background: '#0c1322', border: `1px solid ${PAL.void2}`, borderRadius: 4, padding: '15px 16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 11 }}>
                <span style={{ ...mono(11, PAL.boneDim, '0.14em'), textTransform: 'uppercase' }}>YOUR DATA</span>
                <span style={{ ...mono(10, attestColor, '0.06em'), textTransform: 'uppercase', border: `1px solid ${attestColor}`, borderRadius: 2, padding: '2px 6px' }}>{attestLabel}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 9 }}>
                <span style={{ fontFamily: DISP, fontStretch: '125%', fontWeight: 900, fontSize: 34, lineHeight: .9, color: PAL.bone }}>—×</span>
                <span style={mono(12, PAL.ash)}>tier multiplier</span>
              </div>
              <div style={{ marginTop: 9, fontFamily: BODY, fontSize: 12, lineHeight: 1.5, color: PAL.ash }}>{tierNote}</div>
            </div>

            <a href="/?view=forensic" style={{ marginTop: 'auto', ...mono(12, PAL.bone, '0.06em'), textTransform: 'uppercase', textDecoration: 'none', border: `1px solid ${PAL.void2}`, borderRadius: 4, padding: 11, textAlign: 'center' }}>Re-derive the proofs &rarr;</a>
            <div style={{ ...mono(10, PAL.ash, '0.04em'), textAlign: 'center' }}>host {hostLabel} · {pollLabel} · sustained —</div>
          </aside>
        </div>

        {/* ░ GRIND FORGE-LINE ░ */}
        <div style={{ position: 'relative', flexShrink: 0, padding: '13px 24px 15px', borderTop: `1px solid ${PAL.void2}`, background: PAL.void1 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 7, gap: 12, flexWrap: 'wrap' }}>
            <span style={{ ...mono(11, PAL.boneDim, '0.14em'), textTransform: 'uppercase' }}>GRIND FORGE-LINE · STRUCK LINKS</span>
            <span style={mono(11.5, PAL.boneDim, '0.02em')}>{cl} / {ct} · gic {gicTail} · <span style={{ color: chainColor }}>{chainVerdict}</span></span>
          </div>
          <div style={{ position: 'relative' }}>
            <div style={{ display: 'flex', gap: 2, alignItems: 'flex-end' }}>
              {forgeCells.map((c, i) => <span key={i} style={{ flex: 1, height: 14, borderRadius: 1, background: c.bg, boxShadow: c.glow }} />)}
            </div>
            <div ref={this.pulseRef} style={{ position: 'absolute', top: -2, bottom: -2, width: 36, left: 0, pointerEvents: 'none', opacity: 0, background: `linear-gradient(to right,transparent,${this.rgba(chainColor, 0.85)})`, mixBlendMode: 'screen' }} />
          </div>
        </div>

        {/* ░ SOVEREIGNTY STRIP — read-only; granting is wallet-signed in /consent ░ */}
        <footer style={{ flexShrink: 0, display: 'flex', alignItems: 'center', gap: 16, padding: '12px 24px', borderTop: `1px solid ${PAL.void2}`, background: PAL.void1, flexWrap: 'wrap' }}>
          <span style={{ ...mono(11, PAL.boneDim, '0.14em'), textTransform: 'uppercase' }}>SOVEREIGNTY · CONSENT</span>
          <span style={{ ...mono(10, PAL.ash, '0.06em'), textTransform: 'uppercase', border: `1px solid ${PAL.void2}`, borderRadius: 2, padding: '2px 7px' }}>READ-ONLY</span>
          <div style={{ display: 'flex', gap: 9, flexWrap: 'wrap' }}>
            {consentList.map((c) => (
              <a key={c.label} href="/consent" style={{ display: 'inline-flex', alignItems: 'center', gap: 7, padding: '4px 10px', border: `1px solid ${PAL.void2}`, borderRadius: 2, ...mono(11, PAL.boneDim, '0.03em'), textDecoration: 'none' }}>
                {c.label}&nbsp;<span style={{ color: c.color, fontWeight: 500 }}>{c.status}</span>
              </a>
            ))}
          </div>
          <a href="/consent" style={{ marginLeft: 'auto', ...mono(11, PAL.boneDim, '0.06em'), textTransform: 'uppercase', textDecoration: 'none' }}>you grant · you revoke &rarr;</a>
        </footer>

        {/* ░ BRIDGE-OFFLINE TAG — only when mock is active ░ */}
        {mockActive && (
          <div style={{ position: 'fixed', left: 16, bottom: 16, zIndex: 40, display: 'inline-flex', alignItems: 'center', gap: 8, padding: '5px 10px', background: 'rgba(8,12,20,.94)', border: `1px solid ${PAL.oxblood}`, borderRadius: 4, ...mono(10.5, '#d9849a', '0.06em'), textTransform: 'uppercase' }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: PAL.oxblood, boxShadow: `0 0 8px ${PAL.oxblood}` }} />BRIDGE OFFLINE — placeholder, no live proof
          </div>
        )}

        {/* ░ DISPLAY DOCK — presentation only (NO state override; the bridge is the only truth source) ░ */}
        {s.dockOpen ? (
          <div style={{ position: 'fixed', right: 16, bottom: 16, zIndex: 50, width: 264, background: PAL.void1, border: '1px solid #1c2942', borderRadius: 4, boxShadow: '0 12px 32px -14px #000d' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '11px 13px', borderBottom: `1px solid ${PAL.void2}` }}>
              <span style={{ ...mono(11, PAL.ember, '0.12em'), textTransform: 'uppercase' }}>◇ DISPLAY</span>
              <button onClick={() => this.setState({ dockOpen: false })} style={{ ...mono(14, PAL.boneDim), background: 'transparent', border: 0, cursor: 'pointer', lineHeight: 1 }}>×</button>
            </div>
            <div style={{ padding: 13, display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
                <span style={{ ...mono(10, PAL.ash, '0.06em'), textTransform: 'uppercase', width: 60 }}>seal glow</span>
                <input type="range" min="0" max="1" step="0.05" value={s.glow} onChange={(e) => this.setState({ glow: parseFloat(e.target.value) })} style={{ flex: 1, accentColor: PAL.ember, cursor: 'pointer' }} />
              </div>
              {[
                ['SCANLINES', s.grain, () => this.setState((p) => ({ grain: !p.grain })), s.grain ? 'ON' : 'OFF'],
                ['CORNER LABELS', !s.cornerLabels, () => this.setState((p) => ({ cornerLabels: !p.cornerLabels })), s.cornerLabels ? 'ON' : 'OFF'],
                ['MOTION', s.motionStill, () => this.setState((p) => ({ motionStill: !p.motionStill })), s.motionStill ? 'STILL' : 'ALIVE'],
              ].map(([lbl, engaged, onClick, val]) => (
                <button key={lbl} onClick={onClick} style={{ width: '100%', ...mono(10.5, engaged ? PAL.void0 : PAL.boneDim, '0.04em'), textTransform: 'uppercase', background: engaged ? PAL.ember : '#0c1322', border: `1px solid ${engaged ? PAL.ember : PAL.void2}`, borderRadius: 2, padding: 6, cursor: 'pointer', textAlign: 'left' }}>{lbl} · {val}</button>
              ))}
              <div style={{ ...mono(10, PAL.ash, '0.02em'), lineHeight: 1.55, paddingTop: 2, borderTop: `1px solid ${PAL.void2}` }}>Display only — glow, scanlines, labels and motion are presentation. They never change what the bridge reported. Gold renders only when the bridge reports live + chain connected.</div>
            </div>
          </div>
        ) : (
          <button onClick={() => this.setState({ dockOpen: true })} style={{ position: 'fixed', right: 16, bottom: 16, zIndex: 50, ...mono(11, PAL.ember, '0.1em'), textTransform: 'uppercase', background: PAL.void1, border: '1px solid #1c2942', borderRadius: 4, padding: '9px 13px', cursor: 'pointer' }}>◇ DISPLAY</button>
        )}
      </div>
    )
  }
}
