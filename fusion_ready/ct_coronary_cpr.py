# -*- coding: utf-8 -*-
"""Straightened curved planar reformations (CPR) along the extracted trunk centrelines, two orthogonal
planes each, with the segmented radius overlaid -- the standard coronary-CTA QA view."""
import os, sys, json, numpy as np, nibabel as nib
from scipy import ndimage
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from case_paths import paths as _paths, MMWHS
_P = _paths()
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = _P["coronary"]; TAG = sys.argv[1] if len(sys.argv) > 1 else ""
HALF_MM, STEP_MM, SMOOTH = 7.0, 0.3, 4
img = nib.load(_P["image"]); A = img.affine; Ainv = np.linalg.inv(A)
I = np.asanyarray(img.dataobj).astype(np.float32)
d = json.load(open(os.path.join(OUT, f"coronary{TAG}.json"))); T = np.array(d.get("frame_translation", [37.084294473997595, -31.48178399081597, 159.45926982283387]))
trunks = d["trunks"]

def resample_path(P, r, hu, step=STEP_MM):
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1); s = np.r_[0, np.cumsum(seg)]
    ss = np.arange(0, s[-1], step)
    Pi = np.c_[[np.interp(ss, s, P[:, k]) for k in range(3)]].T
    Pi = ndimage.uniform_filter1d(Pi, SMOOTH * 3, axis=0, mode="nearest")
    return ss, Pi, np.interp(ss, s, r), np.interp(ss, s, hu)

def frames(Pi):
    tng = np.gradient(Pi, axis=0); tng /= np.linalg.norm(tng, axis=1)[:, None] + 1e-9
    n = np.cross(tng[0], [0, 0, 1.0]);
    if np.linalg.norm(n) < 1e-3: n = np.cross(tng[0], [0, 1.0, 0])
    n /= np.linalg.norm(n); N = [n]
    for i in range(1, len(tng)):                       # parallel transport
        v = N[-1] - tng[i] * (N[-1] @ tng[i]); N.append(v / (np.linalg.norm(v) + 1e-9))
    N = np.array(N); B = np.cross(tng, N); return N, B

def sample(Pw, N, us):
    pts = Pw[:, None, :] + us[None, :, None] * N[:, None, :]          # (L, W, 3) world
    ijk = (Ainv[:3, :3] @ pts.reshape(-1, 3).T).T + Ainv[:3, 3]
    return ndimage.map_coordinates(I, ijk.T, order=1, mode="constant", cval=-1000).reshape(len(Pw), len(us))

us = np.arange(-HALF_MM, HALF_MM + 1e-6, 0.25)
fig, axes = plt.subplots(len(trunks) * 2, 1, figsize=(18, 3.2 * len(trunks) * 2))
axes = np.atleast_1d(axes)
k = 0
for nm, tr in trunks.items():
    P = np.array(tr["pts"]) - T                                   # frame A -> world
    ss, Pi, ri, hui = resample_path(P, np.array(tr["r_mm"]), np.array(tr["hu"]))
    N, B = frames(Pi)
    for plane, Nv in (("plane 1", N), ("plane 2", B)):
        cpr = sample(Pi, Nv, us); ax = axes[k]; k += 1
        ax.imshow(cpr.T, cmap="gray", vmin=-100, vmax=700, aspect="auto", origin="lower", extent=[ss[0], ss[-1], us[0], us[-1]])
        ax.plot(ss, ri, "r-", lw=0.8); ax.plot(ss, -ri, "r-", lw=0.8)
        # centreline HU as a thin overlay strip on top
        ax2 = ax.twinx(); ax2.plot(ss, hui, color="cyan", lw=0.8, alpha=0.9); ax2.set_ylim(0, 800); ax2.set_ylabel("centre HU", color="cyan", fontsize=8); ax2.tick_params(labelsize=7)
        ax.set_ylabel("mm"); ax.set_title(f"{nm} -- straightened CPR {plane} (red = segmented radius; cyan = centreline HU; length {ss[-1]:.0f} mm)", fontsize=10)
        ax.tick_params(labelsize=8)
axes[-1].set_xlabel("distance from ostium (mm)")
plt.tight_layout(); out = os.path.join(OUT, f"coronary_cpr{TAG}.png"); plt.savefig(out, dpi=80); print("->", out)
