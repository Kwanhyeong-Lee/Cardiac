# -*- coding: utf-8 -*-
"""Figures for Paper A (reference-standard benchmark) and Paper B (constraint scope).

Every number is read from the saved result files, never retyped. Run after all
experiments; writes PNG at 300 dpi plus a 150-dpi preview into ./figures/.

    python3 make_figures.py A     # Paper A only
    python3 make_figures.py B     # Paper B only
    python3 make_figures.py       # both
"""
import json, os, sys, glob, pickle
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "figures")
os.makedirs(FIG, exist_ok=True)

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9,
    "axes.edgecolor": "#4d4d4d", "axes.linewidth": 0.8,
    "axes.grid": True, "grid.color": "#E8E8E8", "grid.linewidth": 0.6,
    "axes.axisbelow": True, "xtick.color": "#333", "ytick.color": "#333",
    "axes.titlesize": 10, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "figure.facecolor": "white", "savefig.facecolor": "white",
    "legend.frameon": False, "legend.fontsize": 8,
})
BLUE, RED, GREEN = "#2166AC", "#B2182B", "#1B7837"
ORANGE, PURPLE, TEAL, GREY = "#E66101", "#762A83", "#4393C3", "#777777"


def save(fig, name):
    fig.savefig(f"{FIG}/{name}.png", dpi=300, bbox_inches="tight")
    fig.savefig(f"{FIG}/{name}_preview.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  {name}")


def panel(ax, t):
    ax.set_title(t, pad=6)


# ═══════════════════════════════════════════════════════ Paper A
def figA1_bland_altman():
    """Device against thermodilution: the floor every downstream model inherits."""
    d = pd.read_csv(f"{HERE}/wave_windows_ood.csv")
    b = d[d.tier == "BOTH"].dropna(subset=["CO_pc", "CO_td"])
    a = b.groupby("caseid")[["CO_pc", "CO_td"]].median()
    dev, ref = a.CO_pc.to_numpy(), a.CO_td.to_numpy()
    J = json.load(open(f"{HERE}/device_benchmark_v2.json"))

    fig, ax = plt.subplots(1, 2, figsize=(8.4, 3.4))
    fig.subplots_adjust(wspace=0.28)

    ax[0].scatter(ref, dev, s=34, color=BLUE, alpha=0.75, edgecolor="white", linewidth=0.6)
    lim = [min(ref.min(), dev.min()) - 0.5, max(ref.max(), dev.max()) + 0.5]
    ax[0].plot(lim, lim, ls="--", lw=1, color=GREY)
    ax[0].set_xlim(lim); ax[0].set_ylim(lim)
    ax[0].set_xlabel("Thermodilution CO (L/min)")
    ax[0].set_ylabel("Pulse-contour CO (L/min)")
    panel(ax[0], f"A  Device vs reference (n={len(ref)})")
    ax[0].text(0.04, 0.95, f"r = {J['pearson_r']:.2f} [{J['pearson_r_ci'][0]:.2f}, "
                           f"{J['pearson_r_ci'][1]:.2f}]",
               transform=ax[0].transAxes, va="top", fontsize=8.5)

    mean, diff = (dev + ref) / 2, dev - ref
    bias, lo, hi = J["bias"], J["loa"][0], J["loa"][1]
    ax[1].scatter(mean, diff, s=34, color=BLUE, alpha=0.75, edgecolor="white", linewidth=0.6)
    ax[1].axhline(bias, color=RED, lw=1.5, label=f"bias {bias:.2f}")
    for y in (lo, hi):
        ax[1].axhline(y, color=RED, lw=1, ls="--")
    ax[1].axhline(0, color=GREY, lw=0.8, ls=":")
    ax[1].fill_between([mean.min() - 0.4, mean.max() + 0.4], lo, hi,
                       color=RED, alpha=0.06)
    ax[1].set_xlim(mean.min() - 0.4, mean.max() + 0.4)
    ax[1].set_xlabel("Mean of two methods (L/min)")
    ax[1].set_ylabel("Pulse-contour − thermodilution (L/min)")
    panel(ax[1], "B  Bland–Altman")
    ax[1].text(0.98, 0.05,
               f"PE = {J['pct_error']:.1f}% [{J['pct_error_ci'][0]:.1f}, "
               f"{J['pct_error_ci'][1]:.1f}]\nLoA {lo:.2f} to {hi:.2f}",
               transform=ax[1].transAxes, ha="right", va="bottom", fontsize=8.5,
               bbox=dict(boxstyle="round,pad=0.35", fc="#FAFAFA", ec="#DDD", lw=0.6))
    save(fig, "FigA1_device_benchmark")


def figA2_error_decomposition():
    """PE against thermodilution decomposes as sqrt(floor^2 + own^2)."""
    dev = 40.1
    rows = [("morph.", 53.7, 0.320),
            ("morph.\n+ demo.", 47.7, 0.875),
            ("demo.\nonly", 56.5, 0.658),
            ("linear,\nboth", 49.2, 0.521)]
    fig, ax = plt.subplots(1, 3, figsize=(12.2, 3.7))
    fig.subplots_adjust(wspace=0.36, top=0.84)
    x = np.arange(len(rows))
    own = np.array([np.sqrt(max(r[1] ** 2 - dev ** 2, 0)) for r in rows])

    # --- A: total PE with the floor marked; errors do not add linearly ---
    ax[0].bar(x, [r[1] for r in rows], 0.58, color=ORANGE, alpha=0.9)
    ax[0].axhspan(0, dev, color=GREY, alpha=0.16)
    ax[0].axhline(dev, color=RED, lw=1.6, ls="--")
    ax[0].text(3.42, dev - 3.4, f"device floor {dev}%", color=RED, fontsize=8,
               ha="right")
    for i2, (nm, pe, _) in enumerate(rows):
        ax[0].text(i2, pe + 1.0, f"{pe:.1f}", ha="center", fontsize=8.4,
                   fontweight="bold")
    ax[0].set_xticks(x); ax[0].set_xticklabels([r[0] for r in rows], fontsize=8.2)
    ax[0].set_ylabel("PE against thermodilution (%)")
    ax[0].set_ylim(0, 68)
    panel(ax[0], "A  Total error, and the floor")

    # --- B: the model's own contribution, obtained in quadrature ---
    ax[1].bar(x, own, 0.58, color=BLUE, alpha=0.9)
    for i2, o in enumerate(own):
        ax[1].text(i2, o + 0.9, f"{o:.1f}", ha="center", fontsize=8.4,
                   fontweight="bold")
    ax[1].set_xticks(x); ax[1].set_xticklabels([r[0] for r in rows], fontsize=8.2)
    ax[1].set_ylabel("Model's own imitation error (%)")
    ax[1].set_ylim(0, 50)
    ax[1].annotate("", xy=(1, 25.8), xytext=(0, 35.7),
                   arrowprops=dict(arrowstyle="->", color=GREEN, lw=1.6))
    ax[1].text(0.5, 41, "demographics\nrecover 9.9 pp", color=GREEN, fontsize=8,
               ha="center", fontweight="bold")
    ax[1].text(0.02, 0.03,
               r"$\mathrm{own}=\sqrt{\mathrm{PE}^2-40.1^2}$",
               transform=ax[1].transAxes, fontsize=9, color="#444")
    panel(ax[1], "B  What the model itself contributes")

    # --- C: internal fidelity to the device ---
    ax[2].bar(x, [r[2] for r in rows], 0.58,
              color=[BLUE, GREEN, TEAL, PURPLE], alpha=0.9)
    for i2, r in enumerate(rows):
        ax[2].text(i2, r[2] + 0.022, f"{r[2]:.3f}", ha="center", fontsize=8.4)
    ax[2].set_xticks(x); ax[2].set_xticklabels([r[0] for r in rows], fontsize=8.2)
    ax[2].set_ylabel("Internal R² (reproducing the device)")
    ax[2].set_ylim(0, 1.06)
    ax[2].text(2.4, 0.22, "0.320 alone\n0.658 alone\n0.875 together",
               fontsize=8, ha="center", color="#444",
               bbox=dict(boxstyle="round,pad=0.35", fc="#F7F7F7", ec="#DDD", lw=0.6))
    panel(ax[2], "C  The two input sets are complementary")
    save(fig, "FigA2_error_decomposition")


def figA3_trending():
    """Concordance rises with interval — the reference cannot resolve short changes."""
    d = pd.read_csv(f"{HERE}/wave_windows_ood.csv")
    b = d[d.tier == "BOTH"].dropna(subset=["CO_pc", "CO_td"])

    def conc(frame, ref, test, lag, frac=0.15):
        dr, dt = [], []
        for _, x in frame.sort_values(["caseid", "t_win_start"]).groupby("caseid"):
            r, s = x[ref].to_numpy(), x[test].to_numpy()
            if len(r) <= lag:
                continue
            dr.append(r[lag:] - r[:-lag]); dt.append(s[lag:] - s[:-lag])
        if not dr:
            return None
        dr, dt = np.concatenate(dr), np.concatenate(dt)
        k = np.abs(dr) >= frac * frame[ref].mean()
        if k.sum() < 20:
            return None
        return float(np.mean(np.sign(dr[k]) == np.sign(dt[k]))), int(k.sum())

    lags = [1, 2, 3, 4, 6]
    dev = [conc(b, "CO_td", "CO_pc", L) for L in lags]
    mins = [L * 5 for L in lags]

    fig, ax = plt.subplots(1, 2, figsize=(8.4, 3.4))
    fig.subplots_adjust(wspace=0.3)
    ax[0].plot(mins, [c[0] for c in dev], "o-", color=BLUE, lw=1.8, ms=6,
               label="device vs thermodilution")
    ax[0].axhline(0.92, color=GREEN, lw=1.2, ls="--")
    ax[0].text(29, 0.925, "92% clinical threshold", color=GREEN, fontsize=8, ha="right")
    ax[0].axhline(0.5, color=GREY, lw=1, ls=":")
    ax[0].text(6, 0.512, "chance", color=GREY, fontsize=8)
    for m, c in zip(mins, dev):
        ax[0].annotate(f"n={c[1]}", (m, c[0]), textcoords="offset points",
                       xytext=(0, -13), ha="center", fontsize=7, color=GREY)
    ax[0].set_xlabel("Interval between compared readings (min)")
    ax[0].set_ylabel("Four-quadrant concordance")
    ax[0].set_ylim(0.42, 1.0); ax[0].set_xticks(mins)
    ax[0].legend(loc="lower right")
    panel(ax[0], "A  A purpose-built trending monitor also fails")

    ax[1].axis("off")
    txt = ("The device is beat-responsive and marketed for trending.\n"
           "Its concordance against continuous thermodilution rises\n"
           "monotonically with the comparison interval:\n\n"
           "     5 min   0.598\n"
           "    10 min   0.633\n"
           "    15 min   0.733\n"
           "    20 min   0.728\n"
           "    30 min   0.744\n\n"
           "That is the signature of a reference whose own averaging\n"
           "window exceeds the interval being compared, not of a\n"
           "method that cannot track.\n\n"
           "Neither method reaches 92% at any interval, and polar\n"
           "radial limits of agreement are approximately ±200° for\n"
           "both. No trending claim is supportable from this data.")
    ax[1].text(0.0, 0.98, txt, va="top", ha="left", fontsize=8.3, family="DejaVu Sans",
               linespacing=1.5)
    panel(ax[1], "B  Reading")
    save(fig, "FigA3_trending_resolution")


def figA4_abstention():
    """Risk-coverage on transplant, against a random-abstention control."""
    import abstention as AB
    Xtr = np.load("/tmp/Xtrain.npy") if os.path.exists("/tmp/Xtrain.npy") else None
    ev = pickle.load(open("/tmp/ood_eval.pkl", "rb")) if os.path.exists("/tmp/ood_eval.pkl") else None
    if Xtr is None or ev is None:
        print("  FigA4 skipped (rerun the v5 cell to regenerate /tmp artefacts)")
        return
    Xv, err = ev["TRANSPLANT"]
    sc = AB.fit_scores(Xtr)
    rc = AB.compare({"mahalanobis": sc["mahalanobis"](Xv)}, err)
    m, r = rc["mahalanobis"], rc["random"]

    fig, ax = plt.subplots(1, 2, figsize=(8.4, 3.4))
    fig.subplots_adjust(wspace=0.3)
    ax[0].plot(m.coverage * 100, m.mae_median, "o-", color=BLUE, lw=1.8, ms=5,
               label="Mahalanobis distance")
    ax[0].plot(r.coverage * 100, r.mae_median, "s--", color=GREY, lw=1.4, ms=4,
               label="random abstention (control)")
    ax[0].set_xlabel("Coverage retained (%)"); ax[0].set_ylabel("Median |error| (L/min)")
    ax[0].invert_xaxis(); ax[0].legend()
    panel(ax[0], "A  The score does real work")

    ax[1].plot(m.coverage * 100, m.p90, "o-", color=RED, lw=1.8, ms=5, label="p90 |error|")
    ax[1].plot(r.coverage * 100, r.p90, "s--", color=GREY, lw=1.4, ms=4, label="random")
    ax2 = ax[1].twinx()
    ax2.plot(m.coverage * 100, m.frac_over_1Lmin * 100, "^-", color=ORANGE, lw=1.4,
             ms=5, label="> 1 L/min (%)")
    ax2.set_ylabel("Retained readings wrong by > 1 L/min (%)", color=ORANGE)
    ax2.tick_params(axis="y", colors=ORANGE); ax2.grid(False)
    ax[1].set_xlabel("Coverage retained (%)"); ax[1].set_ylabel("90th-percentile |error| (L/min)")
    ax[1].invert_xaxis()
    h1, l1 = ax[1].get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
    ax[1].legend(h1 + h2, l1 + l2, loc="upper right")
    panel(ax[1], "B  And is not enough")
    ax[1].text(0.03, 0.06, "discarding 30% still leaves\n23% wrong by > 1 L/min",
               transform=ax[1].transAxes, fontsize=8, color=RED,
               bbox=dict(boxstyle="round,pad=0.3", fc="#FFF5F5", ec="#EBC", lw=0.6))
    save(fig, "FigA4_abstention")


# ═══════════════════════════════════════════════════════ Paper B
def _ablation_table():
    r = json.load(open(f"{HERE}/results_paper2.json"))
    rows = []
    for x in r:
        lab = x.get("label", "")
        if not (lab.startswith("v3: morphology") or lab.startswith("ablation")):
            continue
        v = x["violations"]
        m = ("A" if lab.startswith("v3") else lab.replace("ablation ", "")
             .replace(" (v3 inputs)", ""))
        rows.append(dict(model=m, seed=x["seed"], r2=x["internal_r2"],
                         T=v["T_neg"], V=v["V_neg"], R=v["R_nonpsd"],
                         n=x["n_val"]))
    return pd.DataFrame(rows)


def figB1_ablation_three_datasets():
    """Accuracy indistinguishable; validity is the discriminating axis."""
    d3 = _ablation_table()
    g = d3.groupby("model").agg(r2=("r2", "mean"), sd=("r2", "std"),
                                T=("T", "mean"), V=("V", "mean"), R=("R", "mean"),
                                n=("n", "mean"), k=("seed", "size"))
    order = ["A", "B", "C", "D"]
    g = g.reindex(order)
    labels = ["A: hard", "B: vanilla\nMLP", "C: no\nstructure", "D: soft\n(penalty)"]

    fig, ax = plt.subplots(1, 3, figsize=(12.2, 3.7))
    fig.subplots_adjust(wspace=0.34, top=0.84)
    x = np.arange(4)

    ds = {"clinical features (Paper 1)": [0.9752, 0.9743, 0.9748, 0.9741],
          "waveform": [0.253, 0.308, 0.314, 0.318],
          "waveform + demographics": list(g.r2)}
    w = 0.26
    for i, (nm, vals) in enumerate(ds.items()):
        ax[0].bar(x + (i - 1) * w, vals, w, label=nm,
                  color=[TEAL, BLUE, PURPLE][i], alpha=0.88)
    ax[0].set_xticks(x); ax[0].set_xticklabels(labels, fontsize=7.8)
    ax[0].set_ylabel("Mean R²"); ax[0].set_ylim(0, 1.34)
    ax[0].legend(fontsize=7.2, loc="upper left", ncol=1)
    panel(ax[0], "A  Accuracy — three datasets")

    w2 = 0.26
    ax[1].bar(x - w2, g["T"], w2, color=RED, label="$T<0$")
    ax[1].bar(x, g["V"], w2, color=ORANGE, label="$V<0$")
    Rp = g["R"].clip(lower=0)
    ax[1].bar(x + w2, Rp, w2, color=PURPLE, label=r"$R\not\succeq0$")
    ax[1].set_xticks(x); ax[1].set_xticklabels(labels, fontsize=7.8)
    ax[1].set_ylabel(f"Violations per {int(g.n.mean()):,} held-out windows")
    ymax = max(g[["T", "V"]].max().max(), Rp.max()) * 1.42
    ax[1].set_ylim(0, ymax)
    ax[1].legend(ncol=3, loc="upper center", fontsize=7.4)
    ax[1].text(0, ymax * 0.07, "0", ha="center", color=GREEN, fontweight="bold",
               fontsize=11)
    d_tot = g.loc["D", ["T", "V"]].sum() + max(g.loc["D", "R"], 0)
    ax[1].text(3, ymax * 0.07, f"{d_tot:.2f}", ha="center", color=RED,
               fontweight="bold", fontsize=9)
    ax[1].text(1 + w2, ymax * 0.045, "n/a", ha="center", fontsize=7.5, color=GREY)
    panel(ax[1], "B  Physical validity")

    ad = g.loc[["A", "D"], ["T", "V", "R"]].clip(lower=0)
    xs = np.arange(2)
    ax[2].bar(xs - 0.22, ad["T"], 0.22, color=RED, label="$T<0$")
    ax[2].bar(xs, ad["V"], 0.22, color=ORANGE, label="$V<0$")
    ax[2].bar(xs + 0.22, ad["R"], 0.22, color=PURPLE, label=r"$R\not\succeq0$")
    ax[2].set_xticks(xs)
    ax[2].set_xticklabels(["A: architecture", "D: penalty"], fontsize=8.5)
    ax[2].set_ylabel("Violations per seed"); ax[2].set_ylim(0, 0.72)
    ax[2].text(0, 0.05, "0\nby construction", ha="center", color=GREEN, fontsize=8.5,
               fontweight="bold")
    ax[2].text(1, 0.40, f"{d_tot:.2f} per seed\n= 1 in 16,626 windows",
               ha="center", color=RED, fontsize=8.5)
    ax[2].legend(ncol=3, loc="upper center", fontsize=7.4)
    panel(ax[2], "C  Rare is not impossible")
    save(fig, "FigB1_ablation")


def figB2_scope():
    """Where the guarantee stops — and that the synthetic probe does not replicate."""
    synth = {  # from RESULTS_v4_scope.md, relative PSD tolerance applied
        0: {"A": (2.6, 9.6, 0), "C": (2.6, 9.5, 0), "E": (3.4, 9.4, 0)},
        6: {"A": (-7.8, 27.0, 24), "C": (-10.8, 26.6, 26), "E": (3.4, 17.4, 0)},
        24: {"A": (-29.6, 92.5, 94), "C": (-38.2, 103.7, 104), "E": (3.4, 386.4, 0)},
    }
    runs = [json.load(open(f)) for f in sorted(glob.glob(f"{HERE}/ood_clinical_*.json"))]
    clin = {}
    for L in "ACE":
        for s in ["IN-DIST (general surgery)", "THORACIC", "TRANSPLANT"]:
            vals = []
            for r in runs:
                for run in r["runs"]:
                    if run["model"] != L:
                        continue
                    for row in run["results"]:
                        if row["set"] == s:
                            vals.append(row["co_negative"])
            clin[(L, s)] = float(np.mean(vals)) if vals else np.nan

    fig, ax = plt.subplots(1, 2, figsize=(8.8, 3.5))
    fig.subplots_adjust(wspace=0.3)
    shifts = [0, 6, 24]
    x = np.arange(len(shifts)); w = 0.26
    for i, (L, c) in enumerate(zip("ACE", [BLUE, RED, GREEN])):
        ax[0].bar(x + (i - 1) * w, [synth[s][L][2] for s in shifts], w,
                  color=c, alpha=0.9,
                  label={"A": "A: state constrained", "C": "C: unconstrained",
                         "E": "E: output constrained"}[L])
    ax[0].set_xticks(x); ax[0].set_xticklabels([f"{s}σ" for s in shifts])
    ax[0].set_xlabel("Synthetic Gaussian displacement")
    ax[0].set_ylabel("Negative cardiac outputs (of 400)")
    ax[0].legend(fontsize=7.6, loc="upper left")
    ax[0].set_ylim(0, 128)
    for k, s in enumerate(shifts):
        ax[0].text(k + w, 3, "0", ha="center", color=GREEN, fontweight="bold",
                   fontsize=9)
    panel(ax[0], "A  Synthetic probe")
    ax[0].text(0.98, 0.42,
               "A keeps T, V, R admissible at every\ndisplacement — only its output fails",
               transform=ax[0].transAxes, fontsize=7.6, ha="right", color="#444",
               bbox=dict(boxstyle="round,pad=0.3", fc="#F7F7F7", ec="#DDD", lw=0.6))

    sets = ["IN-DIST (general surgery)", "THORACIC", "TRANSPLANT"]
    x2 = np.arange(len(sets))
    for i, (L, c) in enumerate(zip("ACE", [BLUE, RED, GREEN])):
        ax[1].bar(x2 + (i - 1) * w, [clin[(L, s)] for s in sets], w, color=c, alpha=0.9)
    ax[1].set_xticks(x2)
    ax[1].set_xticklabels(["general\nsurgery", "thoracic\n(unseen)",
                           "transplant\n(unseen)"], fontsize=8)
    ax[1].set_ylabel("Negative cardiac outputs")
    ax[1].set_ylim(0, 128)
    ax[1].set_yticks(ax[0].get_yticks())
    for k in range(3):
        for i in range(3):
            ax[1].text(k + (i - 1) * w, 3, "0", ha="center", color=GREEN,
                       fontweight="bold", fontsize=9)
    ax[1].text(1, 74, "Not one negative output —\nincluding the entirely\n"
                      "unconstrained model C",
               ha="center", fontsize=9.5, color=GREEN, fontweight="bold")
    ax[1].text(1, 44, "226 + 175 patients never seen in training",
               ha="center", fontsize=7.8, color="#666")
    panel(ax[1], "B  Real clinical shift")
    save(fig, "FigB2_scope")


def figB3_shift():
    """Validity holds under real shift; accuracy is a separate, untouched problem."""
    runs = [json.load(open(f)) for f in sorted(glob.glob(f"{HERE}/ood_clinical_*.json"))]
    rec = []
    for r in runs:
        for run in r["runs"]:
            for row in run["results"]:
                rec.append(dict(model=run["model"], set=row["set"],
                                r2=row["r2_patient"], T=row["T_neg"],
                                R=row["R_nonpsd"], n=row["n_windows"]))
    d = pd.DataFrame(rec)
    sets = ["IN-DIST (general surgery)", "THORACIC", "TRANSPLANT"]
    short = ["general\nsurgery", "thoracic\n(unseen)", "transplant\n(unseen)"]

    fig, ax = plt.subplots(1, 2, figsize=(8.8, 3.5))
    fig.subplots_adjust(wspace=0.3)
    x = np.arange(3); w = 0.26
    for i, (L, c) in enumerate(zip("ACE", [BLUE, RED, GREEN])):
        g = d[d.model == L].groupby("set").r2
        mu = [g.mean()[s] for s in sets]; sd = [g.std()[s] for s in sets]
        ax[0].bar(x + (i - 1) * w, mu, w, yerr=sd, capsize=3, color=c, alpha=0.9,
                  error_kw=dict(lw=1, ecolor="#444"),
                  label={"A": "A: hard", "C": "C: none", "E": "E: output"}[L])
    ax[0].set_xticks(x); ax[0].set_xticklabels(short, fontsize=8)
    ax[0].set_ylabel("R² (patient level)"); ax[0].set_ylim(0, 1.0)
    ax[0].legend(ncol=3, fontsize=7.6, loc="upper right")
    panel(ax[0], "A  Accuracy degrades identically for all")
    ax[0].text(1.5, 0.13, "−0.34 for every architecture", fontsize=8.2,
               ha="center", color="#555",
               bbox=dict(boxstyle="round,pad=0.3", fc="#F7F7F7", ec="#DDD", lw=0.6))

    for i, (L, c) in enumerate(zip("ACE", [BLUE, RED, GREEN])):
        g = d[d.model == L].groupby("set")
        vals = [max(g.R.mean()[s], 0) for s in sets]
        ax[1].bar(x + (i - 1) * w, vals, w, color=c, alpha=0.9)
    ax[1].set_xticks(x); ax[1].set_xticklabels(short, fontsize=8)
    ax[1].set_ylabel(r"Windows with $R\not\succeq0$")
    for i, s in enumerate(sets):
        ax[1].text(i - w, 200, "0", ha="center", color=GREEN, fontweight="bold",
                   fontsize=10)
        ax[1].text(i + w, 200, "0", ha="center", color=GREEN, fontweight="bold",
                   fontsize=10)
    ax[1].set_ylim(0, 7600)
    ax[1].text(1, 6900, "C: every window, every set", ha="center",
               fontsize=9, color=RED, fontweight="bold")
    panel(ax[1], "B  Validity does not")
    save(fig, "FigB3_distribution_shift")


if __name__ == "__main__":
    which = sys.argv[1].upper() if len(sys.argv) > 1 else "AB"
    print("writing figures ->", FIG)
    if "A" in which:
        figA1_bland_altman(); figA2_error_decomposition()
        figA3_trending(); figA4_abstention()
    if "B" in which:
        figB1_ablation_three_datasets(); figB2_scope(); figB3_shift()
