# -*- coding: utf-8 -*-
"""Step 25 -- the HOLLOW whole heart: four chambers + great-vessel lumens as cavities, the patient's LV interior from
v5 (trabeculae, papillary muscles, chordae, parametric valves), coronary arteries on the outside, and a four-chamber
cut-away for teaching.

Voxel side (extended label grid, ~1 mm, from ct_great_vessels.py):
  shell   = (LV myocardium u LV cavity) u blood pools grown by synthetic walls (RV 3.0, atria 2.5, vessels 2.0 mm)
  hollow  = shell  minus  RV/LA/RA/aorta/PA/pulmonary-vein/SVC/IVC label voxels (the lumens)
                   minus  the LV region eroded by 1 mm (a 1 mm epicardial skin stays and overlaps v5 -> seamless union)
  -> continuous-field iso-surface (sigma 0.7 voxel so 2 mm walls survive), largest component
Mesh side (manifold booleans, frame A):
  whole_heart_hollow = hollow  u  v5 (BLENDER_OUT/hollow_ventricle_v5_CT_hires.stl, decimated to <= V5_FACES)  u  coronary tubes
Four-chamber cut: plane through LV apex, mitral centre (frame-A geometry) and tricuspid centre (RV-RA label contact)
  -> halves A/B (+ _PRINT_ORIENTED, cut face down), renders looking into each cut face.
Honesty: LV wall/interior, chambers, great-vessel lumens, coronary routes = patient; RV/atrial/vessel WALL thickness =
synthetic; mitral/aortic leaflets, AV-plane plate, chordae routes = parametric; NO tricuspid/pulmonary valves; vessel
stumps are closed at the scan/cap ends; IVC absent when unenhanced.
Stages are cached; rerun the same command until it prints DONE.  Env: CASE, V5_FACES (600000).
"""
import os, sys, json, time, warnings
import numpy as np, trimesh
from scipy import ndimage
from skimage import measure
from trimesh.smoothing import filter_taubin
from case_paths import paths, geometry, dist_to, HERE
warnings.filterwarnings("ignore")
P = paths(); G = geometry(); OUT = os.path.join(P["base"], "whole_heart_hollow"); os.makedirs(OUT, exist_ok=True)
EXT = os.path.join(P["base"], "labels_extended.npz")
# LV solid: v5 (wall + trabeculae + papillary muscles + parametric plate/valves/chordae) for 1009; for any other case the
# continuous-field LV myocardium from ct_hires_lv.py (wall + trabeculae + papillary muscles, open valve orifices, no leaflets)
V5 = os.path.join(HERE, "BLENDER_OUT", "hollow_ventricle_v5_CT_hires.stl") if P["legacy"] else os.path.join(P["hires"], "LV_myocardium_CT_hires.stl")
WALL = {600: 3.0, 420: 2.5, 550: 2.5, 820: 2.0, 850: 2.0, 901: 2.0, 902: 2.0, 903: 2.0}
V5_FACES, TARGET_HOLLOW = int(os.environ.get("V5_FACES", 600000)), 500000
stage = sys.argv[sys.argv.index("--stage") + 1] if "--stage" in sys.argv else "all"
t0 = time.time()
unit = lambda v: v / (np.linalg.norm(v) + 1e-12)


def iso(mask, A, sp, sigma=0.7, target=TARGET_HOLLOW, taubin=6):
    f = ndimage.gaussian_filter(np.pad(mask, 2).astype(np.float32), (sigma, sigma, sigma * sp[0] / sp[2]))
    v, fc, _, _ = measure.marching_cubes(f, level=0.5, spacing=(1, 1, 1))
    w = trimesh.transform_points(v - 2, A) + np.asarray(G["T"])[:3, 3]
    m = trimesh.Trimesh(w, fc, process=True); trimesh.repair.fix_normals(m)
    parts = m.split(only_watertight=False)
    if len(parts) > 1: m = max(parts, key=lambda q: abs(q.volume))
    filter_taubin(m, lamb=0.5, nu=-0.53, iterations=taubin)
    if len(m.faces) > target: m = m.simplify_quadric_decimation(face_count=target)
    if not m.is_watertight:
        import pymeshfix
        vc, fcc = pymeshfix.clean_from_arrays(np.ascontiguousarray(m.vertices, dtype=np.float64), np.ascontiguousarray(m.faces, dtype=np.int32)); m = trimesh.Trimesh(vc, fcc, process=True)
    trimesh.repair.fix_normals(m); return m


def stage_hollow():
    out = os.path.join(OUT, "hollow_shell_noLV.stl")
    if os.path.exists(out): return "cached"
    z = np.load(EXT); L = z["L"].astype(np.int16); A = z["affine"]; sp = np.array(z["spacing"], float)
    lv = (L == 205) | (L == 500)
    shell = lv.copy()
    for k, w in WALL.items():
        if (L == k).any(): shell |= dist_to(L == k, sp) <= w
    lumens = np.isin(L, list(WALL))
    lv_eroded = lv & (dist_to(~lv, sp) >= 1.0)
    hollow = shell & ~lumens & ~lv_eroded
    # tricuspid centre for the cut plane (RV-RA contact) while the labels are in memory
    st = np.ones((3, 3, 3), bool); tv = (L == 600) & ndimage.binary_dilation(L == 550, structure=st, iterations=2)
    tv_c = trimesh.transform_points(np.argwhere(tv).astype(float), A).mean(0) + np.asarray(G["T"])[:3, 3] if tv.any() else None
    m = iso(hollow, A, sp); m.export(out)
    json.dump(dict(tv_centre_mm=None if tv_c is None else tv_c.round(2).tolist(), wall_mm=WALL, hollow_faces=int(len(m.faces)), hollow_volume_mL=round(float(abs(m.volume)) / 1000, 1), hollow_watertight=bool(m.is_watertight)), open(os.path.join(OUT, "hollow_info.json"), "w"), indent=1)
    print(f"hollow shell (no LV): {len(m.faces):,} f, {abs(m.volume)/1000:.0f} mL, watertight {m.is_watertight}  ({time.time()-t0:.0f}s)"); return "ok"


def stage_union():
    out = os.path.join(OUT, "whole_heart_hollow.stl")
    if os.path.exists(out): return "cached"
    hollow = trimesh.load(os.path.join(OUT, "hollow_shell_noLV.stl"), process=True)
    parts = [hollow]
    if V5 and os.path.exists(V5):
        v5 = trimesh.load(V5, process=True)
        if V5_FACES > 0 and len(v5.faces) > V5_FACES:               # quadric decimation breaks manifoldness -> pymeshfix restores a volume (volume change < 0.1 %)
            v5 = v5.simplify_quadric_decimation(face_count=V5_FACES)
            if not v5.is_volume:
                import pymeshfix
                vc, fcc = pymeshfix.clean_from_arrays(np.ascontiguousarray(v5.vertices, dtype=np.float64), np.ascontiguousarray(v5.faces, dtype=np.int32)); v5 = trimesh.Trimesh(vc, fcc, process=True)
        trimesh.repair.fix_normals(v5); assert v5.is_volume, "v5 is not a volume after decimation/repair"
        parts.append(v5)
    tube_p = os.path.join(P["coronary"], "coronary_tree_print_frameA.stl")
    if os.path.exists(tube_p): parts.append(trimesh.load(tube_p, process=True))
    u = trimesh.boolean.union(parts, engine="manifold"); del parts
    comps = u.split(only_watertight=False)
    if len(comps) > 1:                                   # keep the heart; drop any crumbs the booleans left behind
        comps = sorted(comps, key=lambda q: -abs(q.volume)); crumbs = sum(abs(c.volume) for c in comps[1:]) / 1000; u = comps[0]
    else: crumbs = 0.0
    u.export(out)
    r = dict(faces=int(len(u.faces)), volume_mL=round(float(abs(u.volume)) / 1000, 1), watertight=bool(u.is_watertight), components_before_cleanup=len(comps), crumbs_dropped_mL=round(float(crumbs), 2), lv_solid=os.path.relpath(V5, HERE) if (V5 and os.path.exists(V5)) else None)
    json.dump(r, open(os.path.join(OUT, "union_info.json"), "w"), indent=1); print("union:", r, f"({time.time()-t0:.0f}s)"); return "ok"


def stage_cut():
    outA = os.path.join(OUT, "whole_heart_hollow_4ch_A.stl")
    if os.path.exists(outA): return "cached"
    info = json.load(open(os.path.join(OUT, "hollow_info.json")))
    mv = np.array(G["mv_centre"]); axis = unit(np.array(G["axis"]))
    length = float(json.load(open(os.path.join(HERE, "valve_refit.json")))["lv_geometry"]["length"]) if P["legacy"] else float(G["raw"]["lv_length_mm"])
    apex = mv + axis * length; tv = np.array(info["tv_centre_mm"]) if info["tv_centre_mm"] else None
    n = unit(np.cross(tv - apex, mv - apex)) if tv is not None else unit(np.cross(axis, [0, 1.0, 0]))
    origin = (apex + mv + (tv if tv is not None else mv)) / 3
    whole = trimesh.load(os.path.join(OUT, "whole_heart_hollow.stl"), process=True)
    halves = {}
    for tag, sign in (("A", 1.0), ("B", -1.0)):
        h = trimesh.intersections.slice_mesh_plane(whole, plane_normal=sign * n, plane_origin=origin, cap=True)
        h = trimesh.Trimesh(h.vertices, h.faces, process=True); trimesh.repair.fix_normals(h)
        comps = h.split(only_watertight=False)
        if len(comps) > 1: h = max(comps, key=lambda q: abs(q.volume))
        h.export(os.path.join(OUT, f"whole_heart_hollow_4ch_{tag}.stl"))
        R = trimesh.geometry.align_vectors(sign * n, [0, 0, -1.0]); hp = h.copy(); hp.apply_transform(R); hp.apply_translation(-hp.bounds[0]); hp.export(os.path.join(OUT, f"whole_heart_hollow_4ch_{tag}_PRINT_ORIENTED.stl"))
        halves[tag] = dict(faces=int(len(h.faces)), volume_mL=round(float(abs(h.volume)) / 1000, 1), watertight=bool(h.is_watertight))
        print(f"half {tag}: {halves[tag]}  ({time.time()-t0:.0f}s)")
    json.dump(dict(plane_origin=origin.round(2).tolist(), plane_normal=n.round(4).tolist(), apex=apex.round(2).tolist(), mv=mv.round(2).tolist(), tv=None if tv is None else tv.round(2).tolist(), halves=halves,
                   volume_check=dict(whole=round(float(abs(whole.volume)) / 1000, 1), halves_sum=round(sum(v["volume_mL"] for v in halves.values()), 1))), open(os.path.join(OUT, "cut_info.json"), "w"), indent=1)
    return "ok"


def stage_render():
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection
    cut = json.load(open(os.path.join(OUT, "cut_info.json"))); n = np.array(cut["plane_normal"]); origin = np.array(cut["plane_origin"]); axis = unit(np.array(G["axis"]))
    fig, axes = plt.subplots(1, 3, figsize=(24, 9))
    def draw(ax, mesh, viewdir, title, col=(0.86, 0.70, 0.64)):
        tri, nrm = mesh.triangles, mesh.face_normals
        keep = nrm @ (-viewdir) > -0.2; tri, nrm = tri[keep], nrm[keep]
        light = unit(-viewdir + 0.35 * np.cross(-viewdir, axis)); lam = np.clip(np.abs(nrm @ light), 0, 1) * 0.75 + 0.25
        u = unit(np.cross(viewdir, axis if abs(viewdir @ axis) < 0.9 else [1, 0, 0])); v = np.cross(viewdir, u)
        Pp = (tri - origin) @ np.c_[u, v]; depth = ((tri - origin) @ viewdir).mean(1); order = np.argsort(-depth)
        cols = np.c_[np.tile(lam[order], (3, 1)).T * col, np.ones(len(order))]
        ax.add_collection(PolyCollection(Pp[order], facecolors=cols, edgecolors=cols, linewidths=0.2, antialiased=False))
        lo, hi = Pp.reshape(-1, 2).min(0) - 5, Pp.reshape(-1, 2).max(0) + 5; ax.set_xlim(lo[0], hi[0]); ax.set_ylim(lo[1], hi[1]); ax.set_aspect("equal"); ax.set_axis_off(); ax.set_title(title, fontsize=11)
    A_ = trimesh.load(os.path.join(OUT, "whole_heart_hollow_4ch_A.stl"), process=False); B_ = trimesh.load(os.path.join(OUT, "whole_heart_hollow_4ch_B.stl"), process=False)
    whole = trimesh.load(os.path.join(OUT, "whole_heart_hollow.stl"), process=False)
    if len(whole.faces) > 250000: whole = whole.simplify_quadric_decimation(face_count=250000)
    # half A keeps the +n side: its cut face points to -n, so look along +n (camera on the -n side); B the other way round
    draw(axes[0], A_ if len(A_.faces) < 400000 else A_.simplify_quadric_decimation(face_count=400000), n, "half A — looking into the cut face (four-chamber plane)")
    draw(axes[1], B_ if len(B_.faces) < 400000 else B_.simplify_quadric_decimation(face_count=400000), -n, "half B — looking into the cut face")
    draw(axes[2], whole, np.array([0, -1.0, 0]), "whole hollow heart with coronaries — anterior")
    plt.suptitle(f"case {P['case']} — hollow whole heart: shell − lumens ∪ v5 LV interior ∪ coronaries; four-chamber cut through apex, mitral and tricuspid centres  "
                 f"(patient: LV wall/interior, chambers, lumens, coronary routes | synthetic: RV/atrial/vessel wall thickness | parametric: mitral/aortic leaflets, plate, chordae | no tricuspid/pulmonary valves)", fontsize=10)
    plt.tight_layout(rect=(0, 0, 1, 0.95)); plt.savefig(os.path.join(OUT, "whole_heart_hollow_render.png"), dpi=75); print(f"render done ({time.time()-t0:.0f}s)")


def main():
    if not os.path.exists(EXT): sys.exit(f"{EXT} missing -- run ct_great_vessels.py first")
    if stage in ("hollow", "all"): print("hollow:", stage_hollow())
    if stage in ("union", "all") and time.time() - t0 < 110 and os.path.exists(os.path.join(OUT, "hollow_shell_noLV.stl")): print("union:", stage_union())
    if stage in ("cut", "all") and time.time() - t0 < 110 and os.path.exists(os.path.join(OUT, "whole_heart_hollow.stl")): print("cut:", stage_cut())
    done = os.path.exists(os.path.join(OUT, "whole_heart_hollow_4ch_B.stl"))
    if stage in ("render", "all") and done and time.time() - t0 < 100: stage_render(); print("DONE ->", OUT)
    elif not done: print("not finished -- rerun (stages are cached)")


if __name__ == "__main__":
    main()
