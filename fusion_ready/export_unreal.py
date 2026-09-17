# -*- coding: utf-8 -*-
"""Step 30 -- export the whole-heart teaching model as an Unreal-ready asset pack.

Nothing is recomputed: the meshes are the ones `build_whole_heart_anatomy.py` already wrote.  What this
adds is everything Unreal needs and a mesh file does not carry:

  * COORDINATE FRAME.  The pipeline works in patient RAS millimetres.  glTF is right-handed, Y-up, metres,
    and Unreal's glTF importer converts glTF -> Unreal itself (left-handed, Z-up, cm) preserving the way
    the model LOOKS.  So the only thing this script must get right is RAS -> glTF, and it must keep the
    handedness (an odd permutation would mirror the heart -- exactly the bug that once poisoned
    `cardiac_meshes/`).  Chosen map, determinant +1:
        X_gltf = -X_ras   (patient right ends up on the viewer's left: the anatomical "front view")
        Y_gltf = +Z_ras   (superior -> up)
        Z_gltf = +Y_ras   (anterior -> toward the camera)
    Scale 0.001 (mm -> m), so an imported actor is life size (~12 cm) at Unreal's default import scale.
  * PER-PART COLOUR baked as vertex colours, so a single vertex-colour material renders the whole model,
    and the same colours repeated in `unreal_manifest.json` for material instances.
  * PROVENANCE per part (patient / parametric / synthetic), so the app can put the honesty label on
    screen next to whatever the student is looking at -- the same labels as EDUCATION_PACK.md.
  * A perfusion overlay mesh (LV myocardium coloured by LAD/LCx/RCA territory) when step 20 has run.

Outputs -> fusion_ready/UNREAL/<case>/: parts/*.glb, whole_heart.glb, half_{A,B}.glb,
perfusion_territories.glb, unreal_manifest.json.  Import notes: UNREAL_IMPORT.md.
Env: CASE, UE_DECIMATE (face budget per part; 0 = keep full density, the default -- Nanite wants it).
"""
import os, json, time
import numpy as np, trimesh
from case_paths import paths, HERE

P = paths(); OUT = os.path.join(HERE, "UNREAL", P["case"]); PARTS_OUT = os.path.join(OUT, "parts")
SRC = os.path.join(P["base"], "whole_heart_hollow"); DEC = int(os.environ.get("UE_DECIMATE", "0"))
R = np.array([[-1.0, 0, 0], [0, 0, 1.0], [0, 1.0, 0]])            # RAS -> glTF (Y-up, right-handed); det = +1
SCALE = 0.001
t0 = time.time()
PROV_KIND = [("patient", "환자 CT 그대로"), ("parametric", "파라메트릭 (문헌 비율)"), ("synthetic", "합성 (두께 가정)")]


def kind_of(prov):
    p = prov.lower()
    if "synthetic" in p: return "synthetic"
    if "parametric" in p: return "parametric"
    return "patient"


def to_gltf(m):
    q = m.copy(); q.vertices = (np.asarray(q.vertices) @ R.T) * SCALE
    trimesh.repair.fix_normals(q); return q


def paint(m, rgb):
    c = np.tile(np.r_[np.asarray(rgb, float), 1.0], (len(m.vertices), 1))
    m.visual = trimesh.visual.ColorVisuals(m, vertex_colors=(c * 255).astype(np.uint8)); return m


def save(m, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if DEC and len(m.faces) > DEC: m = m.simplify_quadric_decimation(face_count=DEC)
    m.export(path); return dict(file=os.path.relpath(path, OUT).replace("\\", "/"), faces=int(len(m.faces)), MB=round(os.path.getsize(path) / 1e6, 1))


def main():
    os.makedirs(PARTS_OUT, exist_ok=True)
    man = json.load(open(os.path.join(SRC, "parts_manifest.json")))
    entries = []
    for e in man["parts"]:
        src = os.path.join(SRC, e["file"])
        if not os.path.exists(src): continue
        m = trimesh.load(src, process=False)
        keep_vertex_colours = e["name"] == "LV_myocardium" and hasattr(m.visual, "vertex_colors")   # septum / papillary are painted per vertex
        m = to_gltf(m)
        if not keep_vertex_colours: m = paint(m, e["colour_rgb"])
        info = save(m, os.path.join(PARTS_OUT, f"{e['name']}.glb"))
        entries.append(dict(name=e["name"], colour_rgb=e["colour_rgb"], provenance=e["provenance"], kind=kind_of(e["provenance"]),
                            volume_mL=e["volume_mL"], vertex_colours=bool(keep_vertex_colours), **info))
        print(f"  {e['name']:24s} {info['faces']:>8,} f  {info['MB']:>5} MB  ({time.time()-t0:.0f}s)")
    extra = []
    for nm, src in (("whole_heart", "whole_heart_hollow_v2.stl"), ("half_A", "whole_heart_hollow_v2_4ch_A_anatomy.ply"), ("half_B", "whole_heart_hollow_v2_4ch_B_anatomy.ply")):
        p = os.path.join(SRC, src)
        if not os.path.exists(p): continue
        m = trimesh.load(p, process=False); vc = hasattr(m.visual, "vertex_colors") or hasattr(m.visual, "face_colors")
        m = to_gltf(m)
        if not vc: m = paint(m, (0.72, 0.28, 0.26))
        extra.append(dict(name=nm, source=src, **save(m, os.path.join(OUT, f"{nm}.glb")))); print(f"  {nm:24s} {extra[-1]['faces']:>8,} f  {extra[-1]['MB']:>5} MB")
    terr = os.path.join(P["territories"], "LV_myocardium_territories.ply")
    if os.path.exists(terr):
        extra.append(dict(name="perfusion_territories", source="territories/LV_myocardium_territories.ply", **save(to_gltf(trimesh.load(terr, process=False)), os.path.join(OUT, "perfusion_territories.glb"))))
        print(f"  perfusion_territories    {extra[-1]['faces']:>8,} f  {extra[-1]['MB']:>5} MB")
    cut = json.load(open(os.path.join(SRC, "cut_v2_info.json")))
    o = (np.array(cut["plane_origin"]) @ R.T) * SCALE; n = np.array(cut["plane_normal"]) @ R.T
    json.dump(dict(case=P["case"], units="metres (glTF); Unreal imports at 1 uu = 1 cm, so the actor is life size",
                   frame=dict(source="patient RAS mm", matrix_ras_to_gltf=R.tolist(), scale=SCALE, handedness="preserved (det +1) -- do NOT add a mirror in Unreal",
                              note="X_gltf = -X_ras, Y_gltf = Z_ras, Z_gltf = Y_ras: anterior faces the camera, superior is up, patient right is on the viewer's left"),
                   four_chamber_plane=dict(origin_m=o.round(5).tolist(), normal=n.round(5).tolist(), note="the plane the printed halves are cut on; use it as the default position of the interactive clip plane"),
                   provenance_legend={k: v for k, v in PROV_KIND}, parts=entries, assemblies=extra,
                   licence="Geometry derived from MM-WHS research CT: do not redistribute the meshes or a packaged build containing them. Screenshots, renders and tables may be shared."),
              open(os.path.join(OUT, "unreal_manifest.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    tot = sum(e["MB"] for e in entries) + sum(e["MB"] for e in extra)
    print(f"-> {OUT}  ({len(entries)} parts + {len(extra)} assemblies, {tot:.0f} MB, {time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
