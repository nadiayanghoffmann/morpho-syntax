#!/usr/bin/env python3
"""
behavioral_analysis.py
======================
Behavioral analysis script for the Morpho-Syntax noun stimuli study.
Configured for 12 conditions and their corresponding MEG trigger combinations
from data/stimuli_nouns.csv.

12 Conditions & Trigger Mapping:
--------------------------------
Critical Conditions (2×2×2 factorial: Comp/List × Phrase/Compound × Space/Nospace):
  1. Comp × Phrase   × Space   → [ch160, ch161, ch162, ch163]
  2. Comp × Phrase   × Nospace → [ch160, ch162, ch163]
  3. Comp × Compound × Space   → [ch161, ch162, ch163]
  4. Comp × Compound × Nospace → [ch162, ch163]
  5. List × Phrase   × Space   → [ch160, ch161, ch163]
  6. List × Phrase   × Nospace → [ch160, ch163]
  7. List × Compound × Space   → [ch161, ch163]
  8. List × Compound × Nospace → [ch163]

Localizer Conditions:
  9.  SSELocalizer × Phrase-Loc → [ch160, ch164]
  10. SSELocalizer × List-Loc   → [ch164]
  11. Lexicality   × Word       → [ch165]
  12. Lexicality   × Pseudoword → [ch166]
  13. Lexicality   × ConsonantString → [ch165, ch166]

Trigger Lines:
  • ch160: Phrase trigger line (active for Phrase conditions)
  • ch161: Space trigger line  (active for Spaced conditions)
  • ch162: Comp trigger line   (active for Composition conditions)
  • ch163: Critical baseline marker line
  • ch164: SSELocalizer marker line
  • ch165: Lexicality Word line
  • ch166: Lexicality Pseudoword line

Figures saved to: figures/
CSVs   saved to : analysis/
"""

# ── 0. Imports & configuration ────────────────────────────────────────────────
import csv
import glob
import os
import sys
import warnings
from itertools import combinations
from collections import defaultdict

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import statsmodels.formula.api as smf
import statsmodels.api as sm
from statsmodels.stats.multitest import multipletests
from scipy.stats import ttest_ind

# Import trigger definitions
from port_open_send import (
    TRIGGER_MAP_12, CONDITION_INFO_12, CHANNEL_BITS,
    get_condition_channels, channels_to_mask
)

warnings.filterwarnings("ignore")

# ── Paths ─────────────────────────────────────────────────────────────────────
HERE         = os.path.dirname(os.path.abspath(__file__))
DATA_DIR     = os.path.join(HERE, "data")
LOGS_DIR     = os.path.join(HERE, "logs")
STIMULI_PATH = os.path.join(DATA_DIR, "stimuli_nouns.csv")
FIGURES_DIR  = os.path.join(HERE, "figures")
ANALYSIS_DIR = os.path.join(HERE, "analysis")

os.makedirs(FIGURES_DIR, exist_ok=True)
os.makedirs(ANALYSIS_DIR, exist_ok=True)

# ── Constants ──────────────────────────────────────────────────────────────────
RT_LOW_S  = 0.10   # seconds
RT_HIGH_S = 2.00   # seconds

COND_ORDER_12 = [
    "Comp_Phrase_Space",
    "Comp_Phrase_Nospace",
    "Comp_Compound_Space",
    "Comp_Compound_Nospace",
    "List_Phrase_Space",
    "List_Phrase_Nospace",
    "List_Compound_Space",
    "List_Compound_Nospace",
    "SSELoc_Phrase",
    "SSELoc_List",
    "Lex_Word",
    "Lex_Pseudoword",
    "Lex_ConsonantString",
]

COND_LABELS_12 = {
    "Comp_Phrase_Space":     "Comp Phrase Sp\n[160,161,162,163]",
    "Comp_Phrase_Nospace":   "Comp Phrase NoSp\n[160,162,163]",
    "Comp_Compound_Space":   "Comp Comp Sp\n[161,162,163]",
    "Comp_Compound_Nospace": "Comp Comp NoSp\n[162,163]",
    "List_Phrase_Space":     "List Phrase Sp\n[160,161,163]",
    "List_Phrase_Nospace":   "List Phrase NoSp\n[160,163]",
    "List_Compound_Space":   "List Comp Sp\n[161,163]",
    "List_Compound_Nospace": "List Comp NoSp\n[163]",
    "SSELoc_Phrase":         "SSELoc Phrase\n[160,164]",
    "SSELoc_List":           "SSELoc List\n[164]",
    "Lex_Word":              "Lex Word\n[165]",
    "Lex_Pseudoword":        "Lex Pseudo\n[166]",
    "Lex_ConsonantString":   "Lex Consonant\n[165,166]",
}

COND_COLORS = {
    "Comp_Phrase_Space":     "#1F77B4",
    "Comp_Phrase_Nospace":   "#4A90E2",
    "Comp_Compound_Space":   "#2CA02C",
    "Comp_Compound_Nospace": "#50E3C2",
    "List_Phrase_Space":     "#FF7F0E",
    "List_Phrase_Nospace":   "#F5A623",
    "List_Compound_Space":   "#D62728",
    "List_Compound_Nospace": "#E02020",
    "SSELoc_Phrase":         "#9467BD",
    "SSELoc_List":           "#8B572A",
    "Lex_Word":              "#17BECF",
    "Lex_Pseudoword":        "#BCBD22",
    "Lex_ConsonantString":   "#7F7F7F",
}

# morpho_syntax.py log column → name used in this script
LOG_COLUMN_RENAMES = {
    'Participant':       'participant_id',
    'Participant_Resp':  'pressed_key',
    'Expected_Response': 'expected_key',
    'Correct':           'is_correct',
    'RT_s':              'rt_s',
}

SDT_COLORS = {
    "Hit":            "#4CAF50",
    "Miss":           "#F44336",
    "Correct Reject": "#2196F3",
    "False Alarm":    "#FF9800",
}


# ── 1. Load stimuli & behavioral data ─────────────────────────────────────────
def map_row_to_condition(tc, sl, sp):
    """Map triplet to standardized condition name in COND_ORDER_12."""
    tc, sl, sp = str(tc).strip(), str(sl).strip(), str(sp).strip()
    if tc == 'Comp':
        if sl == 'Phrase':
            return 'Comp_Phrase_Space' if sp == 'Space' else 'Comp_Phrase_Nospace'
        else:
            return 'Comp_Compound_Space' if sp == 'Space' else 'Comp_Compound_Nospace'
    elif tc == 'List':
        if sl == 'Phrase':
            return 'List_Phrase_Space' if sp == 'Space' else 'List_Phrase_Nospace'
        else:
            return 'List_Compound_Space' if sp == 'Space' else 'List_Compound_Nospace'
    elif tc == 'SSELocalizer':
        return 'SSELoc_Phrase' if 'Phrase' in sl else 'SSELoc_List'
    elif tc == 'Lexicality':
        if sl == 'Word':
            return 'Lex_Word'
        if sl == 'ConsonantString':
            return 'Lex_ConsonantString'
        return 'Lex_Pseudoword'
    return 'Unknown'


def load_stimuli_catalog():
    """Load stimuli_nouns.csv and tag with condition and trigger channels."""
    if not os.path.exists(STIMULI_PATH):
        raise FileNotFoundError(f"Stimuli file not found: {STIMULI_PATH}")
    df = pd.read_csv(STIMULI_PATH)

    crit = df['TestControl'].isin(['Comp', 'List'])
    sse  = (df['TestControl'] == 'SSELocalizer') & (df['StrucLevel'].isin(['Phrase-Loc', 'List-Loc']))
    lex  = (df['TestControl'] == 'Lexicality') & (df['StrucLevel'].isin(['Word', 'Pseudoword', 'ConsonantString']))
    df = df[crit | sse | lex].copy()

    df['Condition'] = [
        map_row_to_condition(r['TestControl'], r['StrucLevel'], r['Spacing'])
        for _, r in df.iterrows()
    ]
    df['Trigger_Channels'] = [
        get_condition_channels(r['TestControl'], r['StrucLevel'], r['Spacing'])
        for _, r in df.iterrows()
    ]
    df['Trigger_Mask'] = [channels_to_mask(c) for c in df['Trigger_Channels']]
    return df


def load_all_behavioral_data():
    """
    Load behavioral results from logs/<sub_id>/ or data/*.csv.
    If no behavioral log files are found, simulates realistic participant data
    (N=20) across all 12 conditions to demonstrate full pipeline execution.
    """
    log_files = glob.glob(os.path.join(LOGS_DIR, "**", "*trials.csv"), recursive=True)
    if not log_files:
        log_files = glob.glob(os.path.join(DATA_DIR, "*trials.csv"))

    if log_files:
        print(f"  Found {len(log_files)} participant log files.")
        dfs = []
        for f in log_files:
            # Keys must stay strings ('1'/'2'); pandas would otherwise read them as numbers
            sub_df = pd.read_csv(f, dtype={'Participant_Resp': str, 'Expected_Response': str})
            dfs.append(sub_df)
        df = pd.concat(dfs, ignore_index=True).rename(columns=LOG_COLUMN_RENAMES)
        df['Condition'] = [
            map_row_to_condition(r['TestControl'], r['StrucLevel'], r['Spacing'])
            for _, r in df.iterrows()
        ]
    else:
        print("  No participant session logs found in logs/ or data/. Generating baseline N=20 demonstration data...")
        stim_catalog = load_stimuli_catalog()
        np.random.seed(42)
        n_subs = 20
        sim_rows = []

        # Typical behavioral parameters per condition
        cond_effects = {
            'Comp_Phrase_Space':     (0.95, 0.58),
            'Comp_Phrase_Nospace':   (0.91, 0.64),
            'Comp_Compound_Space':   (0.92, 0.62),
            'Comp_Compound_Nospace': (0.89, 0.67),
            'List_Phrase_Space':     (0.93, 0.61),
            'List_Phrase_Nospace':   (0.88, 0.69),
            'List_Compound_Space':   (0.90, 0.65),
            'List_Compound_Nospace': (0.86, 0.72),
            'SSELoc_Phrase':         (0.96, 0.55),
            'SSELoc_List':           (0.94, 0.59),
            'Lex_Word':              (0.97, 0.52),
            'Lex_Pseudoword':        (0.92, 0.63),
            'Lex_ConsonantString':   (0.97, 0.50),
        }

        for sub_i in range(1, n_subs + 1):
            sub_id = f"sub-{sub_i:02d}"
            for _, r in stim_catalog.iterrows():
                cond = r['Condition']
                base_acc, base_rt = cond_effects.get(cond, (0.90, 0.65))
                is_match = (r['Match'] == 'Match')
                expected = '2' if is_match else '1'

                # Subject-level variation
                acc_prob = np.clip(base_acc + np.random.normal(0, 0.04), 0.5, 0.99)
                is_corr = (np.random.rand() < acc_prob)
                pressed = expected if is_corr else ('1' if expected == '2' else '2')

                rt = np.clip(np.random.normal(base_rt, 0.12), RT_LOW_S, RT_HIGH_S)

                sim_rows.append({
                    'participant_id':   sub_id,
                    'Item':             r['Item'],
                    'TestControl':      r['TestControl'],
                    'StrucLevel':       r['StrucLevel'],
                    'Spacing':          r['Spacing'],
                    'Condition':        cond,
                    'Trigger_Channels': " ".join(r['Trigger_Channels']),
                    'Trigger_Mask':     r['Trigger_Mask'],
                    'Stim1':            r['Stim1'],
                    'Stim2':            r['Stim2'],
                    'Match':            r['Match'],
                    'expected_key':     expected,
                    'pressed_key':      pressed,
                    'is_correct':       is_corr,
                    'rt_s':             round(float(rt), 4),
                })
        df = pd.DataFrame(sim_rows)

    return df


def classify_responses(df):
    """Tag Signal Detection Theory response types (Hit, Miss, CR, FA)."""
    df = df.copy()
    same = (df['Match'] == 'Match')
    k2   = (df['pressed_key'] == '2')
    k1   = (df['pressed_key'] == '1')

    df['Response_Type'] = 'Unclassified'
    df.loc[same  & k2, 'Response_Type'] = 'Hit'
    df.loc[same  & k1, 'Response_Type'] = 'Miss'
    df.loc[~same & k1, 'Response_Type'] = 'Correct Reject'
    df.loc[~same & k2, 'Response_Type'] = 'False Alarm'
    df['Accurate'] = df['Response_Type'].isin(['Hit', 'Correct Reject']).astype(int)

    # Add boolean trigger flags
    df['has_ch160_phrase'] = df['Trigger_Channels'].str.contains('ch160')
    df['has_ch161_space']  = df['Trigger_Channels'].str.contains('ch161')
    df['has_ch162_comp']   = df['Trigger_Channels'].str.contains('ch162')
    return df


def filter_rt(df):
    """Filter reaction times to standard interval."""
    return df[df['rt_s'].notna() & df['rt_s'].between(RT_LOW_S, RT_HIGH_S)].copy()


# ── 2. Stat helpers ────────────────────────────────────────────────────────────
def acc_summary(df, group_cols):
    g = df.groupby(group_cols)
    out = g['Accurate'].agg(mean_acc='mean', n_trials='size').reset_index()
    out['se_acc'] = np.sqrt(out['mean_acc'] * (1 - out['mean_acc']) / out['n_trials'].clip(lower=1))
    return out


def rt_summary(df_rt, group_cols):
    g = df_rt.groupby(group_cols)
    out = g['rt_s'].agg(mean_rt='mean', std_rt='std', n_trials='size').reset_index()
    out['se_rt'] = out['std_rt'] / np.sqrt(out['n_trials'].clip(lower=1))
    return out


def p_star(p):
    if p < 0.001: return "***"
    if p < 0.01:  return "**"
    if p < 0.05:  return "*"
    return "ns"


def pairwise_fdr(df, group_col, value_col):
    """Pairwise Welch t-tests across conditions with FDR-BH correction."""
    groups = [g for g in COND_ORDER_12 if g in df[group_col].unique()]
    pairs = list(combinations(groups, 2))
    records = []
    for g1, g2 in pairs:
        a = df.loc[df[group_col] == g1, value_col].dropna().values
        b = df.loc[df[group_col] == g2, value_col].dropna().values
        if len(a) < 2 or len(b) < 2:
            continue
        _, p = ttest_ind(a, b, equal_var=False)
        records.append({'g1': g1, 'g2': g2, 'p_raw': p})
    if not records:
        return pd.DataFrame(columns=['g1', 'g2', 'p_raw', 'p_adj', 'reject'])
    pw = pd.DataFrame(records)
    reject, padj, _, _ = multipletests(pw['p_raw'], method='fdr_bh')
    pw['p_adj'] = padj
    pw['reject'] = reject
    return pw


# ── 3. Plotting Functions ──────────────────────────────────────────────────────
def plot_2x2x2_factorial(df, rt_df, out_filename):
    """
    Grouped bar chart for the 8 critical conditions:
    TestControl (Comp vs List) × StrucLevel (Phrase vs Compound) × Spacing (Space vs Nospace).
    """
    crit_df = df[df['TestControl'].isin(['Comp', 'List'])].copy()
    crit_rt = rt_df[rt_df['TestControl'].isin(['Comp', 'List'])].copy()

    # 3-way ANOVA
    try:
        acc_model = smf.ols('Accurate ~ C(TestControl) * C(StrucLevel) * C(Spacing)', data=crit_df).fit()
        acc_anova = sm.stats.anova_lm(acc_model, typ=2)
    except Exception:
        acc_anova = pd.DataFrame()

    try:
        rt_model = smf.ols('rt_s ~ C(TestControl) * C(StrucLevel) * C(Spacing)', data=crit_rt).fit()
        rt_anova = sm.stats.anova_lm(rt_model, typ=2)
    except Exception:
        rt_anova = pd.DataFrame()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

    struc_spacings = [('Phrase', 'Space'), ('Phrase', 'Nospace'),
                      ('Compound', 'Space'), ('Compound', 'Nospace')]
    x_labels = ["Phrase\nSpaced", "Phrase\nNoSpace", "Compound\nSpaced", "Compound\nNoSpace"]
    x = np.arange(len(struc_spacings))
    w = 0.35

    a_sum = acc_summary(crit_df, ['TestControl', 'StrucLevel', 'Spacing'])
    r_sum = rt_summary(crit_rt, ['TestControl', 'StrucLevel', 'Spacing'])

    for ax, s_df, ycol, secol, ylabel, is_pct in [
        (ax1, a_sum, 'mean_acc', 'se_acc', 'Accuracy', True),
        (ax2, r_sum, 'mean_rt',  'se_rt',  'Mean RT (s)', False),
    ]:
        comp_vals, comp_err = [], []
        list_vals, list_err = [], []

        for sl, sp in struc_spacings:
            c_row = s_df[(s_df['TestControl'] == 'Comp') & (s_df['StrucLevel'] == sl) & (s_df['Spacing'] == sp)]
            l_row = s_df[(s_df['TestControl'] == 'List') & (s_df['StrucLevel'] == sl) & (s_df['Spacing'] == sp)]

            comp_vals.append(float(c_row[ycol].iloc[0]) if not c_row.empty else 0)
            comp_err.append(float(c_row[secol].iloc[0]) if not c_row.empty else 0)
            list_vals.append(float(l_row[ycol].iloc[0]) if not l_row.empty else 0)
            list_err.append(float(l_row[secol].iloc[0]) if not l_row.empty else 0)

        b1 = ax.bar(x - w/2, comp_vals, w, yerr=comp_err, capsize=4, label='Composition (Comp)', color='#2B5C8F', alpha=0.9, edgecolor='black')
        b2 = ax.bar(x + w/2, list_vals, w, yerr=list_err, capsize=4, label='List Control', color='#D95F02', alpha=0.9, edgecolor='black')

        ax.set_xticks(x)
        ax.set_xticklabels(x_labels, fontsize=10)
        ax.set_ylabel(ylabel, fontsize=11)
        ax.grid(axis='y', alpha=0.3)
        ax.legend(framealpha=0.9)

        if is_pct:
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y*100:.0f}%"))
            ax.set_ylim(0, 1.15)
        else:
            ax.set_ylim(0, max(comp_vals + list_vals) * 1.3)

    ax1.set_title("Critical Conditions — Accuracy\n(2×2×2 Factorial Design)", fontweight='bold', fontsize=12)
    ax2.set_title("Critical Conditions — Reaction Time\n(0.10–2.00 s Filtered)", fontweight='bold', fontsize=12)

    fig.tight_layout()
    path = os.path.join(FIGURES_DIR, out_filename)
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved: {out_filename}")
    return acc_anova, rt_anova


def plot_trigger_channels_breakdown(df, rt_df, out_filename):
    """
    Main effects of individual trigger lines:
      • ch160: Phrase (Phrase vs Compound)
      • ch161: Spaced (Space vs Nospace)
      • ch162: Comp   (Comp vs List)
    """
    crit_df = df[df['TestControl'].isin(['Comp', 'List'])].copy()
    crit_rt = rt_df[rt_df['TestControl'].isin(['Comp', 'List'])].copy()

    fig, axes = plt.subplots(2, 3, figsize=(15, 8))

    lines = [
        ('ch160 (Phrase Line)', 'has_ch160_phrase', ['Compound (0)', 'Phrase (1)'], '#386CB0'),
        ('ch161 (Spacing Line)', 'has_ch161_space',  ['Nospace (0)', 'Spaced (1)'],  '#7FC97F'),
        ('ch162 (Comp Line)',    'has_ch162_comp',   ['List (0)', 'Comp (1)'],       '#FDC086'),
    ]

    for col_idx, (title, flag_col, x_names, col) in enumerate(lines):
        # Accuracy
        ax_a = axes[0, col_idx]
        a_grp = crit_df.groupby(flag_col)['Accurate'].agg(['mean', 'size']).reset_index()
        a_grp['se'] = np.sqrt(a_grp['mean'] * (1 - a_grp['mean']) / a_grp['size'])
        bars = ax_a.bar([0, 1], a_grp['mean'], yerr=a_grp['se'], capsize=5, color=col, alpha=0.85, edgecolor='black', width=0.5)
        ax_a.set_xticks([0, 1])
        ax_a.set_xticklabels(x_names)
        ax_a.set_ylabel("Accuracy")
        ax_a.set_ylim(0, 1.1)
        ax_a.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y*100:.0f}%"))
        ax_a.set_title(f"Accuracy by {title}", fontweight='bold')
        ax_a.grid(axis='y', alpha=0.3)
        for b, m in zip(bars, a_grp['mean']):
            ax_a.text(b.get_x() + b.get_width()/2, m + 0.03, f"{m*100:.1f}%", ha='center', fontsize=9)

        # RT
        ax_r = axes[1, col_idx]
        r_grp = crit_rt.groupby(flag_col)['rt_s'].agg(['mean', 'std', 'size']).reset_index()
        r_grp['se'] = r_grp['std'] / np.sqrt(r_grp['size'])
        bars = ax_r.bar([0, 1], r_grp['mean'], yerr=r_grp['se'], capsize=5, color=col, alpha=0.85, edgecolor='black', width=0.5)
        ax_r.set_xticks([0, 1])
        ax_r.set_xticklabels(x_names)
        ax_r.set_ylabel("Mean RT (s)")
        ax_r.set_ylim(0, r_grp['mean'].max() * 1.3)
        ax_r.set_title(f"RT by {title}", fontweight='bold')
        ax_r.grid(axis='y', alpha=0.3)
        for b, m in zip(bars, r_grp['mean']):
            ax_r.text(b.get_x() + b.get_width()/2, m + 0.02, f"{m:.3f}s", ha='center', fontsize=9)

    fig.suptitle("Main Effects of Trigger Hardware Lines (ch160, ch161, ch162)", fontsize=13, fontweight='bold', y=1.01)
    fig.tight_layout()
    path = os.path.join(FIGURES_DIR, out_filename)
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved: {out_filename}")


def plot_all_12_conditions_matrix(df, rt_df, out_filename):
    """
    Comprehensive breakdown of all 12 conditions with pairwise FDR significance matrix.
    """
    conds = [c for c in COND_ORDER_12 if c in df['Condition'].unique()]
    n = len(conds)

    a_sum = acc_summary(df, ['Condition'])
    r_sum = rt_summary(rt_df, ['Condition'])

    means_acc = [float(a_sum.loc[a_sum['Condition']==c, 'mean_acc'].iloc[0]) for c in conds]
    ses_acc   = [float(a_sum.loc[a_sum['Condition']==c, 'se_acc'].iloc[0]) for c in conds]
    means_rt  = [float(r_sum.loc[r_sum['Condition']==c, 'mean_rt'].iloc[0]) for c in conds]
    ses_rt    = [float(r_sum.loc[r_sum['Condition']==c, 'se_rt'].iloc[0]) for c in conds]

    pw_acc = pairwise_fdr(df, 'Condition', 'Accurate')
    pw_rt  = pairwise_fdr(rt_df, 'Condition', 'rt_s')

    def build_pmat(pw_df):
        idx = {c: i for i, c in enumerate(conds)}
        pmat = np.ones((n, n))
        np.fill_diagonal(pmat, np.nan)
        for _, row in pw_df.iterrows():
            i, j = idx.get(row['g1']), idx.get(row['g2'])
            if i is not None and j is not None:
                pmat[i, j] = pmat[j, i] = float(row['p_adj'])
        return pmat

    pmat_acc = build_pmat(pw_acc)
    pmat_rt  = build_pmat(pw_rt)

    fig = plt.figure(figsize=(22, 19))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.1, 1.8], hspace=0.50, wspace=0.35)
    ax_ab = fig.add_subplot(gs[0, 0])
    ax_rb = fig.add_subplot(gs[0, 1])
    ax_am = fig.add_subplot(gs[1, 0])
    ax_rm = fig.add_subplot(gs[1, 1])

    x = np.arange(n)
    xlabels = [COND_LABELS_12.get(c, c) for c in conds]
    bar_cols = [COND_COLORS.get(c, '#666') for c in conds]

    # Bar charts
    for ax, means, ses, title, ylabel, is_pct in [
        (ax_ab, means_acc, ses_acc, f"Accuracy by Condition ({n} Conditions)", "Accuracy", True),
        (ax_rb, means_rt,  ses_rt,  "Reaction Time by Condition (0.1–2.0 s)", "Mean RT (s)", False),
    ]:
        ax.bar(x, means, yerr=ses, capsize=4, color=bar_cols, alpha=0.88, edgecolor='black', width=0.65)
        for xi, (m, se) in enumerate(zip(means, ses)):
            txt = f"{m*100:.1f}%" if is_pct else f"{m:.3f}s"
            ax.text(xi, m + se + 0.005, txt, ha='center', va='bottom', fontsize=7.5)
        ax.set_xticks(x)
        ax.set_xticklabels(xlabels, fontsize=7.5, rotation=25, ha='right')
        ax.set_ylabel(ylabel, fontsize=10)
        ax.set_title(title, fontweight='bold', fontsize=11)
        ax.grid(axis='y', alpha=0.3)
        if is_pct:
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v*100:.0f}%"))
            ax.set_ylim(0, 1.18)

    # Matrix drawing
    def cell_color(p):
        if p < 0.001: return "#C62828"
        if p < 0.01:  return "#F57C00"
        if p < 0.05:  return "#F9A825"
        return "#EAEAEA"

    def draw_matrix(ax, pmat, title):
        short = [c.replace("_", " ") for c in conds]
        for i in range(n):
            for j in range(n):
                if j > i:
                    ax.add_patch(plt.Rectangle((j-0.5, i-0.5), 1, 1, facecolor='white', edgecolor='#ddd', linewidth=0.3))
                elif j == i:
                    ax.add_patch(plt.Rectangle((j-0.5, i-0.5), 1, 1, facecolor='#f0f0f0', edgecolor='#ddd', linewidth=0.3))
                    ax.text(j, i, str(i+1), ha='center', va='center', fontsize=7, color='#666')
                else:
                    p = pmat[i, j]
                    star = p_star(p)
                    fc = cell_color(p)
                    tc = 'white' if p < 0.01 else '#222'
                    ax.add_patch(plt.Rectangle((j-0.5, i-0.5), 1, 1, facecolor=fc, edgecolor='#ddd', linewidth=0.3))
                    ax.text(j, i, star, ha='center', va='center', fontsize=8, fontweight='bold' if star!='ns' else 'normal', color=tc)

        ax.set_xlim(-0.5, n - 0.5)
        ax.set_ylim(n - 0.5, -0.5)
        ax.set_xticks(range(n))
        ax.set_xticklabels(short, rotation=35, ha='right', fontsize=7.5)
        ax.set_yticks(range(n))
        ax.set_yticklabels(short, fontsize=7.5)
        ax.set_aspect('equal')
        ax.tick_params(length=0)
        ax.set_title(title, fontweight='bold', fontsize=11, pad=10)
        ax.spines[:].set_visible(False)

        leg_elems = [
            mpatches.Patch(facecolor="#C62828", edgecolor="none", label="*** p < .001"),
            mpatches.Patch(facecolor="#F57C00", edgecolor="none", label="**   p < .01"),
            mpatches.Patch(facecolor="#F9A825", edgecolor="none", label="*     p < .05"),
            mpatches.Patch(facecolor="#EAEAEA", edgecolor="#aaa", label="ns   p ≥ .05"),
        ]
        ax.legend(handles=leg_elems, fontsize=7.5, loc="lower right", framealpha=0.95, bbox_to_anchor=(1.0, 0.0))

    draw_matrix(ax_am, pmat_acc, "Pairwise Accuracy Comparisons (Welch t-tests, FDR–BH)")
    draw_matrix(ax_rm, pmat_rt,  "Pairwise RT Comparisons (Welch t-tests, FDR–BH)")

    fig.suptitle(f"All {n} Stimulus Conditions — Accuracy & RT with Pairwise Significance Matrices",
                 fontsize=12, fontweight='bold', y=1.01)

    path = os.path.join(FIGURES_DIR, out_filename)
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved: {out_filename}")


def plot_response_summary_table(df, out_filename):
    """Heatmap table showing Hit, Miss, CR, and FA rates per condition."""
    conds = [c for c in COND_ORDER_12 if c in df['Condition'].unique()]
    rates = {rt: [] for rt in ['Hit', 'Miss', 'Correct Reject', 'False Alarm']}

    for c in conds:
        sub = df[df['Condition'] == c]
        tot = len(sub)
        for rt in rates:
            cnt = (sub['Response_Type'] == rt).sum()
            rates[rt].append(cnt / tot if tot > 0 else 0)

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    for ax, (rt, col) in zip(axes.flat, [('Hit', '#4CAF50'), ('Miss', '#F44336'),
                                         ('Correct Reject', '#2196F3'), ('False Alarm', '#FF9800')]):
        vals = rates[rt]
        bars = ax.barh(range(len(conds)), vals, color=col, alpha=0.85, edgecolor='black')
        ax.set_yticks(range(len(conds)))
        ax.set_yticklabels([c.replace('_', ' ') for c in conds], fontsize=8.5)
        ax.set_xlabel("Rate")
        ax.set_title(f"{rt} Rate across {len(conds)} Conditions", fontweight='bold')
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v*100:.0f}%"))
        ax.grid(axis='x', alpha=0.3)
        for b, v in zip(bars, vals):
            ax.text(v + 0.01, b.get_y() + b.get_height()/2, f"{v*100:.1f}%", va='center', fontsize=7.5)

    fig.suptitle("Signal Detection Theory (SDT) Response Rates by Condition", fontsize=12, fontweight='bold', y=1.01)
    fig.tight_layout()
    path = os.path.join(FIGURES_DIR, out_filename)
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved: {out_filename}")


# ── 4. Main Execution ─────────────────────────────────────────────────────────
def main():
    print("=" * 70)
    print("  Morpho-Syntax Behavioral Analysis (13 Conditions & Triggers)")
    print("=" * 70)

    # 1. Load data
    print("\n[1/5] Loading stimuli and behavioral data …")
    df = load_all_behavioral_data()
    df = classify_responses(df)
    df_rt = filter_rt(df)

    n_subs = df['participant_id'].nunique() if 'participant_id' in df.columns else 1
    n_trials = len(df)
    n_rt = len(df_rt)
    print(f"  Participants  : {n_subs}")
    print(f"  Total trials  : {n_trials:,}")
    print(f"  Trials in RT  : {n_rt:,} ({100*n_rt/n_trials:.1f}%)")
    print(f"  Conditions represented : {df['Condition'].nunique()} / {len(COND_ORDER_12)}")

    # 2. Save trial-level processed CSV
    trial_csv = os.path.join(ANALYSIS_DIR, "trial_level_data.csv")
    df.to_csv(trial_csv, index=False)
    print(f"\n  Trial-level CSV saved → {trial_csv}")

    # 3. Factorial ANOVAs
    print("\n[2/5] Running ANOVAs on Critical Conditions …")
    acc_anova, rt_anova = plot_2x2x2_factorial(df, df_rt, "fig01_2x2x2_factorial_accuracy_rt.png")
    if not acc_anova.empty:
        acc_anova.to_csv(os.path.join(ANALYSIS_DIR, "anova_accuracy_2x2x2.csv"))
    if not rt_anova.empty:
        rt_anova.to_csv(os.path.join(ANALYSIS_DIR, "anova_rt_2x2x2.csv"))
    print("  2×2×2 ANOVA tables saved.")

    # 4. Summary tables
    print("\n[3/5] Saving condition summary tables …")
    acc_sum = acc_summary(df, ['Condition'])
    rt_sum  = rt_summary(df_rt, ['Condition'])
    summary = pd.merge(acc_sum, rt_sum, on='Condition', suffixes=('_acc', '_rt'))
    summary.to_csv(os.path.join(ANALYSIS_DIR, "summary_12_conditions.csv"), index=False)

    sdt_sum = df.groupby(['Condition', 'Response_Type']).size().unstack(fill_value=0)
    sdt_sum.to_csv(os.path.join(ANALYSIS_DIR, "sdt_response_summary.csv"))
    print("  Summary CSVs saved.")

    # 5. Figures
    print("\n[4/5] Generating figures …")
    # Fig 2: Trigger lines breakdown
    plot_trigger_channels_breakdown(df, df_rt, "fig02_trigger_channels_breakdown.png")
    # Fig 3: All 12 conditions with pairwise FDR significance matrix
    plot_all_12_conditions_matrix(df, df_rt, "fig03_all_12_conditions_with_sig_matrix.png")
    # Fig 4: SDT Summary Table
    plot_response_summary_table(df, "fig04_sdt_summary_table.png")

    print("\n[5/5] Done.")
    print(f"\n  Figures directory → {FIGURES_DIR}")
    print(f"  Analysis directory → {ANALYSIS_DIR}")


if __name__ == "__main__":
    main()
