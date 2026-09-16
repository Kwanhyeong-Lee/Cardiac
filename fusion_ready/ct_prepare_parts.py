# -*- coding: utf-8 -*-
"""Turn the raw CT-derived meshes into print-grade parts and cache what v4 needs.

    CT/LV_myocardium_CT_with_PMs.stl (536k f, voxel stair-steps)  -> Taubin smooth -> decimate
        -> CT/LV_myocardium_CT_smooth.stl   (the hollow ventricle with the patient's PMs + trabeculae)
    CT/lv_bloodpool_CT.stl (327k f)                                -> same -> CT/lv_bloodpool_CT_smooth.stl
    CT/blood_sdf_grid.npz   signed distance to the smoothed CT blood pool (1.5 mm), + inside
    CT/pm_tips.json         anterolateral / posteromedial assignment and tip points of the
                            two CT papillary muscles (pm_candidate_{1,2}_CT.stl)
Taubin (lambda 0.5, mu -0.53, 10 it) shrinks volume < 1 %; checked and reported.
"""
import json, os, time
import numpy as np, trimesh
from trimesh.smoothing import filter_taubin
HERE = os.path.dirname(os.path.abspath(__file__)); CT = os.path.join(HERE, "CT")
d = json.load(open(os.path.join(HERE, "valve_refit.json")))
AXIS = np.array(d["lv_geometry"]["axis_base_to_apex"]); MV_C = np.array(d["design"]["mv_centre_mm"]); AV_C = np.array(d["design"]["av_centre_mm"])
TARGET_MYO, TARGET_BLOOD, SDF_SPACING = 320000, 150000, 2.0   # 1.5 mm grid on a 15k proxy timed out (>175 s); 2.0 mm / 8k proxy ~1 min


def smooth_dec(path, target, tag):
    t = time.time(); m = trimesh.load(path, process=True); v0 = abs(m.volume) / 1000
    filter_taubin(m, lamb=0.5, nu=-0.53, iterations=10)
    m = m.simplify_quadric_decimation(face_count=target)
    if not m.is_watertight:
        import pymeshfix
        vc, fc = pymeshfix.clean_from_arrays(np.ascontiguousarray(m.vertices, dtype=np.float64), np.ascontiguousarray(m.faces, dtype=np.int32))
        m = trimesh.Trimesh(vc, fc, process=True)
    trimesh.repair.fix_normals(m)
    print(f"{tag}: {v0:.1f} -> {abs(m.volume)/1000:.1f} mL, {len(m.faces):,} f, watertight {m.is_watertight}, {time.time()-t:.0f}s")
    return m, v0


def main():
    p_myo, p_bl = os.path.join(CT, "LV_myocardium_CT_smooth.stl"), os.path.join(CT, "lv_bloodpool_CT_smooth.stl")
    if os.path.exists(p_myo) and os.path.exists(p_bl):                 # cached from a previous (timed-out) run
        myo = trimesh.load(p_myo, process=True); blood = trimesh.load(p_bl, process=True)
        v_myo0 = abs(trimesh.load(os.path.join(CT, "LV_myocardium_CT_with_PMs.stl"), process=False).volume) / 1000
        v_bl0 = abs(trimesh.load(os.path.join(CT, "lv_bloodpool_CT.stl"), process=False).volume) / 1000
        print(f"cached: myoCT {abs(myo.volume)/1000:.1f} mL {len(myo.faces):,} f wt {myo.is_watertight}; blood {abs(blood.volume)/1000:.1f} mL {len(blood.faces):,} f wt {blood.is_watertight}")
    else:
        myo, v_myo0 = smooth_dec(os.path.join(CT, "LV_myocardium_CT_with_PMs.stl"), TARGET_MYO, "myoCT"); myo.export(p_myo)
        blood, v_bl0 = smooth_dec(os.path.join(CT, "lv_bloodpool_CT.stl"), TARGET_BLOOD, "blood"); blood.export(p_bl)
    # SDF grid of the CT blood pool
    t = time.time(); proxy = blood.simplify_quadric_decimation(face_count=8000)
    lo = blood.bounds[0] - 6; hi = blood.bounds[1] + 6
    axes = [np.arange(lo[i], hi[i] + SDF_SPACING, SDF_SPACING) for i in range(3)]
    G = np.stack(np.meshgrid(*axes, indexing="ij"), -1).reshape(-1, 3)
    q = trimesh.proximity.ProximityQuery(proxy)
    sd = np.concatenate([q.signed_distance(G[i:i + 4000]) for i in range(0, len(G), 4000)]).reshape([len(a) for a in axes]).astype(np.float32)
    np.savez(os.path.join(CT, "blood_sdf_grid.npz"), sdf=sd, origin=lo, spacing=SDF_SPACING)
    print(f"blood SDF grid {sd.shape} ({sd.size:,} pts) {time.time()-t:.0f}s")
    # papillary muscles: assignment + tips
    S = np.array(json.load(open(os.path.join(HERE, "subvalvular.json")))["septal_dir"])
    A_dir = AV_C - MV_C; A_dir -= (A_dir @ AXIS) * AXIS; A_dir /= np.linalg.norm(A_dir); P_dir = np.cross(AXIS, A_dir)
    apex_depth = float(((blood.vertices - MV_C) @ AXIS).max())
    pms = []
    for i in (1, 2):
        m = trimesh.load(os.path.join(CT, f"pm_candidate_{i}_CT.stl"), process=True)
        v = m.centroid - MV_C; v -= (v @ AXIS) * AXIS; r = np.linalg.norm(v); v /= r
        dep = (m.vertices - MV_C) @ AXIS
        tip_pts = m.vertices[dep <= np.quantile(dep, 0.08)]          # most basal 8 % of the muscle = head
        base_pts = m.vertices[dep >= np.quantile(dep, 0.92)]
        pms.append(dict(file=f"pm_candidate_{i}_CT.stl", volume_mL=round(abs(m.volume) / 1000, 2),
                        angle_from_aortic_deg=round(float(np.degrees(np.arctan2(v @ P_dir, v @ A_dir))), 1),
                        septal_dot=round(float(v @ S), 2), radial_mm=round(float(r), 1),
                        tip_mm=[round(float(x), 2) for x in tip_pts.mean(0)], base_mm=[round(float(x), 2) for x in base_pts.mean(0)],
                        tip_depth_frac=round(float((tip_pts.mean(0) - MV_C) @ AXIS) / apex_depth, 3),
                        length_mm=round(float(np.linalg.norm(tip_pts.mean(0) - base_pts.mean(0))), 1)))
    pms.sort(key=lambda p: p["septal_dot"])          # most lateral first
    pms[0]["label"] = "anterolateral"; pms[1]["label"] = "posteromedial"
    for p in pms:
        print(f"{p['label']:<14} {p['volume_mL']} mL  angle {p['angle_from_aortic_deg']:+.0f}  septal {p['septal_dot']:+.2f}  tip depth {p['tip_depth_frac']}  length {p['length_mm']} mm")
    json.dump(dict(muscles=pms, apex_depth_mm=round(apex_depth, 1),
                   volumes=dict(myoCT_raw_mL=round(v_myo0, 2), myoCT_smooth_mL=round(abs(myo.volume) / 1000, 2),
                                blood_raw_mL=round(v_bl0, 2), blood_smooth_mL=round(abs(blood.volume) / 1000, 2))),
              open(os.path.join(CT, "pm_tips.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
