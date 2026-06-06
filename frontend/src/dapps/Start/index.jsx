// Mainstream gamer onboarding — /start
//
// Build 1 of the operator-directed /goal build order (2→1→4→3→5→6).
//
// The door for mainstream PS5 gamers who heard about QorTroller from a
// streamer and need to understand WHY before they touch /consent. The
// operator dashboard is forensic — graticule + monospace + dense data;
// correct for operators, COLD for first-time gamers. This surface uses
// a different room: warmer black (no graticule), generous whitespace,
// Syne display carrying the narrative, JetBrains Mono only where data
// appears as evidence.
//
// Scroll-triggered storytelling in three acts:
//   1. The physical input you make is a fingerprint
//   2. The protocol turns that fingerprint into cryptographic memory
//   3. The data is yours — verifiable, revocable, sovereign
//
// Live data hooks: pulls the actual GIC chain head from the bridge so
// readers can SEE the protocol working — the chain advances while they
// read. That moment ("oh — it's real right now") is the differentiator
// vs every static landing page.
//
// Honesty rails: noMock on the live ticker; bridge-offline shows an
// honest "the bridge is asleep" state. Never fabricates a chain length.

import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion, useScroll, useTransform } from 'framer-motion'
import { useGrindChain } from '../../api/bridgeApi'

// ── tokens (in-line, not theme-bound — this dApp wants warmth) ──
const VOID = '#06090e'              // warmer black than operator graticule
const VOID_SOFT = '#0a0e14'
const CHAIN = '#5bd6a3'
const AMBER = '#f0a868'
const TEXT = '#e8eef5'              // brighter than operator text
const TEXT_DIM = '#9aa6b4'
const TEXT_FAINT = '#5a6675'

const Syne = "'Syne', system-ui, sans-serif"
const Mono = "'JetBrains Mono', monospace"

// ──────────────────────────────────────────────────────────────────────
// HERO — the invitation
// ──────────────────────────────────────────────────────────────────────

function Hero() {
  const ref = useRef(null)
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start start', 'end start'] })
  const y = useTransform(scrollYProgress, [0, 1], [0, -180])
  const opacity = useTransform(scrollYProgress, [0, 0.85], [1, 0])

  return (
    <section ref={ref} style={{
      minHeight: '100vh',
      position: 'relative',
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'space-between',
      padding: '32px 6vw 64px',
    }}>
      {/* top chrome */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'baseline',
        fontFamily: Mono,
        fontSize: 11,
        color: TEXT_FAINT,
      }}>
        <span style={{ fontFamily: Syne, fontSize: 19, fontWeight: 700, color: TEXT, letterSpacing: '-0.02em' }}>
          Qor<span style={{ color: AMBER, fontWeight: 800 }}>T</span>roller
        </span>
        <Link to="/consent" style={{
          color: TEXT_DIM,
          textDecoration: 'none',
          letterSpacing: '0.14em',
          textTransform: 'uppercase',
          fontSize: 10,
        }}>
          Consent Cockpit →
        </Link>
      </div>

      {/* center invitation */}
      <motion.div style={{ y, opacity, maxWidth: 1100, alignSelf: 'flex-start' }}>
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1, duration: 0.85, ease: [0.2, 0.6, 0.2, 1] }}
          style={{
            fontFamily: Mono,
            fontSize: 12,
            letterSpacing: '0.32em',
            color: AMBER,
            textTransform: 'uppercase',
            marginBottom: 28,
          }}
        >
          The protocol that makes cheating <span style={{ color: TEXT }}>structurally impossible</span>
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.32, duration: 1.1, ease: [0.2, 0.6, 0.2, 1] }}
          style={{
            fontFamily: Syne,
            fontWeight: 700,
            fontSize: 'clamp(56px, 9vw, 142px)',
            lineHeight: 0.94,
            letterSpacing: '-0.035em',
            color: TEXT,
            margin: 0,
            maxWidth: '14ch',
          }}
        >
          Your hands<br />
          left a <span style={{ color: AMBER, fontWeight: 800 }}>signature.</span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.7, duration: 0.85, ease: [0.2, 0.6, 0.2, 1] }}
          style={{
            fontFamily: Syne,
            fontSize: 'clamp(18px, 1.8vw, 26px)',
            lineHeight: 1.55,
            color: TEXT_DIM,
            margin: '40px 0 0',
            maxWidth: '54ch',
          }}
        >
          QorTroller turns the way you actually play — the millisecond physics
          of your DualSense Edge — into a cryptographic proof that{' '}
          <span style={{ color: TEXT }}>a real human</span> sat behind those
          inputs. No tracking. No surveillance. Just your hands, signed.
        </motion.p>
      </motion.div>

      {/* scroll cue */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.4, duration: 0.6 }}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          fontFamily: Mono,
          fontSize: 10,
          color: TEXT_FAINT,
          letterSpacing: '0.22em',
          textTransform: 'uppercase',
        }}
      >
        <span style={{
          display: 'inline-block',
          width: 36,
          height: 1,
          background: TEXT_FAINT,
        }} />
        Scroll · to · see · how
      </motion.div>
    </section>
  )
}

// ──────────────────────────────────────────────────────────────────────
// ACT — a single narrative beat with optional live data
// ──────────────────────────────────────────────────────────────────────

function Act({ num, eyebrow, title, body, evidence, accent }) {
  const ref = useRef(null)
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    const node = ref.current
    if (!node) return
    if (typeof IntersectionObserver === 'undefined') {
      setVisible(true)
      return
    }
    const obs = new IntersectionObserver(
      ([entry]) => entry.isIntersecting && setVisible(true),
      { threshold: 0.4 },
    )
    obs.observe(node)
    return () => obs.disconnect()
  }, [])

  return (
    <section ref={ref} style={{
      minHeight: '90vh',
      padding: '14vh 6vw',
      display: 'grid',
      gridTemplateColumns: 'minmax(0, 1fr)',
      gap: 0,
      alignContent: 'center',
    }}>
      <div style={{ maxWidth: 1140 }}>
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          animate={visible ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.7, ease: [0.2, 0.6, 0.2, 1] }}
          style={{
            display: 'flex',
            alignItems: 'baseline',
            gap: 20,
            marginBottom: 28,
          }}
        >
          <span style={{
            fontFamily: Mono,
            fontSize: 13,
            color: accent || AMBER,
            letterSpacing: '0.32em',
          }}>
            {String(num).padStart(2, '0')}
          </span>
          <span style={{
            fontFamily: Mono,
            fontSize: 11,
            color: TEXT_FAINT,
            letterSpacing: '0.24em',
            textTransform: 'uppercase',
          }}>
            {eyebrow}
          </span>
        </motion.div>

        <motion.h2
          initial={{ opacity: 0, y: 36 }}
          animate={visible ? { opacity: 1, y: 0 } : {}}
          transition={{ delay: 0.1, duration: 0.85, ease: [0.2, 0.6, 0.2, 1] }}
          style={{
            fontFamily: Syne,
            fontWeight: 700,
            fontSize: 'clamp(40px, 6vw, 86px)',
            lineHeight: 1.0,
            letterSpacing: '-0.025em',
            color: TEXT,
            margin: 0,
            maxWidth: '18ch',
          }}
        >
          {title}
        </motion.h2>

        <motion.p
          initial={{ opacity: 0, y: 28 }}
          animate={visible ? { opacity: 1, y: 0 } : {}}
          transition={{ delay: 0.28, duration: 0.85, ease: [0.2, 0.6, 0.2, 1] }}
          style={{
            fontFamily: Syne,
            fontSize: 'clamp(17px, 1.55vw, 22px)',
            lineHeight: 1.65,
            color: TEXT_DIM,
            margin: '40px 0 0',
            maxWidth: '52ch',
          }}
        >
          {body}
        </motion.p>

        {evidence && (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={visible ? { opacity: 1, y: 0 } : {}}
            transition={{ delay: 0.5, duration: 0.7, ease: [0.2, 0.6, 0.2, 1] }}
            style={{ marginTop: 56 }}
          >
            {evidence}
          </motion.div>
        )}
      </div>
    </section>
  )
}

// ──────────────────────────────────────────────────────────────────────
// LIVE CHAIN TICKER — the "this is real right now" moment
// ──────────────────────────────────────────────────────────────────────

function LiveChainEvidence() {
  const { data: grindChain, isError } = useGrindChain()
  const chainLength = grindChain?.chain_length
  const chainHead = grindChain?.latest_gic_hash
  const intact = grindChain?.chain_intact

  // Empty/error: honest state, never a fabricated number
  if (isError || chainLength == null) {
    return (
      <div style={{
        padding: '22px 24px',
        border: `1px dashed #2a3850`,
        borderRadius: 6,
        maxWidth: 580,
        fontFamily: Mono,
        fontSize: 12,
        color: TEXT_FAINT,
        lineHeight: 1.6,
      }}>
        the bridge is asleep right now — when it wakes, the chain advances
        every few seconds, live
      </div>
    )
  }

  return (
    <div style={{
      padding: '22px 26px',
      background: VOID_SOFT,
      border: `1px solid ${CHAIN}33`,
      borderRadius: 6,
      maxWidth: 620,
      display: 'flex',
      flexDirection: 'column',
      gap: 14,
    }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'baseline',
      }}>
        <span style={{
          fontFamily: Mono,
          fontSize: 9,
          color: TEXT_FAINT,
          letterSpacing: '0.24em',
          textTransform: 'uppercase',
        }}>
          Live · this bridge · right now
        </span>
        <span style={{
          fontFamily: Mono,
          fontSize: 9,
          color: intact ? CHAIN : AMBER,
          letterSpacing: '0.18em',
          textTransform: 'uppercase',
        }}>
          {intact ? '● chain intact' : '○ chain interrupted'}
        </span>
      </div>
      <div style={{
        display: 'flex',
        alignItems: 'baseline',
        gap: 16,
      }}>
        <span style={{
          fontFamily: Syne,
          fontSize: 56,
          fontWeight: 700,
          letterSpacing: '-0.03em',
          color: CHAIN,
          lineHeight: 1,
        }}>
          {chainLength.toLocaleString()}
        </span>
        <span style={{
          fontFamily: Mono,
          fontSize: 11,
          color: TEXT_DIM,
        }}>
          PoAC frames signed, hash-chained, anchored
        </span>
      </div>
      {chainHead && (
        <div style={{
          fontFamily: Mono,
          fontSize: 10,
          color: TEXT_FAINT,
          letterSpacing: '0.05em',
          wordBreak: 'break-all',
        }}>
          head: <span style={{ color: TEXT_DIM }}>{chainHead.slice(0, 24)}…{chainHead.slice(-8)}</span>
        </div>
      )}
    </div>
  )
}

// ──────────────────────────────────────────────────────────────────────
// CONTROLLER FRAME — Act I evidence (no 3D, just a tasteful visual cue)
// ──────────────────────────────────────────────────────────────────────

function ControllerFrame() {
  return (
    <div style={{
      padding: '24px 28px',
      maxWidth: 600,
      display: 'grid',
      gridTemplateColumns: 'auto 1fr',
      gap: 24,
      alignItems: 'center',
      border: `1px solid #1a2230`,
      borderRadius: 6,
      background: VOID_SOFT,
    }}>
      {/* Stylized controller icon — pure CSS, no asset dependency */}
      <div style={{
        width: 84,
        height: 64,
        position: 'relative',
        flexShrink: 0,
      }}>
        <div style={{
          position: 'absolute',
          inset: '8px 0 8px 0',
          borderRadius: '50px / 38px',
          background: 'linear-gradient(180deg, #1a2230, #0d1218)',
          border: `1px solid ${AMBER}33`,
          boxShadow: `inset 0 0 12px ${AMBER}15`,
        }} />
        <div style={{
          position: 'absolute',
          left: 18, top: 22,
          width: 10, height: 10, borderRadius: '50%',
          background: CHAIN,
          boxShadow: `0 0 8px ${CHAIN}`,
        }} />
        <div style={{
          position: 'absolute',
          right: 18, top: 22,
          width: 10, height: 10, borderRadius: '50%',
          background: TEXT_DIM,
        }} />
      </div>
      <div>
        <div style={{
          fontFamily: Mono,
          fontSize: 9,
          color: TEXT_FAINT,
          letterSpacing: '0.22em',
          textTransform: 'uppercase',
          marginBottom: 8,
        }}>
          What the protocol measures
        </div>
        <div style={{
          fontFamily: Syne,
          fontSize: 16,
          color: TEXT,
          lineHeight: 1.5,
          marginBottom: 4,
        }}>
          1,002 Hz · stick + trigger + IMU
        </div>
        <div style={{
          fontFamily: Mono,
          fontSize: 11,
          color: TEXT_DIM,
          lineHeight: 1.5,
        }}>
          14,000× injection margin · spectral biometrics impossible to spoof
        </div>
      </div>
    </div>
  )
}

// ──────────────────────────────────────────────────────────────────────
// CTA — close the surface, route to /consent
// ──────────────────────────────────────────────────────────────────────

function CallToAction() {
  const ref = useRef(null)
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    const node = ref.current
    if (!node) return
    const obs = new IntersectionObserver(
      ([entry]) => entry.isIntersecting && setVisible(true),
      { threshold: 0.4 },
    )
    obs.observe(node)
    return () => obs.disconnect()
  }, [])

  return (
    <section ref={ref} style={{
      minHeight: '85vh',
      padding: '16vh 6vw 12vh',
      display: 'grid',
      alignContent: 'center',
    }}>
      <motion.div
        initial={{ opacity: 0, y: 32 }}
        animate={visible ? { opacity: 1, y: 0 } : {}}
        transition={{ duration: 1, ease: [0.2, 0.6, 0.2, 1] }}
        style={{ maxWidth: 1100 }}
      >
        <div style={{
          fontFamily: Mono,
          fontSize: 11,
          color: AMBER,
          letterSpacing: '0.28em',
          textTransform: 'uppercase',
          marginBottom: 22,
        }}>
          Ready · when · you · are
        </div>
        <h2 style={{
          fontFamily: Syne,
          fontWeight: 700,
          fontSize: 'clamp(42px, 6.5vw, 92px)',
          lineHeight: 1.0,
          letterSpacing: '-0.03em',
          color: TEXT,
          margin: '0 0 36px',
          maxWidth: '14ch',
        }}>
          Your data,<br />
          <span style={{ color: CHAIN, fontWeight: 800 }}>your authority.</span>
        </h2>
        <p style={{
          fontFamily: Syne,
          fontSize: 'clamp(16px, 1.5vw, 22px)',
          lineHeight: 1.6,
          color: TEXT_DIM,
          margin: '0 0 56px',
          maxWidth: '50ch',
        }}>
          Connect your wallet at the Consent Cockpit. Grant or revoke
          permissions per category. Every grant + revoke is signed by{' '}
          <span style={{ color: TEXT }}>you</span> — the protocol cannot
          forge it. Audit trail is on-chain. Receipts are permanent.
        </p>
        <Link
          to="/consent"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 14,
            padding: '18px 32px',
            background: CHAIN,
            color: VOID,
            borderRadius: 4,
            fontFamily: Mono,
            fontSize: 13,
            fontWeight: 600,
            letterSpacing: '0.18em',
            textTransform: 'uppercase',
            textDecoration: 'none',
            boxShadow: `0 0 32px -8px ${CHAIN}66`,
          }}
        >
          Open the Consent Cockpit →
        </Link>

        <div style={{
          marginTop: 64,
          fontFamily: Mono,
          fontSize: 10,
          color: TEXT_FAINT,
          letterSpacing: '0.14em',
          lineHeight: 1.7,
        }}>
          Not ready? Look at a{' '}
          <Link to="/replay?demo=1" style={{ color: AMBER, textDecoration: 'none' }}>
            verified replay card
          </Link>
          {' '}· read the{' '}
          <Link to="/?view=reference" style={{ color: AMBER, textDecoration: 'none' }}>
            reference
          </Link>
          {' '}· or{' '}
          <a href="https://github.com/ConWan30/QorTroller" target="_blank" rel="noopener noreferrer" style={{ color: AMBER, textDecoration: 'none' }}>
            inspect the source
          </a>
          .
        </div>
      </motion.div>
    </section>
  )
}

// ──────────────────────────────────────────────────────────────────────
// DAPP ENTRY
// ──────────────────────────────────────────────────────────────────────

export default function StartDapp() {
  // Subtle radial that breathes — adds atmosphere without graticule.
  // Position it absolutely so it doesn't interfere with scroll.
  const bgRadial = useMemo(() => `
    radial-gradient(ellipse 80% 50% at 80% -10%, ${AMBER}10, transparent 60%),
    radial-gradient(ellipse 60% 60% at -10% 80%, ${CHAIN}0a, transparent 65%)
  `, [])

  return (
    <div style={{
      background: VOID,
      backgroundImage: bgRadial,
      backgroundAttachment: 'fixed',
      color: TEXT,
      minHeight: '100vh',
      fontFamily: Syne,
    }}>
      <Hero />

      <Act
        num={1}
        eyebrow="Act I · the input"
        title={<>The way you play is <span style={{ color: AMBER }}>uniquely you.</span></>}
        body={
          <>
            Every player squeezes triggers differently. Holds sticks differently.
            Their hands shake at a unique frequency. At a thousand samples per
            second, those differences are <em>measurable</em>. Spoofing them is
            14,000 times harder than the level current bots operate at. The
            certified DualSense Edge is the instrument that makes the
            measurement possible.
          </>
        }
        evidence={<ControllerFrame />}
        accent={AMBER}
      />

      <Act
        num={2}
        eyebrow="Act II · the cryptographic proof"
        title={
          <>
            Every play becomes a <span style={{ color: CHAIN }}>signed receipt.</span>
          </>
        }
        body={
          <>
            A tamper-evident chain of 228-byte cryptographic records — one per
            cognition cycle — hash-linked, anchored on the IoTeX blockchain.
            Below is the actual chain head of this bridge, refreshed in real time.
            No marketing, no mock: if the bridge is running, the number climbs.
          </>
        }
        evidence={<LiveChainEvidence />}
        accent={CHAIN}
      />

      <Act
        num={3}
        eyebrow="Act III · sovereignty"
        title={
          <>
            The protocol cannot speak <span style={{ color: AMBER }}>for you.</span>
          </>
        }
        body={
          <>
            Your consent lives on-chain — signed by your wallet, never by ours.
            Granular: tournament eligibility · research participation · marketplace
            listing · replay-proof export — each is a distinct toggle, each is
            yours to flip. The bridge is a reader, not an author. That property
            is enforced in Solidity by a single rule: msg.sender == gamer.
          </>
        }
        accent={AMBER}
      />

      <CallToAction />

      {/* honest footer */}
      <footer style={{
        padding: '32px 6vw 56px',
        fontFamily: Mono,
        fontSize: 10,
        color: TEXT_FAINT,
        letterSpacing: '0.06em',
        lineHeight: 1.7,
        textAlign: 'center',
        borderTop: `1px solid #1a223044`,
        marginTop: 0,
      }}>
        QorTroller · the reference implementation of <span style={{ color: AMBER }}>V.A.P.I.</span> ·
        Verifiable Autonomous Physical Intelligence · IoTeX L1 · chain ID 4690
      </footer>
    </div>
  )
}
