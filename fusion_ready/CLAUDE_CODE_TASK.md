# Task for Claude Code (run on Windows, in this folder)

You are running on the user's Windows machine where Blender is installed. Your shell is
their real shell. Everything below is executable without asking; only stop for the
decisions marked **ASK**.

Working directory: this folder (`fusion_ready/`). All paths below are relative to it.

## 0. Context in 6 lines

- `frame_A_patient/` holds the only coherent anatomy: LV blood pool + two parametric valves, mm, LV centroid at origin.
- The original valves are ~60° misoriented (`generate_valves.py` hardcodes `lv_axis=[0,0,-1]`). `*_refit_v1.stl` are the corrected ones. Use refit_v1. Details: `valve_refit.json`.
- The valves are 9-component open shells ~1 mm thick. Not printable until fused into closed solids.
- `blender_pipeline.py` does that (voxel remesh 0.25 mm), checks manifoldness, exports STL + .blend + `BLENDER_OUT/blender_report.json`.
- `README.md` and `MANIFEST.json` explain why frames B/C/D are excluded. Do not import them into the print.
- Nothing in `waveform_pinn/` is related to this task.

## 1. Run the pipeline

```powershell
# find blender if not on PATH
$bl = (Get-Command blender -ErrorAction SilentlyContinue).Source
if (-not $bl) { $bl = (Get-ChildItem "$env:ProgramFiles\Blender Foundation\Blender*\blender.exe" | Sort-Object FullName -Descending | Select-Object -First 1).FullName }
& $bl --background --python blender_pipeline.py 2>&1 | Tee-Object BLENDER_OUT\run.log
```

If `blender.exe` is not found anywhere, search `Get-ChildItem C:\ -Recurse -Filter blender.exe -ErrorAction SilentlyContinue | Select-Object -First 3` and use that path. Record the path you used.

## 2. Verify — every line must hold, or go to §3

Read `BLENDER_OUT/blender_report.json`.

| check | expected | source of expectation |
|---|---|---|
| `parts.LV_bloodpool.after.manifold` | `true` | LV PRINT was MeshFix-closed; see `VERIFY.json` |
| `parts.LV_bloodpool.after.volume_mL` | **149.8 ± 1.5** | source volume 149.783 mL (`VERIFY.json`), PRINT retained 100.0% |
| `parts.LV_bloodpool.after.faces` | 39,992 | unchanged by pipeline |
| `parts.mitral_valve.after.manifold` | `true` | remesh must fuse all 9 shells |
| `parts.mitral_valve.after.non_manifold_edges` | 0 | |
| `parts.mitral_valve.after.volume_mL` | **2.5 – 6.0** | shell area 32.9 cm² × ~1 mm thickness ≈ 3.3 mL; remesh adds up to ~1 voxel |
| `parts.mitral_valve.after.extent_mm` | each axis **33 – 40** | source extent [35.7, 37.2, 35.4] + ≤2×voxel |
| `parts.aortic_valve.after.manifold` | `true` | |
| `parts.aortic_valve.after.volume_mL` | **2.5 – 6.0** | shell area 32.5 cm² |
| `parts.aortic_valve.after.extent_mm` | each axis **28 – 34** | source [29.8, 30.1, 29.9] |
| files present | `LV_bloodpool.stl`, `mitral_valve.stl`, `aortic_valve.stl`, `frameA_LV_valves_combined.stl`, `frameA_print.blend` in `BLENDER_OUT/` | |

Additionally, independently re-check each exported STL with Python (trimesh is fine; `pip install trimesh` if needed): `is_watertight`, `volume/1000`, `extents`. The numbers must agree with the report to within 1%. If they do not, the report is wrong and that is the finding — do not trust the report over the file.

## 3. If something fails

- **Valve not manifold after remesh** → rerun with `VOXEL_MM = 0.20` (edit the constant in `blender_pipeline.py`). If still not manifold at 0.20, try 0.15. Record each attempt. Below 0.15 mm the mesh becomes too heavy for printing; stop and report.
- **Valve volume < 2.5 mL** → the remesh voxel is eating the 1 mm wall. Use a smaller voxel (0.20 → 0.15). If volume is still low at 0.15, the shells have gaps wider than the wall; report it, do not force-fill.
- **Valve volume > 6 mL or extent grows > 3 mm** → voxel too coarse or shells were merged with air inside; inspect in Blender (`frameA_print.blend`) and report a screenshot.
- **LV volume outside 149.8 ± 1.5** → the STL importer applied a scale. Check `scene.unit_settings` and the importer's `global_scale`. Do not "fix" by rescaling the output; fix the import.
- **Blender API error on `wm.stl_import`** → Blender < 4.0; the script falls back to `import_mesh.stl`, but that legacy add-on may need enabling: `bpy.ops.preferences.addon_enable(module="io_mesh_stl")` before import.

## 4. When §2 passes — optional follow-ups you may do without asking

1. **Minimum wall thickness of the fused valves**, for print-process choice: in Blender, enable the 3D-Print Toolbox, run "Check All" on each valve with thickness threshold 1.0 mm and then 0.8 mm; report how many faces fail at each. FDM needs ≥ ~1.0 mm; SLA/MJF is fine at 0.6.
2. **Frame check for the myocardium**: `..\cardiac_meshes\LV_Myocardium_case1009.stl` (361,772 faces). Load it, report its bbox centre and extent in mm, and whether it encloses `frame_A_patient/lv_surface.stl` *after* applying the frame-A offset from `MANIFEST.json → groups.frame_A_patient.common_offset_mm` (subtract it, i.e. patient = frameA − offset; then compare). If the LV blood pool sits inside the myocardium shell with a wall of roughly 6–12 mm, say so — that is the piece needed for a *hollow* printable ventricle instead of a solid cavity cast. Do not decimate or print it yet.

## 5. **ASK** before doing

- Anything that touches frames B, C or D (papillary muscles, STACOM right heart, aortic root). They are not registered to the patient; see `MANIFEST.json`.
- Promoting `*_refit_v1.stl` to `mitral_valve.stl` / `aortic_valve.stl`. The refit missed its pre-set acceptance criterion by 2.5 points (`valve_refit.json → gate_note`, `decision`); the user has been told and gets to decide.
- Regenerating valves with a new D-shape orientation ("v2"). That is a design change, not a repair.

## 6. Report back

Print, in this order: the Blender path used; the §2 table with actual values and PASS/FAIL per row; the independent trimesh re-check numbers; anything from §3 that was needed; results of §4 if run. Keep it to one screen. The user will paste it into the Cowork session where the rest of this project lives.
