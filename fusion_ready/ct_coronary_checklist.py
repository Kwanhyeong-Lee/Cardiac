# -*- coding: utf-8 -*-
"""Step 28 -- is anything missing from the coronary tree?  Two checks per case.

A. Anatomical checklist (SCCT-style segments) against coronary.json: LM; LAD proximal/mid/distal by trunk length;
   diagonals (D >= 8 mm); LCx proximal/distal; obtuse marginals (OM >= 8 mm); ramus; RCA proximal/mid/distal; PDA;
   PLV; RV / acute-marginal / conus branches (RV-br).  Dominance from where the PDA comes from.
B. Unclaimed vessel candidates in the image: tubular, bright voxels in the epicardial band (vesselness >= V_MIN and
   HU >= HU_MIN) that are farther than D_TREE from the extracted tree -- grouped into components with size, length,
   mean HU, nearest chamber and position -> "possibly missed artery" vs "probably vein" by HU.
Outputs: <coronary dir>/coronary_checklist.json + coronary_checklist.md
Env: CASE (paths/geometry as everywhere).
"""
import os, json, time
import numpy as np, nibabel as nib, trimesh
from scipy import ndimage
from case_paths import paths, geometry, dist_to
P = paths(); G = geometry(); COR = P["coronary"]; T = np.asarray(G["T"])[:3, 3]
V_MIN, HU_MIN, D_TREE, MIN_ML, HU_ARTERY = 0.08, 200.0, 3.0, 0.15, 300.0
t0 = time.time()


def checklist(cor):
    br = cor["branches"]; L = cor["length_by_name_mm"]; tr = cor["trunks"]
    def tip(nm): return float(tr[nm]["gd"][-1]) if nm in tr else 0.0
    lad, lcx, rca = tip("LAD"), tip("LCx"), tip("RCA")
    rows = []
    def seg(name, present, detail, note=""): rows.append(dict(segment=name, present=bool(present), detail=detail, note=note))
    seg("LM", L.get("LM", 0) > 2, f"{L.get('LM', 0)} mm")
    seg("LAD proximal (0-35 mm)", lad >= 15, f"trunk to {lad:.0f} mm"); seg("LAD mid (35-70 mm)", lad >= 50, f"trunk to {lad:.0f} mm"); seg("LAD distal (>70 mm, to apex)", lad >= 85, f"trunk to {lad:.0f} mm", "" if lad >= 85 else "thin distal LAD often below CT resolution / partial volume")
    d = sorted([b["len_mm"] for b in br if b["name"] == "D" and b["len_mm"] >= 8], reverse=True); seg("diagonals (D1, D2 ...)", len(d) >= 1, f"{len(d)} branch(es) >= 8 mm: {d[:4]}")
    seg("septal perforators", False, "-", "intramyocardial, 1 mm: not resolvable on this CT (expected absence)")
    seg("LCx proximal", lcx >= 12, f"trunk to {lcx:.0f} mm"); seg("LCx distal (> 40 mm)", lcx >= 40, f"trunk to {lcx:.0f} mm", "" if lcx >= 40 else "LCx runs under the LA appendage / next to the great cardiac vein: often lost or vein-pruned")
    om = sorted([b["len_mm"] for b in br if b["name"] == "OM" and b["len_mm"] >= 8], reverse=True); seg("obtuse marginals (OM1, OM2 ...)", len(om) >= 1, f"{len(om)} branch(es) >= 8 mm: {om[:4]}")
    ri = [b["len_mm"] for b in br if b["name"] == "RI"]; seg("ramus intermedius", len(ri) > 0, f"{ri}" if ri else "none", "present in ~20-30 % of people; absence is normal")
    seg("RCA proximal (0-35 mm)", rca >= 15, f"trunk to {rca:.0f} mm"); seg("RCA mid (35-70 mm)", rca >= 50, f"trunk to {rca:.0f} mm"); seg("RCA distal (> 70 mm, to the crux)", rca >= 85, f"trunk to {rca:.0f} mm")
    rvb = [b["len_mm"] for b in br if b["name"] == "RV-br" and b["len_mm"] >= 6]; seg("conus / RV / acute marginal branches", len(rvb) >= 1, f"{len(rvb)} RV-side branch(es) >= 6 mm: {sorted(rvb, reverse=True)[:4]}")
    seg("SA-nodal / AV-nodal arteries", False, "-", "0.5-1 mm: not resolvable (expected absence)")
    pda = L.get("PDA", 0); plv = L.get("PLV", 0); seg("PDA", pda >= 10, f"{pda} mm"); seg("PLV", plv >= 8, f"{plv} mm")
    if pda >= 10: dom = "right-dominant (PDA from the RCA)"
    elif lcx >= 60 and rca < 50: dom = "left-dominant suspected (short RCA, long LCx) -- PDA not resolved"
    else: dom = "undetermined (PDA not resolved; distal RCA / LCx not visible)"
    return rows, dom


def candidates():
    """bright tubular voxels in the band not explained by the tree."""
    vz = np.load(os.path.join(COR, "vesselness.npz")); V = vz["V"].astype(np.float32); lo = vz["lo"]; sp = np.array(vz["sp"], float)
    mz = np.load(os.path.join(COR, "coronary_mask.npz")); final = mz["final"]; b0 = mz["b0"]
    img = nib.load(P["image"]); lab = nib.load(P["label"]); A = img.affine
    sl = tuple(slice(int(a), int(a) + n) for a, n in zip(lo, V.shape))
    I = np.asanyarray(img.dataobj)[sl].astype(np.float32); L = np.asanyarray(lab.dataobj)[sl].astype(np.int16)
    tree = np.zeros(V.shape, bool); tree[tuple(slice(int(a), int(a) + n) for a, n in zip(b0, final.shape))] = final
    cand = (V >= V_MIN) & (I >= HU_MIN) & (L == 0) & (dist_to(tree, sp) > D_TREE) & (dist_to(L > 0, sp) <= 12.0)
    lbl, n = ndimage.label(cand, structure=np.ones((3, 3, 3))); vox_mL = np.prod(sp) / 1000
    sizes = ndimage.sum(cand, lbl, range(1, n + 1)) * vox_mL; out = []
    labs = {500: "LV", 205: "LV", 600: "RV", 420: "LA", 550: "RA", 820: "aorta", 850: "PA"}
    _, ind = ndimage.distance_transform_edt(L == 0, sampling=sp, return_indices=True)
    cLV = trimesh.transform_points((np.argwhere(L == 500)[::37] + lo).astype(float), A).mean(0); cRV = trimesh.transform_points((np.argwhere(L == 600)[::37] + lo).astype(float), A).mean(0); mid = (cLV + cRV) / 2
    # great vessels already modelled by ct_great_vessels.py (pulmonary veins, SVC, PA / aorta extensions) are not coronaries
    ext_p = os.path.join(P["base"], "labels_extended.npz"); GV = None
    if os.path.exists(ext_p):
        z = np.load(ext_p); Lx = z["L"]; Ax = z["affine"]; spx = np.array(z["spacing"], float)
        gv = np.isin(Lx, (820, 850, 901, 902, 903)); GV = (ndimage.binary_dilation(gv, iterations=2), np.linalg.inv(Ax))
    skipped_gv = 0
    for k in np.argsort(sizes)[::-1]:
        if sizes[k] < MIN_ML: break
        m = lbl == k + 1; pts = np.argwhere(m); w = trimesh.transform_points((pts + lo).astype(float), A)
        if GV is not None:
            gi = np.round(trimesh.transform_points(w, GV[1])).astype(int); ok = (gi >= 0).all(1) & (gi < np.array(GV[0].shape)).all(1)
            frac = GV[0][tuple(gi[ok].T)].mean() if ok.any() else 0.0
            if frac > 0.5: skipped_gv += 1; continue
        c = w.mean(0); ev = np.sqrt(np.maximum(np.linalg.eigvalsh(np.cov((w - c).T)), 1e-9)); hu = float(I[m].mean())
        near = labs.get(int(L[tuple(ind[:, pts[0][0], pts[0][1], pts[0][2]])]), "?")
        dtree = float(dist_to(tree, sp)[m].min())
        out.append(dict(volume_mL=round(float(sizes[k]), 2), length_mm=round(float(4 * ev[-1]), 1), elongation=round(float(ev[-1] / max(ev[0], 1e-6)), 1), mean_HU=round(hu), nearest_chamber=near,
                        anterior_mm=round(float(c[1] - mid[1]), 1), superior_mm=round(float(c[2] - mid[2]), 1), min_dist_to_tree_mm=round(dtree, 1), centre_frame=(c + T).round(1).tolist(),
                        verdict=("possibly missed ARTERY segment" if hu >= HU_ARTERY else "probably VEIN (HU below arterial)") + (" -- near the tree, may be a pruned continuation" if dtree < 6 else "")))
        if len(out) >= 12: break
    print(f"  (skipped {skipped_gv} candidate(s) that are modelled great vessels)")
    return out


def main():
    cor = json.load(open(os.path.join(COR, "coronary.json"))); rows, dom = checklist(cor)
    cands = candidates()
    rep = dict(case=P["case"], dominance=dom, checklist=rows, unclaimed_candidates=cands, veins_pruned=cor.get("veins_dropped", [])[:10], params=dict(V_MIN=V_MIN, HU_MIN=HU_MIN, D_TREE=D_TREE, MIN_ML=MIN_ML, HU_ARTERY=HU_ARTERY))
    json.dump(rep, open(os.path.join(COR, "coronary_checklist.json"), "w"), indent=1)
    with open(os.path.join(COR, "coronary_checklist.md"), "w", encoding="utf-8") as f:
        f.write(f"# Coronary completeness — case {P['case']}\n\nDominance: **{dom}**\n\n| segment | present | detail | note |\n|---|---|---|---|\n")
        for r in rows: f.write(f"| {r['segment']} | {'✓' if r['present'] else '✗'} | {r['detail']} | {r['note']} |\n")
        f.write(f"\n## Bright tubular structures NOT in the tree (candidates; V >= {V_MIN}, HU >= {HU_MIN:.0f}, > {D_TREE:.0f} mm from the tree)\n\n| mL | length mm | HU | nearest | anterior mm | superior mm | dist to tree | verdict |\n|---|---|---|---|---|---|---|---|\n")
        for c in cands: f.write(f"| {c['volume_mL']} | {c['length_mm']} | {c['mean_HU']} | {c['nearest_chamber']} | {c['anterior_mm']} | {c['superior_mm']} | {c['min_dist_to_tree_mm']} | {c['verdict']} |\n")
        f.write(f"\nVein-pruned branches (first 10): {rep['veins_pruned']}\n")
    print(f"dominance: {dom}"); [print(f"  {'✓' if r['present'] else '✗'} {r['segment']:40s} {r['detail']}") for r in rows]
    print(f"unclaimed candidates: {len(cands)}"); [print(f"   {c['volume_mL']} mL {c['length_mm']} mm HU {c['mean_HU']} near {c['nearest_chamber']} -> {c['verdict']}") for c in cands[:8]]
    print(f"-> {COR}  ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
