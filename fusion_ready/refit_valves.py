# -*- coding: utf-8 -*-
"""Regenerate the parametric mitral and aortic valves fitted to THIS patient's LV.

THE DEFECT. `generate_valves.py` hardcodes

    lv_axis = np.array([0.0, 0.0, -1.0])            # line 83
    center  = np.array([-0.0222, 0.0044, -0.1489])  # MV, metres
    annulus_radius = 0.0225                         # MV, metres

The measured LV long axis (PCA of the endocardial surface, MM-WHS case 1009) is
[0.448, -0.768, 0.458] -- about 60 degrees off -z. A 45 mm valve tilted 60 degrees from the
base plane pierces the wall on one side and floats outside on the other, which is exactly
what was measured: 54% of mitral vertices inside the LV, the rest up to 22 mm beyond the
wall, axial span 56 mm for a structure that should be ~25 mm tall.

THE FIX. Nothing about the valve *shape* is changed. The generator's own functions are
reused verbatim; only the three positioning constants are replaced with quantities measured
from the LV surface itself:

    lv_axis         PCA long axis, oriented base -> apex
    MV centre       centre of the basal cross-section, moved 3 mm apically so the annulus
                    sits just inside the cavity
    annulus_radius  0.9 x mean basal cross-section radius (annulus sits inside the rim)
    AV centre       MV centre + in-plane offset in the generator's own anterior direction,
                    at (r_mv + r_av) x 0.75 -- preserves the designed MV/AV relationship

Everything is verified afterwards with the same tests that exposed the defect, and the
before/after numbers are written to valve_refit.json. If the refit does not clearly beat
the original on those tests, the original files are left in place.

Usage:  PYTHONPATH=/tmp/pylibs python3 refit_valves.py
"""
import json, os, re, types, warnings
import numpy as np, trimesh
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GEN = os.path.join(ROOT, "generate_valves.py")
FRAME_A = os.path.join(HERE, "frame_A_patient")
OFFSET_A = np.array(json.load(open(os.path.join(HERE, "MANIFEST.json")))
                    ["groups"]["frame_A_patient"]["common_offset_mm"])   # patient mm -> frame A


def lv_geometry(lv):
    P = lv.vertices - lv.vertices.mean(0)
    _, V = np.linalg.eigh(P.T @ P)
    axis = V[:, -1]
    t = P @ axis
    def radius_at(frac):
        band = np.abs(t - (t.min() + frac * (t.max() - t.min()))) < 3.0
        Q = P[band]; Q = Q - (Q @ axis)[:, None] * axis
        return float(np.sqrt((Q ** 2).sum(1)).mean())
    if radius_at(0.08) > radius_at(0.92):        # wider end is the base
        axis = -axis; t = -t
    # now t.max() is the base end. axis points apex -> base; the generator wants base -> apex
    base_t = t.max()
    band = t > base_t - 6.0                      # basal 6 mm ring
    base_centre = lv.vertices.mean(0) + (P[band] - (P[band] @ axis)[:, None] * axis).mean(0) + base_t * axis
    r_base = np.mean([radius_at(0.90), radius_at(0.94)])
    return dict(axis_base_to_apex=-axis, base_centre=base_centre, r_base=r_base,
                length=float(t.max() - t.min()))


def fit_report(lv_coarse, m, axis_b2a, base_centre, label):
    """The same tests that exposed the defect."""
    pts = m.vertices[::9]
    inside = lv_coarse.contains(pts)
    q = trimesh.proximity.ProximityQuery(lv_coarse)
    d_out = np.abs(q.signed_distance(pts[~inside])) if (~inside).any() else np.array([0.0])
    s = (m.vertices - base_centre) @ (-axis_b2a)   # + = basal side of the base plane
    return {"label": label, "faces": int(len(m.faces)),
            "frac_inside_LV": round(float(inside.mean()), 3),
            "outside_median_mm": round(float(np.median(d_out)), 2),
            "outside_max_mm": round(float(d_out.max()), 2),
            "axial_span_mm": round(float(np.ptp(s)), 1),
            "protrudes_above_base_mm": round(float(max(0.0, s.max())), 1)}


def patched_generator(mv_centre_m, mv_r_m, av_centre_m, av_r_m, axis_b2a):
    """Load generate_valves.py with its three positioning constants replaced."""
    src = open(GEN, encoding="utf-8").read()
    def rep(pattern, new, count=1):
        nonlocal src
        src, n = re.subn(pattern, new, src, count=count)
        assert n == count, f"pattern not found: {pattern}"
    v3 = lambda a: "np.array([%.6f, %.6f, %.6f])" % tuple(a)
    rep(r"center = np\.array\(\[-0\.0222, 0\.0044, -0\.1489\]\)", "center = " + v3(mv_centre_m))
    rep(r"annulus_radius = 0\.0225", "annulus_radius = %.6f" % mv_r_m)
    rep(r"lv_axis = np\.array\(\[0\.0, 0\.0, -1\.0\]\)", "lv_axis = " + v3(axis_b2a))
    rep(r"center = np\.array\(\[-0\.0153, 0\.0192, -0\.1311\]\)", "center = " + v3(av_centre_m))
    rep(r"case_radius = 0\.0169", "case_radius = %.6f" % av_r_m)
    rep(r"mv_center = np\.array\(\[-0\.0222, 0\.0044, -0\.1489\]\)", "mv_center = " + v3(mv_centre_m))
    mod = types.ModuleType("gen_fitted"); mod.__file__ = GEN
    exec(compile(src, GEN, "exec"), mod.__dict__)
    return mod


def tris_to_mesh(tris):
    T = np.asarray(tris, dtype=float)               # (n, 3, 3) metres
    if T.ndim == 2:                                  # generator may store flat rows
        T = T.reshape(-1, 3, 3)
    v = T.reshape(-1, 3) * 1000.0                    # -> mm
    f = np.arange(len(v)).reshape(-1, 3)
    m = trimesh.Trimesh(v, f, process=True)
    m.update_faces(m.nondegenerate_faces()); m.update_faces(m.unique_faces())
    m.remove_unreferenced_vertices(); trimesh.repair.fix_normals(m)
    return m


def main():
    lv = trimesh.load(os.path.join(FRAME_A, "lv_surface.stl"), process=True)
    lvc = lv.simplify_quadric_decimation(face_count=8000)
    g = lv_geometry(lv)
    axis = g["axis_base_to_apex"]; base_c = g["base_centre"]; r_base = g["r_base"]
    print(f"LV: length {g['length']:.1f} mm, base centre {np.round(base_c,1)}, "
          f"basal radius {r_base:.1f} mm, axis(base->apex) {np.round(axis,3)}")

    # ---- design parameters, all derived ----
    mv_r = 0.90 * r_base
    mv_c = base_c + 3.0 * axis                       # 3 mm into the cavity
    av_r = mv_r * (0.0169 / 0.0225)                  # keep the generator's AV/MV size ratio
    # anterior direction: the generator's original AV-MV vector, projected into the base plane
    orig = np.array([-0.0153 + 0.0222, 0.0192 - 0.0044, -0.1311 + 0.1489])
    ant = orig - (orig @ axis) * axis
    ant = ant / np.linalg.norm(ant)
    av_c = mv_c + 0.75 * (mv_r + av_r) * ant - 2.0 * axis   # slightly basal of the MV plane
    print(f"MV: centre {np.round(mv_c,1)}  r {mv_r:.1f} mm   AV: centre {np.round(av_c,1)}  r {av_r:.1f} mm")

    # generator works in metres in the ORIGINAL patient frame; frame A = patient + OFFSET_A
    to_m = lambda p_frameA: (p_frameA - OFFSET_A) / 1000.0
    mod = patched_generator(to_m(mv_c), mv_r / 1000.0, to_m(av_c), av_r / 1000.0, axis)
    mv_new = tris_to_mesh(mod.generate_mitral_valve()); mv_new.apply_translation(OFFSET_A)
    av_new = tris_to_mesh(mod.generate_aortic_valve()); av_new.apply_translation(OFFSET_A)

    mv_old = trimesh.load(os.path.join(FRAME_A, "mitral_valve.stl"), process=True)
    av_old = trimesh.load(os.path.join(FRAME_A, "aortic_valve.stl"), process=True)

    rep = {"lv_geometry": {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in g.items()},
           "design": {"mv_centre_mm": mv_c.tolist(), "mv_annulus_r_mm": round(mv_r, 2),
                      "av_centre_mm": av_c.tolist(), "av_annulus_r_mm": round(av_r, 2),
                      "mv_av_centroid_distance_mm": round(float(np.linalg.norm(mv_c - av_c)), 1)},
           "mitral": {"before": fit_report(lvc, mv_old, axis, base_c, "original"),
                      "after": fit_report(lvc, mv_new, axis, base_c, "refit")},
           "aortic": {"before": fit_report(lvc, av_old, axis, base_c, "original"),
                      "after": fit_report(lvc, av_new, axis, base_c, "refit")}}
    for k in ("mitral", "aortic"):
        b, a = rep[k]["before"], rep[k]["after"]
        print(f"\n{k:>7}: {'':10} {'inside%':>8} {'out_med':>8} {'out_max':>8} {'span':>6} {'above_base':>11}")
        for r in (b, a):
            print(f"         {r['label']:<10} {100*r['frac_inside_LV']:>7.1f}% {r['outside_median_mm']:>8.1f}"
                  f" {r['outside_max_mm']:>8.1f} {r['axial_span_mm']:>6.1f} {r['protrudes_above_base_mm']:>11.1f}")

    # ---- accept only if the MITRAL fit clearly improves (the AV is expected to sit
    #      mostly outside the LV blood pool, so it is reported, not used as a gate) ----
    b, a = rep["mitral"]["before"], rep["mitral"]["after"]
    accept = (a["frac_inside_LV"] >= b["frac_inside_LV"] + 0.20
              and a["protrudes_above_base_mm"] <= 6.0
              and a["axial_span_mm"] < b["axial_span_mm"])
    rep["accepted"] = bool(accept)
    if accept:
        for m, n in ((mv_old, "mitral_valve"), (av_old, "aortic_valve")):
            m.export(os.path.join(FRAME_A, n + "_ORIGINAL_unfitted.stl"))
        mv_new.export(os.path.join(FRAME_A, "mitral_valve.stl"))
        av_new.export(os.path.join(FRAME_A, "aortic_valve.stl"))
        print("\nACCEPTED -- refit valves written to frame_A_patient/; originals kept as *_ORIGINAL_unfitted.stl")
    else:
        print("\nNOT ACCEPTED -- originals left in place; see valve_refit.json for why")
    json.dump(rep, open(os.path.join(HERE, "valve_refit.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
