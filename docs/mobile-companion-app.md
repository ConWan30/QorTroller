# VAPI Mobile Companion App — Architecture & Implementation Plan

**Status:** M0 planning artifact. No implementation has begun. Capacitor scaffold deferred until operator explicit authorization.
**Date:** 2026-05-16
**Authoring discipline:** Codex co-architect brief + Claude Code repo survey + VBDIP-0006 compatibility check.
**Anchors consumed:**
- `wiki/methodology/VBDIP-0006-vapi-firmware-reference-implementation.md` (v2 endgame; signing-at-source spec)
- `docs/evidence-os.md` (canonical responsive operator surface)
- `frontend/vite.config.js` (existing dev proxy)
- `frontend/src/api/client.js` (existing API wrapper + VAME validation)
- Operator iPhone 15 walk-through findings (2026-05-16) + Stage 5.3 layout fixes

---

## 0. Why this document exists

The operator wants gamers to be able to verify their session presence + input integrity from their phone while playing on a console — without requiring sophisticated operator setup. Per Mythos's casual-gamer onboarding audit (commit `20567cea` analysis), the v1 deliverable that maps closest to that framing is **Path E: laptop-as-bridge + mobile-as-dashboard** — the cryptographic substrate (PoAC + GIC + L4 + L5 + APOP + VHP) stays on the laptop where USB-HID capture happens; the phone becomes the operator-glance dashboard.

This document specifies the architectural shape of that mobile dashboard, the phased implementation plan, the risk register, and the explicit boundaries that prevent the companion app from becoming a second truth surface.

## 1. Architectural principle

```
Mobile app = trusted companion viewport + connection shell
Evidence OS = canonical operator surface
Bridge / protocol = source of truth
```

The mobile companion app is **a Capacitor wrapper over the existing Evidence OS frontend**. It is not a parallel UI. It is not a re-implementation. It does not fork Evidence OS into a mobile-specific layout.

Discipline points:

- **One source of layout truth.** The Stage 5.3 responsive Evidence OS surface is what renders on every viewport — desktop browser, tablet browser, iPhone Safari, Capacitor WebView. Layout fixes land in `frontend/src/os/*` and propagate to all surfaces simultaneously.
- **One source of API contract truth.** The companion app uses the same `frontend/src/api/*` clients as the desktop Evidence OS. The bridge endpoints are unchanged.
- **Read-mostly default.** v1 companion app surfaces NO write actions that aren't already in the operator's Stage 3 Operator Queue surface. The QueueDetailPanel's two-click confirm + writeGuard cascade applies identically in the Capacitor WebView as in the desktop browser.
- **Phone-only features are the exception, not the rule.** Native capabilities (biometric auth, push notifications, mDNS, BLE) accrete in later milestones (M6) only where they pay clear protocol-layer dividends.

## 2. VBDIP-0006 compatibility verdict

**VBDIP-0006 v1.0 imposes ZERO architectural constraints on the mobile companion app.** The path diagram explains:

| Layer | Current state | VBDIP-0006 future state | Companion app role |
|-------|---------------|-------------------------|-------------------|
| Controller | Stock DualSense Edge over USB | VAPI-Native Controller with SE signing at-source | unchanged (companion never touches controller directly) |
| Bridge | Derives PoAC from HID frames | Validates pre-signed PoAC from controller SE | unchanged (companion never touches bridge construction) |
| API surface | `/operator/*`, `/agent/*`, `/public/*` on port 8080 | identical | identical |
| Companion app | (does not exist yet) | thin Capacitor wrapper over Evidence OS | **read-mostly viewer / dashboard** |

**Two specific VBDIP-0006 future enhancements the companion app COULD adopt later but should NOT in v1:**

1. **Mode A / Mode B consent surface** (VBDIP-0006 §2 Channel C). When VAPI-Native controllers exist, the phone could be the UI where the gamer toggles Mode B (PoAC emission consent) via a bridge endpoint. v1 has no such endpoint and no such controller; deferred.
2. **Hardware-cert-registry verification UI** (VBDIP-0006 §7). When VAPIHardwareCertRegistry is consumed by the companion, the phone could show "This controller is VAPI-Certified manufacturer=X tier=Y." Today the registry exists (`0x1031b7840184D6c8f0EA03F051970578C3c874C2` Phase 99A LIVE) but no VBDIP-0006-conformant controllers are registered. Deferred until at least one cert exists to display.

**The hard guarantee:** the companion app NEVER signs anything. Signing remains either (a) on the bridge wallet via existing chain submission paths, or (b) inside a future VAPI-Native controller's SE per VBDIP-0006. The phone is a read-only viewer. This is the architectural boundary that prevents the companion app from accidentally becoming a private-key holder.

## 3. Recommended app shape

**Capacitor over the existing React + Vite frontend, on the current supported major version verified at M1 commission time.**

**Version-pin discipline (M0.1 amendment 2026-05-16):** This document does NOT hard-pin a Capacitor major. The exact version is resolved at M1 commission via:

```bash
npm view @capacitor/core version       # current latest published
npm view @capacitor/core dist-tags     # current LTS / next channel mapping
```

The version selected at M1 must match the version Capacitor's own docs site currently anchors as the supported release (the docs site at `capacitorjs.com` currently points to **v8** as of authoring; that may have advanced by the time M1 commissions). Hard-pinning a major in this planning artifact would create instant doc drift; the convention is "resolve at install time, record the selected version in the M1 closure note + commit the resulting `package.json` lockfile."

Why Capacitor over alternatives:
- **No code fork.** The same JSX/JS that renders in the desktop browser renders in the WebView. Stage 5.3 + Stage 6 fixes propagate automatically. Mythos's audit dispatched earlier confirmed "underlying responsive layer is mostly correct at iPhone 15 size" — a wrapper is sufficient.
- **Pure web + escape hatch.** When a native capability IS needed (Preferences, mDNS, biometric prompt, push), Capacitor exposes it via well-typed plugins without ejecting to native projects.
- **Cross-platform parity.** iOS + Android single codebase. Stage 5.3 layouts work identically on both.
- **vs React Native:** RN would force a layout rewrite away from CSS into React Native's flexbox-only model. Loses Stage 5.3 work entirely. Rejected.
- **vs PWA-only:** PWA on iOS has degraded support (push, file system, background). Capacitor adds the native shell without the rewrite cost. PWA install path can be retained as a fallback.
- **vs native Swift/Kotlin:** total rewrite; loses Evidence OS; loses Mythos's "wrapper is sufficient" assessment. Rejected.

The Capacitor wrapper adds these specific concerns the desktop browser doesn't have:

- **No Vite dev proxy in production builds.** The bundled WebView serves static files from `capacitor://localhost/`. There's no proxy server. Requests to `/operator/foo` resolve to `capacitor://localhost/operator/foo` which the WebView can't route to the bridge. **Solution: `VITE_BRIDGE_BASE_URL` build-time config + an API client modification to prepend the base URL when set.**
- **iOS Local Network permission.** First time the app talks to a LAN IP, iOS shows a one-time consent prompt requiring `NSLocalNetworkUsageDescription` Info.plist string. UX must surface this honestly ("VAPI needs to reach your laptop's bridge on your home network").
- **Android NEARBY_WIFI_DEVICES** (API 33+) similarly required for any future mDNS / Wi-Fi scan path.
- **WebView's CORS / mixed-content rules** are stricter than dev-mode Vite. Bridge must serve CORS headers permissively to `capacitor://localhost` AND `https://localhost` (Capacitor uses both on different platforms). Existing CORS likely already permits dev origins; needs verification for production-bundle origin.

## 4. Implementation plan — milestones M0 → M6

### M0 — Repo survey + VBDIP-0006 compatibility check ✅ COMPLETE (this document)

Deliverables (done):
- VBDIP-0006 read in full; compatibility verdict above
- Frontend routing inspected (`frontend/src/main.jsx` — react-router-dom v6 nested routes; AppShell mounts `/os/*`; legacy SPA at `/`; 6 public viewer routes preserved)
- Existing API client inspected (`frontend/src/api/client.js` — relative paths + VAME validation + sticky-mock recovery; `frontend/src/api/publicForensic.js` — public read-only hooks)
- Vite dev proxy inspected (12 path prefixes all → `127.0.0.1:8080`)
- Stage 5.3 layout fixes confirmed shipped + iPhone 15 walk-through findings closed

### M1 — Capacitor shell scaffold

Goal: render the existing Evidence OS surface inside a Capacitor WebView, no API access yet — just the shell + cached frontend.

**M0.1 amendment (2026-05-16) — split into Android-first / iOS-deferred tracks** because the operator's host is Windows. iOS scaffolding requires a Mac with Xcode (the Cocoapods + signing chain is Mac-only); attempting iOS work on Windows would either silently fail or produce uncommittable native project artifacts. Android scaffolding works fully on Windows via Android Studio.

#### M1-Android (commission first; Windows-compatible)

Tasks:
- `npm install --save @capacitor/core @capacitor/cli @capacitor/android @capacitor/preferences` (version resolved per §3 at install time; record the resolved version in the M1 closure note)
- `npx cap init` with appId per §9 default, webDir `frontend/dist`, server config initially pointing at the dev Vite for hot-reload (will change for production builds)
- `npx cap add android` (NOT `add ios` — see M1-iOS below)
- `frontend/capacitor.config.ts` (or `.json`) committed; `android/` native project skeleton committed
- Verify `npm run build && npx cap sync android && npx cap open android` produces a launchable Android emulator build (Android Studio on Windows) showing the Evidence OS shell
- Plumb `AndroidManifest.xml` with `INTERNET` + `ACCESS_NETWORK_STATE` permissions
- Sideload to a physical Android device via USB ADB to confirm the WebView renders the responsive Stage 5.3 layout correctly at real-device resolution

Pass criteria (Android-only at this milestone):
- Android emulator launches the Capacitor app; Evidence OS shell renders
- Left rail collapses to top horizontal scroller below 760px
- Sideloaded APK on physical Android phone confirms render
- Operator can hand a tester an .apk file and have it install + launch

Files added (Android only):
- `frontend/capacitor.config.ts` (~30 LOC)
- `frontend/android/` native project (Cap-generated, ~40 files; one bundle)
- `frontend/package.json` updated (~3 LOC dep additions; iOS plugin NOT in deps yet)

Files modified:
- `.gitignore` to exclude `frontend/android/.gradle/`, build artifacts
- `frontend/vite.config.js` — no changes (proxy stays dev-only)

#### M1-iOS (deferred; commission separately when prerequisite available)

**Blocker:** iOS Capacitor scaffolding requires a macOS host with Xcode 15+ and Cocoapods installed. The operator's current development host is Windows.

Options for unblocking M1-iOS:
- **Mac access** — operator borrows / acquires a Mac (mini, MacBook Air, used iMac). One-time enabler for the iOS bundle. Capacitor sync can happen on Windows after; the initial `cap add ios` must run on Mac.
- **CI macOS runner** — GitHub Actions provides `macos-14` and `macos-15` runners free for public repos. A CI job can run `cap add ios` + `cap sync ios` + produce an `.ipa` artifact downloadable to the Windows host. Requires GitHub Actions setup + Apple Developer account ($99/yr) for signing.
- **Cloud Mac service** — MacStadium, MacInCloud (~$1-5/hr). Operator boots an hourly Mac, runs the iOS scaffold once, downloads the resulting native project, commits it from Windows.

iOS-specific tasks (when prerequisite available):
- `npm install --save @capacitor/ios` (no-op on Windows beyond package.json entry; native commands fail until on Mac)
- On Mac: `npx cap add ios && npx cap sync ios && npx cap open ios`
- Plumb `Info.plist` with `NSLocalNetworkUsageDescription`
- Verify iOS simulator launches the Capacitor app; same shell renders
- Distribution path per §9 default (TestFlight is deferred; sideload via Xcode to operator's personal iPhone is the v1 path)

Files added when M1-iOS commissions (NOT in initial Android-only commit):
- `frontend/ios/` native project (Cap-generated on Mac, ~50 files)
- `frontend/package.json` extended with `@capacitor/ios`
- `.gitignore` extended for `frontend/ios/App/Pods/` + iOS build artifacts

**Verification framing:** the M1 closure note captures Android-only verification. iOS verification appears in a future M1-iOS closure addendum when the prerequisite lands. Stage 5.3 phone-viewport validation is iOS-only today (operator walked iPhone 15); R9 in the risk register names the Android responsive audit as a Stage 5.4 prerequisite to M1-Android (per §9 recommendation).

Pass criteria:
- iOS simulator launches the Capacitor app; Evidence OS shell renders; left rail collapses to top horizontal scroller below 760px (iPhone size)
- Android emulator launches the Capacitor app; same shell renders
- No API calls succeed yet (expected — M2 covers this)

### M2 — Bridge URL configuration + connection status

Goal: make API calls actually reach the bridge from the bundled Capacitor app via a configurable LAN base URL.

**M0.1 amendment — runtime bridge URL precedence (FROZEN at M2 spec):**

The base URL the API client uses for every fetch is resolved at request time per the following precedence (highest wins):

| Tier | Source | When it applies |
|------|--------|-----------------|
| 1 | Persisted Capacitor Preferences key `bridgeBaseUrl` | Capacitor bundle — set by operator at first launch via Settings workspace; survives app restarts; explicit operator-changeable |
| 2 | `VITE_BRIDGE_BASE_URL` build-time env var | Capacitor bundle when Preferences key is unset; build-time fallback the operator can bake into a TestFlight / sideload distribution for a known-LAN deployment |
| 3 | Empty string → relative URL → Vite dev proxy | Dev browser at `http://localhost:5173` AND `http://172.20.10.5:5173` (the laptop's LAN-served Vite); behavior byte-identical to current Stage 5.3 |

Implementation contract:
- `runtimeConfig.js` exports `getBridgeBaseUrl()` which evaluates the precedence chain on every call (cheap; Preferences read is sync in v8+ via `@capacitor/preferences` get).
- `client.js`'s `apiGet`/`apiPost` prepend `getBridgeBaseUrl() + path` when the result is non-empty; otherwise pass `path` unchanged.
- `publicForensic.js`'s `publicGet` does the same.
- Settings workspace writes Tier 1 (`Preferences.set({key: 'bridgeBaseUrl', value: ...})`) when operator types/confirms a LAN IP.
- Settings workspace surfaces ALL THREE tiers in the UI so the operator can see which one is active + override.

Tasks:
- Add `VITE_BRIDGE_BASE_URL` to `.env.example` documenting the contract above (empty string in dev → Tier 3 / Vite proxy; populated for Capacitor → Tier 2 build default; overridden by Tier 1 Preferences when operator runs the Settings flow)
- Modify `frontend/src/api/client.js`: prepend the resolved base URL when non-empty; when empty, behavior is byte-identical to today
- Modify `frontend/src/api/publicForensic.js`: same pattern (it has its own `publicGet`)
- Add `runtimeConfig.js` implementing the 3-tier precedence with explicit unit tests proving precedence order
- Add `/os/settings` workspace (or Capacitor-only modal) where operator enters laptop's LAN IP at first launch + sees the active tier. Persist via `@capacitor/preferences`.
- Status surface: add a "Connection" pill to AppShell's StatusStrip showing the currently-configured bridge URL + active precedence tier + last-seen latency. Existing `BRIDGE UNREACHABLE` pill handles the unreachable case.
- Bridge-side: verify `bridge/vapi_bridge/operator_api.py` CORS config permits `capacitor://localhost` + `https://localhost` origins. If not, add them (one-line config tweak; not a protocol change).

Files modified:
- `frontend/src/api/client.js` (~20 LOC; base-URL prepend logic)
- `frontend/src/api/publicForensic.js` (~10 LOC; same)
- `frontend/src/os/AppShell.jsx` (~20 LOC; settings link)
- `frontend/.env.example` (~10 LOC; documentation of 3-tier precedence)
- `bridge/vapi_bridge/operator_api.py` (CORS — verify-only; modify only if missing)

Files added:
- `frontend/src/os/workspaces/SettingsWorkspace.jsx` (~180 LOC; configurable bridge URL + 3-tier precedence display + preference persistence)
- `frontend/src/api/runtimeConfig.js` (~80 LOC; abstracts dev/Capacitor base-URL resolution per 3-tier precedence)
- `frontend/src/__tests__/RuntimeConfig.test.jsx` (~100 LOC; precedence ordering tests)

Pass criteria:
- In dev browser at `localhost:5173`: Tier 3 active; behavior byte-identical to today (test pass at 133/133)
- In dev browser at `172.20.10.5:5173` (LAN-served Vite): Tier 3 active; Vite proxy still routes; behavior identical
- In Capacitor Android bundle with Tier 2 baked: hits the baked URL; QueueSummary populates from real bridge
- In Capacitor Android bundle with Tier 1 set via Settings: Tier 1 wins; URL changes propagate without rebuild
- Android Local Network behaviour: first API call to LAN succeeds (no prompt; Android `INTERNET` is auto-granted; mDNS-class prompts only fire when M6 mDNS work commissions)

### M3 — Evidence OS route embedding / launch target

Goal: ensure the Capacitor app deep-links to specific Evidence OS routes (notification taps, push-handlers later) without breaking react-router.

Tasks:
- Configure Capacitor's URL scheme so `vapi://os/live` opens directly to `/os/live` (and similar for `/queue`, `/replay`, `/protocol`, `/evidence`)
- Capacitor's `App.addListener('appUrlOpen', ...)` handler routes through to react-router programmatic navigation
- Splash screen → /os/evidence redirect on cold launch (same as desktop default)
- No new web routes — the existing `/os/*` route group from Stage 1-6 is the contract

Files modified:
- `frontend/src/main.jsx` (~30 LOC; Capacitor URL listener bridge to react-router)
- `frontend/capacitor.config.ts` (URL scheme registration)

Pass criteria:
- Launch from cold → splash → `/os/evidence`
- `vapi://os/live` deep link → opens directly to Live Match workspace
- Back-button behavior on Android respects react-router history

### M4 — Mobile safe-mode constraints

Goal: enforce the read-mostly default at the WebView boundary so a future regression can't accidentally enable a write surface that the mobile UX doesn't yet handle safely.

Tasks:
- Add a runtime flag `companionMode: 'safe' | 'full'` (default `safe`) to `runtimeConfig.js`
- In `safe` mode, the OperatorQueueWorkspace's `writeGuard` cascade gets a fourth precedence: `companion-safe-mode` (highest precedence after `mock-active`). All write actions render with `ActionGuardBadge` reason `companion-safe-mode — operator review on laptop`.
- The Settings surface lets the operator opt INTO `full` mode with an explicit confirmation: "I understand the laptop has the canonical write surface; enabling full mode on mobile means I will personally double-confirm every destructive action." Once enabled, the cascade reverts to its desktop behavior.
- Default = `safe`. Even if the operator never visits Settings, write actions are visibly disabled with a clear path back to the laptop.
- Document this in `docs/evidence-os.md` §6 (Safety / write-action rules) as a 7th cascade rule.

Files modified:
- `frontend/src/os/workspaces/OperatorQueueWorkspace.jsx` (~15 LOC; add 4th cascade)
- `frontend/src/os/components/ActionGuardBadge.jsx` (~5 LOC; add new reason key)
- `frontend/src/api/runtimeConfig.js` (~20 LOC; companion-mode flag)
- `docs/evidence-os.md` (~30 LOC; 7th cascade rule)

Files added:
- `frontend/src/__tests__/CompanionSafeMode.test.jsx` (~120 LOC; 3-4 tests)

Pass criteria:
- In Capacitor build with default `safe` mode: all writes disabled with the new badge reason
- Tests assert: `safe` disables writes; opt-in to `full` re-enables; the opt-in confirmation requires a typed phrase (mirror governance ceremony pattern)
- Desktop browser unaffected — `safe` mode only auto-engages when `runtimeConfig.detectCapacitor() === true`

### M5 — Test + build verification

Goal: every existing CI gate continues to pass; new mobile-companion tests cover the safe-mode + URL configuration paths.

Tasks:
- Full vitest pass: `npm run test` → expect 133 + ~5 new (M4) = ~138/138
- `npm run build` (web) → main chunk size delta logged; budget +5-10 KB acceptable
- `npx cap sync && npx cap copy ios && npx cap copy android` → Capacitor's own validation passes
- `npx cap doctor` → no warnings beyond stock Capacitor template warnings
- Manual smoke: iOS simulator + Android emulator both launch + render shell + reach a laptop bridge on the LAN

Pass criteria:
- All ~138 frontend tests pass
- Web build passes; main chunk +<10 KB gzipped
- Capacitor builds for both platforms succeed
- Smoke tests on simulator/emulator confirm read endpoints work

### M6 — Deferred roadmap (NOT in v1)

The following are explicitly named as future work, NOT v1:

- **mDNS discovery** of the laptop bridge (currently the operator types the LAN IP manually). Capacitor community plugins exist; iOS requires `NSLocalNetworkUsageDescription` + Bonjour service browsing; Android requires `NEARBY_WIFI_DEVICES`. ~1 week engineering; defer to v1.1 unless operator pain demands earlier.
- **Push notifications** via Capacitor's `@capacitor/push-notifications` plugin (FCM/APNS). Triggered by FSCA CRITICAL findings, draft accumulation thresholds, kill-switch state changes. Requires server-side push token registration on the bridge. Defer to v1.2.
- **Biometric prompt** via Capacitor's `@capacitor-community/biometric-auth`. Use case: gating Settings → companionMode='full' opt-in behind Face ID / fingerprint. Defer to v1.2; the typed-phrase governance pattern is sufficient for v1.
- **VBDIP-0006 Mode A/B consent surface** when VAPI-Native controllers exist on-chain. Defer until first cert registered.
- **VBDIP-0006 hardware-cert-registry verification UI** showing "This controller is VAPI-Certified manufacturer=X tier=Y." Same defer condition.
- **PWA fallback** for users who don't want to install a native shell. Capacitor 6.x's web build IS a PWA if a manifest + service worker land. Defer to v1.1.

## 5. Risk register

| # | Risk | Severity | Likelihood | Mitigation |
|---|------|----------|------------|------------|
| R1 | **Bridge LAN discoverability friction.** Operator must find + type laptop IP. | MEDIUM | HIGH | Defer mDNS to v1.1; v1 Settings surface includes clear "Find your IP" instructions + the `ipconfig`/`ifconfig` command snippet inline. Acceptable v1 UX. |
| R2 | **Mobile browser storage caps.** Capacitor's Preferences API has small quotas; large QueueDetailPanel forensic-payload `<pre>` blocks could spike storage if cached. | LOW | LOW | The frontend doesn't currently persist large blobs to storage — only react-query caches them in-memory. No mitigation needed unless future M-tier caching is added. |
| R3 | **iOS Local Network permission UX.** User denies the prompt → app appears broken with no clear recovery path. | HIGH | MEDIUM | Settings surface MUST detect denied-permission state and surface explicit re-enable instructions ("iOS Settings → VAPI → Local Network → enable"). Show a friendly preflight prompt before triggering the first LAN call so the user understands what they're consenting to. |
| R4 | **Operator write-action safety regression.** A future Evidence OS commit adds a new write surface that doesn't route through `OperatorQueueWorkspace`'s `writeGuard`, bypassing M4's `companion-safe-mode` enforcement. | HIGH | MEDIUM | (a) Add a vitest regression guard that greps for any `apiPost(` call site outside the established write paths; fail CI if introduced without a `writeGuard` check. (b) Document the contract in `docs/evidence-os.md` §6 (M4 task). (c) Mythos hardening pass per §8.9 extension rule must explicitly check this on every new workspace. |
| R5 | **Future signing-path compatibility.** If a future v2 enhancement DOES want the phone to participate in any signing (e.g. operator co-sign for governance ceremonies via WalletConnect), the v1 read-mostly default needs explicit opt-out — and the signing must NEVER happen with a private key stored on the phone itself. | MEDIUM | LOW | Document the signing-path constraint explicitly in this file (§6 below) so any future engineer knows the boundary before commissioning the work. WalletConnect-style remote-sign is acceptable; phone-resident private-key signing is forbidden. |
| R6 | **iOS / Android packaging overhead.** Apple Developer Program ($99/yr) + Google Play Console ($25 one-time) + signing certs + provisioning profiles + version bumps + store review. | MEDIUM | HIGH | v1 ships as a Capacitor debug build distributed via TestFlight (iOS) and direct APK (Android sideload) — NOT through the App Store / Play Store. Defer store submission to v2 when there's empirical user demand. Operator can sideload to personal devices for testing without paying anything yet. |
| R7 | **WebView CORS + mixed content.** Bundled Capacitor app uses `capacitor://localhost` origin; bridge CORS may not allow it. | MEDIUM | MEDIUM | M2 task: verify + extend bridge CORS to permit `capacitor://localhost` + `https://localhost`. One-line config in `operator_api.py`; not a protocol change. |
| R8 | **VAME header validation in Capacitor WebView.** Stage 5.1 added VAME sidecar header validation. WebView may strip or reorder headers; validation could spuriously fail. | LOW | MEDIUM | Test in iOS + Android WebViews before v1 ships. If broken, the existing `vameFailureCount()` counter surfaces it without breaking the app (the validator never throws). If chronic, document as a known M-tier issue + fix in M2. |
| R9 | **Stage 5.3 phone-viewport layout assumed by mythos to be "mostly correct" — but only iPhone 15 + iOS Safari was tested.** | MEDIUM | MEDIUM | Pre-M1: ship one additional small responsive audit pass on Android (Pixel 7-class viewport, Chrome) before committing to the Capacitor shell. If breaks emerge, close them as Stage 5.4 before M1 starts. |
| R10 | **Companion app accidentally becomes "second product surface".** Marketing pressure or feature creep could push UI choices that diverge from Evidence OS (e.g. phone-only widgets, custom mobile flows). | HIGH | MEDIUM | The architectural principle in §1 is the load-bearing defense. This document codifies the "one source of layout truth" discipline. Any deviation requires a successor amendment to this doc + explicit operator authorization. |

## 6. v1 credential rule

**The mobile companion app NEVER holds a private key or a full-write operator API key in v1.** Four subordinate rules (FROZEN at v1 spec; M0.1 amendment 2026-05-16 elevates rule 3 + adds rule 4 to the prior 3-rule signing-path block):

1. **No bridge wallet key on the phone.** The bridge wallet (currently `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692`) lives in `bridge/.env` on the laptop, gitignored. The phone has no copy. Not in build env, not in Preferences, not in WebView localStorage.
2. **No phone-resident private key of any kind.** When VBDIP-0006 v2 controllers exist with at-source signing, the key lives in the controller's secure element — not on the phone. The phone observes signed PoAC records via the bridge; it does not validate signatures locally (the bridge does that; the public `/algorithms` + `/public/session` browser-side verifier already exists for third-party audit). No ECDSA key, no Ed25519 key, no symmetric session key persisted in any phone storage layer.
3. **No persisted full-write API key in v1.** The current desktop frontend uses `VITE_VAPI_API_KEY` (matching the bridge's `OPERATOR_API_KEY`) which is a full-write credential granting access to ALL operator endpoints including state-changing ones (anchor-cedar-bundle, gic-reset, override-gameplay-context, force-corpus-snapshot, etc.). v1 companion app MUST NOT persist this key on the phone. Three derived requirements:
   - The Capacitor build MUST NOT bake `VITE_VAPI_API_KEY` into the bundle at build time (would ship the secret to every device that installs the .apk).
   - Settings workspace MUST NOT expose a text field for entering the full-write API key.
   - First-launch flow MUST treat all bridge endpoints as unauthenticated; this means most operator endpoints will return 401/403, which is exactly the intended v1 read-mostly posture.
4. **Read-only token only if needed.** If v1 read endpoints (e.g. `/agent/curator-status`, `/operator/operator-agent-shadow-log`) require auth that the current bridge config provides via `OPERATOR_API_KEY`, the v1 companion app MAY support a **read-only token** distinct from the full-write key, with these properties:
   - Introduced via a NEW bridge config field `OPERATOR_READ_ONLY_API_KEY` (separate from `OPERATOR_API_KEY`)
   - Bridge enforces: the read-only token grants ONLY GET endpoints; any POST/PUT/DELETE returns 403 regardless of token presence
   - Companion app's Settings flow allows pasting THIS token only (UX surfaces explicit "Read-only key — cannot perform write actions")
   - Even with the read-only token, the M4 `companion-safe-mode` cascade still applies — the token is a belt; the safe-mode block is the suspenders
   - This is a v1 OPTIONAL feature; if not implemented in M1-M5, the v1 companion runs purely against unauthenticated public endpoints (`/public/*` family) which already work without any token

These four rules are non-negotiable in v1. They're the boundary that prevents the companion app from accidentally becoming a credential-bearing artifact a thief / cloner could compromise.

### Future-version signing escape hatch (NOT v1)

If a future v2 or v3 enhancement DOES want the phone to participate in any signing (e.g. operator co-sign for governance ceremonies from the phone), acceptable paths:
- **WalletConnect 2.x** remote-sign flow — signing happens in a separate wallet app that already protects its keys; companion app is a request/display surface only
- **Capacitor wallet plugin delegating to OS keychain** — Secure Enclave on iOS, TEE on Android; signing material stays hardware-protected, never appears in JS memory

Forbidden paths in all versions:
- Phone-resident raw private keys (any algorithm, any storage tier)
- Full-write API key persisted on phone
- Browser localStorage / sessionStorage / IndexedDB persistence of credentials beyond a session-lifetime ephemeral read-only token (and even that requires explicit M-tier authorization beyond this v1 spec)

## 7. Recommended test/build commands

After M1-M2 land, the operator's verification workflow is:

```bash
# Web build (existing, unchanged)
cd frontend && npm run build && npm run test

# Capacitor sync after web changes
npx cap sync

# Open in iOS simulator (Mac required for iOS builds)
npx cap open ios
# OR open in Android emulator (any host)
npx cap open android

# Run on physical iOS device via cable (requires Apple Dev account in M1)
npx cap run ios

# Run on physical Android device via cable / wireless ADB
npx cap run android

# Verify Capacitor sync didn't break web build
npx cap doctor
```

For v1's sideload distribution path:
- **iOS**: TestFlight via Apple Dev account ($99/yr — operator decision when to provision)
- **Android**: Direct APK via `cap run android --release` → install via `adb install` or share the .apk file

## 8. Files added / modified summary (M0-M5 inclusive)

NEW (estimate 9 files):
- `frontend/capacitor.config.ts`
- `frontend/src/os/workspaces/SettingsWorkspace.jsx`
- `frontend/src/api/runtimeConfig.js`
- `frontend/src/__tests__/CompanionSafeMode.test.jsx`
- `frontend/src/__tests__/RuntimeConfig.test.jsx`
- `frontend/ios/` native project (Cap-generated, ~50 files; one bundle)
- `frontend/android/` native project (Cap-generated, ~40 files; one bundle)
- `docs/mobile-companion-app.md` (THIS document)
- `frontend/.env.example` extension for `VITE_BRIDGE_BASE_URL`

MODIFIED (estimate 7 files):
- `frontend/src/api/client.js` (base-URL prepend)
- `frontend/src/api/publicForensic.js` (base-URL prepend)
- `frontend/src/os/AppShell.jsx` (Settings link)
- `frontend/src/os/workspaces/OperatorQueueWorkspace.jsx` (4th writeGuard precedence)
- `frontend/src/os/components/ActionGuardBadge.jsx` (companion-safe-mode reason)
- `frontend/src/main.jsx` (Capacitor URL listener)
- `frontend/package.json` (Capacitor deps)
- `frontend/vite.config.js` (unchanged — proxy stays dev-only)
- `bridge/vapi_bridge/operator_api.py` (CORS extension if needed; verify-first)
- `.gitignore` (native project build artifacts)
- `docs/evidence-os.md` (§6 7th cascade rule for companion-safe-mode)

Total estimate: ~500-1000 LOC of frontend + bridge changes (excluding the Cap-generated native project skeletons which are ~3000-5000 LOC of platform boilerplate but operator-untouched).

## 9. Recommended decisions (operator-authorizable defaults)

**M0.1 amendment 2026-05-16** — each item now ships with a recommended default the operator can authorize as-is. Marked **R** for recommended; if operator accepts without comment, the recommendation is the binding choice. Items still requiring explicit operator input are marked **O**.

1. **App ID convention.** **R: `io.github.conwan30.vapi.companion`**.
   The reverse-DNS convention for app IDs requires a domain the operator controls. The operator's current verifiable namespace is the GitHub account `ConWan30`; `io.github.conwan30.vapi.companion` is the canonical reverse-DNS form for GitHub-account-rooted projects. If a controlled VAPI domain (`vapi.io`, `vapi.xyz`, etc.) is acquired later, a v2 rebrand requires an app uninstall + reinstall cycle (app IDs are immutable on Android Play; iOS allows app ID migration with effort). For v1 sideload distribution this is fine — installs go away when the operator opts. Locked at M1.

2. **App icon + splash assets.** **R: placeholder for v1.**
   Capacitor needs 1024×1024 master icon + adaptive Android icons + iOS sizes. v1 ships with a placeholder derived from the existing VAPI logo / accent palette (the `--os-accent` amber on `--os-bg` deep-void from `frontend/src/os/theme.css` is sufficient as a placeholder masthead). A design pass for production assets is a v1.x deliverable, not a v1 blocker.

3. **iOS distribution path.** **R: deferred until Mac/Xcode access available.**
   Per the M1-Android / M1-iOS split (§4), iOS scaffolding is structurally blocked on Windows. v1 ships Android-only. iOS distribution decision (TestFlight $99/yr vs sideload via Xcode) defers until the Mac prerequisite lands. When it does, sideload via Xcode to operator's personal iPhone is the v1 path; TestFlight is v1.x.

4. **Android distribution path.** **R: direct APK first.**
   Operator builds the .apk via `npx cap build android --release` or Android Studio's `Build > Generate Signed Bundle / APK`, then distributes by direct download / file share / ADB sideload. No Play Console fee, no review cycle, immediate testing. Internal-test track on Play is a v1.x deliverable once the operator has 3+ testers actively using the app. Public Play release is v2.

5. **`companionMode='safe'` default behavior on desktop browsers.** **R: safe-mode OFF on desktop by default.**
   The cascade in M4 only auto-engages safe-mode when `runtimeConfig.detectCapacitor() === true`. Desktop browsers remain the canonical write surface; operators reviewing drafts / managing the queue from their laptop are not gated. If a future v1.x operator decides they ALSO want safe-mode on a specific desktop, they can opt-in via the Settings workspace — but desktop default is OFF.

6. **Mythos co-architect review cadence.** **R: M1 sanity, M2-end, M5-end.**
   Three Mythos dispatches over the v1 arc:
   - **M1 sanity** — read-only review of the Android shell scaffold + native project commits. Catches Capacitor version drift, AndroidManifest permission over-grant, capacitor.config.ts misconfig.
   - **M2-end** — review of the 3-tier bridge URL precedence implementation + the v1 credential rule enforcement (no full-write key baked, no phone-resident private key, read-only token path if implemented). Load-bearing — this is the safety boundary.
   - **M5-end** — review of the final commit arc + test + build verification. Catches any drift introduced over the M1-M5 span before declaring v1 shipped.

7. **Android responsive audit before scaffold.** **R: ship before M1.**
   Stage 5.4 — a focused 30-60 min responsive pass on an Android device (Pixel 7-class viewport at 412×915 logical, or Pixel 8 at 412×914, or whatever the operator has access to). Validates that the Stage 5.3 layout fixes (QueueSummary grid + StatusStrip overflow + Logo flex-shrink) work in Chrome/Edge mobile on Android, not just iOS Safari on iPhone 15. Any breaks land as inline fixes BEFORE the Capacitor shell scaffolding starts — preserves the discipline of "fix the responsive layer before wrapping it." Estimated ~1 day total including walk-through + potential fix commit.

### Acceptance protocol

Operator's authorization options for these defaults:
- **Accept all defaults as-is** — explicit single message ("authorize §9 defaults; commission M1-Android per spec"). The 7 items become binding; Stage 5.4 commissions first, then M1-Android.
- **Accept some, modify others** — operator names which items to override and the replacement choice. Doc gets a follow-up amendment with the modifications before M1 commissions.
- **Defer entirely** — wait until other forward-vectors close before commissioning M1. The plan stays live as the canonical reference but no Capacitor work starts.

## 10. Authoring discipline

This document follows the VBDIP-NNNN authoring pattern (mirrors VBDIP-0001 / VBDIP-0006 structure) but lives in `docs/` not `wiki/methodology/` because it's an engineering plan, not a protocol-layer methodology spec. It is NOT an architect-Ed25519-signed FROZEN spec; it can be amended without ceremony.

Future amendments:
- Each milestone close ships a `## Mn Closure Note` section with commit hash + actual LOC + deviations from plan
- Risk register updates land as a `## Risk Register Revisions` appendix per significant finding
- This document is the canonical source of "what the mobile companion app is + isn't"; any feature proposal that conflicts with §1 architectural principle requires an operator-authorized successor amendment

---

## Stop point

**Per Codex's brief: implementation does NOT begin until operator explicitly authorizes M1.** This document is the M0 deliverable. Open questions in §9 should be answered before commissioning. Mythos co-architect review of this plan is the recommended next step before any Capacitor scaffolding lands.
