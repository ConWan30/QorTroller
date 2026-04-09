// src/shared/components/TierSelector.jsx
import React from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useAuthStore } from '../store/authStore'
import { FONTS, GAMER, DEVELOPER, MANUFACTURER } from '../design/tokens'

const TIERS = [
  {
    id:       'gamer',
    title:    'Gamer',
    accent:   GAMER.cyan,
    accent2:  GAMER.green,
    bg:       GAMER.bg1,
    bd:       GAMER.bd,
    tagline:  'Your proof of humanity',
    desc:     'Connect ioPay, plug in your DualShock Edge, watch your biometric proof build in real time.',
    features: ['Live PITL session feed', 'VHP credential status', 'Enrollment progress', 'Controller Twin 3D', 'Proof QR share'],
    auth:     'ioPay wallet · no api key required',
    path:     '/gamer',
  },
  {
    id:       'developer',
    title:    'Developer',
    accent:   DEVELOPER.orange,
    accent2:  DEVELOPER.amber,
    bg:       DEVELOPER.bg1,
    bd:       DEVELOPER.bd,
    tagline:  'Integrate in one call',
    desc:     'isFullyEligible() behind 16 agents, dual-primitive proof, and 87 bridge tools. Full SDK + OpenAPI reference.',
    features: ['Tournament readiness scorecard', 'Live agent fleet status', 'Gate tester + preflight', 'SDK quickstart'],
    auth:     'Operator api_key required',
    path:     '/developer',
  },
  {
    id:       'manufacturer',
    title:    'Manufacturer',
    accent:   MANUFACTURER.blue,
    accent2:  MANUFACTURER.gold,
    bg:       MANUFACTURER.bg1,
    bd:       MANUFACTURER.bd,
    tagline:  'Certify hardware',
    desc:     'Register controllers at Cert Level 1 or 2. Full data lineage, ioSwarm node infrastructure, and VHP mint pipeline.',
    features: ['Device certification registry', 'Data lineage viewer', 'ioSwarm node panel', 'VHP gate stack'],
    auth:     'Operator api_key required',
    path:     '/manufacturer',
  },
]

export function TierSelector() {
  const navigate  = useNavigate()
  const setTier   = useAuthStore(s => s.setTier)

  const pick = (tier) => {
    setTier(tier.id)
    navigate(tier.path)
  }

  return (
    <div style={{
      minHeight:      '100vh',
      background:     '#030609',
      display:        'flex',
      flexDirection:  'column',
      alignItems:     'center',
      justifyContent: 'center',
      padding:        '2rem 1.25rem',
    }}>
      <motion.div
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        style={{ textAlign: 'center', marginBottom: '2.5rem' }}
      >
        <div style={{
          fontFamily:    FONTS.display,
          fontSize:      42,
          fontWeight:    700,
          letterSpacing: 6,
          color:         '#d4e8ff',
          lineHeight:    1,
        }}>
          VAPI
        </div>
        <div style={{
          fontFamily:    FONTS.display,
          fontSize:      11,
          letterSpacing: 4,
          color:         '#1e3a5a',
          marginTop:     6,
          textTransform: 'uppercase',
        }}>
          Verified Autonomous Physical Intelligence
        </div>
        <div style={{
          fontFamily: FONTS.mono,
          fontSize:   9,
          color:      '#0e2535',
          marginTop:  8,
          letterSpacing: '1px',
        }}>
          IoTeX Testnet · Chain ID 4690 · Phase 149 · 39 Contracts Live
        </div>
      </motion.div>

      <div style={{
        display:    'grid',
        gridTemplateColumns: 'repeat(3, minmax(0, 300px))',
        gap:        '1.25rem',
        width:      '100%',
        maxWidth:   980,
      }}>
        {TIERS.map((tier, i) => (
          <motion.div
            key={tier.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25, delay: i * 0.07 }}
            whileHover={{ scale: 1.015 }}
            onClick={() => pick(tier)}
            style={{
              background:   tier.bg,
              border:       `1px solid ${tier.accent}25`,
              borderTop:    `2px solid ${tier.accent}`,
              borderRadius: 10,
              padding:      '1.5rem',
              cursor:       'pointer',
              transition:   'border-color .15s',
            }}
          >
            <div style={{
              fontFamily:    FONTS.display,
              fontSize:      24,
              fontWeight:    700,
              color:         tier.accent,
              letterSpacing: 2,
              marginBottom:  4,
            }}>
              {tier.title.toUpperCase()}
            </div>
            <div style={{
              fontFamily: FONTS.body,
              fontSize:   11,
              color:      tier.accent2,
              marginBottom: 12,
              letterSpacing: '0.5px',
            }}>
              {tier.tagline}
            </div>
            <div style={{
              fontFamily:  FONTS.body,
              fontSize:    12,
              color:       '#4a6070',
              lineHeight:  1.65,
              marginBottom: 14,
            }}>
              {tier.desc}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5, marginBottom: 16 }}>
              {tier.features.map(f => (
                <div key={f} style={{
                  display:    'flex',
                  alignItems: 'center',
                  gap:        7,
                  fontSize:   10,
                  color:      '#3a5060',
                  fontFamily: FONTS.body,
                }}>
                  <span style={{
                    width: 4, height: 4, borderRadius: '50%',
                    background: tier.accent, flexShrink: 0,
                  }} />
                  {f}
                </div>
              ))}
            </div>
            <div style={{
              fontFamily:    FONTS.mono,
              fontSize:      8,
              color:         tier.accent,
              background:    `${tier.accent}10`,
              border:        `1px solid ${tier.accent}25`,
              padding:       '4px 10px',
              borderRadius:  4,
              letterSpacing: '0.5px',
            }}>
              {tier.auth}
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  )
}
