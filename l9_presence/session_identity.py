"""U1 — the shared session identifier (PoSP prerequisite; docs/d-cert5-unified-presence-design-2026-07-04.md §2.6).

THE ONE PREIMAGE (D-CERT-5.3 rider — no fifth hash scheme):

    session_id = SHA-256(UTF-8(f"{label}_{stamp}")) hex
    session_display = f"{label}_{stamp}"

`label` is the operator-chosen daemon label; `stamp` is the daemon's once-per-session `int(time.time())`
mint (retina_capture_daemon.cmd_start) — the exact canonical string that ALREADY names the session's log,
harvest corpus, and ring-archive directory. Plain SHA-256, no domain tag, no new commitment family:
OPERATIONAL infrastructure per D-CERT-5.2, never a FROZEN-v1 primitive.

D-CERT-9 posture (instance-pinning, operator-resolved 2026-07-04): the stamp is a built-in instance
nonce — label reuse across sessions yields DISTINCT ids (observed live: corpus_growth_20260704 ran twice,
stamps 1783187401/1783188334). Data sinks are span-windowed, so cross-session pooling is prevented by
time; this id closes the residual POST-HOC ambiguity (which instance issued a record) — detection-shaped,
no new refusal surface.

Consumers: retina_capture_daemon (mints + threads env QORTROLLER_SESSION_ID/_DISPLAY into the bridge
child), issue_kas_records (re-derives from the log filename at stop), dualshock_integration (reads the env
into PITL co-capture meta). Pure stdlib; importable everywhere.
"""
from __future__ import annotations

import hashlib
import re

ENV_SESSION_ID = "QORTROLLER_SESSION_ID"
ENV_SESSION_DISPLAY = "QORTROLLER_SESSION_DISPLAY"

_LOG_NAME = re.compile(r"retina_daemon_(?P<label>.+)_(?P<stamp>\d+)\.log$")


def session_display(label: str, stamp) -> str:
    """The human-readable id — the exact canonical string that names the log/corpus/archive."""
    return f"{label}_{int(stamp)}"


def derive_session_id(label: str, stamp) -> str:
    """SHA-256 hex of the canonical display string. The single join key (design doc §2.6/§5.3)."""
    return hashlib.sha256(session_display(label, stamp).encode("utf-8")).hexdigest()


def parse_daemon_log_name(log_basename: str):
    """Recover (label, stamp) from a daemon log filename, or None if it is not one. Lets the stop-time
    issuance path re-derive the SAME id with zero live plumbing (the stamp is already in the name)."""
    m = _LOG_NAME.search(log_basename)
    if not m:
        return None
    return m.group("label"), int(m.group("stamp"))
