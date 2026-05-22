/* QorTroller — Tweaks (gamer-aesthetic) layer.
 *
 * Production port of the newer Claude-Design export iteration: "Create stunning
 * animations and aesthetics that align with what gamers would enjoy looking at
 * when opening their qortroller dashboard" (design chat 2026-05-20).
 *
 * The export's tweaks-panel.jsx was coupled to the Claude-Design host harness
 * (postMessage __activate_edit_mode / __edit_mode_set_keys, on-disk EDITMODE
 * block rewrites). That host does not exist in production, so this module keeps
 * EVERY control + behavior the user iterated on but adapts the plumbing:
 *   - state persists to localStorage (qt.tweaks.v1) instead of host rewrites
 *   - a visible brand-dark toggle opens the panel (no host toolbar)
 *   - the panel chrome is void-black instrument styling (kit.css) rather than
 *     the host's generic light-glass shell — matching the visual output of the
 *     dashboard the gamer actually sees.
 *
 * Default state is forensic-restraint (brand-locked). Honesty discipline is
 * preserved at every setting: status labels stay paired with text, green is
 * still earned (real SHA-256 lives in ForensicView — nothing here fakes a
 * verdict), and the active vibe is announced in the foot label.
 *
 * The provider pushes CSS custom properties onto :root (cleared on unmount)
 * that qortroller-kit.css's GAMER-VIBE OVERLAYS section reacts to:
 *   --qt-glow · --qt-breath · --qt-scanline-alpha · --qt-accent
 */
import {
  createContext, useCallback, useContext, useEffect,
  useRef, useState,
} from 'react'

// ── Defaults (forensic-restraint) ────────────────────────────────────────────
export const TWEAK_DEFAULTS = {
  vibe:              'forensic',
  accent:            '#00d4ff',
  scanlines:         false,
  scanlineIntensity: 24,
  crt:               false,
  noiseGrain:        false,
  glow:              35,
  twinBreathSeconds: 2.8,
  landingFx:         'pulse',
  showVibeLabel:     true,
  // GIC chain display on the Gamer screen: 'orbs' = the orb-web constellation
  // floating around the controller; 'ribbon' = the classic bottom chain ribbon.
  gicView:           'orbs',
}

// ── Vibe presets — selecting a vibe sweeps the dependent knobs (the user can
// flip across vibes without touching every control). Subsequent individual
// edits still win; the preset only fires on vibe change. ──────────────────────
export const VIBE_PRESETS = {
  forensic: {
    scanlines: false, scanlineIntensity: 24, crt: false, noiseGrain: false,
    glow: 35, twinBreathSeconds: 2.8, landingFx: 'pulse', accent: '#00d4ff',
  },
  cinematic: {
    scanlines: false, scanlineIntensity: 18, crt: false, noiseGrain: true,
    glow: 65, twinBreathSeconds: 2.2, landingFx: 'bloom', accent: '#00d4ff',
  },
  arcade: {
    scanlines: true, scanlineIntensity: 36, crt: true, noiseGrain: true,
    glow: 100, twinBreathSeconds: 1.6, landingFx: 'shockwave', accent: '#ff4dcc',
  },
}

const ACCENT_OPTIONS = [
  '#00d4ff', // gamer-cyan (default)
  '#5bd6a3', // chain-green
  '#ff4dcc', // neon-pink
  '#a78bfa', // ultraviolet
]

const STORAGE_KEY = 'qt.tweaks.v1'

const QtTweaksContext = createContext(TWEAK_DEFAULTS)

/* Read current tweak values anywhere under a QtTweaksProvider. Falls back to
   the forensic defaults if no provider is mounted, so consumers are safe to
   call unconditionally (rules-of-hooks clean). */
export function useQtTweaks() {
  return useContext(QtTweaksContext)
}

function loadTweaks() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return TWEAK_DEFAULTS
    return { ...TWEAK_DEFAULTS, ...JSON.parse(raw) }
  } catch {
    return TWEAK_DEFAULTS
  }
}


// ── Provider ──────────────────────────────────────────────────────────────────
export function QtTweaksProvider({ children }) {
  const [t, setValues] = useState(loadTweaks)
  const [open, setOpen] = useState(false)
  const lastVibeRef = useRef(t.vibe)

  const setTweak = useCallback((keyOrEdits, val) => {
    const edits = (typeof keyOrEdits === 'object' && keyOrEdits !== null)
      ? keyOrEdits
      : { [keyOrEdits]: val }
    setValues((prev) => {
      const next = { ...prev, ...edits }
      try { localStorage.setItem(STORAGE_KEY, JSON.stringify(next)) } catch { /* private mode */ }
      return next
    })
  }, [])

  // Vibe change → apply its preset.
  useEffect(() => {
    if (t.vibe === lastVibeRef.current) return
    lastVibeRef.current = t.vibe
    const preset = VIBE_PRESETS[t.vibe]
    if (preset) setTweak({ ...preset })
  }, [t.vibe, setTweak])

  // Push CSS variables to the root so kit.css overlays react. Cleared on
  // unmount (e.g. when the gamer switches tabs) so other views are untouched.
  useEffect(() => {
    const r = document.documentElement.style
    r.setProperty('--qt-accent', t.accent)
    r.setProperty('--qt-glow', String(t.glow / 100))
    r.setProperty('--qt-breath', `${t.twinBreathSeconds}s`)
    r.setProperty('--qt-scanline-alpha', String((t.scanlines ? t.scanlineIntensity : 0) / 100))
    return () => {
      r.removeProperty('--qt-accent')
      r.removeProperty('--qt-glow')
      r.removeProperty('--qt-breath')
      r.removeProperty('--qt-scanline-alpha')
    }
  }, [t.accent, t.glow, t.twinBreathSeconds, t.scanlines, t.scanlineIntensity])

  const offVibe = t.vibe !== 'forensic'

  return (
    <QtTweaksContext.Provider value={t}>
      {children}

      {/* Atmosphere overlays — fixed, pointer-events:none, opt-in */}
      {t.crt        && <div className="qt-crt-overlay"       aria-hidden="true" />}
      {t.scanlines  && <div className="qt-scanlines-overlay" aria-hidden="true" />}
      {t.noiseGrain && <div className="qt-noise-overlay"     aria-hidden="true" />}

      {/* Honesty: announce the active vibe so the operator always knows */}
      {t.showVibeLabel && offVibe && (
        <div className="qt-vibe-foot">VIBE · {t.vibe.toUpperCase()}</div>
      )}

      {/* Visible toggle (replaces the host toolbar) */}
      <button
        type="button"
        className="qt-tweaks-toggle"
        data-vibe={t.vibe}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        title="Tweak the dashboard aesthetic"
      >
        <span className="qt-tweaks-toggle__star" aria-hidden="true">✦</span>
        Tweaks
      </button>

      {open && (
        <TweaksPanel t={t} setTweak={setTweak} onClose={() => setOpen(false)} />
      )}
    </QtTweaksContext.Provider>
  )
}

// ── Control panel ─────────────────────────────────────────────────────────────
function TweaksPanel({ t, setTweak, onClose }) {
  return (
    <div className="qt-tweaks-panel" role="dialog" aria-label="QorTroller tweaks">
      <div className="qt-tweaks-panel__hd">
        <b>Tweaks · QorTroller</b>
        <button className="qt-tweaks-panel__x" aria-label="Close tweaks" onClick={onClose}>✕</button>
      </div>
      <div className="qt-tweaks-panel__body">
        <div className="qt-tweaks-sect">Vibe</div>
        <Seg label="Preset" value={t.vibe}
             options={['forensic', 'cinematic', 'arcade']}
             onChange={(v) => setTweak('vibe', v)} />
        <Chips label="Gamer accent" value={t.accent} options={ACCENT_OPTIONS}
               onChange={(v) => setTweak('accent', v)} />

        <div className="qt-tweaks-sect">Atmosphere</div>
        <Switch label="Scanlines" value={t.scanlines}
                onChange={(v) => setTweak('scanlines', v)} />
        {t.scanlines && (
          <Slider label="Scanline intensity" value={t.scanlineIntensity}
                  min={4} max={60} step={2} unit="%"
                  onChange={(v) => setTweak('scanlineIntensity', v)} />
        )}
        <Switch label="CRT curve" value={t.crt} onChange={(v) => setTweak('crt', v)} />
        <Switch label="Film grain" value={t.noiseGrain} onChange={(v) => setTweak('noiseGrain', v)} />
        <Slider label="Glow" value={t.glow} min={0} max={100} step={5} unit="%"
                onChange={(v) => setTweak('glow', v)} />

        <div className="qt-tweaks-sect">Pace</div>
        <Slider label="Twin breath" value={t.twinBreathSeconds}
                min={0.8} max={6} step={0.2} unit="s"
                onChange={(v) => setTweak('twinBreathSeconds', v)} />

        <div className="qt-tweaks-sect">GIC chain</div>
        <Seg label="Display" value={t.gicView}
             options={['orbs', 'ribbon']}
             onChange={(v) => setTweak('gicView', v)} />

        <div className="qt-tweaks-sect">GIC landing FX</div>
        <Seg label="Style" value={t.landingFx}
             options={['pulse', 'bloom', 'shockwave', 'off']}
             onChange={(v) => setTweak('landingFx', v)} />

        <div className="qt-tweaks-sect">Discipline</div>
        <Switch label="Show vibe label" value={t.showVibeLabel}
                onChange={(v) => setTweak('showVibeLabel', v)} />
      </div>
    </div>
  )
}

// ── Controls ──────────────────────────────────────────────────────────────────
function Slider({ label, value, min = 0, max = 100, step = 1, unit = '', onChange }) {
  return (
    <div className="qt-tweaks-row">
      <div className="qt-tweaks-lbl">
        <span>{label}</span>
        <span className="qt-tweaks-val">{value}{unit}</span>
      </div>
      <input type="range" className="qt-tweaks-slider"
             min={min} max={max} step={step} value={value}
             onChange={(e) => onChange(Number(e.target.value))} />
    </div>
  )
}

function Switch({ label, value, onChange }) {
  return (
    <div className="qt-tweaks-row qt-tweaks-row--h">
      <div className="qt-tweaks-lbl"><span>{label}</span></div>
      <button type="button" className="qt-tweaks-switch" data-on={value ? '1' : '0'}
              role="switch" aria-checked={!!value} aria-label={label}
              onClick={() => onChange(!value)}><i /></button>
    </div>
  )
}

function Seg({ label, value, options, onChange }) {
  return (
    <div className="qt-tweaks-row">
      <div className="qt-tweaks-lbl"><span>{label}</span></div>
      <div className="qt-tweaks-seg" role="radiogroup" aria-label={label}>
        {options.map((o) => (
          <button key={o} type="button" role="radio" aria-checked={o === value}
                  data-on={o === value ? '1' : '0'} onClick={() => onChange(o)}>
            {o}
          </button>
        ))}
      </div>
    </div>
  )
}

function Chips({ label, value, options, onChange }) {
  return (
    <div className="qt-tweaks-row">
      <div className="qt-tweaks-lbl"><span>{label}</span></div>
      <div className="qt-tweaks-chips" role="radiogroup" aria-label={label}>
        {options.map((c) => (
          <button key={c} type="button" role="radio" aria-checked={c === value}
                  className="qt-tweaks-chip" data-on={c === value ? '1' : '0'}
                  style={{ background: c, color: c }}
                  aria-label={c} title={c} onClick={() => onChange(c)} />
        ))}
      </div>
    </div>
  )
}

/* LevelUpBadge — flashes when the real chain length crosses a multiple of 10.
   Driven entirely by the real polled chain_length (never fabricated). */
export function LevelUpBadge({ chainLen }) {
  const [milestone, setMilestone] = useState(null)
  const prevRef = useRef(chainLen)
  useEffect(() => {
    const prev = prevRef.current
    if (typeof chainLen === 'number' && chainLen > prev) {
      const crossed = Math.floor(chainLen / 10) > Math.floor(prev / 10)
      if (crossed && chainLen % 10 === 0) {
        setMilestone(chainLen)
        const id = setTimeout(() => setMilestone(null), 1700)
        prevRef.current = chainLen
        return () => clearTimeout(id)
      }
    }
    if (typeof chainLen === 'number') prevRef.current = chainLen
    return undefined
  }, [chainLen])
  if (milestone == null) return null
  return (
    <div className="qt-levelup" role="status" aria-live="polite">
      GIC MILESTONE
      <span className="qt-levelup__big">{milestone}</span>
    </div>
  )
}
