// Phase 237-EXTEND — useConsentSubmit hook
//
// Establishes the FIRST on-chain wallet-write pattern in this frontend.
// Future Phase 238 marketplace listings, Phase 239 readiness consent, and
// any other gamer-self-sovereign on-chain action will reference this shape.
//
// Design notes:
//   • Reads `VITE_CONSENT_REGISTRY_ADDRESS` from frontend/.env.local at build
//     time. Empty / missing → hook reports `ready=false` and `grant`/`revoke`
//     become no-ops that surface a friendly error. This matches the bridge-
//     side `chain.is_consent_valid()` fail-open behaviour.
//   • Inline ABI (only 2 write methods + 1 read method) keeps the bundle
//     small and avoids importing artefacts from the contracts/ directory.
//     If the consent ABI ever shifts, update this file AND
//     `bridge/vapi_bridge/chain.py`'s `_CONSENT_REGISTRY_ABI` together — they
//     are sibling sources of truth.
//   • Categories are passed as ENUM names (string) to keep the hook
//     ergonomic; we map name → uint8 internally to match the contract.
//   • TX confirmations are NOT awaited inside the hook — wagmi's
//     `useWaitForTransactionReceipt` is the canonical wait pattern; consumers
//     opt in by chaining it after `grant()` returns the txHash.

import { useCallback } from 'react'
import { useAccount, useWriteContract } from 'wagmi'

const CONSENT_REGISTRY_ADDRESS = import.meta.env.VITE_CONSENT_REGISTRY_ADDRESS || ''

// FROZEN — must match VAPIConsentRegistry.sol enum order (Phase 237)
const CATEGORY_TO_UINT8 = {
  TOURNAMENT_GATE:     0,
  ANONYMIZED_RESEARCH: 1,
  MANUFACTURER_CERT:   2,
  MARKETPLACE:         3,
}

// Minimal ABI — only the 3 methods this hook needs.
// Full contract ABI is at contracts/contracts/VAPIConsentRegistry.sol.
const CONSENT_REGISTRY_ABI = [
  {
    type: 'function',
    name: 'grantConsent',
    stateMutability: 'nonpayable',
    inputs: [
      { name: 'category',    type: 'uint8' },
      { name: 'expiresAt',   type: 'uint64' },
      { name: 'consentHash', type: 'bytes32' },
    ],
    outputs: [],
  },
  {
    type: 'function',
    name: 'revokeConsent',
    stateMutability: 'nonpayable',
    inputs: [{ name: 'category', type: 'uint8' }],
    outputs: [],
  },
  {
    type: 'function',
    name: 'isConsentValid',
    stateMutability: 'view',
    inputs: [
      { name: 'gamer',    type: 'address' },
      { name: 'category', type: 'uint8' },
    ],
    outputs: [{ name: '', type: 'bool' }],
  },
]

/**
 * useConsentSubmit() — wallet-write hook for VAPIConsentRegistry.
 *
 * Returns:
 *   ready          : boolean — true iff connected wallet AND CONSENT_REGISTRY_ADDRESS set
 *   address        : connected wallet address (or undefined)
 *   pending        : true while a tx is mid-broadcast
 *   error          : last error from a grant/revoke call (or null)
 *   grant(category, expiresAt, consentHash) : Promise<txHash>
 *   revoke(category)                        : Promise<txHash>
 */
export function useConsentSubmit() {
  const { address, isConnected } = useAccount()
  const { writeContractAsync, isPending, error } = useWriteContract()

  const ready = Boolean(isConnected && CONSENT_REGISTRY_ADDRESS)

  const grant = useCallback(
    async (categoryName, expiresAt, consentHashHex) => {
      if (!ready) {
        throw new Error(
          !isConnected
            ? 'wallet not connected — call connect() first'
            : 'CONSENT_REGISTRY_ADDRESS not set in frontend/.env.local'
        )
      }
      const cat = CATEGORY_TO_UINT8[categoryName]
      if (cat === undefined) {
        throw new Error(`unknown consent category: ${categoryName}`)
      }
      const consentHash = consentHashHex.startsWith('0x')
        ? consentHashHex
        : `0x${consentHashHex}`
      return writeContractAsync({
        address: CONSENT_REGISTRY_ADDRESS,
        abi:     CONSENT_REGISTRY_ABI,
        functionName: 'grantConsent',
        args: [cat, BigInt(expiresAt), consentHash],
      })
    },
    [ready, isConnected, writeContractAsync]
  )

  const revoke = useCallback(
    async (categoryName) => {
      if (!ready) {
        throw new Error(
          !isConnected
            ? 'wallet not connected — call connect() first'
            : 'CONSENT_REGISTRY_ADDRESS not set in frontend/.env.local'
        )
      }
      const cat = CATEGORY_TO_UINT8[categoryName]
      if (cat === undefined) {
        throw new Error(`unknown consent category: ${categoryName}`)
      }
      return writeContractAsync({
        address: CONSENT_REGISTRY_ADDRESS,
        abi:     CONSENT_REGISTRY_ABI,
        functionName: 'revokeConsent',
        args: [cat],
      })
    },
    [ready, isConnected, writeContractAsync]
  )

  return {
    ready,
    address,
    pending: isPending,
    error,
    grant,
    revoke,
    contractAddress: CONSENT_REGISTRY_ADDRESS,
  }
}
