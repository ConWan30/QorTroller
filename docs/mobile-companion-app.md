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

**Capacitor 6.x over the existing React + Vite frontend.**

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

Goal: render the existing Evidence OS surface inside a Capacitor WebView, build an `.apk` and `.ipa` (or at minimum a Capacitor-served Android debug build for first walk-through), no API access yet — just the shell + cached frontend.

Tasks:
- `npm install --save @capacitor/core @capacitor/cli @capacitor/ios @capacitor/android @capacitor/preferences`
- `npx cap init` with appId `xyz.vapi.companion` (or similar), webDir `frontend/dist`, server config initially pointing at the dev Vite for hot-reload (will change for production builds)
- `npx cap add ios && npx cap add android`
- `frontend/capacitor.config.ts` (or `.json`) committed; `ios/` and `android/` native project skeletons committed
- Verify `npm run build && npx cap sync && npx cap open ios` produces a launchable simulator build that shows the Evidence OS shell
- Plumb `Info.plist` with `NSLocalNetworkUsageDescription` + `AndroidManifest.xml` with `INTERNET` + `ACCESS_NETWORK_STATE`

Files added (estimate):
- `frontend/capacitor.config.ts` (~30 LOC)
- `frontend/ios/` native project (Cap-generated, ~50 files)
- `frontend/android/` native project (Cap-generated, ~40 files)
- `frontend/package.json` updated (~5 LOC dep additions)

Files modified:
- `.gitignore` to exclude `frontend/ios/App/Pods/`, `frontend/android/.gradle/`, build artifacts
- `frontend/vite.config.js` — no changes (proxy stays dev-only)

Pass criteria:
- iOS simulator launches the Capacitor app; Evidence OS shell renders; left rail collapses to top horizontal scroller below 760px (iPhone size)
- Android emulator launches the Capacitor app; same shell renders
- No API calls succeed yet (expected — M2 covers this)

### M2 — Bridge URL configuration + connection status

Goal: make API calls actually reach the bridge from the bundled Capacitor app via a configurable LAN base URL.

Tasks:
- Add `VITE_BRIDGE_BASE_URL` to `.env.example` documenting the contract: empty string in dev (use relative paths + Vite proxy), `http://192.168.x.x:8080` in production Capacitor builds
- Modify `frontend/src/api/client.js`: when `VITE_BRIDGE_BASE_URL` is set, prepend it to every fetch URL; when empty, behavior is byte-identical to today
- Modify `frontend/src/api/publicForensic.js`: same pattern (it has its own `publicGet`)
- Add a small in-app settings surface: `/os/settings` (or a Capacitor-only modal) where the operator enters the laptop's LAN IP at first launch. Persist via `@capacitor/preferences`. App reads the preference on boot and stamps it as `VITE_BRIDGE_BASE_URL`-equivalent into a runtime config.
- Status surface: add a "Connection" pill to the AppShell's StatusStrip that shows the currently-configured bridge URL + the last-seen latency. When unreachable, the existing `BRIDGE UNREACHABLE` pill already handles the case.
- Bridge-side: verify `bridge/vapi_bridge/operator_api.py` CORS config permits `capacitor://localhost` + `https://localhost` origins. If not, add them (one-line config tweak; not a protocol change).

Files modified:
- `frontend/src/api/client.js` (~20 LOC; base-URL prepend logic)
- `frontend/src/api/publicForensic.js` (~10 LOC; same)
- `frontend/src/os/AppShell.jsx` (~20 LOC; settings link)
- `frontend/.env.example` (~5 LOC; documentation)
- `bridge/vapi_bridge/operator_api.py` (CORS — verify-only; modify only if missing)

Files added:
- `frontend/src/os/workspaces/SettingsWorkspace.jsx` (~150 LOC; configurable bridge URL + preference persistence)
- `frontend/src/api/runtimeConfig.js` (~50 LOC; abstracts dev/Capacitor base-URL resolution)

Pass criteria:
- In dev browser: behavior unchanged (test pass at 133/133)
- In iOS simulator pointing at a laptop bridge on the LAN: all read endpoints work; QueueSummary populates; Evidence Graph + Protocol State render real data
- iOS Local Network prompt fires on first API call; user accepts; subsequent launches use stored permission

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

## 6. Signing-path constraint (R5 elaboration)

**The mobile companion app NEVER holds a private key.** Three subordinate rules:

1. **No bridge wallet key on the phone.** The bridge wallet (`0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692` currently) lives in `bridge/.env` on the laptop, gitignored. The phone has no copy.
2. **No SE-equivalent on the phone.** When VBDIP-0006 v2 controllers exist with at-source signing, the key lives in the controller's secure element — not on the phone. The phone observes signed PoAC records via the bridge; it does not validate signatures locally (the bridge does that; the public `/algorithms` + `/public/session` browser-side verifier already exists for third-party audit).
3. **WalletConnect-style remote sign is acceptable if needed.** If a future v3 enhancement wants operator co-sign for governance ceremonies from the phone (e.g. PV-CI invariant ratification away from the laptop), the WalletConnect 2.x flow OR a Capacitor wallet-plugin that delegates to the iOS/Android system keychain (Secure Enclave / TEE) is the path — but the signing material remains hardware-protected, not in JS memory.

These three rules are non-negotiable. They're the boundary that prevents the companion app from accidentally becoming a credential-bearing artifact a thief / cloner could compromise.

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

## 9. Unresolved decisions

These need operator input before M1 can commission:

1. **App ID convention.** Suggest `xyz.vapi.companion` or `io.vapi.companion`. Locked at M1 + permanently embedded in the iOS bundle ID + Android package name; changing later means rebuilding from scratch. Operator: pick one.
2. **App icon + splash assets.** Capacitor needs 1024x1024 master icon + adaptive Android icons + iOS app icons in multiple sizes. v1 can ship with a placeholder (e.g. the VAPI logo's color block) and iterate. Operator: confirm placeholder is acceptable, or wait for a design pass.
3. **iOS distribution path.** TestFlight (operator pays $99/yr Apple Dev fee) vs simulator-only-for-now vs sideload via Xcode for the operator's personal device. v1 doesn't need App Store; this affects M1 sequencing.
4. **Android distribution path.** Direct APK download / sideload (free, immediate) vs Google Play Console ($25 one-time) vs internal-test track on Play. Recommend direct APK for v1.
5. **`companionMode='safe'` default behavior on desktop browsers.** Should the safe-mode write-block ALSO engage on desktop browsers if `runtimeConfig.detectCapacitor() === false`? Default no (desktop is the canonical write surface). Confirm.
6. **Mythos co-architect review cadence.** Codex named the co-architect role explicitly. Expectation: Mythos dispatched read-only at M0 (done), M2-end (pre-implementation review of bridge-URL handling), M5-end (post-build review of the final commit arc). Confirm cadence.
7. **Stage 5.4 (Android responsive audit per R9) — ship before M1, or accept iPhone-only walk-through validation?** Recommend ship before M1 (~30 min operator walk on a Pixel-class device if available; ~1 day to close any breaks).

## 10. Authoring discipline

This document follows the VBDIP-NNNN authoring pattern (mirrors VBDIP-0001 / VBDIP-0006 structure) but lives in `docs/` not `wiki/methodology/` because it's an engineering plan, not a protocol-layer methodology spec. It is NOT an architect-Ed25519-signed FROZEN spec; it can be amended without ceremony.

Future amendments:
- Each milestone close ships a `## Mn Closure Note` section with commit hash + actual LOC + deviations from plan
- Risk register updates land as a `## Risk Register Revisions` appendix per significant finding
- This document is the canonical source of "what the mobile companion app is + isn't"; any feature proposal that conflicts with §1 architectural principle requires an operator-authorized successor amendment

---

## Stop point

**Per Codex's brief: implementation does NOT begin until operator explicitly authorizes M1.** This document is the M0 deliverable. Open questions in §9 should be answered before commissioning. Mythos co-architect review of this plan is the recommended next step before any Capacitor scaffolding lands.
