# -*- coding: utf-8 -*-
"""Cross-sections perpendicular to each trunk centreline every STEP mm (16 x 16 mm patches, HU window
-100..700) with the segmented radius drawn -- shows whether the path follows one vessel or hops to a
neighbouring vein / chamber."""
import os, sys, json, numpy as np, nibabel as nib
from scipy import ndimage
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from case_paths import paths as _paths, MMWHS
_P = _paths()
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = _P["coronary"]; TAG = sys.argv[1] if len(sys.argv) > 1 else ""; STEP = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0
HALF, RES = 8.0, 0.25
img = nib.load(_P["image"]); A = img.affine; Ainv = np.linalg.inv(A)
I = np.asanyarray(img.dataobj).astype(np.float32)
d = json.load(open(os.path.join(OUT, f"coronary{TAG}.json"))); T = np.array(d.get("frame_translation", [37.084294473997595, -31.48178399081597, 159.45926982283387]))
us = np.arange(-HALF, HALF + 1e-6, RES); U, W = np.meshgrid(us, us, indexing="ij")

def resample(P, r, hu, step=0.3):
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1); s = np.r_[0, np.cumsum(seg)]; ss = np.arange(0, s[-1], step)
    Pi = np.c_[[np.interp(ss, s, P[:, k]) for k in range(3)]].T; Pi = ndimage.uniform_filter1d(Pi, 12, axis=0, mode="nearest")
    return ss, Pi, np.interp(ss, s, r), np.interp(ss, s, hu)

def frames(Pi):
    tng = np.gradient(Pi, axis=0); tng /= np.linalg.norm(tng, axis=1)[:, None] + 1e-9
    n = np.cross(tng[0], [0, 0, 1.0]); n = n if np.linalg.norm(n) > 1e-3 else np.cross(tng[0], [0, 1.0, 0]); n /= np.linalg.norm(n); N = [n]
    for i in range(1, len(tng)):
        v = N[-1] - tng[i] * (N[-1] @ tng[i]); N.append(v / (np.linalg.norm(v) + 1e-9))
    N = np.array(N); return tng, N, np.cross(tng, N)

rows = []
for nm, tr in d["trunks"].items():
    P = np.array(tr["pts"]) - T; ss, Pi, ri, hui = resample(P, np.array(tr["r_mm"]), np.array(tr["hu"])); tng, N, B = frames(Pi)
    picks = [int(np.argmin(np.abs(ss - x))) for x in np.arange(0, ss[-1] + 1e-6, STEP)]
    rows.append((nm, ss, Pi, ri, hui, N, B, picks))
PER = 8
n_rows = sum(int(np.ceil(len(r[-1]) / PER)) for r in rows)
fig, axes = plt.subplots(n_rows, PER, figsize=(2.3 * PER, 2.5 * n_rows)); axes = np.atleast_2d(axes)
ri_ = 0
for (nm, ss, Pi, ri, hui, N, B, picks) in rows:
    for j, i in enumerate(picks):
        ax = axes[ri_ + j // PER, j % PER]
        pts = Pi[i] + U[..., None] * N[i] + W[..., None] * B[i]
        ijk = (Ainv[:3, :3] @ pts.reshape(-1, 3).T).T + Ainv[:3, 3]
        patch = ndimage.map_coordinates(I, ijk.T, order=1, mode="constant", cval=-1000).reshape(U.shape)
        ax.imshow(patch.T, cmap="gray", vmin=-100, vmax=700, origin="lower", extent=[-HALF, HALF, -HALF, HALF])
        ax.add_patch(plt.Circle((0, 0), ri[i], fill=False, color="r", lw=0.8)); ax.set_title(f"{nm} {ss[i]:.0f} mm  {hui[i]:.0f} HU", fontsize=9)
    ri_ += int(np.ceil(len(picks) / PER))
for ax in axes.ravel(): ax.set_axis_off()
plt.tight_layout(); out = os.path.join(OUT, f"coronary_xsec{TAG}.png"); plt.savefig(out, dpi=72); print("->", out)
