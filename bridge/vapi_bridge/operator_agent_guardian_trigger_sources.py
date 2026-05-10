"""Phase O2-GUARDIAN-TRIGGERS -- 2026-05-10.

Concrete LIVE trigger source(s) for the GuardianPollingLoop shipped in
Phase O2-DRAFT-AUTOLOOP. Sibling of operator_agent_git_trigger_source.py;
follows the same fail-open + opt-in invariants.

DESIGN
======

GuardianFscaTriggerSource is a callable -- when invoked, returns a list of
pending trigger dicts shaped for the polling loop's get_pending_triggers
contract:

    [{"kind": "fsca_finding",
      "payload": {"finding_id", "severity", "agents_involved", "subject"}}]

It subscribes to NEW rows of the fleet_coherence_log SQLite table (Phase 193;
written by FleetSignalCoherenceAgent) by maintaining an in-memory id
high-water mark. Each call enumerates rows with id > last-seen-id and emits
one trigger per new row in id-ascending order. First call seeds the
baseline (returns []) so historical findings don't replay at boot.

DRIFT FINDING (vs brief)
========================
Brief said the table is `fleet_signal_coherence_log`; the actual schema in
bridge/vapi_bridge/store.py:2281 names it `fleet_coherence_log`. The cfg
flag docstring (config.py:2090) also references `fleet_coherence_log`, so
that's the canonical name. This module uses `fleet_coherence_log`.

SEVERITY LADDER MAPPING
=======================
FSCA writes severity as one of {CRITICAL, HIGH, MEDIUM, LOW}. The Guardian
polling loop's _handle_fsca_finding consumes severity in the operational-
diagnostic ladder {critical, error, warn, info}. We map:

    CRITICAL -> critical
    HIGH     -> error
    MEDIUM   -> warn
    LOW      -> info
    (anything else -> info)

INVARIANTS
==========
- NEVER raises; all sqlite3 / JSON / column errors are caught + logged at
  WARNING and result in [] from __call__.
- First call seeds the baseline via SELECT MAX(id) and returns []. If the
  table is missing (FSCA hasn't shipped), baseline is 0 and __call__ also
  returns [].
- Subsequent calls: SELECT id, coherence_id, rule_name, severity,
  agents_involved, explanation FROM fleet_coherence_log WHERE id > last_seen
  ORDER BY id ASC. Update last_seen to the highest id returned.
- agents_involved is JSON-decoded; on parse failure the row still emits a
  trigger with agents_involved=[] (subject still useful for diagnostic
  drafting; we don't drop the finding because of an encoding bug).
- subject = rule_name + " — " + first 60 chars of explanation. Use em-dash
  separator to match the broader VAPI prose convention.

OPT-IN
======
cfg.operator_agent_guardian_fsca_trigger_enabled (default False). Operator
sets to True to activate. Pairs with
cfg.operator_agent_guardian_polling_enabled=True so Guardian's polling loop
receives FSCA-finding triggers as findings land.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from typing import Any, Optional

log = logging.getLogger(__name__)


# FROZEN-v1 severity ladder mapping (FSCA -> Guardian operational-diagnostic).
# Any change to this map is a contract break with the polling loop's
# _handle_fsca_finding handler. Documented in module docstring.
_MAP_SEVERITY: dict[str, str] = {
    "CRITICAL": "critical",
    "HIGH": "error",
    "MEDIUM": "warn",
    "LOW": "info",
}


def _map_severity(raw: Any) -> str:
    """Map FSCA severity string to Guardian severity ladder; default 'info'."""
    if raw is None:
        return "info"
    key = str(raw).strip().upper()
    return _MAP_SEVERITY.get(key, "info")


class GuardianFscaTriggerSource:
    """Phase O2-GUARDIAN-TRIGGERS callable trigger producer for FSCA findings.

    Construction:
      cfg     -- vapi_bridge.config.Config (or test stub) with
                 operator_agent_guardian_fsca_trigger_enabled flag.
      store   -- vapi_bridge.store.Store; we read its `_db_path` and open
                 read-only connections in __call__ (mirrors FSCA's pattern).

    Calling the instance returns the list of pending fsca_finding triggers
    (id-ascending). First call returns [] and seeds the high-water id.
    """

    def __init__(self, *, cfg: Any = None, store: Any = None) -> None:
        self._cfg = cfg
        self._store = store
        self._last_seen_id: Optional[int] = None
        self._initialized = False

    def __call__(self) -> list[dict]:
        """Return list of fsca_finding triggers for rows since last call.
        First call seeds last-seen and returns []. Errors -> []."""
        # Opt-in gate
        if self._cfg is not None and not getattr(
            self._cfg, "operator_agent_guardian_fsca_trigger_enabled", False
        ):
            return []

        if self._store is None:
            return []
        db_path = getattr(self._store, "_db_path", None)
        if not db_path:
            return []

        if not self._initialized:
            # First call: seed baseline from current MAX(id), return [].
            self._last_seen_id = self._fetch_max_id(db_path)
            self._initialized = True
            return []

        baseline = self._last_seen_id or 0
        try:
            rows = self._fetch_rows_since(db_path, baseline)
        except Exception as exc:
            log.warning(
                "GuardianFscaTriggerSource: SELECT since id=%s failed: %s",
                baseline, exc,
            )
            return []

        if not rows:
            return []

        triggers: list[dict] = []
        max_id = baseline
        for row in rows:
            try:
                row_id = int(row["id"])
            except Exception:
                continue
            if row_id > max_id:
                max_id = row_id
            trig = self._row_to_trigger(row)
            if trig is not None:
                triggers.append(trig)

        # Advance high-water mark to the highest id observed (even if some
        # rows produced no trigger -- we don't want to re-process malformed
        # rows on every cycle).
        self._last_seen_id = max_id
        return triggers

    # ------------------------------------------------------------------
    # SQLite plumbing (never raises into __call__)
    # ------------------------------------------------------------------
    def _fetch_max_id(self, db_path: str) -> int:
        """Return MAX(id) of fleet_coherence_log; 0 if table missing/empty."""
        try:
            conn = sqlite3.connect(db_path, timeout=5.0)
            try:
                cur = conn.execute("SELECT MAX(id) FROM fleet_coherence_log")
                row = cur.fetchone()
                if row is None or row[0] is None:
                    return 0
                return int(row[0])
            finally:
                conn.close()
        except sqlite3.OperationalError as exc:
            # Table may not exist yet (FSCA migration hasn't run in this env).
            log.debug(
                "GuardianFscaTriggerSource: baseline MAX(id) skipped (%s)",
                exc,
            )
            return 0
        except Exception as exc:
            log.warning(
                "GuardianFscaTriggerSource: baseline MAX(id) failed: %s", exc
            )
            return 0

    def _fetch_rows_since(self, db_path: str, last_seen: int) -> list:
        """Return rows from fleet_coherence_log where id > last_seen, ASC."""
        try:
            conn = sqlite3.connect(db_path, timeout=5.0)
            try:
                conn.row_factory = sqlite3.Row
                cur = conn.execute(
                    "SELECT id, coherence_id, rule_name, severity, "
                    "agents_involved, explanation "
                    "FROM fleet_coherence_log "
                    "WHERE id > ? ORDER BY id ASC",
                    (int(last_seen),),
                )
                return cur.fetchall()
            finally:
                conn.close()
        except sqlite3.OperationalError as exc:
            # Table missing -> treat as no rows; return []
            log.debug(
                "GuardianFscaTriggerSource: SELECT skipped (%s)", exc
            )
            return []

    def _row_to_trigger(self, row: Any) -> Optional[dict]:
        """Convert a sqlite3.Row to a Guardian fsca_finding trigger dict.
        Returns None on hard parse failure (caller skips silently)."""
        try:
            finding_id = str(row["coherence_id"] or "")
            rule_name = str(row["rule_name"] or "")
            raw_sev = row["severity"]
            severity = _map_severity(raw_sev)
            explanation_full = str(row["explanation"] or "")
            agents_raw = row["agents_involved"]
        except Exception as exc:
            log.warning(
                "GuardianFscaTriggerSource: row column access failed: %s",
                exc,
            )
            return None

        if not finding_id:
            # No coherence_id -> can't dedup downstream; skip.
            return None

        # Parse agents_involved JSON; on failure default to [] but still
        # emit the trigger (subject is still actionable for the operator).
        agents_involved: list[str]
        try:
            parsed = json.loads(agents_raw) if agents_raw else []
            if isinstance(parsed, list):
                agents_involved = [str(a) for a in parsed]
            else:
                agents_involved = []
        except (TypeError, ValueError):
            agents_involved = []

        # subject: rule_name + em-dash + first 60 chars of explanation
        snippet = explanation_full[:60]
        if rule_name and snippet:
            subject = f"{rule_name} — {snippet}"
        elif rule_name:
            subject = rule_name
        else:
            subject = snippet or "(no rule_name)"

        return {
            "kind": "fsca_finding",
            "payload": {
                "finding_id": finding_id,
                "severity": severity,
                "agents_involved": agents_involved,
                "subject": subject,
            },
        }


def make_guardian_fsca_trigger_source(
    *,
    cfg: Any = None,
    store: Any = None,
) -> "GuardianFscaTriggerSource | None":
    """Module-level factory matching the make_git_trigger_source pattern.
    Returns None when cfg.operator_agent_guardian_fsca_trigger_enabled is
    False (opt-in default).

    Higher-level wiring (main.py Pre-Wave autowire) constructs this and
    appends it to Guardian's _composed_sources list. Returning None lets
    the wiring code skip the source without changing the polling loop's
    fallback no-op stub.
    """
    if cfg is not None and not getattr(
        cfg, "operator_agent_guardian_fsca_trigger_enabled", False
    ):
        log.info(
            "GuardianFscaTriggerSource: disabled "
            "(operator_agent_guardian_fsca_trigger_enabled=False)"
        )
        return None
    return GuardianFscaTriggerSource(cfg=cfg, store=store)
