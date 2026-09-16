# Methods draft — patient-specific LV geometry pipeline for printing, phantom casting and CFD

*(요약) MM-WHS 세그멘테이션 하나에서 출발해, 프레임·단위·손대칭을 검증한 좌심실 형상을 만들고,
그 위에 파라메트릭 판막을 실측 축으로 재배치하고, 방실면 판으로 고정해 단일 수밀 솔리드를 얻고,
같은 혈액풀로 lost-core 실리콘 팬텀과 CFD 도메인을 만들었다. 어디까지가 환자 형상이고
어디부터가 이상화인지는 §Limitations에 그대로 적었다. 이 초안은 방법론 논문/포스터의 Methods
골격이며, 결과·고찰은 실제 출력·계측 후에 쓴다.*

## 1. Source data and frame normalisation
Whole-heart CT segmentation of MM-WHS case 1009 (labels: LV blood cavity, LV myocardium, RV,
LA, RA, aorta, PA) was converted to surface meshes upstream. Two derived mesh sets existed:
`cardiac_meshes/` (marching cubes) and `lv_cfd_anatomical/` (CFD preprocessing). The 16 files
mixed metres and millimetres and four mutually inconsistent coordinate frames. We diagnosed
this from per-file bounding extents and pairwise centroid distances, grouped the files into
frames A–D, and kept only frame A (LV blood pool, mitral and aortic valve) as an internally
consistent set (`normalise_assembly.py`, `MANIFEST.json`).

## 2. Handedness (chirality) check
`cardiac_meshes/LV` reproduced the frame-A blood pool as an exact reflection in x (mean
surface distance 0.044 mm, max 0.22 mm; identity 6.8 mm). Which set is correctly handed was
decided by landmark tests whose axes come only from non-chiral landmarks (great vessels
superior, RV anterior of LV): both axis-validating tests passed in both sets, and all three
chirality tests (LV left of RV, LA left of RA, apex left of base) failed in `cardiac_meshes/`
by 11–27 mm. The mechanism is consistent with marching cubes run in voxel-index space without
the NIfTI affine. Frame A is therefore used as the anatomical reference and the myocardium
from `cardiac_meshes/` is brought into it by the validated reflection (`frame_transform.json`).

## 3. Mesh preparation for printing and CAD
Quadric decimation to ≤40 000 (print) and ≤10 000 (CAD) faces with proportional per-component
budgets, followed by MeshFix hole closing where decimation broke watertightness; every output
is checked for watertightness, single component, and surface deviation (`VERIFY.json`).

## 4. Valves
The valves are parametric (`generate_valves.py`), not segmented. The original placement used a
hard-coded LV axis 60° off the measured base→apex axis; we re-derived the axis, annulus centres
and radii from the blood pool and regenerated the valves (`refit_valves.py`), then reduced the
residual leaflet protrusion through the wall with an annulus-anchored, diffusion-smoothed
shrink-wrap to the endocardium with 1 mm clearance (leaflet-inside fraction 0.78 → 0.98). The
generator produces zero-thickness sheets (Euler characteristic 1/0 per component); a 1.2 mm
solidify followed by 0.25 mm voxel remeshing turns each valve into one watertight solid
(mitral 2.63 mL, aortic 3.20 mL).

## 5. Hollow ventricle with fixed valves
The myocardium label is an open cup whose rim ends 0.8 mm basal of the mitral annulus plane;
the aortic annulus floats 1.2 mm above it, and radially outward of the mitral rim there is no
muscle within 20 mm at 28 of 36 directions. There is therefore nothing for a radial collar to
grip. We built the structure that holds both valves in the heart — the fibrous skeleton of the
atrioventricular plane — as a plate: outline = convex hull of the myocardial cross-sections
4, 8 and 12 mm below the annulus; thickness 12.5 mm (4.5 mm apical to 8.0 mm basal of the
mitral plane, covering the 11 mm saddle of the actual annulus); a D-shaped mitral orifice equal
to the sheet's own annulus polygon offset inward by 1.5 mm; a round aortic orifice of the
annulus radius minus 1.5 mm. 87 % of the actual mitral annulus vertices lie inside the plate;
the remaining 13 % is the sector where the mitral annulus crosses the aortic orifice
(aortomitral continuity), left open deliberately. A manifold boolean union of myocardium,
plate and both valve solids gives one watertight component (751 754 faces, 163.9 mL); blood-pool
interior samples inside the union 1.7 %, and both orifice axes are open.

## 6. Papillary muscles and trabeculae — from the original CT
Morphological closing (ball radius 8 mm) of the voxelised blood pool added only 0.4 mL, and the
myocardium inside the closed cavity is a single 0.63 mm-thick film (voxel inflation): the
segmentation includes the papillary muscles in the blood-cavity label, so nothing can be
extracted from the meshes (`extract_pm.py`). We therefore went back to the CT volume
(0.49 × 0.49 × 0.63 mm). Inside label 500 an Otsu threshold between blood (median 340 HU) and
myocardium (median 120 HU) gives 235 HU; 17.8 mL of the 150.4 mL label is muscle. The true
blood pool (132.5 mL, largest component, holes filled) and the augmented myocardium (label 205
plus in-cavity muscle) were meshed at native resolution and brought into frame A by
registering the label-500 surface to the existing blood-pool mesh over all proper axis-aligned
rotations: the winner is a pure translation with 0.19 mm mean / 0.46 mm p95 distance. Thick
in-cavity muscle components inside the smoothed cavity yield two papillary muscles,
anterolateral 2.1 mL (−121° from the mitral→aortic direction, 29 mm long) and posteromedial
3.1 mL (+153°, 31 mm), flanking the inferolateral wall 86° apart. The v4 solid unions this
myocardium with the plate, the valve solids and ten 1 mm chordae routed from the CT muscle
tips to leaflet free-edge points (each verified inside the CT blood pool): 712 322 faces, one
watertight component, 181.8 mL. In v4 the wall, endocardium, trabeculae and papillary muscles
are the patient's; leaflets, plate and chordae routes remain parametric.

Two earlier routes are recorded because they failed informatively. Papillary muscles from a
second source (frame B, another heart) could not be rigidly registered — a 6-DOF refinement
with base-attachment, containment and tip-to-annulus constraints violates every gate
simultaneously (`pm_registration.json`). Before the CT re-segmentation, v3 used *idealised*
muscles (tapered bodies at ±120° from the mitral→aortic direction, bases at 62 % depth) with
the same chordae scheme; against the CT muscles the anterolateral guess was within 1°, the
posteromedial 33° off. v3 is kept for comparison only.

## 7. Flow phantom (lost-core casting) and CFD domain
A silicone phantom needs the LV as a cavity, so a two-part negative mould (which casts a solid)
is the wrong object. The core is the blood pool plus two cylindrical port stubs along the LV
axis (Ø19 mm mitral, Ø15.8 mm aortic = 2.84 / 1.96 cm², matching the effective areas already
used in the CFD case), printed in water-soluble PVA; the mould box (4 mm walls, two bores with
0.4 mm clearance, open pour face with 8 mm freeboard, 32 mm corner feet) holds the core by the
stubs. Design checks: no core–wall contact, ≥15 mm silicone everywhere, ≈0.98 L silicone. The
same core, split at the stub end-caps into `inlet`, `outlet` and `LV` patches, is the CFD
domain (closed multi-region STL in metres, 40 948 faces), so simulation and bench share one
boundary.

## 8. Verification practice
Every step writes a JSON with its acceptance metrics; thresholds were fixed before running and
were not moved after a miss (the v1 mitral refit stayed at 87.5 % against a 90 % gate until an
independent v2 passed). Three figure and check bugs were found and are recorded because they
would otherwise recur: sections drawn in per-mesh 2-D frames; a marching-cubes mesh left in
voxel-index coordinates (empty boolean → false negative); `np.False_ is False`.

## Limitations (state these verbatim in any write-up)
1. Valve leaflets, the AV-plane plate and the chordae (routes, number, radius) are parametric;
   in v4 the wall, endocardium, trabeculae and papillary muscles are the patient's (CT-derived).
2. The phantom core and CFD domain still use the label-500 cavity (papillary-muscle-inclusive,
   150 mL) rather than the CT blood pool (132.5 mL); swapping in a lightly closed version of
   the CT pool is a one-line change but has not been done or checked for castability.
3. Single case, static end-diastolic-like geometry; no motion, no compliance matching (silicone
   is compliant, the CFD wall is rigid).
4. No ground truth for valve anatomy in this dataset; "correct" placement means consistent
   with the measured LV axis and annulus, not with the patient's valves.
5. Print/mesh checks are geometric; nothing here has been physically printed or measured yet.
