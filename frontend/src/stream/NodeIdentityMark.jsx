/**
 * STREAM-2 Q1 — NodeIdentityMark
 * Ambient "you are a node" face: short node_id + derived-not-minted honesty.
 * Never paints a fabricated hex. Missing identity → dignified unformed state.
 */
import React from 'react'
import { STREAM_PAL, STREAM_FONTS } from './streamTokens'

export function NodeIdentityMark({ identity = null }) {
  const present = Boolean(identity && identity.present && identity.node_id_short)
  const short = present ? identity.node_id_short : null
  const claim = (identity && identity.claim_language) || 'derived_not_minted'
  const deviceShort = identity?.device_id_short || null
  const deviceEvidence = Boolean(identity?.device_on_chain_evidence)

  return (
    <div
      data-testid="node-identity-mark"
      data-present={present ? 'true' : 'false'}
      data-claim={claim}
      style={{
        fontFamily: STREAM_FONTS.mono,
        border: `1px solid ${STREAM_PAL.bd}`,
        borderRadius: 6,
        padding: '12px 14px',
        background: STREAM_PAL.void1,
      }}
    >
      <div style={{
        color: STREAM_PAL.amber,
        fontSize: 10,
        letterSpacing: '0.12em',
        textTransform: 'uppercase',
        marginBottom: 8,
      }}>
        Node · identity
      </div>
      {present ? (
        <>
          <div
            data-testid="node-id-short"
            style={{
              color: STREAM_PAL.cyan,
              fontSize: 18,
              letterSpacing: '0.06em',
              marginBottom: 6,
            }}
          >
            {short}
          </div>
          <div style={{ color: STREAM_PAL.dim, fontSize: 11, lineHeight: 1.6 }}>
            <span data-testid="node-claim">derived spine · not minted</span>
            {deviceEvidence && deviceShort ? (
              <span data-testid="device-evidence">
                {' · '}device {deviceShort}… may be on-chain; node_id is not
              </span>
            ) : (
              <span data-testid="device-evidence-absent"> · device evidence ABSENT</span>
            )}
          </div>
        </>
      ) : (
        <div data-testid="node-id-unformed" style={{ color: STREAM_PAL.dim, fontSize: 12, lineHeight: 1.6 }}>
          {identity?.line || 'node identity unformed — birth + public device_id required'}
        </div>
      )}
    </div>
  )
}

export default NodeIdentityMark
