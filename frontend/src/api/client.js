// VAPI API client — every fetch goes through here
// W1 fix (Phase 224): attaches x-api-key header on every request
// Key is read from VITE_VAPI_API_KEY env var — never inlined as a string literal
// Phase 236-VAME: every JSON response is validated against the X-VAME-Commitment
// sidecar header so a MITM that mutates the body but can't forge the GIC-bound
// commitment is detected at the application layer.

import { validateVame } from './vame'
import { isMockActive, deactivateMock } from './mockBridge'

const _key = import.meta.env.VITE_VAPI_API_KEY

// Fail at build time if env var is missing in production
if (import.meta.env.PROD && !_key) {
  throw new Error(
    'VITE_VAPI_API_KEY is not set. Copy frontend/.env.example to frontend/.env.local ' +
    'and set OPERATOR_API_KEY from bridge/.env'
  )
}

// Typed errors the UI layer can branch on
export class ApiKeyError extends Error {
  constructor() { super('Operator key invalid (401/403)'); this.name = 'ApiKeyError' }
}
export class BridgeOfflineError extends Error {
  constructor() { super('Bridge offline'); this.name = 'BridgeOfflineError' }
}

// Core fetch wrapper: attaches x-api-key header + api_key query param (for legacy endpoints)
// Returns parsed JSON on success; throws typed error on auth/offline failure
export async function apiGet(path, options = {}) {
  // Append api_key as query param for older endpoints that still require it
  const url = _key ? `${path}${path.includes('?') ? '&' : '?'}api_key=${encodeURIComponent(_key)}` : path

  const headers = { 'Content-Type': 'application/json' }
  if (_key) headers['x-api-key'] = _key

  const res = await fetch(url, {
    method: 'GET',
    headers,
    signal: AbortSignal.timeout(options.timeout ?? 5000),
    ...options,
  })

  if (res.status === 401 || res.status === 403) throw new ApiKeyError()
  if (res.status === 503 || res.status === 502 || res.status === 504) throw new BridgeOfflineError()
  if (!res.ok) throw new BridgeOfflineError()

  // Phase 236-VAME: validate the sidecar commitment BEFORE parsing JSON.
  // Read the body once as ArrayBuffer (so VAME can hash the exact bytes the
  // server signed), then parse the same buffer as JSON. Browser caches handle
  // the second read efficiently; we never refetch.
  const bodyBuf  = await res.arrayBuffer()
  const bodyView = new Uint8Array(bodyBuf)
  // VAME validation runs but never throws — failures surface via vameFailureCount()
  await validateVame(res.headers, path, bodyView)
  // Mythos audit fix (post-/goal 2026-05-15): clear the sticky mock
  // banner here, on EVERY successful fetch — not only on get()-helper
  // routed calls. The prior placement (bridgeApi.js:28) missed
  // direct-apiGet hooks (BrpView, EnrollmentStatus, etc.), so when
  // the bridge recovered while the user was on a tab whose hooks
  // bypass get(), the __vapiMockActive flag stayed stuck and the
  // 'MOCK DATA — bridge offline' banner persisted. Closing this gap
  // makes recovery automatic regardless of which view is active.
  if (isMockActive()) deactivateMock()
  return JSON.parse(new TextDecoder('utf-8').decode(bodyView))
}

export async function apiPost(path, body, options = {}) {
  const url = _key ? `${path}${path.includes('?') ? '&' : '?'}api_key=${encodeURIComponent(_key)}` : path

  const headers = { 'Content-Type': 'application/json' }
  if (_key) headers['x-api-key'] = _key

  const res = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(options.timeout ?? 5000),
    ...options,
  })

  if (res.status === 401 || res.status === 403) throw new ApiKeyError()
  if (res.status === 503 || res.status === 502 || res.status === 504) throw new BridgeOfflineError()
  if (!res.ok) throw new BridgeOfflineError()

  // Mythos audit fix — mirror the apiGet success-path mock clear.
  if (isMockActive()) deactivateMock()
  return res.json()
}
