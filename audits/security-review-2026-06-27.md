# QorTroller Repository Security Review — 2026-06-27

Branch: `claude/repo-vulnerability-analysis-wvwmow`

Scope: full-repo vulnerability analysis across the Python bridge HTTP service, the
Solidity contract set, the React frontend, committed secrets, and dangerous sinks
(injection, traversal, SSRF, deserialization). Findings are split into **FIXED in
this branch** (safe, code-level changes with no on-chain / redeploy impact) and
**REPORTED for operator action** (deployed/FROZEN contracts and governance items
that require review + redeployment, which are out of the safe-change envelope for an
automated audit branch).

---

## 1. FIXED in this branch

### 1.1 CRITICAL — Hardcoded live API key in a public repo (leaked credential)
The QuickSilver LLM API key `sk-el_TumeRtoQdi-lY-YQmTQ` was hardcoded as a fallback in
two committed files of a **public** repository:

- `bridge/vapi_bridge/vapi_llm_client.py:19` — used directly as a `Bearer` token.
- `frontend/src/views/LlmChatView.jsx:94` — baked into the browser bundle and sent
  on a direct `fetch()` to `api.quicksilverpro.io` from every client.

**Fix applied:** removed both hardcoded fallbacks; the code now fails closed when the
env var (`QUICKSILVER_API_KEY` / `VITE_QUICKSILVER_API_KEY`) is unset. The key is no
longer present anywhere in the working tree (`git grep` clean).

**OPERATOR ACTION STILL REQUIRED (cannot be done from code):**
1. **Rotate/revoke the key at QuickSilver now** — it has been public and must be
   treated as compromised regardless of removal.
2. The key remains in **git history** (introduced in commit `7991e11`). Purging it
   requires a history rewrite + force-push to a public repo, which is on the project's
   "NEVER without explicit operator request" list — left for an explicit operator
   decision. Rotation (step 1) is the load-bearing mitigation; history purge is
   secondary cleanup.
3. Architectural follow-up: the frontend should never hold a provider key. Proxy LLM
   calls through the bridge so the secret stays server-side.

### 1.2 HIGH — Empty-key auth bypass + timing oracle on a mutating endpoint
`bridge/vapi_bridge/operator_api/agent_operator_initiative.py` —
`POST /operator/evaluate-agent-action` used `if api_key != cfg.operator_api_key`. With
the default empty `OPERATOR_API_KEY`, an empty `api_key` satisfied `"" != ""` → False →
auth passed, on an endpoint that runs Cedar evaluation and writes a `shadow_log` row.
The plain `!=` was also a per-byte timing oracle.

**Fix applied:** fail closed with 503 when no key is configured, and compare with
`hmac.compare_digest`, matching the `_check_key` pattern used elsewhere.

### 1.3 MEDIUM — Timing-unsafe key comparison on main-app operator endpoints
`bridge/vapi_bridge/transports/http.py` — five sites (`PATCH /config`,
`POST /operator/passport`, `POST /operator/passport/issue`, and two others) used plain
`!=` for key comparison. They already fail closed on the unconfigured case (no bypass),
but the comparison leaked timing.

**Fix applied:** all five now use `hmac.compare_digest` (added `import hmac`).

### 1.4 MEDIUM — Path-traversal via `startswith` prefix bug (auth-gated)
`bridge/vapi_bridge/operator_api/agent_misc.py` — the `read_file` tool of
`POST /agent/local-host/execute` confined paths with
`safe_path.startswith(normpath(repo_root))`. A bare prefix test admits sibling
directories whose name extends the repo root (e.g. `../QorTroller-secret/...` resolves
outside the repo but still starts with `/home/user/QorTroller`).

**Fix applied:** containment now uses `os.path.commonpath([safe_path, repo_root])`.
Verified against in-repo paths (allowed), `../../../passwd` and `/etc/passwd` (blocked,
existing test still passes), and the sibling-prefix case (now blocked).

**Verification:** edited modules syntax-check clean; `test_local_host_tools_endpoint.py`
passes 5/6 (the 1 failure — `read_file` of `cli_chat.py` — is a pre-existing
checkout/fixture issue that fails identically on the original code, unrelated to these
changes); `test_operator_initiative_o3_expedite.py` and `_post_o3.py` pass.

---

## 2. REPORTED for operator action (not edited here)

### 2.1 Bridge — read-key fails open when `OPERATOR_API_KEY` is unset (MEDIUM)
`operator_api/_app.py` `_check_read_key` enforces auth only when a key is configured;
the default is empty, so a forgotten env var silently exposes all read-only `/agent/*`
and `/bridge/*` status endpoints. This is documented as intentional dev behavior, so it
is left as-is. **Recommendation:** add a startup assertion/warning that
`operator_api_key` is non-empty when HTTP is enabled, or gate unauthenticated reads
behind an explicit `ALLOW_UNAUTH_READS=1` opt-in.

### 2.2 Bridge — unvalidated `output_dir` write on `POST /operator/vpm-compile` (LOW)
`operator_api/agent_zkba_vpm.py` passes a body-supplied `output_dir` to the compiler
unconstrained. Requires the full operator write key (properly `compare_digest`-checked),
so it is a privileged-operator-only primitive. **Recommendation:** constrain `output_dir`
to a fixed artifacts root.

### 2.3 Solidity contracts (deployed/FROZEN — require review + redeploy)
These are real findings but the contracts are deployed on-chain and pinned by PV-CI
invariants; fixing them safely needs operator review, redeployment, and (where relevant)
a trusted-setup ceremony. **Do not patch the live bytecode from an audit branch.**

- **H-1 `VAPIQuickSilverCollateral.claimExcessYield()`** (`:147-164`) — computes
  "excess" as `balanceOf(this) − caller.lockedAmount`, i.e. the whole-contract balance
  minus only the caller's lock. In a multi-operator deployment one operator can withdraw
  collateral backing other operators. **Fix:** track `totalLocked`; only
  `balanceOf(this) − totalLocked` is claimable, distributed pro-rata.
- **H-2 `BountyMarket.aggregateSwarmReport()`** (`:691-765`) — no access modifier; loops
  `deviceRegistry.updateReputation(...)` (BountyMarket is an authorized updater) and emits
  a `PhysicalOracleReport` consensus event. Anyone can inflate any device's corroboration
  reputation and emit an attacker-chosen "verified" oracle feed. **Fix:** gate the
  function and require each record be unused evidence already bound to the bounty; de-dup
  record hashes.
- **H-3 `VAPIGovernanceTimelock`** (`:201-216`) — `setCoSigner` / `transferOperator` are
  `onlyOperator` and **not** timelocked, defeating the contract's stated purpose: a stolen
  operator key can replace the co-signer instantly, then push a malicious operator
  transition the real co-signer can no longer veto. **Fix:** subject both to the same 48h
  queue, or require the co-signer's signature to change the co-signer.
- **H-4 `PoACVerifier.verifyPoAC`** (`:200-434`) — the signed digest is
  `sha256(body)` with no `chainid` / `address(this)` / caller binding, and verification is
  permissionless, so a captured `(deviceId, body, sig)` replays across forks/redeploys and
  contexts. **Fix (respecting the FROZEN 228-byte wire format):** bind context at the
  on-chain digest — `sha256(body || chainid || address(this))` with matching firmware —
  and/or require `msg.sender` == device owner. EIP-712-style domain separation.
- **M-1 `TieredDeviceRegistry._validateAttestationV2`** (`:324`) — manufacturer signature
  over `keccak256(_pubkey)` with no domain separation; once `attestationEnforced=true`, a
  single observed signed pair is replayable to claim Attested tier. **Fix:** sign over
  `keccak256(abi.encode(block.chainid, address(this), _manufacturer, _pubkey))`.
- **M-2 `ZKSepProofVerifier.verifyAndCheckSnapshot`** (`:111-142`) — proof not bound to
  `msg.sender`/claimer; replayable if any downstream consumer treats a `true` return as
  authorization for `claimedPlayerId`. **Fix:** bind claimer into circuit public inputs +
  per-proof used-marker; range-check the 128-bit hash halves.
- **Low/Info:** unchecked ERC20 return values in `VAPIOperatorRegistry.slash()` and
  `VAPIHardwareCertRegistry.certifyHardware` (use `SafeERC20`); single-step operator
  transfers in several registries (use 2-step); verify upgradeable NFT proxies
  (`VAPIGamerControllerNFT`, `VAPIOperatorAgentNFT`) are not left uninitialized.

---

## 3. Confirmed clean

- **SQL injection** — the `store/` layer is parameterized throughout; the handful of
  f-string SQL fragments use a static allowlist or `?,?` placeholders generated from list
  length with bound tuples. No injection.
- **Command injection** — no `os.system`; the only HTTP-reachable `subprocess` calls use
  argument lists (no shell) with hardcoded commands. The daemon's `execute_shell` LLM tool
  is defended by a metacharacter ban + prefix whitelist + sealed env (`get_sealed_env`) and
  is reachable only via the agent loop, not anonymous HTTP.
- **Insecure deserialization** — no `pickle`, `marshal`, unsafe `yaml.load`, `eval`, or
  `exec` on request/external data anywhere.
- **SSRF** — no HTTP endpoint fetches a user-controlled URL host.
- **CORS** — the public forensic sub-app uses `allow_origins=["*"]` with
  `allow_credentials=False` (correct for read-only public data); the main app restricts
  origins to localhost + a configurable `FRONTEND_ORIGIN`.
- **Other committed-secret candidates** — `.env.example` files are placeholders; the
  `vsd-vault` attestation JSON holds only a public key + public wallet address; AWS keys in
  tests are obvious fixtures (`AKIATESTTESTTESTTEST`); `0x…` wallet addresses are public.
  No PEM private keys, mnemonics, Pinata JWTs, or Anthropic keys committed.
