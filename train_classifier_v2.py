"""
RHOAI Release Confidence Classifier — v2
Adds minority-class balancing: SMOTE, ADASYN, Random Oversampling
Compares 4 strategies: baseline (class_weight only), ROS, SMOTE, ADASYN
Each strategy runs LR + RF with 5-fold stratified CV on balanced train splits.
"""

import json
import pickle
import numpy as np
from collections import Counter

from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import roc_auc_score, f1_score, accuracy_score
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

from imblearn.over_sampling import SMOTE, ADASYN, RandomOverSampler

DATA_PATH  = '/Users/yluria/Downloads/RHOAI-fpdor-and-phase-labels/data/features/3.5.json'
OUT_DIR    = '/Users/yluria/Documents/ai-first-scheduler/'
SEED       = 42

JIRA_PRI   = {'Critical': 4, 'High': 3, 'Medium': 2, 'Low': 1}
PHASE_ORD  = {'EA1': 1, 'EA2': 2, 'GA': 3}

# ── 1. Load & featurise ──────────────────────────────────────────────────────
def load_rows():
    rows = []
    with open(DATA_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows

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

def build_dataset(rows):
    committed = [r for r in rows
                 if r.get('committedPhase') and r['committedPhase'] not in (None, 'None', 'never')]
    X_raw, y, keys = [], [], []
    le = LabelEncoder()
    comps = [r.get('primaryComponent') or 'unknown' for r in committed]
    le.fit(comps)
    for r in committed:
        label = 1 if r.get('deliveredPhase') == r.get('committedPhase') else 0
        sig   = extract_fpdor(r.get('fpdorAtFreeze'))
        rice  = r.get('priority', {}).get('rice')
        comp  = r.get('primaryComponent') or 'unknown'
        try:
            comp_enc = le.transform([comp])[0]
        except ValueError:
            comp_enc = 0
        X_raw.append([
            sig['pass_rate'], sig['mandatory_pass_rate'], sig['criteria_pass_rate'],
            sig['passed_count'], sig['rt_pass'], sig['docs_pass'],
            rice if rice is not None else np.nan,
            JIRA_PRI.get(r.get('priority', {}).get('jiraPriority', ''), 0),
            PHASE_ORD.get(r.get('committedPhase', 'GA'), 3),
            len(r.get('slips') or []),
            int(r.get('hasDocsComponent', False)),
            float(comp_enc),
        ])
        y.append(label)
        keys.append(r['key'])
    FEATURE_NAMES = [
        'fpdor_pass_rate', 'mandatory_pass_rate', 'criteria_pass_rate',
        'fpdor_passed_count', 'rt_pass', 'docs_pass',
        'rice', 'jira_priority', 'committed_phase_ord',
        'slip_count', 'has_docs_component', 'component_encoded',
    ]
    return np.array(X_raw, dtype=float), np.array(y), keys, le, FEATURE_NAMES

# ── 2. Impute NaNs before oversampling (SMOTE/ADASYN need clean arrays) ──────
def impute(X):
    imp = SimpleImputer(strategy='median')
    return imp.fit_transform(X), imp

# ── 3. CV with balancing applied inside each fold ────────────────────────────
STRATEGIES = {
    'Baseline\n(class_weight)': None,
    'Random\nOversampling':     RandomOverSampler(random_state=SEED),
    'SMOTE':                    SMOTE(k_neighbors=3, random_state=SEED),   # k=3 for 11 negatives
    'ADASYN':                   ADASYN(n_neighbors=3, random_state=SEED),
}

def make_lr(): return LogisticRegression(class_weight='balanced', max_iter=2000, random_state=SEED, C=1.0)
def make_rf(): return RandomForestClassifier(n_estimators=300, class_weight='balanced',
                                              max_depth=None, min_samples_leaf=1,
                                              random_state=SEED, n_jobs=-1)

def run_cv_strategy(X_clean, y, strategy, k=5):
    skf = StratifiedKFold(n_splits=k, shuffle=True, random_state=SEED)
    results = {m: {s: [] for s in ('acc','auc','f1')} for m in ('lr','rf')}
    for train_idx, test_idx in skf.split(X_clean, y):
        X_tr, X_te = X_clean[train_idx], X_clean[test_idx]
        y_tr, y_te = y[train_idx], y[test_idx]
        if len(np.unique(y_te)) < 2:
            continue
        # apply balancer only to train split
        if strategy is not None:
            try:
                X_tr_b, y_tr_b = strategy.fit_resample(X_tr, y_tr)
            except Exception:
                X_tr_b, y_tr_b = X_tr, y_tr   # fallback if ADASYN fails
        else:
            X_tr_b, y_tr_b = X_tr, y_tr
        for name, model in [('lr', make_lr()), ('rf', make_rf())]:
            # LR needs scaling, RF doesn't — apply scaler manually
            if name == 'lr':
                scl = StandardScaler()
                X_tr_s = scl.fit_transform(X_tr_b)
                X_te_s = scl.transform(X_te)
            else:
                X_tr_s, X_te_s = X_tr_b, X_te
            model.fit(X_tr_s, y_tr_b)
            y_pred = model.predict(X_te_s)
            y_prob = model.predict_proba(X_te_s)[:, 1]
            results[name]['acc'].append(accuracy_score(y_te, y_pred))
            results[name]['auc'].append(roc_auc_score(y_te, y_prob))
            results[name]['f1'].append(f1_score(y_te, y_pred, zero_division=0))
    return results

# ── 4. Main ──────────────────────────────────────────────────────────────────
def main():
    print('='*65)
    print('RHAI Release Confidence Classifier v2 — Balancing Techniques')
    print('='*65)

    rows = load_rows()
    X_raw, y, keys, comp_le, feature_names = build_dataset(rows)
    X_clean, imp = impute(X_raw)

    n_pos, n_neg = y.sum(), (y==0).sum()
    print(f'\nOriginal: {len(y)} samples  |  {n_pos} shipped ({n_pos/len(y)*100:.0f}%)  |  {n_neg} slipped ({n_neg/len(y)*100:.0f}%)')
    print(f'After SMOTE (k=3): ~{n_pos} pos + {n_pos} neg synthetic')

    all_results = {}
    for strat_name, sampler in STRATEGIES.items():
        label = strat_name.replace('\n', ' ')
        print(f'\n── {label} ──')
        res = run_cv_strategy(X_clean, y, sampler, k=5)
        all_results[strat_name] = res
        for m in ('lr','rf'):
            r = res[m]
            print(f'  {m.upper()}  acc={np.mean(r["acc"])*100:.1f}%±{np.std(r["acc"])*100:.1f}%'
                  f'  AUC={np.mean(r["auc"])*100:.1f}%±{np.std(r["auc"])*100:.1f}%'
                  f'  F1={np.mean(r["f1"])*100:.1f}%±{np.std(r["f1"])*100:.1f}%')

    # ── pick best strategy for final model ──────────────────────────────────
    best_strat_name, best_auc = None, -1
    for sname, res in all_results.items():
        auc_rf = np.mean(res['rf']['auc'])
        if auc_rf > best_auc:
            best_auc = auc_rf
            best_strat_name = sname
    print(f'\n── Best strategy for RF: {best_strat_name.replace(chr(10), " ")} (AUC={best_auc*100:.1f}%) ──')

    # ── train final models on full dataset with best strategy ────────────────
    best_sampler = STRATEGIES[best_strat_name]
    if best_sampler is not None:
        X_final, y_final = best_sampler.fit_resample(X_clean, y)
    else:
        X_final, y_final = X_clean, y
    print(f'Final training set: {Counter(y_final)}')

    lr_final = make_lr()
    rf_final = make_rf()
    scl_final = StandardScaler()
    X_final_s = scl_final.fit_transform(X_final)
    lr_final.fit(X_final_s, y_final)
    rf_final.fit(X_final, y_final)

    # ── save models ──────────────────────────────────────────────────────────
    with open(OUT_DIR + 'models_v2.pkl', 'wb') as f:
        pickle.dump({
            'lr': lr_final, 'lr_scaler': scl_final,
            'rf': rf_final,
            'imputer': imp,
            'comp_le': comp_le,
            'feature_names': feature_names,
            'all_cv': all_results,
            'best_strategy': best_strat_name,
        }, f)
    print(f'\nSaved → {OUT_DIR}models_v2.pkl')
    print('\nNext: run plot_cv_v2.py  →  run_inference_v2.py  →  update index.html ML_SCORES')

if __name__ == '__main__':
    main()
