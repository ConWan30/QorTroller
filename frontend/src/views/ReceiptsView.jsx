// RECEIPTS — your proof history, honestly stamped.
// GIC progress (your verified-session chain) + the provenance-quadrille idea, read from real
// hooks. Honest caveats (not tournament-grade, not on-chain anchored) are shown calmly, never
// hidden — the same anti-overclaim discipline as the rest of the protocol.

import { useGrindChain } from '../api/bridgeApi'
import { usePublicGicLinks } from '../api/publicForensic'
import { FONTS, GAMER } from '../shared/design/tokens'
import { HashSpecimen } from '../design/Primitives'
import { ExplainChip } from '../components/ExplainChip'

export function ReceiptsView() {
  const { data: chain } = useGrindChain()
  const { data: links } = usePublicGicLinks()
  const len = chain?.chain_length ?? 0
  const target = chain?.grind_target ?? 100
  const intact = chain?.chain_intact
  const pct = target > 0 ? Math.min(100, Math.round((len / target) * 100)) : 0
  const tone = intact === false ? GAMER.red : GAMER.green

  return (
    <div style={{ flex: 1, overflow: 'auto', background: GAMER.bg, padding: '24px 20px 40px',
      display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18 }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontFamily: FONTS.mono, fontSize: 11, letterSpacing: '0.32em',
          textTransform: 'uppercase', color: GAMER.t3 }}>Receipts</div>
        <div style={{ fontFamily: FONTS.body, fontSize: 13, color: GAMER.t2, marginTop: 6, maxWidth: 480 }}>
          The tamper-evident record of your verified sessions.
          <ExplainChip term="gic" label="grind integrity chain" />
        </div>
      </div>

      <div style={{ width: '100%', maxWidth: 620, borderRadius: 14, padding: '22px',
        background: GAMER.bg1, border: `1px solid ${tone}33` }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
          <span style={{ fontFamily: FONTS.display, fontSize: 32, fontWeight: 700, color: GAMER.t1 }}>
            {len}<span style={{ fontSize: 16, color: GAMER.t3 }}> / {target}</span>
          </span>
          <span style={{ fontFamily: FONTS.mono, fontSize: 11, color: tone, letterSpacing: '0.1em' }}>
            {intact === false ? 'CHAIN BREAK' : intact ? 'INTACT' : 'PENDING'}
          </span>
        </div>
        <div style={{ height: 8, borderRadius: 4, background: GAMER.bg3, marginTop: 12, overflow: 'hidden' }}>
          <div style={{ width: `${pct}%`, height: '100%', background: tone, transition: 'width 0.4s ease' }} />
        </div>
        {chain?.latest_gic_hash && (
          <div style={{ marginTop: 14 }}>
            <div style={{ fontFamily: FONTS.mono, fontSize: 9, letterSpacing: '0.14em',
              textTransform: 'uppercase', color: GAMER.t3, marginBottom: 4 }}>Latest link</div>
            <HashSpecimen value={chain.latest_gic_hash} size="sm" truncate ends={10} />
          </div>
        )}
      </div>

      <div style={{ width: '100%', maxWidth: 620, borderRadius: 12, padding: '16px 18px',
        border: `1px solid ${GAMER.bd}`, background: GAMER.bg3 }}>
        <div style={{ fontFamily: FONTS.display, fontSize: 14, fontWeight: 700, color: GAMER.t1, marginBottom: 6 }}>
          Provenance seal
          <ExplainChip term="quadrille" label="provenance quadrille" />
        </div>
        <div style={{ fontFamily: FONTS.body, fontSize: 12.5, color: GAMER.t3, lineHeight: 1.5 }}>
          A single seal that four integrity chains all line up — your play, the device, the corpus,
          and the system. The shareable receipt export and the on-chain anchor are deliberate later
          steps; this view does not claim an anchor that has not happened.
          {links?.length ? ` ${links.length} public links available.` : ''}
        </div>
      </div>
    </div>
  )
}
