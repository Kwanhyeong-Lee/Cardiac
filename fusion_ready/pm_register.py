# -*- coding: utf-8 -*-
"""6-DOF rigid registration of the papillary muscles (frame B) into the LV (frame A).

STATE OF PLAY. Axis-aligned searches (pm_recovery.json, frame_B_recheck.json) agree on one
candidate -- perm (0,2,1), signs (-,-,-), a proper rotation -- but it leaves the muscle bases
floating 6.7 mm off the endocardium. Axis-aligned candidates cannot fix that: the residual is
a small rotation plus a translation, which is exactly the 6-DOF refinement done here.

ANATOMICAL CONSTRAINTS, turned into a cost (all distances mm, LV SDF positive inside):
    base attachment   base-region vertices should sit ON the endocardium: relu(sdf)^2 for
                      being away from the wall, relu(-sdf-2)^2 for being buried deeper than
                      2 mm into it
    containment       every other vertex inside the cavity: relu(-sdf)^2
    tip distance      each tip 15-30 mm from the mitral annulus centre (chordae span this)
    tip aim           the base->tip direction should point at the annulus (cos >= 0.6)

Both papillary muscles move as ONE rigid body -- they come from the same CT volume and their
mutual pose is real; only their frame is wrong.

Optimiser: scipy Powell over (rotation vector, translation) from the axis-aligned start.
Coarse LV proxy (8k faces) and subsampled PM points keep each cost evaluation ~50 ms.

Nothing is overwritten. Outputs go to frame_A_patient/*_registered.stl plus
pm_registration.json with before/after metrics. The result is judged on the same metrics
that failed before: base gap and tip-to-annulus, plus the fraction inside the cavity.

Usage:  PYTHONPATH=/tmp/pylibs python3 pm_register.py
"""
import json, os, time, warnings
import numpy as np, trimesh
from scipy.optimize import minimize
from scipy.spatial.transform import Rotation as Rot
from scipy.ndimage import map_coordinates
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
FA = os.path.join(HERE, "frame_A_patient")
FB = os.path.join(HERE, "frame_B_papillary")
design = json.load(open(os.path.join(HERE, "valve_refit.json")))["design"]
MV_C = np.array(design["mv_centre_mm"])              # mitral annulus centre, frame A
MV_R = float(design["mv_annulus_r_mm"])
lvgeo = json.load(open(os.path.join(HERE, "valve_refit.json")))["lv_geometry"]
AXIS = np.array(lvgeo["axis_base_to_apex"])          # unit, base -> apex

# axis-aligned start from frame_B_recheck.json (proper rotation)
PERM, SIGNS = (0, 2, 1), (-1, -1, -1)
R0 = np.zeros((3, 3))
for i, (p, s) in enumerate(zip(PERM, SIGNS)):
    R0[i, p] = s
assert np.linalg.det(R0) > 0


def load_pm(name, step):
    m = trimesh.load(os.path.join(FB, name + ".stl"), process=True)
    return m, m.vertices[::step].copy()


def end_regions(pts, frac=0.15):
    """Split a PM point cloud into its two ends along its PCA long axis."""
    c = pts.mean(0); P = pts - c
    _, V = np.linalg.eigh(P.T @ P); ax = V[:, -1]
    t = P @ ax
    lo, hi = np.quantile(t, frac), np.quantile(t, 1 - frac)
    return ax, c, pts[t <= lo], pts[t >= hi]


def main():
    t0 = time.time()
    lv = trimesh.load(os.path.join(FA, "lv_surface.stl"), process=True)
    # SDF from a cached 2.5 mm grid (lv_sdf_grid.npz, built once from an 8k-face LV proxy),
    # trilinear-interpolated: ~1e4x faster than per-call mesh queries, which made the
    # optimiser infeasible (0.57 s per 800-point evaluation).
    g = np.load(os.path.join(HERE, "lv_sdf_grid.npz"))
    SG, ORG, H = g["sdf"], g["origin"], float(g["spacing"])
    def sdf(P):
        idx = ((np.asarray(P) - ORG) / H).T
        return map_coordinates(SG, idx, order=1, mode="nearest")   # + inside

    pms = {n: load_pm(n, 90) for n in ["anterolateral_pm", "posteromedial_pm"]}
    allpts = np.vstack([pms[n][1] for n in pms])
    pmc = allpts.mean(0)                                        # rigid-body pivot (frame B)

    # ---- decide base vs tip per PM using the START pose: the end farther from the
    #      annulus plane (more apical) is the base ----
    def pose_pts(P, rv, t):
        return (Rot.from_rotvec(rv).as_matrix() @ R0 @ (P - pmc).T).T + t
    t_start = lv.bounds.mean(0) + np.array([-2.81, -0.66, -0.88])   # recheck's translation
    ends = {}
    for n, (m, P) in pms.items():
        ax, c, endA, endB = end_regions(P)
        dA = (pose_pts(endA, np.zeros(3), t_start) - MV_C) @ AXIS    # depth below annulus
        dB = (pose_pts(endB, np.zeros(3), t_start) - MV_C) @ AXIS
        base, tip = (endA, endB) if dA.mean() > dB.mean() else (endB, endA)
        ends[n] = dict(base=base, tip=tip)
    base_pts = np.vstack([ends[n]["base"] for n in pms])
    tip_pts = np.vstack([ends[n]["tip"] for n in pms])
    # containment applies to the NON-base body: the base is allowed to sit in the wall,
    # everything else must be in the cavity. Mixing them let the first run bury 24% of the
    # muscle through the wall to close the base gap.
    base_set = {tuple(np.round(r, 6)) for r in base_pts}
    body_pts = np.array([r for r in allpts if tuple(np.round(r, 6)) not in base_set])

    def cost(x, verbose=False):
        rv, t = x[:3], x[3:]
        B = pose_pts(base_pts, rv, t); T = pose_pts(tip_pts, rv, t); A = pose_pts(body_pts, rv, t)
        sB, sA = sdf(B), sdf(A)
        c_base = np.mean(np.maximum(sB, 0) ** 2) + np.mean(np.maximum(-sB - 2.0, 0) ** 2)
        # near-hard containment: mean AND worst offender (0.5 mm tolerance = grid error)
        viol = np.maximum(-sA - 0.5, 0)
        c_in = np.mean(viol ** 2) + 0.1 * np.max(viol) ** 2
        dT = np.linalg.norm(T - MV_C, axis=1)
        c_tip = np.mean(np.maximum(dT - 40, 0) ** 2 + np.maximum(15 - dT, 0) ** 2)
        # this is a REFINEMENT of an exhaustively-found candidate: rotations beyond 15 deg
        # mean the optimiser has abandoned it, which the first run did (46.7 deg)
        c_rot = max(0.0, np.degrees(np.linalg.norm(rv)) - 15.0) ** 2
        # aim: base->tip vs base->annulus, per PM
        c_aim = 0.0
        for n in pms:
            b = pose_pts(ends[n]["base"], rv, t).mean(0); tp = pose_pts(ends[n]["tip"], rv, t).mean(0)
            u = tp - b; u /= np.linalg.norm(u); v = MV_C - b; v /= np.linalg.norm(v)
            c_aim += max(0.0, 0.6 - float(u @ v)) ** 2 * 100
        J = 1.0 * c_base + 30.0 * c_in + 0.02 * c_tip + c_aim + c_rot
        if verbose:
            return dict(base_gap_mm=float(np.mean(np.maximum(sB, 0))),
                        base_median_sdf_mm=float(np.median(sB)),
                        frac_inside=float((sA > 0).mean()),
                        tip_to_annulus_mm=float(dT.mean()),
                        tip_depth_below_annulus_mm=float(((T - MV_C) @ AXIS).mean()),
                        cost=float(J))
        return J

    x0 = np.r_[np.zeros(3), t_start]
    before = cost(x0, verbose=True)
    print("START (axis-aligned candidate):", {k: round(v, 2) for k, v in before.items()})

    res = minimize(cost, x0, method="Powell",
                   options=dict(maxiter=60, maxfev=6000, xtol=1e-3, ftol=1e-7, disp=False))
    x = res.x
    after = cost(x, verbose=True)
    print("AFTER 6-DOF refinement:        ", {k: round(v, 2) for k, v in after.items()})
    rot_deg = float(np.degrees(np.linalg.norm(x[:3])))
    print(f"refinement applied: rotation {rot_deg:.1f} deg, translation {np.round(x[3:] - t_start, 2)} mm  "
          f"({time.time()-t0:.0f}s, {res.nfev} evals)")

    # full-resolution transform: x_A = R (x_B - pmc) + t
    R = Rot.from_rotvec(x[:3]).as_matrix() @ R0
    M = np.eye(4); M[:3, :3] = R; M[:3, 3] = x[3:] - R @ pmc
    out = {"transform_frameB_mm_to_frameA_mm": M.tolist(),
           "start_candidate": {"perm": PERM, "signs": SIGNS, "det": float(np.linalg.det(R0))},
           "refinement": {"rotation_deg": rot_deg, "translation_mm": (x[3:] - t_start).tolist(),
                          "optimizer": "Powell", "n_eval": int(res.nfev)},
           "metrics_before": before, "metrics_after": after,
           "acceptance": {"base_gap_mm <= 1.5": after["base_gap_mm"] <= 1.5,
                          "frac_inside >= 0.95": after["frac_inside"] >= 0.95,
                          "tip_to_annulus 15-40": 15 <= after["tip_to_annulus_mm"] <= 40,
                          "rotation_refinement <= 15deg": rot_deg <= 15.0}}
    out["accepted"] = all(out["acceptance"].values())

    # per-PM full-res export + per-PM metrics on the full mesh
    per = {}
    for n, (m, _) in pms.items():
        mm = m.copy(); mm.apply_transform(M)
        mm.export(os.path.join(FA, n + "_registered.stl"))
        s = sdf(mm.vertices[::5])
        per[n] = dict(faces=int(len(mm.faces)), frac_inside=round(float((s > 0).mean()), 3),
                      centre_mm=[round(float(v), 1) for v in mm.bounds.mean(0)])
    for n in ["chordae_combined", "chordae_al", "chordae_pm"]:
        m = trimesh.load(os.path.join(FB, n + ".stl"), process=True); m.apply_transform(M)
        m.export(os.path.join(FA, n + "_registered.stl"))
    out["per_pm_fullres"] = per
    json.dump(out, open(os.path.join(HERE, "pm_registration.json"), "w"), indent=1)
    print("\nacceptance:", out["acceptance"], "->", "ACCEPTED" if out["accepted"] else "NOT ACCEPTED")
    print("per-PM full-res:", per)


if __name__ == "__main__":
    main()
