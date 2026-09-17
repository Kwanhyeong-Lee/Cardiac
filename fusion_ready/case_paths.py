# -*- coding: utf-8 -*-
"""One place that knows where a case's files live and what its LV geometry is.

Two layouts:
  * legacy (case 1009, the case everything was developed on): outputs under fusion_ready/CT/{coronary,hires,...}
    and geometry in frame A (valve_refit.json + ct_refine.json translation) -- unchanged behaviour.
  * any other case (or CASE_LAYOUT=cases): outputs under fusion_ready/CT/cases/<case>/{coronary,hires,territories,
    whole_heart} and geometry in WORLD mm (NIfTI affine, RAS) from CT/cases/<case>/case_geometry.json, which
    ct_case_geometry.py derives from the labels alone (MV/AV centres from label contacts, base->apex axis, Otsu).

Every CT script does:   from case_paths import paths, geometry ; P = paths() ; G = geometry()
and uses P["coronary"], P["hires"], ..., G["axis"], G["mv_centre"], G["av_centre"], G["thr_HU"], G["T"].
Env: CASE (default 1009), CARDIAC_DATA (MM-WHS/ct_train), CASE_LAYOUT=cases to force the per-case layout for 1009.
"""
import os, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
MMWHS = os.environ.get("CARDIAC_DATA", "/sessions/vibrant-youthful-hopper/mnt/MM-WHS/ct_train")


def case_id():
    return os.environ.get("CASE", "1009")


def paths(case=None):
    case = case or case_id()
    legacy = (case == "1009" and os.environ.get("CASE_LAYOUT", "legacy") == "legacy")
    base = os.path.join(HERE, "CT") if legacy else os.path.join(HERE, "CT", "cases", case)
    cor = os.path.join(base, "coronary")
    p = dict(case=case, legacy=legacy, base=base, coronary=cor, hires=os.path.join(base, "hires"),
             territories=os.path.join(cor, "territories") if legacy else os.path.join(base, "territories"),
             whole=os.path.join(base, "whole_heart"), geometry_json=os.path.join(base, "case_geometry.json"),
             image=os.path.join(MMWHS, f"ct_train_{case}_image.nii.gz"), label=os.path.join(MMWHS, f"ct_train_{case}_label.nii.gz"))
    p["coronary"] = os.environ.get("CORO_OUT", p["coronary"])
    return p


def geometry(case=None):
    """dict: axis (base->apex, unit), mv_centre, av_centre, mv_r, av_r (mm, in the working frame), thr_HU,
    T (4x4 world->working frame), frame (str), plus the raw json."""
    p = paths(case)
    if p["legacy"]:
        vr = json.load(open(os.path.join(HERE, "valve_refit.json"))); ref = json.load(open(os.path.join(HERE, "CT", "ct_refine.json")))
        T = np.array(ref["world_to_frameA"]["matrix"])
        return dict(axis=np.array(vr["lv_geometry"]["axis_base_to_apex"], float), mv_centre=np.array(vr["design"]["mv_centre_mm"], float), av_centre=np.array(vr["design"]["av_centre_mm"], float),
                    mv_r=float(vr["design"]["mv_annulus_r_mm"]), av_r=float(vr["design"]["av_annulus_r_mm"]), thr_HU=float(ref["otsu_HU"]), T=T, frame="A", raw=None)
    if not os.path.exists(p["geometry_json"]):
        raise FileNotFoundError(f"{p['geometry_json']} missing -- run:  CASE={p['case']} python ct_case_geometry.py")
    g = json.load(open(p["geometry_json"]))
    return dict(axis=np.array(g["axis_base_to_apex"], float), mv_centre=np.array(g["mv_centre_mm"], float), av_centre=np.array(g["av_centre_mm"], float),
                mv_r=float(g["mv_annulus_r_mm"]), av_r=float(g["av_annulus_r_mm"]), thr_HU=float(g["otsu_HU"]), T=np.eye(4), frame="world", raw=g)


def frame_translation(G):
    """the pipelines only ever need the translation part (world -> frame is a pure translation for 1009, identity otherwise)."""
    return np.asarray(G["T"])[:3, 3]


def dist_to(mask_true, sp, coarse_if_more_than=40_000_000):
    """Euclidean distance (mm, float32) from every voxel to the nearest True voxel of `mask_true`.
    Arrays above `coarse_if_more_than` voxels are max-pooled 2x first and the result repeated back
    (+-1 voxel accuracy) -- scipy's EDT needs ~20 bytes/voxel and OOMs the 4 GB sandbox on 0.35 mm CTs."""
    from scipy import ndimage
    m = np.asarray(mask_true, bool); sp = np.asarray(sp, float)
    if m.size <= coarse_if_more_than:
        return ndimage.distance_transform_edt(~m, sampling=sp).astype(np.float32)
    f = 2; sh = m.shape; mp = np.pad(m, [(0, (-n) % f) for n in sh])
    mp = mp.reshape(mp.shape[0] // f, f, mp.shape[1] // f, f, mp.shape[2] // f, f).any(axis=(1, 3, 5))
    d2 = ndimage.distance_transform_edt(~mp, sampling=sp * f).astype(np.float32); del mp
    d = np.repeat(np.repeat(np.repeat(d2, f, 0), f, 1), f, 2); del d2
    return np.ascontiguousarray(d[:sh[0], :sh[1], :sh[2]])
