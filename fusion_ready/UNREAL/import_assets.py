# -*- coding: utf-8 -*-
"""Runs INSIDE the Unreal editor (Tools > Execute Python Script), not in the pipeline environment.

Imports the asset pack written by fusion_ready/export_unreal.py: every part .glb as a static mesh with
vertex colours kept and meshes NOT combined (parts have to stay separable to be toggled), then writes a
DataTable-friendly JSON copy of the manifest next to the assets so Blueprints can read name / colour /
provenance / volume without re-parsing the glTF.

Edit PACK to point at fusion_ready/UNREAL/<case>.  Unreal's Python API names move between 5.x releases --
run it once on a throwaway folder and check the log before pointing it at the real project.
"""
import json, os
import unreal

PACK = r"C:\work\Cardiac\fusion_ready\UNREAL\1009"          # <- source folder
DEST = "/Game/Heart"                                          # <- content browser destination
COMBINE, NANITE = False, False                                # parts must stay separate; 2.4M tris runs fine without Nanite


def options():
    o = unreal.InterchangeGenericAssetsPipeline()
    o.mesh_pipeline.set_editor_property("combine_static_meshes", COMBINE)
    o.mesh_pipeline.set_editor_property("build_nanite", NANITE)
    o.common_meshes_properties.set_editor_property("import_vertex_colors", True)     # WITHOUT this every part imports white
    o.common_meshes_properties.set_editor_property("vertex_color_import_option", unreal.VertexColorImportOption.REPLACE)
    return o


def task(src, dest):
    t = unreal.AssetImportTask()
    t.filename = src; t.destination_path = dest; t.automated = True; t.replace_existing = True; t.save = True
    t.set_editor_property("options", options())
    return t


def main():
    man = json.load(open(os.path.join(PACK, "unreal_manifest.json"), encoding="utf-8"))
    tasks = [task(os.path.join(PACK, e["file"]), f"{DEST}/Parts") for e in man["parts"]]
    tasks += [task(os.path.join(PACK, e["file"]), f"{DEST}/Assemblies") for e in man["assemblies"]]
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    rows = [dict(Name=e["name"], R=e["colour_rgb"][0], G=e["colour_rgb"][1], B=e["colour_rgb"][2],
                 Kind=e["kind"], Provenance=e["provenance"], VolumeML=e["volume_mL"], Mesh=f"{DEST}/Parts/{e['name']}")
            for e in man["parts"]]
    out = os.path.join(PACK, "parts_datatable.json")
    json.dump(rows, open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    unreal.log(f"imported {len(tasks)} meshes; DataTable source -> {out}")
    unreal.log(f"four-chamber plane (metres, glTF frame): {man['four_chamber_plane']}")
    unreal.log(man["licence"])


main()
