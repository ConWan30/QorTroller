"""Precision/recall of the CFB snap extractor vs machine-readable ground-truth transitions.
GT labels (ground_truth_transitions.jsonl, kind=downdist_text_change) are read from the capture dir;
they were labeled by reading 4s-interval scoreboard filmstrips of run1_cfb27 (operator/agent eyeball,
now EXPLICIT + machine-readable — grok r03 R1). Greedy nearest-unmatched matching within tolerance.
Usage: python scripts/cfb_eval_pr.py <capture_dir> [tolerances...]"""
import os, sys, json

def evaluate(capture_dir, tols=(5.0, 8.0)):
    det = [json.loads(l)["ts_s"] for l in open(os.path.join(capture_dir, "snap_events.jsonl"))]
    gtrows = [json.loads(l) for l in open(os.path.join(capture_dir, "ground_truth_transitions.jsonl"))]
    gt = [r["ts_s"] for r in gtrows if r.get("kind") == "downdist_text_change"]
    out = {"n_detected": len(det), "n_gt": len(gt), "by_tolerance": {}}
    for tol in tols:
        matched = set(); tp = 0; fp = []
        for de in det:
            cands = sorted((abs(de - g), i) for i, g in enumerate(gt) if i not in matched and abs(de - g) <= tol)
            if cands:
                matched.add(cands[0][1]); tp += 1
            else:
                fp.append(round(de, 1))
        fn = [round(gt[i]) for i in range(len(gt)) if i not in matched]
        out["by_tolerance"][str(tol)] = {
            "tp": tp, "precision": round(tp / len(det), 3), "recall": round(tp / len(gt), 3),
            "false_positives": fp, "missed_gt": fn,
        }
    return out

if __name__ == "__main__":
    d = sys.argv[1]
    tols = [float(x) for x in sys.argv[2:]] or [5.0, 8.0]
    print(json.dumps(evaluate(d, tols), indent=2))
