# -*- coding: utf-8 -*-
"""Step 24 -- great vessels from the CT itself: extend the MM-WHS labels along the contrast-filled lumen.

MM-WHS labels stop short: the aorta ends above the root, the PA is a stub, and the pulmonary veins, SVC and
IVC are not labelled at all.  In an arterial-phase CTA the blood pool is bright and continuous, so the label
map can be grown along it:

  working grid ~1 mm (label/image subsampled)      Hs = gaussian(HU, 0.7 vox)
  each structure is grown from its own label by geodesic dilation inside a structure-specific HU window
  (aorta >= 0.80 x aorta HU; LA/pulmonary veins >= 0.85 x LA HU; PA within [0.72 x PA HU, PA HU + 70];
  RA >= max(150, 0.7 x RA HU)), excluding bone (Hs > 450 grown 3 mm), farther than REACH_MM from the labels,
  and voxels already claimed by a brighter structure (order: aorta, veins, PA, RA)
  geodesic caps from the original label: aorta 130 mm (root -> arch -> proximal descending), PA 70 mm
  (trunk + proximal branches), LA 45 mm (pulmonary veins), RA 70 mm (SVC / IVC; only tubes >= 12 mm thick)
  components must touch their label and be >= 0.5 mL

New ids: 901 pulmonary_veins (LA extension), 902 SVC and 903 IVC (RA extension split above/below the RA
centre); aorta/PA extensions merge into 820/850.  Output CT/<case>/labels_extended.npz (working grid) +
great_vessels.json + great_vessels_check.png (coronal/sagittal MIP overlay).  build_whole_heart.py picks the
extended labels up automatically (-> whole_heart_ext/).

Limits, stated: the IVC is usually UNENHANCED in the arterial phase (~100 HU) and will be missing or short;
the SVC may carry undiluted contrast (streaks) or be dark depending on injection side/timing; veins and
arteries are separated only by HU windows + growth order, so check the MIP overlay.  For a phase-independent, complete
set (IVC, SVC, pulmonary veins, full aorta) run TotalSegmentator on the PC and feed its label map in.
Env: CASE, CARDIAC_DATA, HU_BRIGHT (default 0.5 x aorta mean, clipped to 170..260).
"""
import os, json, time, warnings
import numpy as np, nibabel as nib, trimesh
from scipy import ndimage
from case_paths import paths, geometry, dist_to
warnings.filterwarnings("ignore")
P = paths(); G = geometry(); OUT = P["base"] if not P["legacy"] else os.path.join(P["base"]); os.makedirs(OUT, exist_ok=True)
TARGET_MM, REACH_MM, BONE_HU, MIN_ML = 1.0, 90.0, 450.0, 0.5
CAPS = {820: 130.0, 850: float(os.environ.get('PA_CAP_MM', 70)), 420: float(os.environ.get('PV_CAP_MM', 30)), 550: 70.0}   # caps in mm from the label; PA 70 reaches the hila (set 45 for a sturdier print), PV 30 = stumps
NAMES = {205: "LV_myocardium", 500: "LV", 600: "RV", 420: "LA", 550: "RA", 820: "aorta", 850: "PA", 901: "pulmonary_veins", 902: "SVC", 903: "IVC"}
t0 = time.time()


def main():
    img = nib.load(P["image"]); lab = nib.load(P["label"]); A = img.affine.copy(); sp0 = np.array(img.header.get_zooms()[:3], float)
    ds = np.maximum(1, np.round(TARGET_MM / sp0)).astype(int); sp = sp0 * ds; A[:3, :3] = A[:3, :3] * ds[None, :]
    L = np.asanyarray(lab.dataobj)[::ds[0], ::ds[1], ::ds[2]].astype(np.int16)
    I = np.asanyarray(img.dataobj)[::ds[0], ::ds[1], ::ds[2]].astype(np.float32)
    vox_mL = np.prod(sp) / 1000
    Hs = ndimage.gaussian_filter(I, (0.7, 0.7, 0.7 * sp[0] / sp[2])); del I
    aorta_hu = float(Hs[L == 820].mean()) if (L == 820).any() else 350.0
    HU_BRIGHT = float(os.environ.get("HU_BRIGHT", np.clip(0.5 * aorta_hu, 170, 260)))
    bone = dist_to(Hs > BONE_HU, sp) <= 3.0
    near = dist_to(L > 0, sp) <= REACH_MM
    st = np.ones((3, 3, 3), bool); mean_vox = float(np.mean(sp))
    hu = {k: float(Hs[L == k].mean()) for k in (420, 550, 820, 850) if (L == k).any()}
    # structure-specific HU windows (arterial phase: aorta > LA/veins > PA > RA), grown in this order so a brighter
    # structure claims a shared voxel first; each growth is a geodesic dilation from the original label
    plan = [(820, "aorta", lambda h: h >= 0.80 * hu.get(820, 400), CAPS[820]),
            (420, "pulmonary_veins", lambda h: h >= max(HU_BRIGHT, 0.85 * hu.get(420, 300)), CAPS[420]),
            (850, "PA", lambda h: (h >= 0.72 * hu.get(850, 240)) & (h <= hu.get(850, 240) + 70), CAPS[850]),
            (550, "RA", lambda h: h >= max(150.0, 0.7 * hu.get(550, 220)), CAPS[550])]
    # Touching vessels (SVC / right PA / right upper pulmonary vein / ascending aorta) merge at ~1 mm through partial
    # volume.  Split them at their necks first: watershed on the negative inside-distance of the bright union with the
    # original labels as markers (the classic touching-object separation), then apply each structure's HU window,
    # geodesic cap, contact and size filters.
    from skimage.segmentation import watershed
    windows = {k: win for k, _, win, _ in plan}
    bright_any = np.zeros(L.shape, bool)
    for k, nm, win, cap in plan:
        if (L == k).any(): bright_any |= win(Hs) & (near if k == 550 else (~bone & near)) & (L == 0)
    Din = dist_to(~(bright_any | (L > 0)), sp)                                   # distance to the outside = inside radius
    markers = np.where(np.isin(L, (420, 550, 820, 850, 600, 500)), L, 0).astype(np.int32)
    W = watershed(-Din, markers=markers, mask=bright_any | (L > 0)); del Din
    gd = {}
    for k, nm, win, cap in plan:
        if not (L == k).any(): continue
        region = (W == k) & (L == 0) & win(Hs)
        reach = (L == k).copy(); dist = np.full(L.shape, np.inf, np.float32); dist[reach] = 0.0
        for i in range(int(cap / mean_vox)):
            nxt = ndimage.binary_dilation(reach, structure=st) & (region | reach)
            newly = nxt & ~reach
            if not newly.any(): break
            dist[newly] = (i + 1) * mean_vox; reach = nxt
        gd[k] = dist
    del W
    # second pass: bright voxels whose basin's window rejected them (e.g. PA branches that fell into the LA basin) go to
    # the geodesically closest structure whose own HU window accepts them
    assigned = np.zeros(L.shape, bool)
    for k in gd: assigned |= np.isfinite(gd[k]) & (L == 0)
    left = bright_any & ~assigned & (L == 0)
    for k, nm, win, cap in plan:
        if k not in gd: continue
        region = left & win(Hs); reach = np.isfinite(gd[k]); dist = gd[k]
        base = np.where(reach, dist, 0).max() if reach.any() else 0.0
        for i in range(int(cap / mean_vox)):
            nxt = ndimage.binary_dilation(reach, structure=st) & (region | reach)
            newly = nxt & ~reach
            if not newly.any(): break
            dist[newly] = base + (i + 1) * mean_vox; reach = nxt
        gd[k] = dist
    keys = list(gd); stack = np.stack([gd[k] for k in keys]); best = np.argmin(stack, axis=0); anyreach = np.isfinite(stack.min(axis=0)); del stack
    Lx = L.copy().astype(np.int16); rep = dict(case=P["case"], HU_BRIGHT=HU_BRIGHT, aorta_HU=round(aorta_hu), hu_by_label={NAMES[k]: round(v) for k, v in hu.items()}, working_voxel_mm=sp.round(3).tolist(), structures={})
    for j, k in enumerate(keys):
        nm = dict((kk, n_) for kk, n_, _, _ in plan)[k]; cap = CAPS[k]
        seg = (best == j) & anyreach & (L == 0)
        lbl, n = ndimage.label(seg, structure=st)
        if n:
            touch = np.unique(lbl[ndimage.binary_dilation(L == k, structure=st) & seg]); sizes = ndimage.sum(seg, lbl, range(1, n + 1)) * vox_mL
            keep = [i + 1 for i in range(n) if (i + 1) in touch and sizes[i] >= MIN_ML]; seg = np.isin(lbl, keep)
        if not seg.any(): rep["structures"][nm + ("_extension" if k in (820, 850) else "")] = dict(volume_mL=0.0); print(f"  {nm}: nothing grew"); continue
        if k in (820, 850):
            Lx[seg] = k; rep["structures"][nm + "_extension"] = dict(volume_mL=round(float(seg.sum() * vox_mL), 1), cap_mm=cap, mean_HU=round(float(Hs[seg].mean())))
        elif k == 420:
            Lx[seg] = 901; rep["structures"]["pulmonary_veins"] = dict(volume_mL=round(float(seg.sum() * vox_mL), 1), cap_mm=cap, components=int(ndimage.label(seg, structure=st)[1]), mean_HU=round(float(Hs[seg].mean())))
        else:   # RA extension: keep only thick (>= 12 mm) tubes -> SVC / IVC by position; thin bits (coronary sinus etc.) dropped
            thick = dist_to(~seg, sp) >= 6.0
            lbl2, n2 = ndimage.label(seg, structure=st); good = np.unique(lbl2[thick]); seg = np.isin(lbl2, good[good > 0])
            zc = trimesh.transform_points(np.argwhere(L == 550)[::20].astype(float), A)[:, 2].mean()
            lbl3, n3 = ndimage.label(seg, structure=st); up = np.zeros_like(seg); down = np.zeros_like(seg)
            for c_ in range(1, n3 + 1):                                   # whole components: SVC above the RA centre, IVC below
                mk = lbl3 == c_; cz = trimesh.transform_points(np.argwhere(mk)[::5].astype(float), A)[:, 2].mean()
                (up if cz > zc else down)[mk] = True
            for m_, code, nm2 in ((up, 902, "SVC"), (down, 903, "IVC")):
                if m_.any(): Lx[m_] = code
                rep["structures"][nm2] = dict(volume_mL=round(float(m_.sum() * vox_mL), 1), mean_HU=round(float(Hs[m_].mean())) if m_.any() else None, cap_mm=cap)
        print(f"  {nm}: {[(kk, vv) for kk, vv in rep['structures'].items()][-1]}")
    # extents of the final aorta / PA (label + extension) for the report
    for k in (820, 850, 901, 902, 903):
        if (Lx == k).any():
            w = trimesh.transform_points(np.argwhere(Lx == k)[::10].astype(float), A); rep["structures"].setdefault(NAMES[k], {})["extent_mm"] = (w.max(0) - w.min(0)).round(1).tolist()
            rep["structures"][NAMES[k]]["total_volume_mL"] = round(float((Lx == k).sum() * vox_mL), 1)
    np.savez_compressed(os.path.join(OUT, "labels_extended.npz"), L=Lx, affine=A, spacing=sp, names=json.dumps({str(k): v for k, v in NAMES.items()}), T=np.asarray(G["T"]))
    json.dump(rep, open(os.path.join(OUT, "great_vessels.json"), "w"), indent=1)
    # check figure: MIPs of HU with the new structures overlaid
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    cols = {820: (0.9, 0.3, 0.2), 850: (0.3, 0.5, 0.85), 901: (0.95, 0.6, 0.6), 902: (0.4, 0.75, 0.95), 903: (0.2, 0.55, 0.7)}
    fig, axes = plt.subplots(1, 3, figsize=(20, 8))
    for ax, axis, ttl in zip(axes, (0, 1, 2), ("sagittal-ish (axis 0)", "coronal-ish (axis 1)", "axial (axis 2)")):
        ax.imshow(Hs.max(axis=axis).T, cmap="gray", vmin=-100, vmax=600, origin="lower")
        for k, c in cols.items():
            m_ = (Lx == k) & (L != k) if k in (820, 850) else (Lx == k)
            if m_.any():
                pr = m_.any(axis=axis).T.astype(float); ax.contourf(pr, levels=[0.5, 1.5], colors=[c], alpha=0.45); ax.contour(pr, levels=[0.5], colors=[c], linewidths=0.8)
        ax.contour((L > 0).any(axis=axis).T.astype(float), levels=[0.5], colors="yellow", linewidths=0.5); ax.set_title(ttl); ax.set_axis_off()
    plt.suptitle(f"case {P['case']} — great vessels grown from the labels along the bright lumen (yellow = MM-WHS labels; red aorta ext, blue PA ext, pink pulmonary veins, light-blue SVC, teal IVC)", fontsize=11)
    plt.tight_layout(); plt.savefig(os.path.join(OUT, "great_vessels_check.png"), dpi=80)
    print(json.dumps(rep["structures"], indent=0)[:1500]); print(f"-> {OUT}  ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
