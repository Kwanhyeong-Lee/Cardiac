# -*- coding: utf-8 -*-
"""Step 21a -- LV geometry of any MM-WHS case from its labels alone (no valve fitting, no frame A).

  mitral centre  = centroid of the label-500 (LV) voxels that touch label 420 (LA)      -> MV annulus plane
  aortic centre  = centroid of the label-500 voxels that touch label 820 (aorta)        -> AV annulus
  annulus radii  = sqrt(contact area / pi)  (contact area ~ voxels x mean voxel face area; rough, +-15 %)
  base->apex axis: apex = LV point farthest from the MV centre, refined 3x along the current axis
  Otsu threshold  inside label 500 (blood vs in-cavity muscle), contrast stats per chamber (HU)

Writes CT/cases/<case>/case_geometry.json (world mm, NIfTI affine / RAS).  For 1009 it also prints the
distance to the frame-A values used so far (sanity: should be a few mm at most after the translation).
Env: CASE, CARDIAC_DATA.   Usage: CASE=1001 python ct_case_geometry.py
"""
import os, json, time
import numpy as np, nibabel as nib, trimesh
from scipy import ndimage
from skimage import filters
from case_paths import paths, HERE, MMWHS
LABELS = {500: "LV", 600: "RV", 420: "LA", 550: "RA", 205: "LV_myo", 820: "aorta", 850: "PA"}
unit = lambda v: v / (np.linalg.norm(v) + 1e-12)


def contact(L, a, b, r_vox=1):
    st = np.ones((3, 3, 3), bool)
    m = (L == a) & ndimage.binary_dilation(L == b, structure=st, iterations=r_vox)
    return m


def main():
    t0 = time.time(); case = os.environ.get("CASE", "1009")
    P = paths(case); base = os.path.join(HERE, "CT", "cases", case); os.makedirs(base, exist_ok=True)
    img = nib.load(P["image"]); lab = nib.load(P["label"]); A = img.affine; sp = np.array(img.header.get_zooms()[:3], float); vox_mL = np.prod(sp) / 1000
    L = np.asanyarray(lab.dataobj).astype(np.int16)
    present = {int(k): LABELS[k] for k in LABELS if (L == k).any()}
    missing = [LABELS[k] for k in LABELS if k not in present]
    W = lambda idx: trimesh.transform_points(np.asarray(idx, float), A)
    # ---- contacts ----
    mv = contact(L, 500, 420); r = 1
    while mv.sum() < 200 and r < 4: r += 1; mv = contact(L, 500, 420, r)
    av = contact(L, 500, 820); r2 = 1
    while av.sum() < 100 and r2 < 4: r2 += 1; av = contact(L, 500, 820, r2)
    if mv.sum() < 50: raise RuntimeError(f"case {case}: no LV-LA contact found (mitral annulus) -- labels touching? counts LV {(L==500).sum()} LA {(L==420).sum()}")
    if av.sum() < 30: raise RuntimeError(f"case {case}: no LV-aorta contact found (aortic annulus)")
    face_area = float(np.mean([sp[0] * sp[1], sp[1] * sp[2], sp[0] * sp[2]]))
    mv_c = W(np.argwhere(mv)).mean(0); av_c = W(np.argwhere(av)).mean(0)
    mv_r = float(np.sqrt(mv.sum() * face_area / r / np.pi)); av_r = float(np.sqrt(av.sum() * face_area / r2 / np.pi))
    # ---- axis ----
    lv_idx = np.argwhere((L == 500) | (L == 205)); lvW = W(lv_idx[::3])
    d = unit(lvW.mean(0) - mv_c)
    for _ in range(3):
        apex = lvW[np.argmax((lvW - mv_c) @ d)]; d = unit(apex - mv_c)
    length = float(np.linalg.norm(apex - mv_c))
    # ---- HU ----
    I = np.asanyarray(img.dataobj)
    thr = float(filters.threshold_otsu(I[(L == 500) | (L == 205)].astype(np.float32)))
    hu = {name: dict(mean=round(float(I[L == k].mean()), 1), sd=round(float(I[L == k].std()), 1)) for k, name in present.items()}
    vols = {name: round(float((L == k).sum() * vox_mL), 1) for k, name in present.items()}
    g = dict(case=case, frame="world (NIfTI affine, RAS mm)", voxel_mm=sp.round(4).tolist(), shape=list(L.shape), labels_present=list(present.values()), labels_missing=missing,
             mv_centre_mm=mv_c.round(2).tolist(), av_centre_mm=av_c.round(2).tolist(), mv_annulus_r_mm=round(mv_r, 1), av_annulus_r_mm=round(av_r, 1),
             mv_contact_voxels=int(mv.sum()), av_contact_voxels=int(av.sum()), contact_dilation_vox=[r, r2],
             axis_base_to_apex=d.round(5).tolist(), apex_mm=apex.round(2).tolist(), lv_length_mm=round(length, 1), otsu_HU=round(thr, 1),
             hu_by_label=hu, volume_mL_by_label=vols, contrast_note=("arterial-phase-like (aorta >= 300 HU)" if hu.get("aorta", {}).get("mean", 0) >= 300 else "LOW contrast in the aorta -- coronary extraction unreliable"))
    json.dump(g, open(os.path.join(base, "case_geometry.json"), "w"), indent=1)
    print(f"case {case}: voxel {sp.round(3)}  LV {vols.get('LV')} mL  MV r {mv_r:.1f}  AV r {av_r:.1f}  LV length {length:.1f} mm  Otsu {thr:.0f} HU  aorta {hu.get('aorta',{}).get('mean')} HU  missing {missing}  ({time.time()-t0:.0f}s)")
    if case == "1009":
        vr = json.load(open(os.path.join(HERE, "valve_refit.json"))); ref = json.load(open(os.path.join(HERE, "CT", "ct_refine.json"))); T = np.array(ref["world_to_frameA"]["matrix"])[:3, 3]
        dm = np.linalg.norm(mv_c + T - np.array(vr["design"]["mv_centre_mm"])); da = np.linalg.norm(av_c + T - np.array(vr["design"]["av_centre_mm"]))
        ang = np.degrees(np.arccos(np.clip(d @ np.array(vr["lv_geometry"]["axis_base_to_apex"]), -1, 1)))
        print(f"  vs frame-A values: MV centre {dm:.1f} mm, AV centre {da:.1f} mm, axis {ang:.1f} deg, MV r {mv_r:.1f} vs {vr['design']['mv_annulus_r_mm']}, AV r {av_r:.1f} vs {vr['design']['av_annulus_r_mm']}")


if __name__ == "__main__":
    main()
