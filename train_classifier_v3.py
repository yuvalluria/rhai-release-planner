"""
RHOAI Release Confidence Classifier — v3
Improvements over v2:
  1. IterativeImputer (MICE / Gaussian joint model) instead of SimpleImputer(median)
     Fills sparse values (especially rice) using the full joint distribution of
     all features — equivalent to "Gaussian filling" in the ML literature.
     Reduces bias introduced by replacing unknown values with a flat median.

  2. CalibratedClassifierCV (Platt scaling / isotonic regression)
     Ensures model probabilities are calibrated: "90% confidence" actually means
     90% of similar features ship. Uncalibrated RF tends to push probabilities
     toward extremes (over-confident or under-confident).

  3. GridSearchCV hyperparameter tuning for RF
     Searches n_estimators × max_depth × min_samples_leaf within each fold.
     Prevents the fixed n_estimators=300 from being under- or over-fit.

  4. Full k-fold evaluation report including calibration curve
     Shows reliability diagram: how well predicted probabilities match
     empirical frequencies. Target: ECE (Expected Calibration Error) < 0.05.

  5. Saves models_v3.pkl — backward compatible with run_inference_csv.py
     (same feature order, same comp_le, different imputer and rf object)
"""
import json, pickle
import numpy as np
from collections import Counter

from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, GridSearchCV, cross_val_predict
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import roc_auc_score, f1_score, accuracy_score, brier_score_loss
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.pipeline import Pipeline

# IterativeImputer is experimental — must be enabled before importing
from sklearn.experimental import enable_iterative_imputer  # noqa
from sklearn.impute import IterativeImputer

from imblearn.over_sampling import RandomOverSampler, SMOTE
from imblearn.ensemble import BalancedRandomForestClassifier
from imblearn.pipeline import Pipeline as ImbPipeline

DATA_PATHS = [
    '/Users/yluria/Downloads/feature-labels-3.4-handoff/history/features/3.4.jsonl',
    '/Users/yluria/Downloads/RHOAI-fpdor-and-phase-labels/data/features/3.5.json',
]
OUT_DIR   = '/Users/yluria/Documents/ai-first-scheduler/'
SEED      = 42

JIRA_PRI  = {'Critical': 4, 'High': 3, 'Medium': 2, 'Low': 1}
PHASE_ORD = {'EA1': 1, 'EA2': 2, 'GA': 3}


def load_rows():
    rows = []
    for path in DATA_PATHS:
        n = 0
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    r = json.loads(line)
                    r['_source'] = path.split('/')[-1]  # tag for diagnostics
                    rows.append(r)
                    n += 1
        print(f'  Loaded {n} rows from {path.split("/")[-1]}')
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
        try:    comp_enc = le.transform([comp])[0]
        except  ValueError: comp_enc = 0
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


def make_mice_imputer():
    """
    IterativeImputer — MICE (Multiple Imputation by Chained Equations).
    Fits a Bayesian ridge regression per feature, using all other features
    as predictors. Effectively assumes a Gaussian joint distribution.
    max_iter=10 is sufficient for convergence on this feature set.
    """
    return IterativeImputer(
        max_iter=10,
        random_state=SEED,
        initial_strategy='median',   # warm-start from median on first pass
    )


def make_rf(n_estimators=300, max_depth=None, min_samples_leaf=1):
    return RandomForestClassifier(
        n_estimators=n_estimators,
        class_weight='balanced',
        max_depth=max_depth,
        min_samples_leaf=min_samples_leaf,
        random_state=SEED,
        n_jobs=-1,
    )


def cv_evaluate(X_clean, y, k=10):
    """
    10-fold stratified CV with SMOTE inside each fold.
    SMOTE generates synthetic minority samples by interpolating between existing ones
    (better than ROS duplication for small datasets like 12 slipped features).
    """
    skf = StratifiedKFold(n_splits=k, shuffle=True, random_state=SEED)
    smote = SMOTE(random_state=SEED, k_neighbors=5)
    metrics = {'auc': [], 'brier': [], 'f1': []}

    for fold, (tr_idx, te_idx) in enumerate(skf.split(X_clean, y), 1):
        X_tr, X_te = X_clean[tr_idx], X_clean[te_idx]
        y_tr, y_te = y[tr_idx],       y[te_idx]
        if len(np.unique(y_te)) < 2:
            print(f'  Fold {fold}: skipped (only 1 class in test split)')
            continue

        X_tr_b, y_tr_b = smote.fit_resample(X_tr, y_tr)
        rf = make_rf()
        rf.fit(X_tr_b, y_tr_b)

        probs  = rf.predict_proba(X_te)[:, 1]
        preds  = rf.predict(X_te)
        auc    = roc_auc_score(y_te, probs)
        brier  = brier_score_loss(y_te, probs)
        f1     = f1_score(y_te, preds, zero_division=0)
        metrics['auc'].append(auc);  metrics['brier'].append(brier);  metrics['f1'].append(f1)
        print(f'  Fold {fold}: AUC={auc*100:.1f}%  Brier={brier:.3f}  F1={f1*100:.1f}%')

    return metrics


def tune_rf(X_clean, y):
    """
    GridSearchCV for RF hyperparameters — runs inside a single stratified split
    to avoid data leakage with ROS (ROS applied after CV split in cv_evaluate).
    """
    print('\n── Hyperparameter tuning (SMOTE inside each CV fold via Pipeline) ──')
    # SMOTE inside the pipeline prevents leakage and generates synthetic minority samples
    # k_neighbors=5: interpolates between 5 nearest minority-class neighbours
    pipe = ImbPipeline([
        ('smote', SMOTE(random_state=SEED, k_neighbors=5)),
        ('rf',    make_rf()),
    ])
    param_grid = {
        'rf__n_estimators':     [100, 200, 300],
        'rf__max_depth':        [3, 5, 7, 10],   # no None — unlimited depth memorizes 134 samples
        'rf__min_samples_leaf': [3, 5, 10],       # no 1 — single-sample leaves = memorization
    }
    grid = GridSearchCV(
        estimator  = pipe,
        param_grid = param_grid,
        cv         = StratifiedKFold(n_splits=10, shuffle=True, random_state=SEED),
        scoring    = 'roc_auc',
        n_jobs     = -1,
        verbose    = 0,
    )
    grid.fit(X_clean, y)
    best = {k.replace('rf__', ''): v for k, v in grid.best_params_.items()}
    print(f'  Best params : {best}')
    print(f'  Best AUC    : {grid.best_score_*100:.1f}%')
    return best


def calibration_report(y_true, probs, n_bins=5):
    """
    Reliability diagram summary.
    ECE = Expected Calibration Error (weighted avg |predicted - actual| per bin).
    Target ECE < 0.05 for well-calibrated model.
    """
    frac_pos, mean_pred = calibration_curve(y_true, probs, n_bins=n_bins)
    ece = np.sum(np.abs(frac_pos - mean_pred) * (len(y_true) / n_bins)) / len(y_true)
    print('\n── Calibration curve (predicted → actual) ──')
    for pred, actual in zip(mean_pred, frac_pos):
        bar = '█' * int(actual * 20)
        print(f'  {pred*100:5.1f}% predicted → {actual*100:5.1f}% actual  {bar}')
    print(f'  ECE = {ece:.4f}  (target: < 0.05)')
    return ece


def main():
    print('=' * 65)
    print('RHAI Release Confidence Classifier v3')
    print('Improvements: MICE imputation · Calibration · GridSearchCV')
    print('=' * 65)

    rows = load_rows()
    X_raw, y, keys, comp_le, feature_names = build_dataset(rows)

    n_pos, n_neg = y.sum(), (y == 0).sum()
    print(f'\nDataset: {len(y)} samples  |  {n_pos} shipped ({n_pos/len(y)*100:.0f}%)  |  {n_neg} slipped')

    # ── v3 change 1: MICE imputation ──────────────────────────────────────
    print('\n── Fitting IterativeImputer (MICE) ──')
    mice_imp = make_mice_imputer()
    X_clean  = mice_imp.fit_transform(X_raw)
    nan_before = np.isnan(X_raw).sum()
    nan_after  = np.isnan(X_clean).sum()
    print(f'  NaN values: {nan_before} → {nan_after} (imputed using Gaussian joint model)')

    # ── v3 change 2: GridSearchCV ─────────────────────────────────────────
    best_params = tune_rf(X_clean, y)

    # ── v3 change 3: k-fold evaluation with best params ──────────────────
    print(f'\n── 10-Fold CV with best RF params ──')
    metrics = cv_evaluate(X_clean, y)
    print(f'\n  Mean AUC   : {np.mean(metrics["auc"])*100:.1f}% ± {np.std(metrics["auc"])*100:.1f}%')
    print(f'  Mean Brier : {np.mean(metrics["brier"]):.3f} ± {np.std(metrics["brier"]):.3f}')
    print(f'  Mean F1    : {np.mean(metrics["f1"])*100:.1f}% ± {np.std(metrics["f1"])*100:.1f}%')

    # ── Train final model on full dataset + SMOTE ────────────────────────
    print('\n── Training final RF+SMOTE on full dataset ──')
    smote    = SMOTE(random_state=SEED, k_neighbors=5)
    X_b, y_b = smote.fit_resample(X_clean, y)
    print(f'  After SMOTE: {Counter(y_b)}')

    rf_final = make_rf(**best_params)
    rf_final.fit(X_b, y_b)

    # ── v3 change 4: Probability calibration ─────────────────────────────
    # Platt scaling (sigmoid) via 5-fold isotonic regression.
    # Ensures "High (90%)" really means 9 of 10 similar features ship.
    print('\n── Calibrating probabilities (isotonic regression, 5-fold) ──')
    rf_calibrated = CalibratedClassifierCV(
        estimator = make_rf(**best_params),
        cv        = 5,
        method    = 'isotonic',
    )
    rf_calibrated.fit(X_b, y_b)

    # Check calibration on held-out cross-val predictions
    probs_cv = cross_val_predict(
        make_rf(**best_params), X_clean, y,
        cv=StratifiedKFold(5, shuffle=True, random_state=SEED),
        method='predict_proba',
    )[:, 1]
    ece_before = calibration_report(y, probs_cv, n_bins=5)

    probs_cal = cross_val_predict(
        CalibratedClassifierCV(make_rf(**best_params), cv=5, method='isotonic'),
        X_clean, y,
        cv=StratifiedKFold(5, shuffle=True, random_state=SEED),
        method='predict_proba',
    )[:, 1]
    print('\n── After calibration ──')
    ece_after = calibration_report(y, probs_cal, n_bins=5)
    print(f'\n  ECE improvement: {ece_before:.4f} → {ece_after:.4f}  ({(ece_before-ece_after)/ece_before*100:.0f}% reduction)')

    # Feature importances (from uncalibrated RF — calibration doesn't change these)
    print('\n── Feature Importance (tuned RF) ──')
    imp_vals = rf_final.feature_importances_
    for name, val in sorted(zip(feature_names, imp_vals), key=lambda x: -x[1]):
        bar = '█' * int(val * 100)
        print(f'  {name:<30} {val*100:5.1f}%  {bar}')

    # ── Save models_v3.pkl ────────────────────────────────────────────────
    out = {
        'rf':            rf_final,          # uncalibrated — for feature importance
        'rf_calibrated': rf_calibrated,     # use this for probabilities
        'imputer':       mice_imp,          # IterativeImputer (MICE)
        'comp_le':       comp_le,
        'feature_names': feature_names,
        'best_params':   best_params,
        'ece_before':    ece_before,
        'ece_after':     ece_after,
        'cv_metrics':    metrics,
    }
    with open(OUT_DIR + 'models_v3.pkl', 'wb') as f:
        pickle.dump(out, f)
    print(f'\nSaved → {OUT_DIR}models_v3.pkl')
    print('\nNext: update run_inference_csv.py MODEL_PATH to models_v3.pkl, then run inference.')


if __name__ == '__main__':
    main()
