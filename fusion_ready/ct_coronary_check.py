# -*- coding: utf-8 -*-
"""Step 1 -- is there a coronary tree in the 1009 CT?  Cheap, threshold-only look.

epicardial band = within BAND_MM outside the union of all MM-WHS labels, but >= GAP_MM away from
any blood-pool label (500/600/420/550/820/850) so partial-volume rims of the chambers are excluded.
Bright voxels (>= HU_LO) in the band are grouped into connected components; each component gets
volume, PCA elongation and mean HU.  Outputs MIPs + a component table.
"""
import os, sys, json, time
import numpy as np, nibabel as nib
from scipy import ndimage
from case_paths import paths as _paths, MMWHS
_P = _paths()
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = _P["coronary"]; os.makedirs(OUT, exist_ok=True)
CASE = _P["case"]; BAND_MM, GAP_MM, HU_LO, MARGIN_MM = 14.0, 1.0, 180.0, 20.0
BLOOD = (500, 600, 420, 550, 820, 850)

t0 = time.time()
img = nib.load(os.path.join(MMWHS, f"ct_train_{CASE}_image.nii.gz")); lab = nib.load(os.path.join(MMWHS, f"ct_train_{CASE}_label.nii.gz"))
A = img.affine; sp = np.array(img.header.get_zooms()[:3], float)
L = np.asanyarray(lab.dataobj); print("full shape", L.shape, "spacing", sp, "affine diag", np.diag(A)[:3])
H = L > 0
idx = np.argwhere(H); m = np.ceil(MARGIN_MM / sp).astype(int)
lo = np.maximum(idx.min(0) - m, 0); hi = np.minimum(idx.max(0) + m + 1, L.shape); sl = tuple(slice(a, b) for a, b in zip(lo, hi))
Lc = L[sl]; del L, H, idx
I = np.asanyarray(img.dataobj)[sl].astype(np.float32); print("crop", Lc.shape, f"{time.time()-t0:.0f}s")

# HU statistics of the labelled structures (contrast phase check)
stats = {}
for k, name in [(820, "aorta"), (500, "LV"), (600, "RV"), (420, "LA"), (550, "RA"), (850, "PA"), (205, "LV_myo")]:
    v = I[Lc == k]; stats[name] = dict(mean=round(float(v.mean()), 1), sd=round(float(v.std()), 1), p50=round(float(np.median(v)), 1)) if v.size else None
print(json.dumps(stats))

# epicardial band
Hc = Lc > 0
dist_out = ndimage.distance_transform_edt(~Hc, sampling=sp)            # distance to nearest labelled voxel
blood = np.isin(Lc, BLOOD)
dist_blood = ndimage.distance_transform_edt(~blood, sampling=sp)
band = (dist_out <= BAND_MM) & (dist_blood >= GAP_MM)                     # includes label-205 voxels >= 1 mm from a blood label
cand = band & (I >= HU_LO)
lbl, n = ndimage.label(cand, structure=np.ones((3, 3, 3)))
vox_mL = np.prod(sp) / 1000
sizes = ndimage.sum(cand, lbl, range(1, n + 1))
print(f"band {band.sum()*vox_mL:.1f} mL, candidates {cand.sum()*vox_mL:.2f} mL in {n} components  {time.time()-t0:.0f}s")

# component table (largest 40)
order = np.argsort(sizes)[::-1][:40]
rows = []
for j in order:
    k = j + 1; pts = np.argwhere(lbl == k)
    if len(pts) < 5: continue
    w = pts * sp; c = w.mean(0); ev = np.linalg.eigvalsh(np.cov((w - c).T)); ev = np.sqrt(np.maximum(ev, 1e-9))
    hu = I[lbl == k]
    # how far along the LV axis / which side: use world coords
    rows.append(dict(k=int(k), mL=round(float(len(pts) * vox_mL), 3), len_mm=round(float(4 * ev[-1]), 1), elong=round(float(ev[-1] / max(ev[0], 1e-6)), 1),
                     mean_HU=round(float(hu.mean()), 0), max_HU=round(float(hu.max()), 0), centroid_idx=(pts.mean(0) + lo).round(0).tolist(),
                     min_dist_out=round(float(dist_out[lbl == k].min()), 2)))
for r in rows[:25]: print(r)
json.dump(dict(stats=stats, spacing=sp.tolist(), crop_lo=lo.tolist(), crop_shape=list(Lc.shape), n_components=int(n), components=rows), open(os.path.join(OUT, "check.json"), "w"), indent=1)

# MIPs: band-masked HU (0 outside), three axes, plus label silhouette for orientation
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
V = np.where(band, I, 0)
fig, ax = plt.subplots(2, 3, figsize=(16, 10))
names = ["axis0 (i)", "axis1 (j)", "axis2 (k)"]
for a in range(3):
    mip = V.max(axis=a); sil = Hc.any(axis=a)
    ax[0, a].imshow(mip.T, cmap="gray", vmin=100, vmax=600, origin="lower"); ax[0, a].contour(sil.T, levels=[0.5], colors="c", linewidths=0.5); ax[0, a].set_title(f"band MIP along {names[a]}  (HU 100-600)")
    ax[1, a].imshow(I.max(axis=a).T, cmap="gray", vmin=-200, vmax=800, origin="lower"); ax[1, a].contour(sil.T, levels=[0.5], colors="c", linewidths=0.5); ax[1, a].set_title("full MIP")
for x in ax.ravel(): x.set_axis_off()
plt.tight_layout(); plt.savefig(os.path.join(OUT, "mip.png"), dpi=90); print("->", OUT, f"{time.time()-t0:.0f}s")
np.savez_compressed(os.path.join(OUT, "band.npz"), band=band, lo=lo, sp=sp, A=A)
