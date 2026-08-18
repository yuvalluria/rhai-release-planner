"""
Inference v2 — uses RF trained with Random Oversampling (best strategy).
Outputs inference_3.6_ea1_v2.json keyed by RHAISTRAT key.
"""
import json, pickle
import numpy as np

MODEL_PATH = '/Users/yluria/Documents/ai-first-scheduler/models_v2.pkl'
DATA_PATH  = '/Users/yluria/Downloads/RHOAI-fpdor-and-phase-labels/data/features/3.6-EA1-freeze-baseline.jsonl'
OUT_PATH   = '/Users/yluria/Documents/ai-first-scheduler/inference_3.6_ea1_v2.json'

HIST_CAP   = {'EA1': 75, 'EA2': 60, 'GA': 40}
JIRA_PRI   = {'Critical': 4, 'High': 3, 'Medium': 2, 'Low': 1}
PHASE_ORD  = {'EA1': 1, 'EA2': 2, 'GA': 3}

with open(MODEL_PATH, 'rb') as f:
    m = pickle.load(f)

rf_pipe  = m['rf']
imp      = m['imputer']
comp_le  = m['comp_le']

def extract_fpdor(fpdor):
    if not fpdor:
        return dict(pass_rate=0, mandatory_pass_rate=0, criteria_pass_rate=0,
                    passed_count=0, rt_pass=0, docs_pass=0)
    items      = fpdor.get('items', [])
    applicable = [i for i in items if i.get('state') != 'not-checked']
    mandatory  = [i for i in applicable if i.get('group') == 'mandatory']
    criteria   = [i for i in applicable if i.get('group') == 'criteria']
    def pr(lst): return sum(1 for i in lst if i.get('pass')) / len(lst) if lst else 0.0
    rt   = next((i for i in items if i['name'] == 'Release Type'), None)
    docs = next((i for i in items if i['name'] == 'Docs impact'),   None)
    ac   = fpdor.get('applicableCount', 1) or 1
    return dict(
        pass_rate           = fpdor.get('passedCount', 0) / ac,
        mandatory_pass_rate = pr(mandatory),
        criteria_pass_rate  = pr(criteria),
        passed_count        = fpdor.get('passedCount', 0),
        rt_pass             = int(rt['pass'] == True)   if rt   else 0,
        docs_pass           = int(docs['pass'] == True) if docs else 0,
    )

def build_row(r):
    sig  = extract_fpdor(r.get('fpdorAtFreeze'))
    comp = r.get('primaryComponent') or 'unknown'
    try:
        comp_enc = comp_le.transform([comp])[0]
    except ValueError:
        comp_enc = 0
    rice = r.get('priority', {}).get('rice')
    return [
        sig['pass_rate'], sig['mandatory_pass_rate'], sig['criteria_pass_rate'],
        sig['passed_count'], sig['rt_pass'], sig['docs_pass'],
        rice if rice is not None else np.nan,
        JIRA_PRI.get(r.get('priority', {}).get('jiraPriority', ''), 0),
        PHASE_ORD.get(r.get('committedPhase', 'EA1'), 1),
        len(r.get('slips') or []),
        int(r.get('hasDocsComponent', False)),
        float(comp_enc),
    ]

rows_36 = []
with open(DATA_PATH) as f:
    for line in f:
        line = line.strip()
        if line:
            rows_36.append(json.loads(line))

committed_36 = [r for r in rows_36
                if r.get('committedPhase') and r['committedPhase'] not in (None, 'None')]

print(f'3.6 EA1 baseline: {len(rows_36)} total, {len(committed_36)} with committedPhase')

X36_raw = np.array([build_row(r) for r in committed_36])
X36     = imp.transform(X36_raw)
probs   = rf_pipe.predict_proba(X36)[:, 1]

results = {}
print(f"\n{'Key':<20} {'Phase':<6} {'Old cap':>8} {'ROS+RF':>8} {'Delta':>7}")
for r, p in zip(committed_36, probs):
    phase   = r.get('committedPhase', 'EA1')
    old_cap = HIST_CAP.get(phase, 60)
    ml_pct  = round(p * 100, 1)
    delta   = ml_pct - old_cap
    results[r['key']] = {
        'key':            r['key'],
        'summary':        r.get('summary', ''),
        'committedPhase': phase,
        'old_hist_cap':   old_cap,
        'rf_prob':        round(p, 4),
        'rf_conf_pct':    ml_pct,
        'delta_vs_cap':   round(delta, 1),
    }
    print(f"{r['key']:<20} {phase:<6} {old_cap:>7}%  {ml_pct:>7}%  {delta:>+6.1f}%")

ml_probs = [v['rf_conf_pct'] for v in results.values()]
print(f'\nRF (ROS) mean: {np.mean(ml_probs):.1f}%  range: {np.min(ml_probs):.1f}%–{np.max(ml_probs):.1f}%')

with open(OUT_PATH, 'w') as f:
    json.dump(results, f, indent=2)
print(f'Saved → {OUT_PATH}')
