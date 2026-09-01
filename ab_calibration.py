#!/usr/bin/env python3
"""
ab_calibration.py
A/B calibration: compare pre-freeze ML predictions vs. EA2 committed features.

Inputs:
  committed_csv     — Jira export of Sarah's EA2 committed list (93 features)
  3.6.json          — our draft plans (predicted placements + scores)
  merged_ml_scores  — raw ML scores per key

Outputs to stdout:
  - Precision / Recall / F1 for EA2 prediction
  - False positives (we predicted EA2, not committed)
  - False negatives (committed but we missed or ranked low)
  - v10 training rows appended to: training_extended_v10_seed.jsonl

Run:
  python3 ab_calibration.py [path-to-committed-csv]
  Default CSV path: ~/Downloads/Untitled spreadsheet - Your Jira Issues.csv
"""

import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
DEFAULT_CSV = Path.home() / "Downloads" / "Untitled spreadsheet - Your Jira Issues.csv"
DRAFT_JSON  = HERE / "releases" / "draft-plans" / "drafts" / "RHOAI" / "3.6.json"
SCORES_FILE = HERE / "merged_ml_scores.json"
OUTPUT_JSONL = HERE / "training_extended_v10_seed.jsonl"


def load_committed(csv_path: Path) -> dict:
    """Return {key: {summary, status, priority}} for all committed EA2 features."""
    committed = {}
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        lines = f.readlines()
    # Skip leading rows until we find the real header (contains "Key")
    start = next(i for i, l in enumerate(lines) if "Key" in l and "Issue Type" in l)
    reader = csv.DictReader(lines[start:])
    for row in reader:
        key = row.get("Key", "").strip()
        if not key or not key.startswith("RHAISTRAT-"):
            continue
        committed[key] = {
            "summary": row.get("Summary", "").strip(),
            "status":  row.get("Status", "").strip(),
            "priority": row.get("Priority", "").strip(),
        }
    return committed


def load_predictions(draft_path: Path) -> dict:
    """Return {key: {basePlacement, priorityScore, summary}} from draft plans."""
    with open(draft_path) as f:
        data = json.load(f)
    return {
        c["key"]: {
            "basePlacement": c["basePlacement"],
            "priorityScore": c.get("priorityScore", 0),
            "summary": c.get("summary", ""),
            "bigRock": c.get("bigRock", ""),
            "readiness": c.get("readiness", {}),
        }
        for c in data["candidates"]
    }


def load_scores(scores_path: Path) -> dict:
    if not scores_path.exists():
        return {}
    with open(scores_path) as f:
        raw = json.load(f)
    out = {}
    for k, v in raw.items():
        out[k] = v.get("score", v) if isinstance(v, dict) else float(v)
    return out


def build_v10_row(key: str, pred: dict, committed_info: dict | None, label: int) -> dict:
    """Build a training row for v10. label=1 → shipped as predicted, 0 → slipped/missed."""
    score_0_100 = round((pred.get("priorityScore") or 0) * 100, 1)
    is_draft = "[draft]" in (pred.get("summary") or "").lower()
    return {
        "key": key,
        "summary": pred.get("summary", ""),
        "product": "RHOAI",
        "_source": "ab_calibration_3.6_ea2",
        "committedPhase": pred.get("basePlacement", "EA2"),
        "deliveredPhase": "EA2" if label == 1 else "MISSED",
        "slips": [] if label == 1 else ["missed_ea2_freeze"],
        "fpdorAtFreeze": None,
        "bigRock": pred.get("bigRock", ""),
        "isDraft": is_draft,
        "ml_score_pre_freeze": score_0_100,
        "ab_label": label,
        "committed_status": (committed_info or {}).get("status", ""),
    }


def fmt_conf(score_0_1: float) -> str:
    pct = round(score_0_1 * 100)
    if pct >= 70:
        return f"\033[92m{pct}%\033[0m"
    if pct >= 50:
        return f"\033[93m{pct}%\033[0m"
    return f"\033[91m{pct}%\033[0m"


def main():
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CSV
    if not csv_path.exists():
        sys.exit(f"ERROR: committed CSV not found at {csv_path}")
    if not DRAFT_JSON.exists():
        sys.exit(f"ERROR: draft plans not found at {DRAFT_JSON}\nRun write_draft_contract.py first.")

    committed  = load_committed(csv_path)
    predictions = load_predictions(DRAFT_JSON)
    scores = load_scores(SCORES_FILE)

    committed_keys  = set(committed.keys())
    predicted_ea2   = {k for k, v in predictions.items() if v["basePlacement"] == "EA2"}
    predicted_ea1   = {k for k, v in predictions.items() if v["basePlacement"] == "EA1"}
    predicted_ga    = {k for k, v in predictions.items() if v["basePlacement"] == "GA"}
    predicted_below = {k for k, v in predictions.items() if v["basePlacement"] == "Below cut"}

    # Core confusion matrix for EA2 prediction
    tp = committed_keys & predicted_ea2        # we said EA2, they committed EA2 ✅
    fp = predicted_ea2 - committed_keys        # we said EA2, not committed ❌
    fn = committed_keys - predicted_ea2        # committed EA2, we didn't predict EA2 ❌

    precision = len(tp) / len(predicted_ea2) if predicted_ea2 else 0
    recall    = len(tp) / len(committed_keys) if committed_keys else 0
    f1        = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0

    print("\n" + "="*70)
    print("  A/B CALIBRATION — RHOAI 3.6 EA2")
    print("  Pre-freeze predictions vs. Sarah's committed list (Sep 1, 2026)")
    print("="*70)
    print(f"\n  Committed features (ground truth):  {len(committed_keys)}")
    print(f"  Our EA2 predictions (pre-freeze):   {len(predicted_ea2)}")
    print(f"\n  True Positives  (TP):  {len(tp):3d}  — predicted EA2, committed ✅")
    print(f"  False Positives (FP):  {len(fp):3d}  — predicted EA2, NOT committed ❌")
    print(f"  False Negatives (FN):  {len(fn):3d}  — committed, we MISSED ❌")
    print(f"\n  Precision:  {precision:.1%}")
    print(f"  Recall:     {recall:.1%}")
    print(f"  F1 Score:   {f1:.1%}")

    # Where did FN land in our model?
    fn_by_bucket = {"EA1": 0, "GA": 0, "Below cut": 0, "Not in model": 0}
    for k in fn:
        if k in predicted_ea1:   fn_by_bucket["EA1"] += 1
        elif k in predicted_ga:  fn_by_bucket["GA"] += 1
        elif k in predicted_below: fn_by_bucket["Below cut"] += 1
        else: fn_by_bucket["Not in model"] += 1

    print(f"\n  Missed features (FN) by our bucket:")
    for bucket, cnt in fn_by_bucket.items():
        if cnt: print(f"    {bucket:15s}: {cnt}")

    # False Positives — features we over-predicted
    print(f"\n{'─'*70}")
    print(f"  FALSE POSITIVES ({len(fp)}) — we predicted EA2, did NOT commit")
    print(f"{'─'*70}")
    fp_sorted = sorted(fp, key=lambda k: predictions[k]["priorityScore"], reverse=True)
    for k in fp_sorted[:20]:
        p = predictions[k]
        score_str = fmt_conf(p["priorityScore"])
        is_draft = "⚠ [DRAFT]" if "[draft]" in p["summary"].lower() else ""
        br = f"[{p['bigRock']}]" if p.get("bigRock") else ""
        print(f"  {k:<20} {score_str:>8}  {is_draft} {br}")
        print(f"    {p['summary'][:75]}")

    # False Negatives — features we missed
    print(f"\n{'─'*70}")
    print(f"  FALSE NEGATIVES ({len(fn)}) — committed but we didn't predict EA2")
    print(f"{'─'*70}")
    fn_with_scores = []
    for k in fn:
        raw_score = scores.get(k, None)
        score_pct = float(raw_score) if raw_score is not None else None
        our_bucket = predictions.get(k, {}).get("basePlacement", "Not in model")
        summary = committed[k]["summary"]
        fn_with_scores.append((k, score_pct, our_bucket, summary, committed[k]["status"]))
    fn_with_scores.sort(key=lambda x: x[1] or 0)  # lowest score first = biggest surprise

    for k, score_pct, bucket, summary, status in fn_with_scores[:20]:
        score_str = fmt_conf(score_pct / 100) if score_pct is not None else "  N/A"
        is_draft = "⚠ [DRAFT]" if "[draft]" in summary.lower() else ""
        print(f"  {k:<20} {score_str:>8}  → we put in {bucket:<12} status={status} {is_draft}")
        print(f"    {summary[:75]}")

    # v10 training rows
    v10_rows = []
    for k in tp:
        v10_rows.append(build_v10_row(k, predictions[k], committed.get(k), label=1))
    for k in fp:
        v10_rows.append(build_v10_row(k, predictions[k], None, label=0))
    for k in fn:
        pred_stub = predictions.get(k, {"basePlacement": "EA2", "priorityScore": None, "summary": committed[k]["summary"], "bigRock": ""})
        v10_rows.append(build_v10_row(k, pred_stub, committed[k], label=1))

    with open(OUTPUT_JSONL, "w") as f:
        for row in v10_rows:
            f.write(json.dumps(row) + "\n")

    print(f"\n{'─'*70}")
    print(f"  v10 TRAINING SEED — {len(v10_rows)} labeled rows written to:")
    print(f"  {OUTPUT_JSONL}")
    print(f"    TP (label=1, shipped):  {len(tp)}")
    print(f"    FP (label=0, missed):   {len(fp)}")
    print(f"    FN (label=1, committed we missed): {len(fn)}")
    print(f"\n  Next: merge into training_extended_v8.jsonl and run train_classifier_v10.py")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
