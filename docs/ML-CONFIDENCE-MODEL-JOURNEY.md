# ML Confidence Model Journey (v1 → v6 + v7 experiment)

**Purpose:** Record how the AI-First release planner confidence model was built, what each version tried, and what the working group should use today.

**Last updated:** 2026-08-26  
**Working group:** Erle, John, Yuval, Eder  
**Owner track:** Yuval (training / demo scores)

---

## Current recommendation

Use **v6** for live scoring of 3.6 candidates. It is the freeze-track production model: **n=319**, **39 slipped**, **AUC about 85.4%** (10-fold CV). Treat **v7** (architect spreadsheet signals) as an experiment only. It gained about **+0.1% AUC**, but only ~15% of training rows have architect scores, and **no 3.6 features** have those scores at inference time. Do not switch live scoring to v7 until coverage is fixed.

---

## What the model does

Predict whether a feature **committed at planning freeze** will **ship in its planned phase** or **slip**.

- **Training labels:** sealed delivery outcomes (committed phase vs delivered phase / slips), plus **FPDoR-at-freeze** and related signals.
- **Inference:** scores live on **3.6** candidates (demo / Candidate Plan confidence column).
- **Not a packing engine:** schedule placement still comes from packer + capacity logic. This model only estimates delivery risk.

---

## Version table

| Version | Data | What we tried | Result | Why it mattered |
|---------|------|---------------|--------|-----------------|
| **v1** | 3.5 only, n=115 (11 slipped) | LR L1/L2/Ridge/ElasticNet vs RF; drop NaN / median / MICE; ROS / SMOTE / ADASYN; Isolation Forest; overfit demo | RF+ROS ~91.9% AUC; SMOTE weak at n=11; unlimited depth → fake ~100% confidence | Established baselines and which levers matter |
| **v2** | 3.4+3.5, n=134 (12 slipped) | Depth sensitivity; 10-fold CV | AUC **96.3%** looked great; team flagged overfit | Do not trust headline accuracy without enough slips in CV folds |
| **v3** | Same n=134 | MICE; Platt vs Isotonic; reliability diagrams; GridSearchCV | Better calibration; AUC still ~97.5% and still overfit | Calibrated probabilities matter for planning thresholds; more tricks do not fix small n_slipped |
| **v4/v5** | Transition on path to larger data | ROS → SMOTE; demo confidence caps (~95% with slip history / ~85% without) | SMOTE unsafe at n≈11; becomes reasonable when minority class grows | Synthetic balancing only when the slipped class is large enough |
| **v6** *(current)* | 3.4+3.5 + FPDoR cycle snapshots, **n=319** (**39** slipped) | RF + MICE + GridSearchCV + SMOTE + Isotonic; depth=10 | **AUC 85.4% ± 9.5%** | First honest CV number; FPDoR aggregates now compete with slip history |
| **v7** *(experiment)* | v6 + ~60 rows’ architect spreadsheet fields | Architect Quality Assessment + risk flags | AUC **85.5%** (+0.1%); architect_score ~**4.4%** importance | Signal is real but coverage blocks live use |

Earlier shiny AUCs (96–97%) looked better than 85.4%. They were not trustworthy: too few slipped examples in test folds. **85.4% is the first number the WG should treat as real.**

---

## v1 — First experiments (3.5 only, n=115)

### What

- Compared classifiers: Logistic Regression (L1 / L2 / Ridge / ElasticNet) vs Random Forest.
- Imputation: drop NaN rows vs median vs MICE.
- Balancing: ROS vs SMOTE vs ADASYN (plus `class_weight` alone).
- Outlier check: Isolation Forest.
- Overfit demo: unlimited tree depth vs constrained depth.

### Why

Class imbalance was about 9:1 (104 shipped / 11 slipped). A model that always says “ship” looks ~90% accurate. The team needed real baselines before trusting any score on 3.6.

### Lesson

RF + ROS was the workable v1 choice (~91.9% AUC). SMOTE and ADASYN were weak with only 11 slipped points to interpolate. Unlimited depth memorized the train set and pushed confidence toward ~100% on unseen 3.6 features. Depth must be chosen by CV.

---

## v2 — Add 3.4 data + depth check (n=134)

### What

Combined 3.4 + 3.5 committed features (122 shipped / 12 slipped). Ran depth sensitivity with CV over `max_depth ∈ {3, 5, 7, 10}`.

### Why

More history should help. Shallow depth was preferred by CV when slips were still scarce.

### Lesson

**96.3% AUC was suspicious.** With only 12 slips across many folds, some folds have almost no slipped test cases. Do not trust headline accuracy without honest CV and enough minority examples.

---

## v3 — MICE + calibration + GridSearch (still n=134)

### What

- MICE (IterativeImputer) instead of flat median fill.
- Platt (sigmoid) vs Isotonic calibration; reliability diagrams.
- GridSearchCV over RF hyperparameters.

### Why

Uncalibrated RF pushes probabilities to extremes. Planners need “80%” to mean something close to 80% of similar features shipping.

### Lesson

Calibration improved reliability of the scores. It did **not** fix the small-slipped-class problem. High AUC on n=134 still overstated skill.

---

## v4 / v5 — ROS → SMOTE and display caps

### What

Moved balancing standard from ROS toward SMOTE as slipped-class size grew. Demo added confidence caps:

- Features with real slip history → display max about **95%**
- Features with no slip record (imputed slip_count=0) → max about **85%**, then FPDoR penalty for incomplete readiness

### Why

At ~11 slipped examples, SMOTE invents noisy neighbors. At ~39 (v6), SMOTE has enough support points. Caps stop the UI from showing false certainty when slip history is missing.

### Lesson

Synthetic balancing is safe only when the minority class is large enough. Caps are a product guardrail, not a substitute for better labels.

---

## v6 — Current / final for freeze track (n=319)

### What

Extended training with per-phase FPDoR cycle snapshots (`build_extended_training.py` → `fpdor_cycles_extended.jsonl`). Added ~185 labeled rows (158 shipped / 27 slipped). Many new slips have `slip_count=0`, so the model must use FPDoR and priority signals, not only past slips.

Production stack (as documented in the HTML demo / notebook):

- Random Forest + MICE + GridSearchCV + SMOTE (inside CV) + Isotonic calibration
- Chosen depth **10**, `min_samples_leaf=3`
- Class split: **280 shipped · 39 slipped**
- **AUC-ROC 85.4% ± 9.5%** (10-fold CV)

### Feature importance (v6)

Shifted away from slip history alone. Approximate live ranking from the demo appendix:

| Signal | Share (approx.) |
|--------|-----------------|
| Prior slip history | 21% (was ~48% before extended FPDoR rows) |
| Mandatory FPDoR pass rate | 19% |
| FPDoR pass rate | 9% |
| Release type (pass/fail) | 8% |
| Jira priority | 8% |
| FPDoR items passed | 8% |
| RICE | 7% |
| Other FPDoR / component / phase | remainder |

Plots in Yuval’s repo: `feature_importance.png`, `cv_results_v2.png` (and notebook exports such as `feature_importance_v1_vs_v6.png` when regenerated).

### Confidence caps (still applied at display)

- Real slip history → max ~**95%**
- No slip record → max ~**85%**, minus FPDoR incompleteness penalty

### Lesson

More honest data beats a prettier AUC. v6 is the model to score 3.6 with until the WG agrees otherwise.

### Code / artifacts

| Item | Location |
|------|----------|
| Repo (local) | `/Users/emarion/repos/rhai-release-planner` |
| Repo (GitHub) | https://github.com/yuvalluria/rhai-release-planner |
| Training builder | `build_extended_training.py` |
| Trainer (production path) | `train_classifier_v3.py` → `models_v3.pkl` |
| Trainer (experiment) | `train_classifier_v7.py` → `models_v7.pkl` (3.4 spreadsheet signals) |
| Arjay training merge | `merge_arjay_training.py` → `training_extended_v8.jsonl` (~416 rows) |
| Extended labels | `fpdor_cycles_extended.jsonl` |
| Experiment notebook | `rhoai_release_classifier.ipynb` |
| Demo scores | `index.html` embeds **v6** `ML_SCORES` only (as of 2026-08-25 `main`) |
| Inference | `run_inference_csv.py`, `run_inference_v2.py`, `merge_scores.py` |

---

## v7 script in repo (not production in demo)

`train_classifier_v7.py` on Yuval `main` adds the same 3.4 planning spreadsheet features documented above. It writes `models_v7.pkl`. The HTML demo **does not** use v7 scores yet — still **v6** `ML_SCORES`.

Promote v7 only if training coverage and 3.6 inference inputs improve (architect assessments at freeze).

---

## v8 experiment — Arjay capacity merge (not production)

`merge_arjay_training.py` merges Arjay Hinek’s `Release_Fit_Predictor` CSV with existing JSONL training rows → `training_extended_v8.jsonl` (~416 rows vs v6’s 319).

- Adds size / component-count features from Arjay’s dataset
- Rows without real slip history get **imputed** slip labels (conservative rates by size)
- Intended to enrich training, not to replace v6 until Yuval validates AUC and leakage

The prototype **SIZE** column (S/M/L/XL from component count, 140pt release ceiling) comes from Arjay’s model in `index.html` — separate from ML confidence version.

---

## v7 experiment — Architect spreadsheet signals

### What

Pulled signals from the **3.4 planning spreadsheet**:

- Architect Quality Assessment (Green / Yellow / Yellow-Red / Red)
- Risk flags (Unrefined / Not Started / Missing RFE)

About **60** features were extracted and added to training.

### Result

- AUC **85.5%** (+**0.1%** vs v6)
- `architect_score` importance about **4.4%**
- Only **48 of 319** training rows have architect scores (~**15%** coverage)
- At inference on **3.6**, **none** of the candidates have architect assessments, so the live model cannot use the signal even if training learned it

### Lesson

The signal is real but too sparse to change production scoring. Coverage at train **and** at inference must improve before v7 is worth promoting.

### OPEN QUESTIONS (for Erle / Eder)

1. **Does a similar planning spreadsheet exist for 3.5** with an Architect Quality Assessment tab? Adding 3.5 assessments would push training coverage from ~15% toward ~40%+.
2. **Can Eder provide 3.6 architect assessments** so inference can use real scores? That is when the signal becomes a meaningful improvement, not just an experiment.

Until both are answered with usable data, keep **v6** as the live scorer.

---

## Pointers for agents and humans

| Need | Where |
|------|--------|
| Continuity / WG context | `docs/AI-FIRST-PLANNING-CONTEXT.md` (this repo) |
| Full experiment log | `rhoai_release_classifier.ipynb` in Yuval’s repo |
| Live demo scores | Yuval `index.html` / Downloads `index (11).html` (newer copies may appear) |
| Capacity producer (separate track) | `/Users/emarion/repos/release-capacity-dataset` |

---

## What NOT to change without WG agreement

- **Sealed delivery labels** (committed vs delivered phase / slip definitions)
- **FPDoR item names and grouping** aligned to Org Pulse (checklist contract)
- **v6 as the production scorer** for 3.6 freeze work
- **Label / feature schema** used by `train_classifier_v3.py` and inference scripts (breaking schema silently invalidates scores)
- Promoting **v7** (or any new feature family) to live scoring without coverage numbers the WG accepts

If you need a new signal, document coverage at train and at inference first. Do not swap models because a single AUC tick looks better.
