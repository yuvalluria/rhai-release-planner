# Migrate AI-First planner into Org Pulse Draft Plans

**Status:** Team implementation plan (handoff — no code in this document)  
**Last updated:** 2026-08-26 (reuse existing GitLab runner + archive; one new GitHub tooling repo)  
**Audience:** Arjay Hinek, Yuval Luria, John Graham, Eder Ignatowicz, Org Pulse engineers, Erle Marion  
**Related:** [DRAFT-PLANS-DATA-CONTRACT.md](./DRAFT-PLANS-DATA-CONTRACT.md), [DRAFT-WORK-PLAN-RELEASE-PLANNER-MVP-3.6-EA2.md](./DRAFT-WORK-PLAN-RELEASE-PLANNER-MVP-3.6-EA2.md), [ML-CONFIDENCE-MODEL-JOURNEY.md](./ML-CONFIDENCE-MODEL-JOURNEY.md)

---

## 1. Purpose

Move the working-group planner from Yuval’s standalone HTML demo ([rhai-release-planner](https://github.com/yuvalluria/rhai-release-planner)) into production using the **same split as Quality Gate 1** (GitHub tooling, GitLab runner, GitLab archive), then **display the archived run on Org Pulse Draft Plans**.

QG1 already proves the split. The planner **reuses the two GitLab projects that already exist** and creates **one new GitHub tooling repo**. Do not create `release-planner-runner` or `release-planner-archive`.

| Role | QG1 (pattern) | Planner (reuse / create) |
|------|---------------|--------------------------|
| **Tooling** (logic, tests, config) | [opendatahub-io/release-planner-quality-gate](https://github.com/opendatahub-io/release-planner-quality-gate) | **Create:** GitHub `opendatahub-io/rhai-release-planner` (or agreed name) |
| **Runner** (schedule / on-demand CI) | [release-quality-gate-runner](https://gitlab.com/redhat/rhel-ai/agentic-ci/release-quality-gate-runner) | **Reuse:** [release-planning](https://gitlab.com/redhat/rhel-ai/agentic-ci/release-planning) — gut old jobs; keep as thin runner |
| **Archive** (durable run data) | [release-quality-gate-archive](https://gitlab.com/redhat/rhel-ai/agentic-ci/release-quality-gate-archive) | **Reuse:** [release-planning-data](https://gitlab.com/redhat/rhel-ai/agentic-ci/release-planning-data) — move old trees to `legacy/`; new `latest/v{version}/` layout |

The HTML demo cannot go to production as a CSV-upload page. Production compute must be a Python CLI in a GitHub tooling repo, invoked only by a thin GitLab runner, with each run committed to a data-only archive. Org Pulse Draft Plans **reads that archive**. It does not run the packer, the ML model, or Yuval’s browser scheduler.

This document is the handoff plan for Arjay, Yuval, and John. It names owners, repo layout, CI jobs, archive files, Org Pulse fetch changes, phases, and acceptance tests. **Do not implement from this chat** — implement from this plan.

---

## 2. Executive summary

**Locked production path (2026-08-26):** Same split as QG1 (logic on GitHub, thin GitLab runner, data-only GitLab archive). **Reuse** [release-planning](https://gitlab.com/redhat/rhel-ai/agentic-ci/release-planning) and [release-planning-data](https://gitlab.com/redhat/rhel-ai/agentic-ci/release-planning-data). **Create** one GitHub tooling repo. Gut and archive the old Claude `/release-plan` + `auto_scheduler.py` path — do not run it beside the new CLI. Do not put planner logic in the GitLab runner. Do not have Org Pulse call Jira or sklearn on the request path for packing. Stop using `{product}/latest/release-plan.json` as the Draft Plans spine once `latest/v{version}/candidate-plan.json` is live.

| Layer | Where it lives in production | Owner |
|-------|------------------------------|-------|
| **Tooling** (packer, SIZE, ML inference, artifact writer) | **New** GitHub repo under `opendatahub-io` (seeded from Yuval HTML + John’s packer + Arjay SIZE) | John (packer), Yuval (ML), Arjay (SIZE + repo shape) |
| **Runner** (clone tooling, run CLI, push archive) | **Reuse** [release-planning](https://gitlab.com/redhat/rhel-ai/agentic-ci/release-planning) | John (jobs); Eder / Fege (CI pattern) |
| **Archive** (dated runs + `latest/` pointer) | **Reuse** [release-planning-data](https://gitlab.com/redhat/rhel-ai/agentic-ci/release-planning-data) (project `81798612`) | Existing runner bot is the only writer |
| **Display + red-pen + freeze** | Org Pulse Draft Plans | Org Pulse |
| **Live FPDoR / rubric / slide tray** | Org Pulse planning + execution APIs (join by key) | Org Pulse |
| **Approve to Jira (TV + FV)** | Org Pulse write API (not the runner) | John + Org Pulse |
| **QG1 labels** (`rp-qg1-pass` / `fail`) | Existing QG1 three-repo system; packer **reads** labels only | QG1 owners |
| **Model training** | Tooling repo notebooks / scripts; **never** on the runner inference path | Yuval |

**Do not** build a second “Candidate Plan” page. **Do not** port `index.html` (~4k lines) as a new app. **Do not** leave packer or ML inside `release-planning` after the cut. **Reuse** Draft Plans + Features List readiness components.

**What the HTML demo becomes:** UX and scoring **reference**. The browser scheduler, CSV upload, and pasted `ML_SCORES` blob are retired from the freeze path.

**What the old GitLab pipeline becomes:** Tagged snapshot under `legacy/` (code) and `legacy/` (data). Not a living job on `main`.

---

## 3. What we are migrating (and what we are not)

### 3.1 From Yuval’s `rhai-release-planner`

| Capability in HTML demo (`main` Aug 25) | Migrate to Draft Plans? | Notes |
|----------------------------------------|-------------------------|--------|
| EA1 / EA2 / GA / No placement display | **Yes** | Source = packer `basePlacement`, not re-run placement in the browser |
| Priority Score (RICE 30% + Big Rock 30% + TV 25% + Jira 15%) | **Partial** | Org Pulse already has `effectivePriorityScore`; align formula in docs, do not fork scoring in Vue |
| Readiness gate before scheduler | **Yes** | Use Org Pulse FPDoR + planning `confidence`; same gates as Features List |
| Filters (event, component, priority, Big Rock, failed FPDoR) | **Yes** | Draft Plans has most filters; add failed-FPDoR filter |
| FPDoR fraction + weighted `w:` score | **Partial** | Show Org Pulse FPDoR; optional `w:` using aligned `FPDOR_WEIGHTS` ([PR #1](https://github.com/yuvalluria/rhai-release-planner/pull/1) on `main`) |
| ML confidence % (`ML_SCORES` **v6**) | **Yes** | Still v6 in demo; publish `mlConfidencePct` from inference — not v7/v8 until promoted |
| TYPE column (DP/TP/GA + title-prefix fallback) | **Yes** | Org Pulse already has Release Type on features; reuse, do not duplicate heuristics |
| SIZE column + capacity load panel (Arjay 140pt) | **Phase F** | S/M/L/XL from component count in demo; coordinate with Arjay + John — **not** a substitute for packer `capacityWarning` |
| `ROADMAP_OUTCOMES` (259+ baked Big Rock labels) | **No — replace** | Use Org Pulse Big Rocks + Outcome; do not ship static `roadmap_outcomes.json` in Pulse |
| Big Rocks panel (gaps, “not in plan”, 3.5 match badges) | **Phase F** | High value for freeze review; wire to live plan rows + Org Pulse Big Rocks |
| 40/40/20 capacity mix panel | **Phase F** | Planning insight; not a packing gate |
| Org Pulse KPI snapshot row (TV/FV aligned) | **Phase F** | Read live from PM Hub / TV/FV Delta — do not paste static Aug 25 numbers |
| Release horizon timeline (3.6–3.8) | **Phase F** | Link to release calendar or shared milestone data |
| **RHAI Roadmap timeline** (Big Rock swimlanes × EA1/EA2/GA) | **Phase F** | See §5B — dual view in Draft Plans; **not** standalone HTML |
| Bottleneck teams + Docs 50% warning | **Phase F** | Useful triage; derive from plan + Org Pulse team attribution |
| Architecture / Data Appendix tabs | **No** | Keep in repo as reference; link from About or WG docs |
| CSV upload / `parseCSV` | **No** | Replace with artifact load + live APIs |
| In-browser placement algorithm (Phase 1 committed / Phase 2 Big Rocks) | **No** | Packer owns placement; Pulse displays + red-pen overrides |

### 3.2 From Org Pulse Features List (reuse, do not rebuild)

| Asset | Path |
|-------|------|
| Feature slide tray | `modules/releases/client/plan/components/FeatureReadinessDrawer.vue` |
| FPDoR popover | `FPDoRPopover.vue`, `FPDoRChecklistSections.vue` |
| Drawer adapter | `utils/feature-readiness-drawer-model.js` |
| FPDoR evaluation | `server/planning/fpdor.js` |
| Planning readiness API | `GET /api/modules/releases/planning/feature-readiness` |
| Execution detail + `aiReview` | `GET /api/modules/releases/execution/features/:key` |

### 3.3 Stays external permanently

- Random Forest training, cross-validation, calibration (`train_classifier_v3.py`, notebook)
- QG1 label writer (existing agentic-ci quality-gate three-repo system)
- Heavy capacity computation (`release-capacity-dataset` CLI) until it has its own archive
- Old Claude `/release-plan` markdown + in-repo `auto_scheduler.py` — **archive on a tag / `legacy/` branch**, do not keep as a living pipeline on `main`

Org Pulse **consumes** archive JSON. It does not become the compute engine (see AGENTS.md hard constraint #3). The **GitLab runner** also does not become the compute engine — it only clones and invokes the GitHub CLI.

---

## 4. Current state (as of Aug 2026)

### 4.1 Org Pulse Draft Plans — already shipped

- **View:** `DraftPlansView.vue` at `#/releases/plan?tab=draft-plans`
- **Server:** `modules/releases/server/draft-plans/` (routes, fetch, normalize, ACL, plan-admins)
- **Capabilities:** red-pen move/descope, local approve checkbox, per-event freeze, audit panel, viewer ACL, demo fixture `draft-3.6-demo.json`
- **PRs:** [#1240](https://github.com/red-hat-data-services/rhai-org-pulse/pull/1240) red-pen, [#1249](https://github.com/red-hat-data-services/rhai-org-pulse/pull/1249) MVP, [#1251](https://github.com/red-hat-data-services/rhai-org-pulse/pull/1251) audit, [#1258](https://github.com/red-hat-data-services/rhai-org-pulse/pull/1258) ACL

### 4.2 Org Pulse Draft Plans — gaps for planner MVP

| Gap | Detail |
|-----|--------|
| **Load packer artifact** | `fetch.js` already reads `release-planning-data` (`81798612`) but still uses `{product}/latest/release-plan.json`, not `latest/v{version}/candidate-plan.json` |
| **Normalize passthrough** | `normalize.js` drops `readiness`, `capacityWarning`, `priorityScore`, `engComponents`, `humanSignoff`, `qg1Pass` from artifact rows |
| **Approve to Jira** | Row “approve” is local overlay only; no TV/FV write |
| **Confidence column** | No ML % from Yuval v6 |
| **Readiness drawer** | `DraftPlanDrawer.vue` is placement-only; no FPDoR checklist, no `aiReview.scores` |
| **RHELAI** | Fetch `KNOWN_PRODUCTS` is RHOAI + RHAII only; MVP scope includes RHELAI on a **combined** file |
| **Regenerate** | No “reload latest packer run” wired to the QG1-style archive (refresh exists but points at the wrong project/files) |
| **Three-repo split** | GitLab runner + archive **exist**; they still mix old Claude/scheduler output. GitHub tooling repo **does not exist yet**. |

### 4.3 Yuval repo — reference implementation (check `main` regularly)

| Item | Status on `main` (2026-08-25) |
|------|-------------------------------|
| `index.html` | ~4k lines; scheduler + dashboards + embedded data |
| Live ML scores in UI | **v6** (`ML_SCORES`, AUC ~85.4%, n=319) — comment in file still says v6 |
| `train_classifier_v7.py` | 3.4 spreadsheet signals (architect score, process/schedule/missing-RFE flags) — experiment, not wired to demo scores |
| `merge_arjay_training.py` + `training_extended_v8.jsonl` | ~416 rows merging Arjay `Release_Fit_Predictor` CSV with FPDoR training — v8 not promoted |
| `roadmap_outcomes.json` | 1,147 keys with `bigRock` + `roadmapConfidence` from `RHAI-Roadmap.html` |
| `extract_roadmap_outcomes.py` | Regenerates roadmap JSON — local path to HTML |
| FPDoR weights | Org Pulse names on `main` (Erle PR #1 merged) |
| Recent commits | Arjay SIZE + capacity panel; 40/40/20 mix; horizon 3.7/3.8; Org Pulse KPI strip; collapsible BR “not in plan”; TYPE plain-text fix |

**Inference path (unchanged):** `run_inference_csv.py` / `run_inference_v2.py` → JSON → `merge_scores.py` → paste into `ML_SCORES` or publish sidecar for Org Pulse.

### 4.4 Prototype vs Org Pulse — what changed our recommendations

1. **The demo grew faster than Draft Plans load path.** Do not wait to port every panel before Phase 1 (CLI fixture) and Phase C (readiness drawer).

2. **Two capacity concepts — keep separate:**
   - **John / packer:** per-component ceilings, `capacityWarning`, `placeReason` on each row.
   - **Arjay / SIZE:** release-level point load (140pt ceiling, S/M/L/XL from component count). Useful executive view; add in Phase F after archive load works.

3. **Big Rocks:** Demo now uses `ROADMAP_OUTCOMES` when CSV Outcome keywords miss. Org Pulse should use **PM Hub Big Rocks + feature Outcome** — not import Yuval’s JSON into production storage.

4. **ML:** Still **ship v6** for freeze. Inference belongs in the tooling CLI on the runner, not pasted `ML_SCORES`. v7 and v8 stay off the runner until Yuval + WG agree.

5. **Static KPIs in the demo** (e.g. TV/FV aligned Aug 25) must become **live queries** in Org Pulse or they will go stale immediately.

6. **Production hosting:** Copy the QG1 **split**. Reuse GitLab `release-planning` (thin runner) and `release-planning-data` (archive). Create one GitHub tooling repo. Gut Claude/`auto_scheduler` off `main` — do not grow that GitLab repo into the compute engine.

---

## 5. Production architecture — copy the QG1 three-repo pattern

QG1 rule, quoted from the runner README: **the runner owns only plumbing; all discovery, checks, and scoring live in the tooling repo.** Changing thresholds in the runner is impossible by design (the strings do not exist there). The planner must follow the same rule.

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ 1. TOOLING  GitHub  opendatahub-io/rhai-release-planner (**create**)     │
│    Python CLI (uv): packer + SIZE + ML v6 inference + artifact writer    │
│    Tests, config, models_v6.pkl. No GitLab CI. No Vue. No CSV upload.    │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │ git clone --depth 1  (runner only)
                                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ 2. RUNNER   GitLab  redhat/rhel-ai/agentic-ci/release-planning (**reuse**)|
│    Thin after gut: setup, clone tooling, run CLI, copy artifacts, push   │
│    Jobs: planner-validate (dry-run) · planner-batch (schedule) ·         │
│          planner-version (manual, VERSION=3.6)                           │
│    Old generate-plan / auto_scheduler / Claude: tag + remove from main   │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │ git commit + push (existing GITLAB_PUSH_TOKEN)
                                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ 3. ARCHIVE  GitLab  redhat/rhel-ai/agentic-ci/release-planning-data       │
│    (**reuse**, project 81798612). Data only. Bot push on protected main. │
│    New: runs/<UTC-date>/v{version}/batch/  and  latest/v{version}/       │
│    Old RHOAI/ RHAII/ trees: move under legacy/ (do not delete history)   │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │ GitLab Files API (DRAFT_PLANS_GITLAB_TOKEN)
                                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ 4. DISPLAY  Org Pulse Draft Plans                                        │
│    fetch.js pulls latest/v{version}/candidate-plan.json + confidence.json│
│    writes PVC: releases/draft-plans/drafts/combined/{version}.json       │
│    join live FPDoR / aiReview by key → table + roadmap + slide tray      │
│    Plan Admin: red-pen overlay, freeze, Approve to Jira                  │
└──────────────────────────────────────────────────────────────────────────┘
```

**QG1 stays a separate three-repo system.** The planner runner does not clone `release-planner-quality-gate`. The packer reads `rp-qg1-pass` / `rp-qg1-fail` from Jira (or from feature-traffic labels already on the feature). It never writes those labels.

**Do not create** `release-planner-runner` or `release-planner-archive`. The GitLab pair already exists. Empty `release-planning` of compute; keep it as plumbing. Move old `release-planning-data` product trees to `legacy/` so they are not confused with `latest/v{version}/candidate-plan.json`. Org Pulse **keeps** `projectId: '81798612'` and **changes file paths**.

### 5.0 Gut `release-planning` — do not leave the old pipeline on `main`

Today [release-planning](https://gitlab.com/redhat/rhel-ai/agentic-ci/release-planning) mixes fetch scripts, `auto_scheduler.py`, Claude `/release-plan`, `forecast.py`, and `ci-scripts/push-results.py`. That is the opposite of QG1. After the cut, **logic lives on GitHub**; this GitLab repo is clone / run / push only.

Consequences of leaving both paths on `main`:

- Someone will trigger `generate-plan` by habit and overwrite or confuse Draft Plans.
- Packer changes would still land in GitLab MRs next to CI tokens.
- Yuval’s HTML and ML scripts on a personal GitHub with laptop pickle paths still cannot run here.

**Archive the old functionality (do not delete git history):**

1. Tag current `release-planning` `main` as e.g. `legacy-claude-release-plan-2026-08`.
2. Optional `legacy/` branch with the old `.gitlab-ci.yml` stages (`fetch-data`, `generate-plan`, `generate-health`, `publish-results`) for archaeology.
3. On `main`, replace CI with the thin runner jobs in §5.3. Remove or stop scheduling Claude / `auto_scheduler.py`.
4. In [release-planning-data](https://gitlab.com/redhat/rhel-ai/agentic-ci/release-planning-data), move `RHOAI/` and `RHAII/` (including `latest/release-plan.json`) under `legacy/` in one commit. Git history keeps the files.
5. GitLabForm already allows the `release-planning` bot to push `release-planning-data` `main` — **keep that exception**; do not add a second archive project.

QG1 already solved the split: GitHub owns the CLI; GitLab runner is a wrapper; archive is a dated git history Org Pulse can consume. We copy the **split**, not the **project names**.

### 5.1 Repo map — QG1 vs planner (copy this table)

| Concern | QG1 (copy from) | Planner (build this) |
|---------|-----------------|----------------------|
| Tooling host | GitHub `opendatahub-io/release-planner-quality-gate` | **Create** GitHub `opendatahub-io/rhai-release-planner` (org-owned; do not leave production on `yuvalluria/rhai-release-planner`) |
| Runner host | GitLab `agentic-ci/release-quality-gate-runner` | **Reuse** [agentic-ci/release-planning](https://gitlab.com/redhat/rhel-ai/agentic-ci/release-planning) |
| Archive host | GitLab `agentic-ci/release-quality-gate-archive` | **Reuse** [agentic-ci/release-planning-data](https://gitlab.com/redhat/rhel-ai/agentic-ci/release-planning-data) (`81798612`) |
| CLI entry | `uv run python scripts/quality_gate.py` | `uv run python scripts/release_planner.py` (name can vary; one entry) |
| Local commands | `make run` / `make run-dry` / `make run-issue` | `make run` / `make run-dry` / `make run VERSION=3.6` |
| Runner clone | `GATE_REPO` + `GATE_DIR=/tmp/gate` | `PLANNER_REPO` + `PLANNER_DIR=/tmp/planner` |
| Report file | `artifacts/run-data.json` | `artifacts/candidate-plan.json` + `artifacts/confidence.json` + `artifacts/run-manifest.json` |
| Archive layout | `runs/<UTC-date>/<batch\|ISSUE>/run-data.json` | Same date layout **plus** `latest/` pointer (Org Pulse needs a stable path) |
| Jira writes from CI | Yes — labels + comments + optional RICE | **No.** Planner is read-only toward Jira. Approve to Jira is Org Pulse. |
| Claude / Vertex | Required (`claude -p /rice-score`) | **Not required** for v6 inference (sklearn pickle). Do not copy `setup-claude-ci.sh` unless a later step truly needs Claude. |
| Runner jobs | `qg1-validate` (dry-run, no archive) · `qg1-batch` · `qg1-single` | `planner-validate` · `planner-batch` · `planner-version` |
| Serialize overlapping runs | `resource_group: qg1` | `resource_group: planner` |
| Archive push token | `RESULTS_PUSH_TOKEN` on QG1 runner | **Reuse** existing `GITLAB_PUSH_TOKEN` on `release-planning` (already writes `release-planning-data`). Same stash-and-unset hygiene. |
| GitLabForm exception | `release-quality-gate-archive` bot on protected `main` | **Already exists** for `release-planning-data` (`project_81798612_bot_…` from the runner). Keep it. Do not add a second archive exception. |
| Push token hygiene | Stash token to `/root/.tokens/results` and `unset RESULTS_PUSH_TOKEN` before the CLI runs | Same, even without Claude — do not leak the write token into the packer process |
| Archive push failure | Best-effort: CI artifact still keeps `run-data.json`; job should not fail the whole run if Jira writes already happened | Best-effort: planner did not write Jira, but still keep CI artifacts; warn, do not hide a bad plan |
| Pre-merge tests | Runner `tox` on MRs; tooling `pytest` on GitHub | Same split |
| Protected variables | Inherited from `agentic-ci` group (`JIRA_API_TOKEN`, `JIRA_EMAIL`) | Same, plus a **read** token for `feature-traffic-data` (and later capacity-dataset archive if that is how capacity is published) |

Recommended GitHub name `opendatahub-io/rhai-release-planner` matches QG1’s org. If that name is taken, use `opendatahub-io/release-planner`. Confirm with Eder before creating the repo.

### 5.2 Tooling repo — what to extract, file by file

**Rule:** If a string or formula affects placement, SIZE, or confidence, it lives here. If it is “clone / run / push”, it does not.

#### 5.2.1 Suggested tree

```text
rhai-release-planner/                  # GitHub tooling (new org repo)
  pyproject.toml                       # uv, python >=3.11
  uv.lock
  Makefile                             # install, test, run, run-dry
  README.md                            # local run; points to runner + archive
  CLAUDE.md                            # agent conventions (optional)
  config/
    pipeline-settings.yaml             # version, products, gates, SIZE table
    release-calendar.json              # same role as QG1 calendar
    fpDor-weights.yaml                 # aligned Org Pulse names (PR #1)
  models/
    models_v6.pkl                      # production RF; committed or Git LFS
    MODEL.md                           # n=319, AUC, feature list, caps
  scripts/
    release_planner.py                 # orchestrator (discover → pack → score → write)
    packer.py                          # John’s improved packer (no primary component)
    size_model.py                      # Arjay 140pt / S-M-L-XL
    ml_inference.py                    # v6 scorer; no training
    artifact.py                        # candidate-plan.json + confidence.json writer
    jira_utils.py                      # read-only Jira (or skip if feature-traffic is enough)
    report.py                          # run-manifest.json
  tests/
    test_packer.py
    test_size_model.py
    test_ml_inference.py
    test_artifact_schema.py            # JSON Schema vs DRAFT-PLANS-DATA-CONTRACT §4
    fixtures/                          # small candidate lists, no production secrets
  artifacts/                           # gitignored; local CLI output
```

Yuval’s current `index.html` stays in `yuvalluria/rhai-release-planner` as a prototype. Do not copy it into the org tooling repo as a production page. Port **algorithms**, not the DOM.

#### 5.2.2 Orchestrator steps (`release_planner.py`)

Mirror `quality_gate.py`: one invocation does the whole job. Suggested flags:

```text
uv run python scripts/release_planner.py
  --version 3.6
  --dry-run                  # write artifacts locally; runner skips archive push
  --input-dir /path          # pre-fetched feature-traffic + capacity (CI)
  --jira                     # optional live Jira refresh (local/debug only)
```

Pipeline inside the CLI (deterministic; no Claude):

1. **Load universe** — features for RHOAI + RHAII + RHELAI, open statuses, from `--input-dir` (feature-traffic `latest/index.json` + per-feature files, plus any supplemental fields). Do not JQL-discover in the runner. If a field is missing from feature-traffic, add it there or fetch in the **tooling** CLI with Jira read, not in runner shell scripts.
2. **Join QG1** — `qg1Pass` / `qg1Fail` / `qg1AutoRice` from labels on the feature record. Packer **reads** only.
3. **Join capacity** — `capacity-dataset.json` (Erle’s producer) or component velocity already used by John’s packer. Soft ceilings only.
4. **SIZE** — Arjay model: component-count → S/M/L/XL and 3/5/8/13 points; optional 140pt release load. Separate from packer `capacityWarning`.
5. **Pack** — improved packer: no primary component; full `engComponents[]`; `basePlacement` ∈ {EA1, EA2, GA, Below cut}; every in-scope feature in exactly one bucket; `placeReason` always set; `capacityWarning` boolean + reason. **Do not** reimplement Yuval’s browser Phase 1/2 JS. John’s packer is the production placement engine; Yuval’s HTML is the reference for *display* columns and gates, not the CI scheduler.
6. **ML inference (v6)** — `ml_inference.py` loads `models/models_v6.pkl`, scores each candidate, writes `mlConfidencePct` (and optional band). Fix today’s hard-coded `/Users/yluria/...` paths. Training scripts stay in the repo but are **not** invoked by `release_planner.py`.
7. **Write artifacts** — see §5.4. Validate against JSON Schema before exit 0.

Exit codes: `0` valid artifacts; `2` schema/contract failure (do not archive); `1` unexpected error.

#### 5.2.3 What moves out of `index.html` vs what dies

| HTML / demo piece | Production |
|-------------------|------------|
| In-browser placement (`run()`, `_place`, Phase 1 committed / Phase 2 Big Rocks) | **Die.** John’s `packer.py` owns placement. |
| CSV `parseCSV` / upload | **Die.** CLI reads feature-traffic / JSON. |
| Embedded `ML_SCORES` | **Die.** `models_v6.pkl` + `confidence.json`. |
| `ROADMAP_OUTCOMES` / `extract_roadmap_outcomes.py` | **Die as source of truth.** Big Rock from Org Pulse / feature-traffic Outcome. |
| `FEATURE_TEAM_LOOKUP` baked JSON | **Die.** Team from capacity-dataset + Jira Team field. |
| `COMPONENT_CAPACITY` in HTML | **Replace** with packer `ceilingsByComponent` from velocity/capacity dataset. |
| SIZE / 140pt JS | **Port** to `size_model.py`. |
| `FPDOR_WEIGHTS` / `w:` | **Port** optional weighted score for display; live FPDoR checklist still from Org Pulse. |
| Filters / table / roadmap UX | **Do not port to tooling.** Org Pulse Draft Plans (§5A, §5B, §7). |
| `train_classifier_v3.py`, v7, v8 JSONL | Stay in tooling as research; CI inference = v6 until WG promotes. |

#### 5.2.4 Inputs the runner must clone or pass in

| Input | Source | How the runner provides it |
|-------|--------|----------------------------|
| Feature universe | `redhat/rhel-ai/agentic-ci/feature-traffic-data` (`latest/`) | `git clone --depth 1` into `$PLANNER_DIR/data/feature-traffic` (same idea as `release-planning` `fetch-data`) |
| Rubric scores (optional for packer; required for training) | `strat-pipeline-data` or execution index | Tooling reads if present; Org Pulse drawer still joins live `aiReview` |
| Capacity dataset | `release-capacity-dataset` output JSON | Until that producer has its own archive, commit a versioned snapshot under `data/capacity/` in tooling **or** clone a future `capacity-dataset-archive`. Do not bake numbers in the runner. |
| Release calendar | `config/release-calendar.json` in tooling | Already in the clone |
| ML model | `models/models_v6.pkl` in tooling | Already in the clone |

Jira credentials on the runner are **optional** for the happy path if feature-traffic is complete. Keep them available for a `--jira` backfill job, matching QG1 variable names (`JIRA_SERVER`, `JIRA_USER`/`JIRA_EMAIL`, `JIRA_TOKEN`/`JIRA_API_TOKEN`).

#### 5.2.5 Artifact schema the CLI must emit

`artifacts/candidate-plan.json` **is** the Draft Plans contract ([DRAFT-PLANS-DATA-CONTRACT.md](./DRAFT-PLANS-DATA-CONTRACT.md) §4), plus planner metadata:

```json
{
  "generatedAt": "2026-08-26T14:00:00.000Z",
  "generated_at": "2026-08-26T14:00:00.000Z",
  "version": "3.6",
  "baselineAsOf": "2026-08-26",
  "createdBy": "release-planner-cli",
  "packerId": "improved-packer",
  "packerVersion": "git-sha",
  "toolingCommit": "abc123",
  "dry_run": false,
  "productFamilyScope": ["RHOAI", "RHAII", "RHELAI"],
  "scoring": {
    "formula": "org-pulse-priority-v1",
    "mlModel": "v6",
    "sizeModel": "arjay-140pt-v1"
  },
  "summary": {
    "candidateCount": 0,
    "scheduled": 0,
    "belowCut": 0,
    "byEvent": { "EA1": 0, "EA2": 0, "GA": 0, "Below cut": 0 }
  },
  "ceilingsByComponent": {},
  "candidates": []
}
```

Include both `generatedAt` (Draft Plans / JS) and `generated_at` (QG1-style Python archive scripts) **or** pick one and teach `push_results.py` + Org Pulse the same key. Recommendation: **emit both**, same ISO-8601 UTC value.

`artifacts/confidence.json`:

```json
{
  "generated_at": "2026-08-26T14:00:00.000Z",
  "version": "3.6",
  "model": "v6",
  "scores": {
    "RHAISTRAT-1281": { "mlConfidencePct": 81.2, "source": "jsonl", "mlConfidenceBand": "high" }
  }
}
```

Also embed `mlConfidencePct` on each `candidates[]` row so Org Pulse can render if the sidecar fetch fails.

`artifacts/run-manifest.json` (archive index, analogous to QG1 `run-data.json` summary):

```json
{
  "generated_at": "2026-08-26T14:00:00.000Z",
  "version": "3.6",
  "dry_run": false,
  "issue_key": null,
  "tooling_commit": "abc123",
  "summary": {
    "candidateCount": 180,
    "scheduled": 140,
    "belowCut": 40,
    "scored": 165,
    "unscored": 15
  },
  "files": ["candidate-plan.json", "confidence.json"]
}
```

`push_results.py` should validate `run-manifest.json` the way QG1 validates `run-data.json` (`summary` object + parseable timestamp).

#### 5.2.6 Tests the tooling repo must have before the runner is useful

- Schema test: fixture `candidates[]` round-trips through Org Pulse `normalize.js` field list (copy the required keys into a JSON Schema in tooling).
- Packer: no primary component; missing team/component → `placeReason` / `readiness.hardReasons`, never dropped.
- RHOAI + RHAII + RHELAI all present in one file.
- ML: 10 golden keys match known v6 percentages (spot-check, not full training).
- `--dry-run` writes files and does not need GitLab.
- No `process.env` secrets in GitHub Actions beyond optional Jira for integration tests; unit tests use fixtures.

### 5.3 Runner repo — thin plumbing only

Copy [release-quality-gate-runner](https://gitlab.com/redhat/rhel-ai/agentic-ci/release-quality-gate-runner) **job shape** into the existing [release-planning](https://gitlab.com/redhat/rhel-ai/agentic-ci/release-planning) repo. **Do not** copy Claude/Vertex setup unless inference needs it (v6 does not). **Do not** create a new GitLab project.

#### 5.3.1 Suggested tree (after gut; this **is** `release-planning`)

```text
release-planning/                    # existing GitLab runner repo
  .gitlab-ci.yml                     # replace old stages; see jobs below
  scripts/
    setup-ci.sh                      # ubi-minimal: git, python, uv — no Claude
    clone-data-repo.sh               # clone release-planning-data
    clone-inputs.sh                  # clone feature-traffic-data (+ capacity when ready)
    run-planner.sh                   # re-exec as unprivileged user; uv sync; run CLI
    push_results.py                  # generalize current ci-scripts/push-results.py
    test_push_results.py
  tox.ini / pytest.ini
  README.md                          # “logic lives in the GitHub repo”
```

Keep `ci-scripts/` only if you rewrite them in place. Old `scripts/auto_scheduler.py`, `ci-scripts/run-claude.sh`, and `/release-plan` invocation **leave `main`** (tag / `legacy/` branch).

#### 5.3.2 `.gitlab-ci.yml` jobs (mirror QG1)

| Job | When | What |
|-----|------|------|
| `python-tests` | MR + default branch | `tox` on `push_results.py` only |
| `planner-validate` | **manual** only; never on MR | `run-planner.sh --dry-run --version "$VERSION"`; copy artifacts to CI; **no** archive push. Proves uv + inputs. |
| `planner-batch` | **schedule** + manual | Full run for default version (config in tooling, e.g. next freeze cycle). Archive push. |
| `planner-version` | manual, `VERSION=3.6` | Same as batch but explicit cycle. Archive path includes version (see §5.4). |

Shared:

- Tags: `aipcc-small-x86_64` (same as QG1).
- Image: `registry.access.redhat.com/ubi9/ubi-minimal:latest`.
- `resource_group: planner` so two batch jobs cannot push the archive at once.
- `timeout`: start at 1h; raise if feature-traffic clone + pack + inference needs more.
- CI artifacts: `candidate-plan.json`, `confidence.json`, `run-manifest.json`, expire 30 days (even when archive push is skipped).
- Rules: never run gate jobs on `merge_request_event` (protected tokens). Same as QG1.

Variables:

```yaml
variables:
  PLANNER_REPO: "https://github.com/opendatahub-io/rhai-release-planner.git"
  PLANNER_DIR: "/tmp/planner"
  RESULTS_REPO: "redhat/rhel-ai/agentic-ci/release-planning-data"
  FEATURE_TRAFFIC_DATA_REPO: "redhat/rhel-ai/agentic-ci/feature-traffic-data"
  VERSION: "3.6"   # overridable on planner-version
```

`run-planner.sh` (pattern from `run-gate.sh`):

1. If root, `exec runuser -u planner-ci -- bash "$0" "$@"`.
2. Preflight: required env (feature-traffic token, not RESULTS_PUSH_TOKEN).
3. `cd $PLANNER_DIR && uv sync --frozen || uv sync`.
4. `uv run python scripts/release_planner.py --version "$VERSION" --input-dir ...` plus `"$@"`.
5. `ls -l artifacts/candidate-plan.json`.

Publish block (pattern from QG1 `*publish`):

1. Copy `$PLANNER_DIR/artifacts/*.json` to `$CI_PROJECT_DIR`.
2. If `/root/.tokens/results` is non-empty, run `push_results.py`; on failure print `WARNING` and **do not** fail the job unless `--strict-archive` is set. First production weeks: warn-only, matching QG1.

#### 5.3.3 `push_results.py` differences from QG1

QG1 writes one file derived from `generated_at` + `issue_key or "batch"`.

Planner should:

1. Validate `run-manifest.json` (timestamp + `summary` + `version`).
2. Copy **all** files in `files[]` to:
   - `runs/<UTC-date>/v<version>/batch/` (audit trail; version in path so 3.5 and 3.6 same day do not clobber)
   - `latest/v<version>/` (Org Pulse stable pointer)
3. Optionally also copy `latest/candidate-plan.json` if only one active freeze version exists — **prefer versioned latest** so Draft Plans can list cycles.
4. Commit message: `Planner run 2026-08-26 v3.6 batch: scheduled=140 belowCut=40 scored=165`.
5. Plain `git push` (QG1: no rebase; runner is the only writer; `resource_group` serializes).
6. `--dry-run` on the publisher = local commit, no push (for runner unit tests).

Same-UTC-day re-run **overwrites** that day’s folder (latest verdict wins), same as QG1. `latest/v3.6/` always matches the most recent successful **non-dry-run** batch for that version.

### 5.4 Archive repo — reuse `release-planning-data`

Do **not** create a new archive project. Use [release-planning-data](https://gitlab.com/redhat/rhel-ai/agentic-ci/release-planning-data) (GitLab project `81798612`).

- **No application CI** (already true). GitLabForm exception **already exists** (`only_allow_merge_if_pipeline_succeeds: false`; protected `main` allows the `release-planning` bot). See `infrastructure/data/gitlab_security_exceptions.yml`.
- README: add that new runs use `latest/v{version}/`; old product trees live under `legacy/`.
- **Cutover commit:** move `RHOAI/` and `RHAII/` to `legacy/RHOAI/` and `legacy/RHAII/` so Org Pulse cannot accidentally keep reading `{product}/latest/release-plan.json` after fetch.js is updated.
- New layout:

```text
legacy/                                 # frozen Claude / auto_scheduler output
  RHOAI/latest/release-plan.json
  RHAII/latest/release-plan.json
  …
runs/
  2026-08-26/
    v3.6/
      batch/
        candidate-plan.json
        confidence.json
        run-manifest.json
latest/
  v3.6/
    candidate-plan.json
    confidence.json
    run-manifest.json
```

No pruning (QG1 policy). Plans are larger than QG1 `run-data.json`; still fine in git for hundreds of features. If files grow past a few MB, switch `candidates[]` to a compact JSON and keep git; do not invent object storage in v1.

**Org Pulse reads:** `latest/v{version}/candidate-plan.json` and `latest/v{version}/confidence.json` via GitLab repository files API:

```text
GET https://gitlab.com/api/v4/projects/81798612/repository/files/
    latest%2Fv3.6%2Fcandidate-plan.json/raw?ref=main
Authorization: Bearer $DRAFT_PLANS_GITLAB_TOKEN
```

The token needs `read_api` / `read_repository` on the archive. It must **not** be the write token.

### 5.5 Org Pulse Draft Plans — consume the archive (not the HTML, not PVC push from CI)

Today (`modules/releases/server/draft-plans/fetch.js`):

- `DEFAULT_CONFIG.projectId = '81798612'` (`release-planning-data`)
- `KNOWN_PRODUCTS = ['RHOAI', 'RHAII']` — **missing RHELAI**
- `FILES_TO_FETCH = ['release-plan.json', 'release-health.json']`
- Path: `{product}/latest/{file}`
- Writes: `releases/draft-plans/{product}/{file}`
- Token: `DRAFT_PLANS_GITLAB_TOKEN` (already in `modules/releases/module.json`)
- Refresh: existing `doFetch()` when config `enabled: true`

**Change to (implementation notes for Org Pulse, not for this chat):**

| Item | New behavior |
|------|----------------|
| Config | **Keep** `projectId: '81798612'`; keep `gitlabBaseUrl`, `branch: main`. Change **paths**, not the project. |
| Files | `latest/v{version}/candidate-plan.json`, `latest/v{version}/confidence.json` (not `{product}/latest/release-plan.json`) |
| Version list | `GET /repository/tree?path=latest` to list `v3.6`, `v3.5`, … **or** a committed `latest/index.json` listing versions (simpler for Pulse; have `push_results.py` maintain it) |
| Storage | `releases/draft-plans/drafts/combined/{version}.json` (already the Draft Plans editor path) |
| Confidence | `releases/draft-plans/confidence/{version}.json` |
| Normalize | Extend `normalize.js` + `draft-plan-model.js` to pass through `placeReason`, `capacityWarning`, `engComponents`, `qg1Pass`, `mlConfidencePct`, `featureSize`, `featurePoints`, `readiness` (today many of these are dropped) |
| RHELAI | Combined file already includes `productFamily` per row; drop per-product fetch loop |
| `release-health.json` | Optional: read from `legacy/{product}/latest/` if still wanted; not required for Draft Plans table |
| Refresh UI | Keep “Refresh from pipeline” → `doFetch()`. After a runner batch, wait for archive push, then refresh. Do not trigger GitLab pipelines from Org Pulse in v1 (manual/schedule on the runner is enough). |
| Join | `mergeDraftWithReadiness()` (§5A) for live FPDoR + drawer |
| Demo | Keep `fixtures/draft-3.6-demo.json` when GitLab is disabled |

**ACL:** unchanged (viewer allowlist + plan admins). Archive is not public; Pulse is the access-controlled display.

### 5.6 Secrets and GitLab setup checklist (Week 1 infra)

Do this before writing packer features. Eder/Fege have done it for QG1.

1. **Create** GitHub `opendatahub-io/rhai-release-planner` (or agreed name). Grant John, Yuval, Arjay write. Seed empty CLI + README pointing at this plan. **This is the only new repo.**
2. **Reuse** GitLab `release-planning` as the runner. Confirm group vars (`JIRA_*`, `GITLAB_PUSH_TOKEN`, feature-traffic read token) still work. Stash the push token out of the CLI environment (QG1 hygiene).
3. **Reuse** GitLab `release-planning-data`. Do **not** create an archive project. Do **not** add a new GitLabForm exception unless the bot identity changes.
4. Tag old `release-planning` `main` (`legacy-claude-release-plan-…`). Disable or delete pipeline schedules that run `generate-plan`.
5. Move `RHOAI/` and `RHAII/` in the data repo to `legacy/` **after** Pulse fetch.js is ready, or in the same change window so nothing reads a missing path.
6. Replace `.gitlab-ci.yml` on `release-planning` `main` with `planner-validate` / `planner-batch` / `planner-version`. Daily schedule → `planner-batch` after feature-traffic has refreshed.
7. Org Pulse: keep `projectId` `81798612`; switch paths; confirm `DRAFT_PLANS_GITLAB_TOKEN` can still read the project (it already can).
8. Confirm runner still uses `aipcc-small-x86_64` and add `resource_group: planner`.

### 5.7 What the working group stops doing on the freeze path

1. Export Features List CSV and upload into `index.html`.
2. Paste `ML_SCORES` into HTML.
3. Treat `release-planning-data/{product}/latest/release-plan.json` as the Draft Plans spine.
4. Run packing or sklearn inside Org Pulse.
5. Put packer or ML code in GitLab `release-planning` after the gut (that repo is plumbing only).
6. Run the old Claude `/release-plan` job on `main` next to the new CLI.

Yuval’s personal HTML repo remains valid for experiments. Production scores and placement come only from a tooling commit SHA recorded in `run-manifest.json`.

**Live enrichment (not on the archive):** When a Draft Plans row or roadmap card is opened, join `GET /planning/feature-readiness` or `GET /execution/features/:key` for fresh FPDoR and `aiReview.scores` if the archived snapshot is stale.

---

## 5A. Rewiring data flow — Yuval CSV import → Org Pulse sources

**Short answer:** The migration plan names “replace CSV with artifact + APIs” but did not, until this section, spell out **per-field** rewiring. That mapping is below.

### How the standalone demo gets data today

```text
┌──────────────────────────────────────────────────────────────────┐
│ Yuval index.html                                                 │
│  1. User uploads CSV  OR  page loads embedded SAMPLE string      │
│  2. parseCSV() → allData[] (one row per feature)                   │
│  3. run() merges embedded blobs by Key:                          │
│     ML_SCORES, ROADMAP_OUTCOMES, FEATURE_TEAM_LOOKUP, BIG_ROCKS   │
│  4. Browser scheduler sets _place (EA1/EA2/GA/No) — NOT in CSV   │
│  5. Derived fields: _wFPDoR, _featurePts, _path, _conf, filters   │
└──────────────────────────────────────────────────────────────────┘
```

The CSV is usually an **Org Pulse Features List export** (`feature-readiness-YYYY-MM-DD.csv`). Same columns as `feature-readiness-export.js`. The demo is already shaped like Org Pulse — the problem is the **manual export → upload** loop and **extra data baked into HTML**.

### Target: three layers in Draft Plans (no CSV)

```text
Layer 1 — Schedule spine (who is in the plan, base placement)
  Source: Tooling CLI packer → runner → archive latest/v{version}/candidate-plan.json
          → Org Pulse fetch.js → draft-plans storage
  API:    GET /api/modules/releases/draft-plans/:version
          GET /api/modules/releases/draft-plans/editor/:version (red-pen overlay)

Layer 2 — Feature attributes (Jira + FPDoR + rubric + teams)
  Source: Same merge pipeline as Features List / PM Hub
  API:    GET /api/modules/releases/planning/feature-readiness
          (or execution index + per-key GET /execution/features/:key for drawer)
  Join:   candidate.key → feature-readiness row

Layer 3 — ML delivery confidence (v6)
  Source: Tooling `ml_inference.py` (v6 pickle) → archive latest/v{version}/confidence.json
  API:    Sidecar fetched with the plan; also embedded `mlConfidencePct` on each row
  Join:   candidate.key → score map
```

**Placement rule:** In Org Pulse, **display placement** = red-pen overlay on artifact `basePlacement` (same as Draft Plans today). Do **not** re-run Yuval’s browser scheduler in Vue.

### CSV column → Org Pulse source (Features List export columns)

| CSV column (demo input) | Org Pulse source when wired | Notes |
|-------------------------|----------------------------|--------|
| `Key` | Artifact `candidates[].key` | Spine join key |
| `Title` | Jira via feature-readiness `title` | `mergeFeatureData()` in `feature-readiness.js` |
| `Score` | `effectivePriorityScore` | Priority formula in planning layer (RICE + Big Rock + TV + Jira priority) |
| `Rank` | Sort order on table | Artifact `rank` or sort by Score in UI |
| `FPDoR` | `fpdor.passedCount` / applicable | `computeFPDoRReadiness()` at read time |
| `Failed FPDoR Items` | `fpdor.items` where `pass === false` | Same strings as export; drives `w:` if shown |
| `Path` | Labels → `pathLabel()` | AI First vs Legacy; from Jira labels |
| `Outcome` | `bigRock` / Big Rocks linkage | Org Pulse Big Rocks — **not** `roadmap_outcomes.json` |
| `Target Versions` | Jira `targetVersions[]` | Live Jira refresh or snapshot on artifact |
| `Fix Version` | Jira `fixVersion` | Same |
| `TV/FV Align` | `alignmentCategory` | TV/FV Delta logic (Features List already has this) |
| `Release Type` | `releaseType` | Jira field + title-prefix fallback only in demo |
| `Components` | `components[]` | Jira + aiReview merge |
| `Team` | `team` from team index / Jira Team | Replace demo `FEATURE_TEAM_LOOKUP` with capacity-dataset + Team field |
| `Status` | Jira `status` | |
| `Priority` | Jira `priority` | |
| `Confidence` | Planning `confidence` (`committed` / `ready` / `not-ready`) | **Not** the same as ML % in demo export |
| `Labels` | Jira `labels[]` | QG1, strat-creator, path detection |

### Demo fields **not** in CSV — explicit rewiring

| Demo field / blob | Today | Org Pulse replacement |
|-------------------|--------|------------------------|
| `Placement` / `_place` | Browser scheduler after CSV load | Artifact `basePlacement` + editor `placement` overlay |
| `Confidence%` / `_conf` (ML) | `ML_SCORES[key]` embedded in HTML | `mlConfidencePct` from inference JSON or artifact |
| `Reason` / `_reason` | Scheduler + gates | Artifact `placeReason` + readiness recommendations |
| `TYPE` (DP/TP/GA) | CSV + title heuristic | `releaseType` from feature-readiness |
| `SIZE` / `_featurePts` | Derived from component count in browser | Phase F: compute from `engComponents[]` or Arjay fields on artifact |
| Big Rock panel | `BIG_ROCKS` + `ROADMAP_OUTCOMES` in HTML | Big Rocks API + in-plan row keys |
| Component ceilings | `COMPONENT_CAPACITY` in HTML | Artifact `ceilingsByComponent` + Component Release Load report |
| Team lookup map | `FEATURE_TEAM_LOOKUP` (large baked JSON) | `release-capacity-dataset` / Jira Team on feature |
| Org Pulse KPI strip | Static numbers in HTML | Live PM Hub / TV/FV Delta APIs |

### Implementation options (pick one for Layer 2 join)

| Option | Pros | Cons |
|--------|------|------|
| **A — Client dual fetch** | Fast to ship; reuses `useFeatureReadiness` + `useDraftPlans` | Two requests; merge logic in Vue |
| **B — Server `enriched` endpoint** | Single response; merge in `draft-plans/routes.js` using `mergeFeatureData` | New API + tests |
| **C — Snapshot on artifact** | Single fetch; freeze-time consistent | Stale Jira; duplicates Features List |

**Recommendation:** **A for MVP** (parallel fetch + merge by key in `useDraftPlans` or a small `mergeDraftWithReadiness()` helper). **B** before freeze if performance or consistency becomes an issue. Avoid **C** for fields that change daily (status, FPDoR, labels). The **archive snapshot** is Layer 1 (placement + pack-time fields). Layer 2 stays a live Org Pulse join.

### Org Pulse tasks for Layer 2/3 join (Phase 2B)

| Task | Deliverable |
|------|-------------|
| 2B.7 | `mergeDraftWithReadiness(draft, readinessMap)` — same field mapping as table above |
| 2B.8 | Load Layer 3 from archive sidecar into `releases/draft-plans/confidence/{version}.json` |
| 2B.9 | Remove any Draft Plans dependency on CSV upload; Features List export is **training-only** |
| 2B.10 | Optional: `GET /draft-plans/:version/enriched` if client merge is too brittle |

### What the working group stops doing

1. Export Features List CSV from Org Pulse for planner review.  
2. Upload CSV into `index.html`.  
3. Treat embedded `SAMPLE` / `ML_SCORES` / `ROADMAP_OUTCOMES` as production data.

Yuval’s repo remains valid for **ML experiments** and **UX reference**; production planner review moves to Draft Plans + CI-published artifacts.

---

## 5B. Roadmap timeline view — incorporate `RHAI-Roadmap.html` into Draft Plans

**Reference prototype:** `RHAI-Roadmap.html` (Yuval / WG export; Erle copy: `RHAI-Roadmap (1).html`). Title: **RHAI Release Roadmap Timeline**. Same embedded Features List CSV as the planner demo, rendered as a **Big Rock swimlane grid** across release phases (EA1 / EA2 / GA), with filters and color-coded readiness on each feature card.

**Do not** ship this as a second standalone HTML page in production. **Add it as an alternate view inside Draft Plans**, sharing the same three data layers from §5A and the same **FeatureReadinessDrawer** as Features List and PM Hub (Phase C).

### What the HTML prototype does today

| Element | Behavior in `RHAI-Roadmap.html` |
|---------|----------------------------------|
| **Layout** | Fixed phase columns (`3.5 EA1` … `3.6 GA`); rows grouped by **Big Rock** (priority, pillar, name) |
| **Big Rock assignment** | Keyword match on `Outcome` + `Title` against baked `BIG_ROCKS` array (18 rocks + “Other Features”) |
| **Phase column** | Parse `Target Versions` / `Fix Version` strings (`getRelease()`) — **not** packer placement |
| **Card styling** | `committed` (17/17 FPDoR), `not-ready` (&lt;17), `high-risk` (&lt;10) from FPDoR fraction |
| **Card content** | Title, Key, Score, FPDoR badge, top components |
| **Filters** | Release, Big Rock, readiness status |
| **Row header** | Collapsible; shows rock priority, pillar, feature count, committed count |
| **Click** | **Modal** with ~12 flat fields (Key, Big Rock, TV, Outcome, Score, FPDoR, failed items, etc.) |

**Gap vs Org Pulse:** The modal is a read-only summary. It does **not** show the full FPDoR checklist, rubric 0–8 (`aiReview.scores`), QG1 / sign-off labels, or Jira deep links that **FeatureReadinessDrawer** already provides on Features List and PM Hub.

### Target UX in Draft Plans

```text
Draft Plans (#/releases/plan?tab=draft-plans)
  View toggle: [ Table ]  [ Roadmap ]
  Shared filter bar (release event, Big Rock, readiness, failed FPDoR — Phase C/F)
  Shared data: mergeDraftWithReadiness() + artifact placement overlay

  Table view (existing)
    Row click → FeatureReadinessDrawer (+ optional placement edit)

  Roadmap view (new — Phase F, after Phase 2 + C)
    Phase columns scoped to selected cycle (e.g. 3.6 EA1 / EA2 / GA + optional 3.5 carry-over)
    Rows = Org Pulse Big Rocks (ordered), not baked BIG_ROCKS keywords
    Cards in column = features with effective placement in that phase
    Card click → same FeatureReadinessDrawer (NOT roadmap modal)
    Row collapse state persisted in session (localStorage key per version)
```

**One drawer, two entry points:** Table row and roadmap card both call `toDrawerFeature(mergedRow)` and open `FeatureReadinessDrawer` with planning + execution join — same pattern as `FeatureReadinessView.vue` and `ComponentReleaseLoadReport.vue` (PM Hub path). Placement-only edits stay in table view or a placement section inside the drawer (see §7.2).

### Data mapping — roadmap fields vs Org Pulse (not CSV)

| Roadmap concept | Standalone HTML source | Org Pulse Draft Plans source |
|-----------------|------------------------|------------------------------|
| **Which column (phase)** | `getRelease()` on Jira TV/FV strings | **Effective placement** = red-pen overlay on artifact `basePlacement` (§5A). For roadmap **review** of live Jira drift, optional secondary mode: column from current TV (toggle — default = plan placement) |
| **Big Rock row** | `matchBigRock()` + `BIG_ROCKS` keywords | Org Pulse **Big Rocks API** + feature `bigRock` / Outcome linkage (PM Hub). **Do not** import `roadmap_outcomes.json` into PVC |
| **Rock priority / pillar** | Hard-coded in `BIG_ROCKS` | Big Rocks config (`pm-hub/pillar-config` or planning Big Rocks module) |
| **Readiness color** | FPDoR fraction thresholds on CSV `FPDoR` column | Live `fpdor` from feature-readiness join + planning `confidence` |
| **Card badges** | Score, FPDoR from CSV | `effectivePriorityScore`, `fpdor.passedCount/applicable`, optional `mlConfidencePct` |
| **Feature set** | All CSV rows with parseable release | Artifact `candidates[]` for selected version (+ red-pen descopes). Optional filter: “in plan only” vs “all readiness rows” for gap analysis |
| **Stats strip** | Showing / Total | Same merged set as table view |

**Important distinction:** The HTML roadmap is a **Jira TV snapshot** view. Draft Plans roadmap should default to **packed plan placement** so EA2 freeze review matches the table and Approve to Jira. A “show current Jira TV” toggle is optional for PM triage (Phase F+).

### Component plan (Vue)

| Piece | Path / approach |
|-------|-----------------|
| View toggle | `DraftPlansView.vue` — `viewMode: 'table' \| 'roadmap'` |
| Roadmap container | `DraftPlanRoadmapView.vue` (new) |
| Phase header row | `DraftPlanRoadmapPhaseHeaders.vue` — columns from release calendar for active `version` |
| Big Rock row | `DraftPlanRoadmapRow.vue` — header + grid |
| Feature card | `DraftPlanRoadmapCard.vue` — readiness classes mirror HTML CSS tokens (map to Tailwind) |
| Shared filters | Extend existing Draft Plans filter composable; roadmap reads same `filteredRows` ref |
| Drawer | Reuse `FeatureReadinessDrawer.vue` + `toDrawerFeature()` — **remove** roadmap modal pattern |
| Styles | Port layout from HTML (grid, collapse, legend) into Tailwind; no embedded `<style>` block from 2k-line HTML |

**Server:** No new endpoint required if Phase 2B client merge (`mergeDraftWithReadiness`) is in place. Roadmap is a **presentation layer** over the same enriched row model as the table.

### Phasing relative to §8

| Phase | Roadmap work |
|-------|----------------|
| **B / 2B** | Enriched row model must include `basePlacement`, `bigRock`, `fpdor`, `effectivePriorityScore` — roadmap blocked without archive fetch |
| **C** | **Required before roadmap is useful:** card/row click opens `FeatureReadinessDrawer` with FPDoR + `aiReview` |
| **D** | Optional ML % badge on roadmap cards (same column data as table) |
| **F** | Ship roadmap view + Big Rock row ordering from live API + phase column scoping + collapse/filters/legend |

**Suggested Phase F tasks (add to §8 Phase F table):**

| Task | Deliverable |
|------|-------------|
| F-R1 | `DraftPlanRoadmapView.vue` + view toggle in `DraftPlansView.vue` |
| F-R2 | `placementToPhaseColumn(effectivePlacement, version)` helper — map EA1/EA2/GA/Below cut to column ids |
| F-R3 | Group `filteredRows` by `bigRock.id` or name; sort by Big Rocks priority |
| F-R4 | Readiness card classes from joined `fpdor` (17/17, &lt;17, &lt;10 rules — match HTML legend) |
| F-R5 | Card click → shared drawer state with table view (single `selectedFeatureKey`) |
| F-R6 | Filters: release scope, Big Rock, readiness (reuse filter bar; hide table-only columns in roadmap mode) |
| F-R7 | Playwright: toggle roadmap, click card, assert drawer FPDoR section visible |
| F-R8 | (Optional) “Column by Jira TV” toggle for PM drift review |

**Acceptance:**

- [ ] Toggle Table ↔ Roadmap without losing version selection or red-pen overlay
- [ ] 3.6 EA2 plan features appear in correct phase columns per **effective placement**
- [ ] Big Rock rows match Org Pulse Big Rocks order (not keyword-only fallback)
- [ ] Click roadmap card → **FeatureReadinessDrawer** shows FPDoR checklist + rubric when `aiReview` exists (same as Features List)
- [ ] No modal duplicate of drawer content; no CSV load path

### What not to port from `RHAI-Roadmap.html`

- Embedded multi-thousand-line CSV string and `parseCSV()`
- Baked `BIG_ROCKS` keyword array as source of truth (use Org Pulse Big Rocks + Outcome)
- `showFeatureDetails()` modal
- Fixed `3.5` + `3.6` phase list hard-coded in HTML — derive from release calendar + selected version
- Standalone file distribution (WG should not need a Download HTML step)

(See §10 #11–#12 for roadmap column-source decisions.)

---

## 6. Data contract & join requirements

### 6.1 Packer artifact (John) — must match Draft Plans

Canonical spec: [DRAFT-PLANS-DATA-CONTRACT.md](./DRAFT-PLANS-DATA-CONTRACT.md) §4. This is the file the **GitHub tooling CLI** writes to `artifacts/candidate-plan.json`. The runner copies it into the archive. Org Pulse fetch must not invent a second schema.

**Top-level required:** `version`, `generatedAt`, `summary`, `ceilingsByComponent`, `candidates[]`.

**Recommended metadata:** `packerId`, `packerVersion`, `evaluatedAgainst`, `productFamily` scope.

**Per candidate (minimum for MVP):**

- `key`, `summary`, `basePlacement`, `rank`, `priority`, `priorityScore`
- `component` or `engComponents[]` (no single “primary” gate)
- `assignee`, `pm`, `currentTV`, `targetVersions[]`, `productFamily`
- `placeReason`, `capacityWarning`, `capacitySource`
- `humanSignoff`, `qg1Pass` (from Jira labels at pack time)
- `readiness` object (structural + recommendations) when available
- `bigRock` or `outcomeKey` (from Org Pulse / roadmap — not a second baked JSON file in Pulse)
- Optional Arjay fields for Phase F: `featureSize` (`S|M|L|XL`), `featurePoints` (3|5|8|13)

**Optional for confidence (Yuval):**

- `mlConfidencePct` (0–100 calibrated)
- `mlConfidenceBand` (`high` | `medium` | `low`) — optional derived field
- Or separate file: `confidence-3.6.json` keyed by `key` (merge in Org Pulse on load)

### 6.2 Org Pulse normalize — extend passthrough

Update **both** (keep in sync):

- `modules/releases/server/draft-plans/normalize.js`
- `modules/releases/client/plan/utils/draft-plan-model.js`

Pass through artifact fields listed above instead of dropping them. Add fixture row examples in `fixtures/draft-3.6-demo.json`.

### 6.3 aiReview / rubric (Org Pulse native)

Not required on artifact if join works:

| Field | Source |
|-------|--------|
| `aiReview.scores.feasibility` etc. | Execution feature detail |
| `rubricTotal` (0–8) | Sum of four dimensions in UI |
| FPDoR items | `computeFPDoRReadiness()` at read time or cached on feature |

**Training note:** Yuval can add `rubricTotal` + four dimensions to Features List CSV export as a bridge until Draft Plans join is live.

---

## 7. UI migration map

### 7.1 Draft Plans table — new or extended columns

| Column | Source | Owner |
|--------|--------|-------|
| Placement | `basePlacement` + edit overlay | Exists |
| FPDoR | `fpdor.passedCount/applicable` via join or artifact | Org Pulse |
| Failed FPDoR (chips or popover) | `FPDoRPopover` on row | Org Pulse |
| Confidence % | `mlConfidencePct` on row or join | Yuval → artifact; Org Pulse display |
| Capacity warn | `capacityWarning` + tooltip `placeReason` | John → artifact |
| Rubric (optional) | `rubricTotal` from `aiReview` join | Org Pulse |
| SIZE / points (optional) | Arjay model on artifact or computed in UI from `engComponents[]` | Arjay + Org Pulse Phase F |
| TYPE (DP/TP/GA) | `releaseType` from Jira / feature-readiness join | Org Pulse |
| Ready (planning) | Existing `ready` / `readyBool` | Exists |

**Summary strip (Phase F):** In-plan %, average confidence, at-risk count — mirror demo `exec-strip` but compute from loaded artifact + live joins, not hard-coded.

Sort/filter: add **Failed FPDoR item** filter (same item names as Features List export).

### 7.2 Row interaction — slide tray

**Replace or supplement** `DraftPlanDrawer` on feature row click:

1. Load full feature via `toDrawerFeature()` adapter + execution/planning join.
2. Open `FeatureReadinessDrawer` (same as Features List / Component Load report).
3. Keep `DraftPlanDrawer` for placement-only quick edit if needed, or merge placement section into readiness drawer.

**Files to touch:**

- `DraftPlansView.vue`, `DraftPlanRow.vue`
- Import `FeatureReadinessDrawer.vue`, `toDrawerFeature`

### 7.3 Access control

| Role | Capability |
|------|------------|
| **Viewer allowlist** | See Draft Plans during planning WG / freeze prep |
| **Plan admin** | Freeze, reset, Approve to Jira |
| **Default users** | No access until allowlist expanded |

Config: `draftPlansViewerEmails`, plan-admin list in `plan-admins.js` / `acl.js`. DEMO_MODE opens all locally.

**Decision:** Confirm viewer list with Erle before freeze demo (PMs, DOs, architects?).

### 7.4 Roadmap timeline view (Phase F)

Alternate layout inside Draft Plans — full spec in **§5B**.

| Element | Implementation |
|---------|----------------|
| View toggle | Table ↔ Roadmap in `DraftPlansView.vue` |
| Columns | EA1 / EA2 / GA for selected version (from release calendar) |
| Rows | Big Rocks (live API), collapsible |
| Cards | Feature title, key, score, FPDoR badge; color = readiness tier |
| Click | `FeatureReadinessDrawer` (shared with table — Phase C) |
| Filters | Same bar as table: release, Big Rock, readiness |

**Not in MVP:** Standalone `RHAI-Roadmap.html` export; modal detail panel from HTML prototype.

---

## 8. Phased implementation plan

Work is **repo-shaped**, not “John emails a JSON.” Phase 0 is mostly gut-and-tag on existing GitLab plus **one new GitHub repo**. Phase 1 can start on GitHub in parallel. UI phases C–F can use a committed fixture until `latest/v{version}/` is live.

### Phase 0 — One new GitHub repo; gut the two existing GitLab repos

**Goal:** GitHub tooling exists; `release-planning` is a thin runner on `main`; old Claude/scheduler is tagged; `release-planning-data` ready for the new layout.

| Task | Deliverable | Owner |
|------|-------------|-------|
| 0.1 | **Create** GitHub `opendatahub-io/rhai-release-planner` (or agreed name); protect `main`; CODEOWNERS | Eder + Arjay |
| 0.2 | Tag `release-planning` `main` as `legacy-claude-release-plan-YYYY-MM-DD`; optional `legacy/` branch with old CI | John |
| 0.3 | Disable old pipeline schedules (`generate-plan` / fetch-data Claude path) | John / Fege |
| 0.4 | Confirm `GITLAB_PUSH_TOKEN` still writes `release-planning-data`; stash-and-unset in new jobs | Fege |
| 0.5 | GitLabForm: **no new exception** unless bot identity changes | Fege / infra |
| 0.6 | Confirm feature-traffic **read** token on `release-planning` | John / Fege |
| 0.7 | Replace `.gitlab-ci.yml` with `planner-validate` skeleton that clones GitHub tooling | John (copy QG1 job shape) |
| 0.8 | Plan the `legacy/` move in `release-planning-data` (execute with Phase 2B so Pulse does not 404) | John + Org Pulse |
| 0.9 | README on both GitLab repos: logic in GitHub; this runner / this archive; UI in Org Pulse | Arjay |

**Acceptance:**

- [ ] Manual `planner-validate` on `release-planning` clones GitHub `main` and exits 0
- [ ] Dry-run does **not** commit to `release-planning-data`
- [ ] `push_results.py --dry-run` writes the path layout in §5.4
- [ ] Old `generate-plan` is not scheduled on `main`
- [ ] Protected `main` on `release-planning-data` still accepts the existing runner bot

**Dependency for:** Phase 1 can start on GitHub in parallel; Phase 2A needs 0.1–0.7.

---

### Phase 1 — Tooling CLI (John + Yuval + Arjay)

**Goal:** `uv run python scripts/release_planner.py --version 3.6 --dry-run` on a laptop produces contract-valid JSON. No GitLab required.

| Task | Deliverable | Owner |
|------|-------------|-------|
| 1.1 | `packer.py`: `candidates[]` with `basePlacement`, `placeReason`, `capacityWarning`; no primary component; full `engComponents[]` | John |
| 1.2 | Combined RHOAI + RHAII + RHELAI in one file | John |
| 1.3 | `size_model.py` (Arjay 140pt / S-M-L-XL) as optional fields on each row | Arjay |
| 1.4 | `ml_inference.py` + `models/models_v6.pkl` in-repo; no `/Users/yluria/...` paths | Yuval |
| 1.5 | `artifact.py` writes `candidate-plan.json`, `confidence.json`, `run-manifest.json`; JSON Schema test vs contract §4 | Arjay |
| 1.6 | README + Makefile `run` / `run-dry` matching QG1 | Arjay |
| 1.7 | Golden fixture committed for Org Pulse (copy into Pulse `fixtures/`) | John + Org Pulse |
| 1.8 | Document: HTML demo is reference only; do not invoke the browser scheduler in production | Yuval |

**Acceptance:**

- [ ] Every in-scope open Feature appears in exactly one bucket (EA1 / EA2 / GA / Below cut)
- [ ] Zero silent omissions (`placeReason` always set)
- [ ] ≥80% of rows have `mlConfidencePct` when v6 coverage allows
- [ ] `pytest` green on GitHub Actions (no Jira secrets required for unit tests)
- [ ] Org Pulse can load the fixture through `normalize.js` without hand-editing

**Do not:** copy this CLI into the runner repo.

---

### Phase 2 — Runner + archive + Org Pulse fetch

**Goal:** Scheduled/manual GitLab job publishes `latest/v3.6/candidate-plan.json`; Draft Plans refresh loads it.

#### 2A — Runner (John + Fege)

| Task | Deliverable |
|------|-------------|
| 2A.1 | `run-planner.sh` + `uv sync` in cloned tooling |
| 2A.2 | Clone `feature-traffic-data` into the tooling input dir |
| 2A.3 | Jobs `planner-batch` / `planner-version` / `planner-validate` as §5.3.2 |
| 2A.4 | `push_results.py` writes `runs/<date>/v<version>/batch/` **and** `latest/v<version>/` |
| 2A.5 | `resource_group: planner`; best-effort archive push |
| 2A.6 | Daily schedule after feature-traffic refresh |
| 2A.7 | CI artifacts retain JSON even if archive push warns |

#### 2B — Org Pulse fetch (Org Pulse / Arjay)

| Task | Deliverable |
|------|-------------|
| 2B.1 | Point `fetch.js` at planner-archive `projectId`; paths `latest/v{version}/candidate-plan.json` + `confidence.json` |
| 2B.2 | Write `releases/draft-plans/drafts/combined/{version}.json` |
| 2B.3 | Extend `normalize.js` + `draft-plan-model.js` passthrough (§6.2) |
| 2B.4 | Cycle picker from `latest/` tree or `latest/index.json` |
| 2B.5 | Existing refresh button calls `doFetch()` |
| 2B.6 | Integration test: mock GitLab files API with contract fixture |
| 2B.7 | `mergeDraftWithReadiness()` — join by key (§5A) |
| 2B.8 | Load confidence sidecar; fall back to row `mlConfidencePct` |
| 2B.9 | No CSV path in Draft Plans UI |
| 2B.10 | Stop fetching `{product}/latest/release-plan.json`; after `legacy/` move those paths 404 by design |
| 2B.11 | RHELAI via combined file (`productFamily` on rows), not a third product loop |

**Acceptance:**

- [ ] Manual `planner-version` with `VERSION=3.6` appears in archive `latest/v3.6/` within one successful pipeline
- [ ] Draft Plans “Refresh” shows that run’s placements
- [ ] `placeReason` and `capacityWarning` visible on row or tooltip
- [ ] Red-pen edits still persist to `edits/` overlay
- [ ] Dry-run job never updates `latest/`

**Files (Org Pulse):** `server/draft-plans/fetch.js`, `normalize.js`, `routes.js`, `useDraftPlans.js`, `DraftPlansView.vue`. Token `DRAFT_PLANS_GITLAB_TOKEN` already in `module.json`.

**Owner:** 2A John + Fege; 2B Org Pulse (Arjay unless assigned otherwise)

---

### Phase C — Readiness + slide tray (Org Pulse)

**Goal:** Same FPDoR / rubric experience as Features List, inside Draft Plans.

| Task | Deliverable |
|------|-------------|
| C1 | On row click, open `FeatureReadinessDrawer` |
| C2 | Join feature by key: planning readiness or execution detail |
| C3 | Show FPDoR checklist, failed items, rubric 0–8 from `aiReview.scores` |
| C4 | Optional: `FPDoRPopover` in table column |
| C5 | Failed-FPDoR filter in Draft Plans filter bar |
| C6 | Playwright: open drawer from Draft Plans row |

**Acceptance:**

- [ ] Click feature in Draft Plans → drawer shows FPDoR + rubric (when `aiReview` exists)
- [ ] No navigation to Features List required for triage
- [ ] FPDoR item names match Confluence / Org Pulse export strings

**Owner:** Org Pulse  
**Reuse:** `FeatureReadinessDrawer.vue`, `feature-readiness-drawer-model.js`, `fpdor.js`

---

### Phase D — ML confidence column (Yuval + Org Pulse)

**Goal:** Show **v6** confidence on each row at review time. Inference runs **inside the tooling CLI** on the runner, not as a laptop CSV job.

| Task | Deliverable |
|------|-------------|
| D1 | `ml_inference.py` in tooling uses `models/models_v6.pkl`; outputs `confidence.json` + per-row `mlConfidencePct` (Phase 1.4) |
| D2 | Runner archives both files; Org Pulse fetch loads sidecar (Phase 2B.8) |
| D3 | Org Pulse: column + sort; display caps (~95% with slip history / ~85% without) if product wants demo parity |
| D4 | No `merge_scores.py` paste into HTML; no hard-coded `/Users/yluria/` paths |
| D5 | Document that **v7** and **v8** are **not** production until WG promotes; training stays off the runner path |

**Acceptance:**

- [ ] ≥80% of 3.6 EA2 rows show a numeric confidence (not blank)
- [ ] Scores match Yuval `ML_SCORES` / inference JSON for sample keys (spot-check 10)
- [ ] Org Pulse does not run training or pickle inference on the request path
- [ ] Runner does not invoke `train_classifier_*.py`

**Owner:** Yuval (model + inference module), Org Pulse (column)

**Do not promote without WG agreement:**

- **v7** — 3.4 architect spreadsheet (+0.1% AUC; ~15% training coverage; no 3.6 architect scores at inference)
- **v8** — Arjay CSV merge (~416 rows; imputed slip labels for rows without real slip history)

---

### Phase E — Approve to Jira (John + Org Pulse)

**Goal:** Plan Admin writes Target Version + Fix Version from frozen plan.

| Task | Deliverable |
|------|-------------|
| E1 | Dry-run API: list TV/FV changes without write |
| E2 | Approve API: batch Jira update for approved rows |
| E3 | UI: “Dry-run” and “Approve to Jira” (Plan Admin only) |
| E4 | Audit log entries for each write |
| E5 | Respect freeze flags; map placement → standard TV strings per product family |

**Acceptance:**

- [ ] Dry-run shows diff for 5 sample features
- [ ] Approve updates Jira TV/FV for approved rows only
- [ ] Failed writes reported per key; no partial silent success

**Owner:** John (TV/FV mapping rules), Org Pulse (API + UI)

---

### Phase F — Enrichment (post-freeze / parallel if capacity allows)

| Item | Source in prototype | Org Pulse approach | Owner |
|------|---------------------|-------------------|-------|
| Big Rocks coverage panel + “not in plan” lists | `BIG_ROCKS`, `ROADMAP_OUTCOMES` fallback | Live plan rows + Org Pulse Big Rocks API; no `roadmap_outcomes.json` in PVC | Org Pulse |
| Capacity load panel (140pt / zones) | Arjay model in `index.html` | Optional banner above table; sum `featurePoints` on in-plan rows | Arjay + Org Pulse |
| 40/40/20 plan mix | Label + BR heuristic | Phase F insight panel; not a gate | Org Pulse |
| Release horizon (3.7 / 3.8) | Static timeline in HTML | Release calendar / milestone API | Org Pulse |
| **Roadmap timeline view** | `RHAI-Roadmap.html` swimlanes | `DraftPlanRoadmapView.vue` in Draft Plans (§5B) | Org Pulse |
| TV/FV aligned KPIs | Static Aug 25 snapshot | Live PM Hub / TV/FV Delta roll-up | Org Pulse |
| Bottleneck teams + Docs warning | Team lookup + heuristics | Team from capacity-dataset or Jira Team field | Erle + Org Pulse |
| Component capacity appendix | John throughput table | Link or embed from planning appendix | John |
| Features List CSV rubric columns | — | `rubricTotal` + four dimensions for Yuval training bridge | Org Pulse |
| Retrain / promote v7 or v8 | `train_classifier_v7.py`, v8 JSONL | Tooling repo only until metrics + coverage approved; never on runner | Yuval |
| Regenerate confidence | `ml_inference.py` in tooling CLI | Every `planner-batch` run | Yuval + John |

---

## 9. Testing strategy

| Layer | Tests |
|-------|--------|
| Tooling | GitHub Actions `pytest` — packer, SIZE, v6 golden keys, JSON Schema vs contract §4 |
| Runner | `tox` / `test_push_results.py` on MRs (path layout, validation); no live Jira |
| Archive | Manual: after `planner-version`, files exist under `runs/` and `latest/v3.6/` |
| Org Pulse server | `modules/releases/__tests__/server/draft-plans/` — fetch from mocked archive paths, normalize passthrough |
| Org Pulse client | `draft-plans-view.test.js`, drawer opens from row |
| E2E | `make test-module MODULE=releases` — Draft Plans load + drawer + roadmap card → drawer (Phase F) |
| Manual | Load 3.6 from archive, compare 10 keys to Yuval demo placement + confidence |

---

## 10. Open decisions (resolve in Week 1 of execution)

| # | Question | Options | Decision owner |
|---|----------|---------|----------------|
| 1 | **GitLab projects** | **Locked:** reuse [release-planning](https://gitlab.com/redhat/rhel-ai/agentic-ci/release-planning) (runner) and [release-planning-data](https://gitlab.com/redhat/rhel-ai/agentic-ci/release-planning-data) (archive). One new GitHub tooling repo. Gut old Claude/scheduler; do not create `release-planner-runner` / `release-planner-archive`. | Erle (locked 2026-08-26) |
| 2 | GitHub tooling name | `opendatahub-io/rhai-release-planner` vs `opendatahub-io/release-planner` | Eder + Arjay |
| 3 | Confidence files | **Locked default:** both embed `mlConfidencePct` on rows **and** write `confidence.json` sidecar | Yuval |
| 4 | Live join vs snapshot | Drawer always hits execution API vs archive-only at freeze | Org Pulse |
| 5 | Viewer allowlist for freeze demo | Named emails vs role-based | Erle |
| 6 | Keep `DraftPlanDrawer` | Merge into readiness drawer vs dual drawers | Org Pulse UX |
| 7 | `latest/index.json` vs tree API | Explicit index file (simpler for Pulse) vs GitLab tree listing | Org Pulse + John |
| 8 | Big Rock source of truth | Org Pulse Big Rocks vs Yuval `roadmap_outcomes.json` | Erle + PM domain — **recommend Org Pulse** |
| 9 | Arjay SIZE vs packer capacity | Two panels vs one `capacityWarning` column | John + Arjay — **recommend both** (different questions) |
| 10 | ML production version | v6 only vs promote v7/v8 | Yuval + WG |
| 11 | Roadmap column source | Plan placement vs live Jira TV | Erle + PM |
| 12 | Roadmap multi-version columns | 3.5 carry-over in same grid vs version-scoped only | Erle |
| 13 | Capacity dataset input | Snapshot in tooling `data/` vs future capacity archive clone | Arjay + Erle |
| 14 | Old Claude `/release-plan` | **Locked:** tag + `legacy/` branch; not a living job on `main` | Erle (locked 2026-08-26) |

---

## 11. Suggested owners and timeline

| Week | Focus | Who |
|------|-------|-----|
| 1 | Phase 0: create GitHub tooling; tag/gut `release-planning`; Phase 1 CLI skeleton | Eder, John, Arjay |
| 2 | Phase 1 ML + SIZE in CLI; Phase 2A runner jobs; Phase C drawer against fixture | Yuval, John, Org Pulse |
| 3 | Phase 2B Org Pulse fetch from archive; Phase D column; Phase E dry-run Approve | Arjay, Org Pulse, John |
| 4+ | Phase F enrichment + roadmap view | WG as capacity allows |

Adjust dates to the active planning freeze. If the archive slips, run Phase C against the Phase 1 fixture + live execution join so readiness work is not blocked.

**Handoff roles (plain):**

| Person | Owns |
|--------|------|
| **Arjay** | Tooling repo shape (`uv`, Makefile, schema, SIZE module); Org Pulse fetch switch; this plan as the checklist |
| **Yuval** | v6 pickle in tooling, `ml_inference.py`, no laptop paths; HTML remains prototype |
| **John** | `packer.py`, capacity warnings, runner jobs copied from QG1, TV/FV mapping for Approve |
| **Eder / Fege** | GitHub org repo creation; CI job shape on existing `release-planning`; **no** new GitLab projects |
| **Org Pulse** | Draft Plans display, drawer, roadmap, Approve API, ACL |

---

## 11A. Org Pulse touchpoints

Org Pulse is the **display + red-pen + freeze** layer. It reads the archive; it does not run the packer, ML inference, or Yuval’s browser scheduler.

### What Org Pulse does **not** change

- **Features List** — keep `FeatureReadinessDrawer`, `FPDoRPopover`, `fpdor.js`, planning/execution APIs as-is; Draft Plans joins them by key.
- **Archive project** — keep `projectId: 81798612` (`release-planning-data`); change paths only.
- **Secrets** — keep `DRAFT_PLANS_GITLAB_TOKEN` in `module.json` (read-only; no write token).
- **ACL / plan admins** — viewer allowlist and plan-admin freeze rules unchanged.
- **Red-pen overlay, audit, per-event freeze** — already shipped; keep behavior.
- **QG1** — separate system; planner packer reads labels only; Org Pulse does not write QG1 labels.
- **No** new Candidate Plan page, **no** CSV upload in Draft Plans, **no** `roadmap_outcomes.json` in PVC, **no** packer/ML/sklearn on the request path, **no** triggering GitLab pipelines from the UI in v1.

### By phase

| Phase | Org Pulse work | When |
|-------|----------------|------|
| **Phase 0** | Coordinate timing of archive `legacy/` move (task 0.8) with fetch cutover so nothing 404s mid-flight. No feature work yet. | Week 1 (with runner gut) |
| **Phase 1** | Load tooling golden fixture through `normalize.js`; extend passthrough fields early if helpful. | Parallel with CLI; unblocks tests before live archive |
| **Phase 2B** | **Main fetch + model cutover** (see below). | After runner publishes `latest/v{version}/` |
| **Phase C** | Row click → `FeatureReadinessDrawer` (FPDoR + rubric); failed-FPDoR filter. | Week 2–3; can start on fixture + live join |
| **Phase D** | ML confidence % column from archive (sidecar + row fallback). | After 2B.8 |
| **Phase E** | Approve to Jira (dry-run + write APIs); Plan Admin UI. | Week 3+ |
| **Phase F** | Big Rocks panel, SIZE/140pt banner, roadmap view, live KPIs — post-freeze enrichment. | Week 4+ |

### Phase 2B — fetch, storage, normalize (required)

**`fetch.js`**

| Today | Target |
|-------|--------|
| Per-product loop: `RHOAI`, `RHAII` | Single **combined** file per version (RHOAI + RHAII + RHELAI via `productFamily` on rows) |
| `{product}/latest/release-plan.json` | `latest/v{version}/candidate-plan.json` |
| `release-health.json` | `latest/v{version}/confidence.json` (optional: legacy health from `legacy/{product}/latest/` only if still wanted) |
| Writes `releases/draft-plans/{product}/…` | `releases/draft-plans/drafts/combined/{version}.json` + `releases/draft-plans/confidence/{version}.json` |

- Keep `projectId`, `gitlabBaseUrl`, `branch: main`, existing **Refresh** → `doFetch()`.
- Cycle picker: list versions from `latest/` tree or `latest/index.json` (2B.4).
- Stop fetching `{product}/latest/release-plan.json` once archive trees move under `legacy/` (2B.10).

**`normalize.js` + `draft-plan-model.js`** (keep in sync)

Pass through artifact fields currently dropped or thin, including: `placeReason`, `capacityWarning`, `engComponents`, `qg1Pass`, `humanSignoff`, `readiness`, `priorityScore`, `mlConfidencePct`, `featureSize`, `featurePoints`.

**Layer 2/3 join (2B.7–2B.8)**

- `mergeDraftWithReadiness(draft, readinessMap)` — client dual-fetch (MVP) or optional `GET …/enriched` later.
- Confidence: load sidecar; fall back to per-row `mlConfidencePct`.

**Tests:** mock GitLab Files API with contract fixture (2B.6).

**Files:** `fetch.js`, `normalize.js`, `draft-plan-model.js`, `routes.js`, `useDraftPlans.js`, `DraftPlansView.vue`.

### Phase C — FPDoR / drawer parity

- Replace placement-only `DraftPlanDrawer` on row click with **`FeatureReadinessDrawer`** + `toDrawerFeature()` (same as Features List / PM Hub).
- **FPDoR** at read time from planning APIs — do not duplicate checklist logic in Vue.
- **Priority:** display `effectivePriorityScore` from the feature-readiness join; artifact `priorityScore` is pack-time snapshot only — align formula in docs, do not fork scoring in the UI.
- Optional weighted `w:` display can use aligned `FPDOR_WEIGHTS`; live checklist stays Org Pulse-native.
- Add **failed-FPDoR** filter (same item names as Features List export).

### Phase D — ML column

- Show **v6** `mlConfidencePct` only; inference stays in tooling CLI on the runner.
- v7/v8 not production until WG promotes.
- Org Pulse does not run training or pickle inference.

### Phase E — Approve to Jira

- Local approve checkbox → real TV/FV write API (dry-run + batch approve).
- Respect freeze flags; audit each write.

### Phase F — enrichment (Org Pulse only)

Roadmap swimlane view, Big Rocks coverage, Arjay SIZE/140pt panel, live TV/FV KPIs — all presentation over the same enriched row model from 2B + C. No new archive schema required.

### Secrets & config

| Item | Action |
|------|--------|
| `DRAFT_PLANS_GITLAB_TOKEN` | **No change** — confirm read access to `81798612` after `legacy/` move |
| `module.json` draft-plans config | **Paths only** — same project, new file layout |
| Demo / local dev | **Keep** `fixtures/draft-3.6-demo.json` when GitLab fetch is disabled (`enabled: false`); update fixture rows to match contract passthrough fields |
| Demo fixture “deprecation” | Not removed — remains the offline/dev fallback; production spine becomes archive `latest/v{version}/`, not the fixture |

### Cutover checklist (Org Pulse)

1. **Phase 2B** merged and deployed **before or same window** as archive `RHOAI/` / `RHAII/` → `legacy/` move.
2. Refresh loads 3.6 from `latest/v3.6/candidate-plan.json`; placements match runner output.
3. Red-pen edits still persist to `edits/` overlay.
4. **Phase C** drawer shows FPDoR + rubric without leaving Draft Plans.
5. **Phase D** confidence column populated for ≥80% of rows (v6 coverage).

---

## 12. References

| Resource | URL / path |
|----------|------------|
| **QG1 tooling (pattern)** | https://github.com/opendatahub-io/release-planner-quality-gate |
| **QG1 runner (pattern)** | https://gitlab.com/redhat/rhel-ai/agentic-ci/release-quality-gate-runner |
| **QG1 archive (pattern)** | https://gitlab.com/redhat/rhel-ai/agentic-ci/release-quality-gate-archive |
| **Planner runner (reuse)** | https://gitlab.com/redhat/rhel-ai/agentic-ci/release-planning |
| **Planner archive (reuse)** | https://gitlab.com/redhat/rhel-ai/agentic-ci/release-planning-data (project `81798612`) |
| GitLabForm data-repo exception | `infrastructure/data/gitlab_security_exceptions.yml` (`release-planning-data`) |
| Yuval demo + training (prototype) | https://github.com/yuvalluria/rhai-release-planner (`main`) |
| Old mixed pipeline (tag, then gut `main`) | https://gitlab.com/redhat/rhel-ai/agentic-ci/release-planning |
| Draft Plans fetch target (keep project, change paths) | `release-planning-data` project `81798612` |
| Prototype changelog (Aug 21–25) | Arjay SIZE/capacity, roadmap outcomes, 40/40/20, horizon, KPI strip |
| `roadmap_outcomes.json` | Demo only — do not import to Org Pulse PVC |
| `RHAI-Roadmap.html` | Big Rock × phase swimlane UX reference — port to Draft Plans §5B, not standalone |
| `training_extended_v8.jsonl` | Experimental training merge (Arjay + FPDoR) |
| FPDoR weight alignment PR | https://github.com/yuvalluria/rhai-release-planner/pull/1 |
| Org Pulse Draft Plans view | `modules/releases/client/plan/views/DraftPlansView.vue` |
| Org Pulse fetch (today) | `modules/releases/server/draft-plans/fetch.js` |
| Draft Plans data contract | `release-planner-tool/docs/DRAFT-PLANS-DATA-CONTRACT.md` |
| ML journey v1–v6 | `release-planner-tool/docs/ML-CONFIDENCE-MODEL-JOURNEY.md` |
| Capacity dataset | `/Users/emarion/repos/release-capacity-dataset` |
| Turnover task 1c | `release-planner-tool/docs/TURNOVER-TOPICS-ARJAY-HINEK.md` |

---

## 13. Out of scope for this migration

- Building a second Plan or Candidate Plan page
- Hosting model training or GridSearch in Org Pulse **or** in the GitLab runner
- Putting packer / ML / SIZE code in [release-planning](https://gitlab.com/redhat/rhel-ai/agentic-ci/release-planning) after the gut
- Creating `release-planner-runner` or `release-planner-archive` (reuse the two existing GitLab projects)
- Leaving Claude `/release-plan` and `auto_scheduler.py` as living jobs on `release-planning` `main`
- Replacing the packer with Yuval’s HTML placement JavaScript
- Standalone `RHAI-Roadmap.html` as the production roadmap (must live in Draft Plans §5B)
- Full soft-freeze (PM agreed + Delivery agreed) as a gate before Approve
- Reviving legacy AIPCC Draft Plans Jira tickets (DRP-A*)
- Writing QG1 labels from the planner runner (QG1 three-repo system already does that)
- Triggering GitLab pipelines from the Org Pulse UI in v1
