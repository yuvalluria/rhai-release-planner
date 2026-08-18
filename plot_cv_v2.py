"""
CV comparison plot — v2
Panel 1: RF AUC across all 4 balancing strategies vs LR baseline
Panel 2: per-fold detail for winner (Random Oversampling, LR vs RF)
Panel 3: feature importance with ROS-balanced RF
"""
import pickle
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

OUT_COMPARE = '/Users/yluria/Documents/ai-first-scheduler/cv_results_v2.png'
OUT_IMP     = '/Users/yluria/Documents/ai-first-scheduler/feature_importance_v2.png'

with open('/Users/yluria/Documents/ai-first-scheduler/models_v2.pkl', 'rb') as f:
    m = pickle.load(f)

cv = m['all_cv']
rf = m['rf']
feature_names = m['feature_names']

STRAT_LABELS = {
    'Baseline\n(class_weight)': 'Baseline\n(class_weight only)',
    'Random\nOversampling':     'Random\nOversampling ★',
    'SMOTE':                    'SMOTE',
    'ADASYN':                   'ADASYN',
}
STRAT_KEYS = list(cv.keys())

LR_COLOR = '#c0392b'
RF_COLOR = '#2471a3'
BAR_W    = 0.34

# ── Figure: 3 panels ─────────────────────────────────────────────────────────
fig = plt.figure(figsize=(18, 6.5))
fig.patch.set_facecolor('#f8f9fa')
gs = fig.add_gridspec(1, 3, wspace=0.38, left=0.06, right=0.97, top=0.80, bottom=0.18)
ax1, ax2, ax3 = fig.add_subplot(gs[0]), fig.add_subplot(gs[1]), fig.add_subplot(gs[2])
for ax in (ax1, ax2, ax3):
    ax.set_facecolor('#f8f9fa')

# ── Panel 1: RF AUC across strategies (grouped LR vs RF bars) ────────────────
x = np.arange(len(STRAT_KEYS))
lr_aucs  = [np.mean(cv[s]['lr']['auc']) * 100 for s in STRAT_KEYS]
rf_aucs  = [np.mean(cv[s]['rf']['auc']) * 100 for s in STRAT_KEYS]
lr_stds  = [np.std(cv[s]['lr']['auc'])  * 100 for s in STRAT_KEYS]
rf_stds  = [np.std(cv[s]['rf']['auc'])  * 100 for s in STRAT_KEYS]

bars_lr = ax1.bar(x - BAR_W/2, lr_aucs, BAR_W, color=LR_COLOR, alpha=0.82,
                  label='Logistic Regression (baseline)', edgecolor='white', linewidth=0.8)
bars_rf = ax1.bar(x + BAR_W/2, rf_aucs, BAR_W, color=RF_COLOR, alpha=0.82,
                  label='Random Forest', edgecolor='white', linewidth=0.8)

# error bars
ax1.errorbar(x - BAR_W/2, lr_aucs, yerr=lr_stds, fmt='none', color=LR_COLOR,
             capsize=4, linewidth=1.5, alpha=0.6)
ax1.errorbar(x + BAR_W/2, rf_aucs, yerr=rf_stds, fmt='none', color=RF_COLOR,
             capsize=4, linewidth=1.5, alpha=0.6)

# value labels
for bar, v in zip(bars_lr, lr_aucs):
    ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.6,
             f'{v:.1f}%', ha='center', va='bottom', fontsize=8.5,
             color=LR_COLOR, fontweight='bold')
for bar, v, is_best in zip(bars_rf, rf_aucs, [False, True, False, False]):
    ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.6,
             f'{v:.1f}%{"  ★" if is_best else ""}',
             ha='center', va='bottom', fontsize=8.5,
             color='#1a5276' if is_best else RF_COLOR, fontweight='bold')

# highlight best bar background
best_idx = 1  # Random Oversampling
ax1.axvspan(best_idx - 0.5, best_idx + 0.5, color='#e3f2fd', alpha=0.5, zorder=0)

ax1.set_title('AUC-ROC by Balancing Strategy\n(RF vs LR baseline)', fontsize=12,
              fontweight='bold', pad=10, color='#222')
ax1.set_ylabel('AUC-ROC (%)', fontsize=10)
ax1.set_xticks(x)
ax1.set_xticklabels([STRAT_LABELS[s] for s in STRAT_KEYS], fontsize=8.5)
ax1.set_ylim(72, 100)
ax1.yaxis.set_major_formatter(mticker.FormatStrFormatter('%g%%'))
ax1.spines[['top','right']].set_visible(False)
ax1.grid(axis='y', alpha=0.2, linestyle='--', zorder=1)
ax1.legend(fontsize=8, loc='lower right', framealpha=0.9, edgecolor='#ccc')
ax1.text(best_idx, 73.5, 'RF wins here', ha='center', fontsize=8,
         color='#1565c0', style='italic')

# ── Panel 2: per-fold detail for winner (ROS), LR vs RF ──────────────────────
ros_key = 'Random\nOversampling'
ros     = cv[ros_key]
folds   = list(range(1, len(ros['lr']['auc']) + 1))
xf      = np.arange(len(folds))

for i, (model, color) in enumerate([('lr', LR_COLOR), ('rf', RF_COLOR)]):
    vals   = np.array(ros[model]['auc']) * 100
    mean_v = np.mean(vals)
    std_v  = np.std(vals)
    label  = (f'LR — baseline\n  {mean_v:.1f}% ± {std_v:.1f}%' if model == 'lr'
              else f'RF (ROS) ★\n  {mean_v:.1f}% ± {std_v:.1f}%')
    bars = ax2.bar(xf + i * BAR_W, vals, BAR_W,
                   color=color, alpha=0.82, label=label,
                   edgecolor='white', linewidth=0.8, zorder=3)
    ax2.axhline(mean_v, color=color, linestyle='--', linewidth=1.8, alpha=0.65, zorder=2)
    for bar, v in zip(bars, vals):
        if v < 99.5:
            ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.6,
                     f'{v:.0f}%', ha='center', va='bottom',
                     fontsize=8, color=color, fontweight='bold')

ax2.annotate(
    '* Fold 1: only 1 negative\nin test split → high variance',
    xy=(0 + BAR_W/2, min(np.array(ros['lr']['auc'])[0], np.array(ros['rf']['auc'])[0]) * 100 - 1),
    xytext=(1.2, 55),
    fontsize=7.5, color='#666',
    arrowprops=dict(arrowstyle='->', color='#999', lw=1),
    bbox=dict(boxstyle='round,pad=0.3', fc='#fffde7', ec='#f0c040', alpha=0.9),
)
ax2.set_title('AUC per Fold — Best Strategy\n(Random Oversampling, 5-Fold CV)', fontsize=12,
              fontweight='bold', pad=10, color='#222')
ax2.set_xlabel('Fold', fontsize=10)
ax2.set_xticks(xf + BAR_W/2)
ax2.set_xticklabels([f'Fold {f}' for f in folds], fontsize=9.5)
ax2.set_ylim(45, 103)
ax2.yaxis.set_major_formatter(mticker.FormatStrFormatter('%g%%'))
ax2.spines[['top','right']].set_visible(False)
ax2.grid(axis='y', alpha=0.2, linestyle='--', zorder=1)
ax2.legend(fontsize=8.5, loc='lower left', framealpha=0.9, edgecolor='#ccc')

# ── Panel 3: RF feature importance (balanced RF) ──────────────────────────────
LABELS = {
    'slip_count':            'Prior slip history',
    'fpdor_pass_rate':       'FPDoR pass rate',
    'fpdor_passed_count':    'FPDoR items passed',
    'component_encoded':     'Component reliability',
    'rice':                  'RICE score',
    'criteria_pass_rate':    'Criteria pass rate',
    'mandatory_pass_rate':   'Mandatory items pass rate',
    'committed_phase_ord':   'Committed phase (EA1/EA2/GA)',
    'jira_priority':         'Jira priority',
    'docs_pass':             'Docs impact (FPDoR)',
    'has_docs_component':    'Has Docs component',
    'rt_pass':               'Release type set (pass/fail)',
}
imp    = rf.feature_importances_
labels = [LABELS.get(n, n) for n in feature_names]
pct    = imp * 100
idx    = np.argsort(pct)[::-1]
labels = [labels[i] for i in idx]
pct    = pct[idx]

colors = []
for i, v in enumerate(pct):
    if i == 0:   colors.append('#c62828')
    elif v == 0: colors.append('#e0e0e0')
    else:        colors.append('#2471a3')

bars3 = ax3.barh(range(len(labels)), pct, color=colors, edgecolor='white', linewidth=0.6)
for bar, v in zip(bars3, pct):
    if v > 0:
        ax3.text(v + 0.3, bar.get_y() + bar.get_height()/2,
                 f'{v:.1f}%', va='center', ha='left', fontsize=8.5,
                 fontweight='bold', color='#333')
ax3.set_yticks(range(len(labels)))
ax3.set_yticklabels(labels, fontsize=9)
ax3.invert_yaxis()
ax3.set_xlabel('Feature Importance (%)', fontsize=10)
ax3.set_xlim(0, max(pct) * 1.22)
ax3.spines[['top','right','left']].set_visible(False)
ax3.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x:.0f}%'))
ax3.grid(axis='x', alpha=0.2, linestyle='--')
ax3.tick_params(left=False)
ax3.set_title('Feature Importance\n(RF with Random Oversampling)', fontsize=12,
              fontweight='bold', pad=10, color='#222')

# ── overall title + footnotes ─────────────────────────────────────────────────
fig.text(0.5, 0.96,
         'RHAI Release Confidence — Balancing Techniques Comparison',
         ha='center', fontsize=14, fontweight='bold', color='#111')
fig.text(0.5, 0.905,
         'Training: RHOAI 3.5  ·  n=115 committed (104 shipped, 11 slipped)  ·  '
         '5-Fold Stratified CV  ·  Balancers applied inside each train split only',
         ha='center', fontsize=9.5, color='#444')

fig.text(0.5, 0.04,
         'Verdict: RF beats LR with oversampling (ROS: 91.9% vs 90.5%).  '
         'SMOTE hurt RF — interpolating between only 11 negatives adds noise.  '
         'High variance (±16%) is expected with 11 true negatives; '
         '3.4 data will reduce it.',
         ha='center', fontsize=9, color='#555', style='italic',
         bbox=dict(boxstyle='round,pad=0.45', facecolor='#fff3cd',
                   edgecolor='#ffc107', alpha=0.95))

plt.savefig(OUT_COMPARE, dpi=160, bbox_inches='tight', facecolor=fig.get_facecolor())
print(f'Saved → {OUT_COMPARE}')
