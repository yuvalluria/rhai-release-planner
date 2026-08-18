"""
Clean feature importance plot — human-readable labels.
"""
import pickle
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT = '/Users/yluria/Documents/ai-first-scheduler/feature_importance.png'

with open('/Users/yluria/Documents/ai-first-scheduler/models.pkl', 'rb') as f:
    m = pickle.load(f)

rf  = m['rf'].named_steps['clf']
raw = m['feature_names']

LABELS = {
    'slip_count':            'Prior slip history',
    'fpdor_pass_rate':       'FPDoR pass rate (at freeze)',
    'fpdor_passed_count':    'FPDoR items passed (count)',
    'component_encoded':     'Component (delivery reliability)',
    'rice':                  'RICE score',
    'criteria_pass_rate':    'FPDoR criteria pass rate',
    'mandatory_pass_rate':   'Mandatory items pass rate',
    'committed_phase_ord':   'Committed phase (EA1/EA2/GA)',
    'jira_priority':         'Jira priority',
    'docs_pass':             'Docs impact (FPDoR item)',
    'has_docs_component':    'Has Docs component',
    'rt_pass':               'Release type set (pass/fail only)',
}

imp    = rf.feature_importances_
labels = [LABELS.get(n, n) for n in raw]
pct    = imp * 100

# sort descending
idx    = np.argsort(pct)[::-1]
labels = [labels[i] for i in idx]
pct    = pct[idx]

# color: dominant = dark red, rest = blue gradient, zero = grey
colors = []
for i, v in enumerate(pct):
    if i == 0:   colors.append('#c62828')   # slip_count — dominant
    elif v == 0: colors.append('#e0e0e0')   # zero signal
    else:        colors.append('#2471a3')

fig, ax = plt.subplots(figsize=(11, 5.5))
fig.patch.set_facecolor('#f8f9fa')
ax.set_facecolor('#f8f9fa')

bars = ax.barh(range(len(labels)), pct, color=colors, edgecolor='white', linewidth=0.6)

# value labels
for bar, v in zip(bars, pct):
    if v > 0:
        ax.text(v + 0.3, bar.get_y() + bar.get_height()/2,
                f'{v:.1f}%', va='center', ha='left', fontsize=9,
                fontweight='bold', color='#333')

ax.set_yticks(range(len(labels)))
ax.set_yticklabels(labels, fontsize=10)
ax.invert_yaxis()
ax.set_xlabel('Feature Importance (%)', fontsize=10)
ax.set_xlim(0, max(pct) * 1.18)
ax.spines[['top', 'right', 'left']].set_visible(False)
ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x:.0f}%'))
ax.grid(axis='x', alpha=0.2, linestyle='--')
ax.tick_params(left=False)

ax.set_title(
    'RHAI Release Confidence — Feature Importance\n'
    'Random Forest · trained on RHOAI 3.5 (n=115 committed features)',
    fontsize=12, fontweight='bold', pad=12, color='#111'
)

fig.text(
    0.99, 0.02,
    '⚠  "Release type (pass/fail only)" = 0% — actual DP/TP/GA value not in 3.5 training data. '
    'Adding it is expected to unlock meaningful signal (currently +8% / +5% boosts are rule-based).',
    ha='right', fontsize=7.5, color='#777', style='italic'
)

plt.tight_layout(rect=[0, 0.04, 1, 1])
plt.savefig(OUT, dpi=160, bbox_inches='tight', facecolor=fig.get_facecolor())
print(f'Saved → {OUT}')
