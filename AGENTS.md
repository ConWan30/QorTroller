# AGENTS.md

Operating guidance for agents working in the QorTroller / V.A.P.I. monorepo.

The canonical, exhaustive project context lives in `CLAUDE.md` (architecture, phases,
FROZEN-v1 invariants, hard rules). Read it for protocol detail. Standard build/test
commands are in `README.md` (Quick start) and the root `Makefile`. This file only adds
durable, non-obvious operating notes.

## Cursor Cloud specific instructions

These notes are for cloud agents running on a VM where the startup update script has
already installed dependencies. They capture non-obvious caveats discovered during
environment setup; they are NOT a dependency-install guide.

### Services and how to run them (development mode)
- **Bridge** (core Python asyncio service, FastAPI/uvicorn) — `python -m bridge.vapi_bridge.main`
  from the repo root. Serves HTTP + WebSocket on `:8080`. This is the heart of the protocol
  (PoAC ingestion, 9-level anti-cheat stack, adjudication agents, GIC/WEC integrity chains).
- **Frontend dashboard** (React + Vite) — `npm run dev` in `frontend/` → `http://localhost:5173`.
  Proxies API calls to the bridge at `:8080`; falls back to mock data if the bridge is offline.
- **Contracts** (Hardhat) — `cd contracts && npx hardhat test` (781 tests, all pass). A local
  node (`npx hardhat node`, `:8545`) is only needed for the E2E suite (`make test-e2e`).
- The protocol's contracts are already live on IoTeX testnet (chain ID 4690); the bridge reads
  live on-chain state when configured but does not require a local chain.

### `python` vs `python3`
- The VM ships only `python3`. A `/usr/local/bin/python -> python3` symlink was created during
  setup (the `Makefile`, `README`, and docs all invoke `python`). If `python` is ever missing,
  recreate it: `ln -sf "$(command -v python3)" /usr/local/bin/python`.

### Bridge `.env` configuration traps (IMPORTANT — these crash startup if mis-set)
Copy `bridge/.env.example` to `bridge/.env`, then fix these (the shipped example values are
placeholders that break a fresh boot):
- `DB_PATH=` (empty) is FATAL. An empty value becomes `sqlite3.connect("")`, which opens a
  *private temporary database per connection*, so `schema_versions` vanishes between connections
  (`OperationalError: no such table: schema_versions`). Set an explicit path, e.g.
  `DB_PATH=/home/ubuntu/.vapi/bridge.db`. (A machine with no `DB_PATH` line at all is fine —
  the default kicks in only when the var is *absent*, not when it is set empty.)
- `BRIDGE_PRIVATE_KEY=0x...` and the `*_ADDRESS=0x...` placeholders are invalid hex and crash
  parsing. For headless dev, blank `BRIDGE_PRIVATE_KEY=` (the bridge then runs read-only / no
  on-chain writes — correct for dev).
- `POAC_VERIFIER_ADDRESS` is REQUIRED or the bridge exits with `Config error`. Use the deployed
  testnet address from `contracts/deployed-addresses.json` → `PoACVerifier`
  (`0x26178AD95DB507f0D298fAAFC19752fC86166c6C`).
- Set `MQTT_ENABLED=false` for headless dev (no MQTT broker on the VM). Leave `DUALSHOCK_ENABLED=false`
  (no physical controller).
- `OPERATOR_API_KEY` must equal `frontend/.env.local`'s `VITE_VAPI_API_KEY`, or `/operator/*`
  endpoints return 401/503. Generate one with `python -c "import os;print(os.urandom(16).hex())"`.

### Expected headless behavior (not errors)
- "hid library not available" / "Detected 0 controllers" — expected; no USB controller is attached.
- Submitted PoAC records land in `dead_letter` status: with no `BRIDGE_PRIVATE_KEY`, on-chain
  anchoring is skipped, so records are stored locally but not chain-submitted. The ingest →
  parse → adjudicate → store path still runs fully.
- `GET /api/v1/records/recent` raises a 500 (`UnicodeDecodeError`) for *unverified* records whose
  `device_id` is raw bytes (genesis records with an unregistered pubkey). This is a pre-existing
  code issue, not an environment problem; use `GET /api/v1/devices`, `GET /api/v1/stats`, or
  `GET /dashboard/snapshot` to read state instead.

### Quick end-to-end smoke test
With the bridge running: `POST /api/v1/records` with a 228-byte body returns `{"status":"accepted"}`
and `GET /api/v1/stats` shows `records_total`/`devices_active` incrementing. (The 228-byte wire
format = 164-byte body + 64-byte raw ECDSA-P256 r||s signature; see `bridge/vapi_bridge/codec.py`.)

### Tests / lint — pre-existing non-environment failures
- The full bridge pytest suite is very large (thousands of tests, hours). Use targeted modules
  during iteration, or `pytest -n auto` (pytest-xdist is installed). CI runs
  `pytest bridge/tests/ --ignore=bridge/tests/test_e2e_simulation.py -m "not hardware"`.
- ~21 SDK tests named `test_sdk_version_*` FAIL on a stale version-string pin (SDK is at
  `3.1.1-...` but old phase tests assert older strings). These are pre-existing, not env issues.
- Per `CLAUDE.md`, the GitHub full-matrix CI is RED on pre-existing failures (e.g. pytest running
  before `npx hardhat compile`); the protocol-integrity gates (invariant gate, mythos, path-scope)
  are the real bar. `python scripts/vapi_invariant_gate.py` must print `PASS — 179`.
- `ruff` is the Python linter (`make lint-py`); the repo has no ruff config, so it reports many
  pre-existing style findings — informational, not gating.
- `npx hardhat compile` rewrites tracked files under `contracts/artifacts/` and
  `contracts/cache/`; the running bridge appends to `wiki/contradictions.md`. Do not commit these
  runtime/generated changes.
