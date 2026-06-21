# AGENTS.md

## Cursor Cloud specific instructions

This section captures durable, non-obvious setup/run caveats for the QorTroller / V.A.P.I.
monorepo discovered while standing up the dev environment. Standard commands live in
`README.md`, `Makefile`, and the `## Build & Test Commands` section of `CLAUDE.md` — refer
to those rather than duplicating. The dependency-refresh (pip/npm/rust/submodule) runs
automatically via the Cloud Agent update script; the notes below are the things that are
NOT obvious and bite you at run time.

### Services & ports
- **Bridge** (core product, Python/asyncio + FastAPI): `python -m bridge.vapi_bridge.main`
  from the repo root → serves on `http://0.0.0.0:8080` (HTTP + WebSocket).
- **Frontend** (Vite + React dashboard): `cd frontend && npm run dev` → `http://localhost:5173`.
  Vite binds IPv6 `localhost` (`::1`), not `127.0.0.1`; use `http://localhost:5173` in a
  browser. Its proxy forwards `/api`, `/bridge`, `/operator`, `/health`, `/ws`, etc. to the
  bridge at `127.0.0.1:8080`, so the bridge must be running for the dashboard to show live data.
- The `python` alias is provided by the `python-is-python3` apt package (installed during
  setup, not by the update script). If `python` is ever missing on a fresh pod, use `python3`
  — they are the same 3.12 interpreter.

### Bridge `.env` is required and the shipped `.env.example` has startup-breaking placeholders
`bridge/.env` is git-ignored, so it must be (re)created from `bridge/.env.example` before the
bridge will start. The example ships placeholders that crash startup — fix these four things:
- `DB_PATH=` (empty) → **must be a real path** (e.g. `DB_PATH=$HOME/.vapi/bridge.db`). An empty
  value is passed verbatim to `sqlite3.connect("")`, which gives each connection its own private
  temp DB, so tables vanish between connections → `sqlite3.OperationalError: no such table: schema_versions`.
- `BRIDGE_PRIVATE_KEY=0x...` → replace with a valid 0x + 64-hex key. A throwaway dev key is fine
  (no chain writes happen with `CHAIN_SUBMISSION_PAUSED` / `AGENT_DRY_RUN` defaults and empty
  contract paths): `BRIDGE_PRIVATE_KEY=0x$(python -c "import os;print(os.urandom(32).hex())")`.
- `POAC_VERIFIER_ADDRESS=0x...` → **required and must be a valid checksummed address**
  (`config.validate()` rejects empty). Use the real deployed testnet address from
  `contracts/deployed-addresses.json` (`PoACVerifier = 0x26178AD95DB507f0D298fAAFC19752fC86166c6C`).
  The other `*_ADDRESS=0x...` placeholders should be set to real addresses or left blank.
- For headless (no controller, no broker): set `MQTT_ENABLED=false`, `DUALSHOCK_ENABLED=false`,
  `AUTO_DETECT_DEVICE=false`. Set `OPERATOR_API_KEY` to a random hex and mirror the same value as
  `VITE_VAPI_API_KEY` in `frontend/.env.local` (gates all `/operator/*` endpoints).

### Invariant gate needs the firmware submodule
`python scripts/vapi_invariant_gate.py` fails `INV-FIRMWARE-001/002` ("FILE NOT FOUND
bridge/firmware/joypad-os/...") unless the submodule is initialized:
`git submodule update --init bridge/firmware/joypad-os` (the update script does this; CI does too).

### Running tests
- **Bridge tests import `vapi_bridge` directly.** Run the whole suite as
  `python -m pytest bridge/tests/` from the repo root (works), or `cd bridge && python -m pytest`.
  Running a *single* file by path from the repo root fails with `ModuleNotFoundError: vapi_bridge`
  — for individual files prefix with `PYTHONPATH=bridge`.
- **SDK** (`python -m pytest sdk/tests/`): ~595 functional tests pass; ~21 `test_sdk_version_is_phaseNNN`
  tests fail. These are pre-existing version-string drift (SDK_VERSION moved to `3.1.1-…`, tests
  pin old `3.0.0-phaseNNN`) — environment-independent, not a setup problem.
- **Contracts**: `cd contracts && npx hardhat compile && npx hardhat test` (781 passing). `npx hardhat
  compile` rewrites tracked files under `contracts/artifacts/` and `contracts/cache/`; do NOT commit
  that build noise.
- The bridge's FleetSignalCoherenceAgent appends to the tracked file `wiki/contradictions.md` at
  runtime while the bridge is running — revert that runtime churn before committing.

### PoAC HTTP ingestion (core data-plane hello-world)
`POST /api/v1/records` expects a raw 228-byte PoAC record (164-byte body + 64-byte ECDSA-P256
sig). For an HTTP genesis record (`prev_poac_hash = 32×0x00`) the bridge resolves the signing
pubkey by scanning registered devices and, for genesis, uses the first device with a known
pubkey. With multiple registered devices the genesis fallback picks the wrong key and
verification 400s (production sends the device_id in the uplink header). For a clean
single-device demo, start from a fresh DB (`rm ~/.vapi/bridge.db*`) and register exactly one
device before submitting.
