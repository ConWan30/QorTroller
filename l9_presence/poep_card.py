"""QorTroller PoEP P3 — gamer-facing verification card (self-contained HTML).

Renders one PoEP verdict the gamer can open/screenshot: live human + certified device,
proven by a nonce-fresh reflex on the adaptive-trigger channel. Carries the born-PQ
(SHA-256) commitment. Honestly labelled: a reproducible commitment, NOT a ZK proof, and
NOT activated (L6B N>=50 + governance, P4). Pure string templating; no deps.
"""
from __future__ import annotations

_COLOR = {"PRESENT": "#00e0c0", "REJECT": "#ff3b30",
          "calibration_incomplete": "#8a8f98"}
_SUMMARY = {
    "PRESENT": "Live human on the certified device — reflex in the human band, device-auth OK.",
    "REJECT": "Did not pass — reflex outside the human band and/or device-auth failed.",
    "calibration_incomplete": "Model not yet calibrated (L6B N>=50) — no verdict issued.",
}


def _row(k: str, v: str) -> str:
    return f'<tr><td class="k">{k}</td><td class="v">{v}</td></tr>'


def render_poep_card(*, player: str, device_id: str, verdict: str, latency_ms,
                     band, liveness_pass: bool, device_auth_pass: bool,
                     device_auth_score, commitment: str, ts_iso: str) -> str:
    color = _COLOR.get(verdict, "#8a8f98")
    summary = _SUMMARY.get(verdict, verdict)
    band_s = f"{band[0]:.0f}–{band[1]:.0f} ms" if band else "—"
    rows = "".join([
        _row("Player", player),
        _row("Device", device_id),
        _row("Liveness (reaction)", f"{latency_ms:.0f} ms" if latency_ms is not None else "—"),
        _row("Human reflex band", band_s),
        _row("Liveness pass", "yes" if liveness_pass else "no"),
        _row("Device-auth pass", f"{'yes' if device_auth_pass else 'no'}"
             f"{f' (score {device_auth_score})' if device_auth_score is not None else ''}"),
        _row("Issued", ts_iso),
    ])
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>QorTroller — Proof of Embodied Presence</title>
<style>
  :root {{ --bg:#08090c; --panel:#11141a; --ink:#e7e9ee; --dim:#8a8f98; --accent:{color}; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
         font:14px/1.5 ui-monospace,Menlo,Consolas,monospace; padding:32px; }}
  .card {{ max-width:680px; margin:0 auto; background:var(--panel);
          border:1px solid #20242e; border-radius:14px; overflow:hidden; }}
  .hd {{ padding:20px 24px; border-bottom:1px solid #20242e; }}
  .hd .brand {{ color:var(--dim); letter-spacing:.18em; font-size:11px; text-transform:uppercase; }}
  .hd h1 {{ margin:6px 0 0; font-size:20px; }}
  .verdict {{ display:flex; align-items:center; gap:12px; padding:18px 24px; border-bottom:1px solid #20242e; }}
  .dot {{ width:14px; height:14px; border-radius:50%; background:var(--accent); box-shadow:0 0 14px var(--accent); }}
  .verdict .lbl {{ font-size:18px; font-weight:600; color:var(--accent); }}
  .verdict .sub {{ color:var(--dim); font-size:12px; }}
  table {{ width:100%; border-collapse:collapse; }}
  td {{ padding:10px 24px; border-bottom:1px solid #181c24; }}
  td.k {{ color:var(--dim); width:46%; }} td.v {{ text-align:right; }}
  .commit {{ padding:16px 24px; }}
  .commit .k {{ color:var(--dim); font-size:11px; text-transform:uppercase; letter-spacing:.12em; }}
  .commit code {{ display:block; margin-top:6px; word-break:break-all; color:#00e0c0; font-size:12px; }}
  .note {{ padding:16px 24px; color:var(--dim); font-size:11px; border-top:1px solid #20242e; }}
  .note b {{ color:var(--ink); }}
</style></head>
<body><div class="card">
  <div class="hd"><div class="brand">QorTroller · V.A.P.I.</div>
    <h1>Proof of Embodied Presence</h1></div>
  <div class="verdict"><span class="dot"></span>
    <div><div class="lbl">{verdict}</div><div class="sub">{summary}</div></div></div>
  <table>{rows}</table>
  <div class="commit"><div class="k">PoEP commitment (SHA-256, post-quantum-safe)</div><code>{commitment}</code></div>
  <div class="note">
    <b>What this proves:</b> a live human (reflex in the empirical human band) operating the
    certified device (adaptive-trigger force-response), responding to a fresh nonce (anti-replay).
    <b>Layers:</b> reaction-band = liveness floor; device-auth = real-Edge physics; nonce = freshness.
    <b>Limits:</b> a reproducible commitment, <b>not</b> a zero-knowledge proof (real ZKBA later);
    born post-quantum (SHA-256 commit; hybrid ML-DSA-65 credential signing once IoTeX's PQ precompile
    ships). <b>Not activated</b> — calibration + governance (L6B N≥50, two-key) gate issuance. Your device, your data.
  </div>
</div></body></html>"""
