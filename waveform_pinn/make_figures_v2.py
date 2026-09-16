# -*- coding: utf-8 -*-
"""Figures B4 and B5 — the post-audit results.

Style is imported from make_figures.py so the whole set matches. Every number is read from
the saved result files; none is retyped into the plotting code.

    python3 make_figures_v2.py
"""
import json, os
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

from make_figures import FIG, save, panel, BLUE, RED, GREEN, ORANGE, PURPLE, TEAL, GREY

HERE = os.path.dirname(os.path.abspath(__file__))
CM = json.load(open(f"{HERE}/results_capacity_match.json"))
PR = json.load(open(f"{HERE}/results_port_rollout.json"))


def rows(store, model):
    return sorted([r for r in store if r["model"] == model], key=lambda z: z["seed"])


# ════════════════════════════════════════════════════ B4: the output constraint
def figB4():
    order = ["A", "E", "E2", "E3"]
    col = {"A": GREY, "E": ORANGE, "E2": PURPLE, "E3": GREEN}
    fig, ax = plt.subplots(1, 3, figsize=(12.4, 3.7))
    fig.subplots_adjust(wspace=0.34)

    # (A) the learned floor and what it excludes
    panel(ax[0], "A  A learned offset, not a guarantee")
    xs, floors, excl = [], [], []
    for m in ["E", "E2", "E3"]:
        rr = rows(CM, m)
        xs.append(m)
        floors.append(np.mean([r["floor_cost"]["floor_Lmin"] for r in rr]))
        excl.append(100 * np.mean([r["floor_cost"]["frac_train_targets_below_floor"]
                                   for r in rr]))
    b = ax[0].bar(xs, floors, color=[col[m] for m in xs], width=0.55, zorder=3)
    for k, (bb, e, f) in enumerate(zip(b, excl, floors)):
        ax[0].text(bb.get_x() + bb.get_width() / 2, f + 0.12,
                   f"{f:.2f} L/min\n{e:.1f}% of targets\nunreachable" if f > 0
                   else "0.00 L/min\nnothing excluded",
                   ha="center", va="bottom", fontsize=7.0,
                   color=RED if f > 0 else GREEN)
    ax[0].set_ylabel("implied output floor  (L/min)")
    ax[0].set_ylim(0, max(floors) * 1.85)
    ax[0].text(0.97, 0.97, "E, E2:  y = _scale·CO + _shift\n"
                           "            (both free)\n"
                           "E3:  y = (CO − μ)/σ   (fixed)",
               transform=ax[0].transAxes, va="top", ha="right", fontsize=7.0, color="#444")

    # (B) two-sided range probe at 40 sigma
    panel(ax[1], "B  Positivity ≠ plausibility (40σ)")
    neg, above, inside = [], [], []
    for m in order:
        rr = rows(CM, m)
        n = sum(r["output_range_probe"]["sigma40"]["n"] for r in rr)
        nn = sum(r["output_range_probe"]["sigma40"]["n_negative"] for r in rr)
        lo = sum(r["output_range_probe"]["sigma40"]["n_below_lo"] for r in rr)
        hi = sum(r["output_range_probe"]["sigma40"]["n_above_hi"] for r in rr)
        neg.append(lo); above.append(hi); inside.append(n - lo - hi)
    xi = np.arange(len(order))
    ax[1].bar(xi, inside, color="#CFE3F2", label="inside 0.5–20 L/min", zorder=3)
    ax[1].bar(xi, neg, bottom=inside, color=RED, label="below 0.5 L/min", zorder=3)
    ax[1].bar(xi, above, bottom=np.array(inside) + np.array(neg), color=ORANGE,
              label="above 20 L/min", zorder=3)
    for i, m in enumerate(order):
        mx = max(r["output_range_probe"]["sigma40"]["max"] for r in rows(CM, m))
        ax[1].text(i, 12300, f"max\n{mx:,.0f}", ha="center", fontsize=7, color="#444")
    ax[1].set_xticks(xi); ax[1].set_xticklabels(order)
    ax[1].set_ylabel("probes"); ax[1].set_ylim(0, 15000)
    ax[1].legend(loc="lower left", fontsize=7)

    # (C) accuracy is unchanged
    panel(ax[2], "C  Accuracy unchanged")
    for i, m in enumerate(order):
        rr = rows(CM, m)
        v = [r["internal_r2"] for r in rr]
        ax[2].scatter([i] * len(v), v, s=26, color=col[m], zorder=4)
        ax[2].plot([i - 0.22, i + 0.22], [np.mean(v)] * 2, color=col[m], lw=2.2, zorder=3)
    ax[2].set_xticks(range(len(order))); ax[2].set_xticklabels(order)
    ax[2].set_ylabel("held-out R²  (patient level)")
    ax[2].set_xlabel("3 seeds; every difference sits inside the seed spread",
                     fontsize=7.4, color="#666", labelpad=6)
    save(fig, "FigB4_output_constraint")


# ════════════════════════════════════════════════════ B5: the port rollout
def figB5():
    order = ["P", "Pm", "U", "F"]
    col = {"P": RED, "Pm": GREEN, "U": BLUE, "F": GREY}
    lab = {"P": "P\nR=LLᵀ", "Pm": "Pm\nR=diag softplus", "U": "U\nunconstrained", "F": "F\nfree MLP"}
    fig, ax = plt.subplots(1, 3, figsize=(12.8, 3.8))
    fig.subplots_adjust(wspace=0.32)

    # (A) passivity
    panel(ax[0], "A  Energy at zero input")
    xs, val, flip, ns = [], [], [], []
    for m in ["P", "Pm", "U"]:
        rr = rows(PR, m)
        e = [r["rollout_zero_input"]["energy"]["moving_steps"] for r in rr]
        xs.append(m)
        val.append(100 * np.mean([q["frac_gain_relative"] for q in e]))
        flip.append(100 * np.mean([q["frac_gain_under_sign_flip"] for q in e]))
        ns.append(sum(q["n_steps"] for q in e))
    xi = np.arange(len(xs))
    ax[0].bar(xi - 0.18, val, width=0.34, color=[col[m] for m in xs], zorder=3,
              label="as trained")
    ax[0].bar(xi + 0.18, flip, width=0.34, color="none", edgecolor="#888", lw=1.1,
              hatch="///", zorder=3, label="under sign flip (H,J,R)→(−H,−J,−R)")
    for i, (v, n) in enumerate(zip(val, ns)):
        ax[0].text(i - 0.18, v + 2.5, f"{v:.1f}%", ha="center", fontsize=7.5,
                   color=RED if v > 1 else GREEN, weight="bold")
        ax[0].text(i, -13, f"n={n:,}", ha="center", fontsize=6.8, color="#666")
    ax[0].set_xticks(xi); ax[0].set_xticklabels([lab[m].split("\n")[0] for m in xs])
    ax[0].set_ylabel("energy-gaining steps  (%)"); ax[0].set_ylim(0, 118)
    ax[0].legend(loc="upper left", fontsize=6.8)
    ax[0].text(0.03, 0.72, "U is near-symmetric under the flip:\n"
                           "the signature of having no sign\nconvention — i.e. no energy",
               transform=ax[0].transAxes, ha="left", va="top", fontsize=6.8, color="#444")

    # (B) admissibility by condition
    panel(ax[1], "B  Does the simulator stay physiological?")
    conds = [("box_uniform", "uniform\nover box"), ("dose_x5", "dose ×5"),
             ("recover_6sig", "recover\nfrom 6σ")]
    w, xi = 0.2, np.arange(len(conds))
    for k, m in enumerate(order):
        rr = rows(PR, m)
        v = [np.mean([r[f"rollout_{c}"]["frac_admissible"] for r in rr]) for c, _ in conds]
        ax[1].bar(xi + (k - 1.5) * w, v, width=w, color=col[m], label=m, zorder=3)
    ax[1].set_xticks(xi); ax[1].set_xticklabels([t for _, t in conds])
    ax[1].set_ylabel("fraction still admissible"); ax[1].set_ylim(0, 1.14)
    ax[1].legend(ncol=4, fontsize=7.5, loc="upper center")
    ax[1].set_xlabel("P and Pm impose mathematically identical guarantees",
                     fontsize=7.4, color="#444", labelpad=6)

    # (C) the growth-order explanation
    panel(ax[2], "C  Parameterisation, not constraint")
    for m in order:
        rr = rows(PR, m)
        x = [r["first_step_norm"]["recover_6sig"] for r in rr]
        y = [r["rollout_box_uniform"]["frac_admissible"] for r in rr]
        ax[2].scatter(x, y, s=44, color=col[m], zorder=4, label=m,
                      edgecolor="white", linewidth=0.7)
        ax[2].scatter([np.mean(x)], [np.mean(y)], s=150, marker="X", color=col[m],
                      zorder=5, edgecolor="white", linewidth=1.0)
    ax[2].set_xlabel("first-step magnitude at 6σ  (state sd)")
    ax[2].set_ylabel("fraction admissible, uniform over box")
    ax[2].legend(fontsize=7.5, loc="upper right", ncol=2)
    ax[2].annotate("R = LLᵀ is quadratic in its head output;\n"
                   "R = diag softplus is linear.\nSame guarantee, different growth order.",
                   xy=(0.03, 0.03), xycoords="axes fraction", ha="left", va="bottom",
                   fontsize=6.9, color="#444")
    save(fig, "FigB5_port_rollout")


if __name__ == "__main__":
    print("figures ->", FIG)
    figB4()
    figB5()
