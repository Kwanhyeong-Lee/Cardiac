# -*- coding: utf-8 -*-
"""Build lv_sdf_grid.npz: signed distance to the LV blood-pool surface on a regular grid
(positive INSIDE the cavity). Used by pm_register.py, generate_subvalvular.py,
build_hollow_v2.py for fast containment tests (trilinear interpolation, ~1e4x faster than
per-call mesh queries and, unlike trimesh's ray-cast contains(), memory-safe).
    2.5 mm spacing, 12 mm margin around the pool -> ~65k points, ~30 s on an 8k-face proxy.
"""
import os, time
import numpy as np, trimesh
HERE = os.path.dirname(os.path.abspath(__file__))
SPACING, MARGIN = 2.5, 12.0


def main():
    t0 = time.time()
    lv = trimesh.load(os.path.join(HERE, "PRINT", "frame_A_patient", "lv_surface.stl"), process=True)
    proxy = lv.simplify_quadric_decimation(face_count=8000)
    lo = lv.bounds[0] - MARGIN; hi = lv.bounds[1] + MARGIN
    axes = [np.arange(lo[i], hi[i] + SPACING, SPACING) for i in range(3)]
    G = np.stack(np.meshgrid(*axes, indexing="ij"), -1).reshape(-1, 3)
    q = trimesh.proximity.ProximityQuery(proxy)
    sd = np.concatenate([q.signed_distance(G[i:i + 5000]) for i in range(0, len(G), 5000)])
    sdf = sd.reshape(len(axes[0]), len(axes[1]), len(axes[2])).astype(np.float32)
    np.savez(os.path.join(HERE, "lv_sdf_grid.npz"), sdf=sdf, origin=lo.astype(np.float64), spacing=SPACING)
    print(f"grid {sdf.shape} = {sdf.size:,} pts, inside fraction {(sdf > 0).mean():.3f}, {time.time()-t0:.0f}s -> lv_sdf_grid.npz")


if __name__ == "__main__":
    main()
