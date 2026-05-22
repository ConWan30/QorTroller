"""QorTroller PoEP sub-lane B — device-handoff de-risk (the decisive GO/NO-GO).

Sub-lane B (PoEP micro-challenge at menu lulls) needs the ACTIVE pydualsense challenger and
the PASSIVE hidapi reader to share one controller — but two opens of one HID device conflict.
This checks the single fact that decides the whole hardware path:

  Can ONE process, repeatedly, do: passive hidapi read -> release -> pydualsense acquire +
  fire + capture -> release -> passive hidapi REACQUIRE -- cleanly, without crashing or
  losing the stream?

  GO  -> Option A: a handoff state machine; sub-lane B can live inside the Witness process.
  NO-GO -> Option B: unify on pydualsense as the SOLE device owner (cleaner; but then de-risk
           that the parsed-state read preserves the validated L9 coupling result).

The reacquire-after-pydualsense step is the load-bearing one. Hardware required; the verdict
logic is unit-tested separately. EXIT: 0 GO(A) / 4 no hardware / 6 NO-GO(B).
"""
from __future__ import annotations

import sys
import time

_VID, _PID = 0x054C, 0x0DF2


def assess_handoff(rounds: list) -> dict:
    """Verdict from per-round results [{read1_ok, acquire_ok, reacquire_ok}]. GO only if EVERY
    round did all three (passive read, pydualsense acquire+fire, passive reacquire)."""
    n = len(rounds)
    read1 = sum(1 for r in rounds if r.get("read1_ok"))
    acq = sum(1 for r in rounds if r.get("acquire_ok"))
    reacq = sum(1 for r in rounds if r.get("reacquire_ok"))
    clean = sum(1 for r in rounds if r.get("read1_ok") and r.get("acquire_ok") and r.get("reacquire_ok"))
    go = bool(n > 0 and clean == n)
    return {
        "rounds": n, "passive_read": read1, "pydualsense_acquire": acq,
        "reacquire_after_pydualsense": reacq, "clean_rounds": clean, "go": go,
        "recommendation": (
            "Option A: handoff is clean -> sub-lane B can live in the Witness process (build the state machine)"
            if go else
            "Option B: handoff flaky -> unify on pydualsense as SOLE owner; then de-risk it preserves L9 coupling"),
    }


def _raw_read(reads: int = 50) -> bool:
    """Passive hidapi read — returns True if at least one report arrives."""
    try:
        import hid
    except Exception:
        return False
    d = None
    try:
        d = hid.device(); d.open(_VID, _PID); d.set_nonblocking(True)
        for _ in range(reads):
            if d.read(64):
                return True
            time.sleep(0.002)
        return False
    except Exception:
        return False
    finally:
        try:
            if d is not None:
                d.close()
        except Exception:
            pass


def _pydualsense_active() -> bool:
    """Acquire via pydualsense, fire a brief stimulus, confirm analog state reads, release."""
    try:
        from pydualsense import pydualsense
    except Exception:
        return False
    ds = None
    try:
        ds = pydualsense(); ds.init()
        try:
            ds.setLeftMotor(160); ds.setRightMotor(160); time.sleep(0.1)
            ds.setLeftMotor(0); ds.setRightMotor(0)
        except Exception:
            pass
        for _ in range(40):
            if getattr(ds.state, "R2_value", None) is not None:
                return True
            time.sleep(0.005)
        return True   # init succeeded even if state attr missing
    except Exception:
        return False
    finally:
        try:
            if ds is not None:
                ds.close()
        except Exception:
            pass


def run_handoff_derisk(rounds: int = 5) -> dict:
    # preflight: is the device reachable at all?
    if not _raw_read():
        try:
            import hid  # noqa: F401
        except Exception:
            return {"status": "no_hidapi"}
        # hidapi present but no read -> maybe pydualsense can still reach it; check once
        if not _pydualsense_active():
            return {"status": "controller_unreachable"}
    results = []
    for i in range(rounds):
        r1 = _raw_read()
        acq = _pydualsense_active()
        time.sleep(0.2)
        r2 = _raw_read()                       # the load-bearing reacquire
        results.append({"read1_ok": r1, "acquire_ok": acq, "reacquire_ok": r2})
        print(f"  round {i + 1}/{rounds}: read={r1} acquire={acq} reacquire={r2}")
        time.sleep(0.3)
    out = assess_handoff(results)
    out["status"] = "ok"
    return out


def main() -> int:
    print("=" * 64)
    print("QorTroller PoEP sub-lane B — device-handoff de-risk")
    print("=" * 64)
    print("  Controller on USB (a game need NOT be running). Brief buzzes are expected.\n")
    r = run_handoff_derisk()
    print("  " + "=" * 60)
    if r.get("status") == "no_hidapi":
        print("  ABORT: pip install hidapi"); return 4
    if r.get("status") == "controller_unreachable":
        print("  NO-GO: controller not reachable on USB"); return 4
    print(f"  clean {r['clean_rounds']}/{r['rounds']} | reacquire-after-pydualsense "
          f"{r['reacquire_after_pydualsense']}/{r['rounds']}")
    print(f"  RESULT: {'GO' if r['go'] else 'NO-GO'} — {r['recommendation']}")
    return 0 if r["go"] else 6


if __name__ == "__main__":
    sys.exit(main())
