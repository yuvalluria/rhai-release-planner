"""
RHOAI Release Confidence Classifier — v8
Upgrade from v7 (RF only, AUC 85.4%) to soft-voting ensemble.

Changes vs v7:
  * Training data: 416 samples (185 real + 231 Arjay historical, all RHOAI schema)
  * Ensemble: RandomForest + GradientBoosting + LogisticRegression (soft vote, isotonic calibration)
  * New features: feature_pts (3/5/8/13), component_count, release_type_ord (DP=2,TP=1,GA=0)
  * Removed: jira_priority — confirmed circular by Arjay+Erle (Aug 26 sync)
  * SMOTE ratio=0.3 — increased from default to compensate for Arjay data diluting slip class

Key decisions from Arjay/Yuval sync (Aug 26):
  - Use delivered metrics not committed (label = deliveredPhase == committedPhase) ✓ already done
  - Dev Preview +8, Tech Preview +5 → encoded as release_type_ord 2/1/0
  - RICE is not primary; effort sizing (feature_pts) is more honest signal
  - Capacity planning: CI approach over precise averages ✓ Arjay's model already uses 90% CI
"""
import json, pickle, re
import numpy as np
from collections import Counter

from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, VotingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import roc_auc_score, f1_score, brier_score_loss
from sklearn.calibration import CalibratedClassifierCV, calibration_curve

from sklearn.experimental import enable_iterative_imputer  # noqa
from sklearn.impute import IterativeImputer

from imblearn.over_sampling import SMOTE

DATA_PATH            = '/Users/yluria/Documents/ai-first-scheduler/training_extended_v8.jsonl'
PLANNING_SIGNALS_PATH = '/Users/yluria/Documents/ai-first-scheduler/planning_signals_3.4.json'
OUT_PATH             = '/Users/yluria/Documents/ai-first-scheduler/models_v8.pkl'
SEED                 = 42

PHASE_ORD = {'EA1': 1, 'EA2': 2, 'GA': 3}
SIZE_PTS  = {'Small': 3, 'Medium': 5, 'Large': 8, 'Extra Large': 13, 'XL': 13}


def load_planning_signals():
    try:
        with open(PLANNING_SIGNALS_PATH) as f:
            return json.load(f)
    except FileNotFoundError:
        print(f'  [WARN] planning_signals_3.4.json not found — architect_score will be all-NaN')
        return {}


def load_rows():
    rows = []
    with open(DATA_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    print(f'  Loaded {len(rows)} rows from {DATA_PATH.split("/")[-1]}')
    return rows


def extract_fpdor(fpdor):
    if not fpdor:
        return dict(pass_rate=np.nan, mandatory_pass_rate=np.nan, criteria_pass_rate=np.nan,
                    passed_count=np.nan, rt_pass=np.nan, docs_pass=np.nan)
    items      = fpdor.get('items', [])
    applicable = [i for i in items if i.get('state') != 'not-checked']
    mandatory  = [i for i in applicable if i.get('group') == 'mandatory']
    criteria   = [i for i in applicable if i.get('group') == 'criteria']
    def pr(lst): return sum(1 for i in lst if i.get('pass')) / len(lst) if lst else 0.0
    rt   = next((i for i in items if i['name'] == 'Release Type'), None)
    docs = next((i for i in items if i['name'] == 'Docs impact'),  None)
    ac   = fpdor.get('applicableCount', 1) or 1
    return dict(
        pass_rate           = fpdor.get('passedCount', 0) / ac,
        mandatory_pass_rate = pr(mandatory),
        criteria_pass_rate  = pr(criteria),
        passed_count        = fpdor.get('passedCount', 0),
        rt_pass             = int(rt['pass'] == True)   if rt   else 0,
        docs_pass           = int(docs['pass'] == True) if docs else 0,
    )


def get_release_type_ord(r):
    """Dev Preview=2, Tech Preview=1, GA=0. Check summary + labels."""
    text = (r.get('summary', '') + ' ' + ' '.join(r.get('labels', [])
            if isinstance(r.get('labels'), list) else [str(r.get('labels', ''))])).lower()
    if '[dp]' in text or 'dev preview' in text or 'development preview' in text:
        return 2
    if '[tp]' in text or 'tech preview' in text or 'technical preview' in text:
        return 1
    return 0


def build_dataset(rows, planning_signals):
    committed = [r for r in rows
                 if r.get('committedPhase') and r['committedPhase'] not in (None, 'None', 'never')]
    X_raw, y, keys = [], [], []

    le = LabelEncoder()
    comps = [r.get('primaryComponent') or 'unknown' for r in committed]
    le.fit(comps)

    hit, miss = 0, 0
    for r in committed:
        label = 1 if r.get('deliveredPhase') == r.get('committedPhase') else 0
        sig   = extract_fpdor(r.get('fpdorAtFreeze'))
        rice  = r.get('priority', {}).get('rice') if isinstance(r.get('priority'), dict) else None
        comp  = r.get('primaryComponent') or 'unknown'
        try:    comp_enc = le.transform([comp])[0]
        except  ValueError: comp_enc = 0

        # New v8 features
        feat_pts       = float(r.get('feature_pts') or
                               SIZE_PTS.get(r.get('size_category', ''), 5))
        comp_count     = float(r.get('component_count') or len(r.get('components') or []))
        rt_ord         = float(get_release_type_ord(r))

        key = r['key']
        ps  = planning_signals.get(key, {})
        if ps:  hit += 1
        else:   miss += 1

        X_raw.append([
            # FPDoR features (6)
            sig['pass_rate'], sig['mandatory_pass_rate'], sig['criteria_pass_rate'],
            sig['passed_count'], sig['rt_pass'], sig['docs_pass'],
            # RICE (1) — kept but jira_priority REMOVED (circular)
            rice if rice is not None else np.nan,
            # Phase / slip history (2)
            PHASE_ORD.get(r.get('committedPhase', 'GA'), 3),
            len(r.get('slips') or []),
            # Component signals (2)
            int(r.get('hasDocsComponent', False)),
            float(comp_enc),
            # Planning signals from 3.4 spreadsheet (4)
            float(ps['architect_score']) if 'architect_score' in ps else np.nan,
            float(ps.get('has_process_risk', 0)),
            float(ps.get('has_schedule_risk', 0)),
            float(ps.get('missing_rfe', 0)),
            # NEW v8 signals (3)
            feat_pts,
            comp_count,
            rt_ord,
        ])
        y.append(label)
        keys.append(key)

    print(f'  Planning signals matched: {hit}/{hit+miss} training rows')

    FEATURE_NAMES = [
        'fpdor_pass_rate', 'mandatory_pass_rate', 'criteria_pass_rate',
        'fpdor_passed_count', 'rt_pass', 'docs_pass',
        'rice',
        'committed_phase_ord', 'slip_count',
        'has_docs_component', 'component_encoded',
        'architect_score', 'has_process_risk', 'has_schedule_risk', 'missing_rfe',
        # new v8
        'feature_pts', 'component_count', 'release_type_ord',
    ]
    return np.array(X_raw, dtype=float), np.array(y), keys, le, FEATURE_NAMES


def make_ensemble():
    rf = RandomForestClassifier(
        n_estimators=300, class_weight='balanced',
        max_depth=None, min_samples_leaf=3,
        random_state=SEED, n_jobs=-1,
    )
    gb = GradientBoostingClassifier(
        n_estimators=200, max_depth=4, learning_rate=0.05,
        subsample=0.8, random_state=SEED,
    )
    lr = LogisticRegression(
        class_weight='balanced', C=0.1,
        max_iter=1000, random_state=SEED,
    )
    return VotingClassifier(
        estimators=[('rf', rf), ('gb', gb), ('lr', lr)],
        voting='soft',
    )


def cv_evaluate(X_clean, y, k=10):
    skf     = StratifiedKFold(n_splits=k, shuffle=True, random_state=SEED)
    smote   = SMOTE(random_state=SEED, k_neighbors=3,
                    sampling_strategy=0.3)   # oversample to 30% of majority
    metrics = {'auc': [], 'brier': [], 'f1': []}

    for fold, (tr_idx, te_idx) in enumerate(skf.split(X_clean, y), 1):
        X_tr, X_te = X_clean[tr_idx], X_clean[te_idx]
        y_tr, y_te = y[tr_idx],       y[te_idx]
        if len(np.unique(y_te)) < 2:
            print(f'  Fold {fold}: skipped (only 1 class in test split)')
            continue
        X_tr_b, y_tr_b = smote.fit_resample(X_tr, y_tr)
        ens = make_ensemble()
        ens.fit(X_tr_b, y_tr_b)
        probs = ens.predict_proba(X_te)[:, 1]
        preds = ens.predict(X_te)
        auc   = roc_auc_score(y_te, probs)
        brier = brier_score_loss(y_te, probs)
        f1    = f1_score(y_te, preds, zero_division=0)
        metrics['auc'].append(auc)
        metrics['brier'].append(brier)
        metrics['f1'].append(f1)
        print(f'  Fold {fold:2d}: AUC={auc*100:.1f}%  Brier={brier:.3f}  F1={f1*100:.1f}%')

    return metrics


def calibration_report(y_true, probs, n_bins=5):
    frac_pos, mean_pred = calibration_curve(y_true, probs, n_bins=n_bins)
    ece = np.sum(np.abs(frac_pos - mean_pred) * (len(y_true) / n_bins)) / len(y_true)
    print('\n── Calibration ──')
    for pred, actual in zip(mean_pred, frac_pos):
        bar = '█' * int(actual * 20)
        print(f'  {pred*100:5.1f}% predicted → {actual*100:5.1f}% actual  {bar}')
    print(f'  ECE = {ece:.4f}  (target: < 0.05)')
    return ece


def main():
    V7_AUC_BASELINE = 85.4

    print('=' * 65)
    print('RHOAI Release Confidence Classifier — v8')
    print('Ensemble: RandomForest + GradientBoosting + LogisticRegression')
    print('New features: feature_pts, component_count, release_type_ord')
    print('Removed: jira_priority (circular)')
    print('=' * 65)

    planning_signals = load_planning_signals()
    print(f'Loaded planning signals for {len(planning_signals)} features')

    rows = load_rows()
    arjay_count = sum(1 for r in rows if r.get('_source') == 'arjay_csv')
    print(f'  Original rows: {len(rows) - arjay_count}  |  Arjay historical: {arjay_count}')

    X_raw, y, keys, comp_le, feature_names = build_dataset(rows, planning_signals)

    n_pos = y.sum()
    n_neg = (y == 0).sum()
    print(f'\nDataset: {len(y)} samples  |  {n_pos} shipped ({n_pos/len(y)*100:.0f}%)  '
          f'|  {n_neg} slipped ({n_neg/len(y)*100:.0f}%)')

    print('\n── MICE imputation ──')
    mice_imp = IterativeImputer(max_iter=10, random_state=SEED, initial_strategy='median')
    X_clean  = mice_imp.fit_transform(X_raw)
    print(f'  NaN: {np.isnan(X_raw).sum()} → {np.isnan(X_clean).sum()}')

    print('\n── 10-Fold Stratified CV (ensemble, SMOTE ratio=0.3) ──')
    metrics = cv_evaluate(X_clean, y)
    mean_auc = np.mean(metrics['auc']) * 100
    std_auc  = np.std(metrics['auc'])  * 100
    print(f'\n  Mean AUC   : {mean_auc:.1f}% ± {std_auc:.1f}%')
    print(f'  Mean Brier : {np.mean(metrics["brier"]):.3f} ± {np.std(metrics["brier"]):.3f}')
    print(f'  Mean F1    : {np.mean(metrics["f1"])*100:.1f}% ± {np.std(metrics["f1"])*100:.1f}%')

    print('\n── Training final ensemble on full dataset (SMOTE) ──')
    smote    = SMOTE(random_state=SEED, k_neighbors=3, sampling_strategy=0.3)
    X_b, y_b = smote.fit_resample(X_clean, y)
    print(f'  After SMOTE: {Counter(y_b)}')

    ens_final = make_ensemble()
    ens_final.fit(X_b, y_b)

    print('\n── Calibrating (isotonic, 5-fold) ──')
    ens_calibrated = CalibratedClassifierCV(make_ensemble(), cv=5, method='isotonic')
    ens_calibrated.fit(X_b, y_b)

    probs_cv = cross_val_predict(
        make_ensemble(), X_clean, y,
        cv=StratifiedKFold(5, shuffle=True, random_state=SEED),
        method='predict_proba',
    )[:, 1]
    calibration_report(y, probs_cv)

    # Feature importance from RF component
    rf_component = ens_final.estimators_[0]   # RF is first
    print('\n── Feature Importance (RF component) ──')
    for name, val in sorted(zip(feature_names, rf_component.feature_importances_), key=lambda x: -x[1]):
        bar = '█' * int(val * 80)
        print(f'  {name:<30} {val*100:5.1f}%  {bar}')

    print('\n' + '=' * 65)
    print(f'  v7 baseline AUC : {V7_AUC_BASELINE:.1f}%')
    print(f'  v8 ensemble AUC : {mean_auc:.1f}% ± {std_auc:.1f}%')
    delta = mean_auc - V7_AUC_BASELINE
    print(f'  Delta           : {delta:+.1f}%')
    print('=' * 65)

    out = {
        'model':          ens_final,
        'model_calibrated': ens_calibrated,
        'imputer':        mice_imp,
        'le':             comp_le,
        'feature_names':  feature_names,
        'cv_metrics':     metrics,
        'version':        'v8',
        'n_samples':      len(y),
        'n_slipped':      int(n_neg),
        'mean_auc':       mean_auc,
        'std_auc':        std_auc,
    }
    with open(OUT_PATH, 'wb') as f:
        pickle.dump(out, f)
    print(f'\nSaved → {OUT_PATH}')
    print('Next: update run_inference_v2.py and run_inference_csv.py to load models_v8.pkl')


if __name__ == '__main__':
    main()
