"""
Inference from Org Pulse CSV — scores ALL features using RF+ROS model.
Extends coverage beyond the 70 JSONL-sourced features by extracting
features directly from CSV columns and imputing slip_count (=0).

Usage:
    python run_inference_csv.py path/to/orgpulse.csv

Output: inference_3.6_csv_v1.json — all CSV features with a recognised
        Target Version get an AI Delivery Signal score.

Merge strategy (in merge_scores.py):
    JSONL-sourced scores (70 features, include slip history) take priority.
    CSV-only scores (all others) fill the gap.
"""
import csv, json, pickle, sys
import numpy as np

import os as _os
_V3 = '/Users/yluria/Documents/ai-first-scheduler/models_v3.pkl'
_V2 = '/Users/yluria/Documents/ai-first-scheduler/models_v2.pkl'
MODEL_PATH = _V3 if _os.path.exists(_V3) else _V2
OUT_PATH   = '/Users/yluria/Documents/ai-first-scheduler/inference_3.6_csv_v1.json'

# Must match training-time encoding exactly
JIRA_PRI  = {'Blocker': 5, 'Critical': 4, 'Major': 3, 'High': 3, 'Medium': 2, 'Low': 1}
PHASE_ORD = {'EA1': 1, 'EA2': 2, 'GA': 3}

# FPDoR item grouping — mirrors the JSONL mandatory/criteria groups
# 'mandatory' group items (Release Type, TV, Components, PM, Assignee, Priority, RICE, Docs)
MANDATORY_ITEMS = frozenset({
    'Release Type', 'Target Version', 'Components',
    'PM', 'PM Assigned', 'Delivery Owner', 'Assignee',
    'Priority', 'RICE', 'RICE Score', 'Docs impact', 'Documentation',
})
# 'criteria' group items (readiness content checks)
CRITERIA_ITEMS = frozenset({
    'Source RFE', 'Requirements Clarity', 'Acceptance Criteria',
    'Risks & Assumptions', 'Architectural Alignment', 'Scope Defined',
    'UXD', 'Cross-functional Engineering', 'Feature human sign-off', 'Child Epics',
})
N_MANDATORY = 8   # canonical count in training data
N_CRITERIA  = 5   # canonical count (varies by feature; use 5 as safe estimate)


def detect_phase(tv: str) -> str | None:
    tv = (tv or '').lower()
    if 'ea1' in tv:                                                       return 'EA1'
    if 'ea2' in tv:                                                       return 'EA2'
    if ' ga ' in tv or tv.endswith(' ga') or \
       'ga release' in tv or 'ga rhaii' in tv or 'ga rhelai' in tv:      return 'GA'
    return None


def parse_fpdor(fpdor_str: str, failed_str: str) -> dict:
    """Parse '11/13' and the semicolon-separated Failed FPDoR Items field."""
    fpdor_str = (fpdor_str or '').strip()
    has_data  = fpdor_str and fpdor_str not in ('—', '-') and '/' in fpdor_str
    if not has_data:
        return dict(pass_rate=0.0, mandatory_pass_rate=0.0, criteria_pass_rate=0.0,
                    passed_count=0, rt_pass=0, docs_pass=0)

    passed, total = 0, 13
    try:
        p, t   = fpdor_str.split('/', 1)
        passed = int(p.strip())
        total  = max(1, int(t.strip()))
    except ValueError:
        pass

    failed_set    = {x.strip() for x in (failed_str or '').split(';') if x.strip()}
    mand_failed   = len(MANDATORY_ITEMS & failed_set)
    crit_failed   = len(CRITERIA_ITEMS  & failed_set)

    return dict(
        pass_rate           = passed / total,
        mandatory_pass_rate = max(0.0, (N_MANDATORY - mand_failed) / N_MANDATORY),
        criteria_pass_rate  = max(0.0, (N_CRITERIA  - crit_failed) / N_CRITERIA),
        passed_count        = passed,
        rt_pass             = 0 if 'Release Type' in failed_set else 1,
        docs_pass           = 0 if any(d in failed_set for d in ('Docs impact', 'Documentation')) else 1,
    )


def build_feature_vector(row: dict, comp_le, slip_impute: float) -> list:
    """
    Construct the 12-feature vector matching training order:
      fpdor_pass_rate, mandatory_pass_rate, criteria_pass_rate,
      fpdor_passed_count, rt_pass, docs_pass,
      rice, jira_priority, committed_phase_ord,
      slip_count, has_docs_component, component_encoded
    """
    fpdor = parse_fpdor(row.get('FPDoR', ''), row.get('Failed FPDoR Items', ''))

    comps   = [c.strip() for c in (row.get('Components') or '').split(';') if c.strip()]
    primary = comps[0] if comps else 'unknown'
    try:
        comp_enc = float(comp_le.transform([primary])[0])
    except ValueError:
        comp_enc = 0.0   # unseen component → 0 (same as training fallback)

    # Score column is the RICE composite (same field as priority.rice in JSONL)
    try:
        rice = float(row.get('Score') or 'nan')
        if rice == 0:
            rice = np.nan   # 0 in CSV usually means "not filled in"
    except (ValueError, TypeError):
        rice = np.nan

    jira_pri  = JIRA_PRI.get((row.get('Priority') or '').strip(), 0)
    phase_ord = PHASE_ORD.get(detect_phase(row.get('Target Versions', '')), 2)
    has_docs  = int(any('doc' in c.lower() for c in comps))

    return [
        fpdor['pass_rate'],
        fpdor['mandatory_pass_rate'],
        fpdor['criteria_pass_rate'],
        fpdor['passed_count'],
        fpdor['rt_pass'],
        fpdor['docs_pass'],
        rice,
        jira_pri,
        phase_ord,
        slip_impute,   # slip_count: imputed (see note below)
        has_docs,
        comp_enc,
    ]


def main():
    if len(sys.argv) < 2:
        csv_path = input('Org Pulse CSV path: ').strip()
    else:
        csv_path = sys.argv[1]

    print(f'Loading model from {MODEL_PATH}...')
    with open(MODEL_PATH, 'rb') as f:
        m = pickle.load(f)
    # Use calibrated RF if v3 model — probabilities are better calibrated (ECE < 0.05)
    rf_pipe = m.get('rf_calibrated') or m['rf']
    imp     = m['imputer']   # IterativeImputer (v3) or SimpleImputer (v2)
    comp_le = m['comp_le']
    model_ver = 'v3 (MICE + calibrated)' if 'rf_calibrated' in m else 'v2 (SimpleImputer)'
    print(f'  Model version : {model_ver}')

    # Slip-count imputation strategy:
    # Training set median = 0 (104 of 115 features have 0 prior slips).
    # Imputing 0 is conservative and consistent with "no known slip history".
    # Slight upward bias for features that actually slipped but we don't know.
    # v3 training with IterativeImputer will reduce this gap.
    SLIP_IMPUTE = 0.0

    rows_all = []
    with open(csv_path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows_all.append(row)

    eligible = [r for r in rows_all if detect_phase(r.get('Target Versions', ''))]
    skipped  = len(rows_all) - len(eligible)
    print(f'CSV rows: {len(rows_all)} total  ·  {len(eligible)} with recognised Target Version  ·  {skipped} skipped (no TV or non-standard)')

    X_raw = np.array(
        [build_feature_vector(r, comp_le, SLIP_IMPUTE) for r in eligible],
        dtype=float
    )
    # Apply the same SimpleImputer as training (fills rice NaN with training median)
    X = imp.transform(X_raw)

    probs = rf_pipe.predict_proba(X)[:, 1]

    results = {}
    print(f"\n{'Key':<22} {'Phase':<6} {'Score':>8}  {'Title'}")
    print('-' * 70)
    for row, p in zip(eligible, probs):
        key     = (row.get('Key') or '').strip()
        phase   = detect_phase(row.get('Target Versions', '')) or 'GA'
        ml_pct  = round(p * 100, 1)
        results[key] = {
            'key':         key,
            'title':       row.get('Title', ''),
            'phase':       phase,
            'rf_prob':     round(float(p), 4),
            'rf_conf_pct': ml_pct,
            'source':      'csv_imputed',   # flag: slip_count was imputed, not observed
        }
        print(f"{key:<22} {phase:<6} {ml_pct:>7}%  {row.get('Title','')[:40]}")

    vals = [v['rf_conf_pct'] for v in results.values()]
    print(f'\n─── CSV Inference Summary ───')
    print(f'  Features scored : {len(results)}')
    print(f'  Mean confidence : {np.mean(vals):.1f}%')
    print(f'  Range           : {np.min(vals):.1f}% – {np.max(vals):.1f}%')
    print(f'  Slip imputation : {SLIP_IMPUTE} (conservative — no prior slip history in CSV)')
    print(f'\n  Note: features also in inference_3.6_ea1_v2.json have BETTER scores')
    print(f'  (those include actual slip history). Run merge_scores.py to combine.')

    with open(OUT_PATH, 'w') as f:
        json.dump(results, f, indent=2)
    print(f'\nSaved → {OUT_PATH}')
    print('\nNext: python merge_scores.py  →  copy ML_SCORES output into index.html')


if __name__ == '__main__':
    main()
