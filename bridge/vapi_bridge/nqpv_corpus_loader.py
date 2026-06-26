"""NQPV study-corpus loader (RETINA-EXCL-2 defensibility study, cycle-30 critical path step 4).

Reads persisted per-record co-capture into normalized, labeled corpus records that the study
harness feeds to ``NovelPresenceFusionOrchestrator.fuse()``. This is the small DB->corpus bridge:
the harness does NOT touch the DB schema or the live loop; it consumes ``NqpvCorpusRecord`` objects.

PURE MODULE + INJECTED FETCHER (Sensor B/C precedent): ``load_from_rows`` operates on injected
row-dicts and is fully deterministic/testable; the single I/O function ``fetch_human_rows`` is the
only thing that touches the store, and it reuses the existing tested ``Store.get_recent_records``.

HONESTY RAILS (the whole point of RETINA-EXCL-2 is a defensible operating point, so the corpus must
not lie about what was live):
  * Two row shapes are accepted and normalized:
      (a) co-capture sidecar rows (``nqpv_*`` keys) -- the future shape, once the sidecar fields are
          persisted to a queryable column/table (NOT yet wired -- see PERSISTENCE GAP below); and
      (b) plain ``records`` rows (today's queryable shape) -- which carry ``pitl_humanity_prob`` but
          NO cco_tier and NO retina signal.
  * An ABSENT oracle becomes ``None`` (ABSTAIN), never a fabricated value. The calibrated fuse()
    model omits abstaining oracles from the weighted score, so a partial-oracle corpus produces an
    honest partial verdict -- exactly the PILOT regime (PoEP off, camera/screen not live).
  * The controller-lobe retina signal (CONTROLLER_CLEAN/_ANOMALY) is kept as METADATA only. It is
    NOT the screen/coupled lobe that fuse() scores (COUPLED_CLEAN/LIVE_COHERENT/PLAUSIBLE/
    IMPLAUSIBLE); feeding it as fuse()'s ``retina_report`` would correctly abstain, but conflating
    the two vocabularies would be dishonest, so the loader never does it. A genuine coupled/screen
    verdict (live only when a camera witness exists) rides on ``retina_coupled_verdict`` and is the
    only field mapped to fuse()'s ``retina_report``.
  * The LABEL is provenance, supplied by the caller: human positives come from the DB
    (``default_label="human"``); adversary negatives come from the synthesizer (a later step) and
    carry their own ``label``. The loader is label-source-agnostic.

PERSISTENCE GAP (recorded honestly, do not let it rot): the live-loop co-capture hook attaches the
``nqpv_*`` fields to the per-record PITL meta sidecar, but ``main.IngestService.on_record`` only maps
a FIXED set of ``pitl_*`` columns onto the persisted record -- the ``nqpv_*`` keys are NOT among them,
so they are dropped before ``insert_record``. Until that mapping (or a dedicated co-capture table) is
wired, the only queryable source is the ``records`` table, where the single recoverable NQPV oracle
is ``l4_l5_l6_ok`` derived from ``pitl_humanity_prob``. The PILOT therefore runs on this single live
oracle; cco_tier/retina/poep abstain. The loader is built to consume the richer sidecar shape the
moment it is persisted -- no loader change required, only the persistence wiring.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Iterable, Optional

from vapi_bridge.novel_presence_fusion import (
    FusedGamerPresenceProof,
    NovelPresenceFusionOrchestrator,
)

# humanity_prob -> l4_l5_l6_ok proxy floor (matches cocapture_fields_from_pitl_meta in
# novel_presence_fusion: the humanity formula fuses L4/L5/L6/L2B/L2C; >=0.5 is the human side).
HUMANITY_PROXY_FLOOR: float = 0.5

# Provenance labels the harness understands. None = unlabeled (excluded from TAR/FAR).
LABEL_HUMAN = "human"
LABEL_ADVERSARY = "adversary"

# Keys that mark a row as the (future) richer co-capture sidecar shape.
_COCAPTURE_KEYS = (
    "nqpv_cco_tier",
    "nqpv_l4l5l6_ok",
    "nqpv_poep_present",
    "nqpv_retina_controller_signal",
    "nqpv_retina_coupled_verdict",
)


def _as_bool(v: Any, default: Optional[bool] = None) -> Optional[bool]:
    """SQLite/JSON-tolerant tri-state bool: None/'' -> default; 0/1, true/false, yes/no understood."""
    if v is None or v == "":
        return default
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    s = str(v).strip().lower()
    if s in ("1", "true", "yes", "y", "t"):
        return True
    if s in ("0", "false", "no", "n", "f"):
        return False
    return default


def _as_float(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _row_ts_ns(row: dict) -> int:
    """Best-effort ns timestamp from whatever the row carries (sidecar ns, ms, or epoch-sec REAL)."""
    for k in ("nqpv_ts_ns", "ts_ns"):
        v = row.get(k)
        if isinstance(v, (int, float)) and v > 0:
            return int(v)
    ms = row.get("timestamp_ms")
    if isinstance(ms, (int, float)) and ms > 0:
        return int(ms) * 1_000_000
    sec = _as_float(row.get("created_at"))
    if sec and sec > 0:
        return int(sec * 1_000_000_000)
    return 0


@dataclass(frozen=True, slots=True)
class NqpvCorpusRecord:
    """One normalized, labeled corpus row. Every oracle field is tri-state: a value, or None=ABSTAIN.

    ``retina_controller_signal`` is METADATA (controller lobe), never fed to fuse(). Only
    ``retina_coupled_verdict`` (screen/coupled lobe, live only with a camera witness) reaches fuse().
    """
    device_id: str
    record_hash: str
    ts_ns: int
    label: Optional[str]            # "human" / "adversary" / None
    source: str                     # "cocapture" (sidecar shape) | "records" (records-table shape)
    cco_tier: Optional[str] = None
    l4_l5_l6_ok: Optional[bool] = None
    poep_present: Optional[bool] = None
    retina_coupled_verdict: Optional[str] = None     # -> fuse() retina_report (screen lobe)
    retina_controller_signal: Optional[str] = None   # metadata only (controller lobe)
    consent_ok: bool = True
    humanity_prob: Optional[float] = None            # kept for audit / ROC threshold sweeps

    @property
    def binding_ok(self) -> bool:
        return bool(self.device_id) and bool(self.record_hash)

    @property
    def live_oracle_count(self) -> int:
        """How many oracles are non-abstaining (drives whether a row is study-usable at all)."""
        return sum(
            x is not None
            for x in (self.cco_tier, self.l4_l5_l6_ok, self.poep_present, self.retina_coupled_verdict)
        )


def _normalize_row(row: dict, default_label: Optional[str]) -> NqpvCorpusRecord:
    is_cocap = any(k in row for k in _COCAPTURE_KEYS)
    device_id = str(row.get("device_id") or row.get("nqpv_device_id") or "")
    record_hash = str(row.get("record_hash") or row.get("record_hash_hex") or "")

    # l4_l5_l6_ok: prefer the explicit sidecar bool; else derive from persisted humanity_prob.
    hp = _as_float(row.get("pitl_humanity_prob"))
    if hp is None:
        hp = _as_float(row.get("humanity_prob"))
    l4_l5_l6 = _as_bool(row.get("nqpv_l4l5l6_ok"))
    if l4_l5_l6 is None and hp is not None:
        l4_l5_l6 = hp >= HUMANITY_PROXY_FLOOR

    # cco_tier / retina only come from the sidecar; never fabricated from a plain records row.
    cco_tier = row.get("nqpv_cco_tier") or None
    coupled = row.get("nqpv_retina_coupled_verdict") or None
    controller = row.get("nqpv_retina_controller_signal") or None

    return NqpvCorpusRecord(
        device_id=device_id,
        record_hash=record_hash,
        ts_ns=_row_ts_ns(row),
        label=(row.get("label") or row.get("nqpv_label") or default_label),
        source="cocapture" if is_cocap else "records",
        cco_tier=str(cco_tier) if cco_tier else None,
        l4_l5_l6_ok=l4_l5_l6,
        poep_present=_as_bool(row.get("nqpv_poep_present")),  # None abstain (PoEP off-by-default)
        retina_coupled_verdict=str(coupled) if coupled else None,
        retina_controller_signal=str(controller) if controller else None,
        consent_ok=bool(_as_bool(row.get("nqpv_consent_ok"), default=True)),
        humanity_prob=hp,
    )


def load_from_rows(
    rows: Iterable[dict],
    *,
    default_label: Optional[str] = None,
    require_binding: bool = True,
) -> list[NqpvCorpusRecord]:
    """Normalize injected DB/sidecar row-dicts into corpus records (pure; no I/O).

    ``require_binding`` (default True) drops rows missing device_id/record_hash -- an unbound row
    would only ever fuse to UNVERIFIABLE and pollute the ROC, so it is excluded at load time.
    """
    out: list[NqpvCorpusRecord] = []
    for row in rows:
        rec = _normalize_row(row, default_label)
        if require_binding and not rec.binding_ok:
            continue
        out.append(rec)
    return out


def to_fuse_inputs(rec: NqpvCorpusRecord) -> dict:
    """Map a corpus record to ``NovelPresenceFusionOrchestrator.fuse()`` kwargs.

    cco_tier -> a minimal cco_report (fuse reads ``.tier``); retina_coupled_verdict -> retina_report
    (screen lobe ONLY; the controller-lobe signal is deliberately NOT mapped). Abstaining oracles
    pass through as None so fuse() omits them from the weighted score.
    """
    return {
        "device_id": rec.device_id or None,
        "record_hash": rec.record_hash or None,
        "cco_report": SimpleNamespace(tier=rec.cco_tier, commitment="") if rec.cco_tier else None,
        "retina_report": rec.retina_coupled_verdict or None,
        "poep_present": rec.poep_present,
        "l4_l5_l6_ok": rec.l4_l5_l6_ok,
        "consent_ok": rec.consent_ok,
        "timestamp_ns": rec.ts_ns,
    }


def fuse_record(
    rec: NqpvCorpusRecord,
    orchestrator: Optional[NovelPresenceFusionOrchestrator] = None,
    *,
    weights: Optional[dict[str, float]] = None,
    threshold: Optional[float] = None,
) -> FusedGamerPresenceProof:
    """Convenience: fuse one corpus record with optional study-injected weights/threshold."""
    orch = orchestrator or NovelPresenceFusionOrchestrator()
    return orch.fuse(weights=weights, threshold=threshold, **to_fuse_inputs(rec))


# --- I/O boundary (the ONLY store-touching function) -------------------------------------------

def fetch_human_rows(store: Any, *, limit: int = 500, device_id: Optional[str] = None) -> list[dict]:
    """Pull the queryable human-capture rows from the store (reuses the tested get_recent_records).

    These are real consented captures -> the caller labels them ``LABEL_HUMAN``. Until the nqpv_*
    sidecar is persisted (see PERSISTENCE GAP in the module docstring), these rows carry only
    ``pitl_humanity_prob`` as a live oracle; everything else abstains.
    """
    return store.get_recent_records(limit=limit, device_id=device_id)


def load_human_corpus_from_store(
    store: Any, *, limit: int = 500, device_id: Optional[str] = None
) -> list[NqpvCorpusRecord]:
    """End-to-end convenience: fetch human rows from the store and normalize them, labeled human."""
    return load_from_rows(
        fetch_human_rows(store, limit=limit, device_id=device_id),
        default_label=LABEL_HUMAN,
    )
