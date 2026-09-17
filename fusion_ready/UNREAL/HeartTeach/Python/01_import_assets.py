# -*- coding: utf-8 -*-
"""Runs INSIDE the Unreal editor: Tools > Execute Python Script (or -ExecutePythonScript=...).

Imports fusion_ready/UNREAL/<case>/*.glb and builds the three DataTables the app reads.
Idempotent: re-running re-imports over the same assets.

Failure points to expect on a first run (API names drift between 5.x):
  * the Interchange pipeline property names under `mesh_pipeline` / `common_meshes_properties`
  * DataTableFunctionLibrary.fill_data_table_from_csv_string
Each step prints before it runs, so the log tells you which one.
"""
import csv, io, json, os
import unreal

PACK = os.environ.get("HEART_PACK", r"C:\work\Cardiac\fusion_ready\UNREAL\1009")
DEST = "/Game/Heart"
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
PROV = {"patient": "Patient", "parametric": "Parametric", "synthetic": "Synthetic"}


def log(msg): unreal.log(f"[HeartTeach] {msg}")


def import_options():
    o = unreal.InterchangeGenericAssetsPipeline()
    o.mesh_pipeline.set_editor_property("combine_static_meshes", False)     # parts must stay separable
    o.mesh_pipeline.set_editor_property("build_nanite", False)              # 2.4M tris total; Nanite + masked/two-sided is version-dependent
    o.common_meshes_properties.set_editor_property("import_vertex_colors", True)   # without this every part imports white
    o.common_meshes_properties.set_editor_property("vertex_color_import_option", unreal.VertexColorImportOption.REPLACE)
    return o


def import_meshes(man):
    tasks = []
    for group, folder in (("parts", "Parts"), ("assemblies", "Assemblies")):
        for e in man.get(group) or []:
            src = os.path.join(PACK, e["file"])
            if not os.path.exists(src):
                log(f"MISSING {src}"); continue
            t = unreal.AssetImportTask()
            t.filename = src; t.destination_path = f"{DEST}/{folder}"
            t.automated = True; t.replace_existing = True; t.save = True
            t.set_editor_property("options", import_options())
            tasks.append(t)
    log(f"importing {len(tasks)} meshes")
    TOOLS.import_asset_tasks(tasks)


def make_table(name, struct_path, csv_text):
    """DataTable from a CSV string.  `struct_path` is the C++ row struct, e.g. /Script/HeartTeach.HeartPartRow."""
    path = f"{DEST}/{name}"
    dt = unreal.EditorAssetLibrary.load_asset(path)
    if not dt:
        dt = TOOLS.create_asset(name, DEST, unreal.DataTable, unreal.DataTableFactory())
        dt.set_editor_property("row_struct", unreal.load_object(None, struct_path))
    unreal.DataTableFunctionLibrary.fill_data_table_from_csv_string(dt, csv_text)
    unreal.EditorAssetLibrary.save_asset(path)
    log(f"{name}: {len(csv_text.splitlines()) - 1} rows")
    return dt


def to_csv(header, rows):
    buf = io.StringIO(); w = csv.writer(buf, lineterminator="\n")
    w.writerow(header); [w.writerow(r) for r in rows]
    return buf.getvalue()


def col(rgb):  # UE parses FLinearColor in a CSV as "(R=..,G=..,B=..,A=..)"
    return f"(R={rgb[0]:.4f},G={rgb[1]:.4f},B={rgb[2]:.4f},A=1.0)"


def main():
    man = json.load(open(os.path.join(PACK, "unreal_manifest.json"), encoding="utf-8"))
    log(f"case {man['case']}: {len(man['parts'])} parts, {len(man['assemblies'])} assemblies")
    log(man["licence"])
    import_meshes(man)

    rows = []
    for e in man["parts"]:
        mesh = f"/Script/Engine.StaticMesh'{DEST}/Parts/{e['name']}.{e['name']}'"
        rows.append([e["name"], e["name"], mesh, col(e["colour_rgb"]), PROV.get(e["kind"], "Patient"),
                     e["provenance"].replace(",", ";"), e["volume_mL"],
                     "True" if e.get("vertex_colours") else "False", e["name"].replace("_", " ")])
    make_table("DT_HeartParts", "/Script/HeartTeach.HeartPartRow",
               to_csv(["Name", "PartName", "Mesh", "Colour", "Provenance", "ProvenanceNote", "VolumeML", "bUseVertexColours", "DisplayName"], rows))

    pf = man.get("perfusion")
    if pf:
        make_table("DT_HeartTerritories", "/Script/HeartTeach.HeartTerritoryRow",
                   to_csv(["Name", "Site", "Vessel", "MassAtRiskG", "PercentOfLV"],
                          [[f"S{i}", s["site"].replace(",", ";"), s["vessel"], s["mass_at_risk_g"], s["percent_of_LV"]] for i, s in enumerate(pf["scenarios"])]))
        make_table("DT_HeartTerritoryColours", "/Script/HeartTeach.HeartTerritoryColourRow",
                   to_csv(["Name", "Vessel", "bMeasured", "Colour", "VertexCount"],
                          [[f"{c['vessel']}_{'M' if c['confidence'] == 'measured' else 'P'}", c["vessel"],
                            "True" if c["confidence"] == "measured" else "False",
                            col([v / 255.0 for v in c["rgb8"]]), c.get("vertex_count", 0)]
                           for c in pf["colours"]]))
        log(f"perfusion: LV {pf['lv_mass_g']} g, {pf['far_from_visible_percent']} % of the myocardium is further than 25 mm from any visible vessel")
        log("pale territory colours = assigned from a groove prior, NOT measured -- keep that visible in the UI")

    log("done. next: 02_build_materials.py")


main()
