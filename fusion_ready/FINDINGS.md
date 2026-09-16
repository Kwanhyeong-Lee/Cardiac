# Findings — frame-A print pipeline run (2026-09-16)

Blender `C:\Program Files\Blender Foundation\Blender 5.2\blender.exe` (5.2.1 LTS).
All §2 acceptance rows pass. Three defects were found and fixed; one large frame-level
finding changes how `cardiac_meshes/` must be used.

§§1–5 were done under the task's own authority. §§6–8 (v2 mitral, promotion, hollow
ventricle, frame B) were authorised by the user afterwards — the task had reserved them.
Frames C and D remain untouched.

---

## 1. The valves are zero-thickness sheets, not 1 mm shells  — FIXED

`CLAUDE_CODE_TASK.md` §0 and §3 assume the valve shells are "~1 mm thick" and that a low
fused volume means the voxel is eating that wall. Both are false.

Every one of the 9 components in each valve has Euler characteristic 1 or 0 — an open
disc or annulus, with no enclosed volume. There is no wall. Voxel-remeshing such a sheet
produces a film whose thickness is set by the voxel alone:

| voxel mm | mitral mL | aortic mL | manifold |
|---|---|---|---|
| 0.25 | 0.291 | 0.187 | true |
| 0.20 | 0.217 | 0.191 | true |
| 0.15 | 0.152 | 0.163 | true |

Measured film thickness at voxel 0.25 was 0.278 mm = **1.11 × voxel** (2V/A). §3's ladder
makes it monotonically *worse*, and manifoldness was never the failure mode.

**Fix:** `SOLIDIFY 1.2 mm` (centred, rim-capped) *before* the voxel remesh — the value
`blender_pipeline.py`'s own docstring already named as intended. Evidence retained in
`BLENDER_OUT/voxel_ladder.json` and `blender_report_voxel025_nosolidify.json`.

**Note on the 2.5–6.0 mL band:** it was derived as area × 1 mm = 3.3 mL, which
double-counts where leaflets overlap. A true 1.0 mm wall yields 2.21 mL for the mitral,
below the stated floor, because the remesh *unions* the overlapping layers. At 1.2 mm both
valves land in band and the measured wall is ≥ 1.0 mm over 99.8 % of area.

## 2. Loose fragment in the aortic valve — FIXED

The generator leaves two 16-face patches (~4 mm, 0.121 cm²) in
`aortic_valve_refit_v1.stl`. One became a 0.014 mL island floating 0.74 mm off the main
body — debris in the print. Added `drop_loose_fragments()` to the pipeline (drops islands
below 1 % of the part). Every exported part is now a single watertight component.

## 3. `cardiac_meshes/` is left–right MIRRORED; frame A is correct — IMPORTANT

`frame_A_patient/lv_surface.stl` is an **exact X-reflection** of
`cardiac_meshes/LV_case1009.stl`: mean surface distance **0.044 mm**, max 0.230 mm.
For comparison, identity gives 6.77 mm, Y-reflection 6.33 mm, Z-reflection 7.45 mm, and the
project's own `mm_to_cfd_transform.npy` gives 2.79 mm — none of them reproduce the file.

Which set is correct was decided by landmark tests, with anatomical axes derived from
*non-chiral* landmarks (great vessels are superior; RV anterior, LA posterior):

| test | result |
|---|---|
| apex is INFERIOR (non-chiral, validates the axes) | OK |
| RV is ANTERIOR of LV (non-chiral, validates the axes) | OK |
| LV should be LEFT of RV | **violated, −22.9 mm** |
| LA should be LEFT of RA | **violated, −26.7 mm** |
| apex should point LEFT of base | **violated, −11.3 mm** |

Both axis-validating checks pass and all three chirality checks fail consistently, so
**`cardiac_meshes/` is mirrored and frame A is correctly handed.**

Mechanism, and it is self-consistent: `lv_cfd_anatomical` was built via
`nifti_world_to_lvcfd_transform.npy`, i.e. through NIfTI *world* coordinates — and all three
stored transforms are proper rotations (det > 0, uniform singular values), so the documented
pipeline preserves handedness. `cardiac_meshes/` looks like marching cubes run in
voxel-index space without applying the affine, which mirrors the anatomy. That is a common
bug and it matches the evidence exactly.

**Consequence: the frame-A print is anatomically correct. Do not "fix" it.** Anything taken
from `cardiac_meshes/` must be mirrored first.

## 4. Myocardium registered into frame A — DELIVERED

Transform (mirror in X about the `cardiac_meshes` LV bbox centre, then origin-centre) is in
`BLENDER_OUT/frame_transform.json`; validated on the LV at **0.044 mm mean / 0.22 mm max**.

`MANIFEST.json → groups.frame_A_patient.common_offset_mm` does **not** do this job — it maps
frame A back to `lv_cfd_anatomical/constant/triSurface/`, a different source tree roughly
[−173, −125, −243] mm from `cardiac_meshes/`. §4.2's prescribed comparison cannot be done as
written.

`BLENDER_OUT/LV_myocardium_frameA.stl` — 361,772 faces, watertight, 125.64 mL,
centre [−0.24, 1.37, 0.32], extent [79.58, 94.21, 82.53] mm.

- blood pool interior inside the muscle: **0.07 %** (cleanly disjoint labels)
- 87.3 % of the pool surface has muscle outboard; the remaining 12.7 % is the valve orifice
- **wall median 7.78 mm, 86.6 % within 6–12 mm** (p05 5.2, p95 11.4)

This is the piece for a hollow printable ventricle. Not decimated, not printed — see §5.

## 5. Assembly checks

- MV–AV centroid separation is now **30.6 mm** (MANIFEST flagged 48 mm as too large for two
  annuli sharing the aortomitral curtain; typical 20–30). The refit fixed this; it had not
  been re-measured since.
- Both valves contact the LV (mitral overlaps up to 16.4 mm, aortic 3.9 mm) — the assembly
  is connected and prints as one piece.
- The valves do not touch each other (0.00 % mutual overlap).
- Combined STL true **union volume 153.1 ± 0.8 mL**, not the 155.5 mL naive sum — 2.4 mL is
  double-counted overlap. Use 153 mL for material estimates.
- Aortic valve sits 95.4 % outside the blood pool. This is expected, not a defect: the
  aortic valve belongs in the outflow tract and root, above the cavity, and the pool mesh
  stops at the annulus. `valve_refit.json`'s `frac_inside_LV` falling 0.125 → 0.045 is the
  valve moving to the right place. Renders in `BLENDER_OUT/render_*.png` show it perching on
  the base with only tangential contact — worth an eye before printing.

## 6. v2 mitral — BUILT, PASSES, PROMOTED

Full record in `valve_refit_v2.json`. The leaflet-zone metric was first reimplemented and
validated against the published number (0.875 → reproduced 0.878 on the same file).

| | v1 | v2 | gate |
|---|---|---|---|
| leaflet_inside | 0.878 | **0.978** | ≥ 0.90 PASS |
| outside leaflet vertices | 1075 / 8803 | **193** | |
| beyond wall, median | 1.55 mm | **0.65 mm** | |
| beyond wall, p95 / max | 4.85 / 6.02 | **3.02 / 4.94** | |
| worst 45° sector | 438 | **31** | |

Method: smoothed shrink-wrap of the protruding leaflet-zone vertices onto the endocardium
with 1.0 mm clearance, displacement diffused so no crease forms, annulus ring anchored.
Mean displacement 0.31 mm, max 7.06 mm, zero degenerate faces, 9 components preserved.

**Honest caveat:** this deforms refit_v1 rather than re-parameterising `generate_valves.py`
(whose D-factor is hard-coded to θ = π/2 at line 109). It reaches the same anatomical goal.
Two radial approaches — scaling about the base→apex axis, then about the true cavity
centreline — both made the metric *worse* (0.878 → 0.798), because the residual is shallow
and one-sided so a global radial shrink distorts the whole valve. Recorded so it is not
retried blindly.

**Promotion:** since v2 clears the gate that blocked v1, `mitral_valve.stl` ← refit_v2 and
`aortic_valve.stl` ← refit_v1 (the aortic was never gated). Originals preserved as
`*_ORIGINAL_unfitted.stl`, the convention `refit_valves.py` uses on its own accept path.
`blender_pipeline.py` now reads the canonical names. All §2 rows re-verified and PASS:
mitral 2.625 mL, aortic 3.197 mL, both single watertight components.

## 7. Hollow ventricle — BUILT

`BLENDER_OUT/LV_myocardium_frameA.stl` already *is* the hollow ventricle: one watertight
component, open at the base, 125.64 mL of muscle around a cavity the blood pool fills
(0.05 % overlap). No boolean was needed.

- own wall thickness: p05 5.36, **median 7.97**, p95 11.73 mm — only 0.01 % of area < 1 mm
- `BLENDER_OUT/hollow_ventricle_print.stl` = myocardium + both valves, bbox 79.6 × 94.2 ×
  99.5 mm, 131.5 mL of material

**Caveat you need before printing this one:** the valves overlap the *muscle* by only
0.00 % (mitral, after v2 pulled it inward) and 0.62 % (aortic). They overlapped the blood
*pool*, which in the hollow version is empty space. So in `hollow_ventricle_print.stl` the
valves are effectively loose in the cavity. Either print the myocardium alone and the valves
separately, or extend the valve annuli into the muscle — that is a design change, so I left
it. The blood-pool print is unaffected: the mitral still penetrates it by 16.4 mm (70.0 % of
its volume inside, up from 67.3 %) and the aortic by 3.8 mm.

## 8. Frame B re-examined — candidate confirmed, still not print-ready

`pm_recovery.json` withdrew its recovery because the inside-fraction metric did not
discriminate (spread 0.044 across the top 5), and noted that a proper test needs the mitral
position verified first. That precondition is now met, so the test was redone: all 48
axis-aligned transforms (24 proper rotations **and** 24 reflections, which the original
search never tried), translation optimised per candidate against an LV signed-distance grid,
scored on inside-fraction, base-on-endocardium gap, and tip-to-mitral-annulus distance.

Result in `frame_B_recheck.json`. Best is **perm (0,2,1), signs (−1,−1,−1), a proper
rotation** — the same candidate `pm_recovery.json` originally ranked first — now with real
separation: **0.809 vs 0.731** for the runner-up. Reflections were tested and lose, so frame
B does **not** carry the mirror bug from §3.

Not promoted to usable: the base gap is 6.7 mm, i.e. the papillary muscles float ~7 mm off
the endocardium instead of attaching to it. A true recovery needs a full 6-DOF rigid
registration with the base-attachment constraint, not a search over axis-aligned candidates.
Frames C and D untouched.
