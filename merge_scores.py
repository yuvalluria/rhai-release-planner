"""
Merge inference scores — JSONL-sourced (70 features, with slip history) take
priority over CSV-imputed scores (all features, slip_count=0).

Output: merged_ml_scores.json  +  JS snippet for index.html ML_SCORES const.

Run after both inference scripts:
    python run_inference_csv.py path/to/orgpulse.csv
    python merge_scores.py
"""
import json
import numpy as np

JSONL_PATH   = '/Users/yluria/Documents/ai-first-scheduler/inference_3.6_ea1_v2.json'
CSV_PATH     = '/Users/yluria/Documents/ai-first-scheduler/inference_3.6_csv_v1.json'
OUT_JSON     = '/Users/yluria/Documents/ai-first-scheduler/merged_ml_scores.json'
OUT_JS_SNIP  = '/Users/yluria/Documents/ai-first-scheduler/ml_scores_snippet.js'

with open(JSONL_PATH) as f:
    jsonl_scores = json.load(f)   # {key: {rf_conf_pct, ...}}

with open(CSV_PATH) as f:
    csv_scores   = json.load(f)   # {key: {rf_conf_pct, source:'csv_imputed', ...}}

merged   = {}
sourced  = {'jsonl': 0, 'csv_imputed': 0, 'both': 0}

# Start with all CSV-imputed scores
for key, v in csv_scores.items():
    merged[key] = {'score': v['rf_conf_pct'], 'source': 'csv_imputed', 'phase': v.get('phase')}

# JSONL scores overwrite CSV scores (JSONL is more accurate — includes slip history)
for key, v in jsonl_scores.items():
    pct = v.get('rf_conf_pct', v.get('rf_prob', 0) * 100)
    if key in merged:
        merged[key] = {'score': round(pct, 1), 'source': 'jsonl', 'phase': v.get('committedPhase')}
        sourced['both'] += 1
    else:
        merged[key] = {'score': round(pct, 1), 'source': 'jsonl', 'phase': v.get('committedPhase')}
    sourced['jsonl'] += 1

sourced['csv_imputed'] = len(csv_scores) - sourced['both']

# ── Summary ────────────────────────────────────────────────────────────────
scores = [v['score'] for v in merged.values()]
jsonl_s  = [v['score'] for v in merged.values() if v['source'] == 'jsonl']
csv_s    = [v['score'] for v in merged.values() if v['source'] == 'csv_imputed']

print('─── Merge Summary ───')
print(f'  Total features scored : {len(merged)}')
print(f'  JSONL-sourced (w/slip history)  : {len(jsonl_s)} — mean {np.mean(jsonl_s):.1f}%')
print(f'  CSV-imputed (slip_count=0)      : {len(csv_s)} — mean {np.mean(csv_s):.1f}%')
print(f'  In both (JSONL wins)            : {sourced["both"]}')
print(f'  Overall mean confidence         : {np.mean(scores):.1f}%')
print(f'  Range                           : {np.min(scores):.1f}% – {np.max(scores):.1f}%')

with open(OUT_JSON, 'w') as f:
    json.dump(merged, f, indent=2)
print(f'\nSaved full JSON → {OUT_JSON}')

# ── Generate JS snippet ────────────────────────────────────────────────────
# Produces a const ML_SCORES = {...} block to paste into index.html
# JSONL-sourced entries get no suffix; CSV-imputed get /* ~ */ comment
lines = []
for key, v in sorted(merged.items()):
    suffix = '' if v['source'] == 'jsonl' else ' /* ~ */'
    lines.append(f'  "{key}":{v["score"]}{suffix}')

snippet = 'const ML_SCORES = {\n' + ',\n'.join(lines) + '\n};'

with open(OUT_JS_SNIP, 'w') as f:
    f.write('// ML_SCORES — merged: JSONL (slip history) + CSV-imputed\n')
    f.write(f'// JSONL: {len(jsonl_s)} features  |  CSV-imputed: {len(csv_s)} features\n')
    f.write(f'// Entries marked /* ~ */ have imputed slip_count=0 (lower accuracy)\n\n')
    f.write(snippet)

print(f'JS snippet → {OUT_JS_SNIP}')
print('\nPaste the ML_SCORES const from that file into index.html, replacing the existing one.')
print('Features marked /* ~ */ in the snippet should show ~🤖 in the UI (already handled).')
