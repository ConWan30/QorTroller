"""Match preflight gate -- RP-CLOSE-1 gate RP-5: contention hygiene, mechanized.

Three separate live-match measurement corruptions motivated this gate, each previously
caught only after burning a full match:

  Match 11  -- a zombie killfeed_audit_lane.py process (started ~25h earlier, never cleaned
              up) starved WGC capture to ~8fps; indistinguishable from a real capture bug
              without a process check.
  Match 12  -- bridge at 94.9% CPU under Remote Play codec load; ema_fps collapsed to 3.76.
  cycle-49  -- the 5.4GB bridge DB's per-record nqpv write was a CPU-creep lag source;
              a fresh DB fixed it.
  pre-M8    -- the capture ring persisted hours-old crops across sessions, polluting archives.

Pure functions -- ALL evidence is INJECTED (process list, cpu%, db size, dir listing, env);
the CLI runner (scripts/match_preflight.py) does the gathering. Fail-open discipline per
Sensor C: a gather error is UNVERIFIABLE, never a spurious PASS; overall verdict is
fail-closed (any BLOCK or UNVERIFIABLE -> NO_GO).

Advisory tooling -- the operator can always override by playing anyway; the gate's job is
to make the M11-class false-negative impossible to hit silently.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class CheckState(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    BLOCK = "BLOCK"
    UNVERIFIABLE = "UNVERIFIABLE"   # gather error -- never silently PASS


class OverallVerdict(str, Enum):
    GO = "GO"
    GO_WITH_WARNINGS = "GO_WITH_WARNINGS"
    NO_GO = "NO_GO"


# Command-line substrings identifying heavy tools that must NOT be running when a live
# match starts. killfeed_audit_lane alone collapsed WGC 60->8fps (M11). A pre-existing
# retina_capture_daemon is a stale daemon (preflight runs BEFORE `daemon start`).
HEAVY_TOOL_PATTERNS: tuple = (
    "killfeed_audit_lane",
    "c33_recall_analysis",
    "retina_capture_daemon",
    "capture_session.py",
    "pytest",
    "calibrate_coupling_threshold",
    "run_adversarial",
    "hardware_calibration_watcher",
)

CPU_WARN_PCT: float = 40.0    # bridge-on baseline was ~43-50% in lean mode -- above this, ask why
CPU_BLOCK_PCT: float = 60.0   # M12 measured 94.9% at failure; 60 leaves headroom for codec+capture
DB_WARN_BYTES: int = 3 * 1024 ** 3   # 5.4GB was the measured lag source; warn at 3GB


@dataclass(slots=True)
class ProcessInfo:
    pid: int
    command_line: str


@dataclass
class PreflightEvidence:
    """Injected by the runner. None on any field = that gather step failed (UNVERIFIABLE),
    EXCEPT capture_dir_entries where None = directory does not exist (fresh -- PASS) and
    bridge_db_bytes where None = DB file not found (fresh -- PASS); gather ERRORS for those
    two are reported via the errors dict instead."""
    python_processes: Optional[list] = None          # list[ProcessInfo]
    cpu_percent: Optional[float] = None
    bridge_db_bytes: Optional[int] = None
    capture_dir_entries: Optional[list] = None       # list[str]
    env: dict = field(default_factory=dict)
    errors: dict = field(default_factory=dict)       # check_name -> error string


@dataclass(slots=True)
class CheckResult:
    name: str
    state: CheckState
    note: str


@dataclass
class PreflightReport:
    verdict: OverallVerdict
    checks: list = field(default_factory=list)

    def go(self) -> bool:
        return self.verdict != OverallVerdict.NO_GO


def _check_orphaned_processes(ev: PreflightEvidence, self_pid: int) -> CheckResult:
    if "processes" in ev.errors:
        return CheckResult("orphaned_processes", CheckState.UNVERIFIABLE,
                           f"process gather failed: {ev.errors['processes']}")
    if ev.python_processes is None:
        return CheckResult("orphaned_processes", CheckState.UNVERIFIABLE,
                           "process list not gathered")
    hits = []
    for p in ev.python_processes:
        if p.pid == self_pid:
            continue
        cmd = p.command_line or ""
        for pat in HEAVY_TOOL_PATTERNS:
            if pat in cmd:
                hits.append(f"pid={p.pid} [{pat}]")
                break
    if hits:
        return CheckResult("orphaned_processes", CheckState.BLOCK,
                           f"{len(hits)} heavy tool process(es) running: {'; '.join(hits)} "
                           "-- kill before match start (M11 lesson)")
    return CheckResult("orphaned_processes", CheckState.PASS,
                       f"no heavy tools among {len(ev.python_processes)} python process(es)")


def _check_cpu_baseline(ev: PreflightEvidence) -> CheckResult:
    if "cpu" in ev.errors or ev.cpu_percent is None:
        return CheckResult("cpu_baseline", CheckState.UNVERIFIABLE,
                           f"cpu gather failed: {ev.errors.get('cpu', 'not gathered')}")
    cpu = float(ev.cpu_percent)
    if cpu >= CPU_BLOCK_PCT:
        return CheckResult("cpu_baseline", CheckState.BLOCK,
                           f"cpu {cpu:.0f}% >= {CPU_BLOCK_PCT:.0f}% -- no headroom for "
                           "RP codec + capture (M12 failed at 94.9%)")
    if cpu >= CPU_WARN_PCT:
        return CheckResult("cpu_baseline", CheckState.WARN,
                           f"cpu {cpu:.0f}% >= {CPU_WARN_PCT:.0f}% -- investigate before starting")
    return CheckResult("cpu_baseline", CheckState.PASS, f"cpu {cpu:.0f}%")


def _check_db_size(ev: PreflightEvidence) -> CheckResult:
    if "db" in ev.errors:
        return CheckResult("bridge_db_size", CheckState.UNVERIFIABLE,
                           f"db size gather failed: {ev.errors['db']}")
    if ev.bridge_db_bytes is None:
        return CheckResult("bridge_db_size", CheckState.PASS, "no bridge DB found (fresh)")
    gb = ev.bridge_db_bytes / 1024 ** 3
    if ev.bridge_db_bytes > DB_WARN_BYTES:
        return CheckResult("bridge_db_size", CheckState.WARN,
                           f"bridge DB {gb:.1f}GB > {DB_WARN_BYTES / 1024**3:.0f}GB -- per-record "
                           "write lag risk; consider DB_PATH fresh override (cycle-49 lesson)")
    return CheckResult("bridge_db_size", CheckState.PASS, f"bridge DB {gb:.2f}GB")


def _check_capture_dir_fresh(ev: PreflightEvidence) -> CheckResult:
    if "capture_dir" in ev.errors:
        return CheckResult("capture_dir_fresh", CheckState.UNVERIFIABLE,
                           f"capture dir gather failed: {ev.errors['capture_dir']}")
    if ev.capture_dir_entries is None:
        return CheckResult("capture_dir_fresh", CheckState.PASS,
                           "capture dir does not exist yet (fresh)")
    n = len(ev.capture_dir_entries)
    if n > 0:
        return CheckResult("capture_dir_fresh", CheckState.WARN,
                           f"capture dir already holds {n} entries -- ring persists across "
                           "sessions; use a fresh --capture-dir per match (pre-M8 lesson)")
    return CheckResult("capture_dir_fresh", CheckState.PASS, "capture dir empty")


def _check_env_sanity(ev: PreflightEvidence) -> CheckResult:
    if not ev.env.get("RETINA_KILLFEED_CAPTURE_MAX"):
        return CheckResult("env_sanity", CheckState.WARN,
                           "RETINA_KILLFEED_CAPTURE_MAX not set -- default ring may be too "
                           "small for a full match (launch-stack lesson)")
    return CheckResult("env_sanity", CheckState.PASS,
                       f"RETINA_KILLFEED_CAPTURE_MAX={ev.env['RETINA_KILLFEED_CAPTURE_MAX']}")


def evaluate_preflight(ev: PreflightEvidence, *, self_pid: int = -1) -> PreflightReport:
    """Evaluate all preflight checks against injected evidence. Fail-closed overall:
    any BLOCK or UNVERIFIABLE -> NO_GO; any WARN -> GO_WITH_WARNINGS; else GO."""
    checks = [
        _check_orphaned_processes(ev, self_pid),
        _check_cpu_baseline(ev),
        _check_db_size(ev),
        _check_capture_dir_fresh(ev),
        _check_env_sanity(ev),
    ]
    states = {c.state for c in checks}
    if CheckState.BLOCK in states or CheckState.UNVERIFIABLE in states:
        verdict = OverallVerdict.NO_GO
    elif CheckState.WARN in states:
        verdict = OverallVerdict.GO_WITH_WARNINGS
    else:
        verdict = OverallVerdict.GO
    return PreflightReport(verdict=verdict, checks=checks)
