# -*- coding: utf-8 -*-
"""Assemble the one-page deliverables gallery from the figures the pipeline already wrote.

Nothing is computed here: every panel is an existing PNG, so the gallery can be regenerated after any
step is rerun.  Missing panels are skipped (and listed), so it also works on a case that has only some
of the steps.  Env: CASE (default 1009), OUT (default fusion_ready/DELIVERABLES_<today>.png).
Usage:  python render_gallery.py            /  CASE=1001 python render_gallery.py
"""
import os, sys, datetime
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.image import imread
from case_paths import paths, HERE

P = paths(); CT = P["base"]; BO = os.path.join(HERE, "BLENDER_OUT")
PANELS = [  # (path, title, subtitle)
    (os.path.join(CT, "coronary", "coronary_render.png"), "18 — coronary tree from the CT", "LM / LAD+D / LCx+OM / RCA, named by topology; tubes >= 2 mm for printing"),
    (os.path.join(CT, "coronary", "coronary_cpr.png"), "18 — CPR quality control", "curved reformat along each centreline: bright = trustworthy, faint = extrapolated"),
    (os.path.join(CT, "hires", "hires_closeup.png"), "19 — continuous-field surfaces", "binary-mask staircase (left) vs iso-surface of a continuous field (right)"),
    (os.path.join(BO, "cutaway_v4_vs_v5.png"), "19 — LV cut-away, v4 vs v5", "trabeculae and both papillary muscles resolved at 0.49 mm"),
    (os.path.join(CT, "coronary", "territories", "territory_map.png"), "20 — perfusion territories + AHA 17", "Voronoi to the visible tree + groove priors; mass at risk per occlusion site"),
    (os.path.join(CT, "great_vessels_check.png"), "24 — great vessels grown from the CT", "pulmonary veins, SVC, PA branches beyond the MM-WHS labels"),
    (os.path.join(CT, "whole_heart_ext", "whole_heart_render.png"), "22+24 — whole heart + coronaries", "chamber casts, synthetic walls, great vessels, coronary systems"),
    (os.path.join(CT, "whole_heart_hollow", "whole_heart_hollow_v2_anatomy_render.png"), "26+29 — hollow heart, four-chamber cut", "16 anatomical parts; cut face re-triangulated and outlined"),
    (os.path.join(CT, "cases", "summary.png"), "21+23 — the method across cases", "every step runs from the labels alone; per-case table in CT/cases/SUMMARY.md"),
]


def main():
    have = [(p, t, s) for p, t, s in PANELS if os.path.exists(p)]
    miss = [os.path.relpath(p, HERE) for p, _, _ in PANELS if not os.path.exists(p)]
    if not have: print("no panels found"); return
    n = len(have); rows = (n + 1) // 2
    fig, axes = plt.subplots(rows, 2, figsize=(15, 4.6 * rows))
    for ax, (p, t, s) in zip(axes.ravel(), have):
        ax.imshow(imread(p)); ax.set_axis_off()
        ax.set_title(t, fontsize=12, weight="bold", loc="left"); ax.text(0, -0.035, s, transform=ax.transAxes, fontsize=9, color="0.3", va="top")
    for ax in axes.ravel()[n:]: ax.set_axis_off()
    plt.suptitle(f"case {P['case']} — phase-1 deliverables ({datetime.date.today()})\nMM-WHS research CT: renders and tables may be shared, the meshes may not be redistributed", fontsize=14)
    out = os.environ.get("OUT", os.path.join(HERE, f"DELIVERABLES_{datetime.date.today()}.png"))
    plt.tight_layout(rect=(0, 0, 1, 0.97))
    for attempt in range(3):
        try: plt.savefig(out, dpi=72); break                       # OneDrive occasionally refuses the overwrite
        except OSError: import time; time.sleep(2)
    print(f"-> {out}  ({n} panels" + (f", missing: {', '.join(miss)})" if miss else ")"))


if __name__ == "__main__":
    main()
