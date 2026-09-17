# -*- coding: utf-8 -*-
"""Step 27 -- parametric TRICUSPID and PULMONARY valves fitted to the patient's annuli (labels), as watertight solids.

Annuli from the label contacts (extended label grid): tricuspid = RV(600)|RA(550) contact, pulmonary = RV(600)|PA(850)
contact -> centre, plane normal (PCA of the contact patch, oriented into the RV for the TV and towards the PA for
the PV), radius = 90th-percentile in-plane distance of the contact voxels.
Leaflets (literature proportions, scaled by the fitted radius; NOT the patient's leaflets -- CT does not show them):
  tricuspid: 3 leaflets, anterior (140 deg, height 1.15 r), septal (120 deg, 0.9 r, centred on the direction to the
             LV = the interventricular septum), posterior (100 deg, 0.9 r); funnel towards the RV apex, free edges
             converging (closed / systolic pose); belly outward
  pulmonary: 3 semilunar cusps (120 deg each, height 0.9 r, belly 0.4 h) -- same construction as the aortic generator
Each leaflet = thick grid solid (1.0 mm), attachment ring pushed 1.0 mm into the wall so booleans fuse it.
Outputs: <valves dir>/tricuspid_valve_parametric.stl, pulmonary_valve_parametric.stl, right_valves.json
(frame_A_patient/ for 1009, CT/cases/<id>/valves/ otherwise).  No chordae / papillary muscles on the right side.
"""
import os, json, time
import numpy as np, trimesh
from scipy import ndimage
from case_paths import paths, geometry, HERE
P = paths(); G = geometry(); T = np.asarray(G["T"])[:3, 3]
EXT = os.path.join(P["base"], "labels_extended.npz")
OUT = os.path.join(HERE, "frame_A_patient") if P["legacy"] else os.path.join(P["base"], "valves"); os.makedirs(OUT, exist_ok=True)
THICK, N_T, N_H, EMBED = 1.0, 48, 26, 1.0
unit = lambda v: v / (np.linalg.norm(v) + 1e-12)


def annulus(L, A, a, b, toward_pts):
    st = np.ones((3, 3, 3), bool)
    c = (L == a) & ndimage.binary_dilation(L == b, structure=st, iterations=2)
    c |= (L == b) & ndimage.binary_dilation(L == a, structure=st, iterations=2)
    pts = trimesh.transform_points(np.argwhere(c).astype(float), A) + T
    centre = pts.mean(0); w, v = np.linalg.eigh(np.cov((pts - centre).T)); n = v[:, 0]
    if (toward_pts.mean(0) - centre) @ n < 0: n = -n
    inpl = (pts - centre) - np.outer((pts - centre) @ n, n); r = float(np.percentile(np.linalg.norm(inpl, axis=1), 90))
    return centre, unit(n), r, int(c.sum())


def frame(n, ref):
    u = unit(np.cross(n, ref)) if abs(unit(ref) @ n) < 0.95 else unit(np.cross(n, [1.0, 0, 0])); return u, np.cross(n, u)


def thick_grid_solid(mid, normals, t):
    """mid: (nt, nh, 3) surface points, normals: (nt, nh, 3) unit; returns a watertight thick solid."""
    top = mid + 0.5 * t * normals; bot = mid - 0.5 * t * normals
    nt, nh = mid.shape[:2]; V = np.concatenate([top.reshape(-1, 3), bot.reshape(-1, 3)]); off = nt * nh
    idx = lambda i, j: i * nh + j; F = []
    for i in range(nt - 1):
        for j in range(nh - 1):
            a, b, c, d = idx(i, j), idx(i + 1, j), idx(i + 1, j + 1), idx(i, j + 1)
            F += [[a, b, c], [a, c, d], [off + a, off + c, off + b], [off + a, off + d, off + c]]
    for i in range(nt - 1):                                  # j = 0 and j = nh-1 edges
        a, b = idx(i, 0), idx(i + 1, 0); F += [[a, off + b, b], [a, off + a, off + b]]
        a, b = idx(i, nh - 1), idx(i + 1, nh - 1); F += [[a, b, off + b], [a, off + b, off + a]]
    for j in range(nh - 1):                                  # i = 0 and i = nt-1 edges
        a, b = idx(0, j), idx(0, j + 1); F += [[a, b, off + b], [a, off + b, off + a]]
        a, b = idx(nt - 1, j), idx(nt - 1, j + 1); F += [[a, off + b, b], [a, off + a, off + b]]
    m = trimesh.Trimesh(V, np.array(F), process=True); m.update_faces(m.nondegenerate_faces()); m.remove_unreferenced_vertices()
    trimesh.repair.fix_normals(m); return m


def leaflet(centre, n, u, v, r, th0, th1, height, belly_frac, funnel_in, toward_axis_sign):
    """AV-type leaflet: hangs from the annulus ring along +n*toward_axis_sign (into the ventricle), free edge converges
    to funnel_in*r; semilunar cusps use funnel_in ~ 0.55 with belly and scallop."""
    ths = np.linspace(th0, th1, N_T); fs = np.linspace(0, 1, N_H); mid = np.zeros((N_T, N_H, 3))
    for i, th in enumerate(ths):
        radial = np.cos(th) * u + np.sin(th) * v; ang = (th - th0) / (th1 - th0); scallop = np.sin(np.pi * ang) ** 0.6
        for j, f in enumerate(fs):
            rr = (r + EMBED) * (1 - f) + funnel_in * r * f                                      # radius shrinks towards the free edge
            drop = height * f * (0.35 + 0.65 * scallop)                                         # deeper at the leaflet centre
            bulge = belly_frac * height * np.sin(np.pi * f) * scallop
            mid[i, j] = centre + rr * radial + toward_axis_sign * drop * n + bulge * radial
    # normals by finite differences
    du = np.gradient(mid, axis=0); dv = np.gradient(mid, axis=1); nrm = np.cross(du, dv); nrm /= np.linalg.norm(nrm, axis=2)[..., None] + 1e-12
    return thick_grid_solid(mid, nrm, THICK)


def main():
    t0 = time.time(); z = np.load(EXT); L = z["L"].astype(np.int16); A = z["affine"]
    W = lambda k: trimesh.transform_points(np.argwhere(L == k)[::7].astype(float), A) + T
    rv, lv, pa = W(600), W(500), W(850)
    rep = {}
    # ---- tricuspid ----
    c, n, r, nv = annulus(L, A, 600, 550, rv)                # n points into the RV
    sept = unit((lv.mean(0) - c) - ((lv.mean(0) - c) @ n) * n); u, v = frame(n, sept)          # u ~ septal direction
    th_s = np.arctan2(sept @ v, sept @ u)
    spans = {"septal": (th_s - np.radians(60), th_s + np.radians(60), 0.9), "anterior": (th_s + np.radians(60), th_s + np.radians(200), 1.15), "posterior": (th_s + np.radians(200), th_s + np.radians(300), 0.9)}
    tv = trimesh.util.concatenate([leaflet(c, n, u, v, r, a, b, hh * r, 0.15, 0.12, +1.0) for a, b, hh in spans.values()])
    tv.export(os.path.join(OUT, "tricuspid_valve_parametric.stl"))
    rep["tricuspid"] = dict(centre_mm=c.round(2).tolist(), normal_into_RV=n.round(4).tolist(), annulus_r_mm=round(r, 1), contact_voxels=nv, leaflets={k: dict(span_deg=round(np.degrees(b - a)), height_mm=round(hh * r, 1)) for k, (a, b, hh) in spans.items()}, faces=int(len(tv.faces)), volume_mL=round(float(abs(tv.volume)) / 1000, 2), watertight_leaflets=all(p.is_watertight for p in tv.split(only_watertight=False)))
    # ---- pulmonary ----
    c2, n2, r2, nv2 = annulus(L, A, 600, 850, pa)            # n2 points into the PA
    u2, v2 = frame(n2, sept)
    pv = trimesh.util.concatenate([leaflet(c2, n2, u2, v2, r2, k * 2 * np.pi / 3, (k + 1) * 2 * np.pi / 3, 0.9 * r2, 0.40, 0.45, +1.0) for k in range(3)])
    pv.export(os.path.join(OUT, "pulmonary_valve_parametric.stl"))
    rep["pulmonary"] = dict(centre_mm=c2.round(2).tolist(), normal_into_PA=n2.round(4).tolist(), annulus_r_mm=round(r2, 1), contact_voxels=nv2, cusp_height_mm=round(0.9 * r2, 1), faces=int(len(pv.faces)), volume_mL=round(float(abs(pv.volume)) / 1000, 2), watertight_leaflets=all(p.is_watertight for p in pv.split(only_watertight=False)))
    rep["notes"] = ["leaflet shapes are literature proportions scaled to the fitted annulus -- not the patient's leaflets", "closed (systolic) pose for the tricuspid, semilunar cusps for the pulmonary", "no chordae / papillary muscles on the right side", "1.0 mm thick solids, attachment ring embedded 1 mm into the wall"]
    json.dump(rep, open(os.path.join(OUT, "right_valves.json"), "w"), indent=1)
    print(json.dumps({k: (v if k == "notes" else {kk: vv for kk, vv in v.items() if kk in ("annulus_r_mm", "contact_voxels", "faces", "volume_mL", "watertight_leaflets")}) for k, v in rep.items()}, indent=0), f"({time.time()-t0:.0f}s) -> {OUT}")


if __name__ == "__main__":
    main()
