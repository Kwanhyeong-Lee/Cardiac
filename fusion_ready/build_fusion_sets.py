# -*- coding: utf-8 -*-
"""Produce the two Fusion-ready mesh sets from the normalised frames, with verification.

    PRINT/   <= 40,000 faces per part. Watertight where the source topology allows it.
             For 3D printing and for Fusion's Mesh workspace (display, section, split).
    CAD/     <= 10,000 faces per part. The range Fusion's Convert Mesh (mesh -> BRep) can
             actually handle. For boolean/shell/hole work around the anatomy.

Both sets keep the frame's coordinates exactly (no per-part centring), so PRINT and CAD
overlay each other and the frame_A parts overlay each other.

Verification per part, written to VERIFY.json:
    - face count before/after
    - surface area and (if watertight) volume retention, %
    - one-sided nearest-point distance from the ORIGINAL vertices to the decimated surface:
      mean / p95 / max in mm. This is the Hausdorff-style error a printer or a CAD boolean
      will actually see.
    - watertight before/after, component count

Non-watertight sources are reported, not forced closed. The parametric valves are thin
open leaflet sheets by construction; closing them would be inventing geometry.

Usage:  PYTHONPATH=/tmp/pylibs python3 build_fusion_sets.py <frame_dir> [<frame_dir> ...]
"""
import json, os, sys, time, warnings
import numpy as np, trimesh
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
TARGETS = {"PRINT": 40_000, "CAD": 10_000}
VER = os.path.join(HERE, "VERIFY.json")


def load_verify():
    return json.load(open(VER)) if os.path.exists(VER) else {}


def nearest_dist(src_pts, mesh):
    """One-sided distance original-vertices -> decimated surface, mm."""
    q = trimesh.proximity.ProximityQuery(mesh)
    d = np.abs(q.signed_distance(src_pts)) if mesh.is_watertight else \
        np.linalg.norm(src_pts - q.on_surface(src_pts)[0], axis=1)
    return dict(mean=round(float(d.mean()), 4), p95=round(float(np.percentile(d, 95)), 4),
                max=round(float(d.max()), 4))


def process(frame_dir):
    ver = load_verify()
    fname = os.path.basename(frame_dir.rstrip("/\\"))
    ver.setdefault(fname, {})
    for stl in sorted(f for f in os.listdir(frame_dir) if f.endswith(".stl")):
        name = stl[:-4]
        t0 = time.time()
        src = trimesh.load(os.path.join(frame_dir, stl), process=True)
        src_pts = src.vertices[:: max(1, len(src.vertices) // 20_000)]
        entry = {"source": dict(faces=int(len(src.faces)), watertight=bool(src.is_watertight),
                                components=int(len(src.split(only_watertight=False))),
                                area_cm2=round(float(src.area) / 100, 3),
                                volume_mL=round(float(abs(src.volume)) / 1000, 3)
                                if src.is_watertight else None)}
        for setname, cap in TARGETS.items():
            outdir = os.path.join(HERE, setname, fname)
            os.makedirs(outdir, exist_ok=True)
            if len(src.faces) <= cap:
                m = src.copy()
            else:
                m = src.simplify_quadric_decimation(face_count=cap)
            # light repair that never invents surface: drop degenerate/duplicate faces,
            # merge coincident vertices, fix winding
            m.update_faces(m.nondegenerate_faces()); m.update_faces(m.unique_faces())
            m.merge_vertices(); m.remove_unreferenced_vertices()
            trimesh.repair.fix_normals(m)
            if src.is_watertight and not m.is_watertight:
                # decimation can leave a few non-manifold edges that fill_holes chases in
                # circles (seen on the LV: 4 broken faces at every target count). MeshFix
                # closes them properly. Only applied when the source WAS closed -- never
                # used to invent a closed surface from an open one.
                import pymeshfix
                mf = pymeshfix.MeshFix(np.ascontiguousarray(m.vertices, dtype=np.float64),
                                       np.ascontiguousarray(m.faces, dtype=np.int32))
                mf.repair(joincomp=True, remove_smallest_components=True)
                m = trimesh.Trimesh(mf.points, mf.faces, process=True)
                trimesh.repair.fix_normals(m)
            m.export(os.path.join(outdir, stl))
            d = nearest_dist(src_pts, m)
            e = dict(faces=int(len(m.faces)),
                     reduction_pct=round(100 * (1 - len(m.faces) / len(src.faces)), 1),
                     watertight=bool(m.is_watertight),
                     components=int(len(m.split(only_watertight=False))),
                     area_retained_pct=round(100 * float(m.area) / float(src.area), 2),
                     volume_retained_pct=round(100 * abs(m.volume) / abs(src.volume), 2)
                     if (src.is_watertight and m.is_watertight) else None,
                     dist_mm=d)
            entry[setname] = e
            print(f"  {fname}/{name:<22} {setname:<5} {len(src.faces):>8,} -> {len(m.faces):>7,}"
                  f"  WT {('Y' if src.is_watertight else 'N')}->{('Y' if m.is_watertight else 'N')}"
                  f"  area {e['area_retained_pct']:6.2f}%"
                  f"  dist mean {d['mean']:.3f} p95 {d['p95']:.3f} max {d['max']:.3f} mm",
                  flush=True)
        entry["seconds"] = round(time.time() - t0, 1)
        ver[fname][name] = entry
        json.dump(ver, open(VER, "w"), indent=1)      # incremental
    return ver


if __name__ == "__main__":
    for fd in sys.argv[1:]:
        print(f"\n[{fd}]")
        process(os.path.join(HERE, fd) if not os.path.isabs(fd) else fd)
