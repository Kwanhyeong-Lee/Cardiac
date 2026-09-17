# -*- coding: utf-8 -*-
"""Step 26 -- REMASTER of the hollow whole heart + anatomical segmentation.

Fixes versus step 25:
  * the AV-plane PLATE is gone.  The 12.5 mm slab (34.9 mL) was a device to hold the parametric valves in the
    stand-alone LV model; inside a whole heart it sat where the left atrium and aortic root belong ("the cylinder
    above the LV").  The LV solid is now  hires myocardium u mitral u aortic u chordae  (LV_v6_noplate.stl).
  * the mitral and aortic ORIFICES are open.  Step 25 kept a 1 mm skin of the LV region wherever it bordered
    anything -- including the LA / aortic lumens -- which left a 1 mm membrane across both orifices.  The skin is
    now kept only where the LV region borders the OUTSIDE (epicardium / basal myocardium).
Anatomical segmentation (multi-colour printing, viewing, teaching):
  parts/<name>.stl for every wall: RV_wall, LA_wall, RA_wall, aorta_wall, PA_wall, pulmonary_vein_walls, SVC_wall (each
  synthetic wall voxel belongs to the lumen it was grown from), LV_myocardium (patient), mitral_valve, aortic_valve,
  chordae (parametric), coronary systems rebuilt per name group: coronary_LAD_system (LM+LAD+D),
  coronary_LCx_system (LCx+OM+RI), coronary_RCA_system (RCA+PDA+PLV+RV-br); septum and papillary muscles are given
  as vertex labels on the LV myocardium (septum = within SEPT_MM of the RV lumen; PM = inside the CT PM candidates).
  parts_manifest.json: file, colour, provenance, volume.  whole_heart_hollow_v2_4ch_{A,B}_anatomy.ply: the cut halves
  with per-face colours by nearest part.  Render: halves coloured by part + legend.
Cut face (stage `recap`): slice_mesh_plane caps each section loop with an ear-clipping fan of slivers that span
  several structures at once, so the cut face came out as coloured streaks with no readable boundary.  The cap is
  now rebuilt from the body's own open boundary with a constrained Delaunay triangulation (Triangle, -pq28a3YY:
  quality interior, NO Steiner points on any segment), material/lumen decided by a flood fill that flips only
  across a section segment, leftover leaks at self-touching outline points closed with pymeshfix.  Volumes are
  preserved to 0.3 % and both halves stay watertight.  The section outlines are written to section_loops_{A,B}.npz
  and drawn in black over the render, which also gets a third panel: the cut face alone, labelled per chamber.
  Optional dependency: `pip install triangle` -- without it the original cap is kept (no other behaviour changes).
Stages cached: lv | hollow | union | cut | recap | anatomy | render | all.   Env: CASE, V5 not used.
"""
import os, sys, json, time, warnings
import numpy as np, trimesh
from scipy import ndimage
from scipy.spatial import cKDTree
from skimage import measure
from trimesh.smoothing import filter_taubin
from case_paths import paths, geometry, dist_to, HERE
warnings.filterwarnings("ignore")
P = paths(); G = geometry(); OUT = os.path.join(P["base"], "whole_heart_hollow"); PARTS = os.path.join(OUT, "parts"); os.makedirs(PARTS, exist_ok=True)
EXT = os.path.join(P["base"], "labels_extended.npz"); BO = os.path.join(HERE, "BLENDER_OUT"); FA = os.path.join(HERE, "frame_A_patient")
RV_DIR = FA if P["legacy"] else os.path.join(P["base"], "valves")
WALL = {600: 3.0, 420: 2.5, 550: 2.5, 820: 2.0, 850: 2.0, 901: 2.0, 902: 2.0, 903: 2.0}
WALLNAME = {600: "RV_wall", 420: "LA_wall", 550: "RA_wall", 820: "aorta_wall", 850: "PA_wall", 901: "pulmonary_vein_walls", 902: "SVC_wall", 903: "IVC_wall"}
COL = {"LV_myocardium": (0.72, 0.28, 0.26), "LV_septum": (0.60, 0.22, 0.30), "LV_papillary": (0.85, 0.45, 0.42), "mitral_valve": (0.93, 0.88, 0.72), "aortic_valve": (0.90, 0.85, 0.65), "chordae": (0.97, 0.95, 0.90), "tricuspid_valve": (0.88, 0.84, 0.70), "pulmonary_valve": (0.86, 0.82, 0.66),
       "RV_wall": (0.42, 0.50, 0.72), "LA_wall": (0.88, 0.58, 0.60), "RA_wall": (0.58, 0.70, 0.85), "aorta_wall": (0.88, 0.40, 0.28), "PA_wall": (0.30, 0.50, 0.80), "pulmonary_vein_walls": (0.95, 0.72, 0.72), "SVC_wall": (0.55, 0.78, 0.95), "IVC_wall": (0.35, 0.60, 0.75),
       "coronary_LAD_system": (0.90, 0.10, 0.10), "coronary_LCx_system": (0.97, 0.60, 0.10), "coronary_RCA_system": (0.10, 0.35, 0.90)}
SEPT_MM, LV_FACES = 6.0, 600000
stage = sys.argv[sys.argv.index("--stage") + 1] if "--stage" in sys.argv else "all"
t0 = time.time(); unit = lambda v: v / (np.linalg.norm(v) + 1e-12)


def fix_volume(m):
    if not m.is_volume:
        import pymeshfix
        vc, fc = pymeshfix.clean_from_arrays(np.ascontiguousarray(m.vertices, dtype=np.float64), np.ascontiguousarray(m.faces, dtype=np.int32)); m = trimesh.Trimesh(vc, fc, process=True)
    trimesh.repair.fix_normals(m); return m


def iso(mask, A, sp, sigma=0.7, target=400000, taubin=6, keep_min_mL=None):
    f = ndimage.gaussian_filter(np.pad(mask, 2).astype(np.float32), (sigma, sigma, sigma * sp[0] / sp[2]))
    v, fc, _, _ = measure.marching_cubes(f, level=0.5, spacing=(1, 1, 1))
    m = trimesh.Trimesh(trimesh.transform_points(v - 2, A) + np.asarray(G["T"])[:3, 3], fc, process=True); trimesh.repair.fix_normals(m)
    parts = m.split(only_watertight=False)
    if len(parts) > 1:
        m = max(parts, key=lambda q: abs(q.volume)) if keep_min_mL is None else trimesh.util.concatenate([q for q in parts if abs(q.volume) / 1000 >= keep_min_mL] or [max(parts, key=lambda q: abs(q.volume))])
    filter_taubin(m, lamb=0.5, nu=-0.53, iterations=taubin)
    if len(m.faces) > target: m = m.simplify_quadric_decimation(face_count=target)
    return fix_volume(m) if keep_min_mL is None else m


def stage_lv():
    out = os.path.join(BO, "LV_v6_noplate.stl")
    if os.path.exists(out): return "cached"
    myo = trimesh.load(os.path.join(P["hires"], "LV_myocardium_CT_hires.stl"), process=True)
    parts = [myo]
    for f in (os.path.join(BO, "mitral_valve.stl"), os.path.join(BO, "aortic_valve.stl"), os.path.join(FA, "chordae_v5_CT_hires.stl")):
        if os.path.exists(f): parts.append(fix_volume(trimesh.load(f, process=True)))
    u = trimesh.boolean.union(parts, engine="manifold"); del parts
    comps = u.split(only_watertight=False); u.export(out)
    r = dict(faces=int(len(u.faces)), volume_mL=round(float(abs(u.volume)) / 1000, 2), watertight=bool(u.is_watertight), components=len(comps), component_mL=[round(float(abs(c.volume)) / 1000, 2) for c in sorted(comps, key=lambda c: -abs(c.volume))][:6])
    json.dump(r, open(os.path.join(OUT, "lv_v6_info.json"), "w"), indent=1); print("LV v6 (no plate):", r, f"({time.time()-t0:.0f}s)"); return "ok"


def stage_hollow():
    out = os.path.join(OUT, "hollow_shell_v2.stl")
    if os.path.exists(out): return "cached"
    z = np.load(EXT); L = z["L"].astype(np.int16); A = z["affine"]; sp = np.array(z["spacing"], float)
    lv = (L == 205) | (L == 500); lumens = np.isin(L, list(WALL))
    shell = lv.copy()
    for k, w in WALL.items():
        if (L == k).any(): shell |= dist_to(L == k, sp) <= w
    outside = ~(lv | lumens)
    skin = lv & (dist_to(outside, sp) <= 1.0)                 # epicardial / basal skin only -- NOT across the mitral or aortic orifice
    hollow = (shell & ~lumens & ~lv) | skin
    # owner of every wall voxel = the lumen it was grown from (for the anatomical parts)
    _, ind = ndimage.distance_transform_edt(~lumens, sampling=sp, return_indices=True)
    owner = L[tuple(ind)].astype(np.int16); owner[skin] = 205; owner[~hollow] = 0
    st = np.ones((3, 3, 3), bool); tv = (L == 600) & ndimage.binary_dilation(L == 550, structure=st, iterations=2)
    tv_c = trimesh.transform_points(np.argwhere(tv).astype(float), A).mean(0) + np.asarray(G["T"])[:3, 3] if tv.any() else None
    np.savez_compressed(os.path.join(OUT, "hollow_v2_owner.npz"), owner=owner, hollow=hollow, affine=A, spacing=sp)
    m = iso(hollow, A, sp); m.export(out)
    json.dump(dict(tv_centre_mm=None if tv_c is None else tv_c.round(2).tolist(), wall_mm=WALL, faces=int(len(m.faces)), volume_mL=round(float(abs(m.volume)) / 1000, 1), watertight=bool(m.is_watertight),
                   note="skin only against the outside: mitral and aortic orifices are open"), open(os.path.join(OUT, "hollow_v2_info.json"), "w"), indent=1)
    print(f"hollow shell v2: {len(m.faces):,} f, {abs(m.volume)/1000:.0f} mL, watertight {m.is_watertight}  ({time.time()-t0:.0f}s)"); return "ok"


def stage_union():
    out = os.path.join(OUT, "whole_heart_hollow_v2.stl")
    if os.path.exists(out): return "cached"
    hollow = trimesh.load(os.path.join(OUT, "hollow_shell_v2.stl"), process=True)
    lv = trimesh.load(os.path.join(BO, "LV_v6_noplate.stl"), process=True)
    if len(lv.faces) > LV_FACES: lv = fix_volume(lv.simplify_quadric_decimation(face_count=LV_FACES))
    parts = [hollow, lv]
    tube_p = os.path.join(P["coronary"], "coronary_tree_print_frameA.stl")
    if os.path.exists(tube_p): parts.append(trimesh.load(tube_p, process=True))
    for f in (os.path.join(RV_DIR, "tricuspid_valve_parametric.stl"), os.path.join(RV_DIR, "pulmonary_valve_parametric.stl")):   # step 27 right-side valves
        if os.path.exists(f): parts += [fix_volume(q) for q in trimesh.load(f, process=True).split(only_watertight=False)]
    u = trimesh.boolean.union(parts, engine="manifold"); del parts
    comps = sorted(u.split(only_watertight=False), key=lambda c: -abs(c.volume)); kept = [c for c in comps if abs(c.volume) / 1000 >= 0.5]
    u = trimesh.util.concatenate(kept) if len(kept) > 1 else kept[0]; u.export(out)
    r = dict(faces=int(len(u.faces)), volume_mL=round(float(abs(u.volume)) / 1000, 1), watertight=bool(u.is_watertight), components=len(kept), component_mL=[round(float(abs(c.volume)) / 1000, 2) for c in kept[:6]], crumbs_dropped=len(comps) - len(kept))
    json.dump(r, open(os.path.join(OUT, "union_v2_info.json"), "w"), indent=1); print("union v2:", r, f"({time.time()-t0:.0f}s)"); return "ok"


def cut_plane():
    info = json.load(open(os.path.join(OUT, "hollow_v2_info.json")))
    mv = np.array(G["mv_centre"]); axis = unit(np.array(G["axis"]))
    length = float(json.load(open(os.path.join(HERE, "valve_refit.json")))["lv_geometry"]["length"]) if P["legacy"] else float(G["raw"]["lv_length_mm"])
    apex = mv + axis * length; tv = np.array(info["tv_centre_mm"]) if info["tv_centre_mm"] else None
    n = unit(np.cross(tv - apex, mv - apex)) if tv is not None else unit(np.cross(axis, [0, 1.0, 0]))
    return (apex + mv + (tv if tv is not None else mv)) / 3, n, apex, mv, tv


def stage_cut():
    if os.path.exists(os.path.join(OUT, "whole_heart_hollow_v2_4ch_B.stl")): return "cached"
    origin, n, apex, mv, tv = cut_plane()
    whole = trimesh.load(os.path.join(OUT, "whole_heart_hollow_v2.stl"), process=True); halves = {}
    for tag, sign in (("A", 1.0), ("B", -1.0)):
        h = trimesh.intersections.slice_mesh_plane(whole, plane_normal=sign * n, plane_origin=origin, cap=True)
        h = trimesh.Trimesh(h.vertices, h.faces, process=True); trimesh.repair.fix_normals(h)
        comps = sorted(h.split(only_watertight=False), key=lambda c: -abs(c.volume)); h = trimesh.util.concatenate([c for c in comps if abs(c.volume) / 1000 >= 0.3]) if len(comps) > 1 else h
        h.export(os.path.join(OUT, f"whole_heart_hollow_v2_4ch_{tag}.stl"))
        R = trimesh.geometry.align_vectors(sign * n, [0, 0, -1.0]); hp = h.copy(); hp.apply_transform(R); hp.apply_translation(-hp.bounds[0]); hp.export(os.path.join(OUT, f"whole_heart_hollow_v2_4ch_{tag}_PRINT_ORIENTED.stl"))
        halves[tag] = dict(faces=int(len(h.faces)), volume_mL=round(float(abs(h.volume)) / 1000, 1), watertight=bool(h.is_watertight)); print(f"half {tag}: {halves[tag]}  ({time.time()-t0:.0f}s)")
    json.dump(dict(plane_origin=origin.round(2).tolist(), plane_normal=n.round(4).tolist(), apex=apex.round(2).tolist(), mv=mv.round(2).tolist(), tv=None if tv is None else tv.round(2).tolist(), halves=halves,
                   volume_check=dict(whole=round(float(abs(whole.volume)) / 1000, 1), halves_sum=round(sum(v["volume_mL"] for v in halves.values()), 1))), open(os.path.join(OUT, "cut_v2_info.json"), "w"), indent=1)
    return "ok"


def cap_mask(h, origin, n, tol=0.05, dot=0.99):
    """faces of a sliced half that lie in the cut plane (the cap produced by slice_mesh_plane)."""
    return (np.abs((h.triangles_center - origin) @ n) < tol) & (np.abs(h.face_normals @ n) > dot)


def plane_basis(n):
    u = unit(np.cross(n, [0, 0, 1.0] if abs(n[2]) < 0.9 else [1.0, 0, 0])); return u, np.cross(n, u)   # u x v = n


def open_edges(faces):
    e = np.sort(faces[:, [0, 1, 1, 2, 2, 0]].reshape(-1, 2), axis=1)
    uq, cnt = np.unique(e, axis=0, return_counts=True); return uq[cnt == 1]


def inside_by_flood(TF, S):
    """Label the triangles of a constrained triangulation material / lumen by flooding from the outside and
    flipping only when a CONSTRAINED segment is crossed.  Point-in-polygon rules are ambiguous where the cut
    plane grazes a thin wall and the section outline touches itself; this is consistent by construction --
    two triangles sharing a non-segment edge always get the same label, so no interior edge can be left open."""
    from collections import deque
    F = len(TF); E = np.sort(TF[:, [0, 1, 1, 2, 2, 0]].reshape(-1, 2), axis=1); fid = np.repeat(np.arange(F), 3)
    o = np.lexsort((E[:, 1], E[:, 0])); E, fid = E[o], fid[o]
    same = np.all(E[1:] == E[:-1], axis=1)
    pe = E[:-1][same]; pa = fid[:-1][same]; pb = fid[1:][same]
    segs = set(map(tuple, np.sort(np.asarray(S), axis=1)))
    cross = np.fromiter((tuple(x) in segs for x in pe), bool, len(pe))
    adj = [[] for _ in range(F)]
    for a, b, c in zip(pa, pb, cross): adj[a].append((b, c)); adj[b].append((a, c))
    single = np.ones(len(E), bool); single[:-1] &= ~same; single[1:] &= ~same          # hull edges: one triangle only
    lab = np.full(F, -1, np.int8); q = deque()
    for f in np.unique(fid[single]):
        if lab[f] < 0: lab[f] = 0; q.append(f)
    while q:
        f = q.popleft()
        for g, c in adj[f]:
            if lab[g] < 0: lab[g] = lab[f] ^ int(c); q.append(g)
    lab[lab < 0] = 0
    return lab


def boundary_loops(faces):
    """edges used once inside a face patch -> the patch outline, chained into closed loops."""
    bnd = open_edges(faces)
    adj = {}
    for a, b in bnd: adj.setdefault(int(a), []).append(int(b)); adj.setdefault(int(b), []).append(int(a))
    seen, loops = set(), []
    for s in list(adj):
        if s in seen: continue
        loop = [s]; seen.add(s); cur, prev = s, None
        while True:
            nxt = [q for q in adj[cur] if q != prev and q not in seen]
            if not nxt: break
            prev, cur = cur, nxt[0]; seen.add(cur); loop.append(cur)
        if len(loop) >= 3: loops.append(loop)
    return bnd, loops


def recap(h, origin, n, max_area=3.0, min_angle=28):
    """Replace the cap of a sliced half by a QUALITY constrained triangulation of the same section polygon.

    slice_mesh_plane caps each section loop with an ear-clipping fan: a handful of sliver triangles that
    (a) span several different structures, so a per-face colour is meaningless, and (b) render as thin streaks
    across the cut face.  Here the cap is thrown away and rebuilt from the BODY's own open boundary (the exact
    section outline), fed to Triangle as a PSLG with -Y (no Steiner points ON the boundary) so every boundary
    vertex is kept and the seal is exact; only the interior is refined to <= max_area mm^2.  Triangles that
    fall in a chamber lumen are dropped by a crossing-number test against the same segments.
    Returns (mesh, loops_3d, ok).  Without the optional `triangle` package the cap is left as it was.
    """
    cap = cap_mask(h, origin, n)
    if cap.sum() < 4: return h, [], False
    _, loops = boundary_loops(h.faces[cap]); u, v = plane_basis(n); B = np.c_[u, v]
    loops3 = [h.vertices[lp] for lp in loops]
    if len(loops) > cap.sum() / 2:                                                     # unmerged mesh: every triangle is its own "loop" -> Triangle would get duplicate points
        print("  [recap skipped: mesh vertices are not merged]"); return h, loops3, False
    try: import triangle as _tr
    except Exception as e:
        print(f"  [recap skipped: {e}] -- pip install triangle"); return h, loops3, False
    s = float(np.sign((h.face_normals[cap] @ n).mean()))
    body = h.faces[~cap]; bnd = open_edges(body)                                       # the hole the new cap has to seal, exactly as the body sees it
    vid = np.unique(bnd); remap = np.full(len(h.vertices), -1, int); remap[vid] = np.arange(len(vid))
    V2 = (h.vertices[vid] - origin) @ B; S = remap[bnd]
    t = _tr.triangulate(dict(vertices=V2, segments=S), f"pq{min_angle}a{max_area}YY")   # YY: no Steiner points on ANY segment (single Y protects only the convex hull, and the chamber outlines are internal segments)
    TV = np.asarray(t["vertices"], float); TF = np.asarray(t["triangles"], int)
    if not np.allclose(TV[:len(vid)], V2, atol=1e-6): return h, loops3, False          # input order must be preserved
    lab = inside_by_flood(TF, S)                                                       # parity is fixed by area: -p already confines Triangle to the outer contour, so "seeded from the hull" is material, not air
    ar = lambda F: 0.5 * float(np.abs(np.cross(TV[F[:, 1]] - TV[F[:, 0]], TV[F[:, 2]] - TV[F[:, 0]])).sum())
    a0 = float(h.area_faces[cap].sum()); keep = lab == (0 if abs(ar(TF[lab == 0]) - a0) < abs(ar(TF[lab == 1]) - a0) else 1)
    TF = TF[keep]
    new = TV[len(vid):] @ B.T + origin
    idx = np.concatenate([vid, len(h.vertices) + np.arange(len(new))])
    newcap = idx[TF][:, ::-1] if s < 0 else idx[TF]
    m = trimesh.Trimesh(np.vstack([h.vertices, new]), np.vstack([body, newcap]), process=True)
    if not m.is_watertight:                                                            # ~300 leaks remain where the outline touches itself (plane grazing a thin wall): parity is undefined there
        n_open = len(open_edges(m.faces)); m = fix_volume(m)
        print(f"  {n_open} open edge(s) at self-touching outline points -> pymeshfix -> watertight {m.is_watertight}")
    trimesh.repair.fix_normals(m)
    if not m.is_watertight or abs(abs(m.volume) - abs(h.volume)) / max(abs(h.volume), 1) > 0.02:
        print(f"  [recap rejected: watertight {m.is_watertight}, volume {abs(m.volume)/1000:.1f} vs {abs(h.volume)/1000:.1f} mL]"); return h, loops3, False
    print(f"  cap: {cap.sum():,} sliver f -> {len(newcap):,} f (<= {max_area} mm2), {len(loops)} loops, watertight {m.is_watertight}")
    return m, loops3, True


def stage_recap():
    """re-cap both halves with the quality triangulation (idempotent; per-tag cache in cut_v2_info.json)."""
    info_p = os.path.join(OUT, "cut_v2_info.json"); info = json.load(open(info_p))
    if all(info.get("cap_retriangulated", {}).get(t) for t in ("A", "B")): return "cached"
    origin = np.array(info["plane_origin"]); n = np.array(info["plane_normal"]); done = info.get("cap_retriangulated", {})
    for tag, sign in (("A", 1.0), ("B", -1.0)):
        if done.get(tag) or time.time() - t0 > 60: continue
        p = os.path.join(OUT, f"whole_heart_hollow_v2_4ch_{tag}.stl")
        h = trimesh.load(p, process=True)                                  # MUST merge vertices: an unmerged STL has no shared edges, so every cap triangle would look like its own loop
        m, loops3, ok = recap(h, origin, n)
        np.savez_compressed(os.path.join(OUT, f"section_loops_{tag}.npz"), **{f"l{i}": L for i, L in enumerate(loops3)})
        if not ok: done[tag] = False; continue
        m.export(p)
        R = trimesh.geometry.align_vectors(sign * n, [0, 0, -1.0]); hp = m.copy(); hp.apply_transform(R); hp.apply_translation(-hp.bounds[0])
        hp.export(os.path.join(OUT, f"whole_heart_hollow_v2_4ch_{tag}_PRINT_ORIENTED.stl"))
        info["halves"][tag] = dict(faces=int(len(m.faces)), volume_mL=round(float(abs(m.volume)) / 1000, 1), watertight=bool(m.is_watertight)); done[tag] = True
        print(f"half {tag} recapped: {info['halves'][tag]}  ({time.time()-t0:.0f}s)")
    info["cap_retriangulated"] = done; info["cap_note"] = "cut cap re-triangulated (Triangle, -Y so the section outline is untouched); section outlines in section_loops_{A,B}.npz"
    info["volume_check"]["halves_sum"] = round(sum(v["volume_mL"] for v in info["halves"].values()), 1)
    json.dump(info, open(info_p, "w"), indent=1); return "ok" if all(done.get(t) for t in ("A", "B")) else "partial"


def tube_from_centrelines(cor, names, vox=0.3, r_min=1.0):
    pts, rad = [], []
    for cid, cl in cor["centrelines"].items():
        if cl["name"] not in names or len(cl["pts"]) < 2: continue
        Pp = np.array(cl["pts"]); r = np.maximum(np.array(cl["r_mm"]), r_min)
        seg = np.linalg.norm(np.diff(Pp, axis=0), axis=1); s = np.r_[0, np.cumsum(seg)]; ss = np.arange(0, s[-1] + 1e-6, vox)
        pts.append(np.c_[[np.interp(ss, s, Pp[:, k]) for k in range(3)]].T); rad.append(np.interp(ss, s, r))
    if not pts: return None
    pts = np.concatenate(pts); rad = np.concatenate(rad); lo = pts.min(0) - 4; shape = np.ceil((pts.max(0) + 4 - lo) / vox).astype(int) + 1
    grid = np.zeros(shape, bool); gi = ((pts - lo) / vox).round().astype(int); rmax = int(np.ceil(rad.max() / vox)) + 1
    offs = np.argwhere(np.ones((2 * rmax + 1,) * 3)) - rmax; od = np.linalg.norm(offs, axis=1) * vox
    for c, r in zip(gi, rad):
        q = c + offs[od <= r]; q = q[(q >= 0).all(1) & (q < shape).all(1)]; grid[tuple(q.T)] = True
    f = ndimage.gaussian_filter(grid.astype(np.float32), 1.0); v, fc, _, _ = measure.marching_cubes(f, level=0.5, spacing=(vox,) * 3)
    m = trimesh.Trimesh(v + lo, fc, process=True); trimesh.repair.fix_normals(m); filter_taubin(m, lamb=0.5, nu=-0.53, iterations=8); return m


def stage_anatomy():
    man_p = os.path.join(OUT, "parts_manifest.json")
    if os.path.exists(man_p): return "cached"
    z = np.load(os.path.join(OUT, "hollow_v2_owner.npz")); owner = z["owner"]; A = z["affine"]; sp = np.array(z["spacing"], float)
    manifest = []
    def add(name, path, prov, mesh=None):
        m = mesh if mesh is not None else trimesh.load(path, process=False)
        manifest.append(dict(name=name, file=os.path.relpath(path, OUT), colour_rgb=[round(c, 3) for c in COL.get(name, (0.7, 0.7, 0.7))], provenance=prov, faces=int(len(m.faces)), volume_mL=round(float(abs(m.volume)) / 1000, 2)))
    for k, nm in WALLNAME.items():
        if not (owner == k).any(): continue
        m = iso(owner == k, A, sp, target=200000, keep_min_mL=0.3); p = os.path.join(PARTS, f"{nm}.stl"); m.export(p)
        add(nm, p, "synthetic wall thickness (uniform) around the patient's lumen"); print(f"  {nm}: {len(m.faces):,} f  ({time.time()-t0:.0f}s)")
    # LV parts (copies) with septum / papillary vertex labels on the myocardium
    myo = trimesh.load(os.path.join(P["hires"], "LV_myocardium_CT_hires.stl"), process=False)
    z2 = np.load(EXT); L = z2["L"].astype(np.int16); A2 = z2["affine"]
    rv_pts = trimesh.transform_points(np.argwhere(L == 600)[::3].astype(float), A2) + np.asarray(G["T"])[:3, 3]
    d_rv, _ = cKDTree(rv_pts).query(myo.vertices); lab = np.zeros(len(myo.vertices), np.int8); lab[d_rv <= SEPT_MM] = 1
    for i in (1, 2):
        pmp = os.path.join(HERE, "CT", f"pm_candidate_{i}_CT.stl")
        if os.path.exists(pmp):
            pm = trimesh.load(pmp, process=True); dpm, _ = cKDTree(pm.vertices).query(myo.vertices); lab[dpm <= 1.5] = 2
    cols = np.array([COL["LV_myocardium"], COL["LV_septum"], COL["LV_papillary"]])[lab]
    myo.visual.vertex_colors = np.c_[(cols * 255).astype(np.uint8), np.full(len(cols), 255, np.uint8)]
    p = os.path.join(PARTS, "LV_myocardium.ply"); myo.export(p); add("LV_myocardium", p, "patient (CT continuous-field iso-surface); vertex colours: septum = within 6 mm of the RV lumen, papillary = CT PM candidates", myo)
    np.save(os.path.join(PARTS, "LV_myocardium_vertex_labels.npy"), lab)
    for nm, src, prov in (("mitral_valve", os.path.join(BO, "mitral_valve.stl"), "parametric leaflets fitted to the patient's annulus, 1.2 mm solid"), ("aortic_valve", os.path.join(BO, "aortic_valve.stl"), "parametric, 1.2 mm solid"), ("chordae", os.path.join(FA, "chordae_v5_CT_hires.stl"), "parametric routes from the CT papillary tips"),
                          ("tricuspid_valve", os.path.join(RV_DIR, "tricuspid_valve_parametric.stl"), "parametric 3 leaflets on the patient's RV-RA annulus (step 27), 1.0 mm"), ("pulmonary_valve", os.path.join(RV_DIR, "pulmonary_valve_parametric.stl"), "parametric 3 cusps on the patient's RV-PA annulus (step 27), 1.0 mm")):
        if os.path.exists(src):
            m = trimesh.load(src, process=False); p = os.path.join(PARTS, f"{nm}.stl"); m.export(p); add(nm, p, prov, m)
    # coronary systems
    cor = json.load(open(os.path.join(P["coronary"], "coronary.json")))
    for nm, names in (("coronary_LAD_system", ("LM", "LAD", "D")), ("coronary_LCx_system", ("LCx", "OM", "RI")), ("coronary_RCA_system", ("RCA", "PDA", "PLV", "RV-br"))):
        m = tube_from_centrelines(cor, names)
        if m is None: continue
        p = os.path.join(PARTS, f"{nm}.stl"); m.export(p); add(nm, p, f"patient centrelines {names}, tubes >= 2 mm for printing", m); print(f"  {nm}: {len(m.faces):,} f")
    json.dump(dict(case=P["case"], frame=G["frame"], parts=manifest, notes=["walls other than the LV are synthetic-thickness shells around patient lumens", "tricuspid / pulmonary valves are parametric (annulus fitted, leaflets literature-shaped), no right-sided chordae", "IVC absent when unenhanced; aortic arch absent when outside the FOV"]), open(man_p, "w"), indent=1)
    print(f"manifest: {len(manifest)} parts  ({time.time()-t0:.0f}s)"); return "ok"


def colour_by_part(mesh, manifest):
    pts, cols = [], []
    for e in manifest:
        m = trimesh.load(os.path.join(OUT, e["file"]), process=False)
        if e["name"] == "LV_myocardium":
            vc = np.asarray(m.visual.vertex_colors)[:, :3] / 255.0; idx = np.random.default_rng(0).choice(len(m.vertices), size=min(60000, len(m.vertices)), replace=False)
            pts.append(m.vertices[idx]); cols.append(vc[idx]); continue
        s, _ = trimesh.sample.sample_surface(m, min(30000, max(2000, len(m.faces) // 4)), seed=0); pts.append(s); cols.append(np.tile(e["colour_rgb"], (len(s), 1)))
    kd = cKDTree(np.concatenate(pts)); allc = np.concatenate(cols)
    _, j = kd.query(mesh.triangles_center); return allc[j]


def polylines(L, gap=2.0):
    """split a chained outline wherever consecutive points jump (chaining through a pinch point) and close
    only the pieces whose ends really meet -- otherwise a long chord is drawn straight across the section."""
    out = []
    for q in np.split(L, np.where(np.linalg.norm(np.diff(L, axis=0), axis=1) > gap)[0] + 1):
        if len(q) >= 2: out.append(np.vstack([q, q[:1]]) if np.linalg.norm(q[0] - q[-1]) <= gap else q)
    return out


def chamber_marks(origin, n, B, band=9.0):
    """centroid of each chamber's voxels WITHIN `band` mm of the cut plane, in plane coordinates (for labels)."""
    if not os.path.exists(EXT): return []
    z = np.load(EXT); L = z["L"].astype(np.int16); A2 = z["affine"]; out = []
    NAMES = {500: "LV", 600: "RV", 420: "LA", 550: "RA", 820: "Ao", 850: "PA", 902: "SVC"}
    for k, nm in NAMES.items():
        idx = np.argwhere(L == k)
        if len(idx) < 200: continue
        W = trimesh.transform_points(idx[::7].astype(float), A2) + np.asarray(G["T"])[:3, 3]
        sel = W[np.abs((W - origin) @ n) <= band]
        if len(sel) < 30: continue
        out.append((nm, ((sel.mean(0) - origin) @ B).tolist()))
    del L; return out


def stage_render():
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection, LineCollection; from matplotlib.patches import Patch
    manifest = json.load(open(os.path.join(OUT, "parts_manifest.json")))["parts"]
    origin, n, apex, mv, tv = cut_plane(); axis = unit(np.array(G["axis"]))
    fig = plt.figure(figsize=(26, 10.5)); axes = [fig.add_subplot(1, 3, i + 1) for i in range(3)]
    sec = None
    for ax, tag, view in ((axes[0], "A", n), (axes[1], "B", -n)):
        h = trimesh.load(os.path.join(OUT, f"whole_heart_hollow_v2_4ch_{tag}.stl"), process=False)
        cap = cap_mask(h, origin, n)
        if len(h.faces) > 500000:                                          # decimate the NON-cap part only: keep the section crisp
            body = trimesh.Trimesh(h.vertices, h.faces[~cap], process=True).simplify_quadric_decimation(face_count=500000 - int(cap.sum()))
            capm = trimesh.Trimesh(h.vertices, h.faces[cap], process=True)
            h = trimesh.util.concatenate([body, capm]); cap = np.r_[np.zeros(len(body.faces), bool), np.ones(len(capm.faces), bool)]
        fc = colour_by_part(h, manifest)
        ply = h.copy(); ply.visual.face_colors = np.c_[(fc * 255).astype(np.uint8), np.full(len(fc), 255, np.uint8)]; ply.export(os.path.join(OUT, f"whole_heart_hollow_v2_4ch_{tag}_anatomy.ply"))
        tri, nrm = h.triangles, h.face_normals
        keep = (nrm @ (-view) > 0.03) | cap                                # strict back-face culling; the cap always faces the camera
        light = unit(-view + 0.35 * np.cross(-view, axis)); lam = np.clip(np.abs(nrm[keep] @ light), 0, 1) * 0.62 + 0.28
        col = fc[keep] * lam[:, None]
        cp = cap[keep]; col[cp] = fc[keep][cp] * 0.82 + 0.18               # cut face: flat, slightly lifted -> reads as a polished section
        u, v = plane_basis(n); v = -v if tag == "A" else v                 # u x v = -view, so the image is not mirrored
        if abs(u @ axis) > abs(v @ axis): u, v = v, -u                     # put the long axis roughly vertical
        if (apex - origin) @ v > 0: u, v = -u, -v                          # apex down
        Pp = (tri[keep] - origin) @ np.c_[u, v]; depth = ((tri[keep] - origin) @ view).mean(1); order = np.argsort(-depth)
        ax.add_collection(PolyCollection(Pp[order], facecolors=np.c_[col[order], np.ones(len(order))], edgecolors=np.c_[col[order], np.ones(len(order))], linewidths=0.45, antialiased=False))
        lp = os.path.join(OUT, f"section_loops_{tag}.npz"); loops = [np.asarray(q) for q in np.load(lp).values()] if os.path.exists(lp) else []
        segs = [q for L in loops if len(L) >= 3 for q in polylines(np.c_[(L - origin) @ u, (L - origin) @ v])]
        ax.add_collection(LineCollection(segs, colors="black", linewidths=0.75, zorder=5))
        lo, hi = Pp.reshape(-1, 2).min(0) - 5, Pp.reshape(-1, 2).max(0) + 5; ax.set_xlim(lo[0], hi[0]); ax.set_ylim(lo[1], hi[1]); ax.set_aspect("equal"); ax.set_axis_off()
        ax.set_title(f"half {tag} — looking into the four-chamber cut\n(cut face outlined; {len(h.faces):,} faces)", fontsize=12)
        if tag == "A": sec = (Pp[cp], fc[keep][cp], segs, u, v)
    # ---- panel 3: the section itself, face on ----
    ax = axes[2]; Pc, fcc, segs, u, v = sec
    ax.add_collection(PolyCollection(Pc, facecolors=np.c_[fcc, np.ones(len(fcc))], edgecolors=np.c_[fcc * 0.88, np.ones(len(fcc))], linewidths=0.25, antialiased=True))
    ax.add_collection(LineCollection(segs, colors="black", linewidths=1.0, zorder=5))
    for nm, (x, y) in chamber_marks(origin, n, np.c_[u, v]):
        ax.text(x, y, nm, fontsize=13, weight="bold", ha="center", va="center", zorder=6, color="black",
                bbox=dict(boxstyle="round,pad=0.18", fc="white", ec="0.4", alpha=0.75, lw=0.5))
    lo, hi = Pc.reshape(-1, 2).min(0) - 5, Pc.reshape(-1, 2).max(0) + 5; ax.set_xlim(lo[0], hi[0]); ax.set_ylim(lo[1], hi[1]); ax.set_aspect("equal"); ax.set_axis_off()
    ax.set_title(f"the cut face alone — four-chamber section\n(apex–mitral–tricuspid plane, {len(Pc):,} triangles)", fontsize=12)
    handles = [Patch(color=COL[k], label=k) for k in COL if any(e["name"] == k for e in manifest) or k in ("LV_septum", "LV_papillary")]
    fig.legend(handles=handles, loc="lower center", fontsize=9, ncol=9, framealpha=0.9, bbox_to_anchor=(0.5, 0.005))
    plt.suptitle(f"case {P['case']} — hollow whole heart v2 (no plate, open mitral/aortic orifices) — anatomical segmentation", fontsize=14)
    plt.tight_layout(rect=(0, 0.075, 1, 0.95)); plt.savefig(os.path.join(OUT, "whole_heart_hollow_v2_anatomy_render.png"), dpi=85); print(f"render done ({time.time()-t0:.0f}s)")


def main():
    if stage in ("lv", "all"): print("lv:", stage_lv())
    if stage in ("hollow", "all") and time.time() - t0 < 120: print("hollow:", stage_hollow())
    if stage in ("union", "all") and time.time() - t0 < 100 and os.path.exists(os.path.join(OUT, "hollow_shell_v2.stl")) and os.path.exists(os.path.join(BO, "LV_v6_noplate.stl")): print("union:", stage_union())
    if stage in ("cut", "all") and time.time() - t0 < 110 and os.path.exists(os.path.join(OUT, "whole_heart_hollow_v2.stl")): print("cut:", stage_cut())
    if stage in ("recap", "all") and time.time() - t0 < 130 and os.path.exists(os.path.join(OUT, "cut_v2_info.json")): print("recap:", stage_recap())
    if stage in ("anatomy", "all") and time.time() - t0 < 100 and os.path.exists(os.path.join(OUT, "hollow_v2_owner.npz")): print("anatomy:", stage_anatomy())
    done = os.path.exists(os.path.join(OUT, "whole_heart_hollow_v2_4ch_B.stl")) and os.path.exists(os.path.join(OUT, "parts_manifest.json"))
    if stage in ("render", "all") and done and time.time() - t0 < 100: stage_render(); print("DONE ->", OUT)
    elif not done: print("not finished -- rerun (stages are cached)")


if __name__ == "__main__":
    main()
