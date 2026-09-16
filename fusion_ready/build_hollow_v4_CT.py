# -*- coding: utf-8 -*-
"""Hollow ventricle v4 -- the patient's own interior.

    CT/LV_myocardium_CT_smooth.stl   myocardium re-segmented from the CT at 0.49 mm: the label-205
                                     wall PLUS the 17.8 mL of muscle the label-500 cavity had
                                     swallowed -- i.e. the patient's papillary muscles and
                                     trabeculae are part of this mesh (ct_refine_lv.py)
    U  frame_A_patient/av_plane_plate.stl        (make_av_plate.py)
    U  BLENDER_OUT/mitral_valve.stl, aortic_valve.stl   (parametric, solidified)
    U  chordae: N_CH tubes per muscle from the CT muscle tips (CT/pm_tips.json) to free-edge
       points of both leaflets within +-CH_SPAN deg; each verified inside the CT blood pool

What is patient-specific in v4: wall, cavity surface, papillary muscles, trabeculae.
What is parametric: valve leaflets, the AV-plane plate, the chordae (routes only; number and
radius are design constants).

Outputs: BLENDER_OUT/hollow_ventricle_v4_CT.stl, BLENDER_OUT/hollow_v4_check.json,
         frame_A_patient/chordae_v4_CT.stl
"""
import json, os, time, warnings
import numpy as np, trimesh
from scipy.ndimage import map_coordinates
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__)); FA = os.path.join(HERE, "frame_A_patient"); BO = os.path.join(HERE, "BLENDER_OUT"); CT = os.path.join(HERE, "CT")
d = json.load(open(os.path.join(HERE, "valve_refit.json")))
AXIS = np.array(d["lv_geometry"]["axis_base_to_apex"]); MV_C = np.array(d["design"]["mv_centre_mm"]); AV_C = np.array(d["design"]["av_centre_mm"])
N_CH, CH_R, CH_SPAN, CH_OVER, FREE_EDGE_MIN = 5, 1.0, 70.0, 1.2, 8.0
unit = lambda v: v / (np.linalg.norm(v) + 1e-12)


def tube(p, q, r):
    v = q - p; L = np.linalg.norm(v); c = trimesh.creation.cylinder(radius=r, height=L, sections=24)
    T = trimesh.geometry.align_vectors([0, 0, 1], v / L); T[:3, 3] = (p + q) / 2; c.apply_transform(T); return c


def main():
    t0 = time.time()
    g = np.load(os.path.join(CT, "blood_sdf_grid.npz")); SG, ORG, H = g["sdf"], g["origin"], float(g["spacing"])
    sdf = lambda P: map_coordinates(SG, ((np.atleast_2d(P) - ORG) / H).T, order=1, mode="nearest")
    parts = {n: trimesh.load(p, process=True) for n, p in [("myoCT", os.path.join(CT, "LV_myocardium_CT_smooth.stl")), ("plate", os.path.join(FA, "av_plane_plate.stl")),
                                                          ("mitral", os.path.join(BO, "mitral_valve.stl")), ("aortic", os.path.join(BO, "aortic_valve.stl"))]}
    for n, m in parts.items():
        if not m.is_volume: trimesh.repair.fix_normals(m)
        assert m.is_volume, n
    mv_sheet = trimesh.load(os.path.join(FA, "mitral_valve.stl"), process=True)
    A_dir = unit(AV_C - MV_C - ((AV_C - MV_C) @ AXIS) * AXIS); P_dir = unit(np.cross(AXIS, A_dir))
    e = mv_sheet.edges_sorted; u_, c_ = np.unique(e, axis=0, return_counts=True); B = mv_sheet.vertices[np.unique(u_[c_ == 1])]
    free = B[(B - MV_C) @ AXIS > FREE_EDGE_MIN]; free_ang = np.degrees(np.arctan2((free - MV_C) @ P_dir, (free - MV_C) @ A_dir))

    pm = json.load(open(os.path.join(CT, "pm_tips.json")))["muscles"]
    chordae, rows = [], []
    for m in pm:
        tip, base = np.array(m["tip_mm"]), np.array(m["base_mm"]); ax = unit(base - tip)
        a = m["angle_from_aortic_deg"]
        da = np.abs(((free_ang - a + 180) % 360) - 180); cand = free[da <= CH_SPAN]; cand_ang = free_ang[da <= CH_SPAN]
        order = np.argsort(cand_ang); cand = cand[order]
        pick = cand[np.linspace(0, len(cand) - 1, N_CH).round().astype(int)] if len(cand) >= N_CH else cand
        kept = 0
        for k, tgt in enumerate(pick):
            side = unit(np.cross(ax, tgt - tip))
            start = tip + 3.0 * ax + 2.0 * side * (k - (len(pick) - 1) / 2) / max(1, len(pick) - 1)   # 3 mm inside the muscle head
            end = tgt + CH_OVER * unit(tgt - start)
            samp = start + np.outer(np.linspace(0, 1, 40), end - start); L = np.linalg.norm(end - start)
            inside = sdf(samp) > 0.3; n_chk = int(40 * (1 - 2.5 / L)); n_skip = int(40 * (4.0 / L))   # first 4 mm are in the muscle
            if inside[n_skip:n_chk].all():
                chordae.append(tube(start, end, CH_R)); kept += 1
                rows.append(dict(muscle=m["label"], length_mm=round(float(L), 1), target=[round(float(x), 1) for x in tgt]))
        print(f"{m['label']:<14} tip {np.round(tip,1)}  free-edge candidates {len(cand)}  chordae {kept}/{len(pick)}")
    ch = trimesh.util.concatenate(chordae); ch.export(os.path.join(FA, "chordae_v4_CT.stl"))

    v4 = trimesh.boolean.union(list(parts.values()) + chordae, engine="manifold")
    comps = v4.split(only_watertight=False)
    print(f"union {len(v4.faces):,} f  watertight {v4.is_watertight}  comps {len(comps)}  {abs(v4.volume)/1000:.2f} mL  {time.time()-t0:.0f}s")
    v4.export(os.path.join(BO, "hollow_ventricle_v4_CT.stl"))

    # checks on the small parts (never contains() on the union)
    rng = np.random.default_rng(0); cand = rng.uniform(parts["myoCT"].bounds[0], parts["myoCT"].bounds[1], size=(60000, 3)); pts = cand[sdf(cand) > 1.0][:3000]
    small = [parts["plate"], parts["mitral"].simplify_quadric_decimation(face_count=40000), parts["aortic"].simplify_quadric_decimation(face_count=40000)] + chordae
    blocked = float(np.any([m.contains(pts) for m in small], axis=0).mean())
    probe = lambda c: bool(np.any([m.contains(np.array([c + t * AXIS for t in (-3, 0, 3)])).any() for m in small]))
    rep = dict(parts={n: dict(faces=int(len(m.faces)), volume_mL=round(abs(m.volume) / 1000, 2)) for n, m in parts.items()},
               chordae=rows, union=dict(faces=int(len(v4.faces)), watertight=bool(v4.is_watertight), components=len(comps), volume_mL=round(abs(v4.volume) / 1000, 2)),
               cavity_blocked_by_added_parts_frac=round(blocked, 4), mitral_axis_blocked=probe(MV_C), aortic_axis_blocked=probe(AV_C),
               patient_specific=["wall", "endocardial surface incl. trabeculae", "papillary muscles"], parametric=["leaflets", "AV-plane plate", "chordae routes"])
    rep["verdict"] = "OK" if (v4.is_watertight and len(comps) == 1 and blocked < 0.05 and not rep["mitral_axis_blocked"] and not rep["aortic_axis_blocked"]) else "CHECK"
    print(f"cavity blocked by plate/valves/chordae {100*blocked:.1f}%  mitral axis {rep['mitral_axis_blocked']}  aortic axis {rep['aortic_axis_blocked']}  -> {rep['verdict']}")
    json.dump(rep, open(os.path.join(BO, "hollow_v4_check.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
