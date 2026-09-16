# -*- coding: utf-8 -*-
"""Paper 2 v3 — trending analysis (PROTOCOL.md §6, entry of 2026-07-30).

Absolute agreement and trending ability are distinct. A cardiac output method can fail
Bland-Altman and still be clinically useful if it tracks the direction and size of
changes, which is why four-quadrant concordance and polar-plot agreement are reported
alongside percentage error in this literature.

The v2 window extraction already gives ~30 time-ordered windows per patient, so this
needs no new data.

Definitions
-----------
Four-quadrant concordance
    For each consecutive pair of windows within a patient, take the change in the
    reference (dRef) and in the method (dMethod). Pairs with |dRef| below an exclusion
    zone are discarded, because near-zero changes are dominated by noise and their
    direction is uninformative. Concordance is the share of remaining pairs in which the
    two changes share a sign. Conventional threshold: 92%.

Polar plot
    Each change pair is written in polar form; the angle from the identity line measures
    disagreement in the *size* of the change. Reported as mean angular bias and radial
    limits of agreement. Conventional threshold: radial LoA within +-30 degrees.

Both are computed within patient and then pooled, so between-patient offsets — the very
thing Bland-Altman measures — cannot contribute.
"""
import numpy as np
import pandas as pd


def _pairs(df, ref_col, test_col, group="caseid", time="t_win_start"):
    """Consecutive within-patient change pairs."""
    out = []
    for g, d in df.sort_values([group, time]).groupby(group):
        r = d[ref_col].to_numpy(float)
        t = d[test_col].to_numpy(float)
        ok = np.isfinite(r) & np.isfinite(t)
        r, t = r[ok], t[ok]
        if len(r) < 2:
            continue
        out.append(np.column_stack([np.diff(r), np.diff(t), np.full(len(r) - 1, g)]))
    return np.vstack(out) if out else np.empty((0, 3))


def four_quadrant(df, ref_col, test_col, exclusion_frac=0.15, **kw):
    """Concordance rate outside a central exclusion zone.

    `exclusion_frac` is a fraction of the reference mean, following the usual practice of
    setting the zone relative to the measurement scale rather than to an absolute value.
    """
    p = _pairs(df, ref_col, test_col, **kw)
    if len(p) < 20:
        return dict(note="too few change pairs", n=len(p))
    ref_mean = np.nanmean(df[ref_col])
    zone = exclusion_frac * ref_mean
    keep = np.abs(p[:, 0]) >= zone
    if keep.sum() < 20:
        return dict(note="too few pairs outside exclusion zone", n=int(keep.sum()),
                    zone=round(float(zone), 3))
    dr, dt = p[keep, 0], p[keep, 1]
    conc = float(np.mean(np.sign(dr) == np.sign(dt)))
    # patient-clustered bootstrap: resample patients, not pairs
    cases = np.unique(p[keep, 2])
    rng = np.random.default_rng(0)
    boots = []
    for _ in range(2000):
        pick = rng.choice(cases, len(cases), replace=True)
        idx = np.concatenate([np.where(p[keep, 2] == c)[0] for c in pick])
        boots.append(np.mean(np.sign(dr[idx]) == np.sign(dt[idx])))
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return dict(n_pairs=int(keep.sum()), n_patients=int(len(cases)),
                exclusion_zone=round(float(zone), 3),
                concordance=round(conc, 4), ci=[round(float(lo), 4), round(float(hi), 4)],
                meets_92pct=bool(lo >= 0.92))


def polar(df, ref_col, test_col, exclusion_frac=0.15, **kw):
    """Mean angular bias and radial limits of agreement, in degrees."""
    p = _pairs(df, ref_col, test_col, **kw)
    if len(p) < 20:
        return dict(note="too few change pairs", n=len(p))
    ref_mean = np.nanmean(df[ref_col])
    zone = exclusion_frac * ref_mean
    dr, dt = p[:, 0], p[:, 1]
    radius = np.sqrt(dr ** 2 + dt ** 2) / np.sqrt(2)
    keep = radius >= zone
    if keep.sum() < 20:
        return dict(note="too few pairs outside exclusion zone", n=int(keep.sum()))
    dr, dt = dr[keep], dt[keep]
    # angle from the line of identity; positive means the method over-reads the change
    ang = np.degrees(np.arctan2(dt - dr, (dt + dr) / np.sqrt(2)))
    ang = (ang + 180) % 360 - 180
    bias, sd = float(np.mean(ang)), float(np.std(ang, ddof=1))
    return dict(n_pairs=int(keep.sum()), angular_bias=round(bias, 2),
                radial_loa=[round(bias - 1.96 * sd, 1), round(bias + 1.96 * sd, 1)],
                within_30deg=bool(abs(bias - 1.96 * sd) <= 30 and abs(bias + 1.96 * sd) <= 30))


def report(df, ref_col, test_col, label="", **kw):
    return {"label": label,
            "four_quadrant": four_quadrant(df, ref_col, test_col, **kw),
            "polar": polar(df, ref_col, test_col, **kw)}
