# -*- coding: utf-8 -*-
"""Lost-core casting set for a silicone LV flow phantom -- the CAD deliverable.

WHY LOST-CORE. A flow phantom needs the LV as a CAVITY inside a clear silicone block, with
tubing ports where the mitral inflow and aortic outflow are. A two-part negative mould casts
a solid replica, which is the wrong object. The standard route is:
    1. print the CORE  = blood-pool solid + two port cylinders, in water-soluble PVA (or wax)
    2. seat the core in the MOULD BOX by its port stubs, pour silicone, cure
    3. dissolve the core -> silicone block with the patient's LV cavity and two ports
The result plugs into a pulsatile pump and gives a bench counterpart to the CFD/PINN work.

PARTS (frame A, mm; every dimension is a named constant below)
    core        LV_bloodpool (PRINT set, 39,992 f, watertight) U mitral port U aortic port.
                Ports are cylinders along the LV axis from the two annulus centres, so both
                exit the same (basal) face and the core can be held by two bores.
    mould box   rectangular shell around the core with WALL-thick walls, open on the face
                opposite the ports (pour side), two through-bores for the port stubs with
                CLEAR radial clearance, and a fillet-free flat bottom for printing.
    check       the box bores clear the port stubs; the core does not touch the box walls;
                silicone wall thickness around the cavity >= MARGIN everywhere.

Booleans by manifold3d (installed under /tmp/pylibs). Outputs -> fusion_ready/PHANTOM/.
Change a constant, rerun; nothing is hand-modelled.
"""
import json, os, warnings
import numpy as np, trimesh
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "PHANTOM"); os.makedirs(OUT, exist_ok=True)
d = json.load(open(os.path.join(HERE, "valve_refit.json")))
AXIS = np.array(d["lv_geometry"]["axis_base_to_apex"])
MV_C = np.array(d["design"]["mv_centre_mm"]); AV_C = np.array(d["design"]["av_centre_mm"])

# ---- design constants (mm) ----
PORT_R_MV, PORT_R_AV = 9.5, 7.9      # 19 mm (3/4") and 15.8 mm (5/8") bores = 2.84 / 1.96 cm2, the same
                                      # effective areas lv_cfd_patient uses (mv_radius 9.4, av_radius 7.8 mm)
PORT_LEN = 45.0                       # stub length beyond the annulus, basal
PORT_SINK = 6.0                       # how far the stub starts inside the cavity (overlap for union)
MARGIN = 15.0                         # minimum silicone around the cavity
WALL = 4.0                            # mould box wall
CLEAR = 0.4                           # radial clearance stub -> bore (PVA prints oversize)
POUR_LIP = 8.0                        # extra height on the open (pour) side above the core
FOOT, FOOT_H = 6.0, 32.0              # 12 mm square corner feet, taller than the stub protrusion


def cyl(c0, axis_dir, r, length):
    """Cylinder from c0 along axis_dir (unit) for `length`."""
    m = trimesh.creation.cylinder(radius=r, height=length, sections=96)
    # trimesh cylinder is centred at origin along +z; move to start at c0
    T = trimesh.geometry.align_vectors([0, 0, 1], axis_dir)
    T[:3, 3] = c0 + axis_dir * (length / 2.0)
    m.apply_transform(T); return m


def main():
    lv = trimesh.load(os.path.join(HERE, "PRINT", "frame_A_patient", "lv_surface.stl"), process=True)
    basal = -AXIS
    # --- core ---
    p_mv = cyl(MV_C - basal * PORT_SINK, basal, PORT_R_MV, PORT_LEN + PORT_SINK)
    p_av = cyl(AV_C - basal * PORT_SINK, basal, PORT_R_AV, PORT_LEN + PORT_SINK)
    core = trimesh.boolean.union([lv, p_mv, p_av], engine="manifold")
    assert core.is_watertight and len(core.split()) == 1, "core not a single solid"

    # --- mould box, aligned to the LV axis so the ports exit one flat face ---
    # build in a frame where +z = basal (ports), then transform back
    R = trimesh.geometry.align_vectors(basal, [0, 0, 1])      # frame A -> box frame
    core_b = core.copy(); core_b.apply_transform(R)
    lv_b = lv.copy(); lv_b.apply_transform(R)
    lo, hi = lv_b.bounds
    stub_top = core_b.bounds[1][2]                             # z of the port ends
    # box interior: LV bbox +MARGIN laterally and apically; basal face at the annulus height
    # + MARGIN so the silicone covers the base too; ports pass through that face
    inner_lo = np.array([lo[0] - MARGIN, lo[1] - MARGIN, lo[2] - MARGIN])
    inner_hi = np.array([hi[0] + MARGIN, hi[1] + MARGIN, hi[2] + MARGIN])
    outer_lo = inner_lo - WALL; outer_hi = inner_hi + WALL
    # open face = apical (-z) side?  No: pouring must be opposite the ports so the stubs
    # hold the core; ports exit +z (basal), so the pour opening is the -z face and the box
    # is printed upside down. Add POUR_LIP on that side.
    outer_lo[2] -= POUR_LIP
    inner_lo[2] = outer_lo[2] - 1.0                            # cut clean THROUGH the -z face (open side)
    outer = trimesh.creation.box(extents=outer_hi - outer_lo, transform=trimesh.transformations.translation_matrix((outer_lo + outer_hi) / 2))
    inner = trimesh.creation.box(extents=inner_hi - inner_lo, transform=trimesh.transformations.translation_matrix((inner_lo + inner_hi) / 2))
    box = trimesh.boolean.difference([outer, inner], engine="manifold")
    # feet on the port face: during the pour the box stands port-face DOWN with the stubs
    # protruding through it, so it needs FOOT_H > stub protrusion to sit flat on the bench
    feet = []
    for sx in (0, 1):
        for sy in (0, 1):
            cx = outer_lo[0] + FOOT + (outer_hi[0] - outer_lo[0] - 2 * FOOT) * sx
            cy = outer_lo[1] + FOOT + (outer_hi[1] - outer_lo[1] - 2 * FOOT) * sy
            feet.append(trimesh.creation.box(extents=[2 * FOOT, 2 * FOOT, FOOT_H],
                        transform=trimesh.transformations.translation_matrix([cx, cy, outer_hi[2] + FOOT_H / 2 - 0.5])))
    box = trimesh.boolean.union([box] + feet, engine="manifold")
    # bores for the two stubs through the +z wall
    zc = inner_hi[2] + WALL / 2.0
    bores = []
    for c, r in [(MV_C, PORT_R_MV), (AV_C, PORT_R_AV)]:
        cb = trimesh.transform_points(c[None], R)[0]
        b = trimesh.creation.cylinder(radius=r + CLEAR, height=WALL + 2.0, sections=96,
                                      transform=trimesh.transformations.translation_matrix([cb[0], cb[1], zc]))
        bores.append(b)
    box = trimesh.boolean.difference([box] + bores, engine="manifold")
    assert box.is_watertight, "box not watertight"

    # --- checks in box frame ---
    q_box = trimesh.proximity.ProximityQuery(box)
    core_pts = core_b.sample(6000)
    touch = float((q_box.signed_distance(core_pts) > -0.05).mean())      # core inside box wall material?
    # silicone thickness: distance from cavity surface to box inner wall, min over cavity
    inner_shell = trimesh.creation.box(extents=inner_hi - inner_lo, transform=trimesh.transformations.translation_matrix((inner_lo + inner_hi) / 2))
    q_in = trimesh.proximity.ProximityQuery(inner_shell)
    sil = np.abs(q_in.signed_distance(lv_b.sample(4000)))
    # do stubs protrude past the box outer face, and do the feet clear them?
    protrude = float(stub_top - outer_hi[2])
    # is the pour side really open? a ray along +z from below the box must not hit a floor
    open_face = not bool(box.contains([[(inner_lo[0] + inner_hi[0]) / 2, (inner_lo[1] + inner_hi[1]) / 2, outer_lo[2] + 0.5]])[0])
    # and the port face must be CLOSED except for the bores
    closed_face = bool(box.contains([[(inner_lo[0] + inner_hi[0]) / 2 + 30.0, (inner_lo[1] + inner_hi[1]) / 2 + 25.0, inner_hi[2] + WALL / 2]])[0])

    # --- back to frame A and export ---
    Rinv = np.linalg.inv(R)
    box_A = box.copy(); box_A.apply_transform(Rinv)
    core.export(os.path.join(OUT, "core_LV_with_ports.stl"))
    box_A.export(os.path.join(OUT, "mould_box.stl"))
    # also a version of the box in its own print orientation (open face up = -z up)
    box_print = box.copy(); box_print.apply_transform(trimesh.transformations.rotation_matrix(np.pi, [1, 0, 0]))
    box_print.apply_translation(-box_print.bounds[0])
    box_print.export(os.path.join(OUT, "mould_box_PRINT_ORIENTED.stl"))
    core_print = core_b.copy(); core_print.apply_translation(-core_print.bounds[0])
    core_print.export(os.path.join(OUT, "core_PRINT_ORIENTED.stl"))

    rep = dict(
        constants=dict(PORT_R_MV=PORT_R_MV, PORT_R_AV=PORT_R_AV, PORT_LEN=PORT_LEN, MARGIN=MARGIN,
                       WALL=WALL, CLEAR=CLEAR, POUR_LIP=POUR_LIP, FOOT=FOOT, FOOT_H=FOOT_H),
        procedure=["print core in PVA (or wax); print box in PLA/PETG",
                   "stand box on its feet, port face down; drop core stubs through the two bores",
                   "seal the 0.4 mm stub clearance from outside with hot glue or clay",
                   "degas and pour clear silicone (e.g. Ecoflex/Sylgard, ~0.95 L) to MARGIN above the apex",
                   "cure, lift block out, cut stubs flush, dissolve core in warm water (PVA)",
                   "push barb fittings into the 19 mm (mitral, inflow) and 12.7 mm (aortic, outflow) ports"],
        core=dict(faces=int(len(core.faces)), watertight=bool(core.is_watertight),
                  volume_mL=round(abs(core.volume) / 1000, 2), extent_mm=[round(float(x), 1) for x in core.extents],
                  note="print in PVA/wax; this is the cavity + tubing ports"),
        mould_box=dict(faces=int(len(box.faces)), watertight=bool(box.is_watertight),
                       outer_extent_mm=[round(float(x), 1) for x in (outer_hi - outer_lo)],
                       inner_extent_mm=[round(float(x), 1) for x in (inner_hi - inner_lo)],
                       silicone_volume_mL=round(float(np.prod(inner_hi - inner_lo) - abs(lv.volume)) / 1000, 0),
                       bores_mm=dict(mitral=round(2 * (PORT_R_MV + CLEAR), 2), aortic=round(2 * (PORT_R_AV + CLEAR), 2))),
        checks=dict(core_touching_box_wall_frac=round(touch, 4),
                    silicone_min_mm=round(float(sil.min()), 1), silicone_p05_mm=round(float(np.percentile(sil, 5)), 1),
                    stubs_protrude_past_outer_face_mm=round(protrude, 1),
                    feet_clear_stubs=bool(FOOT_H > protrude + 2.0),
                    pour_face_open=bool(open_face), port_face_closed=bool(closed_face),
                    PASS=bool(touch < 0.001 and sil.min() >= MARGIN - 0.5 and protrude > 5.0
                              and FOOT_H > protrude + 2.0 and open_face and closed_face)),
        files=["core_LV_with_ports.stl", "mould_box.stl", "core_PRINT_ORIENTED.stl", "mould_box_PRINT_ORIENTED.stl"])
    json.dump(rep, open(os.path.join(OUT, "phantom_design.json"), "w"), indent=1)
    for k in ("core", "mould_box", "checks"):
        print(k, rep[k])


if __name__ == "__main__":
    main()
