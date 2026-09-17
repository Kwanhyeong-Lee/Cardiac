# -*- coding: utf-8 -*-
"""Step 22 -- whole-heart teaching model of a case, from the 7 MM-WHS labels + the coronary tree.

Two deliverables (case working frame: frame A for 1009, world otherwise; mm):
  parts/  one smooth solid per label (continuous-field iso-surface, largest component):
          LV_myocardium (205), LV_cavity (500), RV (600), LA (420), RA (550), aorta (820), PA (850)
          -> the classic "blood-pool cast" teaching set, print each in its own colour
  whole_heart_shell.stl              exterior shell = LV myocardium u LV cavity u the other blood pools grown by a
                                     SYNTHETIC wall (RV 3.0 mm, atria 2.0 mm, great vessels 1.5 mm -- MM-WHS labels
                                     only segment the LV wall), smoothed; one watertight solid
  whole_heart_with_coronaries.stl    shell u coronary tubes (CT/<case>/coronary/coronary_tree_print_frameA.stl,
                                     min diameter 2 mm) via manifold union -> the printable "heart with arteries"
Honesty labels: LV wall/cavity, chambers, great vessels and coronary routes are the patient's; RV/atrial/great-vessel
WALL THICKNESS is synthetic (uniform); valves are not included (see v5 for the LV valves).
Fine CTs are worked at ~0.7 mm (label downsampling) so the whole-heart field fits in memory; the LV parts of the v5
pipeline stay at full resolution.  Stages are cached: rerun the command until it prints DONE.
Env: CASE, CARDIAC_DATA.   Usage: CASE=1001 python build_whole_heart.py [--stage parts|shell|union|render|all]
"""
import os, sys, json, time, warnings
import numpy as np, nibabel as nib, trimesh
from scipy import ndimage
from skimage import measure
from trimesh.smoothing import filter_taubin
from case_paths import paths, geometry, dist_to
warnings.filterwarnings("ignore")
P = paths(); G = geometry()
EXT = os.path.join(P["base"], "labels_extended.npz")                         # from ct_great_vessels.py (step 24), if present
USE_EXT = os.path.exists(EXT) and os.environ.get("NO_EXT") != "1"
OUT = P["whole"] + ("_ext" if USE_EXT else ""); PARTS = os.path.join(OUT, "parts"); os.makedirs(PARTS, exist_ok=True)
LABELS = {205: "LV_myocardium", 500: "LV_cavity", 600: "RV", 420: "LA", 550: "RA", 820: "aorta", 850: "PA"}
if USE_EXT: LABELS.update({901: "pulmonary_veins", 902: "SVC", 903: "IVC"})
WALL = {600: 3.0, 420: 2.0, 550: 2.0, 820: 1.5, 850: 1.5, 901: 1.5, 902: 1.5, 903: 1.5}
TARGET_PART, TARGET_SHELL, MARGIN_MM, TARGET_MM = 150000, 400000, 8.0, 0.7
COL = {"LV_myocardium": (0.80, 0.30, 0.30), "LV_cavity": (0.85, 0.15, 0.15), "RV": (0.25, 0.45, 0.85), "LA": (0.90, 0.55, 0.55), "RA": (0.45, 0.65, 0.90), "aorta": (0.90, 0.35, 0.25), "PA": (0.35, 0.55, 0.80),
       "pulmonary_veins": (0.95, 0.70, 0.70), "SVC": (0.55, 0.75, 0.95), "IVC": (0.35, 0.60, 0.75)}
stage = sys.argv[sys.argv.index("--stage") + 1] if "--stage" in sys.argv else "all"
t0 = time.time()


def load_labels():
    if USE_EXT:                                                                  # already ~1 mm, great vessels grown from the CT
        z = np.load(EXT); L = z["L"].astype(np.int16); A = z["affine"]; sp = np.array(z["spacing"], float); ds = np.ones(3, int)
        idx = np.argwhere(L > 0); m = np.ceil(MARGIN_MM / sp).astype(int)
        lo = np.maximum(idx.min(0) - m, 0); hi = np.minimum(idx.max(0) + m + 1, L.shape); sl = tuple(slice(a, b) for a, b in zip(lo, hi))
        return L[sl], A, sp, lo, ds
    lab = nib.load(P["label"]); A = lab.affine.copy(); sp = np.array(lab.header.get_zooms()[:3], float)
    L = np.asanyarray(lab.dataobj).astype(np.int16)
    ds = np.maximum(1, np.round(TARGET_MM / sp)).astype(int)                     # per-axis label downsampling to ~0.7 mm
    L = L[::ds[0], ::ds[1], ::ds[2]]; sp = sp * ds; A[:3, :3] = A[:3, :3] * ds[None, :]
    idx = np.argwhere(L > 0); m = np.ceil(MARGIN_MM / sp).astype(int)
    lo = np.maximum(idx.min(0) - m, 0); hi = np.minimum(idx.max(0) + m + 1, L.shape); sl = tuple(slice(a, b) for a, b in zip(lo, hi))
    return L[sl], A, sp, lo, ds


def to_frame(v_idx, A, lo):
    return trimesh.transform_points(np.asarray(v_idx, float) + lo, A) + np.asarray(G["T"])[:3, 3]


def iso_solid(mask, A, sp, lo, sigma=1.0, target=150000, taubin=8, step=1, keep_min_mL=None):
    f = ndimage.gaussian_filter(np.pad(mask, 2).astype(np.float32), (sigma, sigma, sigma * sp[0] / sp[2]))
    v, fc, _, _ = measure.marching_cubes(f, level=0.5, spacing=(1, 1, 1), step_size=step)
    m = trimesh.Trimesh(to_frame(v - 2, A, lo), fc, process=True); trimesh.repair.fix_normals(m)
    parts = m.split(only_watertight=False)
    if len(parts) > 1:                       # chambers: largest component; vessels (keep_min_mL): every piece above the size floor
        m = max(parts, key=lambda q: abs(q.volume)) if keep_min_mL is None else trimesh.util.concatenate([q for q in parts if abs(q.volume) / 1000 >= keep_min_mL] or [max(parts, key=lambda q: abs(q.volume))])
    filter_taubin(m, lamb=0.5, nu=-0.53, iterations=taubin)
    if len(m.faces) > target: m = m.simplify_quadric_decimation(face_count=target)
    if not m.is_watertight:
        import pymeshfix
        vc, fcc = pymeshfix.clean_from_arrays(np.ascontiguousarray(m.vertices, dtype=np.float64), np.ascontiguousarray(m.faces, dtype=np.int32)); m = trimesh.Trimesh(vc, fcc, process=True)
    trimesh.repair.fix_normals(m); return m


def stage_parts(L, A, sp, lo):
    rep = {}
    for k, name in LABELS.items():
        out = os.path.join(PARTS, f"{name}.stl")
        if os.path.exists(out) or os.path.exists(out + ".missing"): rep[name] = "cached"; continue
        if not (L == k).any(): rep[name] = "label missing"; open(out + ".missing", "w").write("label absent in this case\n"); continue
        m = iso_solid(L == k, A, sp, lo, target=TARGET_PART, keep_min_mL=(0.3 if k in (820, 850, 901, 902, 903) else None)); m.export(out)
        rep[name] = dict(faces=int(len(m.faces)), volume_mL=round(float(abs(m.volume)) / 1000, 1), watertight=bool(m.is_watertight))
        print(f"part {name}: {rep[name]}  ({time.time()-t0:.0f}s)")
        if time.time() - t0 > 130: print("time budget -> rerun for the remaining parts"); break
    return rep


def stage_shell(L, A, sp, lo):
    out = os.path.join(OUT, "whole_heart_shell.stl")
    if os.path.exists(out): return "cached"
    shell = (L == 205) | (L == 500)
    for k, w in WALL.items():
        if (L == k).any(): shell |= dist_to(L == k, sp) <= w
    m = iso_solid(shell, A, sp, lo, sigma=1.2, target=TARGET_SHELL, taubin=10); m.export(out)
    r = dict(faces=int(len(m.faces)), volume_mL=round(float(abs(m.volume)) / 1000, 1), watertight=bool(m.is_watertight)); print("shell:", r, f"({time.time()-t0:.0f}s)"); return r


def stage_union():
    out = os.path.join(OUT, "whole_heart_with_coronaries.stl"); tube_p = os.path.join(P["coronary"], "coronary_tree_print_frameA.stl")
    if os.path.exists(out): return "cached"
    if not os.path.exists(tube_p): return "no coronary tube model (run ct_coronary_finalize.py first)"
    shell = trimesh.load(os.path.join(OUT, "whole_heart_shell.stl"), process=True); tube = trimesh.load(tube_p, process=True)
    for m in (shell, tube):
        if not m.is_volume: trimesh.repair.fix_normals(m)
    u = trimesh.boolean.union([shell, tube], engine="manifold"); comps = u.split(only_watertight=False)
    # how much of the tree stays outside the shell (visible after the union): volume bookkeeping, no ray casting
    vis = float(np.clip((abs(u.volume) - abs(shell.volume)) / max(abs(tube.volume), 1e-6), 0, 1))
    u.export(out)
    r = dict(faces=int(len(u.faces)), volume_mL=round(float(abs(u.volume)) / 1000, 1), watertight=bool(u.is_watertight), components=len(comps), coronary_volume_outside_shell_frac=round(vis, 2))
    print("union:", r, f"({time.time()-t0:.0f}s)"); return r


def dec(m, n):
    return m.simplify_quadric_decimation(face_count=n) if len(m.faces) > n else m


def stage_render():
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    u_p = os.path.join(OUT, "whole_heart_with_coronaries.stl"); tube_p = os.path.join(P["coronary"], "coronary_tree_print_frameA.stl")
    shell = dec(trimesh.load(os.path.join(OUT, "whole_heart_shell.stl"), process=False), 60000)
    tube = dec(trimesh.load(tube_p, process=False), 20000) if os.path.exists(tube_p) else None
    parts = {n: dec(trimesh.load(os.path.join(PARTS, f"{n}.stl"), process=False), 25000) for n in LABELS.values() if os.path.exists(os.path.join(PARTS, f"{n}.stl"))}
    fig = plt.figure(figsize=(20, 11))
    def draw(ax, meshes_cols, elev, azim, title):
        ax.set_proj_type("ortho"); light = np.array([np.cos(np.radians(elev)) * np.cos(np.radians(azim)), np.cos(np.radians(elev)) * np.sin(np.radians(azim)), np.sin(np.radians(elev))])
        tris, cols = [], []
        for m, c in meshes_cols:
            keep = m.face_normals @ light > -0.15; lam = np.clip(m.face_normals[keep] @ light, 0, 1) * 0.7 + 0.3      # keep grazing faces: no pinholes
            tris.append(m.triangles[keep]); cols.append(np.c_[np.tile(c, (int(keep.sum()), 1)) * lam[:, None], np.ones(int(keep.sum()))])
        tri = np.concatenate(tris); col = np.concatenate(cols)
        ax.add_collection3d(Poly3DCollection(tri, facecolors=col, edgecolors=col, linewidths=0.2, antialiased=False))
        b = np.concatenate([m.bounds for m, _ in meshes_cols]); c = (b.min(0) + b.max(0)) / 2; r = (b.max(0) - b.min(0)).max() / 2 * 0.95
        ax.set_xlim(c[0] - r, c[0] + r); ax.set_ylim(c[1] - r, c[1] + r); ax.set_zlim(c[2] - r, c[2] + r); ax.view_init(elev=elev, azim=azim); ax.set_box_aspect((1, 1, 1)); ax.set_axis_off(); ax.set_title(title, fontsize=10)
    ext = [(shell, (0.88, 0.80, 0.76))] + ([(tube, (0.75, 0.05, 0.05))] if tube is not None else [])
    cast = [(m, COL[n]) for n, m in parts.items() if n != "LV_myocardium"]          # casts = blood pools; the LV wall would hide its own cavity
    for i, (elev, azim, t) in enumerate([(10, 90, "anterior"), (10, 180, "left lateral"), (-55, 100, "inferior")]):
        draw(fig.add_subplot(2, 3, 1 + i, projection="3d"), ext, elev, azim, f"whole heart with coronary arteries — {t}")
        draw(fig.add_subplot(2, 3, 4 + i, projection="3d"), cast, elev, azim, f"chamber casts (label solids) — {t}")
    plt.suptitle(f"case {P['case']} whole-heart teaching model — top: shell (patient LV wall; RV/atrial/great-vessel walls synthetic 3/2/1.5 mm) u coronary tubes; "
                 f"bottom: chamber casts — LV cavity (red), RV (blue), LA (pink), RA (light blue), aorta, PA" + (", pulmonary veins, SVC, IVC (grown from the CT, step 24)" if USE_EXT else "") + "; LV_myocardium.stl is a separate part", fontsize=11)
    plt.tight_layout(); plt.savefig(os.path.join(OUT, "whole_heart_render.png"), dpi=80); print("render done", f"({time.time()-t0:.0f}s)")


def main():
    rep_p = os.path.join(OUT, "whole_heart_report.json"); rep = json.load(open(rep_p)) if os.path.exists(rep_p) else dict(case=P["case"], frame=G["frame"], synthetic_wall_mm=WALL, label_downsample_target_mm=TARGET_MM, extended_labels=USE_EXT)
    need_labels = stage in ("parts", "shell", "all")
    if need_labels:
        L, A, sp, lo, ds = load_labels(); rep["label_downsample"] = ds.tolist(); rep["working_voxel_mm"] = sp.round(3).tolist(); print(f"labels {L.shape} at {sp.round(2)} mm (downsample {ds})  ({time.time()-t0:.0f}s)")
    if stage in ("parts", "all"):
        r = stage_parts(L, A, sp, lo); rep.setdefault("parts", {}).update({k: v for k, v in r.items() if v != "cached"})
        if not all(os.path.exists(os.path.join(PARTS, f"{n}.stl")) or os.path.exists(os.path.join(PARTS, f"{n}.stl.missing")) for n in LABELS.values()):
            json.dump(rep, open(rep_p, "w"), indent=1); print("parts incomplete -- rerun"); return
    if stage in ("shell", "all") and time.time() - t0 < 120:
        r = stage_shell(L, A, sp, lo); rep["shell"] = rep.get("shell") if r == "cached" else r
    if stage in ("union", "all") and os.path.exists(os.path.join(OUT, "whole_heart_shell.stl")) and time.time() - t0 < 120:
        r = stage_union(); rep["union"] = rep.get("union") if r == "cached" else r
    json.dump(rep, open(rep_p, "w"), indent=1)
    done = all(os.path.exists(os.path.join(OUT, f)) for f in ("whole_heart_shell.stl", "whole_heart_with_coronaries.stl"))
    if stage in ("render", "all") and done and time.time() - t0 < 110:
        stage_render(); print("DONE ->", OUT)
    elif not done: print("not finished -- rerun the same command (stages are cached)")


if __name__ == "__main__":
    main()
