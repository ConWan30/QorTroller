"""
Live end-to-end exercise of the QorTroller Daemon Tier 1-3 self-honesty gates.

This is NOT a unit test. It instantiates the real QorTrollerBrain and drives the
real _execute_tool fabrication wrapper + finalize_plan READY gate + adversarial_verify
on real files. Temp DBs are used so the genuine AGENT-COMMIT chain / rate-limiter
state is not polluted.

Verdicts printed are ASCII-only (Windows console).
"""
import os
import sys
import tempfile
import shutil

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO_ROOT)

import qortroller_daemon as qd  # noqa: E402
from _daemon_tools_schema import GovernanceHardStop, DaemonIdentity  # noqa: E402

_tmp = tempfile.mkdtemp(prefix="daemon_gate_live_")
_results = []


def _finalize_capture(brain, plan_name, verdict):
    """finalize_plan raises GovernanceHardStop on success. Return the rendered
    REVIEW text (where the gate writes the (possibly downgraded) verdict)."""
    try:
        ret = brain._execute_tool(
            "finalize_plan",
            {"plan_name": plan_name, "summary": "live gate check", "verdict": verdict},
        )
        # No hard stop -> something short-circuited (rate-limit etc.)
        return {"raised": False, "ret": ret, "review": ""}
    except GovernanceHardStop as hs:
        review_path = getattr(hs, "review_path", None)
        text = ""
        if review_path and os.path.isfile(review_path):
            text = open(review_path, encoding="utf-8", errors="replace").read()
        return {"raised": True, "ret": None, "review": text, "review_path": review_path}


def _record(name, ok, detail):
    _results.append((name, ok, detail))
    flag = "PASS" if ok else "FAIL"
    print(f"  [{flag}] {name}: {detail}", flush=True)


def _repoint_temp_state():
    """Repoint module-global DBs to temp so the real chain is untouched."""
    qd.SQLITE_DB_PATH = os.path.join(_tmp, "agent_memory.db")
    qd._RATE_LIMITER = qd.RateLimiter(os.path.join(_tmp, "rl.db"))
    qd._DAEMON_COMMIT_CHAIN = qd.DaemonCommitChain(os.path.join(_tmp, "chain.db"))
    # Identity is real (signs the commitment); key already exists outside repo.
    try:
        qd._DAEMON_IDENTITY = DaemonIdentity(qd._DAEMON_KEY_PATH)
    except Exception as e:
        print(f"  [WARN] identity init failed ({e}); AGENT-COMMIT block will no-op", flush=True)


def _cleanup_artifacts(rel_paths):
    for rel in rel_paths:
        p = os.path.normpath(os.path.join(REPO_ROOT, rel))
        if os.path.isfile(p):
            try:
                os.remove(p)
            except OSError:
                pass
    # Remove REVIEW_*_gate_live* packages this run produced
    pdir = os.path.join(REPO_ROOT, "docs", "_daemon_proposals")
    if os.path.isdir(pdir):
        for f in os.listdir(pdir):
            if f.startswith("REVIEW_") and "gate_live" in f:
                try:
                    os.remove(os.path.join(pdir, f))
                except OSError:
                    pass


def main():
    print("=" * 64)
    print("  DAEMON TIER 1-3 GATE LIVE EXERCISE (real code paths)")
    print("=" * 64)
    _repoint_temp_state()

    bad_rel = "docs/_daemon_proposals/_gate_live_bad.py"
    good_rel = "docs/_daemon_proposals/_gate_live_good.py"

    # ---- CASE A: Tier 1.1 fabrication detection on a syntactically invalid .py ----
    print("\n[CASE A] Fabricated artifact -> verify_artifact must flag + READY must block")
    brain_a = qd.QorTrollerBrain(qd.MemoryStore(qd.SQLITE_DB_PATH))
    bad_content = "def broken(:\n    return  # invalid python syntax\n"
    brain_a._execute_tool("task_track", {"plan_name": "_gate_live_a", "steps": ["live gate check A"]})
    res_a = brain_a._execute_tool("write_file", {"path": bad_rel, "content": bad_content})
    _record(
        "A1 auto verify_artifact flags fabrication",
        "FABRICATION_DETECTED" in res_a and brain_a._fabrication_detected,
        f"_fabrication_detected={brain_a._fabrication_detected}",
    )
    fa = _finalize_capture(brain_a, "_gate_live_a", "READY")
    a2_ok = fa["raised"] and ("BLOCKED_FABRICATION" in fa["review"])
    _record(
        "A2 finalize_plan(READY) blocked on fabrication",
        a2_ok,
        "REVIEW verdict downgraded to BLOCKED_FABRICATION (hard-stop fired)" if a2_ok
        else f"NOT blocked (raised={fa['raised']}, ret={repr(fa.get('ret'))[:120]})",
    )

    # ---- CASE B: clean artifact -> adversarial_verify runs, READY not falsely blocked ----
    print("\n[CASE B] Valid artifact -> fabrication clear, adversarial gate runs")
    brain_b = qd.QorTrollerBrain(qd.MemoryStore(qd.SQLITE_DB_PATH))
    good_content = "def ok():\n    return 42\n"
    brain_b._execute_tool("task_track", {"plan_name": "_gate_live_b", "steps": ["live gate check B"]})
    res_b = brain_b._execute_tool("write_file", {"path": good_rel, "content": good_content})
    _record(
        "B1 valid artifact verified (no fabrication)",
        ("VERIFIED" in res_b) and (not brain_b._fabrication_detected),
        f"_fabrication_detected={brain_b._fabrication_detected}",
    )
    fb = _finalize_capture(brain_b, "_gate_live_b", "READY")
    blocked_b = ("BLOCKED_FABRICATION" in fb["review"]) or ("BLOCKED_ADVERSARIAL" in fb["review"])
    ready_in_review = "READY" in fb["review"]
    _record(
        "B2 clean artifact not falsely blocked",
        fb["raised"] and (not blocked_b) and ready_in_review,
        "REVIEW keeps READY (gates ran, no false block, hard-stop fired)"
        if (fb["raised"] and not blocked_b) else f"unexpected (raised={fb['raised']}, blocked={blocked_b})",
    )

    # ---- CASE C: direct adversarial_verify on a tampered .proposed mixin ----
    print("\n[CASE C] adversarial_verify diff-oracle on a missing/empty artifact")
    av = qd.adversarial_verify(
        os.path.join(_tmp, "nonexistent.proposed"), repo_root=REPO_ROOT,
    )
    _record(
        "C1 adversarial_verify fails closed on missing artifact",
        not av["ok"] and av["method"] == "missing_artifact",
        f"method={av['method']} ok={av['ok']}",
    )

    _cleanup_artifacts([bad_rel, good_rel])
    shutil.rmtree(_tmp, ignore_errors=True)

    print("\n" + "=" * 64)
    passed = sum(1 for _, ok, _ in _results if ok)
    total = len(_results)
    print(f"  GATE LIVE EXERCISE: {passed}/{total} checks fired correctly")
    print("=" * 64)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
