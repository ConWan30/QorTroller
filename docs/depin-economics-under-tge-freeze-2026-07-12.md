# DePIN economics under the TGE freeze — token-free rails + anti-cosplay list

**2026-07-12 · A2A-CDM build ⑤ (grok R04 Q2-P4 + Q3-P1/P2/P4, grounded R05).** The honest answer to
"how is this DePIN *now*, with the token frozen": **verifiable services, not rewards.** Every model
below runs on what is live today; everything that needs a token says so.

## Token-free models (honest DePIN-now)

| model | how it works without a token | what BREAKS without a token |
|---|---|---|
| **Venue fee-for-attestation** | venue charges fiat/invoice for N observation certificates + verify support; reputation = public re-verify pass-rate + uptime log (hash-anchored, free) | cryptoeconomic slash · permissionless bonding · transferable stake reputation |
| **Mesh verification credits** | venues prepay **credits** redeemable for cross-seat re-verify compute — **non-transferable + fiat-denominated + expiring** (SaaS API-credit shape; the R05 anti-cosplay rail) | trustless cross-venue slash · global staking pool · anonymous node entry |
| **Dual fiat SKUs** | action-provenance bundles (consent leg **LIVE** — `VAPIWorldModelConsentRegistry`) and observation-provenance seals as separate fiat SKUs; a joined SKU only when both consents exist | on-chain settlement in protocol units · burn/mint · automated token royalty splits |

What survives in ALL models: gamer-sovereign grant/revoke · consent-category gates · Curator packaging
abort on consent fail · zero-trust re-verification by the buyer · exclusion-from-next-event as the
enforcement of last resort (contract law + ToS, not slashing).

## The anti-cosplay list (do NOT ship before TGE — grok Q3-P4, adopted as a standing rail)

- No pretend-stake, no points-as-token, no "soulbound mining rewards" implying transferable economic
  security.
- No transferable or secondary-priced credits (that is a token with extra steps).
- Stake/slash designs (asymmetric role-typed slash, bonded oracles, witness lotteries) remain
  **design-ahead documents only** until TGE — and TGE itself stays sequenced behind the separation-
  ratio invariant (CLAUDE.md hard rule).

## Default-grants matrix (UX defaults vs cryptographic categories — grok Q2-P4)

| activity | consent surface it needs | status today |
|---|---|---|
| tournament play | v1 `TOURNAMENT_GATE` (frozen bitmask) | LIVE |
| WMP action-bundle export | standalone WM registry (`isWorldModelConsentGranted`) | **LIVE** (gamer-granted 2026-07-11) |
| observation SKU / venue catalog / spectator | CONSENT-v2 categories (design-ahead: locus × export, R04 Q2-P1) | **GATED: CONSENT-v2 ceremony** — which must FIRST reconcile the three-layer surface (v1 bitmask · Arc-4 manifest dimensions · standalone WM registry — the R05 headline catch) |

Until the v2 ceremony: observation stays local/advisory with **no marketplace claim** — UX may
*recommend*, only categories *permit*.

---
*A2A-CDM build ⑤ — economics rails from grok R04, sharpened by Claude R05 (credits rail, three-layer
consent reconciliation, action-SKU split). Ideation/docs only; TGE frozen; ceremony operator-fired.*
