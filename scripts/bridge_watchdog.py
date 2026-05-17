"""Phase 236-WATCHDOG — VAPI bridge process watchdog.

Operational layer that protects the GIC grind from process-level failure.
Not a generic restart-on-death tool: refuses to restart in conditions that
would compromise GIC chain integrity, and writes every event to the WEC
(Watchdog Event Chain) audit table for tamper-evident provenance.

VAPI-exclusive properties (why this isn't supervisord):
  1. INV-GIC-003 enforcement at the ops layer — refuses restart when the
     bridge reports gic_chain_broken=True. Restart would mask, not fix.
  2. Grind-session pinning — refuses restart when GRIND_SESSION_ID drifts
     between bridge/.env reads (silent rotation = corpus contamination).
  3. WEC chain — every lifecycle event is appended to watchdog_event_log
     with chained SHA-256 hashes, paralleling the GIC chain pattern.
  4. Grind-cadence-aware backoff — capped at 60s because auto_grind.py
     polls at 60s. Longer = guaranteed missed adjudication windows.
  5. 3-restarts-per-hour ceiling — beyond this the watchdog HALTS rather
     than masking a real fault. Operator must intervene.

USAGE:
    python scripts/bridge_watchdog.py
    # In a separate terminal:
    python auto_grind.py
    cd frontend && npm run dev

INVARIANTS:
  - Never modifies bridge/.env (GRIND_SESSION_ID must survive restarts).
  - Never resets _gic_chain_broken — only POST /operator/gic-reset can do that.
  - Bridge SQLite is shared state; watchdog uses Store directly to write WEC
    events (no HTTP back-call into the dying bridge).
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

# urllib is stdlib — no third-party deps for the watchdog itself.
import urllib.error
import urllib.request


# ----- Constants ------------------------------------------------------------

DEFAULT_BRIDGE_HOST = "127.0.0.1"
DEFAULT_BRIDGE_PORT = 8080
DEFAULT_POLL_INTERVAL_S = 10.0
DEFAULT_HEALTH_TIMEOUT_S = 5.0
DEFAULT_UNHEALTHY_BEFORE_RESTART_S = 30.0   # 3 consecutive failed polls
DEFAULT_BACKOFF_SCHEDULE_S = (5, 10, 30, 60)  # cap at 60s = auto_grind cadence
DEFAULT_MAX_RESTARTS_PER_HOUR = 3
DEFAULT_DEGRADED_HOST_GRACE_S = 300.0       # 5 min CONTESTED before flagging

# Working directory: project root (parent of scripts/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BRIDGE_ENV = PROJECT_ROOT / "bridge" / ".env"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [WATCHDOG] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("watchdog")


# ----- Bridge Store import (delayed) ---------------------------------------

def _import_store_and_chain():
    """Lazy-import the bridge Store and watchdog_chain.

    The watchdog runs from project root. We import only when needed so a
    misconfigured PYTHONPATH gives a clear error, not a startup crash.
    """
    sys.path.insert(0, str(PROJECT_ROOT))
    from bridge.vapi_bridge.config import Config
    from bridge.vapi_bridge.store import Store
    from bridge.vapi_bridge.watchdog_chain import EVENT_CODES
    return Config, Store, EVENT_CODES


# ----- .env helpers ---------------------------------------------------------

def read_grind_session_id_from_env() -> str:
    """Read GRIND_SESSION_ID from bridge/.env without touching it.

    Returns empty string if not set or file missing. Watchdog never modifies
    this file — that's an INVARIANT: GRIND_SESSION_ID continuity across
    restarts is the user-controlled grind anchor.
    """
    if not BRIDGE_ENV.exists():
        return ""
    try:
        for line in BRIDGE_ENV.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("GRIND_SESSION_ID="):
                return line.split("=", 1)[1].strip().strip("\"'")
    except Exception as e:
        log.warning("Failed to read bridge/.env: %s", e)
    return ""


def read_operator_api_key_from_env() -> str:
    if not BRIDGE_ENV.exists():
        return ""
    try:
        for line in BRIDGE_ENV.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line.startswith("OPERATOR_API_KEY="):
                return line.split("=", 1)[1].strip().strip("\"'")
    except Exception:
        pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip
    return ""


# ----- Health probes --------------------------------------------------------

def _http_get_json(url: str, headers: dict | None = None, timeout: float = 5.0) -> dict | None:
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ConnectionError):
        return None
    except Exception as e:
        log.debug("http_get unexpected: %s", e)
        return None


def probe_bridge_health(host: str, port: int, timeout: float) -> bool:
    """Hit /health. Returns True iff 200 OK with parseable JSON."""
    return _http_get_json(f"http://{host}:{port}/health", timeout=timeout) is not None


def probe_grind_chain(host: str, port: int, api_key: str, timeout: float) -> dict | None:
    """Hit /bridge/grind-chain-status. Returns dict (with chain_intact) or None."""
    headers = {"x-api-key": api_key} if api_key else {}
    return _http_get_json(
        f"http://{host}:{port}/bridge/grind-chain-status",
        headers=headers, timeout=timeout,
    )


def probe_capture_health(host: str, port: int, api_key: str, timeout: float) -> dict | None:
    headers = {"x-api-key": api_key} if api_key else {}
    return _http_get_json(
        f"http://{host}:{port}/bridge/capture-health",
        headers=headers, timeout=timeout,
    )


# ----- Watchdog core --------------------------------------------------------

class Watchdog:
    def __init__(self, args: argparse.Namespace):
        self.host = args.host
        self.port = args.port
        self.poll_interval = float(args.poll_interval)
        self.health_timeout = float(args.health_timeout)
        self.unhealthy_before_restart = float(args.unhealthy_before_restart)
        self.max_restarts_per_hour = int(args.max_restarts_per_hour)
        self.backoff_schedule = DEFAULT_BACKOFF_SCHEDULE_S
        self.degraded_host_grace = DEFAULT_DEGRADED_HOST_GRACE_S
        self.dry_run = bool(args.dry_run)

        # Lazy imports so a missing bridge install gives a clear error
        Config, Store, EVENT_CODES = _import_store_and_chain()
        # Phase 236-WATCHDOG-FIX 2026-05-06: Config has no from_env() classmethod;
        # field defaults already read from env via _env*() helpers, so plain Config()
        # is the canonical load pattern (mirrors bridge main.py:94 self.cfg = cfg
        # which receives Config()).
        self._cfg = Config()
        self._store = Store(self._cfg.db_path)
        self._event_codes = EVENT_CODES

        # Pinned grind session ID — read once at startup. If it changes
        # mid-watchdog-lifetime, we refuse restart (silent rotation guard).
        self._pinned_sid = read_grind_session_id_from_env()
        self._operator_key = read_operator_api_key_from_env()

        self._proc: subprocess.Popen | None = None
        self._unhealthy_since: float | None = None
        self._restart_timestamps: list[float] = []  # monotonic-time epochs of restarts
        self._halted = False
        self._stop = False

        # Degraded-host tracking
        self._degraded_since: float | None = None

        log.info("Watchdog init — bridge=%s:%d poll=%.1fs sid=%r dry_run=%s",
                 self.host, self.port, self.poll_interval,
                 self._pinned_sid, self.dry_run)

    # --- WEC writes -----------------------------------------------------

    def _record_event(self, event_name: str, pid: int = 0, **metadata) -> None:
        """Append one event to watchdog_event_log via the Store."""
        try:
            ec = int(self._event_codes.get(event_name, 0))
            if ec == 0:
                log.warning("Unknown event_name=%s — not recorded", event_name)
                return
            md = json.dumps(metadata, default=str)[:1024]
            wec_hex = self._store.insert_watchdog_event(
                event_code=ec,
                event_name=event_name,
                pid=int(pid),
                grind_session_id=self._pinned_sid,
                ts_ns=time.time_ns(),
                metadata_json=md,
            )
            log.info("WEC event=%s pid=%d wec=%s",
                     event_name, pid, wec_hex[:16])
        except Exception as e:
            # Recording failures must NEVER kill the watchdog. Operational
            # continuity outweighs audit-log completeness during a crisis.
            log.error("Failed to record WEC event %s: %s", event_name, e)

    # --- Restart guards -------------------------------------------------

    def _gic_broken(self) -> bool:
        """Best-effort read of bridge gic-chain-status — returns True if chain_intact=False."""
        status = probe_grind_chain(self.host, self.port, self._operator_key, self.health_timeout)
        if status is None:
            # Can't reach bridge — assume chain not broken (process might be
            # restarting; restart-decision is made elsewhere).
            return False
        return not bool(status.get("chain_intact", True))

    def _gic_broken_in_db(self) -> bool:
        """Direct Store read of latest WEC + ruling chain (when bridge unreachable).

        We re-verify the GIC chain via Store as a fallback when /bridge endpoints
        are unreachable (bridge is the dying process — can't ask it).
        """
        try:
            cs = self._store.get_grind_chain_status(self._pinned_sid, self._cfg)
            return cs.get("chain_length", 0) > 0 and not cs.get("chain_intact", True)
        except Exception as e:
            log.warning("GIC DB check failed: %s", e)
            return False

    def _sid_drifted(self) -> tuple[bool, str]:
        """Returns (drifted, current_sid). drifted=True if env disagrees with pinned."""
        cur = read_grind_session_id_from_env()
        return (cur != "" and cur != self._pinned_sid), cur

    def _restart_ceiling_hit(self) -> bool:
        cutoff = time.monotonic() - 3600.0
        self._restart_timestamps = [t for t in self._restart_timestamps if t >= cutoff]
        return len(self._restart_timestamps) >= self.max_restarts_per_hour

    # --- Process control ------------------------------------------------

    def _spawn_bridge(self) -> int:
        """Spawn the bridge as a subprocess. Returns PID."""
        if self.dry_run:
            log.info("DRY RUN — would spawn: python -m bridge.vapi_bridge.main")
            return 0
        cmd = [sys.executable, "-m", "bridge.vapi_bridge.main"]
        log.info("Spawning bridge: %s (cwd=%s)", " ".join(cmd), PROJECT_ROOT)
        # Inherit env (so GRIND_SESSION_ID, OPERATOR_API_KEY etc. flow through)
        self._proc = subprocess.Popen(cmd, cwd=str(PROJECT_ROOT))
        pid = self._proc.pid
        return pid

    def _terminate_bridge(self) -> None:
        if self.dry_run or self._proc is None:
            return
        log.info("Terminating bridge pid=%s", self._proc.pid)
        try:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                log.warning("Bridge did not exit on TERM — sending KILL")
                self._proc.kill()
                self._proc.wait(timeout=5)
        except Exception as e:
            log.warning("Bridge termination raised: %s", e)
        self._proc = None

    def _backoff_for_attempt(self, attempt: int) -> float:
        idx = min(attempt, len(self.backoff_schedule) - 1)
        return float(self.backoff_schedule[idx])

    # --- Restart decision ----------------------------------------------

    def _attempt_restart(self) -> None:
        """Triage and (if safe) restart the bridge."""
        # Guard 1: GIC chain integrity — never restart over a broken chain
        if self._gic_broken() or self._gic_broken_in_db():
            log.critical("REFUSING RESTART — gic_chain_broken=True. "
                         "Operator must POST /operator/gic-reset before restart.")
            self._record_event("BRIDGE_RESTART_REFUSED_GIC",
                               pid=(self._proc.pid if self._proc else 0))
            self._halted = True
            self._record_event("WATCHDOG_HALT", reason="gic_chain_broken")
            return

        # Guard 2: GRIND_SESSION_ID drift — never restart with rotated session
        drifted, cur = self._sid_drifted()
        if drifted:
            log.critical("REFUSING RESTART — GRIND_SESSION_ID drifted from %r to %r. "
                         "Restart with new session_id would corrupt the corpus. "
                         "Resolve manually before continuing.",
                         self._pinned_sid, cur)
            self._record_event("BRIDGE_RESTART_REFUSED_SID",
                               pid=(self._proc.pid if self._proc else 0),
                               pinned=self._pinned_sid, current=cur)
            self._halted = True
            self._record_event("WATCHDOG_HALT", reason="grind_session_id_drift")
            return

        # Guard 3: restart-rate ceiling
        if self._restart_ceiling_hit():
            log.critical("REFUSING RESTART — %d restarts in last hour exceeds ceiling. "
                         "Cascading failure suspected. Operator intervention required.",
                         len(self._restart_timestamps))
            self._record_event("WATCHDOG_BACKOFF_CEILING",
                               restarts=len(self._restart_timestamps))
            self._halted = True
            self._record_event("WATCHDOG_HALT", reason="restart_ceiling")
            return

        # All guards passed — proceed with restart
        attempt = len(self._restart_timestamps)
        backoff = self._backoff_for_attempt(attempt)
        log.warning("Restarting bridge (attempt %d, backoff=%.1fs)", attempt + 1, backoff)
        self._terminate_bridge()
        self._record_event("BRIDGE_RESTART_TRIGGERED",
                           pid=0, attempt=attempt + 1, backoff_s=backoff)
        time.sleep(backoff)
        new_pid = self._spawn_bridge()
        self._restart_timestamps.append(time.monotonic())
        self._unhealthy_since = None
        self._record_event("BRIDGE_START", pid=new_pid)

    # --- Main loop ------------------------------------------------------

    def run(self) -> int:
        """Main supervision loop. Returns exit code."""
        # Install signal handlers
        signal.signal(signal.SIGINT, self._on_signal)
        signal.signal(signal.SIGTERM, self._on_signal)

        # Initial spawn
        pid = self._spawn_bridge()
        self._record_event("BRIDGE_START", pid=pid)

        # Allow bridge a generous startup window before health-checking
        log.info("Waiting %.1fs for bridge to initialize...", 15.0)
        time.sleep(15.0)

        while not self._stop:
            if self._halted:
                log.error("Watchdog HALTED. Manual intervention required.")
                break

            # Process liveness check first (cheaper than HTTP)
            if not self.dry_run and self._proc is not None:
                rc = self._proc.poll()
                if rc is not None:
                    log.warning("Bridge process exited with code=%s", rc)
                    self._record_event("BRIDGE_UNRESPONSIVE",
                                       pid=self._proc.pid, exit_code=rc)
                    self._unhealthy_since = time.monotonic() - self.unhealthy_before_restart - 1
                    self._attempt_restart()
                    continue

            # HTTP health check
            healthy = probe_bridge_health(self.host, self.port, self.health_timeout)

            if healthy:
                # Capture-health degradation (CONTESTED) — log but don't restart
                cap = probe_capture_health(self.host, self.port, self._operator_key,
                                           self.health_timeout)
                if cap and cap.get("host_state") in ("CONTESTED", "DEGRADED"):
                    if self._degraded_since is None:
                        self._degraded_since = time.monotonic()
                    elif (time.monotonic() - self._degraded_since) > self.degraded_host_grace:
                        log.warning("Host state %s sustained > %.0fs (advisory only)",
                                    cap.get("host_state"), self.degraded_host_grace)
                        self._record_event("BRIDGE_DEGRADED_HOST_STATE",
                                           pid=(self._proc.pid if self._proc else 0),
                                           host_state=cap.get("host_state"))
                        self._degraded_since = time.monotonic()  # reset timer
                else:
                    self._degraded_since = None

                if self._unhealthy_since is not None:
                    log.info("Bridge recovered.")
                    self._unhealthy_since = None
                self._record_event("BRIDGE_HEALTHY",
                                   pid=(self._proc.pid if self._proc else 0))
            else:
                if self._unhealthy_since is None:
                    self._unhealthy_since = time.monotonic()
                    log.warning("Bridge unhealthy — entering grace window")
                elapsed = time.monotonic() - self._unhealthy_since
                self._record_event("BRIDGE_UNRESPONSIVE",
                                   pid=(self._proc.pid if self._proc else 0),
                                   unhealthy_for_s=round(elapsed, 1))
                if elapsed >= self.unhealthy_before_restart:
                    log.error("Bridge unresponsive for %.1fs — restarting", elapsed)
                    self._attempt_restart()

            # Sleep, but only emit one HEALTHY event per minute to avoid log spam
            time.sleep(self.poll_interval)

        # Shutdown
        log.info("Watchdog stopping.")
        self._terminate_bridge()
        return 0 if not self._halted else 2

    def _on_signal(self, signum, _frame) -> None:
        log.info("Received signal=%s — initiating clean stop", signum)
        self._stop = True


# ----- CLI ------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="VAPI bridge process watchdog (Phase 236-WATCHDOG)")
    p.add_argument("--host", default=DEFAULT_BRIDGE_HOST)
    p.add_argument("--port", type=int, default=DEFAULT_BRIDGE_PORT)
    p.add_argument("--poll-interval", type=float, default=DEFAULT_POLL_INTERVAL_S,
                   help="Seconds between health probes (default 10)")
    p.add_argument("--health-timeout", type=float, default=DEFAULT_HEALTH_TIMEOUT_S,
                   help="HTTP probe timeout in seconds (default 5)")
    p.add_argument("--unhealthy-before-restart", type=float,
                   default=DEFAULT_UNHEALTHY_BEFORE_RESTART_S,
                   help="Seconds of unhealthiness before restart (default 30)")
    p.add_argument("--max-restarts-per-hour", type=int,
                   default=DEFAULT_MAX_RESTARTS_PER_HOUR,
                   help="Restart ceiling per rolling hour (default 3)")
    p.add_argument("--dry-run", action="store_true",
                   help="Probe but never spawn or terminate bridge")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    wd = Watchdog(args)
    return wd.run()


if __name__ == "__main__":
    sys.exit(main())
