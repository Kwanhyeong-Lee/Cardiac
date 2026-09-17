# -*- coding: utf-8 -*-
"""Step 19 -- high-fidelity LV parts straight from the CT (replaces the stair-stepped binary-mask
meshes behind v4 when smoothness matters: prints, renders, CFD walls).

Why the old parts look rough: ct_refine_lv.py ran marching cubes on BINARY masks (0.49 x 0.49 x
0.63 mm voxels -> staircase), then ct_prepare_parts.py did 10 Taubin passes and decimated to 320k
faces -- the staircase survives as faceting.  Here the iso-surfaces come from CONTINUOUS fields, so
the boundary is located at sub-voxel precision and is smooth by construction:

    L    = gaussian(label 500 u 205, SIG_L)   -- smooth epicardial / basal boundary  (label is manual)
    L500 = gaussian(label 500, SIG_L)
    Hs   = gaussian(HU, SIG_H)                -- the blood/muscle interface is a real image edge
    F_blood = min(L500 - 0.5, (Hs - thr) / 200)          > 0  inside the contrast-filled cavity
    F_myo   = min(L - 0.5, -F_blood)                      > 0  wall + papillary muscles + trabeculae
    thr = Otsu threshold from ct_refine.json (235 HU)

Islands (dark noise specks in the pool -> floating 'muscle', bright specks -> bubbles) are dropped by
keeping the largest connected component of each iso-surface; nothing is thresholded twice.
Then Taubin (TAUBIN passes), quadric decimation to TARGET_*, pymeshfix if needed, frame A.

Quality report (CT/hires/hires_report.json + hires_closeup.png): roughness amplitude = RMS distance
of vertices to a heavily smoothed copy (2 mm scale), old vs new; volumes; mean surface distance
old->new (must stay < 0.4 mm: same anatomy, better surface).

Env (defaults fit the 3 GB sandbox; on the 32 GB PC use TARGET_MYO=1500000 TARGET_BLOOD=800000 TAUBIN=15):
  CARDIAC_DATA  MM-WHS/ct_train dir      SIG_L, SIG_H (voxels)      TARGET_MYO, TARGET_BLOOD, TAUBIN
"""
import os, json, time, warnings
import numpy as np, nibabel as nib, trimesh
from scipy import ndimage
from skimage import measure
from trimesh.smoothing import filter_taubin
warnings.filterwarnings("ignore")
from case_paths import paths as _paths, geometry as _geometry, MMWHS
_P = _paths(); _G = _geometry()
HERE = os.path.dirname(os.path.abspath(__file__)); CT = os.path.join(HERE, "CT"); OUT = _P["hires"]; os.makedirs(OUT, exist_ok=True); CASE = _P["case"]
SIG_L, SIG_H = float(os.environ.get("SIG_L", 1.0)), float(os.environ.get("SIG_H", 0.6))
TARGET_MYO, TARGET_BLOOD, TAUBIN = int(os.environ.get("TARGET_MYO", 800000)), int(os.environ.get("TARGET_BLOOD", 400000)), int(os.environ.get("TAUBIN", 10))
MARGIN_VOX = 12


def largest(mesh):
    parts = mesh.split(only_watertight=False)
    if len(parts) <= 1: return mesh, 0
    parts = sorted(parts, key=lambda m: -abs(m.volume)); return parts[0], len(parts) - 1


def finish(mesh, target, tag):
    t = time.time(); v0 = abs(mesh.volume) / 1000
    filter_taubin(mesh, lamb=0.5, nu=-0.53, iterations=TAUBIN)
    if len(mesh.faces) > target: mesh = mesh.simplify_quadric_decimation(face_count=target)
    if not mesh.is_watertight:
        import pymeshfix
        vc, fc = pymeshfix.clean_from_arrays(np.ascontiguousarray(mesh.vertices, dtype=np.float64), np.ascontiguousarray(mesh.faces, dtype=np.int32))
        mesh = trimesh.Trimesh(vc, fc, process=True)
    trimesh.repair.fix_normals(mesh)
    print(f"{tag}: {v0:.1f} -> {abs(mesh.volume)/1000:.1f} mL, {len(mesh.faces):,} f, watertight {mesh.is_watertight}  ({time.time()-t:.0f}s)")
    return mesh


def roughness_mm(mesh, n=20000):
    """voxel-scale roughness: RMS distance of the vertices to a lightly smoothed copy (6 Taubin passes
    ~ 1 mm scale). Stair-steps zig-zag at 0.5 mm and show up here; real anatomy (>2 mm) does not."""
    m = mesh.copy(); sm = mesh.copy(); filter_taubin(sm, lamb=0.5, nu=-0.53, iterations=6)
    rng = np.random.default_rng(0); vi = rng.choice(len(m.vertices), size=min(n, len(m.vertices)), replace=False)
    return float(np.sqrt(((m.vertices[vi] - sm.vertices[vi]) ** 2).sum(1).mean()))


def closeups(myo_new, blood_new):
    """same camera, same 24 mm patch, flat Lambert shading (facets show as shading jumps): old vs new."""
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    AXIS = np.array(_G["axis"]); MV_C = np.array(_G["mv_centre"])
    old_myo = trimesh.load(os.path.join(CT, "LV_myocardium_CT_smooth.stl"), process=False); old_bl = trimesh.load(os.path.join(CT, "lv_bloodpool_CT_smooth.stl"), process=False)
    apex = MV_C + AXIS * 0.9 * float(((blood_new.vertices - MV_C) @ AXIS).max())
    # patch 1: epicardium, mid-ventricle, direction +y (anterior); patch 2: endocardium (blood-pool surface) near the apex
    mid = MV_C + AXIS * 45.0; ant = np.array([0, 1.0, 0]); ant -= (ant @ AXIS) * AXIS; ant /= np.linalg.norm(ant)
    c1 = mid + ant * 40.0; c2 = apex
    HALF = 12.0
    def patch(mesh, c, half):
        cen = mesh.triangles_center; keep = np.all(np.abs(cen - c) <= half, axis=1); return mesh.triangles[keep], mesh.face_normals[keep]
    fig, axes = plt.subplots(2, 2, figsize=(12, 12))
    rows = [("epicardium 24 mm patch", old_myo, myo_new, c1, -ant), ("endocardium (blood-pool surface) at the apex, 24 mm", old_bl, blood_new, c2, AXIS)]
    for r, (title, old, new, c, viewdir) in enumerate(rows):
        for k, (tag, mesh) in enumerate([("OLD  binary-mask marching cubes + Taubin10 + decimation", old), ("NEW  continuous-field iso-surface", new)]):
            tri, nrm = patch(mesh, c, HALF + 4)
            light = -viewdir / np.linalg.norm(viewdir); light = light + 0.35 * np.cross(light, AXIS); light /= np.linalg.norm(light)
            lam = np.clip(np.abs(nrm @ light), 0, 1) * 0.8 + 0.2          # two-sided (endocardium seen from inside)
            # orthographic projection onto the plane perpendicular to viewdir; far triangles first
            u = np.cross(viewdir, AXIS if abs(viewdir @ AXIS) < 0.9 else [1, 0, 0]); u /= np.linalg.norm(u); v = np.cross(viewdir, u)
            P = (tri - c) @ np.c_[u, v]; depth = ((tri - c) @ viewdir).mean(1); order = np.argsort(-depth)
            ax = axes[r, k]
            from matplotlib.collections import PolyCollection
            cols = np.c_[np.tile(lam[order], (3, 1)).T * [0.85, 0.75, 0.7], np.ones(len(order))]
            ax.add_collection(PolyCollection(P[order], facecolors=cols, edgecolors=cols, linewidths=0.3, antialiased=False))
            ax.set_xlim(-HALF, HALF); ax.set_ylim(-HALF, HALF); ax.set_aspect("equal"); ax.set_axis_off(); ax.set_title(f"{tag}\n{title}  ({len(mesh.faces):,} faces total)", fontsize=9)
    plt.tight_layout(); plt.savefig(os.path.join(OUT, "hires_closeup.png"), dpi=90); plt.close(fig)


def main():
    t0 = time.time()
    img = nib.load(os.path.join(MMWHS, f"ct_train_{CASE}_image.nii.gz")); lab = nib.load(os.path.join(MMWHS, f"ct_train_{CASE}_label.nii.gz"))
    A = img.affine; sp = np.array(img.header.get_zooms()[:3])
    thr = float(_G["thr_HU"]); T = np.array(_G["T"])
    L = np.asanyarray(lab.dataobj); lv = (L == 500) | (L == 205)
    idx = np.argwhere(lv); lo = np.maximum(idx.min(0) - MARGIN_VOX, 0); hi = np.minimum(idx.max(0) + MARGIN_VOX + 1, L.shape); sl = tuple(slice(a, b) for a, b in zip(lo, hi))
    Lc = np.asarray(L[sl]); del L, lv, idx
    I = np.asanyarray(img.dataobj)[sl].astype(np.float32)
    cav = (Lc == 500).astype(np.float32); both = ((Lc == 500) | (Lc == 205)).astype(np.float32); del Lc
    sig_vox = lambda s: (s, s, s * sp[0] / sp[2])                 # isotropic in mm
    Lf = ndimage.gaussian_filter(both, sig_vox(SIG_L)); L5 = ndimage.gaussian_filter(cav, sig_vox(SIG_L)); Hs = ndimage.gaussian_filter(I, sig_vox(SIG_H)); del both, cav, I
    F_blood = np.minimum(L5 - 0.5, (Hs - thr) / 200.0); del L5, Hs
    F_myo = np.minimum(Lf - 0.5, -F_blood); del Lf
    print(f"crop {F_myo.shape}, thr {thr:.0f} HU, fields ready ({time.time()-t0:.0f}s)")

    def iso(F, tag):
        v, f, _, _ = measure.marching_cubes(F, level=0.0, spacing=(1, 1, 1))
        w = trimesh.transform_points(v + lo, A) + T[:3, 3]           # index -> world -> frame A (pure translation)
        m = trimesh.Trimesh(w, f, process=True); trimesh.repair.fix_normals(m)
        m, dropped = largest(m)
        print(f"{tag}: iso-surface {len(m.faces):,} f, {abs(m.volume)/1000:.1f} mL, dropped {dropped} island(s)  ({time.time()-t0:.0f}s)")
        return m
    myo_raw = iso(F_myo, "myoCT"); del F_myo
    blood_raw = iso(F_blood, "blood"); del F_blood
    myo = finish(myo_raw, TARGET_MYO, "myoCT hires"); myo.export(os.path.join(OUT, "LV_myocardium_CT_hires.stl"))
    blood = finish(blood_raw, TARGET_BLOOD, "blood hires"); blood.export(os.path.join(OUT, "lv_bloodpool_CT_hires.stl"))

    # ---- report: old vs new ----
    rep = dict(case=CASE, frame=_G["frame"], params=dict(SIG_L=SIG_L, SIG_H=SIG_H, TARGET_MYO=TARGET_MYO, TARGET_BLOOD=TARGET_BLOOD, TAUBIN=TAUBIN, thr_HU=thr), parts={})
    if not os.path.exists(os.path.join(CT, "LV_myocardium_CT_smooth.stl")) or not _P["legacy"]:
        rep["parts"] = {"myocardium": dict(new=dict(faces=int(len(myo.faces)), volume_mL=round(abs(myo.volume) / 1000, 2), roughness_rms_mm=round(roughness_mm(myo), 3), watertight=bool(myo.is_watertight))),
                        "blood": dict(new=dict(faces=int(len(blood.faces)), volume_mL=round(abs(blood.volume) / 1000, 2), roughness_rms_mm=round(roughness_mm(blood), 3), watertight=bool(blood.is_watertight)))}
        rep["verdict"] = "OK" if (myo.is_watertight and blood.is_watertight) else "CHECK"; json.dump(rep, open(os.path.join(OUT, "hires_report.json"), "w"), indent=1)
        print("verdict", rep["verdict"], f"(no legacy parts to compare; {time.time()-t0:.0f}s)"); return
    for tag, new, old_path in [("myocardium", myo, os.path.join(CT, "LV_myocardium_CT_smooth.stl")), ("blood", blood, os.path.join(CT, "lv_bloodpool_CT_smooth.stl"))]:
        old = trimesh.load(old_path, process=True)
        pts, _ = trimesh.sample.sample_surface(old.simplify_quadric_decimation(face_count=60000), 15000, seed=1)
        _, dist, _ = trimesh.proximity.closest_point(new.simplify_quadric_decimation(face_count=150000) if len(new.faces) > 150000 else new, pts)
        r_old, r_new = roughness_mm(old), roughness_mm(new)
        rep["parts"][tag] = dict(old=dict(faces=int(len(old.faces)), volume_mL=round(abs(old.volume) / 1000, 2), roughness_rms_mm=round(r_old, 3)),
                                 new=dict(faces=int(len(new.faces)), volume_mL=round(abs(new.volume) / 1000, 2), roughness_rms_mm=round(r_new, 3), watertight=bool(new.is_watertight)),
                                 surface_distance_old_to_new_mm=dict(mean=round(float(dist.mean()), 3), p95=round(float(np.percentile(dist, 95)), 3)))
        print(f"{tag}: roughness {r_old:.3f} -> {r_new:.3f} mm RMS; old->new surface distance mean {dist.mean():.3f} p95 {np.percentile(dist,95):.3f} mm")
    closeups(myo, blood)
    ok = all(p["surface_distance_old_to_new_mm"]["mean"] < 0.4 and p["new"]["roughness_rms_mm"] < p["old"]["roughness_rms_mm"] for p in rep["parts"].values())
    rep["verdict"] = "OK" if ok else "CHECK"
    json.dump(rep, open(os.path.join(OUT, "hires_report.json"), "w"), indent=1)
    print("verdict", rep["verdict"], f"({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    if os.environ.get("CLOSEUP_ONLY") == "1":
        closeups(trimesh.load(os.path.join(OUT, "LV_myocardium_CT_hires.stl"), process=False), trimesh.load(os.path.join(OUT, "lv_bloodpool_CT_hires.stl"), process=False))
    else:
        main()
