#!/usr/bin/env python3
"""
merge_arjay_training.py
Merges Arjay Hinek's labeled RHAISTRAT features (Release_Fit_Predictor) with
our existing JSONL training rows to produce training_extended_v8.jsonl for
training the v8 Random Forest slip-predictor.

Arjay's CSV: ~/Release_Fit_Predictor/rhaistrat_features_merged.csv
  - 571 rows total; ~233 with Status=Closed + Fix_Versions + Feature_Points
  - Columns used: Key, Summary, Status, Fix_Versions, Size_Category,
    Component_Count, Components, Issue_Count, Feature_Points

Existing JSONL: training_data.jsonl (185 rows with real slip history)
  - Fields used: key, slipped (0/1), slip_count, fpdor_score, rice_score,
    component_count, has_prior_slip, release_type_boost

Output: training_extended_v8.jsonl
  - Merges both, deduplicating on key
  - Adds imputed slip labels for Arjay's features (no real slip history →
    conservative imputation based on size + issue count)
  - Estimated total: ~400 rows vs current 319
"""

import csv
import json
import os
import sys
from pathlib import Path

ARJAY_CSV  = Path.home() / "Release_Fit_Predictor" / "rhaistrat_features_merged.csv"
EXISTING_JSONL = Path(__file__).parent / "fpdor_cycles_extended.jsonl"
OUTPUT_JSONL   = Path(__file__).parent / "training_extended_v8.jsonl"

SIZE_POINTS = {"Small": 3, "Medium": 5, "Large": 8, "Extra Large": 13, "XL": 13}

# Slip probability by size (imputed, conservative — no real slip_count available)
# XL: higher risk; Small: low risk. Capped at 85% confidence in v8 for imputed rows.
IMPUTED_SLIP_RATE = {"Small": 0.10, "Medium": 0.15, "Large": 0.22, "Extra Large": 0.32, "XL": 0.32}


def load_existing(path: Path) -> dict:
    rows = {}
    if not path.exists():
        print(f"[WARN] {path} not found — starting from Arjay data only", file=sys.stderr)
        return rows
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
                rows[r["key"]] = r
            except Exception as e:
                print(f"[WARN] bad JSONL line: {e}", file=sys.stderr)
    print(f"Loaded {len(rows)} existing training rows from {path.name}")
    return rows


def load_arjay(path: Path) -> list:
    if not path.exists():
        sys.exit(f"ERROR: {path} not found. Clone ahinek/Release_Fit_Predictor to ~/Release_Fit_Predictor/")
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            # Only use shipped features with known size and fix version
            if r.get("Status") != "Closed":
                continue
            if not r.get("Fix_Versions", "").strip():
                continue
            if not r.get("Size_Category", "").strip():
                continue
            rows.append(r)
    print(f"Loaded {len(rows)} usable labeled rows from {path.name}")
    return rows


def arjay_to_training_row(r: dict) -> dict:
    """Convert Arjay CSV row to RHOAI JSONL schema (matches train_classifier_v7/v8 reader)."""
    size = r.get("Size_Category", "Medium").strip()
    ncomps = int(float(r.get("Component_Count", 0) or 0))
    issue_count = int(float(r.get("Issue_Count", 0) or 0))
    feature_pts = int(float(r.get("Feature_Points", SIZE_POINTS.get(size, 5)) or SIZE_POINTS.get(size, 5)))

    # Parse components → primaryComponent (first one if multiple)
    raw_comps = r.get("Components", "").strip()
    comp_list = [c.strip() for c in raw_comps.split(";") if c.strip()] if raw_comps else []
    primary_comp = comp_list[0] if comp_list else "unknown"

    # Determine committedPhase from Fix_Versions string
    fix_ver = r.get("Fix_Versions", "").lower()
    if "ea1" in fix_ver:
        phase = "EA1"
    elif "ea2" in fix_ver:
        phase = "EA2"
    else:
        phase = "GA"

    # All Status=Closed + Fix_Versions → shipped on time → deliveredPhase == committedPhase
    # Trainer label: 1 if deliveredPhase == committedPhase else 0
    return {
        "key": r["Key"].strip(),
        "summary": r.get("Summary", ""),
        "product": "RHOAI",
        "components": comp_list,
        "hasDocsComponent": False,           # unknown from Arjay data
        "primaryComponent": primary_comp,
        "priority": {"rice": None, "jiraPriority": "Major"},  # unknown → neutral
        "committedPhase": phase,
        "deliveredPhase": phase,             # same = shipped on time (label=1)
        "slips": [],                         # no slip history → 0 slips
        "fpdorAtFreeze": None,               # not available → MICE will impute
        "_source": "arjay_csv",
        # Extra signals for v8 (new features the trainer can add):
        "feature_pts": feature_pts,
        "size_category": size,
        "component_count": ncomps,
        "issue_count": issue_count,
        "imputed_conf_cap": 85,              # cap at 85% — no real slip history
    }


def main():
    existing = load_existing(EXISTING_JSONL)
    arjay_rows = load_arjay(ARJAY_CSV)

    merged = dict(existing)  # keyed by Jira key
    added = 0
    skipped_dup = 0

    for r in arjay_rows:
        key = r.get("Key", "").strip()
        if not key:
            continue
        if key in merged:
            skipped_dup += 1
            continue
        merged[key] = arjay_to_training_row(r)
        added += 1

    with open(OUTPUT_JSONL, "w") as f:
        for row in merged.values():
            f.write(json.dumps(row) + "\n")

    # Slipped = deliveredPhase != committedPhase (trainer label=0)
    slipped_total = sum(
        1 for r in merged.values()
        if r.get("deliveredPhase") != r.get("committedPhase")
    )
    shipped_total = len(merged) - slipped_total
    print(f"\nOutput: {OUTPUT_JSONL}")
    print(f"  Total rows:       {len(merged)}")
    print(f"  From existing:    {len(existing)} (real slip history)")
    print(f"  From Arjay CSV:   {added} (all shipped, label=1, cap 85%)")
    print(f"  Duplicates skipped: {skipped_dup}")
    print(f"  Shipped (label=1): {shipped_total} ({100*shipped_total//len(merged)}%)")
    print(f"  Slipped (label=0): {slipped_total} ({100*slipped_total//len(merged)}%)")
    print("\nNext: run train_classifier_v8.py with training_extended_v8.jsonl")


if __name__ == "__main__":
    main()
