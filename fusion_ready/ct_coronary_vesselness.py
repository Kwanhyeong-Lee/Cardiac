# -*- coding: utf-8 -*-
"""Multi-scale Frangi vesselness (bright tubes) for the 1009 CT crop -- own float32 implementation
with analytic 3x3 eigenvalues so it runs in < 1 GB, in resumable z-slabs (one .npy per slab).

  H = sigma^2 * Gaussian second derivatives (6 components)      (scale-normalised Hessian)
  |l1| <= |l2| <= |l3|;  bright tube: l2, l3 << 0, l1 ~ 0
  RA = |l2|/|l3|, RB = |l1|/sqrt(|l2 l3|), S = sqrt(l1^2+l2^2+l3^2)
  V  = (1-exp(-RA^2/2a^2)) * exp(-RB^2/2b^2) * (1-exp(-S^2/2c^2)),  0 where l2>0 or l3>0
  a = b = 0.5, c = GAMMA (HU-derivative units); V = max over sigmas.
Run repeatedly until it prints ASSEMBLED (each call does as many slabs as fit in BUDGET_S)."""
import os, sys, time, glob, numpy as np, nibabel as nib
from scipy import ndimage
from case_paths import paths as _paths, MMWHS, dist_to
_P = _paths()
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = _P["coronary"]; CASE = _P["case"]; WORK = os.path.join(OUT, "vslabs"); os.makedirs(WORK, exist_ok=True)
BAND_MM, GAP_MM, MARGIN_MM = 14.0, 1.0, 20.0
SIGMAS = (1.0, 1.6, 2.4, 3.5, 4.8); GAMMA = 120.0; ALPHA = BETA = 0.5
SLAB, OVL, BUDGET_S = 24, 16, float(os.environ.get("BUDGET_S", 520))
BLOOD = (500, 600, 420, 550, 820, 850)
t0 = time.time()

def prep():
    img = nib.load(os.path.join(MMWHS, f"ct_train_{CASE}_image.nii.gz")); lab = nib.load(os.path.join(MMWHS, f"ct_train_{CASE}_label.nii.gz"))
    sp = np.array(img.header.get_zooms()[:3], float)
    L = np.asanyarray(lab.dataobj); idx = np.argwhere(L > 0); m = np.ceil(MARGIN_MM / sp).astype(int)
    lo = np.maximum(idx.min(0) - m, 0); hi = np.minimum(idx.max(0) + m + 1, L.shape); sl = tuple(slice(a, b) for a, b in zip(lo, hi))
    Lc = np.asarray(L[sl]).astype(np.int16); del L, idx
    band = dist_to(Lc != 0, sp) <= BAND_MM
    band &= dist_to(np.isin(Lc, BLOOD), sp) >= GAP_MM
    del Lc
    I = np.clip(np.asanyarray(img.dataobj)[sl].astype(np.float32), -50, 1200)
    np.save(os.path.join(WORK, "I.npy"), I); np.save(os.path.join(WORK, "band.npy"), band)
    np.savez(os.path.join(WORK, "meta.npz"), lo=lo, sp=sp, shape=np.array(I.shape))
    print("prepared crop", I.shape, f"{time.time()-t0:.0f}s", flush=True)

def eig3_sym(a, b, c, d, e, f):
    """eigenvalues of [[a,d,e],[d,b,f],[e,f,c]] (float32 arrays), returned sorted by |lambda| ascending."""
    p1 = d * d + e * e + f * f
    q = (a + b + c) / 3.0
    p2 = (a - q) ** 2 + (b - q) ** 2 + (c - q) ** 2 + 2.0 * p1
    p = np.sqrt(p2 / 6.0) + 1e-12
    # B = (A - qI)/p ; r = det(B)/2
    ba, bb, bc = (a - q) / p, (b - q) / p, (c - q) / p; bd, be, bf = d / p, e / p, f / p
    r = (ba * (bb * bc - bf * bf) - bd * (bd * bc - bf * be) + be * (bd * bf - bb * be)) / 2.0
    r = np.clip(r, -1.0, 1.0); phi = np.arccos(r) / 3.0
    l1 = q + 2.0 * p * np.cos(phi); l3 = q + 2.0 * p * np.cos(phi + 2.0 * np.pi / 3.0); l2 = 3.0 * q - l1 - l3
    lam = np.stack([l1, l2, l3], 0); order = np.argsort(np.abs(lam), axis=0)
    return np.take_along_axis(lam, order, axis=0)

def vesselness(slab, sp):
    best = np.zeros(slab.shape, np.float32)
    for s in SIGMAS:
        sig = s * sp[0] / sp                          # isotropic in mm: sigma (voxels) per axis
        H = {}
        for k, (o) in {"a": (2, 0, 0), "b": (0, 2, 0), "c": (0, 0, 2), "d": (1, 1, 0), "e": (1, 0, 1), "f": (0, 1, 1)}.items():
            H[k] = (ndimage.gaussian_filter(slab, sig, order=o, mode="nearest") * (s * s)).astype(np.float32)
        lam = eig3_sym(H["a"], H["b"], H["c"], H["d"], H["e"], H["f"]); del H
        l1, l2, l3 = lam[0], lam[1], lam[2]; del lam
        bright = (l2 < 0) & (l3 < 0)
        a2, a3 = np.abs(l2) + 1e-6, np.abs(l3) + 1e-6
        RA = a2 / a3; RB = np.abs(l1) / np.sqrt(a2 * a3); S = np.sqrt(l1 * l1 + l2 * l2 + l3 * l3)
        v = (1 - np.exp(-RA * RA / (2 * ALPHA * ALPHA))) * np.exp(-RB * RB / (2 * BETA * BETA)) * (1 - np.exp(-S * S / (2 * GAMMA * GAMMA)))
        v[~bright] = 0; np.maximum(best, v.astype(np.float32), out=best); del v, RA, RB, S, a2, a3, bright, l1, l2, l3
    return best

if not os.path.exists(os.path.join(WORK, "meta.npz")): prep()
meta = np.load(os.path.join(WORK, "meta.npz")); sp = meta["sp"]; shape = tuple(meta["shape"]); nz = shape[2]
I = np.load(os.path.join(WORK, "I.npy"), mmap_mode="r")
starts = list(range(0, nz, SLAB)); done = 0
for z in starts:
    f = os.path.join(WORK, f"v_{z:04d}.npy")
    if os.path.exists(f): done += 1; continue
    if time.time() - t0 > BUDGET_S: print(f"budget reached after {done}/{len(starts)} slabs -- run again", flush=True); sys.exit(0)
    z0, z1 = max(z - OVL, 0), min(z + SLAB + OVL, nz)
    slab = np.ascontiguousarray(I[:, :, z0:z1]).astype(np.float32)
    v = vesselness(slab, sp); a, b = z - z0, min(z + SLAB, nz) - z0
    np.save(f, v[:, :, a:b].astype(np.float16)); done += 1
    print(f"slab z {z}-{min(z+SLAB, nz)} ({done}/{len(starts)})  {time.time()-t0:.0f}s", flush=True)
# assemble
V = np.zeros(shape, np.float16)
for z in starts: V[:, :, z:z + SLAB] = np.load(os.path.join(WORK, f"v_{z:04d}.npy"))
band = np.load(os.path.join(WORK, "band.npy")); V[~band] = 0
np.savez_compressed(os.path.join(OUT, "vesselness.npz"), V=V, lo=meta["lo"], sp=sp, sigmas=SIGMAS, gamma=GAMMA)
vb = V[band].astype(np.float32)
print("ASSEMBLED  vesselness in band: p50/90/99/99.9 =", np.percentile(vb, [50, 90, 99, 99.9]).round(4), f"max {vb.max():.3f}  frac>0.02 {np.mean(vb>0.02):.4f}  ({time.time()-t0:.0f}s)")
if os.environ.get("KEEP_SLABS") != "1":                      # ~450 MB of intermediates per case; vesselness.npz is all downstream needs
    import shutil; shutil.rmtree(WORK, ignore_errors=True)
