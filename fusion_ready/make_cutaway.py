# -*- coding: utf-8 -*-
"""Teaching cut-away: split a hollow-ventricle solid into two halves along the plane that
contains the LV long axis AND the mitral->aortic line, so each half shows half of both
orifices, the leaflets, the wall thickness and (v3) one papillary muscle with its chordae.

    usage: PYTHONPATH=/tmp/pylibs python3 make_cutaway.py [v2|v3]
Outputs: BLENDER_OUT/hollow_<v>_cutaway_A.stl / _B.stl (+ _PRINT_ORIENTED: cut face down),
         BLENDER_OUT/cutaway_<v>.json
"""
import json, os, sys, time, warnings
import numpy as np, trimesh
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__)); BO = os.path.join(HERE, "BLENDER_OUT")
d = json.load(open(os.path.join(HERE, "valve_refit.json")))
AXIS = np.array(d["lv_geometry"]["axis_base_to_apex"]); MV_C = np.array(d["design"]["mv_centre_mm"]); AV_C = np.array(d["design"]["av_centre_mm"])
FILES = {"v2": "hollow_ventricle_v2_fixed_valves.stl", "v3": "hollow_ventricle_v3_IDEALISED_subvalvular.stl", "v4": "hollow_ventricle_v4_CT.stl", "v5": "hollow_ventricle_v5_CT_hires.stl"}


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "v3"; t0 = time.time()
    solid = trimesh.load(os.path.join(BO, FILES[which]), process=True)
    assert solid.is_volume
    A_dir = AV_C - MV_C; A_dir -= (A_dir @ AXIS) * AXIS; A_dir /= np.linalg.norm(A_dir)
    n = np.cross(AXIS, A_dir)                                   # cut-plane normal
    ext = float(np.linalg.norm(solid.extents)) * 2
    rep = dict(source=FILES[which], plane_point=MV_C.tolist(), plane_normal=n.tolist(), halves={})
    for tag, sgn in (("A", 1.0), ("B", -1.0)):
        # half-space as a big box whose -z face lies on the cut plane
        T = trimesh.geometry.align_vectors([0, 0, 1], sgn * n); T[:3, 3] = MV_C + sgn * n * ext / 2
        box = trimesh.creation.box(extents=[ext, ext, ext], transform=T)
        half = trimesh.boolean.intersection([solid, box], engine="manifold")
        comps = half.split(only_watertight=False)
        # a cut through a trabecula can leave a crumb (< 0.01 mL) with no attachment: drop it
        if len(comps) > 1:
            keep = [c for c in comps if abs(c.volume) / 1000 >= 0.01]
            dropped = len(comps) - len(keep)
            if dropped: print(f"   dropped {dropped} loose crumb(s) < 0.01 mL"); half = trimesh.util.concatenate(keep); comps = keep
        vols = sorted([abs(c.volume) / 1000 for c in comps], reverse=True)
        half.export(os.path.join(BO, f"hollow_{which}_cutaway_{tag}.stl"))
        # print orientation: cut face down (flat on the bed), i.e. rotate so -sgn*n -> -z
        P = half.copy(); R = trimesh.geometry.align_vectors(-sgn * n, [0, 0, -1]); P.apply_transform(R); P.apply_translation(-P.bounds[0])
        P.export(os.path.join(BO, f"hollow_{which}_cutaway_{tag}_PRINT_ORIENTED.stl"))
        rep["halves"][tag] = dict(faces=int(len(half.faces)), watertight=bool(half.is_watertight), components=len(comps),
                                  component_volumes_mL=[round(v, 3) for v in vols[:6]], volume_mL=round(abs(half.volume) / 1000, 2),
                                  extent_mm=[round(float(x), 1) for x in half.extents])
        print(f"{tag}: {len(half.faces):,} f  wt {half.is_watertight}  comps {len(comps)} {[round(v,2) for v in vols[:4]]} mL  "
              f"vol {abs(half.volume)/1000:.2f}  extent {np.round(half.extents,1)}  {time.time()-t0:.0f}s")
    rep["sum_check_mL"] = round(sum(h["volume_mL"] for h in rep["halves"].values()), 2); rep["whole_mL"] = round(abs(solid.volume) / 1000, 2)
    json.dump(rep, open(os.path.join(BO, f"cutaway_{which}.json"), "w"), indent=1)
    print("halves sum", rep["sum_check_mL"], "whole", rep["whole_mL"])


if __name__ == "__main__":
    main()
