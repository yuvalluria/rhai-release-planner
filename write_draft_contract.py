#!/usr/bin/env python3
"""
write_draft_contract.py
Converts our ML inference output into the Org Pulse Draft Plans data contract JSON.

Input:
  merged_ml_scores.json  — {RHAISTRAT-XXXX: score_0_to_100}
  index.html             — embedded CSV with all 3.6 features

Output:
  releases/draft-plans/drafts/RHOAI/3.6.json   (pipeline path Org Pulse reads)
  Also copies to: releases/draft-plans/drafts/combined/3.6.json (legacy)

Run after: python3 merge_scores.py
"""

import csv
import io
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
SCORES_FILE = HERE / "merged_ml_scores.json"
ROADMAP_FILE = HERE / "roadmap_outcomes.json"
HTML_FILE = HERE / "index.html"
OUT_FILE = HERE / "releases" / "draft-plans" / "drafts" / "RHOAI" / "3.6.json"
OUT_FILE_COMBINED = HERE / "releases" / "draft-plans" / "drafts" / "combined" / "3.6.json"

DEFAULT_SCORE = 65  # 0-100; used when key not in merged_ml_scores


def load_roadmap() -> dict:
    if not ROADMAP_FILE.exists():
        return {}
    with open(ROADMAP_FILE) as f:
        data = json.load(f)
    return {k: v.get("bigRock", "") for k, v in data.items()}


def load_scores() -> dict:
    if not SCORES_FILE.exists():
        print(f"[WARN] {SCORES_FILE.name} not found — using default score {DEFAULT_SCORE} for all features",
              file=sys.stderr)
        return {}
    with open(SCORES_FILE) as f:
        return json.load(f)


def extract_csv(html_path: Path) -> list[dict]:
    html = html_path.read_text(encoding="utf-8")
    header_m = re.search(r"(Rank,Key,Title[^\n]+)", html)
    header = header_m.group(1) if header_m else "Rank,Key,Title,Score,FPDoR,Failed FPDoR Items,Outcome,Target Versions,Fix Version,Components,Team,Status,Priority,Confidence,Labels"
    data_lines = [l for l in html.split("\n") if re.match(r"\s*\d+,RHAISTRAT-", l)]
    csv_text = header + "\n" + "\n".join(l.strip() for l in data_lines)
    reader = csv.DictReader(io.StringIO(csv_text))
    return list(reader)


def feature_size(ncomps: int) -> tuple[int, str]:
    if ncomps >= 3:
        return 13, "XL"
    if ncomps == 2:
        return 8, "L"
    if ncomps == 1:
        return 5, "M"
    return 3, "S"


def derive_phase(target_version: str, fix_versions: str, score: float) -> str:
    tv = (target_version or "").upper()
    fv = (fix_versions or "").upper()
    combined = tv + " " + fv
    if score < 50:
        return "Below cut"
    if "EA1" in combined:
        return "EA1"
    if "EA2" in combined:
        return "EA2"
    if "GA" in combined:
        return "GA"
    return "EA2"  # most common default


JIRA_PRIORITY_MAP = {
    "blocker": "Critical", "critical": "Critical",
    "major": "High", "high": "High",
    "minor": "Medium", "medium": "Medium",
    "trivial": "Low", "low": "Low",
}


def build_candidate(row: dict, score_0_100: float, rank: int, roadmap: dict = None) -> dict:
    key = row.get("Key", "").strip()
    title = row.get("Title", "").strip()
    title_lower = title.lower()
    labels = row.get("Labels", "")
    labels_lower = labels.lower()
    components_raw = row.get("Components", "")
    comp_list = [c.strip() for c in components_raw.split(";") if c.strip()]
    ncomps = len(comp_list)
    feature_pts, size_cat = feature_size(ncomps)
    primary_component = comp_list[0] if comp_list else ""

    target_version = row.get("Target Versions", row.get("Target Version", ""))
    fix_versions = row.get("Fix Version", row.get("Fix Versions", ""))
    release_type = row.get("Release Type", "")
    status = row.get("Status", "")
    jira_priority = row.get("Priority", "").strip().lower()
    priority = JIRA_PRIORITY_MAP.get(jira_priority, "Medium")

    phase = derive_phase(target_version, fix_versions, score_0_100)

    is_draft = "[draft]" in title_lower
    has_qg1 = "rp-qg1-pass" in labels_lower
    has_strat = "strat-creator-human-sign-off" in labels_lower

    fpdor_ok = (
        "fpdor-complete" in labels_lower
        or (release_type.strip() and fix_versions.strip() and not is_draft)
    )

    hard_reasons: list[str] = []
    if not fix_versions.strip():
        hard_reasons.append("Fix Version not set")
    if not release_type.strip():
        hard_reasons.append("Release Type not set")

    soft_warnings: list[str] = []
    if score_0_100 < 70:
        soft_warnings.append(f"Low confidence (score: {round(score_0_100)}%)")
    if is_draft:
        soft_warnings.append("Feature is still in DRAFT status")
    if not has_qg1:
        soft_warnings.append("QG1 not passed")
    if not has_strat:
        soft_warnings.append("No strat-creator human sign-off")

    priority_score = round(score_0_100 / 100, 4)
    big_rock = (roadmap or {}).get(key, "")

    return {
        "key": key,
        "summary": title,           # Org Pulse normalizer expects "summary" not "title"
        "basePlacement": phase,
        "rank": rank,
        "priorityScore": priority_score,
        "priority": priority,       # Critical / High / Medium / Low
        "component": primary_component,
        "engComponents": comp_list,
        "currentTV": target_version,
        "productFamily": "RHOAI",
        "assignee": "",             # requires Jira API — empty until connected
        "pm": "",                   # requires Jira API — empty until connected
        "bigRock": big_rock,        # from roadmap_outcomes.json (259 features covered)
        "humanSignoff": has_strat,
        "qg1Pass": has_qg1,
        "isDraft": is_draft,
        "releaseType": release_type,
        "status": status,
        "readiness": {
            "structuralOk": fpdor_ok,
            "hardReasons": hard_reasons,
            "softWarnings": soft_warnings,
        },
        "ready": "Plan-ready" if fpdor_ok else "Not ready",
        "readyBool": fpdor_ok,
        "cycleBudget": feature_pts,
        "featureSize": size_cat,
    }


def main():
    scores = load_scores()
    roadmap = load_roadmap()
    print(f"Loaded {len(scores)} ML scores, {len(roadmap)} roadmap Big Rock labels")

    all_rows = extract_csv(HTML_FILE)
    print(f"Extracted {len(all_rows)} rows from index.html")

    # Filter to 3.6 features (column names vary: "Target Versions" / "Fix Version")
    rows_36 = [
        r for r in all_rows
        if "3.6" in r.get("Target Versions", r.get("Target Version", ""))
        or "3.6" in r.get("Fix Version", r.get("Fix Versions", ""))
    ]
    print(f"Filtered to {len(rows_36)} 3.6-targeted features")

    # Score each feature
    scored = []
    for r in rows_36:
        key = r.get("Key", "").strip()
        raw = scores.get(key, DEFAULT_SCORE)
        # merged_ml_scores.json values are either float or {"score": float, ...}
        raw_score = raw.get("score", DEFAULT_SCORE) if isinstance(raw, dict) else raw
        scored.append((r, float(raw_score)))

    # Sort by score descending before ranking
    scored.sort(key=lambda x: x[1], reverse=True)

    candidates = [
        build_candidate(row, score, rank=i + 1, roadmap=roadmap)
        for i, (row, score) in enumerate(scored)
    ]

    # Summary
    by_event: dict[str, int] = {"EA1": 0, "EA2": 0, "GA": 0}
    below_cut = 0
    for c in candidates:
        p = c["basePlacement"]
        if p in by_event:
            by_event[p] += 1
        else:
            below_cut += 1

    scheduled = sum(by_event.values())
    summary = {
        "candidateCount": len(candidates),
        "scheduled": scheduled,
        "belowCut": below_cut,
        "byEvent": by_event,
    }

    output = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "version": "3.6",
        "createdBy": "rhai-release-planner",
        "summary": summary,
        "candidates": candidates,
    }

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(output, indent=2))
    OUT_FILE_COMBINED.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE_COMBINED.write_text(json.dumps(output, indent=2))

    print(f"\nWrote {OUT_FILE}  (Org Pulse pipeline path)")
    print(f"Wrote {OUT_FILE_COMBINED}  (legacy combined path)")
    print(f"  Total candidates:  {summary['candidateCount']}")
    print(f"  Scheduled:         {summary['scheduled']}  (EA1={by_event['EA1']} EA2={by_event['EA2']} GA={by_event['GA']})")
    print(f"  Below cut:         {summary['belowCut']}")


if __name__ == "__main__":
    main()
