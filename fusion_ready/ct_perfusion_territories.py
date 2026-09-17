# -*- coding: utf-8 -*-
"""Step 20 -- coronary perfusion territories of the LV myocardium (case 1009) + AHA 17-segment table
+ mass at risk per occlusion site.  Everything in frame A (RAS, mm).

Myocardium: same continuous-field mask as ct_hires_lv.py (F_myo > 0, largest component), voxel level.
Territories: every myocardial voxel -> nearest point of the coronary centrelines (Voronoi rule, the
standard for CT-based territory maps), vessel = trunk the point belongs to (LAD / LCx / RCA); side
branches inherit the trunk they leave from; the LM is excluded so its neighbourhood splits LAD/LCx.
The visible tree stops at ~48 mm (RCA) / ~30 mm (LCx) and has no PDA, so the inferior/lateral walls would
be assigned by extrapolation.  Groove PRIORS fill that in honestly: the posterior interventricular groove
(PDA), the basal inferolateral ring (PLV), the basal lateral ring (distal LCx) and a lateral-wall line (OM)
are located from THIS patient's chamber labels; only which trunk feeds them is assumed (right-dominant map
used for the table, left-dominant given as the other bound).  Three maps are reported: visible-only,
+priors RD, +priors LD; every voxel/segment also carries the distance to the nearest VISIBLE vessel so
measurement and assumption stay distinguishable (D_UNSURE = 25 mm).

AHA 17 segments: long axis MV centre -> apex; basal/mid/apical thirds of the cavity length, apex cap
beyond the endocardial apex; angles from the septal centre (LV myocardium touching the RV blood label
at mid level) -- segments 2+3 are the septum by construction, as in the AHA definition.
Standard territories (Cerqueira 2002): LAD 1,2,7,8,13,14,17; RCA 3,4,9,10,15; LCx 5,6,11,12,16.

Outputs -> CT/coronary/territories/:
  territory_report.json, territory_table.md, territory_map.png (bull's-eye + 3D), scenarios (mass at risk),
  LV_myocardium_territories.ply (hires mesh with vertex colours by territory).
"""
import os, json, time, warnings
import numpy as np, nibabel as nib, trimesh
from scipy import ndimage
from scipy.spatial import cKDTree
from skimage import measure
warnings.filterwarnings("ignore")
from case_paths import paths as _paths, geometry as _geometry, MMWHS
_P = _paths(); _G = _geometry()
HERE = os.path.dirname(os.path.abspath(__file__)); CT = os.path.join(HERE, "CT"); COR = _P["coronary"]; HIRES = _P["hires"]; OUT = _P["territories"]; os.makedirs(OUT, exist_ok=True); CASE = _P["case"]
SIG_L, SIG_H, MARGIN_VOX, RHO, D_UNSURE, D_TRUNK = 1.0, 0.6, 12, 1.05, 25.0, 0.8
STD = {1: "LAD", 2: "LAD", 7: "LAD", 8: "LAD", 13: "LAD", 14: "LAD", 17: "LAD", 3: "RCA", 4: "RCA", 9: "RCA", 10: "RCA", 15: "RCA", 5: "LCx", 6: "LCx", 11: "LCx", 12: "LCx", 16: "LCx"}
SEGNAME = {1: "basal anterior", 2: "basal anteroseptal", 3: "basal inferoseptal", 4: "basal inferior", 5: "basal inferolateral", 6: "basal anterolateral",
           7: "mid anterior", 8: "mid anteroseptal", 9: "mid inferoseptal", 10: "mid inferior", 11: "mid inferolateral", 12: "mid anterolateral",
           13: "apical anterior", 14: "apical septal", 15: "apical inferior", 16: "apical lateral", 17: "apex"}
COL = {"LAD": (0.85, 0.15, 0.15), "LCx": (0.95, 0.60, 0.10), "RCA": (0.15, 0.40, 0.85), "uncertain": (0.6, 0.6, 0.6)}
PRIOR_TINT = lambda c: 0.55 * c + 0.45     # pale = this voxel was assigned by a groove prior, not by a visible vessel (export_unreal.py reuses it)
unit = lambda v: v / (np.linalg.norm(v) + 1e-12)


def polyline_dist(P, Q):
    """min distance from each point of P to polyline Q (segments)."""
    A, B = Q[:-1], Q[1:]; AB = B - A; L2 = (AB ** 2).sum(1) + 1e-12
    out = np.full(len(P), np.inf)
    for i in range(0, len(P), 4000):
        p = P[i:i + 4000]; t = np.clip(((p[:, None, :] - A[None]) * AB[None]).sum(2) / L2[None], 0, 1)
        d = np.linalg.norm(p[:, None, :] - (A[None] + t[..., None] * AB[None]), axis=2); out[i:i + 4000] = d.min(1)
    return out


def main():
    t0 = time.time()
    # ---------- myocardium voxels (frame A) ----------
    img = nib.load(os.path.join(MMWHS, f"ct_train_{CASE}_image.nii.gz")); lab = nib.load(os.path.join(MMWHS, f"ct_train_{CASE}_label.nii.gz"))
    A = img.affine; sp = np.array(img.header.get_zooms()[:3]); vox_mL = np.prod(sp) / 1000
    thr = float(_G["thr_HU"]); T = np.array(_G["T"]); AXIS = unit(np.array(_G["axis"])); MV_C = np.array(_G["mv_centre"])
    L = np.asanyarray(lab.dataobj); lv = (L == 500) | (L == 205)
    idx = np.argwhere(lv); lo = np.maximum(idx.min(0) - MARGIN_VOX, 0); hi = np.minimum(idx.max(0) + MARGIN_VOX + 1, L.shape); sl = tuple(slice(a, b) for a, b in zip(lo, hi))
    Lc = np.asarray(L[sl]); rv_c = trimesh.transform_points(np.argwhere(L == 600)[::41].astype(float), A).mean(0) + T[:3, 3]; del L, lv, idx
    I = np.asanyarray(img.dataobj)[sl].astype(np.float32)
    sig = lambda s: (s, s, s * sp[0] / sp[2])
    Lf = ndimage.gaussian_filter(((Lc == 500) | (Lc == 205)).astype(np.float32), sig(SIG_L)); L5 = ndimage.gaussian_filter((Lc == 500).astype(np.float32), sig(SIG_L)); Hs = ndimage.gaussian_filter(I, sig(SIG_H))
    F_blood = np.minimum(L5 - 0.5, (Hs - thr) / 200.0); M = np.minimum(Lf - 0.5, -F_blood) > 0; del Lf, L5, Hs, I
    lbl, n = ndimage.label(M); sizes = ndimage.sum(M, lbl, range(1, n + 1)); M = lbl == (1 + int(np.argmax(sizes))); del lbl
    blood = F_blood > 0; del F_blood
    vox = np.argwhere(M); P = trimesh.transform_points((vox + lo).astype(float), A) + T[:3, 3]          # frame A
    Pb = trimesh.transform_points((np.argwhere(blood)[::7] + lo).astype(float), A) + T[:3, 3]
    ax_depth = (P - MV_C) @ AXIS; L_cav = float(((Pb - MV_C) @ AXIS).max())
    lv_mass_g = M.sum() * vox_mL * RHO
    print(f"myocardium {M.sum()*vox_mL:.1f} mL = {lv_mass_g:.0f} g ({len(P):,} voxels); cavity length {L_cav:.1f} mm  ({time.time()-t0:.0f}s)")

    # ---------- septal reference direction (mid level, myocardium within 3 mm of the RV blood label) ----------
    dRV = ndimage.distance_transform_edt(Lc != 600, sampling=sp)
    sept = M & (dRV <= 3.0); Ps = trimesh.transform_points((np.argwhere(sept) + lo).astype(float), A) + T[:3, 3]
    ds = (Ps - MV_C) @ AXIS; Ps = Ps[(ds > L_cav / 3) & (ds < 2 * L_cav / 3)]
    lv_c_mid = P[(ax_depth > L_cav / 3) & (ax_depth < 2 * L_cav / 3)].mean(0)
    def inplane(v): v = v - np.outer(v @ AXIS, AXIS) if v.ndim == 2 else v - (v @ AXIS) * AXIS; return v
    e_sept = unit(inplane(Ps.mean(0) - lv_c_mid))                           # towards the septum
    e_perp = unit(np.cross(AXIS, e_sept)); post_inf = unit(inplane(np.array([0, -1.0, -1.0])))
    if e_perp @ post_inf < 0: e_perp = -e_perp                              # increasing angle = septum -> inferior -> lateral -> anterior
    # septal angular half-width from the insertion points (for the report only)
    vs = inplane(Ps - lv_c_mid); th_s = np.degrees(np.arctan2(vs @ e_perp, vs @ e_sept)); sept_span = (float(np.percentile(th_s, 2)), float(np.percentile(th_s, 98)))
    print(f"septal centre direction set; septum spans {sept_span[0]:.0f}..{sept_span[1]:.0f} deg around it (AHA assumes -60..+60)")

    # ---------- AHA segments per voxel ----------
    v = inplane(P - lv_c_mid); th = np.degrees(np.arctan2(v @ e_perp, v @ e_sept)) % 360.0
    t = ax_depth / L_cav
    seg = np.zeros(len(P), int)
    ring6 = np.array([3, 4, 5, 6, 1, 2]); ring4 = np.array([14, 15, 16, 13])
    b = t < 1 / 3; m = (t >= 1 / 3) & (t < 2 / 3); a = (t >= 2 / 3) & (t < 1.0); cap = t >= 1.0
    seg[b] = ring6[(th[b] // 60).astype(int) % 6]; seg[m] = ring6[(th[m] // 60).astype(int) % 6] + 6
    seg[a] = ring4[(((th[a] + 45) % 360) // 90).astype(int) % 4]; seg[cap] = 17

    # ---------- coronary points with vessel labels ----------
    cor = json.load(open(os.path.join(COR, "coronary.json")))
    trunks = {k: np.array(v_["pts"]) for k, v_ in cor["trunks"].items()}; trunk_gd = {k: np.array(v_["gd"]) for k, v_ in cor["trunks"].items()}
    pts, vessel, gd_pt, branch_of = [], [], [], []
    for cid, cl in cor["centrelines"].items():
        Q = np.array(cl["pts"]);
        if cl["name"] == "LM" or len(Q) < 2: continue
        dmin = {k: polyline_dist(Q, tp) for k, tp in trunks.items()}
        on = [k for k, d_ in dmin.items() if np.median(d_) < D_TRUNK]
        SYSTEM = {"LAD": "LAD", "D": "LAD", "LCx": "LCx", "OM": "LCx", "RI": "LCx", "RCA": "RCA", "PDA": "RCA", "PLV": "RCA", "RV-br": "RCA"}
        named = SYSTEM.get(cl["name"])                                       # topology names from ct_coronary_seg (preferred)
        if named is not None and named in trunks: k = named
        elif on: k = on[0]
        else: k = min(dmin, key=lambda kk: min(dmin[kk][0], dmin[kk][-1]))
        if on and on[0] == k:                                                # part of that trunk: take the trunk's own geodesic distance
            kd = cKDTree(trunks[k]); _, j = kd.query(Q); g = trunk_gd[k][j]
        else:                                                               # side branch: geodesic = parent trunk distance at the junction + arc length
            if dmin[k][-1] < dmin[k][0]: Q = Q[::-1]
            kd = cKDTree(trunks[k]); _, j0 = kd.query(Q[0]); g0 = trunk_gd[k][j0]
            g = g0 + np.r_[0, np.cumsum(np.linalg.norm(np.diff(Q, axis=0), axis=1))]
        pts.append(Q); vessel += [k] * len(Q); gd_pt.append(g); branch_of += [int(cid)] * len(Q)
    pts = np.concatenate(pts); vessel = np.array(vessel); gd_pt = np.concatenate(gd_pt); branch_of = np.array(branch_of)
    print("coronary points:", {k: int((vessel == k).sum()) for k in ("LAD", "LCx", "RCA")})

    # ---------- groove priors for the segments the scan does not resolve ----------
    # The tree stops at ~48 mm (RCA) / ~30 mm (LCx) and has no PDA. Where those vessels RUN is not in doubt
    # anatomically -- the grooves between the chambers, which the labels give us for THIS patient -- only
    # which trunk feeds them (dominance) is assumed. Prior centrelines:
    #   PDA  : posterior interventricular groove = LV myocardium touching the RV label at the inferior
    #          insertion (theta 30..110 deg from the septal centre), one point per long-axis level
    #   PLV / distal LCx : the basal ring of the inferior-lateral wall (left AV groove), swept in theta;
    #          theta 60..130 -> PLV (RCA if right-dominant), 130..250 -> distal LCx
    r_in = np.linalg.norm(v, axis=1)
    def level_point(sel):
        return P[sel].mean(0) if sel.sum() >= 12 else None
    pda = [level_point((np.abs(t - tt) < 0.03) & (dRV[tuple(vox.T)] <= 3.5) & (th >= 30) & (th <= 110)) for tt in np.linspace(0.12, 0.85, 26)]
    pda = np.array([p_ for p_ in pda if p_ is not None])
    if sum(b_["len_mm"] for b_ in cor["branches"] if b_["name"] == "PDA") >= 20: pda = pda[:0]; print("visible PDA present -> no PDA prior")
    # obtuse-marginal line: the LCx's marginal branches descend the lateral wall (theta ~180) -- assumed present as in ~all hearts
    om = []
    for tt in np.linspace(0.15, 0.75, 14):
        sel = (np.abs(t - tt) < 0.03) & (np.abs(th - 180) < 5)
        if sel.sum() >= 12:
            rr = r_in[sel]; outer = sel.copy(); outer[np.where(sel)[0][rr < np.percentile(rr, 75)]] = False; om.append(P[outer].mean(0))
    om = np.array(om)
    ring = []
    for ta in np.arange(60, 252, 6):
        sel = (t >= 0.0) & (t <= 0.12) & (np.abs(((th - ta + 180) % 360) - 180) < 4)
        if sel.sum() >= 12:
            rr = r_in[sel]; outer = sel.copy(); outer[np.where(sel)[0][rr < np.percentile(rr, 75)]] = False; ring.append((ta, P[outer].mean(0)))
    plv = np.array([p_ for ta, p_ in ring if ta <= 130]); lcx_d = np.array([p_ for ta, p_ in ring if ta > 130])
    if sum(b_["len_mm"] for b_ in cor["branches"] if b_["name"] == "OM") >= 25: om = om[:0]; print("visible OM branches present -> no OM prior")
    print(f"priors: PDA {len(pda)} pts, PLV {len(plv)} pts, distal-LCx {len(lcx_d)} pts, OM {len(om)} pts")
    prior_sets = {"right-dominant": [(pda, "RCA"), (plv, "RCA"), (lcx_d, "LCx"), (om, "LCx")], "left-dominant": [(pda, "LCx"), (plv, "LCx"), (lcx_d, "LCx"), (om, "LCx")]}

    # ---------- Voronoi assignments: visible tree only / + priors (RD) / + priors (LD) ----------
    mass = lambda mask: float(mask.sum() * vox_mL * RHO)
    def assign(extra):
        allp = [pts] + [e for e, _ in extra if len(e)]; allv = [vessel] + [np.array([nm] * len(e)) for e, nm in extra if len(e)]
        src = np.r_[np.zeros(len(pts), bool), np.ones(sum(len(e) for e, _ in extra if len(e)), bool)]          # True = prior point
        kd_ = cKDTree(np.concatenate(allp)); d_, j_ = kd_.query(P); vv = np.concatenate(allv)
        return dict(kd=kd_, vessel=vv, dist=d_, j=j_, terr=vv[j_].copy(), from_prior=src[j_], src=src)
    kd_vis = cKDTree(pts); dist_vis, _ = kd_vis.query(P)
    maps = {"visible": assign([]), "priors_RD": assign(prior_sets["right-dominant"]), "priors_LD": assign(prior_sets["left-dominant"])}
    unsure = dist_vis > D_UNSURE
    per_vessel = {name: {k: round(mass(mp["terr"] == k), 1) for k in ("LAD", "LCx", "RCA")} for name, mp in maps.items()}
    via_prior = {k: round(mass((maps["priors_RD"]["terr"] == k) & maps["priors_RD"]["from_prior"]), 1) for k in ("LAD", "LCx", "RCA")}
    for name in maps: print(f"territory mass g [{name}]: " + ", ".join(f"{k} {per_vessel[name][k]}" for k in per_vessel[name]))
    print(f"of which assigned through a prior point (RD): {via_prior}; myocardium > {D_UNSURE:.0f} mm from any VISIBLE vessel: {mass(unsure):.0f} g ({100*unsure.mean():.0f} %)")
    # working map for the table / figure = priors, right-dominant; the visible-only map is kept alongside
    terr, dist, j = maps["priors_RD"]["terr"], maps["priors_RD"]["dist"], maps["priors_RD"]["j"]; terr_vis = maps["visible"]["terr"]; from_prior = maps["priors_RD"]["from_prior"]
    kd = maps["priors_RD"]["kd"]; vessel_all = maps["priors_RD"]["vessel"]; src_all = maps["priors_RD"]["src"]

    # ---------- 17-segment table ----------
    rows = []
    for s in range(1, 18):
        ms = seg == s; tot = mass(ms)
        frac = {k: float(((terr == k) & ms).sum()) / max(1, ms.sum()) for k in ("LAD", "LCx", "RCA")}
        fvis = {k: float(((terr_vis == k) & ms).sum()) / max(1, ms.sum()) for k in ("LAD", "LCx", "RCA")}
        maj = max(frac, key=frac.get); maj_vis = max(fvis, key=fvis.get); unc = float((unsure & ms).sum()) / max(1, ms.sum()); pri = float((from_prior & ms).sum()) / max(1, ms.sum())
        dmed = float(np.median(dist_vis[ms])) if ms.any() else None
        rows.append(dict(segment=s, name=SEGNAME[s], mass_g=round(tot, 1), standard=STD[s], patient_tree=maj, patient_frac=round(frac[maj], 2), visible_only=maj_vis, visible_only_frac=round(fvis[maj_vis], 2),
                         LAD=round(frac["LAD"], 2), LCx=round(frac["LCx"], 2), RCA=round(frac["RCA"], 2), via_prior_frac=round(pri, 2), far_from_visible_frac=round(unc, 2),
                         median_dist_to_visible_vessel_mm=round(dmed, 1), agree=bool(maj == STD[s]), measured=bool(unc < 0.5)))
    n_agree = sum(r["agree"] for r in rows); n_meas = sum(r["measured"] for r in rows); n_agree_meas = sum(r["agree"] for r in rows if r["measured"])
    print(f"AHA agreement: {n_agree}/17 overall; measured segments (>=50 % within {D_UNSURE:.0f} mm of a visible vessel): {n_meas}, agreement there {n_agree_meas}/{n_meas}")

    # ---------- occlusion scenarios: mass at risk = territory of all points downstream of the site ----------
    gd_all = np.r_[gd_pt, np.full(len(vessel_all) - len(gd_pt), 999.0)]        # prior points = distal to everything visible
    def downstream_mass(trunk, gd_cut):
        sel = (vessel_all == trunk) & (gd_all >= gd_cut)
        return mass(np.isin(j, np.where(sel)[0]))
    d1 = [b_ for b_ in cor["branches"] if b_["len_mm"] >= 15 and b_["name"] in ("D", "branch")]
    d1_gd = min([b_["geo_from_root_mm"][0] for b_ in d1 if b_["geo_from_root_mm"][0] > 15], default=40)
    scen = [("LM occlusion", per_vessel["priors_RD"]["LAD"] + per_vessel["priors_RD"]["LCx"]), ("proximal LAD (after LM)", downstream_mass("LAD", 2)),
            (f"mid LAD (after first diagonal, {d1_gd:.0f} mm)", downstream_mass("LAD", d1_gd + 1)), ("distal LAD (70 mm)", downstream_mass("LAD", 70)),
            ("proximal LCx", downstream_mass("LCx", 2)), ("proximal RCA", downstream_mass("RCA", 2)), ("mid RCA (beyond 25 mm)", downstream_mass("RCA", 25))]
    scen = [dict(site=s_, mass_at_risk_g=round(mm, 1), percent_of_LV=round(100 * mm / lv_mass_g, 1)) for s_, mm in scen]
    for s_ in scen: print(f"  {s_['site']:<45} {s_['mass_at_risk_g']:6.1f} g  {s_['percent_of_LV']:5.1f} %")

    # ---------- outputs ----------
    rep = dict(case=CASE, frame="A (RAS, mm)", lv_mass_g=round(lv_mass_g, 1), density_g_per_mL=RHO, cavity_length_mm=round(L_cav, 1), D_UNSURE_mm=D_UNSURE,
               septal_span_deg_around_centre=[round(x, 1) for x in sept_span], territory_mass_g=per_vessel, assigned_via_prior_g_RD=via_prior,
               priors=dict(PDA_pts=int(len(pda)), PLV_pts=int(len(plv)), distal_LCx_pts=int(len(lcx_d)), OM_pts=int(len(om)), rule="grooves from the patient's labels; dominance assumed (RD = right-dominant map used for the table/figure, LD given for the range)"),
               far_from_visible_mass_g=round(mass(unsure), 1), far_from_visible_percent=round(100 * float(unsure.mean()), 1), segments=rows, scenarios=scen,
               caveats=["territories from the VISIBLE proximal-mid tree only: no PDA/PLV, RCA to ~48 mm, LCx to ~30 mm -> inferior and inferolateral segments are extrapolated (see uncertain_frac)",
                        "dominance unknown from this scan (faint distal RCA); the AHA standard column assumes the common right-dominant pattern",
                        "Voronoi rule (nearest centreline point) ignores vessel calibre and flow; it is the accepted first-order territory model, not a perfusion measurement",
                        "mass at risk is anatomical (downstream territory mass); it says nothing about collaterals or viability"])
    json.dump(rep, open(os.path.join(OUT, "territory_report.json"), "w"), indent=1)
    with open(os.path.join(OUT, "territory_table.md"), "w", encoding="utf-8") as f:
        f.write(f"# Case 1009 — LV perfusion territories (frame A)\n\nLV mass {lv_mass_g:.0f} g (1.05 g/mL).\n\n| map | LAD g | LCx g | RCA g |\n|---|---|---|---|\n")
        for name, lab_ in [("visible", "visible tree only"), ("priors_RD", "visible + groove priors, right-dominant (used below)"), ("priors_LD", "visible + groove priors, left-dominant")]:
            f.write(f"| {lab_} | {per_vessel[name]['LAD']} | {per_vessel[name]['LCx']} | {per_vessel[name]['RCA']} |\n")
        f.write(f"\nMyocardium farther than {D_UNSURE:.0f} mm from any *visible* vessel point: {rep['far_from_visible_mass_g']} g ({rep['far_from_visible_percent']} %) — there the map is groove-prior extrapolation.\n\n")
        f.write("| seg | name | mass g | AHA standard | patient map (RD) | visible-only | LAD/LCx/RCA frac | via prior | far from visible | agree |\n|---|---|---|---|---|---|---|---|---|---|\n")
        for r in rows: f.write(f"| {r['segment']} | {r['name']} | {r['mass_g']} | {r['standard']} | {r['patient_tree']} ({r['patient_frac']}) | {r['visible_only']} ({r['visible_only_frac']}) | {r['LAD']}/{r['LCx']}/{r['RCA']} | {r['via_prior_frac']} | {r['far_from_visible_frac']} | {'✓' if r['agree'] else '✗'}{'' if r['measured'] else ' (prior)'} |\n")
        f.write("\n✓/✗ vs the AHA standard; '(prior)' = segment mostly beyond 25 mm of the visible tree, assignment rests on the groove prior + dominance assumption\n\n## Mass at risk per occlusion site (RD map)\n\n| site | g | % LV |\n|---|---|---|\n")
        for s_ in scen: f.write(f"| {s_['site']} | {s_['mass_at_risk_g']} | {s_['percent_of_LV']} |\n")
        f.write("\n" + "\n".join("- " + c for c in rep["caveats"]) + "\n")

    # mesh with vertex colours (hires myocardium) -- nearest coronary point per vertex
    myo = trimesh.load(os.path.join(HIRES, "LV_myocardium_CT_hires.stl"), process=False)
    dv, jv = kd.query(myo.vertices); tv = vessel_all[jv].astype(object)
    cols = np.array([COL[x] for x in tv]); cols[src_all[jv]] = PRIOR_TINT(cols[src_all[jv]])            # lighter where a prior point decides
    myo.visual.vertex_colors = np.c_[(cols * 255).astype(np.uint8), np.full(len(cols), 255, np.uint8)]
    myo.export(os.path.join(OUT, "LV_myocardium_territories.ply"))
    _pp = [e for e, _ in prior_sets["right-dominant"] if len(e)]
    np.savez_compressed(os.path.join(OUT, "territory_points.npz"), pts_all=kd.data, vessel_all=vessel_all.astype("U12"), src_all=src_all, prior_pts=np.concatenate(_pp) if _pp else np.zeros((0, 3)))
    np.savez_compressed(os.path.join(OUT, "territory_voxels.npz"), lo=lo, shape=np.array(M.shape), vox=vox.astype(np.int16), seg=seg.astype(np.int8), vessel_RD=np.array([{"LAD": 1, "LCx": 2, "RCA": 3}[x] for x in terr], np.int8), vessel_visible=np.array([{"LAD": 1, "LCx": 2, "RCA": 3}[x] for x in terr_vis], np.int8), from_prior=from_prior, far_from_visible=unsure, dist_visible=dist_vis.astype(np.float16))

    print(f"-> {OUT}  ({time.time()-t0:.0f}s)")
    if os.environ.get("SKIP_FIGURE") != "1": figure()


def figure():
    t0 = time.time()
    rep = json.load(open(os.path.join(OUT, "territory_report.json"))); rows = rep["segments"]; scen = rep["scenarios"]; per_vessel = rep["territory_mass_g"]; lv_mass_g = rep["lv_mass_g"]
    n_agree = sum(r["agree"] for r in rows); n_meas = sum(r["measured"] for r in rows); n_agree_meas = sum(r["agree"] for r in rows if r["measured"])
    z = np.load(os.path.join(OUT, "territory_points.npz")); kd = cKDTree(z["pts_all"]); vessel_all = z["vessel_all"].astype(object); src_all = z["src_all"]; prior_pts = z["prior_pts"]
    pr = rep["priors"]; pda, plv, lcx_d, om = [None] * pr["PDA_pts"], [None] * pr["PLV_pts"], [None] * pr["distal_LCx_pts"], [None] * pr["OM_pts"]
    myo = trimesh.load(os.path.join(HIRES, "LV_myocardium_CT_hires.stl"), process=False)
    # ---------- figure: bull's-eye + 3D ----------
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from matplotlib.patches import Wedge, Patch
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    fig = plt.figure(figsize=(20, 11))
    for k_, (title, key) in enumerate([("patient map (visible tree + groove priors, RD)\n% = majority share; pale = mostly prior-based; ✗ = differs from AHA", "patient_tree"), ("AHA 2002 standard assignment (right-dominant)", "standard")]):
        ax = fig.add_subplot(2, 3, 1 + k_); ax.set_aspect("equal"); ax.set_axis_off(); ax.set_title(title, fontsize=10)
        radii = {"b": (0.75, 1.0), "m": (0.5, 0.75), "a": (0.25, 0.5)}
        for r in rows:
            s = r["segment"]
            if s == 17: ring, i, n_ = None, 0, 1
            elif s <= 6: ring, i, n_ = "b", s - 1, 6
            elif s <= 12: ring, i, n_ = "m", s - 7, 6
            else: ring, i, n_ = "a", s - 13, 4
            # bull's-eye convention: anterior at 12 o'clock, septum on the left (viewer's), counter-clockwise 1..6 -> start angle 90 deg + i*60 going ccw
            vessel_name = r[key]
            face = COL[vessel_name]; alpha = 1.0 if key == "standard" else (0.35 if r["via_prior_frac"] >= 0.5 else 0.5 + 0.5 * r["patient_frac"])
            # AHA bull's-eye (seen from the apex): segment 1/7/13 centred at 12 o'clock, then counter-clockwise; septum at 9 o'clock
            if s == 17: w = plt.Circle((0, 0), 0.25, facecolor=face, edgecolor="k", alpha=alpha)
            else:
                span = 360 / n_; th0 = 90 - span / 2 + i * span
                w = Wedge((0, 0), radii[ring][1], th0, th0 + span, width=radii[ring][1] - radii[ring][0], facecolor=face, edgecolor="k", alpha=alpha)
            ax.add_patch(w)
            rr = 0.0 if s == 17 else np.mean(radii[ring]); ang = np.radians(90 + i * (360 / n_)) if s != 17 else 0.0
            txt = f"{s}\n{r['mass_g']:.0f} g" if key == "standard" else f"{s}\n{r['patient_frac']*100:.0f}%" + ("" if r["agree"] else " ✗")
            ax.text(rr * np.cos(ang), rr * np.sin(ang), txt, ha="center", va="center", fontsize=7.5)
        ax.set_xlim(-1.05, 1.05); ax.set_ylim(-1.05, 1.05)
        ax.text(0, 1.03, "anterior", ha="center", fontsize=8); ax.text(-1.03, 0, "septal", ha="center", va="center", rotation=90, fontsize=8); ax.text(1.03, 0, "lateral", ha="center", va="center", rotation=-90, fontsize=8); ax.text(0, -1.06, "inferior", ha="center", fontsize=8)
    ax = fig.add_subplot(2, 3, 3); ax.set_axis_off()
    ax.legend(handles=[Patch(color=COL[k], label=f"{k}  {per_vessel['priors_RD'][k]:.0f} g  (visible-only {per_vessel['visible'][k]:.0f}, left-dominant {per_vessel['priors_LD'][k]:.0f})") for k in ("LAD", "LCx", "RCA")], loc="upper left", fontsize=9, title=f"LV {lv_mass_g:.0f} g — territory mass by map")
    ax.text(0, 0.62, "mass at risk (RD map)\n" + "\n".join(f"{s_['site']}: {s_['mass_at_risk_g']:.0f} g ({s_['percent_of_LV']:.0f} %)" for s_ in scen) + f"\n\n{rep['far_from_visible_percent']:.0f} % of the LV is > {D_UNSURE:.0f} mm from any VISIBLE vessel:\nthere the colour comes from the groove priors\n(PDA {len(pda)}, PLV {len(plv)}, distal LCx {len(lcx_d)}, OM {len(om)} points) and the\ndominance assumption, not from this patient's vessels.", fontsize=8.5, va="top", family="monospace")
    # 3D: decimated hires mesh coloured per face
    dec = myo.simplify_quadric_decimation(face_count=45000); del myo
    bl_proxy = trimesh.load(os.path.join(HIRES, "lv_bloodpool_CT_hires.stl"), process=False).simplify_quadric_decimation(face_count=20000)
    d_bl, _ = cKDTree(bl_proxy.vertices).query(dec.triangles_center); dec.update_faces(d_bl > 3.0); dec.remove_unreferenced_vertices()   # KD-tree on vertices: trimesh closest_point OOMs here
    dvf, jvf = kd.query(dec.triangles_center); tf = vessel_all[jvf].astype(object)
    fcol = np.array([COL[x] for x in tf]); fcol[src_all[jvf]] = PRIOR_TINT(fcol[src_all[jvf]]); tube = trimesh.load(os.path.join(COR, "coronary_tree_print_frameA.stl"), process=False).simplify_quadric_decimation(face_count=15000)
    # the rest of the heart (RV, atria, great vessels) in light grey, so the RCA / LM sit on the chambers they run on
    ctx = trimesh.load(os.path.join(COR, "heart_labels_context_frameA.stl"), process=False).simplify_quadric_decimation(face_count=30000)
    lv_proxy = dec.simplify_quadric_decimation(face_count=12000)
    d_lv, _ = cKDTree(lv_proxy.vertices).query(ctx.triangles_center); ctx.update_faces(d_lv > 2.5); ctx.remove_unreferenced_vertices()
    for k_, (elev, azim, ttl) in enumerate([(10, 90, "anterior"), (-60, 90, "inferior"), (10, 180, "left lateral")]):
        ax = fig.add_subplot(2, 3, 4 + k_, projection="3d"); light = np.array([np.cos(np.radians(elev)) * np.cos(np.radians(azim)), np.cos(np.radians(elev)) * np.sin(np.radians(azim)), np.sin(np.radians(elev))])
        # orthographic view + back-face culling: the painter's sort then only has to order front faces
        ax.set_proj_type("ortho")
        fc_ctx = ctx.face_normals @ light > 0.05; fc_lv = dec.face_normals @ light > 0.0; fc_t = tube.face_normals @ light > -0.2
        lam = np.clip(dec.face_normals[fc_lv] @ light, 0, 1) * 0.7 + 0.3; lam_t = np.clip(tube.face_normals[fc_t] @ light, 0, 1) * 0.7 + 0.3; lam_c = np.clip(ctx.face_normals[fc_ctx] @ light, 0, 1) * 0.6 + 0.4
        tri = np.concatenate([ctx.triangles[fc_ctx], dec.triangles[fc_lv], tube.triangles[fc_t]])
        col = np.concatenate([np.c_[np.tile([0.90, 0.89, 0.87], (int(fc_ctx.sum()), 1)) * lam_c[:, None], np.ones(int(fc_ctx.sum()))], np.c_[fcol[fc_lv] * lam[:, None], np.ones(int(fc_lv.sum()))],
                              np.c_[np.tile([0.1, 0.1, 0.1], (int(fc_t.sum()), 1)) * lam_t[:, None], np.ones(int(fc_t.sum()))]])
        ax.add_collection3d(Poly3DCollection(tri, facecolors=col, edgecolors=col, linewidths=0.2, antialiased=False))   # edges = faces: no white seams between tiny triangles
        ax.scatter(prior_pts[:, 0], prior_pts[:, 1], prior_pts[:, 2], s=6, c="k", marker="x", depthshade=False)
        c = ctx.bounds.mean(0); r_ = (ctx.bounds[1] - ctx.bounds[0]).max() / 2 * 0.92
        ax.set_xlim(c[0] - r_, c[0] + r_); ax.set_ylim(c[1] - r_, c[1] + r_); ax.set_zlim(c[2] - r_, c[2] + r_); ax.view_init(elev=elev, azim=azim); ax.set_box_aspect((1, 1, 1)); ax.set_axis_off(); ax.set_title(f"LV territories (RD map) — {ttl}; black = visible tree, x = groove priors, grey = other chambers", fontsize=9)
    plt.suptitle(f"case {rep['case']} — LV coronary territories: visible tree + groove priors vs AHA 17-segment standard — agreement {n_agree}/17 (measured segments {n_agree_meas}/{n_meas})", fontsize=12)
    plt.tight_layout(); plt.savefig(os.path.join(OUT, "territory_map.png"), dpi=85)
    print(f"figure done ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    figure() if os.environ.get("RENDER_ONLY") == "1" else main()
