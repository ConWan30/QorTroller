# Data Economy Arc 4 — Consent Manifest Migration

Structured 7-dimension consent manifest, ADDITIVE to the deployed Phase 237
`VAPIConsentRegistry` bitmask surface. This note records the migration posture
and the one deliberate divergence from the framework spec (§8 lines 978-1028).

## Deliberate divergence from the spec

The framework spec (line 1024) proposed adding
`VAPIConsentRegistry.getManifest(deviceId)` **in place** on the existing
contract. Pre-investigation (the spec's own §8 checklist item 1) found that
`VAPIConsentRegistry` is a fixed `Ownable + ReentrancyGuard` contract with **no
proxy** — it cannot be upgraded in place. Per the SeparationRatioRegistry
redeploy precedent (2026-05-24), the manifest therefore ships as a **separate
additive contract**, `VAPIConsentManifestRegistry`, rather than an in-place
upgrade.

Two consequences of the separate-contract approach:

1. **Key is the gamer ADDRESS, not the deviceId.** The bitmask registry is
   keyed per `(gamer, category)`; the manifest registry is keyed per gamer
   `msg.sender`. `getManifest(address)` / `hasManifest(address)` take an
   address. This preserves the self-sovereignty invariant — the bridge can
   never write a manifest on a gamer's behalf.
2. **No FROZEN-surface edit.** The `VAPI-CONSENT-v1` commitment formula (frozen
   PATTERN-017 family #5) and the `ConsentCategory` enum
   (`TOURNAMENT_GATE=0 … MARKETPLACE=3`) are untouched. The new
   `manifestHash = keccak256(abi.encode(...15 policy fields...))` is a fresh
   deterministic digest, deliberately NOT registered as a new frozen family
   (no governance ceremony required).

## Backward compatibility (P-check: existing consumers still function)

- The deployed `VAPIConsentRegistry` (`0xA82dB0eF0bF7D15b6400EDd4A09C0D4338C948dA`)
  is unchanged. `isConsentValid` / `getConsentRecord` / `grantConsent` /
  `revokeConsent` remain fully callable.
- Bridge reads stay fail-open: `chain.is_consent_valid` /
  `chain.get_consent_record` (Phase 237) and the new
  `chain.get_consent_manifest` (Arc 4) all return fail-open defaults when their
  respective registry address is unset, so bridge readiness never depends on a
  deploy.

## Default derivation (bitmask → manifest)

A gamer's legacy per-category bitmask maps to sensible manifest defaults when
they first set a structured manifest. This is a **gamer-side / frontend**
convenience (the gamer signs `setManifest`), NOT a bridge critical-path
operation — the bridge only ever READS the manifest. Suggested default mapping
when promoting a legacy consent to a manifest:

| Legacy bitmask category | Manifest default |
|---|---|
| `MARKETPLACE` (3) granted | `allowAggregateStats=true`, `allowSkillRankingProof=true`, `allowTrajectoryProof=true` (tiers 1-2 default-ON); tiers 3-4 OFF |
| `ANONYMIZED_RESEARCH` (1) granted | `allowAcademic=true`, `allowAnonymous=true` |
| (none of the above) | empty manifest — gamer opts in explicitly |

Floors are always stamped at the protocol minimum on a fresh manifest:
`minSessionsPerPackage = 10`, `coolingPeriodHours = 72`, `autonomyLevel = 1`
(approval_required — never full at init). A manifest violating either floor
reverts on-chain.

## Deploy posture

Deploy of `VAPIConsentManifestRegistry` is **DEFERRED, operator-fired**. Until
it is deployed and `CONSENT_MANIFEST_REGISTRY_ADDRESS` is set, the Curator
packaging loop uses the Arc 3 local-manifest path unchanged. Once the address
is set, the loop prefers the structured on-chain manifest and fails closed when
a gamer has no on-chain manifest (a configured registry is the authority).
