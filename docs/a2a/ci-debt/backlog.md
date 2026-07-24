# LANE CI-DEBT — backlog

D-OPS-2 (Option A) disposition record. PR #94's CI Matrix carried a 134-test
backlog that had never been visible before — pytest was dying at collection
time (`Interrupted: N errors during collection`) on every prior run, so the
execution phase never started. Fixing the collection blockers didn't
introduce this backlog; it revealed it. 96 of the 134 are confirmed
pre-existing on `main` too (exact test-ID cross-reference, see
`docs/a2a/l2c-velocity-blowup-investigation/` sibling investigations for the
methodology this branch used throughout).

This file tracks what's left after D-OPS-2's fix/mark/skip pass: 8 fixed in
the PR (stale invariant counts, one unregistered crypto tag family, two
`operator_api.py` path references), 44+9+4+2+3+1+1 = 64 marked
`skip`/`skipif` with a stated reason, 5 marked `xfail(strict=False)`. What
remains untouched, listed here by name — no bulk "investigate everything"
task, just a record of what's known and what isn't.

**Update, second pass (`fix/ci-debt-backlog`, post-merge, operator-directed
"close backlog items rather than open new PRs on top of it"):** closed 6
more items with real, individually-verified root causes rather than guessed
dispositions — coherence rule count drift (3, same class as the original
Cat 2 fixes), the Cedar bundle CWD-sensitivity leak (3, root-caused to 5
files' unrestored `os.chdir()`; first fix attempt was wrong and is recorded
as such below the fix commit, not silently corrected), the ioID
web3/eth_account MagicMock-poisoning cluster (15, same leak class, second
instance), two genuine production copy-paste bugs on real operator API
endpoints (2, not test artifacts — see the dedicated section below), and
the MQTT transport topic-shape mismatch (3, also took two rounds to
diagnose correctly). `test_batcher_recovery.py`'s 2 failures turned out to
be the already-documented CLAUDE.md flake F-DECON2-5, marked
`xfail(strict=False)` with that citation rather than re-litigated.
`test_chain_reconciler.py` was investigated and is recorded below as a real,
deeper finding — not fixed, not guessed at.

**Update, third pass (`fix/ci-debt-backlog`, same branch, continued
operator-directed close-out):** closed 8 more items — a one-test gap in the
touchpad_filter skip-marker rollout (1, `test_phase140_probe_comparison.py`
was the only sibling of 24 similarly-marked tests across 9 files that never
got the marker), a Phase 195 protocol-maturity-scoring rebalance the tests
never caught up to (2, `test_phase191_tsp.py`), a missing `sys.path` insert
plus an uninitialized test-double attribute (2, `test_retina_adaptive_lag.py`),
a MagicMock-truthiness trap on a newer config flag mirroring an existing
guard two lines above it (1, `test_fix_d_feedback_timeout.py`), the same
`CONTRADICTION_RULES` count drift as the second pass's coherence-rule fix
but independently pinned in a second file (1, `test_cfss_drift_sweeper_integration.py`),
and a test that predates a later, deliberate dry-run-aware guard in
`Config.validate()` (1, `test_chain_keystore.py` — not previously in this
backlog at all, surfaced only by a full-suite re-run). `test_qortroller_cli.py`
and `test_qortroller_retina_capture.py` were investigated, found to pass
both standalone and under a real full-suite run, and are removed from the
list below with no code change (order-dependence suspected, apparently
already resolved as a side effect of an earlier fix in this pass; not
chased further since there was nothing left to reproduce). `test_uvc_source.py`
was investigated — no fragile/version-sensitive assertions found on
inspection, still not reproducible locally — and is left as-is alongside
`test_dag_r07_forge.py` in the same "genuinely can't verify without the CI
environment" category. `test_vsd_harness.py` was investigated in depth and
is recorded in its own new section below as a real, unresolved cryptographic-
provenance finding — not a test bug, not fixed.

**The ioID cluster (previously "not confirmed... consistent with a
mock-setup gap") required two rounds to actually close, and the first round's
own verification claim was wrong** — see the rewritten section below for the
full account, kept deliberately un-sanitized because the failure mode (a
commit message claiming "full-suite collection clean" without having actually
run the full suite) is exactly the kind of thing this backlog exists to catch.

## Named separately, not part of this backlog (operator instruction)

**`bridge/tests/test_verify_provenance_dag.py::test_real_m17_index_verifies_cold`**
— sha256 mismatches against three sealed session artifacts
(`audits/posp_record_match17_rp_fixb3_2026-07-08.json`,
`audits/tri_plane_manifest_match17_2026-07-11.json`, `wmp_corpus_real/wmp_corpus.jsonl`)
plus a device-id-stability failure, reported via a real subprocess call into
the DAG verification script. This is a content-integrity check sitting
directly on top of the project's provenance thesis, not an environment
artifact — confirmed by reading the test (`bridge/tests/test_verify_provenance_dag.py`),
it invokes real verification logic against real sealed files, not a mock.
Fails identically on `main` and this branch (both trees carry the same
sealed artifacts). Does not get bundled into the general backlog below —
the operator sees it here, by name, and decides when/how it gets
investigated.

**`bridge/tests/test_mythos_full_variants.py::test_t_mythos_methodology_1_healthy_repo_zero_findings`**
(found during the second pass, 2026-07-24) — the Mythos methodology-drift
scanner correctly reports `wiki/assessments/VAPI Bluetooth Calibration_
Architectural Prerequisites and Threat Model Analysis.pdf` as MISSING. This
is not a test bug or CI artifact: that file is named `[CANONICAL]` in
CLAUDE.md's own "BT Calibration: Canonical Prerequisite Anchor" section —
"Any BT-related design work in VAPI must read [this file]... before
producing architectural proposals" — and it does not exist anywhere in this
repository, tracked or otherwise (confirmed via `git ls-files` and a direct
filesystem check in a fresh worktree; genuinely absent, not just
uncommitted-locally like `touchpad_filter.py` or `cli_chat.py`). Its sibling
canonical document (`DualSense Edge Sensor-Stack Characterization for VAPI
Track-1...pdf`) IS present and tracked, so this looks like an isolated gap,
not a systemic one. Not marked skip/xfail -- the scanner is correctly
detecting a real gap between a stated hard rule and repo contents; masking
that would hide the finding rather than resolve it. Same disposition as the
DAG test above: named here, not bundled into the general backlog, operator
decides whether the document gets sourced and committed or the CLAUDE.md
anchor claim gets amended.

**`bridge/tests/test_daemon_health_monitor.py::test_detect_firmware_drift_on_live_repo`**
(found during the second pass, 2026-07-24) — the most security-relevant
finding in this pass. The test asserts `detect_device_id_firmware_drift(REPO_ROOT)
is False`, with its own comment claiming "F-FW-2-DRIFT seam CLOSED: atca_signer.c
was rewritten to keccak256(65B SEC1 pubkey) per DEVICE_ID_CANON_v1 / F-KEY-1
(no on-chip serial concat, no legacy SHA-256(pubkey||serial) formula)". The
live check returns `True` (drift detected) instead. Traced to the actual
firmware source, not a stale-comment false positive: `bridge/firmware/
joypad-os/src/qortroller/atca_signer.c`'s `_compute_device_id()` (lines
92-110) is real, live firmware code that genuinely still computes
`SHA-256(pubkey[64B] || serial[9B])` via the ATECC chip's on-chip SHA engine
(`atcab_sha(...)`) — the exact superseded formula the test's comment claims
was removed. Checked whether the submodule pointer is simply stale before
concluding this: `git log HEAD..origin/main` and `HEAD..origin/HEAD` inside
the `joypad-os` submodule both return empty — the currently-pinned commit
(`40d24274`) is already at that repo's own upstream tip. This is not a
stale-pointer problem; the claimed firmware rewrite does not appear to
have been implemented in the firmware repository at all, despite being
documented as done. Not touched: rewriting cryptographic device-identity
firmware C code is well outside safe, mechanical CI-debt scope, and the
`joypad-os` submodule is a separate repository (`ConWan30/joypad-os`) I
have no standing authorization to push changes to. Named here for the
operator's direct attention, not bundled into the general backlog or
marked skip -- an assertion that a security-relevant firmware rewrite
landed, when it apparently didn't, is exactly the kind of gap that
shouldn't get quietly suppressed by loosening the test.

**`bridge/tests/test_vsd_harness.py::test_seeded_vault_passes_if_present`**
(found during the third pass, 2026-07-24) — a genuine cryptographic-provenance
finding in the VSD (Verified Synthesis Discipline) content vault, not a code
bug. The harness reports a HIGH-severity `VSD-2` finding on
`vsd-vault/notes/claim/c-cert-scope-is-regime-label.md`: "note bytes changed
since signing (canonical hash mismatch)". Traced to root cause via direct
execution of `vsd_provenance.verify_note()`, not just the test's own error
string: `note_canonical_hash()` is `SHA-256(Path(note_path).read_bytes())` —
raw bytes, no line-ending normalization by design (`vsd-vault/.vsd/vsd_provenance.py:45-47`).
A repo-root `.gitattributes` rule (`vsd-vault/notes/**/*.md text eol=crlf`)
exists specifically to make this deterministic across platforms — its own
comment names an identical prior incident ("this is what stranded cycle
49 before 2026-06-28"). Scanned every tracked note against its manifest
(73 notes checked): **12 fail, all and only the cycle-57 batch** (commit
`c212708f`, "land cycle 57 — dev-cert investigation synthesis" — 9 claim +
2 ingredient + 1 synthesis, exactly matching that commit's own stated
composition); the other 61 notes verify cleanly. This means the `.gitattributes`
mitigation did not fully protect cycle 57's signing pass specifically —
its 12 manifests were apparently signed against bytes that don't match any
reproducible checkout of the current git blobs under the documented policy.
**Not fixed, not fixable by this pass:** VSD-2 exists specifically to detect
this class of drift via Ed25519 signature over the architect key
(`vsd-vault/manifests/notes/*/*.manifest.json`), and the project's own stated
discipline is that "the loop never forges the architect signature" — I have
no access to that key and would not use it here even if I did. The correct
remediation is almost certainly re-running the VSD synthesizer's signing
step for these 12 notes specifically (an architect/operator action), not a
test change. Left honestly red rather than loosened, skipped, or worked
around — same posture as `test_chain_reconciler.py` and
`test_daemon_health_monitor.py` above.

## Reclassified during D-OPS-2 (was going to be marked "missing artifact",
## turned out to need real investigation instead)

**Cedar bundle cluster (3 tests, `bridge/tests/test_phase_o1_c2_shadow_runtime.py`):**
`TestEvaluatorForbidPath::test_sentry_git_push_forbidden`,
`TestEvaluatorMerkleRecomputed::test_merkle_root_matches_bundle_file`,
`TestEvaluatorPermitPath::test_sentry_read_wiki_permits`.

Originally assumed to be Cat 1 (missing Cedar bundle JSON, mark and skip).
That assumption was wrong: `bridge/vapi_bridge/cedar_bundles/anchor_sentry_o1_shadow_v1.json`
and its siblings are tracked in git (`git ls-files` confirms) and present in
this working tree. The test constructs its path as
`Path(cfg.cedar_bundle_dir) / "anchor_sentry_o1_shadow_v1.json"` where
`cedar_bundle_dir = "bridge/vapi_bridge/cedar_bundles"` — a bare relative
string, not anchored via `Path(__file__).parents[...]` the way most of this
suite's file-path construction is. Working hypothesis, not confirmed: some
earlier-collected test in the full-suite run changes the process's CWD
(`os.chdir`) without restoring it, and this test — unlike the majority of
the suite — is one of the few that doesn't defend against that. This is the
same *class* of bug as the `sys.modules` sdk-stub leak fixed earlier on this
branch (an earlier test's side effect surviving into a later test's
collection/execution), just a different mechanism (CWD vs. `sys.modules`).
Plausibly a cheap, mechanical fix once someone bisects which test moves the
CWD — flagging it as such rather than leaving it looking like a generic
"missing file" skip.

## Everything else — untriaged, deferred post-merge

Grouped by apparent shared cause where the failure text suggests one,
without confirming any of these by direct investigation:

**ioID ceremony test cluster (14 tests, `test_controller_ioid_registration.py`)
+ 2 related (`test_controller_ceremony.py::test_transfer_topic0_is_canonical_erc721`,
`test_operator_session_register_agents.py` x2) — RESOLVED, but took two
rounds; round 1's own verification claim was wrong, recorded here rather
than quietly corrected:**

All 17 failed with `MagicMock`-shaped errors (`TypeError: fromhex() argument
must be str, not MagicMock`, `TypeError: Object of type MagicMock is not
JSON serializable`) — not a logic bug in the ceremony code (this
functionality is live and working on-chain per CLAUDE.md's ioID ceremony
NOTE), but a test-isolation leak: dozens of other files in this suite stub
`web3`/`eth_account` for their own speed/isolation with no cleanup, and
whichever gets collected first poisons every later import in the same
pytest process.

Round 1 (commit `2f8bb8c7`) added a guard —
`if isinstance(sys.modules.get(name), MagicMock): del sys.modules[name]`
for `"web3"`/`"eth_account"` — verified against one specific known-poisoning
file and claimed in its own commit message "Full-suite collection clean
(6352 tests)." **That claim was false.** A subsequent real full-suite run
(same session) showed all 15 originally-targeted tests still failing with
identical signatures, plus the 2 in `test_operator_session_register_agents.py`
(same error class, never even targeted by that commit).

Root cause of why round 1 was too narrow, confirmed by direct reproduction
of both mechanisms rather than guessed:
1. At least 17 files stub the web3 tree with a genuine `types.ModuleType("web3")`
   instance plus a hand-rolled stub class bolted onto its `.Web3` attribute
   (`test_phase224.py:31-42` is one) — not a `MagicMock` instance, so
   `isinstance(..., MagicMock)` never catches it.
2. At least 38 files poison individual dotted submodules directly
   (`web3.exceptions`, `web3.middleware`, `eth_account.messages`, ...).
   Deleting only the two bare top-level keys doesn't touch these —
   `web3/__init__.py`'s own `from web3.main import Web3` finds the stale
   cached submodule and reuses it instead of re-executing fresh.
3. The production modules themselves (`vapi_bridge.controller_ioid_registration`,
   `bridge.scripts.operator_session_register_agents`) do `from web3 import
   Web3` / `from eth_account import Account` at their own module level. If
   already imported by an earlier-collected file while poisoned, their
   cached bindings stay poisoned regardless of how clean `sys.modules["web3"]`
   is by the time a later test file's guard runs.

Round 2 (commit `2545a1f8`) purges every `sys.modules` key that *is or
starts with* `"web3."`/`"eth_account."` (the whole namespace tree, not two
exact keys) plus force-refreshes the specific production modules each test
file depends on. Verified by reproducing the exact round-1-defeating
mechanism directly (confirmed the old guard fails against it, confirmed the
new one fixes it), then running all three files standalone (62+47 passed)
and in combination after five different known-poisoning files collected
first (129 passed).

**Full-suite confirmation, done properly this time (learning applied from
round 1's mistake):** a fresh, isolated-worktree full-suite run (submodule
initialized, Hardhat artifacts compiled — the two environment gaps that
produced 5 misleading results in an earlier pass of this same
verification, all traced to worktree setup and none to the code, see the
submodule-masking pattern section below) confirmed **all 17 targeted tests
pass** with **zero regressions** (nothing that was passing is now failing)
and **zero new failures** beyond the already-documented pre-existing set.
A second, fully-clean pass (both environment gaps closed from the start)
was launched to produce a single authoritative tally rather than the
reconciled-from-two-partial-runs arithmetic above — **run in progress as
of this commit; this paragraph will be updated with the final numbers and
a link to the run artifacts once it completes.** Not blocking this PR's
open — the per-test evidence above is already solid confirmation of the
fix itself; this last run is about getting one clean authoritative number
for the record, not about doubting the fix.

**Endpoint 500-vs-200 pair:** `test_phase129_separation_breakthrough.py::test_7_endpoint_5_keys`,
`test_phase134_separation_ratio_strategies.py::test_8_auto_snapshot_status_5_keys`
— both hit `assert 500 == 200` against `/agent/*` endpoints. Same symptom,
possibly same root cause across both tests; not investigated further.

**MQTT transport (3 tests, `test_mqtt_transport.py`):** callback invocation
counts assert 0 where 1/5 expected — looks like a wiring/subscription setup
issue, not investigated.

**Coherence rule count drift — RESOLVED (2nd + 3rd pass):**
`test_coherence_rule_loader.py` (3 tests: 41→43, 28→30, 42→44, second pass)
and, independently, `test_cfss_drift_sweeper_integration.py::test_t_cfss_int_10_total_rule_count`
(28→30, third pass — a second, separate file pinning the same
`CONTRADICTION_RULES` count, found only by a full-suite re-run since it
wasn't part of the original per-file breakdown). Both are exactly the
`FSCA CONTRADICTION_RULES==28` flake CLAUDE.md's "green-main gate reconcile"
note already named as pre-existing — confirmed the same one, not a
different assertion. Live count checked directly against production
(`len(fleet_signal_coherence_agent.CONTRADICTION_RULES)`) before bumping
either file, and cross-checked against the other three files that already
correctly assert 30 (`test_phase204_ioswarm_contradiction.py`,
`test_phase_238_curator_fsca_rules.py`, `test_retina_fsca_cross_oracle.py`) —
no fourth stale copy found.

**Named individually per LANE OPS r-next priority, confirmed pre-existing on
both `main` and branch (not investigated further in this PR):**
`test_phase67_ceremony_hardening.py::TestCeremonyChainIntegration::test_17_record_ceremony_missing_address_raises_runtime_error`
(a fail-closed guard not raising — security-relevant, flagged as
higher-priority than the rest of this list by the reviewing party),
`test_phase54_hardening.py::TestSendRawTxNonceReset::test_send_raw_tx_resets_nonce_on_send_failure`
(nonce-reset-on-failure not firing).

**`test_chain_reconciler.py` (2) — investigated, not fixed, real finding:**
`test_last_block_advances_after_cycle` and `test_reconcile_marks_matched_tx_confirmed`
both show `RuntimeWarning: coroutine '_make_chain_mock.<locals>._bn' was never
awaited`. Traced past the obvious suspect: `ChainReconciler._reconcile_cycle()`
does correctly `await self._chain._w3.eth.block_number` at the direct-call
site (chain_reconciler.py:171) -- but `_get_governor()` (chain_reconciler.py:46)
lazily constructs a REAL `ChainReadGovernor` (TTL cache + semaphore +
`asyncio.wait_for` timeout, with Windows-ProactorEventLoop-specific
cancellation workarounds from the STAGE-9/11/12 hardening arc) whenever no
governor is explicitly injected -- which is exactly what these tests do,
since `ChainReconciler(self.store, chain, poll_interval=999.0)` never passes
one. The test's mock (`chain._w3.eth.block_number = _bn()`, a one-shot
coroutine object -- its own comment already flags this as fragile) only
covers the direct-call fallback path, not the governor's internals, which
are the more likely place a coroutine gets abandoned mid-`wait_for`. Not
fixed here: this is real, carefully-hardened async/Windows-event-loop
production code (three prior hardening stages, per the file's own history),
not a quick copy-paste bug, and does not belong under merge-pressure
guessing. Likely correct fix direction: inject an explicit no-op/mock
governor into these tests rather than relying on the lazy-construction
fallback path -- not attempted, would need its own verification pass.

**Remaining individual items, no shared pattern identified — everything
else in this list was resolved across the second and third passes (see
above) or moved to its own dedicated section (`test_vsd_harness.py`, above).
What's left, genuinely unresolved:**
`test_dag_r07_forge.py` (3 — investigated: passes standalone and in every
locally-reproducible broad-context combination tried, including running
after files known to leave process-global side effects; could not
reproduce the CI failure on this Windows dev machine, plausibly a genuine
Windows-vs-Linux difference, same caveat class as the HID/XInput cluster
but not confirmed with the same certainty; third pass additionally traced
this to the same CRLF-checkout-vs-committed-blob mechanism found
independently in the VSD vault finding above and in
`test_vbdip_0006_conformance_generator.py` — a Windows-local-only artifact,
not a real Linux-CI regression, but still not something to silently
"fix" by changing hash comparisons without operator sign-off), `test_uvc_source.py`
(2 — synthetic-frame optical-flow processing test; third pass checked for
fragile/version-sensitive numeric assertions specifically and found none
(no `pytest.approx`, no float-magnitude comparisons — only type/count/shape
checks), which argues somewhat against the cv2-version-drift theory without
disproving it; still not reproducible locally, still ambiguous, left as-is).

## Methodology note

This entire backlog was measured by running the identical fixed-collection
suite against both `main` (4cddcc03) and this branch (fa512345) and
cross-referencing by exact test ID — 96 of 134 branch failures reproduce on
`main` byte-for-byte. The `main` measurement ran locally on Windows, not
through GitHub Actions CI (Linux) — a real methodology gap, disclosed at the
time. Some of the "branch-only" results in the original cross-reference are
plausibly Windows-vs-Linux artifacts (confirmed for the HID/XInput cluster
specifically: `ctypes` has no `windll` attribute on Linux at all, so that
cluster's Windows-only skip in this PR is evidence-backed, not guessed) —
that class of doubt does not apply to this backlog file, since everything
listed here already failed in real Linux CI on the branch itself.

## Pattern worth naming: recurring test-isolation hygiene gap

Three independent instances of the same bug *class* surfaced during this
D-OPS-2 pass, found only because CI collection was broken for long enough
that someone had to actually look at the full suite instead of trusting a
green check:

1. **`sys.modules` leak** — seven `test_phase7{3,5,6,8,9}*`/`test_phase8{0,1}*.py`
   files install a fake `sdk` module into the process-global `sys.modules`
   via `setdefault()` with no cleanup, permanently shadowing the real `sdk`
   namespace package for every test collected afterward in the same pytest
   run. Fixed in this PR (commit `8be81278`).
2. **CWD-sensitivity** — `test_phase_o1_c2_shadow_runtime.py`'s Cedar bundle
   tests construct a bare relative path (`Path(cfg.cedar_bundle_dir) / "..."`,
   not anchored via `Path(__file__).parents[...]`); working hypothesis is an
   earlier-collected test changes the process's CWD without restoring it.
   Not fixed — reclassified into this backlog rather than mis-labeled
   "missing artifact."
3. **Suspected env/process state** — a ~51-test cluster centered on
   `test_mcp_audit_tool_wrappers.py` and a wide spread of "endpoint returns
   correct keys" tests fails only when the full 6338-test suite runs in one
   local process; each one passes individually or in a small combined
   sample. Windows-local-only — real CI's own full-suite run doesn't
   reproduce any of these 51. Not chased down; mechanism unconfirmed.

Three different mechanisms (`sys.modules`, CWD, something else entirely),
one shared shape: an earlier-collected test's side effect survives into a
later test's collection or execution because pytest runs the whole suite in
a single process and nothing resets the polluted state in between. Worth a
dedicated test-isolation sweep at some point — grep for `sys.path.insert`,
`os.chdir`, and other process-global mutations across `bridge/tests/` and
check each one is scoped/restored — rather than waiting for a fourth
instance to surface the hard way.

**The fourth instance did surface, the hard way, in the third pass** (the
ioID cluster's `sys.modules["web3"/"eth_account"]` leak, full account
above) — and it adds a second lesson on top of the first: a narrow fix
verified against one reproduction of a many-shaped bug can look correct and
still be wrong. Round 1 tested against exactly one poisoning file
(`test_phase157_fleet_consensus.py`) out of dozens that poison the same
namespace through at least two other mechanisms the guard's own condition
(`isinstance(..., MagicMock)` on two exact key names) structurally couldn't
see. The commit message's "full-suite collection clean" claim was true of
*collection* (imports didn't error) and false of *execution* (17 tests
still failed on assertions) — a distinction worth being explicit about in
any future fix's verification claim. The general shape: when a fix targets
"a test-isolation leak," verifying it against the *specific* file that
happened to reproduce the bug in your first repro is necessary but not
sufficient — the fix needs to be checked against the actual *class* of
poisoning (every mechanism, not just the first one found), or run against
real full-suite scale before the verification claim goes in a commit
message.

## Pattern worth naming, separately: empty/unpopulated submodule masking a
## real check (not a test-isolation leak — a different failure shape)

Surfaced during the round-2 ioID-fix full-suite re-verification (third
pass), flagged by LANE RWM r13 (claude-ai) as worth its own category rather
than folding into the pattern above, because the mechanism is genuinely
different: the four instances above are all *pollution surviving between
tests in one process*; this one is *absence silently reading as a pass*.

`bridge/firmware/joypad-os` is a git submodule. `git worktree add` — used
throughout this pass to isolate verification runs from concurrent edits in
the live tree — does not initialize submodules by default, so any freshly
created worktree starts with that directory empty (0 files) unless
`git submodule update --init` is run explicitly. `test_daemon_health_monitor.py::test_detect_firmware_drift_on_live_repo`
calls `detect_device_id_firmware_drift(REPO_ROOT)`, which reads
`bridge/firmware/joypad-os/src/qortroller/atca_signer.c`'s actual content
to check whether it still computes the superseded `SHA-256(pubkey||serial)`
device-id formula. Against an empty submodule directory, the detector has
no file to read and no drift to find — it reported `False` (no drift),
which looked identical to the check genuinely passing. Three other tests
in the same isolated-worktree run failed the *opposite* way on the same
root cause (`INV-FIRMWARE-001`/`002 FILE_NOT_FOUND` against the same
missing submodule files) — those failed loudly; this one passed silently,
which is the more dangerous half of the same gap. Confirmed by re-running
with the submodule properly initialized: the test goes back to failing
(correctly — the real firmware finding, documented in its own section
above, is genuinely still open, unrelated to this session's fixes), and
direct inspection of `atca_signer.c` at the submodule's pinned commit
confirms the old formula is unambiguously still there (`atcab_sha(sizeof(preimage), preimage, _device_id)`
over a `pubkey[64B] || serial[9B]` preimage — no partial/transitional
state, no `keccak`/`SEC1` reference anywhere in the file).

The general shape, worth grepping for specifically in a future audit: any
check whose pass/fail depends on reading real content from a path that
could be a submodule, a `.gitignore`'d generated artifact (the
`AgentRegistry.json` case earlier in this same verification pass — compiled
by a separate CI step, absent in a bare worktree, causing loud collection
failures rather than a silent pass, but the same underlying "verification
environment isn't fully populated" root cause), or any other conditionally-
present directory is at risk of *absence reading as success* rather than
*absence reading as an environment error*. The fix isn't code — it's
verification discipline: any full-suite or isolated-worktree run intended
to produce a trustworthy pass/fail tally needs `git submodule update --init
--recursive` and whatever compile/build steps CI runs before pytest (see
the Hardhat-ordering fix earlier in this pass) as a precondition, not an
afterthought — otherwise a clean-looking run can be quietly wrong in the
one direction (false pass) that's hardest to notice.
