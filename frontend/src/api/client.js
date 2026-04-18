// VAPI API client — every fetch goes through here
// W1 fix (Phase 224): attaches x-api-key header on every request
// Key is read from VITE_VAPI_API_KEY env var — never inlined as a string literal

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

  return res.json()
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

  return res.json()
}
