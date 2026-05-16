/**
 * Phase O5-PUBLIC-VIEWER — public hooks for /public/* endpoints.
 *
 * These hooks DO NOT route through the operator get() helper (which
 * appends api_key + x-api-key). The public surface is unauthenticated
 * by design — anyone can browse the viewer. We use vanilla fetch +
 * react-query with `noMock`-like fail-open semantics (return the
 * shape with a not-found flag rather than mock-substitute).
 *
 * Bridge endpoints consumed:
 *   /public/session/{hash}     → usePublicSession
 *   /public/algorithms         → usePublicAlgorithms
 *   /public/gic/{sessionId}    → usePublicGicChain
 *   /public/agent-roots        → usePublicAgentRoots
 *   /public/protocol-state     → usePublicProtocolState
 */
import { useQuery } from '@tanstack/react-query'
import { validateVame } from './vame'

const _BASE = '/public'

async function publicGet(path) {
  const res = await fetch(_BASE + path, { method: 'GET', mode: 'cors' })
  if (res.status === 429) throw new Error('rate_limited')
  if (!res.ok && res.status !== 404) throw new Error(`HTTP ${res.status}`)
  const bodyBuf = await res.arrayBuffer()
  const bodyView = new Uint8Array(bodyBuf)
  await validateVame(res.headers, _BASE + path, bodyView)
  return JSON.parse(new TextDecoder('utf-8').decode(bodyView))
}

export function usePublicSession(commitmentHex, { enabled = true } = {}) {
  return useQuery({
    queryKey: ['publicSession', commitmentHex],
    queryFn:  () => publicGet(`/session/${commitmentHex}`),
    enabled:  Boolean(commitmentHex) && enabled,
    staleTime: 60_000,
    retry: 1,
  })
}

export function usePublicAlgorithms({ enabled = true } = {}) {
  return useQuery({
    queryKey: ['publicAlgorithms'],
    queryFn:  () => publicGet('/algorithms'),
    enabled,
    staleTime: 5 * 60_000,  // catalog is stable; cache 5 min
    retry: 1,
  })
}

export function usePublicGicChain(grindSessionId, { enabled = true } = {}) {
  return useQuery({
    queryKey: ['publicGicChain', grindSessionId],
    queryFn:  () => publicGet(`/gic/${grindSessionId}`),
    enabled:  Boolean(grindSessionId) && enabled,
    staleTime: 30_000,
    retry: 1,
  })
}

/**
 * Phase O5-PUBLIC-VIEWER Stage 2 — fetch the full chain links list
 * for browser-side recomputation. Returns links[] where each entry
 * carries prev_gic_hex + commitment_hash + verdict_code +
 * host_state_code + gic_ts_ns + grind_chain_hash (the protocol-side
 * answer to verify against).
 */
export function usePublicGicLinks(grindSessionId, { enabled = true, limit = 200 } = {}) {
  return useQuery({
    queryKey: ['publicGicLinks', grindSessionId, limit],
    queryFn:  () => publicGet(`/gic/${grindSessionId}/links?limit=${limit}`),
    enabled:  Boolean(grindSessionId) && enabled,
    staleTime: 60_000,
    retry: 1,
  })
}

export function usePublicAgentRoots({ enabled = true } = {}) {
  return useQuery({
    queryKey: ['publicAgentRoots'],
    queryFn:  () => publicGet('/agent-roots'),
    enabled,
    staleTime: 5 * 60_000,  // identity rarely changes
    retry: 1,
  })
}

export function usePublicProtocolState({ enabled = true } = {}) {
  return useQuery({
    queryKey: ['publicProtocolState'],
    queryFn:  () => publicGet('/protocol-state'),
    enabled,
    refetchInterval: 30_000,
    retry: 1,
  })
}

export function usePublicVhp(tokenId, { enabled = true } = {}) {
  return useQuery({
    queryKey: ['publicVhp', tokenId],
    queryFn:  () => publicGet(`/vhp/${tokenId}`),
    enabled:  (tokenId !== null && tokenId !== undefined) && enabled,
    staleTime: 60_000,
    retry: 1,
  })
}

/**
 * Fetch raw 228-byte PoAC record blob. Used by PoacBodyHasher for
 * in-browser SHA-256 re-execution.
 */
export async function fetchPublicRecordBytes(deviceId, counter) {
  const res = await fetch(
    `${_BASE}/record/${encodeURIComponent(deviceId)}/${counter}`,
    { method: 'GET', mode: 'cors' },
  )
  if (res.status === 404) return null
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const buf = await res.arrayBuffer()
  return new Uint8Array(buf)
}
