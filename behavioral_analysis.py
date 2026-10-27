#!/usr/bin/env python3
"""
behavioral_analysis.py
======================
Reads raw PCIbex behavioral CSVs, excludes flagged participants, and produces
figures parallel to response_analysis.ipynb — adapted for this study's design:

  NEW vs. notebook design
  -----------------------
  • 3 STRUC conditions  : Grammatical | Reversed | Anomalous
  • 8 Cond_IDs          : a-c (Gram × PW 0-2)  d,H (Rev × PW 0, real/anom noun)
                          e,f (Rev × PW 1,2)    G (Anomalous × PW 0 only)
  • Accuracy            : string comparison of Stimulus1 vs Stimulus2 (not Match col)
  • Single study        : Study 2_0 and 2_1 treated as one combined dataset
  • RT filter           : 0.1 – 2.0 s  (same heuristic as reference notebook)

Figures saved to: <repo>/Behavioral data/figures/
CSVs   saved to : <repo>/Behavioral data/analysis/

Excluded participants
---------------------
  Bad      (accuracy < 50 %) : 60fdb73b…, 671bbaf1…, 69cd760c…
  Partial  (< 400 trials)    : 67ac2151… (274), 66541402… (191)
  Risky    (no Prolific ID)   : "undefined"
"""

# ── 0. Imports & configuration ────────────────────────────────────────────────
import csv
import glob
import os
import statistics
import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import statsmodels.formula.api as smf
import statsmodels.api as sm
from statsmodels.stats.multicomp import pairwise_tukeyhsd
from statsmodels.stats.multitest import multipletests
from itertools import combinations
from collections import defaultdict

warnings.filterwarnings("ignore")

# ── Paths ─────────────────────────────────────────────────────────────────────
HERE       = os.path.dirname(os.path.abspath(__file__))
DATA_DIR   = os.path.join(HERE, "..", "Behavioral data")
FIGURES_DIR= os.path.join(DATA_DIR, "figures")
ANALYSIS_DIR=os.path.join(DATA_DIR, "analysis")
os.makedirs(FIGURES_DIR, exist_ok=True)
os.makedirs(ANALYSIS_DIR, exist_ok=True)

# ── Exclusions ─────────────────────────────────────────────────────────────────
EXCLUDED_IDS = {
    # Bad accuracy (< 50 %)
    "60fdb73b85f276ed91d84eb9",   # 16.2 %
    "671bbaf1bec15d847b871b9b",   # 34.8 %
    "69cd760c0c7a99a3364878d6",   # 44.8 %
    # Partial completions
    "67ac2151e5b37e0b91a5af0e",   # 274/400 trials
    "66541402baeab50a7ef62b24",   # 191/400 trials
    # Risky – no Prolific ID
    "undefined",
}

# ── Constants ──────────────────────────────────────────────────────────────────
RT_LOW_S  = 0.10   # seconds
RT_HIGH_S = 2.00   # seconds (same heuristic as reference notebook)

META_COLS = [
    "SET", "Cond_ID", "STRUC", "Pseudowords",
    "NOUN", "ADJECTIVE", "PseudoNOUN", "AnomalousNOUN",
    "PseudoADJ", "AnomalousADJ", "STRUCTURE", "Stimulus1", "Stimulus2", "Match",
]

STRUC_ORDER  = ["Grammatical", "Reversed", "Anomalous"]
PW_ORDER     = [0, 1, 2]
COND_ORDER   = ["a", "b", "c", "d", "H", "e", "f", "G"]
COND_LABELS  = {
    "a": "Gram PW=0",  "b": "Gram PW=1",  "c": "Gram PW=2",
    "d": "Rev PW=0\n(real noun)",
    "H": "Rev PW=0\n(anom noun)",
    "e": "Rev PW=1",   "f": "Rev PW=2",
    "G": "Anom PW=0",
}

# Colour scheme
STRUC_COLORS = {"Grammatical": "#4878CF", "Reversed": "#E87A2D", "Anomalous": "#6ACC65"}
SDT_COLORS   = {"Hit": "#4CAF50", "Miss": "#F44336",
                "Correct Reject": "#2196F3", "False Alarm": "#FF9800"}


# ── 1. Parse raw CSVs → trial-level DataFrame ─────────────────────────────────
def parse_all_csvs(data_dir):
    """Return a trial-level DataFrame with RT and accuracy columns."""
    rows = []

    for filepath in sorted(glob.glob(os.path.join(data_dir, "*.csv"))):
        basename = os.path.basename(filepath)
        study = "Study 2_0" if basename.startswith("2_0") else "Study 2_1"

        # Two-pass: first collect target onsets and prolific IDs, then key presses
        targets   = {}   # (ip_hash, order) -> onset_ms
        prolific  = {}   # ip_hash -> prolific_id

        with open(filepath, newline="", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                row = next(csv.reader([line]))
                if len(row) < 12:
                    continue
                ip = row[1]

                # Prolific ID rows (Label = prolificid, col 13 = ID value)
                if row[5] == "prolificid" and len(row) > 13:
                    pid = row[13].strip()
                    if pid not in ("NULL", "ID", ""):
                        prolific[ip] = pid

                if len(row) < 27 or row[5] != "trial":
                    continue

                # Target onset row
                if row[7] == "Text" and row[8] == "Target" and row[9] == "Print":
                    try:
                        targets[(ip, row[3])] = int(row[11])
                    except ValueError:
                        pass

        # Second pass: key press rows
        with open(filepath, newline="", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                row = next(csv.reader([line]))
                if len(row) < 27 or row[5] != "trial":
                    continue
                if row[7] != "Key" or row[8] != "answerTarget" or row[9] != "PressedKey":
                    continue

                ip    = row[1]
                order = row[3]
                pid   = prolific.get(ip, "UNKNOWN")
                if pid in EXCLUDED_IDS:
                    continue

                meta = dict(zip(META_COLS, row[13:13 + len(META_COLS)]))
                s1   = meta.get("Stimulus1", "").strip()
                s2   = meta.get("Stimulus2", "").strip()
                key  = row[10].strip()

                # Ground truth: string comparison  (same→key '2', diff→key '1')
                expected    = "2" if s1 == s2 else "1"
                is_correct  = (key == expected)

                # RT
                key_time  = int(row[11])
                t_onset   = targets.get((ip, order))
                rt_ms     = (key_time - t_onset) if t_onset is not None else None
                rt_s      = (rt_ms / 1000) if rt_ms is not None else None

                try:
                    pw = int(meta.get("Pseudowords", ""))
                except ValueError:
                    pw = None

                rows.append({
                    "prolific_id":  pid,
                    "study":        study,
                    "ip_hash":      ip,
                    "order":        int(order),
                    "STRUC":        meta.get("STRUC", ""),
                    "Pseudowords":  pw,
                    "Cond_ID":      meta.get("Cond_ID", ""),
                    "STRUCTURE":    meta.get("STRUCTURE", ""),
                    "Stimulus1":    s1,
                    "Stimulus2":    s2,
                    "Match":        meta.get("Match", ""),
                    "key":          key,
                    "expected":     expected,
                    "is_correct":   is_correct,
                    "rt_ms":        rt_ms,
                    "rt_s":         rt_s,
                })

    df = pd.DataFrame(rows)
    df["Pseudowords"] = pd.to_numeric(df["Pseudowords"], errors="coerce")
    return df


def classify_responses(df):
    """Add SDT Response_Type column: Hit / Miss / Correct Reject / False Alarm."""
    same  = df["Stimulus1"] == df["Stimulus2"]
    key2  = df["key"] == "2"
    key1  = df["key"] == "1"
    df = df.copy()
    df["Response_Type"] = "Unclassified"
    df.loc[same  & key2, "Response_Type"] = "Hit"
    df.loc[same  & key1, "Response_Type"] = "Miss"
    df.loc[~same & key1, "Response_Type"] = "Correct Reject"
    df.loc[~same & key2, "Response_Type"] = "False Alarm"
    df["Accurate"] = df["Response_Type"].isin(["Hit", "Correct Reject"]).astype(int)
    return df


# ── 2. Stat helpers ────────────────────────────────────────────────────────────
def filter_rt(df):
    """Return copy with rt_s filtered to [RT_LOW_S, RT_HIGH_S]."""
    return df[df["rt_s"].notna() & df["rt_s"].between(RT_LOW_S, RT_HIGH_S)].copy()


def acc_summary(df, group_cols):
    g = df.groupby(group_cols)
    out = g["Accurate"].agg(
        mean_acc="mean", n_trials="size"
    ).reset_index()
    out["se_acc"] = np.sqrt(
        out["mean_acc"] * (1 - out["mean_acc"]) / out["n_trials"].clip(lower=1)
    )
    return out


def rt_summary(df_rt, group_cols):
    g = df_rt.groupby(group_cols)
    out = g["rt_s"].agg(mean_rt="mean", std_rt="std", n_trials="size").reset_index()
    out["se_rt"] = out["std_rt"] / np.sqrt(out["n_trials"].clip(lower=1))
    return out


def run_anova_2way(df, rt_df, formula_acc, formula_rt):
    """Type-II ANOVA for accuracy (OLS on Accurate) and RT."""
    try:
        acc_model = smf.ols(formula_acc, data=df).fit()
        acc_anova = sm.stats.anova_lm(acc_model, typ=2)
    except Exception:
        acc_anova = pd.DataFrame()
    try:
        rt_model = smf.ols(formula_rt, data=rt_df).fit()
        rt_anova = sm.stats.anova_lm(rt_model, typ=2)
    except Exception:
        rt_anova = pd.DataFrame()
    return acc_anova, rt_anova


def get_pvals(anova_df, terms):
    out = {}
    for t in terms:
        if not anova_df.empty and t in anova_df.index and "PR(>F)" in anova_df.columns:
            out[t] = float(anova_df.loc[t, "PR(>F)"])
        else:
            out[t] = np.nan
    return out


def p_star(p):
    if p < 0.001: return "***"
    if p < 0.01:  return "**"
    if p < 0.05:  return "*"
    return ""


def pairwise_fdr(df, group_col, value_col):
    """Welch t-tests between all group pairs, BH-corrected."""
    groups = sorted(df[group_col].dropna().unique())
    pairs = list(combinations(groups, 2))
    records = []
    for g1, g2 in pairs:
        a = df.loc[df[group_col] == g1, value_col].dropna().values
        b = df.loc[df[group_col] == g2, value_col].dropna().values
        if len(a) < 2 or len(b) < 2:
            continue
        from scipy.stats import ttest_ind
        _, p = ttest_ind(a, b, equal_var=False)
        records.append({"g1": g1, "g2": g2, "p_raw": p})
    if not records:
        return pd.DataFrame(columns=["g1","g2","p_raw","p_adj","reject"])
    pw = pd.DataFrame(records)
    reject, padj, _, _ = multipletests(pw["p_raw"], method="fdr_bh")
    pw["p_adj"] = padj
    pw["reject"] = reject
    return pw


def add_sig_brackets(ax, pw_df, pos_dict,
                     base_h=0.025, step_h=0.035,
                     text_off=0.005, lw=0.8, cap=0.006):
    """Draw star brackets for significant pairs (FDR-corrected)."""
    if pw_df.empty:
        return None
    sig = pw_df[pw_df["reject"] == True].sort_values("p_adj")
    layer, max_y = 0, None
    for _, r in sig.iterrows():
        star = p_star(r["p_adj"])
        if not star:
            continue
        p1 = pos_dict.get(r["g1"])
        p2 = pos_dict.get(r["g2"])
        if p1 is None or p2 is None:
            continue
        x1, y1 = p1; x2, y2 = p2
        y = max(y1, y2) + base_h + layer * step_h
        ax.plot([x1,x1,x2,x2], [y-cap, y, y, y-cap], color="black", lw=lw)
        ax.text((x1+x2)/2, y+text_off, star, ha="center", va="bottom", fontsize=8)
        max_y = (y+text_off) if max_y is None else max(max_y, y+text_off)
        layer += 1
    return max_y


# ── 3. Plotting functions ──────────────────────────────────────────────────────
def _bar_group_positions(groups, pw_vals, width=0.28, group_gap=1.3):
    """Return x positions and tick positions for a grouped bar chart."""
    x_ticks = np.arange(len(pw_vals)) * group_gap
    offsets  = {g: (i - (len(groups)-1)/2) * width for i, g in enumerate(groups)}
    return x_ticks, offsets


def plot_accuracy_rt_2x3(df, rt_df, struc_list, title_prefix, out_filename,
                          anova_acc=None, anova_rt=None):
    """
    Grouped bar chart: accuracy (left) and RT (right) for STRUC × PW.
    struc_list controls which STRUC values appear (normally Grammatical + Reversed).
    """
    sub_acc = df[df["STRUC"].isin(struc_list)]
    sub_rt  = rt_df[rt_df["STRUC"].isin(struc_list)]
    a_sum   = acc_summary(sub_acc, ["STRUC", "Pseudowords"])
    r_sum   = rt_summary(sub_rt, ["STRUC", "Pseudowords"])

    pw_vals  = sorted(sub_acc["Pseudowords"].dropna().unique().astype(int))
    x_ticks, offsets = _bar_group_positions(struc_list, pw_vals)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 7))
    pos_acc, pos_rt = {}, {}

    for struc in struc_list:
        col = STRUC_COLORS.get(struc, "steelblue")
        off = offsets[struc]
        a_sub = a_sum[a_sum["STRUC"] == struc]
        r_sub = r_sum[r_sum["STRUC"] == struc]

        for ax, sub, key_m, key_se, pos_dict in [
            (ax1, a_sub, "mean_acc", "se_acc", pos_acc),
            (ax2, r_sub, "mean_rt",  "se_rt",  pos_rt),
        ]:
            means, ses, xs = [], [], []
            for j, pw in enumerate(pw_vals):
                row = sub[sub["Pseudowords"] == pw]
                if row.empty:
                    continue
                m  = float(row[key_m].iloc[0])
                se = float(row[key_se].iloc[0])
                x  = x_ticks[j] + off
                means.append(m); ses.append(se); xs.append(x)
                pos_dict[f"{struc}_pw{pw}"] = (x, m + se)

            bars = ax.bar(xs, means, width=0.26, yerr=ses, capsize=4,
                          color=col, alpha=0.85, edgecolor="black", label=struc)

    # Pairwise brackets – combine STRUC×PW into single condition label
    for ax, data, vcol, pdict, base_h in [
        (ax1, sub_acc, "Accurate",  pos_acc, 0.025),
        (ax2, sub_rt,  "rt_s",      pos_rt,  0.030),
    ]:
        data2 = data.copy()
        data2["cond"] = data2["STRUC"] + "_pw" + data2["Pseudowords"].astype(int).astype(str)
        pw_df = pairwise_fdr(data2, "cond", vcol)
        pw_df = pw_df.rename(columns={"g1":"g1","g2":"g2"})
        # remap names to match pos dict
        pw_df["g1_m"] = pw_df["g1"]
        pw_df["g2_m"] = pw_df["g2"]
        max_y = add_sig_brackets(ax,
            pw_df.rename(columns={"g1":"g1","g2":"g2"}),
            pdict, base_h=base_h)

    # Axes formatting
    ax1.set_title(f"{title_prefix} — Accuracy", fontsize=12, fontweight="bold")
    ax1.set_xlabel("Number of Pseudowords")
    ax1.set_ylabel("Accuracy")
    ax1.set_xticks(x_ticks); ax1.set_xticklabels(pw_vals)
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda y,_: f"{y*100:.0f}%"))
    ax1.set_ylim(0, min(1.25, ax1.get_ylim()[1] + 0.05))
    ax1.legend(); ax1.grid(axis="y", alpha=0.3)

    ax2.set_title(f"{title_prefix} — Reaction Time", fontsize=12, fontweight="bold")
    ax2.set_xlabel("Number of Pseudowords")
    ax2.set_ylabel("Mean RT (s)")
    ax2.set_xticks(x_ticks); ax2.set_xticklabels(pw_vals)
    ax2.set_ylim(0, ax2.get_ylim()[1] * 1.25)
    ax2.legend(); ax2.grid(axis="y", alpha=0.3)

    # ANOVA p-value annotations
    terms = ["C(STRUC)","C(Pseudowords)","C(STRUC):C(Pseudowords)"]
    short = {"C(STRUC)":"STRUC","C(Pseudowords)":"PW","C(STRUC):C(Pseudowords)":"STRUC×PW"}
    for ax, av in [(ax1, anova_acc),(ax2, anova_rt)]:
        if av is not None and not av.empty:
            pv = get_pvals(av, terms)
            txt = "  ".join(f"{short[t]}:{p_star(pv[t])} p={pv[t]:.3f}" for t in terms if t in pv)
            ax.set_xlabel(f"Pseudowords\n{txt}", fontsize=8)

    fig.suptitle(f"{title_prefix}\n(RT filtered {RT_LOW_S}–{RT_HIGH_S} s; "
                 f"n={len(df['prolific_id'].unique())} participants)",
                 fontsize=11, y=1.01)
    fig.tight_layout()
    path = os.path.join(FIGURES_DIR, out_filename)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_filename}")


def plot_3struc_comparison(df, rt_df, title_prefix, out_filename):
    """
    Side-by-side bar charts comparing all 3 STRUC conditions.
    Accuracy and RT are averaged across available PW levels per STRUC.
    """
    a_sum = acc_summary(df, ["STRUC"])
    r_sum = rt_summary(rt_df, ["STRUC"])

    strucs = [s for s in STRUC_ORDER if s in a_sum["STRUC"].values]
    x = np.arange(len(strucs))
    cols = [STRUC_COLORS[s] for s in strucs]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))

    for ax, sdf, ycol, secol, ylabel, fmt in [
        (ax1, a_sum, "mean_acc", "se_acc", "Accuracy", lambda v: f"{v*100:.1f}%"),
        (ax2, r_sum, "mean_rt",  "se_rt",  "Mean RT (s)", lambda v: f"{v:.3f}s"),
    ]:
        means = [float(sdf.loc[sdf["STRUC"]==s, ycol].iloc[0]) for s in strucs]
        ses   = [float(sdf.loc[sdf["STRUC"]==s, secol].iloc[0]) for s in strucs]
        bars  = ax.bar(x, means, yerr=ses, capsize=5, color=cols, alpha=0.85,
                       edgecolor="black", width=0.55)
        for bar, m, se in zip(bars, means, ses):
            ax.text(bar.get_x()+bar.get_width()/2, m+se+0.005,
                    fmt(m), ha="center", va="bottom", fontsize=9)
        ax.set_xticks(x)
        ax.set_xticklabels(strucs, rotation=10)
        ax.set_ylabel(ylabel)
        ax.grid(axis="y", alpha=0.3)

    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda y,_: f"{y*100:.0f}%"))
    ax1.set_title(f"{title_prefix} — Accuracy by STRUC", fontweight="bold")
    ax2.set_title(f"{title_prefix} — RT by STRUC", fontweight="bold")

    # Pairwise significance across STRUCs
    for ax, data, vcol, base_h in [(ax1,df,"Accurate",0.03),(ax2,rt_df,"rt_s",0.04)]:
        pdict = {}
        sdf2  = acc_summary(df,["STRUC"]) if vcol=="Accurate" else r_sum
        for i, s in enumerate(strucs):
            row = sdf2[sdf2["STRUC"]==s]
            if row.empty: continue
            ym = float(row["mean_acc" if vcol=="Accurate" else "mean_rt"].iloc[0])
            ye = float(row["se_acc"   if vcol=="Accurate" else "se_rt"  ].iloc[0])
            pdict[s] = (float(i), ym+ye)
        pw_df = pairwise_fdr(data, "STRUC", vcol)
        pw_df = pw_df.rename(columns={"g1":"g1","g2":"g2"})
        add_sig_brackets(ax,
            pw_df.rename(columns={"g1":"g1","g2":"g2"}),
            pdict, base_h=base_h)
        # Rescale y
        top = ax.get_ylim()[1]
        ax.set_ylim(0, top * 1.3)

    fig.suptitle(f"{title_prefix} — All 3 STRUC Conditions\n"
                 f"(Anomalous = PW 0 only; * p<.05  ** p<.01  *** p<.001)",
                 fontsize=11, y=1.01)
    fig.tight_layout()
    path = os.path.join(FIGURES_DIR, out_filename)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_filename}")


def plot_cond_id_with_sig_matrix(df, rt_df, out_filename):
    """
    Expanded condition breakdown: bars (top) + pairwise significance matrix (bottom)
    for both accuracy and RT across all 8 Cond_IDs.

    Layout (2 × 2 using GridSpec):
      [0,0] Accuracy bars         [0,1] RT bars
      [1,0] Accuracy sig matrix   [1,1] RT sig matrix

    Matrix cells (lower triangle only):
      Dark red  = *** (p < .001)   Orange = ** (p < .01)
      Amber     = *   (p < .05)    Light gray = ns
    FDR(BH) correction applied across all 28 pairwise tests per outcome.
    """
    conds = [c for c in COND_ORDER if c in df["Cond_ID"].values]
    n = len(conds)

    # ── Summaries ─────────────────────────────────────────────────────────────
    a_sum = acc_summary(df[df["Cond_ID"].isin(conds)],    ["Cond_ID", "STRUC"])
    r_sum = rt_summary(rt_df[rt_df["Cond_ID"].isin(conds)], ["Cond_ID", "STRUC"])

    bar_cols = [STRUC_COLORS.get(
        a_sum.loc[a_sum["Cond_ID"]==c, "STRUC"].iloc[0]
        if not a_sum.loc[a_sum["Cond_ID"]==c].empty else "Grammatical", "#888")
        for c in conds]

    means_acc = [float(a_sum.loc[a_sum["Cond_ID"]==c, "mean_acc"].iloc[0]) for c in conds]
    ses_acc   = [float(a_sum.loc[a_sum["Cond_ID"]==c, "se_acc"].iloc[0])   for c in conds]
    means_rt  = [float(r_sum.loc[r_sum["Cond_ID"]==c, "mean_rt"].iloc[0])  for c in conds]
    ses_rt    = [float(r_sum.loc[r_sum["Cond_ID"]==c, "se_rt"].iloc[0])    for c in conds]

    # ── Pairwise FDR tests ────────────────────────────────────────────────────
    pw_acc = pairwise_fdr(df,    "Cond_ID", "Accurate")
    pw_rt  = pairwise_fdr(rt_df, "Cond_ID", "rt_s")

    def build_pmat(pw_df):
        idx  = {c: i for i, c in enumerate(conds)}
        pmat = np.ones((n, n))
        np.fill_diagonal(pmat, np.nan)
        for _, row in pw_df.iterrows():
            i, j = idx.get(row["g1"]), idx.get(row["g2"])
            if i is not None and j is not None:
                pmat[i, j] = pmat[j, i] = float(row["p_adj"])
        return pmat

    pmat_acc = build_pmat(pw_acc)
    pmat_rt  = build_pmat(pw_rt)

    # ── Figure layout ─────────────────────────────────────────────────────────
    fig = plt.figure(figsize=(20, 18))
    gs  = fig.add_gridspec(2, 2, height_ratios=[1.1, 1.8],
                           hspace=0.55, wspace=0.38)
    ax_ab = fig.add_subplot(gs[0, 0])   # accuracy bars
    ax_rb = fig.add_subplot(gs[0, 1])   # RT bars
    ax_am = fig.add_subplot(gs[1, 0])   # accuracy matrix
    ax_rm = fig.add_subplot(gs[1, 1])   # RT matrix

    x       = np.arange(n)
    xlabels = [COND_LABELS[c] for c in conds]

    # ── Bar charts ────────────────────────────────────────────────────────────
    for ax, means, ses, title, ylabel, is_pct in [
        (ax_ab, means_acc, ses_acc, "Accuracy by Condition",       "Accuracy",    True),
        (ax_rb, means_rt,  ses_rt,  "Mean RT by Condition (0.1–2.0 s filtered)", "Mean RT (s)", False),
    ]:
        ax.bar(x, means, yerr=ses, capsize=5, color=bar_cols,
               alpha=0.87, edgecolor="black", linewidth=0.7, width=0.65)
        for xi, (m, se) in enumerate(zip(means, ses)):
            label = f"{m*100:.1f}%" if is_pct else f"{m:.3f}s"
            ax.text(xi, m + se + (0.004 if is_pct else 0.006),
                    label, ha="center", va="bottom", fontsize=7.5)
        ax.set_xticks(x)
        ax.set_xticklabels(xlabels, fontsize=8.5, rotation=20, ha="right")
        ax.set_ylabel(ylabel, fontsize=10)
        ax.set_title(title, fontweight="bold", fontsize=11, pad=8)
        ax.grid(axis="y", alpha=0.3)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        if is_pct:
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v*100:.0f}%"))
            ax.set_ylim(0, max(means_acc) + max(ses_acc) + 0.12)

    # STRUC-colour legend on accuracy bars
    struc_patches = [mpatches.Patch(color=STRUC_COLORS[s], label=s) for s in STRUC_ORDER]
    ax_ab.legend(handles=struc_patches, fontsize=8.5, loc="lower left",
                 framealpha=0.9, edgecolor="#ccc")

    # ── Significance matrices ──────────────────────────────────────────────────
    def cell_color(p):
        if   p < 0.001: return "#C62828"   # dark red   ***
        elif p < 0.01:  return "#F57C00"   # orange     **
        elif p < 0.05:  return "#F9A825"   # amber      *
        else:           return "#E8E8E8"   # light gray  ns

    def text_color(p):
        return "white" if p < 0.01 else "#333333"

    def draw_matrix(ax, pmat, title):
        short = [COND_LABELS[c].replace("\n", " ") for c in conds]

        for i in range(n):
            for j in range(n):
                if j > i:
                    # upper triangle — blank white
                    ax.add_patch(plt.Rectangle(
                        (j - 0.5, i - 0.5), 1, 1,
                        facecolor="white", edgecolor="#d5d5d5", linewidth=0.4, zorder=1))
                elif j == i:
                    # diagonal — label the condition
                    ax.add_patch(plt.Rectangle(
                        (j - 0.5, i - 0.5), 1, 1,
                        facecolor="#F5F5F5", edgecolor="#d5d5d5", linewidth=0.4, zorder=1))
                    ax.text(j, i, short[i], ha="center", va="center",
                            fontsize=7, color="#555555", style="italic", zorder=2)
                else:
                    # lower triangle — significance cell
                    p  = pmat[i, j]
                    fc = cell_color(p)
                    tc = text_color(p)
                    star = p_star(p) if p < 0.05 else "ns"
                    ax.add_patch(plt.Rectangle(
                        (j - 0.5, i - 0.5), 1, 1,
                        facecolor=fc, edgecolor="#d5d5d5", linewidth=0.4, zorder=1))
                    ax.text(j, i, star, ha="center", va="center",
                            fontsize=9, fontweight="bold" if star != "ns" else "normal",
                            color=tc, zorder=2)

        ax.set_xlim(-0.5, n - 0.5)
        ax.set_ylim(n - 0.5, -0.5)          # y=0 at top so rows read left-to-right
        ax.set_xticks(range(n))
        ax.set_xticklabels(short, rotation=45, ha="right", fontsize=8.5)
        ax.set_yticks(range(n))
        ax.set_yticklabels(short, fontsize=8.5)
        ax.set_aspect("equal")
        ax.tick_params(length=0)
        ax.set_title(title, fontweight="bold", fontsize=11, pad=10)
        ax.spines[:].set_visible(False)

        # Legend
        leg_elems = [
            mpatches.Patch(facecolor="#C62828", edgecolor="none", label="*** p < .001"),
            mpatches.Patch(facecolor="#F57C00", edgecolor="none", label="**   p < .01"),
            mpatches.Patch(facecolor="#F9A825", edgecolor="none", label="*     p < .05"),
            mpatches.Patch(facecolor="#E8E8E8", edgecolor="#aaa", label="ns   p ≥ .05"),
        ]
        ax.legend(handles=leg_elems, fontsize=8, loc="lower right",
                  framealpha=0.95, edgecolor="#ccc",
                  bbox_to_anchor=(1.0, 0.0), borderaxespad=0.5)

    draw_matrix(ax_am, pmat_acc,
                "Pairwise Accuracy Comparisons\n(Welch t-tests, FDR–BH corrected)")
    draw_matrix(ax_rm, pmat_rt,
                "Pairwise RT Comparisons\n(Welch t-tests, FDR–BH corrected)")

    fig.suptitle(
        "All 8 Conditions — Accuracy & RT with Pairwise Significance\n"
        "Conditions:  a–c = Grammatical (PW 0–2)  ·  d = Reversed/Real noun (PW 0)  "
        "·  H = Reversed/Anomalous noun (PW 0)  ·  e–f = Reversed (PW 1–2)  ·  G = Anomalous (PW 0)",
        fontsize=11, fontweight="bold", y=1.01,
    )

    path = os.path.join(FIGURES_DIR, out_filename)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_filename}")


def plot_response_type_rate(df, resp_type, struc_list, title_prefix, out_filename):
    """
    Rate of one SDT response type across STRUC × PW,
    with FDR-corrected pairwise brackets (matching notebook Cell 13).
    """
    sub = df[df["STRUC"].isin(struc_list)].copy()
    sub["is_resp"] = (sub["Response_Type"] == resp_type).astype(int)
    sub["cond"]    = sub["STRUC"] + "_pw" + sub["Pseudowords"].astype(int).astype(str)

    pw_vals   = sorted(sub["Pseudowords"].dropna().astype(int).unique())
    x_ticks, offsets = _bar_group_positions(struc_list, pw_vals)

    a_sum = sub.groupby(["STRUC","Pseudowords"]).agg(
        mean_rate=("is_resp","mean"), n=("is_resp","size")
    ).reset_index()
    a_sum["se"] = np.sqrt(a_sum["mean_rate"]*(1-a_sum["mean_rate"])/a_sum["n"].clip(lower=1))

    pw_fdr = pairwise_fdr(sub, "cond", "is_resp")

    fig, ax = plt.subplots(figsize=(10, 7))
    pos_dict = {}

    for struc in struc_list:
        col = STRUC_COLORS.get(struc,"steelblue")
        s   = a_sum[a_sum["STRUC"]==struc]
        xs, ms, ss = [], [], []
        for j, pw in enumerate(pw_vals):
            r = s[s["Pseudowords"]==pw]
            if r.empty: continue
            m, se = float(r["mean_rate"].iloc[0]), float(r["se"].iloc[0])
            xp = x_ticks[j]+offsets[struc]
            xs.append(xp); ms.append(m); ss.append(se)
            pos_dict[f"{struc}_pw{pw}"] = (xp, m+se)
        ax.bar(xs, ms, width=0.26, yerr=ss, capsize=4,
               color=col, alpha=0.85, edgecolor="black", label=struc)

    # Significance brackets
    max_y = add_sig_brackets(ax,
        pw_fdr.rename(columns={"g1":"g1","g2":"g2"}),
        pos_dict, base_h=0.018, step_h=0.028)
    ylim_top = (max_y + 0.04) if max_y else (a_sum["mean_rate"].max() + a_sum["se"].max() + 0.08)
    ax.set_ylim(0, min(1.05, ylim_top))

    ax.set_title(f"{title_prefix} — {resp_type} Rate (STRUC × PW)", fontweight="bold")
    ax.set_xlabel("Pseudowords")
    ax.set_ylabel(f"{resp_type} Rate")
    ax.set_xticks(x_ticks); ax.set_xticklabels(pw_vals)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y,_: f"{y*100:.0f}%"))
    ax.legend(); ax.grid(axis="y", alpha=0.3)
    n_sig = int(pw_fdr["reject"].sum()) if not pw_fdr.empty else 0
    ax.text(0.01, 0.01, f"FDR(BH) pairwise correction | Significant pairs: {n_sig}",
            transform=ax.transAxes, fontsize=8, va="bottom")
    fig.tight_layout()
    path = os.path.join(FIGURES_DIR, out_filename)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_filename}")


def plot_rt_distributions(df_rt, out_filename):
    """Violin + strip plots of RT distributions by STRUC."""
    import matplotlib.patches as mpatches

    strucs = [s for s in STRUC_ORDER if s in df_rt["STRUC"].values]
    fig, ax = plt.subplots(figsize=(10, 6))

    parts = ax.violinplot(
        [df_rt.loc[df_rt["STRUC"]==s, "rt_s"].dropna().values for s in strucs],
        positions=range(len(strucs)), showmedians=True, showextrema=True,
    )
    for pc, struc in zip(parts["bodies"], strucs):
        pc.set_facecolor(STRUC_COLORS.get(struc,"#aaa"))
        pc.set_alpha(0.7)
    parts["cmedians"].set_color("black")

    ax.set_xticks(range(len(strucs)))
    ax.set_xticklabels(strucs)
    ax.set_ylabel("RT (s)")
    ax.set_title("RT Distribution by STRUC — Overall\n"
                 f"(filtered {RT_LOW_S}–{RT_HIGH_S} s)", fontweight="bold")
    ax.grid(axis="y", alpha=0.3)

    # Annotate medians
    for i, struc in enumerate(strucs):
        med = df_rt.loc[df_rt["STRUC"]==struc,"rt_s"].median()
        ax.text(i, ax.get_ylim()[0]-0.04, f"med={med:.3f}s",
                ha="center", fontsize=8)

    fig.tight_layout()
    path = os.path.join(FIGURES_DIR, out_filename)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_filename}")


def plot_response_summary_table(df, out_filename):
    """Overview heatmap table of response type proportions per STRUC × PW."""
    pivot_data = {}
    strucs = [s for s in STRUC_ORDER if s in df["STRUC"].values]

    for rt_label in ["Hit", "Miss", "Correct Reject", "False Alarm"]:
        df2 = df.copy()
        df2["val"] = (df2["Response_Type"]==rt_label).astype(int)
        grp = df2.groupby(["STRUC","Pseudowords"])["val"].mean().reset_index()
        grp["cell"] = grp["STRUC"]+"_PW"+grp["Pseudowords"].astype(int).astype(str)
        pivot_data[rt_label] = grp.set_index("cell")["val"]

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    for ax, (rt_label, col) in zip(axes.flat,
            [("Hit","#4CAF50"),("Miss","#F44336"),
             ("Correct Reject","#2196F3"),("False Alarm","#FF9800")]):
        series = pivot_data[rt_label].sort_index()
        bars = ax.barh(range(len(series)), series.values, color=col, alpha=0.8, edgecolor="black")
        ax.set_yticks(range(len(series)))
        ax.set_yticklabels(series.index, fontsize=9)
        ax.set_xlabel("Proportion")
        ax.set_title(f"{rt_label} Rate per Cell", fontweight="bold")
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v,_: f"{v*100:.0f}%"))
        ax.grid(axis="x", alpha=0.3)
        for bar, val in zip(bars, series.values):
            ax.text(val+0.003, bar.get_y()+bar.get_height()/2,
                    f"{val*100:.1f}%", va="center", fontsize=8)
    fig.suptitle("SDT Response Type Proportions per STRUC × PW Cell\n(Overall)",
                 fontsize=12, y=1.01)
    fig.tight_layout()
    path = os.path.join(FIGURES_DIR, out_filename)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_filename}")


# ── 4. Main ────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  Unknown Words — Behavioral Analysis")
    print("=" * 60)

    # ── Load & classify
    print("\n[1/5] Parsing raw CSVs …")
    df_raw = parse_all_csvs(DATA_DIR)
    df     = classify_responses(df_raw)
    df_rt  = filter_rt(df)

    n_ppts  = df["prolific_id"].nunique()
    n_trials= len(df)
    n_rt    = len(df_rt)
    pct_rt  = 100 * n_rt / n_trials
    print(f"  Participants : {n_ppts}")
    print(f"  Trials total : {n_trials:,}")
    print(f"  Trials in RT window ({RT_LOW_S}–{RT_HIGH_S}s): {n_rt:,}  ({pct_rt:.1f}%)")
    print(f"  STRUC counts :")
    for s, c in df["STRUC"].value_counts().items():
        print(f"    {s:<12}: {c:,}")

    # ── Save trial-level CSV
    trial_csv = os.path.join(ANALYSIS_DIR, "trial_level_data.csv")
    df.to_csv(trial_csv, index=False)
    print(f"\n  Trial-level CSV saved → {os.path.basename(trial_csv)}")

    # ── ANOVA: Grammatical × Reversed × PW (main 2×3 factorial)
    print("\n[2/5] Running ANOVAs …")
    df_23  = df[df["STRUC"].isin(["Grammatical","Reversed"])]
    rt_23  = df_rt[df_rt["STRUC"].isin(["Grammatical","Reversed"])]

    acc_anova, rt_anova = run_anova_2way(
        df_23, rt_23,
        "Accurate ~ C(STRUC) * C(Pseudowords)",
        "rt_s ~ C(STRUC) * C(Pseudowords)",
    )
    if not acc_anova.empty:
        acc_anova.to_csv(os.path.join(ANALYSIS_DIR, "anova_accuracy_2x3.csv"))
    if not rt_anova.empty:
        rt_anova.to_csv(os.path.join(ANALYSIS_DIR, "anova_rt_2x3.csv"))
    print("  2×3 ANOVA tables saved.")

    # ── Summary CSVs
    print("\n[3/5] Saving summary tables …")
    for cols, fname in [
        (["STRUC","Pseudowords"], "summary_accuracy_struc_pw.csv"),
        (["STRUC"],               "summary_accuracy_struc.csv"),
        (["Cond_ID"],             "summary_accuracy_condid.csv"),
    ]:
        acc_summary(df, cols).to_csv(os.path.join(ANALYSIS_DIR, fname), index=False)
        rt_summary(df_rt, cols).to_csv(
            os.path.join(ANALYSIS_DIR, fname.replace("accuracy","rt")), index=False)
    # SDT response type summary
    sdt = df.groupby(["STRUC","Pseudowords","Response_Type"]).size().reset_index(name="Count")
    sdt.pivot_table(index=["STRUC","Pseudowords"], columns="Response_Type",
                    values="Count", fill_value=0).reset_index()\
       .to_csv(os.path.join(ANALYSIS_DIR, "sdt_response_summary.csv"), index=False)
    print("  Summary CSVs saved.")

    # ── Figures
    print("\n[4/5] Generating figures …")

    # --- Fig 1: Overall 2×3 accuracy + RT (Grammatical × Reversed × PW)
    df_23 = df[df["STRUC"].isin(["Grammatical","Reversed"])]
    rt_23 = df_rt[df_rt["STRUC"].isin(["Grammatical","Reversed"])]
    plot_accuracy_rt_2x3(df_23, rt_23,
                         ["Grammatical","Reversed"], "Overall",
                         "fig01_accuracy_rt_overall.png",
                         anova_acc=acc_anova, anova_rt=rt_anova)

    # --- Fig 2: All 3 STRUC conditions
    plot_3struc_comparison(df, df_rt,
                           "Overall", "fig02_3struc_comparison.png")

    # --- Fig 3: All 8 Cond_IDs with pairwise significance matrices
    plot_cond_id_with_sig_matrix(df, df_rt,
                                 "fig03_cond_id_with_significance.png")

    # --- Fig 4–7: SDT response type rates (matching notebook Cell 13)
    for resp, slug, num in [
        ("Hit",            "hit",            4),
        ("Miss",           "miss",           5),
        ("Correct Reject", "correct_reject", 6),
        ("False Alarm",    "false_alarm",    7),
    ]:
        plot_response_type_rate(
            df, resp, ["Grammatical","Reversed"],
            "Overall", f"fig0{num}_response_{slug}.png"
        )

    # --- Fig 8: RT distributions (violin)
    plot_rt_distributions(df_rt, "fig08_rt_distributions.png")

    # --- Fig 9: SDT summary table
    plot_response_summary_table(df, "fig09_sdt_summary_table.png")

    print("\n[5/5] Done.")
    print(f"\n  Figures → {FIGURES_DIR}")
    print(f"  Tables  → {ANALYSIS_DIR}")
    figs = sorted(os.listdir(FIGURES_DIR))
    print(f"  {len(figs)} figures saved:")
    for f in figs:
        print(f"    {f}")


if __name__ == "__main__":
    main()
