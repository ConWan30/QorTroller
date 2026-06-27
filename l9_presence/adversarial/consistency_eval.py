"""Evaluate the fusion over labeled sessions: 5x6 confusion + honest metrics.

Measures TWO distinct things and refuses to conflate them (the plan's critical
finding):
  1. Machine-assist CATCH + false-ACCUSATION (categorical, on synthetic data).
  2. Contextual LIFT: fusion vs retina-alone vs presence-alone per class -- where
     the second oracle actually adds information.
It explicitly does NOT claim to solve the cheat-vs-pro-skill boundary; that
is a retina-axis ROC question gated on real PRO_SKILL capture (Phase 2).
"""
from __future__ import annotations

from .session_class import SessionClass
from .signal_adapter import evaluate_window, presence_alone_security, retina_alone_security

_VERDICTS = [
    "CONSISTENT_HUMAN",
    "CONSISTENT_INACTIVE",
    "INCONSISTENT_PRESENCE_WITHOUT_AUTHENTIC_TRAJECTORY",
    "INCONSISTENT_AUTHENTIC_TRAJECTORY_WITHOUT_PRESENCE",
    "INDETERMINATE",
    "UNVERIFIABLE",
]
_MACHINE_ASSIST_VERDICT = "INCONSISTENT_PRESENCE_WITHOUT_AUTHENTIC_TRAJECTORY"
_GENUINE_HUMAN_CLASSES = (SessionClass.HUMAN_CLEAN, SessionClass.PRO_SKILL)


def _rate(num: int, den: int) -> float:
    return round(num / den, 4) if den else 0.0


def _params_block(params) -> dict:
    keys = ("retina_tpr_cheat", "retina_fpr_proskill", "retina_fpr_clean",
            "bot_implausible_rate", "relay_presence_rate", "human_presence_pass")
    return {k: getattr(params, k, None) for k in keys}


def run_experiment(sessions: list, params=None, *, provenance: str = "synthetic") -> dict:
    confusion = {c.value: {v: 0 for v in _VERDICTS} for c in SessionClass}
    n_windows = {c.value: 0 for c in SessionClass}
    sec = {"fusion": {}, "retina_alone": {}, "presence_alone": {}}
    for d in sec.values():
        for c in SessionClass:
            d[c.value] = 0

    for s in sessions:
        cl = s.class_label.value
        for w in s.windows:
            n_windows[cl] += 1
            r = evaluate_window(w)
            confusion[cl][r.verdict.value] += 1
            if r.security_flag:
                sec["fusion"][cl] += 1
            if retina_alone_security(w):
                sec["retina_alone"][cl] += 1
            if presence_alone_security(w):
                sec["presence_alone"][cl] += 1

    aa = SessionClass.HUMAN_INPUT_MACRO.value
    catch_rate = _rate(confusion[aa][_MACHINE_ASSIST_VERDICT], n_windows[aa])

    false_accusation = {
        c.value: _rate(sec["fusion"][c.value], n_windows[c.value]) for c in _GENUINE_HUMAN_CLASSES
    }
    contextual = {
        c.value: {
            "fusion": _rate(sec["fusion"][c.value], n_windows[c.value]),
            "retina_alone": _rate(sec["retina_alone"][c.value], n_windows[c.value]),
            "presence_alone": _rate(sec["presence_alone"][c.value], n_windows[c.value]),
        }
        for c in SessionClass
    }

    return {
        "schema": "vapi-consistency-experiment-v1",
        "provenance": provenance,
        "provisional": provenance != "real",
        "params": _params_block(params),
        "n_windows": n_windows,
        "confusion": confusion,
        "metrics": {
            "machine_assist_catch_rate": catch_rate,
            "false_accusation_rate": false_accusation,
            "contextual_security_rate": contextual,
        },
    }


def to_markdown(result: dict, date: str) -> str:
    p = result["params"]
    m = result["metrics"]
    lines = []
    real = result.get("provenance") == "real"
    if real:
        lines.append(f"# Consistency Experiment — REAL CAPTURE — {date}")
        lines.append("")
        lines.append("**Provenance:** real co-captured sessions. **N=1 single-subject** scope per the "
                     "protocol §0: this measures THIS operator's retina FPR/TPR only. A single subject "
                     "can FALSIFY the gate (KILL) but CANNOT VALIDATE it (no population claim). Best "
                     "outcome here is 'not killed — proceed to multi-subject capture.'")
    else:
        lines.append(f"# Consistency Experiment — SYNTHETIC (provisional) — {date}")
        lines.append("")
        lines.append("**Provenance:** synthetic, parameterised model of per-class oracle behaviour. "
                     "This is a SENSITIVITY ANALYSIS over the retina-axis unknowns, NOT real capture. "
                     "Real values (esp. `retina_fpr_proskill`) require Phase 2.")
    lines.append("")
    lines.append("## Parameters (the load-bearing unknowns are the first two)")
    lines.append("")
    lines.append("| param | value |")
    lines.append("|---|---|")
    for k, v in p.items():
        lines.append(f"| `{k}` | {v} |")
    lines.append("")
    lines.append("## Headline metrics")
    lines.append("")
    lines.append(f"- **Machine-assist catch rate** (HUMAN_INPUT_MACRO → security): "
                 f"**{m['machine_assist_catch_rate']}**")
    lines.append("- **False-accusation rate** (genuine humans → any security verdict):")
    for cls, r in m["false_accusation_rate"].items():
        prov = " *(PROVISIONAL — synthetic pro-skill is the weakest proxy; needs real capture)*" \
            if cls == "PRO_SKILL" else ""
        lines.append(f"  - {cls}: **{r}**{prov}")
    lines.append("")
    lines.append("## 5×6 confusion matrix (per window)")
    lines.append("")
    header = "| class \\ verdict | " + " | ".join(v.replace("INCONSISTENT_", "INC_") for v in _VERDICTS) + " |"
    lines.append(header)
    lines.append("|" + "---|" * (len(_VERDICTS) + 1))
    for c in SessionClass:
        row = result["confusion"][c.value]
        lines.append(f"| {c.value} | " + " | ".join(str(row[v]) for v in _VERDICTS) + " |")
    lines.append("")
    lines.append("## Contextual lift — security-accusation rate by detector")
    lines.append("")
    lines.append("| class | fusion | retina-alone | presence-alone |")
    lines.append("|---|---|---|---|")
    for c in SessionClass:
        cr = m["contextual_security_rate"][c.value]
        lines.append(f"| {c.value} | {cr['fusion']} | {cr['retina_alone']} | {cr['presence_alone']} |")
    lines.append("")
    lines.append("## Honest reading")
    lines.append("")
    lines.append("- The fusion's **value is contextual disambiguation**: it separates "
                 "no-human (BOT/relay → `*_WITHOUT_PRESENCE` / INDETERMINATE) from genuine "
                 "human+anomaly (`*_PRESENCE_WITHOUT_AUTHENTIC_TRAJECTORY`) — a distinction "
                 "retina-alone (flags any implausible) and presence-alone (misses any PRESENT cheat) "
                 "cannot make.")
    lines.append("- The fusion does **NOT** rescue the cheat-vs-pro-skill boundary: both are "
                 "PRESENT × (retina-judged) IMPLAUSIBLE, so the false-accusation rate on PRO_SKILL "
                 "EQUALS `retina_fpr_proskill` by construction. The whole question reduces to "
                 "retina's trajectory ROC on elite play — measurable only in Phase 2.")
    lines.append("- **Decision rule status:** the disagreement signal separates the *contextual* "
                 "classes here; whether it separates the cheat from real pro-skill is "
                 "**[UNVALIDATED]** and gated on real `PRO_SKILL` capture.")
    return "\n".join(lines) + "\n"
