# -*- coding: utf-8 -*-
"""Atrioventricular-plane plate: the part that fixes both valves to the hollow ventricle.

WHY A PLATE AND NOT A COLLAR. Measured on LV_myocardium_frameA.stl (FINDINGS.md §4):
    - the muscle cup's basal opening ends 0.8 mm basal of the mitral annulus plane
    - the aortic annulus plane is 1.2 mm basal of the top of the muscle -- the aortic valve
      floats entirely above the cup
    - radially outward from the mitral rim, no muscle exists within 20 mm at 28 of 36 angles
So there is nothing for a radial collar to reach. Anatomically the structure that holds
both valves and closes the ventricular base is the fibrous skeleton at the atrioventricular
plane. This script builds that: a plate whose outline is the muscle's own basal outline,
with a mitral and an aortic orifice, thick enough to embed both annulus rings and overlap
the top of the muscle wall, so a voxel-remesh union in Blender fuses everything into one
printable solid.

GEOMETRY (all frame A, mm)
    plane        normal = LV axis; plate spans from 1.5 mm apical of the mitral annulus
                 plane to 3.0 mm basal of it (4.5 mm thick) -> overlaps the muscle rim by
                 ~2.3 mm, contains the mitral ring (at 0) and the aortic ring (at +2)
    outline      outer boundary of the muscle cross-section at the mitral plane
    orifices     mitral r = r_mv - 1.5, aortic r = r_av - 1.5  (1.5 mm of annulus ring is
                 embedded; leaflets pass through and hang free below the plate)

No booleans: shapely polygon-with-holes -> trimesh.creation.extrude_polygon.
Output: frame_A_patient/av_plane_plate.stl + av_plate.json (dimensions, checks).
"""
import json, os, warnings
import numpy as np, trimesh
from shapely.geometry import Polygon, Point
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
FA = os.path.join(HERE, "frame_A_patient")
d = json.load(open(os.path.join(HERE, "valve_refit.json")))
AXIS = np.array(d["lv_geometry"]["axis_base_to_apex"])
MV_C, MV_R = np.array(d["design"]["mv_centre_mm"]), float(d["design"]["mv_annulus_r_mm"])
AV_C, AV_R = np.array(d["design"]["av_centre_mm"]), float(d["design"]["av_annulus_r_mm"])
APICAL_START, THICK, EMBED = 4.5, 12.5, 1.5  # plate from 4.5 apical to 8.0 basal of the mitral plane
# History. 1.5/6.0 (to 4.5 basal) was the first value; measured against the ACTUAL refit
# mitral sheet only 38 % of its annulus-ring vertices were inside the plate (the 83 % metric
# below is for an idealised flat circle). Causes, in order: the real annulus is a saddle from
# 7.1 basal to 4.0 apical (plate too thin both ways); the real annulus is D-shaped with its
# straight anterior segment at r = 10.8 from the centre, which a circular hole of r = 13.7
# cuts away (hole shape wrong); and a 13 % arc sits inside the aortic orifice (aortomitral
# curtain -- left open on purpose, the aortic outflow wins there). Hence: 12.5 mm thick and a
# D-shaped mitral hole = the sheet's own annulus polygon offset inward by EMBED.


def main():
    myo = trimesh.load(os.path.join(HERE, "BLENDER_OUT", "LV_myocardium_frameA.stl"), process=True)
    origin = MV_C + APICAL_START * AXIS                       # plate bottom face
    normal = -AXIS                                            # extrude basal
    # The muscle's own section at the plate plane is an irregular lip, and deeper sections
    # come back as ONE self-touching loop (inner and outer wall joined by a seam), so
    # polygons_full cannot see the ring. The outline is therefore taken as the convex hull
    # of the wall sections 4, 8 and 12 mm below the mitral plane, projected into the plate
    # plane -- the LV base outline is convex to well under a millimetre, and a plate that
    # slightly overhangs a concavity is harmless.
    sec0 = myo.section(plane_origin=origin, plane_normal=normal)
    p2, to3 = sec0.to_planar()
    inv = np.linalg.inv(to3)
    def to2d(P):
        q = trimesh.transform_points(np.atleast_2d(P), inv); return q[:, :2]
    pts2 = []
    for dep in (4.0, 8.0, 12.0):
        sec = myo.section(plane_origin=MV_C + dep * AXIS, plane_normal=normal)
        if sec is not None:
            pts2.append(to2d(sec.vertices))
    pts2 = np.vstack(pts2)
    from shapely.geometry import MultiPoint
    outer = MultiPoint(pts2).convex_hull
    to2d = lambda P: trimesh.transform_points(np.atleast_2d(P), inv)[0][:2]
    mv2, av2 = to2d(MV_C), to2d(AV_C)
    # mitral hole: the sheet's OWN annulus (boundary vertices within 4 mm of the annulus
    # plane), projected into the plate plane, ordered by angle, offset inward by EMBED
    mv_sheet = trimesh.load(os.path.join(FA, "mitral_valve.stl"), process=True)
    e_ = mv_sheet.edges_sorted; u_, c_ = np.unique(e_, axis=0, return_counts=True)
    Bv = mv_sheet.vertices[np.unique(u_[c_ == 1])]
    Bv = Bv[(Bv - MV_C) @ AXIS < 4.0]
    B2 = trimesh.transform_points(Bv, inv)[:, :2]
    order = np.argsort(np.arctan2(B2[:, 1] - mv2[1], B2[:, 0] - mv2[0]))
    annulus_poly = Polygon(B2[order]).buffer(0)
    mv_hole = annulus_poly.buffer(-EMBED).simplify(0.15)
    circle = Point(*mv2).buffer(MV_R - EMBED, 96)
    if mv_hole.geom_type != "Polygon" or mv_hole.area < 0.5 * circle.area:      # guard: fall back to the circle
        mv_hole = circle; hole_kind = "circle_fallback"
    else:
        hole_kind = "D_from_sheet_annulus"
    holes = [mv_hole, Point(*av2).buffer(AV_R - EMBED, 96)]
    plate2d = outer.difference(holes[0]).difference(holes[1])
    if plate2d.geom_type != "Polygon":                        # keep the main piece
        plate2d = max(plate2d.geoms, key=lambda g: g.area)
    plate = trimesh.creation.extrude_polygon(plate2d, THICK)
    plate.apply_transform(to3)                                # back to frame A
    trimesh.repair.fix_normals(plate)

    # ---- checks ----
    # do the orifices actually sit inside the outline? does the plate overlap the muscle rim?
    q = trimesh.proximity.ProximityQuery(myo.simplify_quadric_decimation(face_count=15000))
    ring = lambda c, r: np.array([c + r * (np.cos(t) * np.cross(AXIS, [1, 0, 0]) / np.linalg.norm(np.cross(AXIS, [1, 0, 0]))
                                          + np.sin(t) * np.cross(AXIS, np.cross(AXIS, [1, 0, 0]) / np.linalg.norm(np.cross(AXIS, [1, 0, 0]))))
                                  for t in np.linspace(0, 2 * np.pi, 48, endpoint=False)])
    inside_plate = trimesh.proximity.ProximityQuery(plate)
    mv_ring_in = float((inside_plate.signed_distance(ring(MV_C, MV_R)) > 0).mean())
    av_ring_in = float((inside_plate.signed_distance(ring(AV_C, AV_R)) > 0).mean())
    overlap_pts = plate.sample(4000)
    frac_in_muscle = float((q.signed_distance(overlap_pts) > 0).mean())
    # the REAL test: boundary vertices of the actual (saddle-shaped) mitral sheet near the
    # annulus -- inside the plate, or within the solidified half-thickness of it
    mv = trimesh.load(os.path.join(FA, "mitral_valve.stl"), process=True)
    e = mv.edges_sorted; u_, c_ = np.unique(e, axis=0, return_counts=True)
    B = mv.vertices[np.unique(u_[c_ == 1])]; bd = (B - MV_C) @ AXIS
    ring_real = B[bd < 4.0]; s_real = inside_plate.signed_distance(ring_real)
    real_in = float((s_real > 0).mean()); real_attached = float((s_real > -0.6).mean())
    out = dict(plane_origin_mm=origin.tolist(), normal_basal=normal.tolist(),
               thickness_mm=THICK, apical_start_mm=APICAL_START,
               outline_area_cm2=round(outer.area / 100, 2), plate_area_cm2=round(plate2d.area / 100, 2),
               mitral_hole=hole_kind, mitral_hole_area_cm2=round(mv_hole.area / 100, 2),
               mitral_circle_equivalent_r_mm=round(float(np.sqrt(mv_hole.area / np.pi)), 2), aortic_orifice_r_mm=round(AV_R - EMBED, 2),
               mitral_centre_in_outline=bool(outer.contains(Point(*mv2))),
               aortic_centre_in_outline=bool(outer.contains(Point(*av2))),
               plate_faces=int(len(plate.faces)), plate_watertight=bool(plate.is_watertight),
               plate_volume_mL=round(abs(plate.volume) / 1000, 3),
               mitral_annulus_ring_embedded_frac=round(mv_ring_in, 3),
               aortic_annulus_ring_embedded_frac=round(av_ring_in, 3),
               mitral_sheet_annulus_verts=int(len(ring_real)),
               mitral_sheet_annulus_inside_plate_frac=round(real_in, 3),
               mitral_sheet_annulus_attached_frac_within_0p6mm=round(real_attached, 3),
               mitral_sheet_annulus_axis_range_mm=[round(float(bd.min()), 1), round(float(bd[bd < 4].max()), 1)],
               plate_volume_frac_overlapping_muscle=round(frac_in_muscle, 3))
    plate.export(os.path.join(FA, "av_plane_plate.stl"))
    json.dump(out, open(os.path.join(HERE, "av_plate.json"), "w"), indent=1)
    for k, v in out.items():
        print(f"  {k:<40} {v}")


if __name__ == "__main__":
    main()
