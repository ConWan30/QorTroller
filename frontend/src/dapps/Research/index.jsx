// WMP Researcher Landing — /research
//
// Build 3 of operator-directed /goal build order (2→1→4→3→5→6).
//
// The door for the WMP buyer class: AI / world-model research labs.
// Different audience than gamers (mainstream PS5 player), grant
// evaluators (IoTeX Halo committee), or forensic cryptographers
// (operator dashboard inhabitants). Researchers live in academic +
// ML-engineering contexts. The Grant Brief deck is wrong audience;
// the operator dashboard is wrong audience; the Consent Cockpit is
// wrong audience.
//
// Aesthetic direction: editorial-scientific. Closer to Distill.pub /
// Stripe docs than to a gaming brand. Side-rail TOC, dense type, real
// runnable verifier in the browser, sample bundle pre-loaded for
// try-it-now. Slightly warmer black (#0a0c10) than operator graticule,
// NO graticule, single-column body with generous measure.
//
// The differentiator: a researcher pastes a bundle JSON in the
// verifier panel and watches each of the 5 checks evaluate live.
// Trust-by-execution. The verifier IS the marketing.
//
// Honesty rails:
//   • Each check's stub status is surfaced honestly. Humanity check
//     v1 is a structural stub; the panel says so. Phase-2 wires
//     snarkjs.
//   • Recency check honestly DEFERS when registry is empty (the
//     "BEACON_REGISTRY_NOT_DEPLOYED" surface — Arc 6 LIVE 2026-06-05
//     but keeper unset means honest deferral is the right answer).
//   • Consent v1 W1-D = CONSENT_GATE_DEFERRED — surfaced honestly.

import { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { verifyBundle, OUTCOME_VERIFIED } from './inBrowserVerifier'
import { SAMPLE_BUNDLE } from './sampleBundle'

// ── tokens (editorial-scientific room) ──
const BG = '#0a0c10'                  // slightly warmer than operator graticule
const BG_SOFT = '#0d1116'
const CHAIN = '#5bd6a3'
const AMBER = '#f0a868'
const RED = '#d65b78'
const TEXT = '#dde3eb'
const TEXT_DIM = '#8a96a5'
const TEXT_FAINT = '#5a6675'
const BORDER = '#1a2230'

const Syne = "'Syne', system-ui, sans-serif"
const Mono = "'JetBrains Mono', monospace"

// section anchors for the side-rail TOC
const SECTIONS = [
  { id: 'placement',  label: 'Honest placement' },
  { id: 'contract',   label: 'What the bundle contains' },
  { id: 'verify',     label: 'Verify in your browser' },
  { id: 'safety',     label: 'Safety rails' },
  { id: 'quickstart', label: 'Quickstart' },
]

export default function ResearchDapp() {
  return (
    <div style={{
      background: BG,
      color: TEXT,
      minHeight: '100vh',
      fontFamily: Syne,
    }}>
      {/* document chrome */}
      <header style={{
        padding: '32px 6vw 18px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'baseline',
        borderBottom: `1px solid ${BORDER}`,
      }}>
        <Link to="/" style={{
          fontFamily: Syne,
          fontSize: 19,
          fontWeight: 700,
          color: TEXT,
          textDecoration: 'none',
          letterSpacing: '-0.02em',
        }}>
          Qor<span style={{ color: AMBER, fontWeight: 800 }}>T</span>roller
        </Link>
        <span style={{
          fontFamily: Mono,
          fontSize: 10,
          color: TEXT_FAINT,
          letterSpacing: '0.22em',
          textTransform: 'uppercase',
        }}>
          Research · WMP · v1
        </span>
      </header>

      {/* main two-column layout: TOC rail + body */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'minmax(0, 1fr)',
        gap: 0,
        maxWidth: 1280,
        margin: '0 auto',
        padding: '0 6vw',
      }}>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 1fr)',
          gap: 0,
        }}>
          {/* hero */}
          <Hero />

          {/* TOC + body grid */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'minmax(0, 220px) minmax(0, 1fr)',
            gap: 60,
            marginTop: 40,
          }} className="research-grid">
            <TocRail />
            <article>
              <PlacementSection />
              <ContractSection />
              <VerifySection />
              <SafetySection />
              <QuickstartSection />
            </article>
          </div>
        </div>
      </div>

      {/* responsive: collapse TOC under 920px */}
      <style>{`
        @media (max-width: 920px) {
          .research-grid {
            grid-template-columns: 1fr !important;
            gap: 32px !important;
          }
          .toc-rail {
            position: static !important;
            border-left: none !important;
            border-bottom: 1px solid ${BORDER};
            padding-left: 0 !important;
            padding-bottom: 22px;
          }
        }
      `}</style>

      <Footer />
    </div>
  )
}

// ──────────────────────────────────────────────────────────────────────
// Hero
// ──────────────────────────────────────────────────────────────────────

function Hero() {
  return (
    <section style={{ padding: '70px 0 50px' }}>
      <div style={{
        fontFamily: Mono,
        fontSize: 11,
        color: AMBER,
        letterSpacing: '0.28em',
        textTransform: 'uppercase',
        marginBottom: 28,
      }}>
        For · world-model · research · labs
      </div>
      <h1 style={{
        fontFamily: Syne,
        fontWeight: 700,
        fontSize: 'clamp(40px, 5.8vw, 78px)',
        lineHeight: 1.02,
        letterSpacing: '-0.03em',
        color: TEXT,
        margin: 0,
        maxWidth: '22ch',
      }}>
        Cryptographically <span style={{ color: CHAIN }}>verifiable</span> human-action demonstrations.
      </h1>
      <p style={{
        fontFamily: Syne,
        fontSize: 20,
        lineHeight: 1.65,
        color: TEXT_DIM,
        margin: '36px 0 0',
        maxWidth: '64ch',
      }}>
        Fei-Fei Li named the bottleneck in her June 2026 taxonomy paper:
        renderers are awash in internet video, but{' '}
        <span style={{ color: TEXT }}>simulators and planners face acute shortages
        of real human action demonstrations</span> — verified at the
        complexity, variability, and duration of real-world deployment.
        Synthetic data can look correct while containing nonsensical
        physics.
      </p>
      <p style={{
        fontFamily: Syne,
        fontSize: 20,
        lineHeight: 1.65,
        color: TEXT_DIM,
        margin: '22px 0 0',
        maxWidth: '64ch',
      }}>
        QorTroller is the candor Li asks for, made cryptographic.{' '}
        <span style={{ color: TEXT }}>Not a world model.</span> A
        provenance source for the demonstration data world models are
        starved for.
      </p>
    </section>
  )
}

// ──────────────────────────────────────────────────────────────────────
// TOC rail
// ──────────────────────────────────────────────────────────────────────

function TocRail() {
  return (
    <nav
      className="toc-rail"
      style={{
        position: 'sticky',
        top: 30,
        alignSelf: 'start',
        paddingLeft: 20,
        borderLeft: `1px solid ${BORDER}`,
        fontFamily: Mono,
      }}
    >
      <div style={{
        fontSize: 9,
        color: TEXT_FAINT,
        letterSpacing: '0.24em',
        textTransform: 'uppercase',
        marginBottom: 14,
      }}>
        Contents
      </div>
      {SECTIONS.map((s, i) => (
        <a
          key={s.id}
          href={`#${s.id}`}
          style={{
            display: 'block',
            padding: '8px 0',
            fontFamily: Syne,
            fontSize: 13,
            color: TEXT_DIM,
            textDecoration: 'none',
            borderTop: i > 0 ? `1px solid ${BORDER}88` : 'none',
          }}
        >
          <span style={{ color: TEXT_FAINT, marginRight: 10, fontFamily: Mono }}>
            {String(i + 1).padStart(2, '0')}
          </span>
          {s.label}
        </a>
      ))}
    </nav>
  )
}

// ──────────────────────────────────────────────────────────────────────
// Section components
// ──────────────────────────────────────────────────────────────────────

function SectionTitle({ num, id, children }) {
  return (
    <h2 id={id} style={{
      fontFamily: Syne,
      fontWeight: 700,
      fontSize: 34,
      letterSpacing: '-0.025em',
      color: TEXT,
      margin: '70px 0 28px',
      paddingTop: 10,
      display: 'flex',
      alignItems: 'baseline',
      gap: 18,
      scrollMarginTop: 40,
    }}>
      <span style={{
        fontFamily: Mono,
        fontSize: 13,
        color: TEXT_FAINT,
        letterSpacing: '0.18em',
      }}>
        {String(num).padStart(2, '0')}
      </span>
      {children}
    </h2>
  )
}

function P({ children }) {
  return (
    <p style={{
      fontFamily: Syne,
      fontSize: 17,
      lineHeight: 1.7,
      color: TEXT_DIM,
      margin: '0 0 18px',
      maxWidth: '64ch',
    }}>
      {children}
    </p>
  )
}

function Code({ children }) {
  return (
    <code style={{
      fontFamily: Mono,
      fontSize: '0.93em',
      color: AMBER,
      background: BG_SOFT,
      padding: '1px 6px',
      borderRadius: 3,
      letterSpacing: '0.02em',
    }}>{children}</code>
  )
}

function PlacementSection() {
  return (
    <section>
      <SectionTitle num={1} id="placement">Honest placement in the world-model taxonomy</SectionTitle>
      <P>
        Li's taxonomy defines three world-model functions plus the POMDP loop:{' '}
        <strong style={{ color: TEXT }}>Renderer</strong> outputs observations (pixels),{' '}
        <strong style={{ color: TEXT }}>Simulator</strong> outputs state (physics / dynamics),
        and <strong style={{ color: TEXT }}>Planner</strong> outputs actions.
        QorTroller is <strong style={{ color: AMBER }}>none of these.</strong>
      </P>
      <P>
        QorTroller instruments the <em>agent → action</em> edge of a real human in
        the loop and stamps that edge with cryptographic provenance.
        In Li's own framing, QorTroller is a provenance-attested source
        of the scarcest input the taxonomy names.
      </P>

      <div style={{
        margin: '28px 0',
        padding: '22px 26px',
        background: BG_SOFT,
        border: `1px solid ${CHAIN}33`,
        borderRadius: 6,
        maxWidth: '64ch',
      }}>
        <div style={{
          fontFamily: Mono, fontSize: 10, color: TEXT_FAINT,
          letterSpacing: '0.22em', textTransform: 'uppercase', marginBottom: 12,
        }}>What WMP can provide</div>
        <ul style={{ margin: 0, paddingLeft: 22, lineHeight: 1.7, color: TEXT_DIM, fontFamily: Syne, fontSize: 15 }}>
          <li>Provenance-attested human action traces (controller input dynamics)</li>
          <li>Cryptographic proof: real human, real recency, real consent</li>
        </ul>
      </div>

      <div style={{
        margin: '24px 0 0',
        padding: '22px 26px',
        background: BG_SOFT,
        border: `1px solid ${AMBER}33`,
        borderRadius: 6,
        maxWidth: '64ch',
      }}>
        <div style={{
          fontFamily: Mono, fontSize: 10, color: TEXT_FAINT,
          letterSpacing: '0.22em', textTransform: 'uppercase', marginBottom: 12,
        }}>What WMP <span style={{ color: AMBER }}>cannot</span> provide — and why</div>
        <ul style={{ margin: 0, paddingLeft: 22, lineHeight: 1.7, color: TEXT_DIM, fontFamily: Syne, fontSize: 15 }}>
          <li>The observation channel (no framebuffer; permanently forbidden by data floor)</li>
          <li>Biomechanical micro-signal (sanitization destroys it; this is the safety property — exported corpora cannot train a bot past the liveness moat)</li>
          <li>Full <Code>(observation, action)</Code> POMDP tuples</li>
          <li>Synthetic augmentation (real sessions only; the realness IS the value)</li>
        </ul>
      </div>
    </section>
  )
}

function ContractSection() {
  return (
    <section>
      <SectionTitle num={2} id="contract">What the bundle contains</SectionTitle>
      <P>
        A <Code>ProvenanceBundle v1</Code> is JSONL-per-session. Each row
        is a frozen dataclass with five sections:
      </P>
      <BundleField label="action_trace">
        Post-φ sanitized matrix at 60 Hz: stick L/R as 4-bit radial sectors,
        triggers as 4-bit compressed states, button mask as 16-bit, IMU
        gravity as 3-bit posture octants. Reference (not copy) to{' '}
        <Code>sanitized_trace_root</Code> — the Poseidon root that's the
        public input to the Groth16 proof.
      </BundleField>
      <BundleField label="humanity_proof">
        Arc 5 VHR Groth16 proof bytes hex, public inputs, verifier address
        on IoTeX testnet. Honest deferred path: when the prover is
        unavailable, <Code>humanity_deferred=true</Code> +{' '}
        <Code>humanity_deferred_reason</Code>.
      </BundleField>
      <BundleField label="recency_proof">
        Arc 6 PoSR — open/close block hashes from{' '}
        <Code>VAPITemporalBeaconRegistry</Code> (deployed{' '}
        <Code>0x96244031…</Code> 2026-06-05). Empty registry address
        surfaces <Code>BEACON_REGISTRY_NOT_DEPLOYED</Code> honestly.
      </BundleField>
      <BundleField label="consent_ref">
        Arc 4 ConsentManifest reference + WMP world-model dimension.
        v1 (W1-D operator decision): <Code>world_model_consent_dimension="DEFERRED"</Code>.
        Phase-2 wires the greenfield{' '}
        <Code>VAPIWorldModelConsentRegistry</Code> view-call.
      </BundleField>
      <BundleField label="scope_disclosure">
        FROZEN values asserting the lane is action-channel only, no
        observation, no biometric fidelity, not a full POMDP tuple.
        Missing or overclaiming this block → REJECTED by the verifier.
      </BundleField>
    </section>
  )
}

function BundleField({ label, children }) {
  return (
    <div style={{
      margin: '16px 0',
      display: 'grid',
      gridTemplateColumns: 'minmax(150px, 200px) 1fr',
      gap: 22,
      paddingBottom: 14,
      borderBottom: `1px solid ${BORDER}88`,
      maxWidth: '64ch',
    }}>
      <div style={{
        fontFamily: Mono,
        fontSize: 12,
        color: AMBER,
        letterSpacing: '0.04em',
        paddingTop: 2,
      }}>
        {label}
      </div>
      <div style={{
        fontFamily: Syne,
        fontSize: 15,
        color: TEXT_DIM,
        lineHeight: 1.65,
      }}>
        {children}
      </div>
    </div>
  )
}

function VerifySection() {
  return (
    <section>
      <SectionTitle num={3} id="verify">Verify in your browser</SectionTitle>
      <P>
        Paste a bundle JSON into the box below and watch each check
        evaluate. The verifier runs <strong style={{ color: TEXT }}>locally
        in this tab</strong> — no trust in QorTroller's infrastructure
        required. The structural rehash check is a JS port of the Python{' '}
        <Code>sdk/wmp_verify.py</Code> and produces byte-identical
        digests.
      </P>
      <InBrowserVerifierPanel />
    </section>
  )
}

function SafetySection() {
  return (
    <section>
      <SectionTitle num={4} id="safety">Safety rails (the moat stays intact)</SectionTitle>
      <P>
        The discriminative signal that powers the anti-cheat moat lives in
        the high-frequency micro-tremor variance and L4 Mahalanobis
        features. The φ pre-processor destroys these BEFORE they reach the
        export path. The{' '}
        <Code>FORBIDDEN_COLUMNS</Code> frozenset (
        <Code>INV-VHR-004</Code>, single source of truth) is the
        cryptographic guard: any caller-supplied field matching a
        forbidden name raises{' '}
        <Code>DataFloorViolationError</Code> before the bundle is built.
      </P>
      <P>
        What this means for a research lab buying a corpus: exported data
        is macro-intent (gameplay strategy), comparable in information
        content to any esports replay. It carries no biomechanical
        signal that could be used to train a bot past the liveness
        verification.
      </P>
    </section>
  )
}

function QuickstartSection() {
  return (
    <section>
      <SectionTitle num={5} id="quickstart">Quickstart</SectionTitle>
      <P>
        Three commands, on your machine:
      </P>
      <CodeBlock>
{`# 1. clone + install deps
git clone https://github.com/ConWan30/QorTroller.git
cd QorTroller && pip install -r bridge/requirements.txt

# 2. assemble + export fixture bundles to JSONL
python scripts/wmp_export.py \\
    --out ./out --allow-fixtures \\
    --fixture-corpus tests/fixtures/wmp_corpus

# 3. verify the JSONL corpus
python scripts/verify_action_provenance.py \\
    --corpus ./out/wmp_corpus.jsonl --allow-synthetic`}
      </CodeBlock>
      <P>
        v1 ships <strong style={{ color: TEXT }}>on fixtures only.</strong>{' '}
        Real-gamer-data export is gated behind a cryptographic consent leg
        that lives in a greenfield <Code>VAPIWorldModelConsentRegistry</Code>{' '}
        — Solidity + Hardhat tests in repo, deploy promotes when the
        first paying buyer needs export. Honest deferral, the same
        pattern as <Code>DeferredProver</Code> and the Arc 6 keeper-unset
        path.
      </P>
    </section>
  )
}

function CodeBlock({ children }) {
  return (
    <pre style={{
      margin: '20px 0',
      padding: '22px 24px',
      background: BG_SOFT,
      border: `1px solid ${BORDER}`,
      borderRadius: 6,
      fontFamily: Mono,
      fontSize: 12.5,
      color: TEXT,
      lineHeight: 1.7,
      letterSpacing: '0.01em',
      overflowX: 'auto',
      maxWidth: '64ch',
    }}>
      {children}
    </pre>
  )
}

// ──────────────────────────────────────────────────────────────────────
// IN-BROWSER VERIFIER PANEL — the "trust by execution" moment
// ──────────────────────────────────────────────────────────────────────

function InBrowserVerifierPanel() {
  const [text, setText] = useState(JSON.stringify(SAMPLE_BUNDLE, null, 2))
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [allowSynthetic, setAllowSynthetic] = useState(true)
  const [running, setRunning] = useState(false)

  async function run() {
    setRunning(true)
    setError(null)
    setResult(null)
    try {
      const bundle = JSON.parse(text)
      const r = await verifyBundle(bundle, { allowSynthetic })
      setResult(r)
    } catch (e) {
      setError(String(e.message || e))
    }
    setRunning(false)
  }

  function loadSample() {
    setText(JSON.stringify(SAMPLE_BUNDLE, null, 2))
    setResult(null)
    setError(null)
  }

  return (
    <div style={{
      marginTop: 24,
      maxWidth: '72ch',
      border: `1px solid ${BORDER}`,
      borderRadius: 6,
      overflow: 'hidden',
    }}>
      {/* controls strip */}
      <div style={{
        padding: '12px 16px',
        background: BG_SOFT,
        borderBottom: `1px solid ${BORDER}`,
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        gap: 14,
        flexWrap: 'wrap',
        fontFamily: Mono,
        fontSize: 11,
      }}>
        <label style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          color: TEXT_DIM,
          letterSpacing: '0.12em',
          textTransform: 'uppercase',
        }}>
          <input
            type="checkbox"
            checked={allowSynthetic}
            onChange={(e) => setAllowSynthetic(e.target.checked)}
            style={{ accentColor: CHAIN }}
          />
          allow synthetic
        </label>
        <div style={{ display: 'flex', gap: 10 }}>
          <button
            type="button"
            onClick={loadSample}
            style={btnSecondary}
          >
            Load sample
          </button>
          <button
            type="button"
            onClick={run}
            disabled={running}
            style={btnPrimary(running)}
          >
            {running ? 'Verifying…' : 'Verify ↗'}
          </button>
        </div>
      </div>

      {/* textarea */}
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        spellCheck={false}
        rows={14}
        style={{
          width: '100%',
          padding: '16px',
          background: BG,
          border: 'none',
          fontFamily: Mono,
          fontSize: 11.5,
          color: TEXT_DIM,
          lineHeight: 1.6,
          outline: 'none',
          resize: 'vertical',
          boxSizing: 'border-box',
          letterSpacing: '0.01em',
        }}
      />

      {/* results */}
      {error && (
        <div style={{
          padding: '14px 18px',
          background: `${RED}11`,
          borderTop: `1px solid ${RED}55`,
          fontFamily: Mono,
          fontSize: 11.5,
          color: RED,
        }}>
          parse error: {error}
        </div>
      )}
      {result && <VerifyResultBlock result={result} />}
    </div>
  )
}

const btnPrimary = (disabled) => ({
  padding: '8px 18px',
  background: disabled ? BG_SOFT : CHAIN,
  color: disabled ? TEXT_FAINT : BG,
  border: 'none',
  borderRadius: 3,
  fontFamily: Mono,
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: '0.14em',
  textTransform: 'uppercase',
  cursor: disabled ? 'not-allowed' : 'pointer',
})

const btnSecondary = {
  padding: '8px 14px',
  background: 'transparent',
  color: TEXT_DIM,
  border: `1px solid ${BORDER}`,
  borderRadius: 3,
  fontFamily: Mono,
  fontSize: 11,
  letterSpacing: '0.14em',
  textTransform: 'uppercase',
  cursor: 'pointer',
}

function VerifyResultBlock({ result }) {
  const verdictColor = result.overall === OUTCOME_VERIFIED ? CHAIN : RED
  return (
    <div style={{
      borderTop: `2px solid ${verdictColor}`,
      background: BG_SOFT,
      padding: '20px 22px',
      fontFamily: Mono,
      fontSize: 11.5,
    }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'baseline',
        marginBottom: 16,
      }}>
        <span style={{
          fontFamily: Syne,
          fontSize: 26,
          fontWeight: 800,
          color: verdictColor,
          letterSpacing: '-0.02em',
        }}>
          {result.overall}
        </span>
        {result.deferred?.length > 0 && (
          <span style={{
            color: AMBER,
            letterSpacing: '0.14em',
            textTransform: 'uppercase',
            fontSize: 10,
          }}>
            {result.deferred.length} deferred · honest no-op
          </span>
        )}
      </div>

      {Object.entries(result.checks).map(([name, ch]) => (
        <CheckRow key={name} name={name} check={ch} />
      ))}

      {result.reasons?.length > 0 && (
        <div style={{
          marginTop: 14,
          paddingTop: 14,
          borderTop: `1px solid ${BORDER}`,
          color: RED,
          lineHeight: 1.6,
        }}>
          {result.reasons.map((r, i) => (
            <div key={i}>· {r}</div>
          ))}
        </div>
      )}
    </div>
  )
}

function CheckRow({ name, check }) {
  let tone = check.passed ? CHAIN : RED
  let glyph = check.passed ? '✓' : '✗'
  if (check.deferred) { tone = AMBER; glyph = '~' }

  return (
    <div style={{
      padding: '6px 0',
      display: 'grid',
      gridTemplateColumns: '24px 1fr auto',
      gap: 12,
      alignItems: 'baseline',
      borderTop: `1px dashed ${BORDER}88`,
      letterSpacing: '0.04em',
    }}>
      <span style={{ color: tone, fontWeight: 700, fontSize: 14 }}>{glyph}</span>
      <span style={{ color: TEXT_DIM }}>{name}</span>
      <span style={{ color: tone, textTransform: 'uppercase', fontSize: 10, letterSpacing: '0.14em' }}>
        {check.deferred ? (check.deferred_reason || 'DEFERRED') : check.passed ? 'PASS' : 'FAIL'}
      </span>
    </div>
  )
}

// ──────────────────────────────────────────────────────────────────────
// Footer
// ──────────────────────────────────────────────────────────────────────

function Footer() {
  return (
    <footer style={{
      marginTop: 70,
      padding: '32px 6vw',
      borderTop: `1px solid ${BORDER}`,
      fontFamily: Mono,
      fontSize: 10,
      color: TEXT_FAINT,
      letterSpacing: '0.06em',
      lineHeight: 1.8,
      textAlign: 'center',
    }}>
      QorTroller · WMP lane v1 · grounded in Li / World Labs (June 2026) ·{' '}
      <a href="https://github.com/ConWan30/QorTroller" target="_blank" rel="noopener noreferrer" style={{ color: AMBER, textDecoration: 'none' }}>
        source
      </a>
      {' '}·{' '}
      <Link to="/start" style={{ color: AMBER, textDecoration: 'none' }}>
        the gamer-facing surface
      </Link>
    </footer>
  )
}
