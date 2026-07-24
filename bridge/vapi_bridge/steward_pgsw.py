"""A2A-STEWARD-EVOLVE B6 — PGSW (Presence-Gated Steward Window).

The 4th novelty and the arc's synthesis: it uses the protocol's OWN presence proof (PoSP) as the liveness
gate on agentic authority. A read-only window wraps the drafters (PCRA / MPJA / DPIG). When a verified
human is present — the registered node's latest PoSP is SYNCHRONIZED within τ, OR a live node session is
active — the window is OPEN and stewards may draft HIGH-severity findings. When no recent presence exists,
the window is CLOSED and stewards draft only LOW-severity / backlog items. HIGH-severity agentic reach is
thus tied to the same PoEP/PoSP/DePIN presence the protocol sells — the operator's liveness IS the
steward's authority.

KAS HYGIENE (load-bearing): presence means a SYNCHRONIZED PoSP or a live session — NEVER an
AUTHORED-without-HID-topology claim. An authorship verdict is explicitly rejected as a presence signal
(the WITNESSED->AUTHORED seam is separate HID-topology work; PGSW must not let authorship stand in for
presence).

READ-ONLY: PGSW never suppresses a draft and never acts — it only sets a DISPOSITION (ACTIVE now vs
BACKLOG until presence returns). Stewards still draft everything; PGSW decides whether a HIGH-severity
draft is live or parked. 0 IOTX, default-OFF (`cfg.pgsw_enabled`). Pure window logic over injected
signals; real PoSP / live-session extraction from the Store is v0.1.

V0 HONESTY / LIMITS (grok round-10):
  * PGSW gates the DISPOSITION of HIGH-severity agentic authority on operator liveness — it does NOT gate
    DETECTION. Under a presence-DoS (adversary forces the window CLOSED), stewards STILL scan and STILL
    emit findings; HIGH/MED drafts merely park to BACKLOG and LOW stays ACTIVE. Force-CLOSED delays HIGH
    ACTIVE surface; it must NEVER become suppression. CONSUMER CONTRACT: BACKLOG is durable, queryable,
    and re-surfaces when the window reopens — a consumer that treats BACKLOG as silent-drop would turn
    presence-DoS into HIGH-finding censorship, which is exactly what this module must not enable. Anything
    that must fire regardless of presence must not be modeled as HIGH-only.
  * SIGNAL TRUST: the pure function trusts the injected `posp_ts_ns` and `live_session_active`. It has NO
    replay binding of its own — it cannot tell a fresh PoSP mint from a recently-re-presented record with
    a recent ts. Recency/replay resistance lives UPSTREAM (PoSP + PoSR recency binding), not here. The
    v0.1 Store adapter must derive OPEN only from genuinely fresh signals and never let an untrusted
    caller assert `live_session_active`.
  * SEVERITY SURFACE: gate_draft speaks HIGH/MED/LOW only. PCRA findings map cleanly. MPJA (JOIN_* verdicts)
    and DPIG (RECOMMEND_* recommendations) are NOT severities — wrapping them requires an explicit
    severity map (JOIN_BROKEN/RECOMMEND_SUSPEND -> HIGH, etc.); that mapping is v0.1, so "wraps the
    drafters" is API-level intent, not automatic normalization for all three.
"""
from __future__ import annotations

SCHEMA = "qortroller-pgsw-v0"
SEVERITIES = ("LOW", "MED", "HIGH")
_DEFAULT_TAU_S = 3600   # a PoSP counts as "present" if SYNCHRONIZED within the last hour


def presence_window(*, posp_verdict: str | None = None, posp_ts_ns: int | None = None,
                    now_ns: int = 0, tau_s: int = _DEFAULT_TAU_S,
                    live_session_active: bool = False) -> dict:
    """Compute whether the presence window is OPEN. OPEN iff a live node session is active OR the latest
    PoSP is SYNCHRONIZED within τ. Authorship verdicts are NOT presence (KAS hygiene)."""
    tau_ns = int(tau_s) * 1_000_000_000
    verdict = None if posp_verdict is None else str(posp_verdict).upper()
    fresh = (posp_ts_ns is not None
             and int(posp_ts_ns) <= int(now_ns) <= int(posp_ts_ns) + tau_ns)

    if live_session_active:
        window_open, reason, source = True, "live node session active", "live_session"
    elif verdict == "SYNCHRONIZED" and fresh:
        window_open, reason, source = True, f"latest PoSP SYNCHRONIZED within tau={tau_s}s", "posp_synchronized"
    else:
        window_open, source = False, None
        if verdict and "AUTHORED" in verdict:
            reason = ("KAS hygiene: an AUTHORED verdict is NOT presence — need a SYNCHRONIZED PoSP or a "
                      "live session (the WITNESSED->AUTHORED seam is separate HID-topology work)")
        elif verdict == "SYNCHRONIZED" and not fresh:
            reason = f"PoSP SYNCHRONIZED but stale (outside tau={tau_s}s or future-dated)"
        else:
            reason = f"no live session and latest PoSP verdict={posp_verdict!r} is not SYNCHRONIZED"

    return {
        "schema": SCHEMA, "window_open": window_open, "reason": reason, "presence_source": source,
        "tau_s": tau_s, "now_ns": now_ns, "posp_verdict": posp_verdict, "posp_ts_ns": posp_ts_ns,
        "note": "READ-ONLY presence gate — OPERATOR LIVENESS (PoSP/live-session) gates HIGH-severity "
                "agentic authority. Authorship is never presence. 0 IOTX; never suppresses a draft, only "
                "sets its disposition.",
    }


def max_active_severity(window: dict) -> str:
    """The highest severity a steward may draft as ACTIVE right now: HIGH when the window is open, else
    LOW (HIGH/MED park to backlog until presence returns)."""
    return "HIGH" if window.get("window_open") else "LOW"


def gate_draft(window: dict, severity: str) -> dict:
    """Set a draft's disposition from the presence window. Window open -> everything ACTIVE. Window closed
    -> only LOW is ACTIVE; MED/HIGH (and any UNKNOWN severity, fail-closed to HIGH) go to BACKLOG. This is
    a disposition label, not suppression — the draft is still produced."""
    sev = str(severity).strip().upper()
    if sev not in SEVERITIES:
        sev = "HIGH"   # fail-closed: an unrecognized severity gets the strictest gate
    active = bool(window.get("window_open")) or sev == "LOW"
    return {
        "schema": SCHEMA, "severity": sev, "window_open": bool(window.get("window_open")),
        "disposition": "ACTIVE" if active else "BACKLOG",
        "note": "ACTIVE = draft is live now; BACKLOG = held until the presence window reopens. PGSW never "
                "deletes or suppresses — the draft persists either way.",
    }


def presence_window_from_store(store, cfg, *, now_ns: int = 0) -> dict:  # pragma: no cover - read-only adapter STUB
    """Read-only adapter, gated by cfg.pgsw_enabled (default False).

    HONEST SCOPE (mirrors B1-B5): STUB. It does NOT yet pull the latest PoSP verdict/timestamp or the live
    node-session state from the Store — that extraction is v0.1. The pure presence_window / gate_draft
    logic over injected signals is real and tested; this adapter does not fabricate presence. Never acts,
    never spends, never git/chain write."""
    if not bool(getattr(cfg, "pgsw_enabled", False)):
        return {"schema": SCHEMA, "enabled": False, "note": "pgsw_enabled=False (opt-in capability)"}
    return {"schema": SCHEMA, "enabled": True,
            "adapter_scope": "STUB — no PoSP / live-session Store extraction yet (v0.1). The pure "
                             "presence_window / gate_draft logic works; this adapter does not.",
            "note": "STUB adapter — refuses to fabricate presence (a fabricated OPEN window would grant "
                    "HIGH-severity authority without a real present operator). Wire PoSP + live-session "
                    "extraction in v0.1. read-only; 0 IOTX; no git/chain."}
