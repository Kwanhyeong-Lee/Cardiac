# -*- coding: utf-8 -*-
"""Step 3 -- deliverables from the coronary segmentation (frame A, mm):
  * coronary_tree_print_frameA.stl : tube sweep along the centrelines with radius max(r, R_MIN) -> every branch
                                     printable (min diameter 2 mm), smooth, watertight
  * coronary_render.png            : tree on the whole-heart label surface, coloured by vessel name
  * summary printed + written into coronary.json['deliverables']"""
import os, json, numpy as np, trimesh
from scipy import ndimage
from skimage import measure
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from case_paths import paths as _paths
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = _paths()["coronary"]; R_MIN, VOX = 1.0, 0.25
d = json.load(open(os.path.join(OUT, "coronary.json")))
COL = {"LM": (0.55, 0.0, 0.0), "LAD": (0.85, 0.1, 0.1), "D": (0.95, 0.45, 0.55), "LCx": (0.95, 0.55, 0.1), "OM": (0.98, 0.75, 0.4), "RI": (0.6, 0.3, 0.7),
       "RCA": (0.15, 0.35, 0.85), "PDA": (0.1, 0.6, 0.8), "PLV": (0.45, 0.6, 0.9), "RV-br": (0.55, 0.65, 0.75), "branch": (0.9, 0.4, 0.6), "RCA-ostial": (0.15, 0.35, 0.85)}

# ---- tube model ----
pts, rad, names = [], [], []
for cid, cl in d["centrelines"].items():
    P = np.array(cl["pts"]); r = np.maximum(np.array(cl["r_mm"]), R_MIN)
    if len(P) < 2: continue
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1); s = np.r_[0, np.cumsum(seg)]; ss = np.arange(0, s[-1] + 1e-6, VOX)
    Pi = np.c_[[np.interp(ss, s, P[:, k]) for k in range(3)]].T; ri = np.interp(ss, s, r)
    pts.append(Pi); rad.append(ri); names += [cl["name"]] * len(Pi)
pts = np.concatenate(pts); rad = np.concatenate(rad); names = np.array(names)
lo = pts.min(0) - 4; hi = pts.max(0) + 4; shape = np.ceil((hi - lo) / VOX).astype(int) + 1
grid = np.zeros(shape, bool)
gi = ((pts - lo) / VOX).round().astype(int); rmax = int(np.ceil(rad.max() / VOX)) + 1
offs = np.argwhere(np.ones((2 * rmax + 1,) * 3)) - rmax; od = np.linalg.norm(offs, axis=1) * VOX
for c, r in zip(gi, rad):
    o = offs[od <= r]; q = c + o; q = q[(q >= 0).all(1) & (q < shape).all(1)]; grid[tuple(q.T)] = True
f = ndimage.gaussian_filter(grid.astype(np.float32), 1.2)
v, fc, _, _ = measure.marching_cubes(f, level=0.5, spacing=(VOX,) * 3)
tube = trimesh.Trimesh(v + lo, fc, process=True); trimesh.repair.fix_normals(tube)
tube = trimesh.smoothing.filter_taubin(tube, lamb=0.5, nu=-0.53, iterations=10)
tube.export(os.path.join(OUT, "coronary_tree_print_frameA.stl"))
print(f"tube model: {len(tube.faces)} faces, watertight {tube.is_watertight}, volume {tube.volume/1000:.2f} mL, bbox {tube.extents.round(1)} mm")

# ---- render by name ----
seg = trimesh.load(os.path.join(OUT, "coronary_tree_frameA.stl"), process=False)
heart = trimesh.load(os.path.join(OUT, "heart_labels_context_frameA.stl"), process=False)
from scipy.spatial import cKDTree
kd = cKDTree(pts); _, idx = kd.query(tube.triangles_center); face_name = names[idx]
def shade(mesh, light, cols):
    n = mesh.face_normals; lam = np.clip(n @ light, 0, 1) * 0.7 + 0.3
    return np.c_[cols * lam[:, None], np.ones(len(n))]
def view(ax, elev, azim, title):
    light = np.array([np.cos(np.radians(elev)) * np.cos(np.radians(azim)), np.cos(np.radians(elev)) * np.sin(np.radians(azim)), np.sin(np.radians(elev))])
    tcols = np.array([COL.get(nm_, COL["branch"]) for nm_ in face_name])
    tri = np.concatenate([heart.triangles, tube.triangles]); col = np.concatenate([shade(heart, light, np.tile([0.88, 0.86, 0.84], (len(heart.faces), 1))), shade(tube, light, tcols)])
    ax.add_collection3d(Poly3DCollection(tri, facecolors=col, edgecolors="none"))
    lo_, hi_ = heart.bounds; c = (lo_ + hi_) / 2; r = (hi_ - lo_).max() / 2
    ax.set_xlim(c[0] - r, c[0] + r); ax.set_ylim(c[1] - r, c[1] + r); ax.set_zlim(c[2] - r, c[2] + r)
    ax.view_init(elev=elev, azim=azim); ax.set_box_aspect((1, 1, 1)); ax.set_axis_off(); ax.set_title(title, fontsize=10)
fig = plt.figure(figsize=(20, 12))
for i, (e, a, t) in enumerate([(10, 90, "anterior"), (10, 140, "left anterior oblique"), (10, 185, "left lateral"), (-55, 100, "inferior"), (15, 40, "right anterior oblique"), (55, 110, "superior (base)")]):
    view(fig.add_subplot(2, 3, i + 1, projection="3d"), e, a, t)
tot = d["length_by_name_mm"]
side = sum(tot.get(k, 0) for k in ("D", "OM", "RI", "PLV", "RV-br", "branch"))
plt.suptitle(f"case {d.get('case', '?')} coronary arteries from CT ({d.get('frame', '')})  --  LM {tot.get('LM',0)} / LAD {tot.get('LAD',0)} / LCx {tot.get('LCx',0)} / RCA {tot.get('RCA',0)} / PDA {tot.get('PDA',0)} / side branches {side:.0f} mm centreline;  "
             f"dark red LM, red LAD (pink D), orange LCx (light OM), blue RCA (cyan PDA, light PLV); tubes >= {2*R_MIN:.0f} mm for printing", fontsize=10)
plt.tight_layout(); plt.savefig(os.path.join(OUT, "coronary_render.png"), dpi=80)

d["deliverables"] = dict(segmentation_stl="coronary_tree_frameA.stl", print_stl="coronary_tree_print_frameA.stl", print_min_diameter_mm=2 * R_MIN,
                         print_faces=int(len(tube.faces)), print_watertight=bool(tube.is_watertight), print_volume_mL=round(tube.volume / 1000, 2),
                         qa_figures=["coronary_cpr.png", "coronary_xsec.png", "coronary_render.png", "coronary_mip.png", "rca_axial.png"])
json.dump(d, open(os.path.join(OUT, "coronary.json"), "w"), indent=1); print("ok")
