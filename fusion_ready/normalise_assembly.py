# -*- coding: utf-8 -*-
"""Bring the 13-structure cardiac assembly into one unit system and document which parts
actually share a coordinate frame.

WHY THIS EXISTS. `cardiac_assembly_summary.json` records 13 structures as an assembly. They
are not one. A full audit (2026-09-15) found:

    units    7 files in METRES (lv_surface, both valves, aortic_root, both papillary
             muscles, chordae) and 6 in MILLIMETRES (*_stacom), in the same directory
    frames   at least four incompatible coordinate frames
    STACOM   the project's own registration validation reports PA surface RMS 28.2 mm,
             RV-LV minimum gap 34.9 mm (they share the septum; should be ~0), and 3 of 5
             anatomical-direction checks failing

Nothing here is silently "fixed". Every structure is converted to mm and cleaned, then
sorted into a frame group with an explicit status. Only Frame A is asserted to be a
coherent, patient-anatomy assembly.

    frame_A_patient/          LV + mitral + aortic valve   -- same CT frame, USE
    frame_B_papillary/        papillary muscles + chordae  -- own frame; recovery attempted
    frame_C_stacom_UNREGISTERED/  right heart + vessels    -- atlas frame, NOT anatomical
    frame_D_orphan/           aortic_root                  -- position unexplained

Outputs are written in millimetres, one common translation applied to Frame A only so the
LV centroid sits at the origin (Fusion imports land sensibly). Per-part centring is NEVER
applied -- it would destroy relative placement.

Usage:  PYTHONPATH=/tmp/pylibs python3 normalise_assembly.py
"""
import json, os, itertools, warnings
import numpy as np, trimesh
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.dirname(HERE), "lv_cfd_anatomical", "constant", "triSurface")

GROUPS = {
    "frame_A_patient": ["lv_surface", "mitral_valve", "aortic_valve"],
    "frame_B_papillary": ["anterolateral_pm", "posteromedial_pm", "papillary_muscles",
                          "chordae_al", "chordae_pm", "chordae_combined"],
    "frame_C_stacom_UNREGISTERED": ["rv_stacom", "ra_stacom", "pa_stacom", "pv_stacom",
                                    "laa_stacom", "coronary_stacom"],
    "frame_D_orphan": ["aortic_root"],
}
STATUS = {
    "frame_A_patient": "coherent patient CT frame (MM-WHS case 1009). Valve *seating* not "
                       "yet verified: MV-AV centroid separation 48 mm is large for two "
                       "annuli sharing the aortomitral curtain (typ. 20-30 mm).",
    "frame_B_papillary": "internally consistent, but ~260 mm from the LV. Derived from the "
                         "same CT, so a recoverable transform should exist; see "
                         "pm_recovery.json for what was tried.",
    "frame_C_stacom_UNREGISTERED": "STACOM2025 atlas frame. Registration to the patient "
                                   "FAILED its own validation (RMS 28.2 mm, RV-LV gap "
                                   "34.9 mm). Visual/placeholder use only.",
    "frame_D_orphan": "x = +204 mm while the LV sits at x = -37 mm. Origin of the offset "
                      "unknown. Do not use until explained.",
}


def load_mm(name):
    m = trimesh.load(os.path.join(SRC, name + ".stl"), process=True)
    m.update_faces(m.nondegenerate_faces())
    m.update_faces(m.unique_faces())
    m.remove_unreferenced_vertices()
    unit = "m" if float(np.max(m.extents)) < 1.0 else "mm"
    if unit == "m":
        m.apply_scale(1000.0)
    trimesh.repair.fix_normals(m)
    return m, unit


def describe(m):
    return dict(faces=int(len(m.faces)), vertices=int(len(m.vertices)),
                components=int(len(m.split(only_watertight=False))),
                watertight=bool(m.is_watertight),
                volume_mL=round(float(abs(m.volume)) / 1000, 2) if m.is_watertight else None,
                area_cm2=round(float(m.area) / 100, 2),
                centre_mm=[round(float(v), 2) for v in m.bounds.mean(0)],
                extent_mm=[round(float(v), 2) for v in m.extents])


def main():
    manifest = {"units_out": "mm", "groups": {}}
    meshes = {}
    for grp, names in GROUPS.items():
        for n in names:
            try:
                m, unit = load_mm(n)
            except Exception as e:
                manifest.setdefault("skipped", {})[n] = f"{type(e).__name__}: {e}"
                continue
            meshes[n] = (grp, m, unit)

    # one common offset for Frame A: LV centroid -> origin. Applied to A only.
    lv = meshes["lv_surface"][1]
    offset_A = -lv.bounds.mean(0)

    for grp, names in GROUPS.items():
        outdir = os.path.join(HERE, grp)
        os.makedirs(outdir, exist_ok=True)
        entry = {"status": STATUS[grp], "parts": {}}
        if grp == "frame_A_patient":
            entry["common_offset_mm"] = [round(float(v), 3) for v in offset_A]
        for n in names:
            if n not in meshes:
                continue
            _, m, unit = meshes[n]
            mm = m.copy()
            if grp == "frame_A_patient":
                mm.apply_translation(offset_A)
            mm.export(os.path.join(outdir, n + ".stl"))
            d = describe(mm)
            d["source_unit"] = unit
            entry["parts"][n] = d
        manifest["groups"][grp] = entry

    json.dump(manifest, open(os.path.join(HERE, "MANIFEST.json"), "w"), indent=1)

    # ---- Frame B recovery attempt: can a rigid axis-permutation + translation put the
    #      papillary muscles inside the LV cavity? Reported whatever it shows. ----
    lvA = meshes["lv_surface"][1].copy(); lvA.apply_translation(offset_A)
    lvA = lvA.simplify_quadric_decimation(face_count=6000)   # coarse proxy is enough
    pm = meshes["papillary_muscles"][1].copy()
    pts = pm.vertices[::150]                                  # ~850 sample points
    best = None
    trials = []
    for perm in itertools.permutations(range(3)):
        for signs in itertools.product([1, -1], repeat=3):
            R = np.zeros((3, 3))
            for i, (p, s) in enumerate(zip(perm, signs)):
                R[i, p] = s
            if np.linalg.det(R) < 0:
                continue                      # no reflections: anatomy is chiral
            q = pts @ R.T
            q = q - q.mean(0) + lvA.bounds.mean(0)   # translate to LV centre
            inside = float(lvA.contains(q).mean())
            trials.append({"perm": list(perm), "signs": list(signs), "inside": round(inside, 4)})
            if best is None or inside > best["inside"]:
                best = trials[-1]
    trials.sort(key=lambda t: -t["inside"])
    rec = {
        "method": "24 proper rotations (axis permutation x sign, det=+1) + translation of PM "
                  "centroid to LV centroid; score = fraction of PM vertices inside LV",
        "best": best, "top5": trials[:5],
        # A single threshold on the best score is not evidence: the metric must also
        # DISCRIMINATE between rotations. Require the best to beat the 5th-best by >= 0.25,
        # i.e. the right rotation puts the PMs inside and wrong ones clearly do not.
        "verdict": ("RECOVERED -- apply best rotation then translate"
                    if (best["inside"] > 0.85 and best["inside"] - trials[4]["inside"] >= 0.25)
                    else "NOT RECOVERED -- no proper rotation + translation places the "
                         "papillary muscles inside the LV. The frames differ by more than "
                         "an axis relabelling; a full rigid/affine registration against the "
                         "endocardium is needed, and that requires knowing which PM surface "
                         "is the attachment."),
    }
    json.dump(rec, open(os.path.join(HERE, "pm_recovery.json"), "w"), indent=1)
    manifest["frame_B_recovery"] = rec["verdict"]

    json.dump(manifest, open(os.path.join(HERE, "MANIFEST.json"), "w"), indent=1)

    print(f"{'group / part':<44}{'unit':>5}{'faces':>9}{'comp':>5}{'WT':>4}  centre(mm)               extent(mm)")
    for grp, e in manifest["groups"].items():
        print(f"\n[{grp}]  {e['status'][:70]}...")
        for n, d in e["parts"].items():
            c, x = d["centre_mm"], d["extent_mm"]
            print(f"  {n:<42}{d['source_unit']:>5}{d['faces']:>9,}{d['components']:>5}"
                  f"{'Y' if d['watertight'] else 'N':>4}  [{c[0]:7.1f}{c[1]:7.1f}{c[2]:7.1f}]"
                  f"  [{x[0]:6.1f}{x[1]:6.1f}{x[2]:6.1f}]")
    print(f"\nFrame B recovery: {rec['verdict']}")
    print(f"  best trial: {best}")


if __name__ == "__main__":
    main()
