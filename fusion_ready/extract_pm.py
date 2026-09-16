# -*- coding: utf-8 -*-
"""Extract the PATIENT'S OWN papillary muscles from the frame-A myocardium.

WHY. Frame B's papillary muscles come from another heart and cannot be rigidly fitted into
this LV (pm_registration.json: every anatomical gate violated at once). But if the
segmentation put the papillary muscles in the MYOCARDIUM label, they are already in
BLENDER_OUT/LV_myocardium_frameA.stl as muscle that protrudes from the wall into the cavity,
and the blood pool wraps around them. This script isolates that protruding muscle.

METHOD (frame A, mm)
    1. voxelise the blood pool (PITCH), fill
    2. morphological CLOSING with a ball of radius R_CLOSE: fills every concavity of the
       cavity narrower than 2*R_CLOSE -- the notches the papillary muscles sit in -- while
       leaving the wide basal/outflow region alone. The result is the "smooth endocardium"
       the cavity would have without the muscles.
    3. marching cubes -> closed-cavity mesh; PM candidates = myocardium INTERSECT closed
       cavity (manifold3d), split into components
    4. keep components that are big enough (V_MIN), thick enough (2V/A >= T_MIN, rejects
       the film that appears wherever the endocardium is slightly concave) and at
       ventricular depth (DEPTH range of the base->apex span)
    5. anatomical labelling: the two muscles lie beneath the mitral commissures, i.e. at
       ~ +-90 deg from the mitral->aortic direction in the short axis; the one on the SEPTAL
       side (toward the RV centroid, brought into frame A with frame_transform.json) is the
       posteromedial muscle, the other the anterolateral.

If nothing survives step 4 the segmentation lumped the muscles into the cavity label and
there is no patient papillary muscle to extract. That is reported, not papered over.

Outputs: frame_A_patient/pm_{anterolateral,posteromedial}_patient.stl, pm_extract.json,
         pm_extract_sections.png
"""
import json, os, warnings, time
import numpy as np, trimesh
from scipy import ndimage
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FA = os.path.join(HERE, "frame_A_patient")
d = json.load(open(os.path.join(HERE, "valve_refit.json")))
AXIS = np.array(d["lv_geometry"]["axis_base_to_apex"])
MV_C = np.array(d["design"]["mv_centre_mm"]); AV_C = np.array(d["design"]["av_centre_mm"])

PITCH = 1.0          # mm voxel
R_CLOSE = 8.0        # mm closing radius: fills notches < 16 mm wide (papillary bases are 8-15 mm)
V_MIN = 0.30         # mL   smallest component kept
T_MIN = 2.0          # mm   2V/A "mean thickness" -- films are ~1 voxel, muscles are >4
DEPTH = (0.20, 0.90) # fraction of base->apex span where a papillary body may sit


def ball(r_vox):
    n = int(np.ceil(r_vox)); g = np.mgrid[-n:n + 1, -n:n + 1, -n:n + 1]
    return (g ** 2).sum(0) <= r_vox ** 2


def main():
    t0 = time.time()
    myo = trimesh.load(os.path.join(HERE, "BLENDER_OUT", "LV_myocardium_frameA.stl"), process=True)
    bp = trimesh.load(os.path.join(HERE, "PRINT", "frame_A_patient", "lv_surface.stl"), process=True)
    apex_depth = float(((bp.vertices - MV_C) @ AXIS).max())          # mm from annulus plane to apex

    # ---- 1-2. voxelise + closing ----
    vg = bp.voxelized(PITCH).fill()
    M = vg.matrix.copy()
    pad = int(np.ceil(R_CLOSE / PITCH)) + 2
    Mp = np.pad(M, pad)
    Mc = ndimage.binary_closing(Mp, structure=ball(R_CLOSE / PITCH), iterations=1)
    Mc |= Mp                                                         # closing never removes; guard rounding
    added_mL = float((Mc.sum() - Mp.sum()) * PITCH ** 3 / 1000)
    # marching cubes returns voxel-INDEX coordinates (centre of voxel i at i); VoxelGrid's
    # .marching_cubes does NOT apply the grid transform. World = origin + index*pitch, with
    # origin = world position of padded index (0,0,0). A misplaced cavity gives an empty
    # intersection and a false "no papillary muscle" -- hence the containment assertion below.
    origin = vg.transform[:3, 3] - pad * PITCH
    closed = trimesh.voxel.ops.matrix_to_marching_cubes(Mc, pitch=PITCH)
    closed.apply_translation(origin)
    closed = trimesh.Trimesh(closed.vertices, closed.faces, process=True)
    trimesh.repair.fix_normals(closed)
    chk = trimesh.boolean.intersection([bp, closed], engine="manifold")
    contain = abs(chk.volume) / abs(bp.volume)
    print(f"blood pool {abs(bp.volume)/1000:.1f} mL -> closed cavity {abs(closed.volume)/1000:.1f} mL "
          f"(+{added_mL:.1f} mL filled by closing), watertight {closed.is_watertight}, {len(closed.faces):,} f; "
          f"closed contains {100*contain:.1f}% of the pool, {time.time()-t0:.0f}s")
    assert contain > 0.97, "closed cavity misplaced -- transform bug, verdict would be meaningless"

    # ---- 3. myocardium inside the closed cavity ----
    inside = trimesh.boolean.intersection([myo, closed], engine="manifold")
    comps = inside.split(only_watertight=False)
    print(f"myo ∩ closed cavity: {abs(inside.volume)/1000:.2f} mL in {len(comps)} components, {time.time()-t0:.0f}s")

    # ---- septal direction from the RV (cardiac_meshes is mirrored; use the validated transform) ----
    ft = json.load(open(os.path.join(HERE, "BLENDER_OUT", "frame_transform.json")))["transform_cardiac_meshes_to_frameA"]
    rv = trimesh.load(os.path.join(ROOT, "cardiac_meshes", "RV_case1009.stl"), process=False)
    rv_c = trimesh.transform_points(rv.centroid[None], np.array(ft))[0]
    def short_axis(v):                                               # component of v perpendicular to AXIS
        v = v - (v @ AXIS) * AXIS; return v / (np.linalg.norm(v) + 1e-9)
    S = short_axis(rv_c - MV_C)                                      # toward the septum / RV
    A_dir = short_axis(AV_C - MV_C)                                  # toward the aortic valve (anterior)
    P_dir = np.cross(AXIS, A_dir)                                    # completes the short-axis frame
    def angle_deg(v):                                                # short-axis angle, 0 = aortic side
        return float(np.degrees(np.arctan2(v @ P_dir, v @ A_dir)))

    # ---- 4. filter ----
    rows = []
    for i, c in enumerate(comps):
        V = abs(c.volume) / 1000; A = c.area / 100
        if V < 0.02: continue
        cen = c.centroid
        dep = float((cen - MV_C) @ AXIS) / apex_depth
        r = short_axis(cen - MV_C)
        rows.append(dict(idx=i, volume_mL=round(V, 3), area_cm2=round(A, 2),
                         thickness_2V_A_mm=round(20 * V / A, 2) if A > 0 else 0.0,
                         depth_frac=round(dep, 3), angle_from_aortic_deg=round(angle_deg(r), 1),
                         septal_dot=round(float(r @ S), 2), extent_mm=[round(float(x), 1) for x in c.extents],
                         faces=int(len(c.faces)), watertight=bool(c.is_watertight)))
    rows.sort(key=lambda r: -r["volume_mL"])
    keep = [r for r in rows if r["volume_mL"] >= V_MIN and r["thickness_2V_A_mm"] >= T_MIN
            and DEPTH[0] <= r["depth_frac"] <= DEPTH[1]]
    print(f"{len(rows)} components >= 0.02 mL; {len(keep)} pass V>={V_MIN} mL, 2V/A>={T_MIN} mm, depth {DEPTH}")
    for r in rows[:12]:
        flag = "KEEP" if r in keep else "    "
        print(f"  {flag} #{r['idx']:<4} V {r['volume_mL']:6.2f} mL  2V/A {r['thickness_2V_A_mm']:5.2f} mm  depth {r['depth_frac']:5.2f}  "
              f"angle {r['angle_from_aortic_deg']:7.1f}  septal {r['septal_dot']:+.2f}  ext {r['extent_mm']}")

    # ---- 5. label ----
    out = dict(params=dict(PITCH=PITCH, R_CLOSE=R_CLOSE, V_MIN=V_MIN, T_MIN=T_MIN, DEPTH=DEPTH),
               blood_pool_mL=round(abs(bp.volume) / 1000, 2), closed_cavity_mL=round(abs(closed.volume) / 1000, 2),
               filled_by_closing_mL=round(added_mL, 2), myo_inside_closed_mL=round(abs(inside.volume) / 1000, 2),
               n_components=len(comps), components=rows[:30], kept=keep,
               septal_dir_frameA=[round(float(x), 3) for x in S], aortic_dir_frameA=[round(float(x), 3) for x in A_dir],
               rv_centroid_frameA=[round(float(x), 1) for x in rv_c])
    labels = {}
    if len(keep) >= 2:
        a, b = keep[0], keep[1]
        sep = abs(((a["angle_from_aortic_deg"] - b["angle_from_aortic_deg"] + 180) % 360) - 180)
        med, lat = (a, b) if a["septal_dot"] > b["septal_dot"] else (b, a)
        labels = dict(posteromedial=med["idx"], anterolateral=lat["idx"], angular_separation_deg=round(sep, 1),
                      beneath_commissures=bool(60 <= abs(a["angle_from_aortic_deg"]) <= 150 and 60 <= abs(b["angle_from_aortic_deg"]) <= 150),
                      opposite_sides=bool(sep >= 100))
        for name, idx in (("posteromedial", med["idx"]), ("anterolateral", lat["idx"])):
            comps[idx].export(os.path.join(FA, f"pm_{name}_patient.stl"))
        out["verdict"] = ("PATIENT PAPILLARY MUSCLES FOUND" if labels["beneath_commissures"] and labels["opposite_sides"]
                          else "TWO CANDIDATES BUT GEOMETRY ATYPICAL -- inspect pm_extract_sections.png")
    elif len(keep) == 1:
        out["verdict"] = "ONE CANDIDATE ONLY -- second muscle absent or merged; inspect"
        comps[keep[0]["idx"]].export(os.path.join(FA, "pm_candidate_single_patient.stl"))
    else:
        out["verdict"] = "NO PAPILLARY MUSCLE IN THE MYOCARDIUM LABEL -- segmentation lumped them into the cavity"
    out["labels"] = labels
    print("VERDICT:", out["verdict"], labels)
    json.dump(out, open(os.path.join(HERE, "pm_extract.json"), "w"), indent=1)

    # ---- figure: three short-axis sections + one long-axis ----
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 4, figsize=(20, 5))
    def draw(axh, origin, normal, title):
        for m, col, lw in ((myo, "0.6", 0.6), (bp, "tab:blue", 0.8), (closed, "tab:green", 0.8)):
            s = m.section(plane_origin=origin, plane_normal=normal)
            if s is None: continue
            p2, _ = s.to_planar(normal=normal)
            for e in p2.discrete: axh.plot(e[:, 0], e[:, 1], color=col, lw=lw)
        for r in keep:
            s = comps[r["idx"]].section(plane_origin=origin, plane_normal=normal)
            if s is None: continue
            p2, _ = s.to_planar(normal=normal)
            for e in p2.discrete: axh.fill(e[:, 0], e[:, 1], color="tab:red", alpha=0.6)
        axh.set_aspect("equal"); axh.set_title(title, fontsize=9)
    for k, f in enumerate((0.35, 0.5, 0.65)):
        draw(ax[k], MV_C + f * apex_depth * AXIS, AXIS, f"short axis, depth {f:.2f} (grey myo, blue pool, green closed, red = kept)")
    draw(ax[3], MV_C, np.cross(AXIS, A_dir), "long axis through MV-AV")
    plt.tight_layout(); plt.savefig(os.path.join(HERE, "pm_extract_sections.png"), dpi=80)
    print(f"done {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
