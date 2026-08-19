"""
Build extended training data from fpdor cycle snapshots.

Extracts features with clear delivery outcomes (shipped/slipped) from the
per-phase fpdor snapshot files, converts them to the same format as 3.4.jsonl,
and saves a new JSONL file for use as additional training data.

New rows: 185 (158 shipped + 27 slipped), all slip_count=0.
The 27 slipped-with-no-prior-history examples are the main value:
they teach the model to use FPDoR + RICE when slip_count=0.
"""
import json
import pathlib

OUT_PATH = pathlib.Path('/Users/yluria/Documents/ai-first-scheduler/fpdor_cycles_extended.jsonl')

SOURCES = [
    ('3.4', 'EA1', '/Users/yluria/Downloads/feature-labels-3.4-handoff/history/cycles/3.4/fpdor-EA1.json'),
    ('3.4', 'EA2', '/Users/yluria/Downloads/feature-labels-3.4-handoff/history/cycles/3.4/fpdor-EA2.json'),
    ('3.4', 'GA',  '/Users/yluria/Downloads/feature-labels-3.4-handoff/history/cycles/3.4/fpdor-GA.json'),
    ('3.5', 'EA1', '/Users/yluria/Downloads/RHOAI-fpdor-and-phase-labels/data/cycles-3.5/fpdor-EA1.json'),
    ('3.5', 'EA2', '/Users/yluria/Downloads/RHOAI-fpdor-and-phase-labels/data/cycles-3.5/fpdor-EA2.json'),
    ('3.5', 'GA',  '/Users/yluria/Downloads/RHOAI-fpdor-and-phase-labels/data/cycles-3.5/fpdor-GA.json'),
]

# Already committed in current training — skip these
CURRENT_TRAINING = {}
for path in [
    '/Users/yluria/Downloads/feature-labels-3.4-handoff/history/features/3.4.jsonl',
    '/Users/yluria/Downloads/RHOAI-fpdor-and-phase-labels/data/features/3.5.json',
]:
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                r = json.loads(line)
                if r.get('committedPhase') not in (None, 'None', 'never'):
                    CURRENT_TRAINING[r['key']] = r

# Also load ALL rows for slip_count lookup (including uncommitted)
ALL_KNOWN = {}
for path in [
    '/Users/yluria/Downloads/feature-labels-3.4-handoff/history/features/3.4.jsonl',
    '/Users/yluria/Downloads/RHOAI-fpdor-and-phase-labels/data/features/3.5.json',
]:
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                r = json.loads(line)
                ALL_KNOWN[r['key']] = r

print(f'Current training keys: {len(CURRENT_TRAINING)}')

CLEAR_SHIPPED = {'closed_by_t1', 'done_lag_after_t1'}
CLEAR_SLIPPED = {'still_open_post_t1'}

seen_keys = set(CURRENT_TRAINING.keys())
rows_out = []
stats = {'shipped': 0, 'slipped': 0, 'skipped_no_fpdor': 0, 'skipped_unclear': 0, 'skipped_dupe': 0}

for cycle_ver, phase, path in SOURCES:
    with open(path) as f:
        d = json.load(f)
    for feat in d.get('features', []):
        k = feat['key']
        closure_val = (feat.get('closure') or {}).get('closure', '')
        fpdor = feat.get('fpdorAtFreeze')

        if k in seen_keys:
            stats['skipped_dupe'] += 1
            continue
        if not fpdor:
            stats['skipped_no_fpdor'] += 1
            continue
        if closure_val not in CLEAR_SHIPPED and closure_val not in CLEAR_SLIPPED:
            stats['skipped_unclear'] += 1
            continue

        seen_keys.add(k)

        shipped = closure_val in CLEAR_SHIPPED
        committed_phase = phase
        delivered_phase = phase if shipped else 'never'

        # Get slip_count from known files if available
        known = ALL_KNOWN.get(k)
        slip_count = len(known.get('slips') or []) if known else 0

        inp = feat.get('inputsAtFreeze', {})
        components = inp.get('components') or []
        has_docs = 'Documentation' in components

        row = {
            'schemaVersion':    2,
            'cycleVersion':     cycle_ver,
            'key':              k,
            'summary':          feat.get('summary', ''),
            'product':          feat.get('product', 'RHOAI'),
            'components':       components,
            'hasDocsComponent': has_docs,
            'primaryComponent': components[0] if components else 'unknown',
            'priority': {
                'jiraPriority': inp.get('priority') or 'Medium',
                'rice':         inp.get('riceScore'),
            },
            'committedPhase':   committed_phase,
            'deliveredPhase':   delivered_phase,
            'slips':            [{'fromPhase': phase, 'toPhase': 'never'}] * slip_count,
            'fpdorAtFreeze':    fpdor,
            '_source':          f'fpdor-cycle-{cycle_ver}-{phase}',
            '_closure':         closure_val,
        }

        rows_out.append(row)
        if shipped:
            stats['shipped'] += 1
        else:
            stats['slipped'] += 1

print(f'\nRows to write: {len(rows_out)}')
print(f'  Shipped: {stats["shipped"]} | Slipped: {stats["slipped"]}')
print(f'  Skipped dupes: {stats["skipped_dupe"]} | No FPDoR: {stats["skipped_no_fpdor"]} | Unclear closure: {stats["skipped_unclear"]}')

with open(OUT_PATH, 'w') as f:
    for row in rows_out:
        f.write(json.dumps(row) + '\n')

print(f'\nSaved → {OUT_PATH}')
print('\nNew training totals (after adding this file):')
print(f'  Total rows:   {len(CURRENT_TRAINING) + len(rows_out)}  (was {len(CURRENT_TRAINING)})')
slipped_current = sum(1 for r in CURRENT_TRAINING.values()
                      if r.get('deliveredPhase') != r.get('committedPhase'))
print(f'  Slipped:      {slipped_current + stats["slipped"]}  (was {slipped_current})')
print(f'  Shipped:      {len(CURRENT_TRAINING) - slipped_current + stats["shipped"]}  (was {len(CURRENT_TRAINING) - slipped_current})')
