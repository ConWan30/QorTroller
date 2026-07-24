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
+ 1 related (`test_controller_ceremony.py::test_transfer_topic0_is_canonical_erc721`):**
all fail with `MagicMock`-shaped errors (`TypeError: fromhex() argument must
be str, not MagicMock`, `TypeError: Object of type MagicMock is not JSON
serializable`, etc.) — consistent with a mock-setup gap specific to a fresh
CI environment rather than a logic bug in the ceremony code itself (this
functionality is live and working on-chain per CLAUDE.md's ioID ceremony
NOTE), but not confirmed. These are also the tests that don't exist at all
on `main` (18 net-new test functions added on this branch) — new-feature
coverage, not a regression, but currently red in CI.

**Endpoint 500-vs-200 pair:** `test_phase129_separation_breakthrough.py::test_7_endpoint_5_keys`,
`test_phase134_separation_ratio_strategies.py::test_8_auto_snapshot_status_5_keys`
— both hit `assert 500 == 200` against `/agent/*` endpoints. Same symptom,
possibly same root cause across both tests; not investigated further.

**MQTT transport (3 tests, `test_mqtt_transport.py`):** callback invocation
counts assert 0 where 1/5 expected — looks like a wiring/subscription setup
issue, not investigated.

**Coherence rule count drift (3 tests, `test_coherence_rule_loader.py`):**
asserts specific rule counts (18, 28 contradiction rules, etc.) against a
live-loaded rule set that has apparently grown — likely the same *class* of
staleness as the Cat 2 fixes in this PR (a hardcoded count that moved), but
the correct new numbers weren't verified, so left alone rather than guessed.
CLAUDE.md's own "green-main gate reconcile" note already documents
`FSCA CONTRADICTION_RULES==28` as a separately pre-existing flake — this may
be the same one resurfacing, or may be a different assertion; not confirmed.

**Named individually per LANE OPS r-next priority, confirmed pre-existing on
both `main` and branch (not investigated further in this PR):**
`test_phase67_ceremony_hardening.py::TestCeremonyChainIntegration::test_17_record_ceremony_missing_address_raises_runtime_error`
(a fail-closed guard not raising — security-relevant, flagged as
higher-priority than the rest of this list by the reviewing party),
`test_phase54_hardening.py::TestSendRawTxNonceReset::test_send_raw_tx_resets_nonce_on_send_failure`
(nonce-reset-on-failure not firing).

**Remaining individual items, no shared pattern identified:**
`test_agent_registration.py` (2, contract-call-shaped error),
`test_batcher_recovery.py` (2), `test_chain_reconciler.py` (2),
`test_daemon_health_monitor.py::test_detect_firmware_drift_on_live_repo`
(1 — this repo's local `bridge/firmware/joypad-os` submodule is in a
modified state per `git status`; plausibly local-state-sensitive, not
confirmed), `test_dag_r07_forge.py` (3), `test_fix_d_feedback_timeout.py`
(1), `test_local_host_tools_endpoint.py` (1), `test_mythos_full_variants.py`
(1 — flags a missing methodology-assessment file reference),
`test_operator_session_register_agents.py` (2),
`test_phase140_probe_comparison.py::test_2_probe_comparison_conflicts_with_session_type`
(1), `test_phase191_tsp.py` (2), `test_qortroller_cli.py` (2),
`test_qortroller_retina_capture.py::test_save_capture_crops_enabled_writes`
(1), `test_retina_adaptive_lag.py` (2 — `AttributeError:
'RetinaGameCapture' object has no attribute '_capture_enabled'`, looks like
a real rename/refactor gap, not confirmed), `test_uvc_source.py` (2 —
synthetic-frame optical-flow processing test, ambiguous between a real bug
and cv2-version/platform-sensitive behavior, not confirmed either way),
`test_vsd_harness.py::test_seeded_vault_passes_if_present` (1).

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
