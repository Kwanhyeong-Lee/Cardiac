# -*- coding: utf-8 -*-
"""Consistent cross-section figures of the hollow-ventricle solids (v2, v3).

Every panel uses ONE 2-D frame for all meshes (Path3D.to_planar otherwise centres each
section on its own centroid, which made the first figures misleading).
    usage: PYTHONPATH=/tmp/pylibs python3 render_sections.py [v2|v3]
"""
import json, os, sys, warnings
import numpy as np, trimesh
warnings.filterwarnings("ignore")
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__)); BO = os.path.join(HERE, "BLENDER_OUT")
d = json.load(open(os.path.join(HERE, "valve_refit.json")))
AXIS = np.array(d["lv_geometry"]["axis_base_to_apex"])
MV_C = np.array(d["design"]["mv_centre_mm"]); AV_C = np.array(d["design"]["av_centre_mm"])
FILES = {"v2": "hollow_ventricle_v2_fixed_valves.stl", "v3": "hollow_ventricle_v3_IDEALISED_subvalvular.stl", "v4": "hollow_ventricle_v4_CT.stl"}


def frame(origin, ex, ey):
    """4x4 mapping 3-D -> (x along ex, y along ey, z along ex x ey) with `origin` at (0,0)."""
    ez = np.cross(ex, ey); R = np.vstack([ex, ey, ez])
    T = np.eye(4); T[:3, :3] = R; T[:3, 3] = -R @ origin; return T


def panel(axh, meshes, origin, ex, ey, title, xlabel, ylabel):
    T2 = frame(origin, ex, ey); normal = np.cross(ex, ey)
    for m, col, lw, fill in meshes:
        s = m.section(plane_origin=origin, plane_normal=normal)
        if s is None: continue
        p2 = s.to_planar(to_2D=T2, check=False)[0]
        for e in p2.discrete:
            (axh.fill if fill else axh.plot)(e[:, 0], e[:, 1], color=col, lw=lw, alpha=0.35 if fill else 1)
    axh.axhline(0, color="k", lw=0.4, ls=":"); axh.axvline(0, color="k", lw=0.4, ls=":")
    axh.set_aspect("equal"); axh.set_title(title, fontsize=9); axh.set_xlabel(xlabel, fontsize=8); axh.set_ylabel(ylabel, fontsize=8)


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "v2"
    solid = trimesh.load(os.path.join(BO, FILES[which]), process=False)
    bp = trimesh.load(os.path.join(HERE, "PRINT", "frame_A_patient", "lv_surface.stl"), process=True)
    apex_depth = float(((bp.vertices - MV_C) @ AXIS).max())
    A_dir = AV_C - MV_C; A_dir -= (A_dir @ AXIS) * AXIS; A_dir /= np.linalg.norm(A_dir)
    P_dir = np.cross(AXIS, A_dir)
    fig, ax = plt.subplots(1, 4, figsize=(21, 5.5))
    M = [(solid, "tab:red", 0.6, True), (bp, "tab:blue", 0.8, False)]
    panel(ax[0], M, MV_C, A_dir, -AXIS, f"{which}: long axis through MV & AV (red = printed solid, blue = blood pool)",
          "toward aortic valve [mm]", "basal ^  (0 = mitral annulus plane) [mm]")
    panel(ax[1], M, MV_C + 1.0 * AXIS, A_dir, P_dir, "1 mm apical of mitral plane (plate with D-shaped mitral + round aortic orifice)",
          "toward aortic valve [mm]", "[mm]")
    panel(ax[2], M, MV_C + 0.30 * apex_depth * AXIS, A_dir, P_dir, "short axis, depth 0.30 (leaflets hanging)", "toward aortic valve [mm]", "[mm]")
    panel(ax[3], M, MV_C + 0.50 * apex_depth * AXIS, A_dir, P_dir, "short axis, depth 0.50", "toward aortic valve [mm]", "[mm]")
    out = os.path.join(BO, f"hollow_{which}_sections.png")
    plt.tight_layout(); plt.savefig(out, dpi=80); print("saved", out)


if __name__ == "__main__":
    main()
