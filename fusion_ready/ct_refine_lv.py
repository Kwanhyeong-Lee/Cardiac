# -*- coding: utf-8 -*-
"""Re-segment the LV interior from the ORIGINAL CT at native resolution.

WHY. The MM-WHS label 500 (LV blood cavity) includes the papillary muscles and trabeculae:
10 % of its voxels (15.3 mL) are darker than the blood/myocardium midpoint. Every mesh so far
inherits that smooth, PM-inclusive cavity -- which is why the printed interior looks crude.
Contrast CT separates blood (median 340 HU) from muscle (median 120 HU) cleanly, so inside the
label we can recover the real endocardium, the real papillary muscles and the trabeculae.

STEPS
    1. crop to the LV labels (+margin); Otsu threshold on HU inside (cavity U myocardium)
    2. blood     = label500 & HU >= thr, opened (r=1 vox), largest component, holes filled
       muscleIn  = label500 & HU <  thr  -> joins the myocardium: myoCT = label205 | muscleIn
    3. marching cubes (skimage) at native resolution for: label500 (registration reference),
       blood, myoCT; vertices -> world via the NIfTI affine
    4. register to frame A: label500 world mesh vs frame_A_patient/lv_surface.stl over the
       24 proper axis-aligned rotations + centroid translation; the winner must be < 1 mm
       mean distance (same label, same case) or the script stops
    5. apply the transform, export; report volumes and the papillary-muscle candidates found
       as thick components of myoCT inside the closed (smoothed) blood cavity

Outputs (frame A, mm): CT/lv_bloodpool_CT.stl, CT/LV_myocardium_CT_with_PMs.stl,
    CT/lv_label500_CT.stl, CT/pm_*_CT.stl, CT/ct_refine.json, CT/masks_crop.npz
"""
import json, os, time, warnings
import numpy as np, trimesh
from scipy import ndimage
from skimage import measure, filters
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "CT"); os.makedirs(OUT, exist_ok=True)
# MM-WHS raw CT lives outside the repository: default D:\data\MM-WHS\ct_train,
# override the root with CARDIAC_DATA (HANDOVER.md section 3).
MMWHS = os.path.join(os.environ.get("CARDIAC_DATA", r"D:\data"), "MM-WHS", "ct_train")
CASE = "1009"
d = json.load(open(os.path.join(HERE, "valve_refit.json")))
AXIS = np.array(d["lv_geometry"]["axis_base_to_apex"]); MV_C = np.array(d["design"]["mv_centre_mm"]); AV_C = np.array(d["design"]["av_centre_mm"])
MARGIN_VOX, R_CLOSE_MM, V_MIN, T_MIN = 12, 8.0, 0.30, 2.0


def mc(mask, affine, offset, spacing, step=1):
    v, f, _, _ = measure.marching_cubes(mask.astype(np.uint8), level=0.5, spacing=(1, 1, 1), step_size=step)
    v = v + offset                                       # crop index -> full index
    w = trimesh.transform_points(v, affine)              # index -> world (mm)
    m = trimesh.Trimesh(w, f, process=True); trimesh.repair.fix_normals(m); return m


def ball(r):
    n = int(np.ceil(r)); g = np.mgrid[-n:n + 1, -n:n + 1, -n:n + 1]; return (g ** 2).sum(0) <= r ** 2


def main():
    import nibabel as nib
    t0 = time.time()
    img = nib.load(os.path.join(MMWHS, f"ct_train_{CASE}_image.nii.gz")); lab = nib.load(os.path.join(MMWHS, f"ct_train_{CASE}_label.nii.gz"))
    A = img.affine; sp = np.array(img.header.get_zooms()[:3])
    L = np.asanyarray(lab.dataobj); I = np.asanyarray(img.dataobj).astype(np.int16)
    lv = (L == 500) | (L == 205)
    idx = np.argwhere(lv); lo = np.maximum(idx.min(0) - MARGIN_VOX, 0); hi = np.minimum(idx.max(0) + MARGIN_VOX + 1, L.shape)
    sl = tuple(slice(a, b) for a, b in zip(lo, hi))
    Lc, Ic = L[sl], I[sl]; del L, I
    cav, myo = Lc == 500, Lc == 205
    thr = float(filters.threshold_otsu(Ic[cav | myo]))
    print(f"crop {Lc.shape}, voxel {sp} mm, Otsu threshold {thr:.0f} HU  ({time.time()-t0:.0f}s)")

    # ---- 2. blood vs in-cavity muscle ----
    blood0 = cav & (Ic >= thr)
    blood = ndimage.binary_opening(blood0, structure=ball(1))
    lbl, n = ndimage.label(blood); sizes = ndimage.sum(blood, lbl, range(1, n + 1)); blood = lbl == (1 + int(np.argmax(sizes)))
    blood = ndimage.binary_fill_holes(blood)
    muscle_in = cav & ~blood                              # dark voxels + what opening removed
    myoCT = myo | muscle_in
    vox_mL = np.prod(sp) / 1000
    rep = dict(case=CASE, voxel_mm=sp.tolist(), otsu_HU=round(thr, 1),
               label500_mL=round(cav.sum() * vox_mL, 2), blood_mL=round(blood.sum() * vox_mL, 2),
               muscle_inside_label500_mL=round(muscle_in.sum() * vox_mL, 2), label205_mL=round(myo.sum() * vox_mL, 2),
               myoCT_mL=round(myoCT.sum() * vox_mL, 2))
    print(f"label500 {rep['label500_mL']} mL -> blood {rep['blood_mL']} mL, muscle inside label {rep['muscle_inside_label500_mL']} mL; myoCT {rep['myoCT_mL']} mL")
    np.savez_compressed(os.path.join(OUT, "masks_crop.npz"), blood=blood, myoCT=myoCT, cav=cav, offset=lo, affine=A, spacing=sp, thr=thr)

    # ---- 3. meshes in world mm ----
    m500 = mc(cav, A, lo, sp); m_blood = mc(blood, A, lo, sp); m_myo = mc(myoCT, A, lo, sp)
    print(f"meshes: label500 {len(m500.faces):,} f {abs(m500.volume)/1000:.1f} mL | blood {len(m_blood.faces):,} f {abs(m_blood.volume)/1000:.1f} mL | "
          f"myoCT {len(m_myo.faces):,} f {abs(m_myo.volume)/1000:.1f} mL  ({time.time()-t0:.0f}s)")

    # ---- 4. registration of world -> frame A on the label-500 surface ----
    ref = trimesh.load(os.path.join(HERE, "frame_A_patient", "lv_surface.stl"), process=True)
    q = trimesh.proximity.ProximityQuery(ref.simplify_quadric_decimation(face_count=20000))
    src = m500.vertices[::max(1, len(m500.vertices) // 4000)]
    best = None
    import itertools
    for perm in itertools.permutations(range(3)):
        for signs in itertools.product((1, -1), repeat=3):
            R = np.zeros((3, 3))
            for i, (p, s) in enumerate(zip(perm, signs)): R[i, p] = s
            if np.linalg.det(R) < 0: continue
            P = src @ R.T; t = ref.centroid - P.mean(0)
            dist = np.abs(q.signed_distance(P + t)).mean()
            if best is None or dist < best[0]: best = (dist, R, t, perm, signs)
    dist, R, t, perm, signs = best
    # refine translation only (ICP-lite: 3 iterations of mean closest-point offset)
    for _ in range(3):
        P = src @ R.T + t; closest, _, _ = q.on_surface(P); t = t + (closest - P).mean(0)
    P = src @ R.T + t; dist = float(np.abs(q.signed_distance(P)).mean()); d95 = float(np.percentile(np.abs(q.signed_distance(P)), 95))
    M = np.eye(4); M[:3, :3] = R; M[:3, 3] = t
    rep["world_to_frameA"] = dict(perm=perm, signs=signs, translation_mm=[round(float(x), 3) for x in t],
                                  mean_dist_mm=round(dist, 3), p95_dist_mm=round(d95, 3), matrix=M.tolist())
    print(f"world->frame A: perm {perm} signs {signs} t {np.round(t,2)}  mean {dist:.3f} mm  p95 {d95:.3f} mm")
    assert dist < 1.0, "registration to frame A failed -- do not trust anything downstream"
    for m in (m500, m_blood, m_myo): m.apply_transform(M)
    m500.export(os.path.join(OUT, "lv_label500_CT.stl")); m_blood.export(os.path.join(OUT, "lv_bloodpool_CT.stl")); m_myo.export(os.path.join(OUT, "LV_myocardium_CT_with_PMs.stl"))

    # ---- 5. papillary muscles = thick parts of myoCT inside the closed blood cavity (voxel space) ----
    # closing by radius R via two Euclidean distance transforms (a 35^3 structuring element
    # in scipy's binary_closing is a MemoryError on this crop); anisotropic voxels handled
    # through `sampling`. dilation: dist(~blood) <= R ; erosion of that: dist(~dilated) >= R
    pad = int(np.ceil(R_CLOSE_MM / sp.min())) + 2
    Bp = np.pad(blood, pad)
    dil = ndimage.distance_transform_edt(~Bp, sampling=sp) <= R_CLOSE_MM
    closed = ndimage.distance_transform_edt(dil, sampling=sp) >= R_CLOSE_MM
    closed = (closed | Bp)[pad:-pad, pad:-pad, pad:-pad]; del dil, Bp
    pm_vox = closed & myoCT
    # peel the 1-voxel film along the wall (partial volume / smoothing) so muscles separate
    pm_core = ndimage.binary_opening(pm_vox, structure=ball(1.5))
    lbl, n = ndimage.label(pm_core); comps = []
    for k in range(1, n + 1):
        mk = lbl == k; V = mk.sum() * vox_mL
        if V < 0.05: continue
        mm = mc(mk, A, lo, sp); mm.apply_transform(M)
        thick = 20 * (abs(mm.volume) / 1000) / (mm.area / 100)
        c = mm.centroid; dep = float((c - MV_C) @ AXIS) / float(((ref.vertices - MV_C) @ AXIS).max())
        comps.append(dict(k=k, volume_mL=round(V, 3), thickness_2V_A_mm=round(thick, 2), depth_frac=round(dep, 3),
                          centroid=[round(float(x), 1) for x in c], faces=int(len(mm.faces)), mesh=mm))
    comps.sort(key=lambda r: -r["volume_mL"])
    keep = [r for r in comps if r["volume_mL"] >= V_MIN and r["thickness_2V_A_mm"] >= T_MIN and 0.15 <= r["depth_frac"] <= 0.92]
    print(f"in-cavity muscle components >= 0.05 mL: {len(comps)}; thick & ventricular: {len(keep)}")
    for r in comps[:10]:
        print(f"  {'KEEP' if r in keep else '    '} V {r['volume_mL']:6.2f} mL  2V/A {r['thickness_2V_A_mm']:5.2f}  depth {r['depth_frac']:.2f}  c {r['centroid']}")
    for i, r in enumerate(keep[:6]):
        r["mesh"].export(os.path.join(OUT, f"pm_candidate_{i+1}_CT.stl"))
    rep["in_cavity_muscle_components"] = [{k: v for k, v in r.items() if k != "mesh"} for r in comps[:15]]
    rep["papillary_candidates_kept"] = [{k: v for k, v in r.items() if k != "mesh"} for r in keep]
    rep["meshes"] = dict(label500=dict(faces=int(len(m500.faces)), mL=round(abs(m500.volume) / 1000, 2)),
                         blood=dict(faces=int(len(m_blood.faces)), mL=round(abs(m_blood.volume) / 1000, 2), watertight=bool(m_blood.is_watertight)),
                         myoCT=dict(faces=int(len(m_myo.faces)), mL=round(abs(m_myo.volume) / 1000, 2), watertight=bool(m_myo.is_watertight)))
    json.dump(rep, open(os.path.join(OUT, "ct_refine.json"), "w"), indent=1)
    print(f"done {time.time()-t0:.0f}s -> {OUT}")


if __name__ == "__main__":
    main()
