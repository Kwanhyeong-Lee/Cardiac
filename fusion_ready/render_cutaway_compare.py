# -*- coding: utf-8 -*-
"""Same camera, same 44 mm window into cut-away half A: v4 (binary-mask parts) vs v5 (continuous-field
parts). Flat Lambert shading so facets and voxel noise are visible. -> BLENDER_OUT/cutaway_v4_vs_v5.png"""
import os, json, numpy as np, trimesh
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
HERE = os.path.dirname(os.path.abspath(__file__)); BO = os.path.join(HERE, "BLENDER_OUT"); CT = os.path.join(HERE, "CT")
d = json.load(open(os.path.join(HERE, "valve_refit.json"))); AXIS = np.array(d["lv_geometry"]["axis_base_to_apex"]); MV_C = np.array(d["design"]["mv_centre_mm"])
cut = json.load(open(os.path.join(BO, "cutaway_v5.json"))); n_cut = np.array(cut["plane_normal"])
pm = json.load(open(os.path.join(CT, "pm_tips.json")))["muscles"]
HALF = 22.0

def draw(ax, mesh, centre, viewdir, title):
    cen = mesh.triangles_center; keep = np.all(np.abs(cen - centre) <= HALF + 6, axis=1)
    tri, nrm = mesh.triangles[keep], mesh.face_normals[keep]
    light = -viewdir + 0.4 * np.cross(-viewdir, AXIS); light /= np.linalg.norm(light)
    lam = np.clip(np.abs(nrm @ light), 0, 1) * 0.8 + 0.2
    u = np.cross(viewdir, AXIS); u /= np.linalg.norm(u); v = np.cross(viewdir, u)
    P = (tri - centre) @ np.c_[u, v]; depth = ((tri - centre) @ viewdir).mean(1); order = np.argsort(-depth)
    cols = np.c_[np.tile(lam[order], (3, 1)).T * [0.86, 0.72, 0.66], np.ones(len(order))]
    ax.add_collection(PolyCollection(P[order], facecolors=cols, edgecolors=cols, linewidths=0.3, antialiased=False))
    ax.set_xlim(-HALF, HALF); ax.set_ylim(-HALF, HALF); ax.set_aspect("equal"); ax.set_axis_off(); ax.set_title(f"{title}\n({len(mesh.faces):,} faces in the half)", fontsize=9)

# look into the cut face (camera on the removed-half side), at the posteromedial papillary muscle
pmm = [m for m in pm if m["label"] == "posteromedial"][0]; centre = (np.array(pmm["tip_mm"]) + np.array(pmm["base_mm"])) / 2
viewdir = n_cut if (centre - MV_C) @ n_cut < 0 else -n_cut         # look from outside the kept half toward the cut face
fig, axes = plt.subplots(1, 2, figsize=(14, 8))
for ax, tag, title in [(axes[0], "v4", "v4 — binary-mask marching cubes parts"), (axes[1], "v5", "v5 — continuous-field iso-surface parts (ct_hires_lv.py)")]:
    half = trimesh.load(os.path.join(BO, f"hollow_{tag}_cutaway_A.stl"), process=False)
    draw(ax, half, centre, viewdir, title)
plt.suptitle("cut-away A, 44 mm window at the posteromedial papillary muscle — same camera, flat shading", fontsize=11)
plt.tight_layout(rect=(0, 0, 1, 0.94)); plt.savefig(os.path.join(BO, "cutaway_v4_vs_v5.png"), dpi=90); print("-> cutaway_v4_vs_v5.png")
