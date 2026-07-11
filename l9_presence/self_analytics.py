"""UC-15 -- Self-analytics view (qortroller-self-analytics-v0).

The inner ring of the data economy: the gamer consuming THEIR OWN verified history. A single
self-contained HTML page rendered from the two verified artifacts below it -- the play-resume
(UC-4) and the skill-strata report (UC-2) -- citing both by path + SHA-256 with the re-verify
commands printed in the footer. No bridge, no network, no JS dependencies (charts are inline
SVG); PROVING GROUND design language (steel -> ember -> struck gold).

CEILING (test-pinned, rendered as a visible banner): SELF-VIEW ONLY -- the page describes one
gamer's own sessions; advisory; counts and verdicts only; no rank; cross-player comparison
re-enters the population gate and is structurally absent (single-subject input by design).

Pure: build_self_analytics_html(resume, strata, refs) -> str. I/O in scripts/build_self_analytics.py.
"""
from __future__ import annotations

import html as _html
from typing import Optional

SCHEMA = "qortroller-self-analytics-v0"

CEILING_BANNER = ("SELF-VIEW ONLY — your own verified sessions · advisory · counts and verdicts "
                  "only · no rank claims · cross-player comparison is structurally absent")

_BAND_COLORS = {
    "AUTHORED_HIGH_DENSITY": "#e8a33d",   # struck gold
    "AUTHORED_STANDARD": "#c96f2e",       # ember
    "AUTHORED_DEFERRED": "#9a5a2b",       # deep ember
    "PRESENCE_ONLY": "#5d6672",           # steel
    "UNGRADED": "#3d434b",                # dark steel
    "EXCLUDED_INTEGRITY": "#6e2f2f",      # oxblood
}


def _esc(v) -> str:
    return _html.escape(str(v if v is not None else "—"), quote=True)


def _bar_svg(rows: list, width: int = 860, bar_h: int = 16, gap: int = 6) -> str:
    """Inline-SVG horizontal bars: authored-best per session, colored by band. No JS."""
    if not rows:
        return "<p class='mut'>no sessions</p>"
    peak = max((r["best"] for r in rows), default=0) or 1
    h = len(rows) * (bar_h + gap) + gap
    parts = [f"<svg viewBox='0 0 {width} {h}' width='100%' role='img' "
             f"aria-label='authored kills per session'>"]
    label_w, val_w = 300, 40
    plot_w = width - label_w - val_w
    for i, r in enumerate(rows):
        y = gap + i * (bar_h + gap)
        w = max(2, int(plot_w * r["best"] / peak)) if r["best"] else 2
        color = _BAND_COLORS.get(r["band"], "#3d434b")
        parts.append(f"<text x='{label_w - 8}' y='{y + bar_h - 4}' text-anchor='end' "
                     f"class='svgt'>{_esc(r['session'][:40])}</text>")
        parts.append(f"<rect x='{label_w}' y='{y}' width='{w}' height='{bar_h}' rx='2' "
                     f"fill='{color}'/>")
        parts.append(f"<text x='{label_w + w + 6}' y='{y + bar_h - 4}' class='svgt gold'>"
                     f"{r['best']}</text>")
    parts.append("</svg>")
    return "".join(parts)


def build_self_analytics_html(resume: dict, strata: dict, *, resume_ref: dict,
                              strata_ref: dict, generated_at: str = "") -> str:
    """Render the page. `*_ref` = {path, sha256} for the citation footer. Pure."""
    strata_by_session = {s.get("session"): s for s in strata.get("sessions", [])}
    rows = []
    for r in resume.get("sessions", []):
        live = int((r.get("kas") or {}).get("authored_kills") or 0)
        deferred = int((r.get("deferred") or {}).get("deferred_authored") or 0)
        st = strata_by_session.get(r.get("session")) or {}
        rows.append({"session": str(r.get("session")), "live": live, "deferred": deferred,
                     "best": max(live, deferred),
                     "kas": (r.get("kas") or {}).get("verdict"),
                     "posp": (r.get("posp") or {}).get("verdict"),
                     "band": st.get("band", "UNGRADED"),
                     "density": st.get("density_kpm")})
    t = resume.get("totals") or {}
    dist = strata.get("distribution") or {}
    handle = resume.get("handle") or "(no handle)"

    tiles = [
        ("sessions", t.get("sessions", 0)),
        ("PoSP synchronized", t.get("posp_synchronized", 0)),
        ("authored — live", t.get("authored_kills_live", 0)),
        ("authored — deferred", t.get("authored_kills_deferred", 0)),
        ("authored — best", t.get("authored_kills_best", 0)),
        ("corpus-eligible", strata.get("corpus_eligible_sessions", 0)),
    ]
    tile_html = "".join(
        f"<div class='tile'><div class='num'>{_esc(v)}</div><div class='lbl'>{_esc(k)}</div></div>"
        for k, v in tiles)
    dist_html = "".join(
        f"<div class='band'><span class='chip' style='background:{_BAND_COLORS.get(b, '#3d434b')}'>"
        f"</span>{_esc(b)}<span class='gold'>&nbsp;{int(n)}</span></div>"
        for b, n in dist.items() if int(n or 0) > 0)
    trow = "".join(
        f"<tr><td>{_esc(r['session'])}</td><td>{_esc(r['kas'])}</td>"
        f"<td class='r'>{r['live']}</td><td class='r'>{r['deferred']}</td>"
        f"<td class='r gold'>{r['best']}</td>"
        f"<td class='r'>{_esc(r['density'])}</td>"
        f"<td><span class='chip' style='background:{_BAND_COLORS.get(r['band'], '#3d434b')}'></span>"
        f"{_esc(r['band'])}</td><td>{_esc(r['posp'])}</td></tr>"
        for r in rows)

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>QorTroller — Self-Analytics — {_esc(handle)}</title>
<style>
  :root {{ --bg:#0e0f11; --panel:#16181c; --line:#262a30; --txt:#d7d3cc; --mut:#7b8290;
           --gold:#e8a33d; --ember:#c96f2e; }}
  body {{ background:var(--bg); color:var(--txt); margin:0;
          font-family:'Hanken Grotesk','Archivo',system-ui,sans-serif; }}
  .wrap {{ max-width:960px; margin:0 auto; padding:28px 20px 60px; }}
  h1 {{ font-family:'Archivo',system-ui,sans-serif; letter-spacing:.02em; margin:0 0 2px;
        font-size:26px; }}
  h1 .gold {{ color:var(--gold); }}
  h2 {{ font-size:13px; letter-spacing:.14em; text-transform:uppercase; color:var(--mut);
        margin:34px 0 10px; }}
  .ceiling {{ border:1px solid var(--ember); background:#1a130c; color:#e6b98a; padding:10px 14px;
              border-radius:6px; font-size:12.5px; letter-spacing:.03em; margin:14px 0 4px; }}
  .tiles {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(130px,1fr)); gap:10px;
            margin-top:14px; }}
  .tile {{ background:var(--panel); border:1px solid var(--line); border-radius:8px;
           padding:12px 14px; }}
  .tile .num {{ font-family:'Martian Mono',ui-monospace,monospace; font-size:22px;
                color:var(--gold); }}
  .tile .lbl {{ font-size:11px; color:var(--mut); letter-spacing:.08em; text-transform:uppercase;
                margin-top:4px; }}
  .bands {{ display:flex; flex-wrap:wrap; gap:14px; font-size:13px; }}
  .band {{ display:flex; align-items:center; gap:6px; }}
  .chip {{ display:inline-block; width:10px; height:10px; border-radius:2px; }}
  .gold {{ color:var(--gold); }}
  .mut {{ color:var(--mut); }}
  table {{ width:100%; border-collapse:collapse; font-size:12.5px; margin-top:6px; }}
  th {{ text-align:left; color:var(--mut); font-weight:600; letter-spacing:.06em;
        text-transform:uppercase; font-size:10.5px; padding:6px 8px;
        border-bottom:1px solid var(--line); }}
  td {{ padding:6px 8px; border-bottom:1px solid var(--line); }}
  td.r {{ text-align:right; font-family:'Martian Mono',ui-monospace,monospace; }}
  .svgt {{ font-size:10px; fill:var(--mut); font-family:ui-monospace,monospace; }}
  .svgt.gold {{ fill:var(--gold); }}
  footer {{ margin-top:36px; border-top:1px solid var(--line); padding-top:14px; font-size:11.5px;
            color:var(--mut); line-height:1.7; }}
  footer code {{ color:#a8b0bd; background:var(--panel); padding:1px 5px; border-radius:4px; }}
</style></head><body><div class="wrap">
  <h1>QORTROLLER <span class="gold">/ SELF-ANALYTICS</span></h1>
  <div class="mut" style="font-size:12.5px">{_esc(handle)} · generated {_esc(generated_at)} · {SCHEMA}</div>
  <div class="ceiling">{_esc(CEILING_BANNER)}</div>

  <h2>Verified totals</h2>
  <div class="tiles">{tile_html}</div>

  <h2>Authored kills per session (best of live / deferred)</h2>
  {_bar_svg(rows)}

  <h2>Demonstration bands (sessions, not rank)</h2>
  <div class="bands">{dist_html}</div>

  <h2>Sessions</h2>
  <table><thead><tr><th>session</th><th>kas verdict</th><th>live</th><th>def</th><th>best</th>
  <th>kpm</th><th>band</th><th>posp</th></tr></thead><tbody>{trow}</tbody></table>

  <footer>
    Rendered from two verified artifacts — re-check them yourself:<br>
    resume&nbsp; <code>{_esc(resume_ref.get('path'))}</code> sha256 <code>{_esc(resume_ref.get('sha256'))}</code><br>
    strata&nbsp; <code>{_esc(strata_ref.get('path'))}</code> sha256 <code>{_esc(strata_ref.get('sha256'))}</code><br>
    verify: <code>python scripts/build_play_resume.py verify --resume {_esc(resume_ref.get('path'))}</code>
    &nbsp;·&nbsp; <code>python scripts/build_skill_strata.py verify --report {_esc(strata_ref.get('path'))}</code><br>
    Summary-integrity + re-derivation only; the underlying cryptography is each artifact's own
    verifier (KAS / PoSP / deferred / PORT-CERT). This page makes no claim those tools do not.
  </footer>
</div></body></html>
"""


def validate_self_view(resume: dict) -> Optional[str]:
    """Structural self-view guard: exactly one handle context, no comparison fields. Returns an
    error string when the input smells multi-subject (fail-closed at the runner)."""
    for key in ("players", "leaderboard", "opponents", "percentile", "rank"):
        if key in resume:
            return f"multi-subject/comparison field {key!r} present — self-view only"
    return None
