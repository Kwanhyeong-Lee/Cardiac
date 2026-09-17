# -*- coding: utf-8 -*-
"""Stage 0 of the SimVascular roadmap: SV-ready surface models with face IDs, in centimetres.

SimVascular imports a closed surface (VTP) and needs its boundary split into named faces to
attach boundary conditions and, for FSI, to identify the fluid-solid interface. Three models:

  SV/fluid_phantom_cm.vtp      phantom fluid domain (blood pool + port stubs)
                               1 lumen_wall   2 inlet (mitral port cap)   3 outlet (aortic port cap)
                               -> stage 1: rigid-wall Navier-Stokes cross-check against OpenFOAM
  SV/fluid_cavity_cm.vtp       label-500 cavity (the smooth, papillary-inclusive cavity that LV
                               FSI/electromechanics models use by convention)
                               1 endocardium (shared with the solid)  2 mitral  3 aortic  4 base_wall
  SV/solid_myocardium_cm.vtp   label-205 wall
                               1 endocardium  2 epicardium  3 base
                               -> stages 2-4: passive inflation, active contraction, FSI

Face rules (frame A, mm): endocardium = faces whose centre lies within ENDO_TOL of the other
domain's surface; mitral/aortic = non-endocardial cavity faces within the annulus radius of the
respective valve axis; base = solid faces on the segmentation's basal cut (normal within 45 deg
of the basal direction, within BASE_DEPTH of the mitral plane). Everything else: epicardium /
base_wall. VTP is written by hand (XML PolyData, ASCII) -- no vtk dependency.

NOTE the two surfaces meet at the endocardium but are NOT the same triangulation; a conforming
fluid+solid volume mesh (needed by svMultiPhysics FSI) is stage 2 (multi-domain mesher from
the label image), see SIMVASCULAR_ROADMAP.md.
"""
import json, os, warnings
import numpy as np, trimesh
from trimesh.proximity import closest_point
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "SV"); os.makedirs(OUT, exist_ok=True)
d = json.load(open(os.path.join(HERE, "valve_refit.json")))
AXIS = np.array(d["lv_geometry"]["axis_base_to_apex"]); MV_C = np.array(d["design"]["mv_centre_mm"]); AV_C = np.array(d["design"]["av_centre_mm"])
MV_R, AV_R = float(d["design"]["mv_annulus_r_mm"]), float(d["design"]["av_annulus_r_mm"])
ph = json.load(open(os.path.join(HERE, "PHANTOM", "phantom_design.json")))["constants"]
ENDO_TOL, BASE_DEPTH, SOLID_FACES, PROXY_FACES, MM2CM = 1.0, 6.0, 80000, 25000, 0.1


def write_vtp(path, mesh, face_id, scale=MM2CM):
    V = mesh.vertices * scale; F = mesh.faces
    with open(path, "w") as f:
        f.write('<?xml version="1.0"?>\n<VTKFile type="PolyData" version="0.1" byte_order="LittleEndian">\n <PolyData>\n')
        f.write(f'  <Piece NumberOfPoints="{len(V)}" NumberOfVerts="0" NumberOfLines="0" NumberOfStrips="0" NumberOfPolys="{len(F)}">\n')
        f.write('   <Points>\n    <DataArray type="Float64" NumberOfComponents="3" format="ascii">\n')
        f.write("\n".join(f"{x:.6f} {y:.6f} {z:.6f}" for x, y, z in V)); f.write("\n    </DataArray>\n   </Points>\n")
        f.write('   <Polys>\n    <DataArray type="Int64" Name="connectivity" format="ascii">\n')
        f.write("\n".join(f"{a} {b} {c}" for a, b, c in F)); f.write("\n    </DataArray>\n")
        f.write('    <DataArray type="Int64" Name="offsets" format="ascii">\n'); f.write(" ".join(str(3 * (i + 1)) for i in range(len(F)))); f.write("\n    </DataArray>\n   </Polys>\n")
        f.write('   <CellData Scalars="ModelFaceID">\n    <DataArray type="Int32" Name="ModelFaceID" format="ascii">\n'); f.write(" ".join(str(int(i)) for i in face_id)); f.write("\n    </DataArray>\n")
        f.write('    <DataArray type="Int32" Name="GlobalElementID" format="ascii">\n'); f.write(" ".join(str(i + 1) for i in range(len(F)))); f.write("\n    </DataArray>\n   </CellData>\n")
        f.write('   <PointData>\n    <DataArray type="Int32" Name="GlobalNodeID" format="ascii">\n'); f.write(" ".join(str(i + 1) for i in range(len(V)))); f.write("\n    </DataArray>\n   </PointData>\n")
        f.write("  </Piece>\n </PolyData>\n</VTKFile>\n")


def near(mesh_from, proxy, tol):
    """faces of mesh_from whose centres lie within tol of proxy (distance only -- no ray casting)."""
    c = mesh_from.triangles_center; out = np.zeros(len(c), bool)
    for i in range(0, len(c), 8000):
        _, dist, _ = closest_point(proxy, c[i:i + 8000]); out[i:i + 8000] = dist < tol
    return out


def inplane_r(P, C):
    v = P - C; v = v - np.outer(v @ AXIS, AXIS); return np.linalg.norm(v, axis=1)


def summarise(name, mesh, fid, names):
    areas = {names[k]: round(float(mesh.area_faces[fid == k].sum()) / 100, 3) for k in names}   # cm2
    return dict(file=name, faces=int(len(mesh.faces)), points=int(len(mesh.vertices)), watertight=bool(mesh.is_watertight),
                volume_mL=round(abs(mesh.volume) / 1000, 2), face_ids={k: names[k] for k in names}, face_area_cm2=areas)


def main():
    rep = dict(units="cm (SimVascular CGS default); source geometry frame A, mm x 0.1", models=[])
    # ---- 1. phantom fluid domain ----
    core = trimesh.load(os.path.join(HERE, "PHANTOM", "core_LV_with_ports.stl"), process=True)
    basal = -AXIS; n = core.face_normals; c = core.triangles_center; cap = n @ basal > 0.99
    def port_cap(C, r):
        along = (c - C) @ basal; inpl = np.linalg.norm((c - C) - np.outer(along, basal), axis=1)
        return cap & (np.abs(along - ph["PORT_LEN"]) < 0.5) & (inpl < r + 0.5)
    fid = np.ones(len(core.faces), int); fid[port_cap(MV_C, ph["PORT_R_MV"])] = 2; fid[port_cap(AV_C, ph["PORT_R_AV"])] = 3
    write_vtp(os.path.join(OUT, "fluid_phantom_cm.vtp"), core, fid)
    rep["models"].append(summarise("fluid_phantom_cm.vtp", core, fid, {1: "lumen_wall", 2: "inlet_mitral_port", 3: "outlet_aortic_port"}))
    print("phantom fluid:", rep["models"][-1]["face_area_cm2"]); del core

    # ---- 2. cavity fluid (label 500) ----
    cav = trimesh.load(os.path.join(HERE, "PRINT", "frame_A_patient", "lv_surface.stl"), process=True)
    myo_full = trimesh.load(os.path.join(HERE, "BLENDER_OUT", "LV_myocardium_frameA.stl"), process=True)
    myo_proxy = myo_full.simplify_quadric_decimation(face_count=PROXY_FACES)
    endo = near(cav, myo_proxy, ENDO_TOL)
    c = cav.triangles_center
    fid = np.full(len(cav.faces), 4, int); fid[endo] = 1
    rest = ~endo
    fid[rest & (inplane_r(c, MV_C) < MV_R)] = 2
    fid[rest & (inplane_r(c, AV_C) < AV_R)] = 3
    write_vtp(os.path.join(OUT, "fluid_cavity_cm.vtp"), cav, fid)
    rep["models"].append(summarise("fluid_cavity_cm.vtp", cav, fid, {1: "endocardium", 2: "mitral", 3: "aortic", 4: "base_wall"}))
    print("cavity fluid:", rep["models"][-1]["face_area_cm2"])
    cav_proxy = cav.simplify_quadric_decimation(face_count=PROXY_FACES); del cav

    # ---- 3. solid myocardium (label 205) ----
    solid = myo_full.simplify_quadric_decimation(face_count=SOLID_FACES); del myo_full
    if not solid.is_watertight:
        import pymeshfix
        vc, fc = pymeshfix.clean_from_arrays(np.ascontiguousarray(solid.vertices, dtype=np.float64), np.ascontiguousarray(solid.faces, dtype=np.int32))
        solid = trimesh.Trimesh(vc, fc, process=True)
    trimesh.repair.fix_normals(solid)
    endo = near(solid, cav_proxy, ENDO_TOL)
    n = solid.face_normals; c = solid.triangles_center
    base = (~endo) & (n @ (-AXIS) > np.cos(np.radians(45))) & (((c - MV_C) @ AXIS) < BASE_DEPTH)
    fid = np.full(len(solid.faces), 2, int); fid[endo] = 1; fid[base] = 3
    write_vtp(os.path.join(OUT, "solid_myocardium_cm.vtp"), solid, fid)
    rep["models"].append(summarise("solid_myocardium_cm.vtp", solid, fid, {1: "endocardium", 2: "epicardium", 3: "base"}))
    print("solid:", rep["models"][-1]["face_area_cm2"], "watertight", solid.is_watertight)
    rep["notes"] = ["fluid_cavity endocardium and solid endocardium are coincident surfaces (label boundary) but different triangulations; "
                    "svMultiPhysics FSI needs a conforming volume mesh -> stage 2 (pygalmesh multi-domain from the label image)",
                    "mitral/aortic faces of the cavity are the parts of the segmentation's basal cap inside the annulus radii; treat base_wall as rigid",
                    "SimVascular: File > Import Model (VTP) -> faces from ModelFaceID; set face types (wall/cap) before meshing"]
    json.dump(rep, open(os.path.join(OUT, "sv_models.json"), "w"), indent=1)
    print("->", OUT)


if __name__ == "__main__":
    main()
