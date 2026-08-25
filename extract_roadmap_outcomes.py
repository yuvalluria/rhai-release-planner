#!/usr/bin/env python3
"""
extract_roadmap_outcomes.py
Extracts embedded CSV from RHAI-Roadmap.html, matches each feature to a Big Rock,
and outputs roadmap_outcomes.json for baking into index.html.
"""
import csv
import io
import json
import re
import sys
from pathlib import Path

ROADMAP_HTML = Path.home() / "Downloads" / "RHAI-Roadmap.html"
OUTPUT_JSON = Path(__file__).parent / "roadmap_outcomes.json"

BIG_ROCKS = [
    {"name": "Upgrade Support",                      "keywords": ["upgrade support"]},
    {"name": "MaaS",                                 "keywords": ["maas", "observability"]},
    {"name": "Gen AI Studio",                        "keywords": ["gen ai studio", "prompt lab", "vllm multimodal"]},
    {"name": "Bring Your Own Agent",                 "keywords": ["bring your own agent", "agentops", "byoa", "open agent core", "openshell"]},
    {"name": "Tool Calling",                         "keywords": ["tool calling"]},
    {"name": "llm-d Platform",                       "keywords": ["llm-d platform experience"]},
    {"name": "Unified RHAII on xKS",                 "keywords": ["llm-d on xks", "inference on xks"]},
    {"name": "Eval Hub",                             "keywords": ["eval hub"]},
    {"name": "AI Hub incl MCP",                      "keywords": ["ai hub"]},
    {"name": "Observability",                        "keywords": ["observability"]},
    {"name": "Multitenancy",                         "keywords": ["multitenancy"]},
    {"name": "AutoRAG",                              "keywords": ["autorag"]},
    {"name": "AI Safety x Model Validation",         "keywords": ["ai safety", "ai safety x model"]},
    {"name": "AutoML",                               "keywords": ["automl", "auto ml"]},
    {"name": "GPUaaS",                               "keywords": ["gpuaas", "gpu-as-a-service"]},
    {"name": "Red Hat AI Factory with NVIDIA Rubin", "keywords": ["nvidia rubin"]},
    {"name": "Model Catalog Updates",               "keywords": []},
    {"name": "Other Features",                      "keywords": []},
]


def match_big_rock(outcome: str, title: str) -> str:
    text = (outcome + " " + title).lower()
    for rock in BIG_ROCKS:
        for kw in rock["keywords"]:
            if kw in text:
                return rock["name"]
    return "Other Features"


def extract_csv(html: str) -> str:
    # Find the template literal CSV inside loadData()
    # Pattern: const csvData = `...`
    m = re.search(r'const csvData\s*=\s*`([^`]+)`', html, re.DOTALL)
    if not m:
        sys.exit("ERROR: Could not find 'const csvData = `...`' in HTML")
    return m.group(1).strip()


def main():
    if not ROADMAP_HTML.exists():
        sys.exit(f"ERROR: {ROADMAP_HTML} not found")

    html = ROADMAP_HTML.read_text(encoding="utf-8")
    csv_text = extract_csv(html)

    reader = csv.DictReader(io.StringIO(csv_text))
    outcomes = {}
    for row in reader:
        key = (row.get("Key") or "").strip()
        if not key or not key.startswith("RHAISTRAT-"):
            continue
        rank_raw = (row.get("Rank") or "").strip()
        rank = int(rank_raw) if rank_raw.isdigit() else None
        outcome_field = (row.get("Outcome") or "").strip()
        title = (row.get("Title") or "").strip()
        confidence = (row.get("Confidence") or "").strip()
        big_rock = match_big_rock(outcome_field, title)
        outcomes[key] = {
            "bigRock": big_rock,
            "rank": rank,
            "roadmapConfidence": confidence,
        }

    with open(OUTPUT_JSON, "w") as f:
        json.dump(outcomes, f, indent=2)

    print(f"Extracted {len(outcomes)} features → {OUTPUT_JSON}")
    # Show Big Rock distribution
    from collections import Counter
    dist = Counter(v["bigRock"] for v in outcomes.values())
    for name, count in dist.most_common():
        print(f"  {count:3d}  {name}")


if __name__ == "__main__":
    main()
