# -*- coding: utf-8 -*-
"""CFD domain = the physical phantom cavity, split into inlet / outlet / LV patches.

The lost-core core (PHANTOM/core_LV_with_ports.stl) IS the fluid domain of the silicone
phantom: blood pool + mitral port + aortic port. Exporting it with the two port end-caps as
named patches gives an OpenFOAM/snappyHexMesh geometry whose boundary is identical to the
bench model -- simulation and experiment then share one geometry, which is what makes the
phantom a validation instrument for lv_cfd_* and for the pH-PINN surrogate.

Patch names follow lv_cfd_patient (0/U, 0/p): inlet (mitral cap), outlet (aortic cap),
LV (everything else, wall). lv_cfd_patient built its inlet by box-selecting part of a
blockMesh face (8.23 cm2 for a 2.8 cm2 valve, velocity scaled by 0.34); here the inlet is a
true 2.84 cm2 disc and the outlet a 1.96 cm2 disc.

Outputs (PHANTOM/cfd/): LV_phantom_mm.stl, LV_phantom_m.stl (multi-solid ASCII STL),
    inlet.stl / outlet.stl / LV.stl in metres (separate files, if preferred),
    cfd_domain.json (patch areas, centres, normals, bounds in m -- frame A, not the
    lv_cfd_patient frame), snappyHexMeshDict_geometry.txt (snippet).
"""
import json, os
import numpy as np, trimesh
HERE = os.path.dirname(os.path.abspath(__file__)); PH = os.path.join(HERE, "PHANTOM"); OUT = os.path.join(PH, "cfd"); os.makedirs(OUT, exist_ok=True)
d = json.load(open(os.path.join(HERE, "valve_refit.json")))
AXIS = np.array(d["lv_geometry"]["axis_base_to_apex"]); MV_C = np.array(d["design"]["mv_centre_mm"]); AV_C = np.array(d["design"]["av_centre_mm"])
ph = json.load(open(os.path.join(PH, "phantom_design.json")))["constants"]
PORT_LEN, R_MV, R_AV = ph["PORT_LEN"], ph["PORT_R_MV"], ph["PORT_R_AV"]


def write_multi_stl(path, named, scale=1.0):
    with open(path, "w") as f:
        for name, m in named:
            f.write(f"solid {name}\n")
            V = m.vertices * scale
            for tri, n in zip(m.faces, m.face_normals):
                f.write(f"  facet normal {n[0]:.6e} {n[1]:.6e} {n[2]:.6e}\n    outer loop\n")
                for i in tri:
                    v = V[i]; f.write(f"      vertex {v[0]:.6e} {v[1]:.6e} {v[2]:.6e}\n")
                f.write("    endloop\n  endfacet\n")
            f.write(f"endsolid {name}\n")


def main():
    core = trimesh.load(os.path.join(PH, "core_LV_with_ports.stl"), process=True)
    basal = -AXIS
    n = core.face_normals; c = core.triangles_center
    cap = n @ basal > 0.99
    def port_cap(C, r):
        along = (c - C) @ basal; inpl = np.linalg.norm((c - C) - np.outer(along, basal), axis=1)
        return cap & (np.abs(along - PORT_LEN) < 0.5) & (inpl < r + 0.5)
    inlet = port_cap(MV_C, R_MV); outlet = port_cap(AV_C, R_AV); wall = ~(inlet | outlet)
    sub = lambda mask: core.submesh([np.where(mask)[0]], append=True)
    parts = [("inlet", sub(inlet)), ("outlet", sub(outlet)), ("LV", sub(wall))]
    a_in, a_out = parts[0][1].area / 100, parts[1][1].area / 100
    print(f"inlet {inlet.sum()} faces {a_in:.2f} cm2 (disc {np.pi*R_MV**2/100:.2f})   outlet {outlet.sum()} faces {a_out:.2f} cm2 (disc {np.pi*R_AV**2/100:.2f})   wall {wall.sum()} faces")
    assert abs(a_in - np.pi * R_MV ** 2 / 100) < 0.1 and abs(a_out - np.pi * R_AV ** 2 / 100) < 0.1, "cap selection wrong"
    write_multi_stl(os.path.join(OUT, "LV_phantom_mm.stl"), parts, 1.0)
    write_multi_stl(os.path.join(OUT, "LV_phantom_m.stl"), parts, 1e-3)
    for name, m in parts:
        write_multi_stl(os.path.join(OUT, f"{name}.stl"), [(name, m)], 1e-3)
    # re-read the multi-solid file: total area and closure must match the core
    back = trimesh.load(os.path.join(OUT, "LV_phantom_mm.stl"), process=False, force="mesh")
    back.merge_vertices(merge_tex=True, merge_norm=True)      # STL per-face normals block the default merge
    open_edges = int((np.unique(back.edges_sorted, axis=0, return_counts=True)[1] == 1).sum())
    print(f"re-read: {len(back.faces):,} faces, watertight {back.is_watertight}, open edges {open_edges}, area diff {abs(back.area-core.area):.3f} mm2")
    assert back.is_watertight and open_edges == 0, "patch split broke closure"
    info = dict(frame="frame A (mm origin at LV blood-pool centroid, NOT the lv_cfd_patient frame); STL in metres",
                patches=dict(inlet=dict(centre_m=(MV_C + PORT_LEN * basal) .tolist(), area_cm2=round(a_in, 3), radius_mm=R_MV,
                                        flow_direction_into_domain=(-basal).tolist(), faces=int(inlet.sum())),
                             outlet=dict(centre_m=(AV_C + PORT_LEN * basal).tolist(), area_cm2=round(a_out, 3), radius_mm=R_AV,
                                         outward_normal=basal.tolist(), faces=int(outlet.sum())),
                             LV=dict(type="wall", faces=int(wall.sum()), area_cm2=round(parts[2][1].area / 100, 1))),
                bounds_m=(core.bounds * 1e-3).tolist(), volume_mL=round(abs(core.volume) / 1000, 2),
                note=["cavity is PM-inclusive: the segmentation lumps papillary muscles into the blood pool (extract_pm.py)",
                      "no leaflets in the domain; on the bench use one-way valves in the inlet/outlet tubing",
                      "silicone wall is compliant; the CFD wall is rigid -- either use a stiff silicone (Sylgard 184) or model FSI",
                      "same geometry as the physical phantom: validation compares like with like"])
    for p in ("inlet", "outlet"):
        info["patches"][p]["centre_m"] = [round(x * 1e-3, 5) for x in info["patches"][p]["centre_m"]]
    json.dump(info, open(os.path.join(OUT, "cfd_domain.json"), "w"), indent=1)
    snippet = """// snappyHexMeshDict geometry block for the phantom domain (metres). Regions come from the
// solid names in LV_phantom_m.stl, so inlet / outlet / LV become separate patches directly --
// no topoSet/createPatch box hack needed.
geometry
{
    LV_phantom_m.stl
    {
        type triSurfaceMesh;
        name phantom;
        regions
        {
            inlet  { name inlet;  }
            outlet { name outlet; }
            LV     { name LV;     }
        }
    }
}
castellatedMeshControls
{
    refinementSurfaces
    {
        phantom
        {
            level (2 3);
            regions
            {
                inlet  { level (3 3); patchInfo { type patch; } }
                outlet { level (3 3); patchInfo { type patch; } }
                LV     { level (2 3); patchInfo { type wall;  } }
            }
        }
    }
    // locationInMesh: any point inside the cavity, e.g. the blood-pool centroid (frame A origin)
    locationInMesh (0 0 0);
}
"""
    open(os.path.join(OUT, "snappyHexMeshDict_geometry.txt"), "w").write(snippet)
    print("->", OUT)


if __name__ == "__main__":
    main()
