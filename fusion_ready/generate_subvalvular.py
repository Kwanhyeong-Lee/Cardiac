# -*- coding: utf-8 -*-
"""IDEALISED subvalvular apparatus: two papillary muscles + chordae, fused to the hollow ventricle.

STATUS OF THIS PART -- READ FIRST. The patient's papillary muscles are NOT in the myocardium
label (extract_pm.py: myocardium inside the smoothed cavity is a single 0.6 mm voxel film,
nothing thicker), i.e. the segmentation put them in the blood pool, and frame B's muscles
are another heart's (pm_registration.json). So the muscles and chordae built here are
PARAMETRIC, placed by textbook anatomy on this patient's LV -- the same standing as the
parametric valves. Every output carries IDEALISED in its name. Do not present them as the
patient's anatomy.

ANATOMY USED (short axis, "12 o'clock" = direction from mitral to aortic centre)
    papillary muscles   at ~+-120 deg from 12 o'clock, i.e. 30 deg posterior of the two
                        mitral commissures (+-90 deg); the muscle on the SEPTAL side (toward
                        the RV centroid) is the posteromedial one, the other anterolateral
    base                on the endocardium at DEPTH_BASE of the base->apex span, sunk EMBED
                        into the wall so the union with the myocardium is solid
    body                tapered revolve, length LEN, base diameter DIAM, rounded tip,
                        pointing at its commissure
    chordae             N_CH tubes of radius CH_R from each tip to free-edge points of BOTH
                        leaflets within +-CH_SPAN deg of the muscle, extended CH_OVER into
                        the leaflet solid; any tube that would leave the cavity is dropped

Fusion: manifold3d union with BLENDER_OUT/hollow_ventricle_v2_fixed_valves.stl.
Outputs: frame_A_patient/pm_{anterolateral,posteromedial}_IDEALISED.stl,
         frame_A_patient/chordae_IDEALISED.stl,
         BLENDER_OUT/hollow_ventricle_v3_IDEALISED_subvalvular.stl, subvalvular.json,
         subvalvular_sections.png
"""
import json, os, time, warnings
import numpy as np, trimesh
from scipy.ndimage import map_coordinates
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FA = os.path.join(HERE, "frame_A_patient"); BO = os.path.join(HERE, "BLENDER_OUT")
d = json.load(open(os.path.join(HERE, "valve_refit.json")))
AXIS = np.array(d["lv_geometry"]["axis_base_to_apex"])
MV_C = np.array(d["design"]["mv_centre_mm"]); MV_R = float(d["design"]["mv_annulus_r_mm"])
AV_C = np.array(d["design"]["av_centre_mm"])

# ---- design constants (mm, deg) ----
PM_ANGLE = 120.0      # from the aortic direction, each side
DEPTH_BASE = 0.62     # fraction of base->apex span
LEN, DIAM, EMBED = 24.0, 11.0, 2.5
N_CH, CH_R, CH_SPAN, CH_OVER = 5, 1.0, 70.0, 1.2
FREE_EDGE_MIN = 8.0   # boundary vertices this far apical of the annulus plane count as free edge


def unit(v): return v / (np.linalg.norm(v) + 1e-12)


def short_axis(v):
    v = np.asarray(v, float); v = v - (v @ AXIS) * AXIS; return unit(v)


def tapered_pm(length, diam):
    """Revolve profile: flat base (embedded), slight taper, rounded tip. Axis = +z, base at z=0."""
    r0, r1 = diam / 2, 0.55 * diam / 2
    prof = [[0.0, 0.0], [r0, 0.0], [r0 * 0.98, 0.25 * length], [r1, length - r1]]
    for t in np.linspace(0, np.pi / 2, 10)[1:]:
        prof.append([r1 * np.cos(t), length - r1 + r1 * np.sin(t)])
    return trimesh.creation.revolve(np.array(prof), sections=64)


def place(mesh, origin, direction):
    T = trimesh.geometry.align_vectors([0, 0, 1], unit(direction)); T[:3, 3] = origin
    m = mesh.copy(); m.apply_transform(T); return m


def tube(p, q, r):
    v = q - p; L = np.linalg.norm(v)
    c = trimesh.creation.cylinder(radius=r, height=L, sections=24)
    T = trimesh.geometry.align_vectors([0, 0, 1], v / L); T[:3, 3] = (p + q) / 2
    c.apply_transform(T); return c


def main():
    t0 = time.time()
    bp = trimesh.load(os.path.join(HERE, "PRINT", "frame_A_patient", "lv_surface.stl"), process=True)
    mv = trimesh.load(os.path.join(FA, "mitral_valve.stl"), process=True)          # zero-thickness sheet
    hollow = trimesh.load(os.path.join(BO, "hollow_ventricle_v2_fixed_valves.stl"), process=True)   # process=True merges STL duplicate vertices; without it the mesh is not a volume
    apex_depth = float(((bp.vertices - MV_C) @ AXIS).max())
    g = np.load(os.path.join(HERE, "lv_sdf_grid.npz")); SG, ORG, H = g["sdf"], g["origin"], float(g["spacing"])
    sdf = lambda P: map_coordinates(SG, ((np.atleast_2d(P) - ORG) / H).T, order=1, mode="nearest")

    # short-axis frame and septal side
    A_dir = short_axis(AV_C - MV_C); P_dir = unit(np.cross(AXIS, A_dir))
    ft = np.array(json.load(open(os.path.join(BO, "frame_transform.json")))["transform_cardiac_meshes_to_frameA"])
    rv_c = trimesh.transform_points(trimesh.load(os.path.join(ROOT, "cardiac_meshes", "RV_case1009.stl"), process=False).centroid[None], ft)[0]
    S = short_axis(rv_c - MV_C)
    sgn_pm = 1.0 if (P_dir @ S) > 0 else -1.0
    ang = {"posteromedial": sgn_pm * PM_ANGLE, "anterolateral": -sgn_pm * PM_ANGLE}
    comm = {k: MV_C + MV_R * (np.cos(np.radians(np.sign(a) * 90)) * A_dir + np.sin(np.radians(np.sign(a) * 90)) * P_dir) for k, a in ang.items()}
    u = lambda deg: np.cos(np.radians(deg)) * A_dir + np.sin(np.radians(deg)) * P_dir

    # ---- free-edge points of the mitral leaflets ----
    edges = mv.edges_sorted; uniq, cnt = np.unique(edges, axis=0, return_counts=True)
    bverts = np.unique(uniq[cnt == 1])
    B = mv.vertices[bverts]; depth = (B - MV_C) @ AXIS
    free = B[depth > FREE_EDGE_MIN]
    free_ang = np.degrees(np.arctan2((free - MV_C) @ P_dir, (free - MV_C) @ A_dir))
    print(f"mitral boundary verts {len(B)}, free-edge (>{FREE_EDGE_MIN} mm apical) {len(free)}, depth max {depth.max():.1f} mm")

    rep = dict(constants=dict(PM_ANGLE=PM_ANGLE, DEPTH_BASE=DEPTH_BASE, LEN=LEN, DIAM=DIAM, EMBED=EMBED,
                              N_CH=N_CH, CH_R=CH_R, CH_SPAN=CH_SPAN, CH_OVER=CH_OVER),
               septal_dir=[round(float(x), 3) for x in S], sgn_posteromedial=sgn_pm, muscles={}, chordae=[])
    parts = []; chordae = []
    for name, a in ang.items():
        Q = MV_C + DEPTH_BASE * apex_depth * AXIS                     # axis point at base depth
        loc, _, _ = bp.ray.intersects_location([Q], [u(a)])
        hit = loc[np.argmax(np.linalg.norm(loc - Q, axis=1))]         # farthest hit = endocardium on that side
        base = hit + EMBED * u(a)                                     # sunk into the wall
        direction = unit(unit(comm[name] - base) * 0.6 + (-AXIS) * 0.4)   # toward commissure, mostly basal
        tip = base + LEN * direction
        # tip must sit well inside the cavity; if not, steer toward the axis
        for _ in range(6):
            if sdf(tip)[0] > DIAM / 2 + 1.0: break
            direction = unit(direction + 0.25 * unit(Q - base)); tip = base + LEN * direction
        pm = place(tapered_pm(LEN, DIAM), base, direction)
        parts.append(pm); pm.export(os.path.join(FA, f"pm_{name}_IDEALISED.stl"))
        # chordae to free-edge points within CH_SPAN of this muscle's angle, spread evenly
        da = np.abs(((free_ang - a + 180) % 360) - 180)
        cand = free[da <= CH_SPAN]; cand_ang = free_ang[da <= CH_SPAN]
        order = np.argsort(cand_ang); cand, cand_ang = cand[order], cand_ang[order]
        pick = cand[np.linspace(0, len(cand) - 1, N_CH).round().astype(int)] if len(cand) >= N_CH else cand
        kept = 0
        for k, tgt in enumerate(pick):
            start = tip - 0.35 * DIAM * direction + 0.3 * DIAM * unit(np.cross(direction, tgt - tip)) * (k - (len(pick) - 1) / 2) / max(1, len(pick) - 1)
            end = tgt + CH_OVER * unit(tgt - start)
            # containment: every point along the tube (bar the last 2.5 mm) inside the cavity
            samp = start + np.outer(np.linspace(0, 1, 30), end - start)
            L = np.linalg.norm(end - start); inside = sdf(samp) > 0.3
            n_check = int(30 * (1 - 2.5 / L))
            if inside[:n_check].all():
                chordae.append(tube(start, end, CH_R)); kept += 1
                rep["chordae"].append(dict(muscle=name, length_mm=round(float(L), 1), target=[round(float(x), 1) for x in tgt]))
        rep["muscles"][name] = dict(angle_from_aortic_deg=a, base_mm=[round(float(x), 1) for x in base],
                                    tip_mm=[round(float(x), 1) for x in tip], tip_sdf_mm=round(float(sdf(tip)[0]), 1),
                                    tip_depth_frac=round(float((tip - MV_C) @ AXIS) / apex_depth, 2),
                                    free_edge_candidates=int(len(cand)), chordae_kept=kept, chordae_dropped=int(len(pick) - kept))
        print(f"{name:<14} angle {a:+.0f}  base depth {DEPTH_BASE:.2f}  tip depth {rep['muscles'][name]['tip_depth_frac']:.2f}  "
              f"tip sdf {rep['muscles'][name]['tip_sdf_mm']} mm  chordae {kept}/{len(pick)}")
    ch = trimesh.util.concatenate(chordae); ch.export(os.path.join(FA, "chordae_IDEALISED.stl"))

    # ---- fuse ----
    v3 = trimesh.boolean.union([hollow] + parts + chordae, engine="manifold")
    comps = v3.split(only_watertight=False)
    print(f"union {len(v3.faces):,} faces  watertight {v3.is_watertight}  components {len(comps)}  "
          f"volume {abs(v3.volume)/1000:.2f} mL (v2 {abs(hollow.volume)/1000:.2f})  {time.time()-t0:.0f}s")
    v3.export(os.path.join(BO, "hollow_ventricle_v3_IDEALISED_subvalvular.stl"))
    # cavity still open? orifices?  -- tested on the ADDED parts only: v2 already passed both
    # tests (hollow_v2_check.json) and contains() on the 790k-face union is an OOM in this
    # sandbox. Blockage = volume the new parts take out of the cavity.
    # interior samples from the SDF grid, not trimesh.sample.volume_mesh (its ray-cast
    # contains() on the 40k-face pool is what blew the 3 GB sandbox twice)
    rng = np.random.default_rng(0)
    cand = rng.uniform(bp.bounds[0], bp.bounds[1], size=(60000, 3))
    pts = cand[sdf(cand) > 1.0][:6000]
    blocked = float(np.any([m.contains(pts) for m in parts + chordae], axis=0).mean())
    probe = lambda c, ax: bool(np.any([m.contains(np.array([c + t * ax for t in (-3, 0, 3)])).any() for m in parts + chordae]))
    rep["union"] = dict(faces=int(len(v3.faces)), watertight=bool(v3.is_watertight), components=len(comps),
                        volume_mL=round(abs(v3.volume) / 1000, 2), added_mL=round((abs(v3.volume) - abs(hollow.volume)) / 1000, 2),
                        cavity_blocked_frac=round(blocked, 4),
                        mitral_axis_blocked=probe(MV_C, AXIS), aortic_axis_blocked=probe(AV_C, AXIS))
    rep["verdict"] = ("OK" if v3.is_watertight and len(comps) == 1 and blocked < 0.08
                      and not rep["union"]["mitral_axis_blocked"] and not rep["union"]["aortic_axis_blocked"] else "CHECK")
    print("cavity blocked %.1f%%  mitral axis blocked %s  aortic axis blocked %s  -> %s" %
          (100 * blocked, rep["union"]["mitral_axis_blocked"], rep["union"]["aortic_axis_blocked"], rep["verdict"]))
    json.dump(rep, open(os.path.join(HERE, "subvalvular.json"), "w"), indent=1)

    # ---- figure ----
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 3, figsize=(16, 5.5))
    def draw(axh, origin, normal, title):
        # ONE 2-D frame per panel: to_planar() otherwise centres every section on its own
        # centroid, which drew the muscles in the middle of the cavity on the first attempt
        T2 = [None]
        def planar(s):
            if T2[0] is None:
                p2, to3 = s.to_planar(normal=normal); T2[0] = np.linalg.inv(to3); return p2
            return s.to_planar(to_2D=T2[0])[0]
        for m, col, lw in ((hollow, "0.55", 0.5), (bp, "tab:blue", 0.7)):
            s = m.section(plane_origin=origin, plane_normal=normal)
            if s is not None:
                for e in planar(s).discrete: axh.plot(e[:, 0], e[:, 1], color=col, lw=lw)
        for m in parts + chordae:
            s = m.section(plane_origin=origin, plane_normal=normal)
            if s is not None:
                for e in planar(s).discrete: axh.fill(e[:, 0], e[:, 1], color="tab:red", alpha=0.7)
        axh.set_aspect("equal"); axh.set_title(title, fontsize=9)
    draw(ax[0], MV_C + 0.5 * apex_depth * AXIS, AXIS, "short axis, mid-cavity (red = idealised PMs/chordae)")
    n_pm = unit(np.cross(AXIS, u(ang["posteromedial"])))
    draw(ax[1], MV_C, n_pm, "long axis through posteromedial PM")
    n_al = unit(np.cross(AXIS, u(ang["anterolateral"])))
    draw(ax[2], MV_C, n_al, "long axis through anterolateral PM")
    plt.tight_layout(); plt.savefig(os.path.join(HERE, "subvalvular_sections.png"), dpi=80)
    print(f"done {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
