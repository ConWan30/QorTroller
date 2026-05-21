"""QorTroller L9 — gamer-facing verification card (self-contained HTML).

Renders one session's causal-presence result as a standalone HTML page the gamer can
open/screenshot: the presence verdict, the coupling evidence, the negative-control
honesty check, and the PoCP commitment hash. This is the ZKBA-READY artifact — it
carries a reproducible commitment, but it is NOT itself a zero-knowledge proof; the
real ZKBA proof is minted later through the governed ceremony. Labelled honestly.

Pure string templating (inline CSS, no deps). Palette mirrors the dashboard:
void-black + electric orange + cyan.
"""
from __future__ import annotations

_VERDICT_COLOR = {
    "PRESENT": "#00e0c0",            # cyan-green: causal human presence
    "REVIEW_LOW_COUPLING": "#ff8a00",  # orange: inconclusive, review
    "INSUFFICIENT_AIM": "#8a8f98",   # grey: not enough aiming to decide
    "DECOUPLED": "#ff3b30",          # red: motion not explained by input
}

_VERDICT_TEXT = {
    "PRESENT": "Causal human presence detected — your input drove the on-screen aim.",
    "REVIEW_LOW_COUPLING": "Low coupling this session — inconclusive, review.",
    "INSUFFICIENT_AIM": "Not enough aiming activity to decide.",
    "DECOUPLED": "On-screen aim was not explained by your input.",
}


def _row(k: str, v: str) -> str:
    return (f'<tr><td class="k">{k}</td><td class="v">{v}</td></tr>')


def render_card(*, player: str, session_id: str, label: str, verdict: str,
                coupling: float, lag_ms: float, negative_control: float,
                neg_margin: float, decoupled_energy: float, n_samples: int,
                commitment: str, ts_iso: str) -> str:
    """Return a self-contained HTML verification card for one session."""
    color = _VERDICT_COLOR.get(verdict, "#8a8f98")
    summary = _VERDICT_TEXT.get(verdict, verdict)
    rows = "".join([
        _row("Player", player),
        _row("Session", session_id),
        _row("Label", label),
        _row("Coupling score", f"{coupling:.3f}"),
        _row("Negative control", f"{negative_control:.3f} (collapsed = causality is real)"),
        _row("Coupling margin", f"{neg_margin:+.3f}"),
        _row("Causal lag", f"{lag_ms:.0f} ms"),
        _row("Decoupled energy", f"{decoupled_energy:.3f}"),
        _row("Samples", str(n_samples)),
        _row("Captured", ts_iso),
    ])
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>QorTroller — Proof of Causal Presence</title>
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
  .verdict {{ display:flex; align-items:center; gap:12px; padding:18px 24px;
             border-bottom:1px solid #20242e; }}
  .dot {{ width:14px; height:14px; border-radius:50%; background:var(--accent);
         box-shadow:0 0 14px var(--accent); }}
  .verdict .lbl {{ font-size:18px; font-weight:600; color:var(--accent); }}
  .verdict .sub {{ color:var(--dim); font-size:12px; }}
  table {{ width:100%; border-collapse:collapse; }}
  td {{ padding:10px 24px; border-bottom:1px solid #181c24; }}
  td.k {{ color:var(--dim); width:40%; }} td.v {{ text-align:right; }}
  .commit {{ padding:16px 24px; }}
  .commit .k {{ color:var(--dim); font-size:11px; text-transform:uppercase; letter-spacing:.12em; }}
  .commit code {{ display:block; margin-top:6px; word-break:break-all; color:#00e0c0; font-size:12px; }}
  .note {{ padding:16px 24px; color:var(--dim); font-size:11px; border-top:1px solid #20242e; }}
  .note b {{ color:var(--ink); }}
</style></head>
<body><div class="card">
  <div class="hd"><div class="brand">QorTroller · V.A.P.I.</div>
    <h1>Proof of Causal Presence</h1></div>
  <div class="verdict"><span class="dot"></span>
    <div><div class="lbl">{verdict}</div><div class="sub">{summary}</div></div></div>
  <table>{rows}</table>
  <div class="commit"><div class="k">PoCP commitment (SHA-256)</div><code>{commitment}</code></div>
  <div class="note">
    <b>What this proves:</b> a human's controller input causally produced the on-screen
    camera motion at a human reaction lag, and that link collapses under a time-shuffle
    negative control. <b>What it does not (yet) prove:</b> this is a reproducible
    commitment, <b>not</b> a zero-knowledge proof — the ZKBA proof is minted later
    through the governed ceremony. Detects full aim-injection / camera takeover, not a
    subtle partial assist. Measured under Remote Play latency. Your data, your control.
  </div>
</div></body></html>"""
