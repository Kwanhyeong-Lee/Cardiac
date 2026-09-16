# -*- coding: utf-8 -*-
"""Hollow ventricle v2 = myocardium U AV-plane plate U solidified mitral U solidified aortic.

manifold3d union of four watertight solids (all frame A, mm):
    BLENDER_OUT/LV_myocardium_frameA.stl   (Claude Code, 361,772 f, 125.6 mL)
    frame_A_patient/av_plane_plate.stl     (make_av_plate.py)
    BLENDER_OUT/mitral_valve.stl           (Blender: solidify 1.2 mm + voxel remesh 0.25)
    BLENDER_OUT/aortic_valve.stl
Checks (all on the PARTS, never contains() on the ~800k-face union -- OOM in a 3 GB sandbox):
    single watertight component; cavity blockage = fraction of blood-pool interior points
    (from lv_sdf_grid.npz) inside plate/valves; mitral and aortic axis probes open.
Output: BLENDER_OUT/hollow_ventricle_v2_fixed_valves.stl, hollow_v2_check.json
"""
import json, os, time, warnings
import numpy as np, trimesh
from scipy.ndimage import map_coordinates
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__)); FA = os.path.join(HERE, "frame_A_patient"); BO = os.path.join(HERE, "BLENDER_OUT")
d = json.load(open(os.path.join(HERE, "valve_refit.json")))
AXIS = np.array(d["lv_geometry"]["axis_base_to_apex"]); MV_C = np.array(d["design"]["mv_centre_mm"]); AV_C = np.array(d["design"]["av_centre_mm"])


def main():
    t0 = time.time()
    names = [("myocardium", os.path.join(BO, "LV_myocardium_frameA.stl")), ("plate", os.path.join(FA, "av_plane_plate.stl")),
             ("mitral", os.path.join(BO, "mitral_valve.stl")), ("aortic", os.path.join(BO, "aortic_valve.stl"))]
    parts = {}
    for n, p in names:
        m = trimesh.load(p, process=True)
        if not m.is_volume: trimesh.repair.fix_normals(m)
        assert m.is_volume, f"{n} is not a volume"
        parts[n] = m; print(f"  {n:<11} {len(m.faces):>8,} f  {abs(m.volume)/1000:7.2f} mL")
    u = trimesh.boolean.union(list(parts.values()), engine="manifold")
    comps = u.split(only_watertight=False)
    print(f"union {len(u.faces):,} f  watertight {u.is_watertight}  comps {len(comps)}  {abs(u.volume)/1000:.2f} mL "
          f"(sum of parts {sum(abs(m.volume) for m in parts.values())/1000:.2f})  {time.time()-t0:.0f}s")
    u.export(os.path.join(BO, "hollow_ventricle_v2_fixed_valves.stl"))

    g = np.load(os.path.join(HERE, "lv_sdf_grid.npz")); SG, ORG, H = g["sdf"], g["origin"], float(g["spacing"])
    sdf = lambda P: map_coordinates(SG, ((np.atleast_2d(P) - ORG) / H).T, order=1, mode="nearest")
    bp = trimesh.load(os.path.join(HERE, "PRINT", "frame_A_patient", "lv_surface.stl"), process=True)
    rng = np.random.default_rng(0); cand = rng.uniform(bp.bounds[0], bp.bounds[1], size=(60000, 3))
    pts = cand[sdf(cand) > 1.0][:3000]
    small = {n: parts[n] for n in ("plate", "mitral", "aortic")}
    for n in ("mitral", "aortic"):                       # decimate for the containment test only
        small[n] = small[n].simplify_quadric_decimation(face_count=40000)
    blocked = float(np.any([m.contains(pts) for m in small.values()], axis=0).mean())
    probe = lambda c: bool(np.any([m.contains(np.array([c + t * AXIS for t in (-3, 0, 3)])).any() for m in small.values()]))
    rep = dict(parts={n: dict(faces=int(len(m.faces)), volume_mL=round(abs(m.volume) / 1000, 2)) for n, m in parts.items()},
               union=dict(faces=int(len(u.faces)), watertight=bool(u.is_watertight), components=len(comps), volume_mL=round(abs(u.volume) / 1000, 2)),
               cavity_blocked_frac=round(blocked, 4), mitral_axis_blocked=probe(MV_C), aortic_axis_blocked=probe(AV_C))
    rep["verdict"] = "OK" if (u.is_watertight and len(comps) == 1 and blocked < 0.05 and not rep["mitral_axis_blocked"] and not rep["aortic_axis_blocked"]) else "CHECK"
    print(f"cavity blocked {100*blocked:.1f}%  mitral axis blocked {rep['mitral_axis_blocked']}  aortic axis blocked {rep['aortic_axis_blocked']}  -> {rep['verdict']}")
    json.dump(rep, open(os.path.join(BO, "hollow_v2_check.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
