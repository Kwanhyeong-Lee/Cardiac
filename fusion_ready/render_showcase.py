# -*- coding: utf-8 -*-
"""Showcase render of the current state (software rasteriser: matplotlib Poly3DCollection).

Anatomical frame for every panel: z up = basal (toward the valves), x = mitral->aortic
direction, y completes the frame. Lambert shading, orthographic camera.
    usage: PYTHONPATH=/tmp/pylibs python3 render_showcase.py <panel 1..6 | compose>
Panels: 1 v4 exterior by part  2 v4 cut-away A (interior)  3 v4 cut-away B
        4 v4 mid-cavity slab (short axis)  5 phantom core + mould box  6 CT blood pool
Output: BLENDER_OUT/showcase_p<k>.png, BLENDER_OUT/showcase_2026-09-16.png
"""
import json, os, sys, warnings
import numpy as np, trimesh
warnings.filterwarnings("ignore")
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

HERE = os.path.dirname(os.path.abspath(__file__)); BO = os.path.join(HERE, "BLENDER_OUT"); FA = os.path.join(HERE, "frame_A_patient")
CT = os.path.join(HERE, "CT"); PH = os.path.join(HERE, "PHANTOM")
d = json.load(open(os.path.join(HERE, "valve_refit.json")))
AXIS = np.array(d["lv_geometry"]["axis_base_to_apex"]); MV_C = np.array(d["design"]["mv_centre_mm"]); AV_C = np.array(d["design"]["av_centre_mm"])
A_dir = AV_C - MV_C; A_dir -= (A_dir @ AXIS) * AXIS; A_dir /= np.linalg.norm(A_dir)
Z_up = -AXIS; Y_dir = np.cross(Z_up, A_dir)
R = np.vstack([A_dir, Y_dir, Z_up])                       # world -> anatomical (rows)
FACE_BUDGET = 45000
DPI = int(os.environ.get("SHOWCASE_DPI", "110")); SUF = "" if DPI == 110 else "_hi"

COL = dict(myo=(0.80, 0.30, 0.30), plate=(0.62, 0.62, 0.66), valve=(0.93, 0.86, 0.72), chordae=(0.97, 0.95, 0.90),
           blood=(0.30, 0.50, 0.85), core=(0.45, 0.65, 0.90), box=(0.35, 0.35, 0.40), cut=(0.80, 0.30, 0.30))


def load(path, budget=FACE_BUDGET):
    m = trimesh.load(path, process=True)
    if len(m.faces) > budget: m = m.simplify_quadric_decimation(face_count=budget)
    m.vertices = (m.vertices - MV_C) @ R.T                 # into the anatomical frame
    return m


def add(ax, m, col, alpha=1.0, light=(0.35, -0.55, 0.75)):
    tri = m.vertices[m.faces]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]); n /= (np.linalg.norm(n, axis=1)[:, None] + 1e-12)
    l = np.array(light, float); l /= np.linalg.norm(l)
    shade = 0.28 + 0.72 * np.clip(np.abs(n @ l), 0, 1) ** 0.9  # two-sided (cut faces / open sheets)
    fc = np.c_[np.outer(shade, col), np.full(len(shade), alpha)]
    pc = Poly3DCollection(tri, facecolors=fc, edgecolors="none"); ax.add_collection3d(pc); return tri


def frame_axes(ax, pts, elev, azim, pad=1.04):
    lo, hi = pts.min(0), pts.max(0); c = (lo + hi) / 2; r = (hi - lo).max() / 2 * pad
    ax.set_xlim(c[0] - r, c[0] + r); ax.set_ylim(c[1] - r, c[1] + r); ax.set_zlim(c[2] - r, c[2] + r)
    ax.set_box_aspect((1, 1, 1)); ax.set_proj_type("ortho"); ax.view_init(elev=elev, azim=azim); ax.set_axis_off()


def panel(k):
    fig = plt.figure(figsize=(7.2, 7.2), dpi=DPI); ax = fig.add_subplot(111, projection="3d"); allpts = []
    if k == 1:   # exterior, by part
        for f, col in ((os.path.join(CT, "LV_myocardium_CT_smooth.stl"), COL["myo"]), (os.path.join(FA, "av_plane_plate.stl"), COL["plate"]),
                       (os.path.join(BO, "mitral_valve.stl"), COL["valve"]), (os.path.join(BO, "aortic_valve.stl"), COL["valve"])):
            m = load(f, 30000); allpts.append(add(ax, m, col).reshape(-1, 3))
        elev, azim, title = 22, -55, "v4 exterior — CT myocardium (red), AV-plane plate (grey), parametric valves (cream)"
    elif k in (2, 3):
        tag = "A" if k == 2 else "B"
        m = load(os.path.join(BO, f"hollow_v4_cutaway_{tag}.stl"), 70000)
        allpts.append(add(ax, m, COL["cut"], light=(0.2, 0.35 if tag == "A" else -0.35, 0.9)).reshape(-1, 3))
        elev, azim = 8, (90 if tag == "A" else -90)   # camera on the cut-face side
        title = f"v4 cut-away {tag} — patient's trabeculae and papillary muscle, chordae to the leaflets"
    elif k == 4:  # slab
        v4 = trimesh.load(os.path.join(BO, "hollow_ventricle_v4_CT.stl"), process=True)
        apex = float(((trimesh.load(os.path.join(CT, "lv_bloodpool_CT_smooth.stl"), process=False).vertices - MV_C) @ AXIS).max())
        zc = MV_C + 0.5 * apex * AXIS
        T = trimesh.geometry.align_vectors([0, 0, 1], AXIS); T[:3, 3] = zc
        box = trimesh.creation.box(extents=[200, 200, 16], transform=T)
        slab = trimesh.boolean.intersection([v4, box], engine="manifold")
        slab.vertices = (slab.vertices - MV_C) @ R.T
        if len(slab.faces) > 70000: slab = slab.simplify_quadric_decimation(face_count=70000)
        allpts.append(add(ax, slab, COL["myo"], light=(0.3, -0.4, 0.85)).reshape(-1, 3))
        elev, azim, title = 62, -60, "v4 mid-cavity slab (16 mm) — wall, both papillary muscles and trabeculae, seen from the base"
    elif k == 5:
        core = load(os.path.join(PH, "core_LV_with_ports.stl"), 30000); allpts.append(add(ax, core, COL["core"]).reshape(-1, 3))
        box = load(os.path.join(PH, "mould_box.stl"), 5000)
        # box as edges only so the core stays visible
        lo, hi = box.bounds; import itertools
        corners = np.array(list(itertools.product(*zip(lo, hi))))
        for i, j in itertools.combinations(range(8), 2):
            if np.sum(corners[i] != corners[j]) == 1:      # edge = corners differing in one axis
                ax.plot(*zip(corners[i], corners[j]), color=COL["box"], lw=0.9, alpha=0.8)
        allpts.append(corners)
        elev, azim, title = 18, -50, "lost-core flow phantom — PVA core (blood pool + Ø19/Ø15.8 ports) inside the mould box"
    elif k == 6:
        m = load(os.path.join(CT, "lv_bloodpool_CT_smooth.stl"), 60000); allpts.append(add(ax, m, COL["blood"]).reshape(-1, 3))
        elev, azim, title = 18, -40, "true blood pool from the CT (132.5 mL) — papillary and trabecular imprints on the surface"
    frame_axes(ax, np.vstack(allpts), elev, azim)
    fig.text(0.5, 0.03, title, ha="center", va="bottom", fontsize=9.5, color="0.2", wrap=True)
    out = os.path.join(BO, f"showcase_p{k}{SUF}.png"); plt.savefig(out, dpi=DPI, facecolor="white"); plt.close(fig); print("saved", out)


def compose():
    from PIL import Image, ImageDraw
    ims = [Image.open(os.path.join(BO, f"showcase_p{k}.png")).convert("RGB") for k in range(1, 7)]
    w, h = ims[0].size; W, H = 3 * w, 2 * h + 70
    canvas = Image.new("RGB", (W, H), "white"); dr = ImageDraw.Draw(canvas)
    for i, im in enumerate(ims):
        canvas.paste(im, ((i % 3) * w, 70 + (i // 3) * h))
    dr.text((24, 18), "Case 1009 left ventricle — state on 2026-09-16: v4 solid (patient wall/interior + parametric valves), flow-phantom core, CT blood pool",
            fill=(30, 30, 30))
    dr.text((24, 40), "software render (matplotlib, Lambert). Basal side up in every panel. Idealised parts are named; everything else is the patient's CT.", fill=(90, 90, 90))
    out = os.path.join(BO, "showcase_2026-09-16.png"); canvas.save(out, optimize=True); print("saved", out, canvas.size)


if __name__ == "__main__":
    a = sys.argv[1] if len(sys.argv) > 1 else "compose"
    compose() if a == "compose" else panel(int(a))
