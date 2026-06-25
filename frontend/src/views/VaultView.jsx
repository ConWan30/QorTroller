// VAULT — "Your gameplay, your keys, your call."
// Shows the gamer's consent categories from the real consent hook, READ-ONLY. Granting and
// revoking are signed by the gamer's own wallet — the bridge can read consent state but can
// never set it (the sovereignty invariant). This view makes that boundary visible and honest.

import { useConsentStatus } from '../api/bridgeApi'
import { FONTS, GAMER } from '../shared/design/tokens'
import { ExplainChip } from '../components/ExplainChip'

const CATEGORIES = [
  { key: 'tournament_gate',     name: 'Tournament play',     desc: 'Use your verified-human proof to enter tournaments.' },
  { key: 'anonymized_research', name: 'Anonymized research', desc: 'Allow anonymized gameplay data to improve the protocol.' },
  { key: 'manufacturer_cert',   name: 'Device certification', desc: 'Share device-authenticity proofs with the manufacturer.' },
  { key: 'marketplace',         name: 'Marketplace',          desc: 'Permit selling your verified-human gameplay data.' },
]

export function VaultView() {
  const { data } = useConsentStatus()
  const granted = data?.categories || data?.granted || {}

  return (
    <div style={{ flex: 1, overflow: 'auto', background: GAMER.bg, padding: '24px 20px 40px',
      display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18 }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontFamily: FONTS.mono, fontSize: 11, letterSpacing: '0.32em',
          textTransform: 'uppercase', color: GAMER.t3 }}>Vault</div>
        <div style={{ fontFamily: FONTS.body, fontSize: 13, color: GAMER.t2, marginTop: 6, maxWidth: 480 }}>
          Your data, your keys. Each permission is granted and revoked with your own wallet.
          <ExplainChip term="consent" label="consent" />
        </div>
      </div>

      <div style={{ width: '100%', maxWidth: 620, display: 'flex', flexDirection: 'column', gap: 10 }}>
        {CATEGORIES.map((c) => {
          const on = !!(granted?.[c.key] ?? granted?.[c.name])
          const tone = on ? GAMER.green : GAMER.t3
          return (
            <div key={c.key} style={{ display: 'flex', alignItems: 'center', gap: 14,
              borderRadius: 10, padding: '14px 16px', background: GAMER.bg1,
              border: `1px solid ${tone}33` }}>
              <div style={{ width: 12, height: 12, borderRadius: '50%', background: tone,
                boxShadow: on ? `0 0 10px ${tone}` : 'none', flexShrink: 0 }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontFamily: FONTS.display, fontSize: 15, fontWeight: 700, color: GAMER.t1 }}>
                  {c.name}
                </div>
                <div style={{ fontFamily: FONTS.body, fontSize: 12, color: GAMER.t3, lineHeight: 1.4 }}>
                  {c.desc}
                </div>
              </div>
              <div style={{ fontFamily: FONTS.mono, fontSize: 11, letterSpacing: '0.1em',
                color: tone, fontWeight: 700 }}>
                {on ? 'GRANTED' : 'OFF'}
              </div>
            </div>
          )
        })}
      </div>

      <div style={{ width: '100%', maxWidth: 620, borderRadius: 12, padding: '14px 16px',
        border: `1px dashed ${GAMER.bd}`, background: GAMER.bg3 }}>
        <div style={{ fontFamily: FONTS.body, fontSize: 12.5, color: GAMER.t3, lineHeight: 1.5 }}>
          This view reads your on-chain consent. To change a permission you sign with your wallet —
          the wallet-signed grant/revoke flow connects in a later stage. The bridge will never set
          consent for you.
          <ExplainChip term="zkba" label="proof cards" />
        </div>
      </div>
    </div>
  )
}
