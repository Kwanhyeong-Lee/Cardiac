# -*- coding: utf-8 -*-
"""Blender headless pipeline: Frame A (LV + refit valves) -> print-ready solids + report.

Run from Windows (Blender is installed there, not in WSL):
    blender --background --python blender_pipeline.py
or double-click run_blender_pipeline.bat, which finds blender.exe and does the same.

WHAT IT DOES
  1. Imports frame A parts in mm:
        LV            PRINT/frame_A_patient/lv_surface.stl   (39,992 faces, watertight)
        mitral valve  frame_A_patient/mitral_valve.stl   (= refit_v2, promoted 2026-09-16)
        aortic valve  frame_A_patient/aortic_valve.stl   (= refit_v1, promoted 2026-09-16)
     The refit valves are used because the originals are ~60 degrees misoriented (see
     valve_refit.json). Both are 9-component open shells ~1 mm thick -- not printable as-is.
  2. Valves: the 9 components are ZERO-THICKNESS open sheets (every component has Euler
     characteristic 1 or 0 -- disc/annulus -- and no enclosed volume). They therefore have no
     wall for the remesh to preserve: voxel-remeshing them directly yields a film whose
     thickness is set purely by the voxel (measured 0.278 mm at voxel 0.25, i.e. 1.11 voxels),
     giving 0.29 mL instead of the ~3.3 mL that 32.9 cm2 x 1 mm implies. Shrinking the voxel
     makes it thinner, not thicker (0.25 -> 0.29 mL, 0.20 -> 0.22 mL, 0.15 -> 0.15 mL).
     So: SOLIDIFY 1.0 mm (centred) FIRST to create the wall, then voxel REMESH (0.25 mm) to
     fuse the 9 solidified components into one closed manifold each.
  3. LV: imported as-is (already watertight) and re-checked.
  4. Every object: non-manifold edge count, volume (mm^3 -> mL), bounding box, face count,
     written to BLENDER_OUT/blender_report.json. The 3D-Print Toolbox is used when present.
  5. Exports per-part STL + one combined STL + the .blend to BLENDER_OUT/.

Units: scene set to millimetres; STL import scale 1.0 (files are already mm).
Blender 4.x API (wm.stl_import); falls back to the legacy importer on 3.x.
"""
import bpy, bmesh, json, os, sys, time
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "BLENDER_OUT")
os.makedirs(OUT, exist_ok=True)
LOG = []


def log(msg):
    print(msg, flush=True); LOG.append(msg)


PARTS = [  # (name, path, treat_as)
    ("LV_bloodpool",   os.path.join(HERE, "PRINT", "frame_A_patient", "lv_surface.stl"),        "solid"),
    ("mitral_valve",   os.path.join(HERE, "frame_A_patient", "mitral_valve.stl"),      "shell"),
    ("aortic_valve",   os.path.join(HERE, "frame_A_patient", "aortic_valve.stl"),      "shell"),
]
VOXEL_MM = 0.25
SOLIDIFY_MM = 1.2        # wall given to the zero-thickness valve sheets, centred (+-0.5 mm)


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    s.unit_settings.system = 'METRIC'
    s.unit_settings.length_unit = 'MILLIMETERS'
    s.unit_settings.scale_length = 0.001          # 1 BU = 1 mm


def import_stl(path, name):
    before = set(bpy.data.objects)
    if hasattr(bpy.ops.wm, "stl_import"):
        bpy.ops.wm.stl_import(filepath=path, global_scale=1.0)
    else:
        bpy.ops.import_mesh.stl(filepath=path, global_scale=1.0)
    obj = (set(bpy.data.objects) - before).pop()
    obj.name = name; obj.data.name = name
    return obj


def mesh_stats(obj):
    bm = bmesh.new(); bm.from_mesh(obj.data)
    bm.edges.ensure_lookup_table()
    non_manifold = sum(1 for e in bm.edges if not e.is_manifold)
    boundary = sum(1 for e in bm.edges if e.is_boundary)
    vol = bm.calc_volume(signed=False) if non_manifold == 0 else None
    bm.free()
    bb = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    lo = [min(v[i] for v in bb) for i in range(3)]; hi = [max(v[i] for v in bb) for i in range(3)]
    return dict(faces=len(obj.data.polygons), verts=len(obj.data.vertices),
                non_manifold_edges=non_manifold, boundary_edges=boundary,
                manifold=(non_manifold == 0),
                volume_mL=round(vol / 1000.0, 3) if vol is not None else None,
                bbox_min_mm=[round(x, 2) for x in lo], bbox_max_mm=[round(x, 2) for x in hi],
                extent_mm=[round(h - l, 2) for l, h in zip(lo, hi)])


def solidify(obj, thickness):
    """Give a zero-thickness sheet a real wall, centred on the original surface."""
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    md = obj.modifiers.new("solidify", 'SOLIDIFY')
    md.thickness = thickness
    md.offset = 0.0                 # centred: +-thickness/2 about the original sheet
    md.use_even_offset = True
    md.use_quality_normals = True
    md.use_rim = True               # cap the open boundaries -> closed shell
    md.use_rim_only = False
    bpy.ops.object.modifier_apply(modifier=md.name)


def voxel_remesh(obj, voxel):
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    md = obj.modifiers.new("remesh", 'REMESH')
    md.mode = 'VOXEL'; md.voxel_size = voxel; md.adaptivity = 0.0
    md.use_smooth_shade = False
    bpy.ops.object.modifier_apply(modifier=md.name)


def drop_loose_fragments(obj, min_frac=0.01):
    """Delete disconnected islands smaller than min_frac of the part's total volume.

    The valve generator leaves two 16-face patches (~4 mm) in aortic_valve_refit_v1; the
    remesh turns one into a 0.014 mL island floating 0.74 mm off the main body, i.e. loose
    debris in the print. Anything at or above min_frac is kept untouched.
    """
    bm = bmesh.new(); bm.from_mesh(obj.data)
    islands, seen = [], set()
    for f in bm.faces:
        if f.index in seen: continue
        stack, grp = [f], []
        seen.add(f.index)
        while stack:
            cur = stack.pop(); grp.append(cur)
            for e in cur.edges:
                for nf in e.link_faces:
                    if nf.index not in seen:
                        seen.add(nf.index); stack.append(nf)
        islands.append(grp)
    if len(islands) > 1:
        vols = [abs(sum(f.calc_area() for f in g)) for g in islands]   # area as size proxy
        keep = max(vols)
        doomed = [f for g, v in zip(islands, vols) if v < keep * min_frac for f in g]
        if doomed:
            bmesh.ops.delete(bm, geom=doomed, context='FACES')
            bm.to_mesh(obj.data); obj.data.update()
            log(f"[{obj.name}] dropped {len(islands) - 1} loose fragment(s), "
                f"{len(doomed)} faces")
    bm.free()


def print3d_check(obj):
    """Use the 3D-Print Toolbox if it is enabled; otherwise report None."""
    try:
        bpy.ops.preferences.addon_enable(module="object_print3d_utils")
    except Exception:
        return None
    try:
        bpy.context.view_layer.objects.active = obj
        for o in bpy.data.objects: o.select_set(o is obj)
        bpy.ops.mesh.print3d_check_all()
        rep = bpy.context.scene.print_3d
        return {"thickness_mm_setting": rep.thickness_min,
                "note": "see Blender N-panel > 3D-Print for the itemised result; headless run only triggers the check"}
    except Exception as e:
        return {"error": str(e)[:120]}


def main():
    t0 = time.time()
    reset_scene()
    report = {"blender": bpy.app.version_string, "voxel_mm": VOXEL_MM,
              "solidify_mm": SOLIDIFY_MM, "parts": {}}
    objs = []
    for name, path, kind in PARTS:
        if not os.path.exists(path):
            log(f"MISSING {path}"); report["parts"][name] = {"error": "file missing"}; continue
        obj = import_stl(path, name)
        before = mesh_stats(obj)
        log(f"[{name}] imported  faces {before['faces']:,}  manifold {before['manifold']}  "
            f"non-manifold edges {before['non_manifold_edges']}")
        mid = None
        if kind == "shell":
            solidify(obj, SOLIDIFY_MM)
            mid = mesh_stats(obj)
            log(f"[{name}] solidified {SOLIDIFY_MM} mm  faces {mid['faces']:,}  "
                f"manifold {mid['manifold']}  volume {mid['volume_mL']} mL")
            voxel_remesh(obj, VOXEL_MM)
            drop_loose_fragments(obj)
            after = mesh_stats(obj)
            log(f"[{name}] remeshed  faces {after['faces']:,}  manifold {after['manifold']}  "
                f"volume {after['volume_mL']} mL  extent {after['extent_mm']} mm")
        else:
            after = before
        report["parts"][name] = {"source": path.replace(HERE, "."), "kind": kind,
                                 "before": before, "solidified": mid, "after": after}
        objs.append(obj)

    # per-part export
    for obj in objs:
        for o in bpy.data.objects: o.select_set(o is obj)
        bpy.context.view_layer.objects.active = obj
        p = os.path.join(OUT, f"{obj.name}.stl")
        if hasattr(bpy.ops.wm, "stl_export"):
            bpy.ops.wm.stl_export(filepath=p, export_selected_objects=True, global_scale=1.0)
        else:
            bpy.ops.export_mesh.stl(filepath=p, use_selection=True, global_scale=1.0)
        log(f"[{obj.name}] -> {os.path.basename(p)}")

    # combined export (all parts, same coordinates)
    for o in bpy.data.objects: o.select_set(o in objs)
    pc = os.path.join(OUT, "frameA_LV_valves_combined.stl")
    if hasattr(bpy.ops.wm, "stl_export"):
        bpy.ops.wm.stl_export(filepath=pc, export_selected_objects=True, global_scale=1.0)
    else:
        bpy.ops.export_mesh.stl(filepath=pc, use_selection=True, global_scale=1.0)

    # 3D-Print toolbox pass on the valves (headless trigger only)
    for obj in objs:
        report["parts"][obj.name]["print3d_toolbox"] = print3d_check(obj)

    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "frameA_print.blend"))
    report["seconds"] = round(time.time() - t0, 1)
    report["log"] = LOG
    json.dump(report, open(os.path.join(OUT, "blender_report.json"), "w"), indent=1)
    log(f"done in {report['seconds']}s -> {OUT}")


if __name__ == "__main__":
    main()

