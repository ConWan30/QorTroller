"""Build a local observation envelope and its clock commitment."""
from __future__ import annotations
import hashlib, json
from dataclasses import dataclass, field
from typing import Any
from .sanitize import strip_truth_leaks

def _canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")

@dataclass(frozen=True)
class Tick:
    clock_ns: int
    frame_seq: int
    ticket_id: str | None
    ticket_kind: str | None
    hid_edge: str | None
    score_digits: str | None
    score_vlm_locked: bool = False
    def as_commit_triple(self) -> dict:
        return {"clock_ns": int(self.clock_ns), "frame_seq": int(self.frame_seq), "ticket_id": self.ticket_id, "ticket_kind": self.ticket_kind, "hid_edge": self.hid_edge, "score_digits": self.score_digits if self.score_vlm_locked else None}

@dataclass
class ObservationEnvelope:
    schema: str
    session_id: str
    plane: str
    title_plane: str
    hid_on_console: bool
    ticks: list[dict]
    sidecar_hashes: dict[str, str]
    clock_commitment: str
    extras: dict = field(default_factory=dict)
    def to_dict(self) -> dict:
        body = {"schema": self.schema, "session_id": self.session_id, "plane": self.plane, "title_plane": self.title_plane, "hid_on_console": self.hid_on_console, "ticks": self.ticks, "sidecar_hashes": self.sidecar_hashes, "clock_commitment": self.clock_commitment}
        if self.extras:
            body["extras"] = self.extras
        return body

SCHEMA = "qoresence.observation-envelope.v0"

def clock_commitment(session_id: str, ticks: list[dict], sidecar_hashes: dict[str, str]) -> str:
    return "sha256:" + hashlib.sha256(_canonical({"session_id": session_id, "sidecar_hashes": sidecar_hashes, "ticks": ticks})).hexdigest()

def build_envelope(*, session_id: str, ticks: list[Tick], sidecars: dict[str, bytes] | None = None, title_plane: str = "observation", hid_on_console: bool = True, extras: dict | None = None) -> ObservationEnvelope:
    if not session_id:
        raise ValueError("session_id required")
    if title_plane != "observation":
        raise ValueError("envelope title_plane must stay observation")
    clean_ticks = [strip_truth_leaks(t.as_commit_triple()) for t in ticks]
    sidecar_hashes = {n: "sha256:" + hashlib.sha256(r).hexdigest() for n, r in (sidecars or {}).items()}
    return ObservationEnvelope(SCHEMA, session_id, "observation", title_plane, hid_on_console, clean_ticks, sidecar_hashes, clock_commitment(session_id, clean_ticks, sidecar_hashes), strip_truth_leaks(extras or {}))

def envelope_from_recap(recap: dict) -> ObservationEnvelope:
    recap = strip_truth_leaks(recap)
    session_id = recap.get("session_id") or recap.get("id")
    if not session_id:
        raise ValueError("recap missing session_id")
    ticks = []
    for raw in recap.get("ticks") or recap.get("civif") or []:
        kind = raw.get("ticket_kind")
        if kind not in ("coupling", "confirm", None):
            kind = None
        ticks.append(Tick(int(raw.get("clock_ns") or 0), int(raw.get("frame_seq") or raw.get("seq") or 0), raw.get("ticket_id"), kind, raw.get("hid_edge") or raw.get("button"), raw.get("score_digits") or raw.get("score"), bool(raw.get("score_vlm_locked") or raw.get("board_locked"))))
    prehashed = {}
    for key in ("buttons", "coupling", "otel", "clip"):
        digest = recap.get(f"{key}_sha256")
        if isinstance(digest, str):
            prehashed[key] = digest if digest.startswith("sha256:") else f"sha256:{digest}"
    env = build_envelope(session_id=str(session_id), ticks=ticks, hid_on_console=bool(recap.get("hid_on_console", True)), extras={"prehashed_sidecars": prehashed} if prehashed else None)
    if prehashed:
        merged = dict(env.sidecar_hashes); merged.update(prehashed)
        env.sidecar_hashes = merged
        env.clock_commitment = clock_commitment(env.session_id, env.ticks, merged)
    return env
