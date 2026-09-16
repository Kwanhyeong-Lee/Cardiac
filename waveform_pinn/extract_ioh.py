# -*- coding: utf-8 -*-
"""Paper 2 — exploratory endpoint: intraoperative hypotension (PROTOCOL.md §3.3.2).

Event  : MAP < 65 mmHg sustained >= 60 s (Solar8000/ART_MBP, native 0.5 Hz)
Anchors: every ANCHOR_MIN minutes; anchors already in hypotension are excluded
Windows: waveform morphology from the ANCHOR_WIN minutes preceding each anchor
Labels : hypotension onset within 5 / 10 / 15 min after the anchor

MANDATORY CONTROL (PROTOCOL.md §3.3.2). Every row also carries a `ctrl_*` block
derived from MAP alone (current level, slope, variability, time below thresholds).
Published critiques of commercial hypotension prediction show that most apparent
performance is attributable to the current pressure level and to how anchors are
selected. The reported result is the increment of the waveform model over a model
fitted on the `ctrl_*` block only — never a raw AUC.

Selection artefact, stated explicitly: excluding anchors that are already hypotensive
means the retained anchors are enriched for pressures near, but above, the threshold.
This inflates apparent performance for any model that reads the current pressure. The
control block is what makes that inflation measurable rather than hidden.

Usage:  python3 extract_ioh.py [n_cases] [start_index]
"""
import os, sys, time, warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
import vitaldb

import extract_features2 as E

HERE = os.path.dirname(os.path.abspath(__file__))
FS = 100.0
MBP_DT = 2.0          # s -- Solar8000/ART_MBP native interval (0.5 Hz).
                      # Requesting 1 s returns 50% NaN, which silently breaks every
                      # sustained-run test; verified against the API on 2026-07-30.
MBP_RANGE = (20.0, 200.0)   # physiological filter: raw MBP contains values from -70 to 346
MAP_THR = 65.0        # mmHg
MIN_DUR = 60          # s, sustained
ANCHOR_MIN = 5.0      # minutes between anchors
ANCHOR_WIN = 3.0      # minutes of waveform preceding each anchor
HORIZONS = (5, 10, 15)   # minutes
MAX_ANCHORS = 40      # per case, so one long operation cannot dominate the set
LEAD_IN = 10.0        # minutes skipped at the start of the record


def load_mbp(cid):
    """Mean arterial pressure on a uniform MBP_DT grid, physiologically filtered.
    Short dropouts (<= 3 samples) are bridged so they do not split sustained runs."""
    v = vitaldb.load_case(int(cid), ["Solar8000/ART_MBP"], MBP_DT)
    if v is None or v.size == 0:
        return None
    m = v[:, 0].astype(float)
    m[~(np.isfinite(m) & (m > MBP_RANGE[0]) & (m < MBP_RANGE[1]))] = np.nan
    return pd.Series(m).interpolate(limit=3, limit_area="inside").to_numpy()


def hypotension_mask(mbp, dt=MBP_DT):
    """True where MAP is below threshold as part of a run lasting >= MIN_DUR seconds."""
    low = np.isfinite(mbp) & (mbp < MAP_THR)
    out = np.zeros_like(low)
    i, n = 0, len(low)
    need = int(np.ceil(MIN_DUR / dt))
    while i < n:
        if low[i]:
            j = i
            while j < n and low[j]:
                j += 1
            if j - i >= need:
                out[i:j] = True
            i = j
        else:
            i += 1
    return out


def control_features(mbp, t_idx, dt=MBP_DT):
    """MAP-only predictors — the control model's entire input."""
    w5 = mbp[max(0, t_idx - int(300 / dt)):t_idx + 1]
    w5 = w5[np.isfinite(w5)]
    if w5.size < int(120 / dt):        # require >= 2 min of usable MAP
        return None
    x = np.arange(w5.size) * dt
    slope = float(np.polyfit(x, w5, 1)[0]) * 60.0          # mmHg/min
    w15 = mbp[max(0, t_idx - int(900 / dt)):t_idx + 1]
    w15 = w15[np.isfinite(w15)]
    return dict(
        ctrl_map_now=float(w5[-1]),
        ctrl_map_mean5=float(w5.mean()),
        ctrl_map_min5=float(w5.min()),
        ctrl_map_sd5=float(w5.std()),
        ctrl_map_slope=slope,
        ctrl_map_mean15=float(w15.mean()) if w15.size else np.nan,
        ctrl_frac_below70=float((w5 < 70).mean()),
        ctrl_frac_below75=float((w5 < 75).mean()),
    )


def process_case(cid):
    mbp = load_mbp(cid)
    if mbp is None or np.isfinite(mbp).sum() < int(20 * 60 / MBP_DT):
        return []
    hyp = hypotension_mask(mbp)

    art = vitaldb.load_case(int(cid), ["SNUADC/ART"], 1 / FS)
    if art is None or art.size == 0:
        return []
    a = art[:, 0].astype(float)

    dur_s = int(min(len(mbp) * MBP_DT, len(a) / FS))
    anchors = np.arange(int(LEAD_IN * 60), dur_s - max(HORIZONS) * 60,
                        int(ANCHOR_MIN * 60), dtype=int)     # seconds
    if anchors.size == 0:
        return []
    if anchors.size > MAX_ANCHORS:            # even thinning, not truncation
        anchors = anchors[np.linspace(0, anchors.size - 1, MAX_ANCHORS).astype(int)]

    rows = []
    for t in anchors:                      # t in seconds
        ti = int(t / MBP_DT)               # index on the MBP grid
        if ti >= len(hyp) or hyp[ti] or not np.isfinite(mbp[ti]):
            continue                       # already hypotensive -> excluded
        ctrl = control_features(mbp, ti)
        if ctrl is None:
            continue
        seg = a[int((t - ANCHOR_WIN * 60) * FS):int(t * FS)]
        seg = seg[np.isfinite(seg) & (seg > E.PHYS[0]) & (seg < E.PHYS[1])]
        if len(seg) < FS * 60:
            continue
        mb, sd, nb = E.ensemble_beat(seg, E.detect_beats(seg))
        if mb is None:
            continue
        f = E.morphology(mb)
        if f is None:
            continue
        row = dict(caseid=int(cid), t_anchor=int(t), n_beats=int(nb),
                   beat_sd=float(np.median(sd)), **f, **ctrl)
        for hz in HORIZONS:
            fut = hyp[ti + 1: ti + 1 + int(hz * 60 / MBP_DT)]
            row[f"ioh_{hz}"] = int(fut.any()) if fut.size else np.nan
        rows.append(row)
    return rows


if __name__ == "__main__":
    coh = pd.read_csv(os.path.join(HERE, "cohort4.csv"))
    ids = coh.loc[coh.has_mbp.astype(bool), "caseid"].astype(int).tolist() \
        if "has_mbp" in coh else coh.caseid.astype(int).tolist()
    n = int(sys.argv[1]) if len(sys.argv) > 1 else len(ids)
    start = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    ids = ids[start:start + n]
    print(f"IOH extraction over {len(ids)} cases "
          f"(anchor every {ANCHOR_MIN} min, max {MAX_ANCHORS}/case)", flush=True)

    out, t0 = [], time.time()
    for k, cid in enumerate(ids):
        try:
            out.extend(process_case(cid))
        except Exception:
            pass
        if k % 20 == 0 and k:
            el = time.time() - t0
            print(f"  {k}/{len(ids)}  rows={len(out)}  {el:.0f}s"
                  f"  eta={el/k*(len(ids)-k):.0f}s", flush=True)

    if not out:
        print("no anchors extracted"); sys.exit(1)
    df = pd.DataFrame(out)
    p = os.path.join(HERE, f"ioh_anchors_{start}.csv")
    df.to_csv(p, index=False)
    print(f"\nsaved {len(df)} anchors from {df.caseid.nunique()} cases "
          f"-> {os.path.basename(p)}")
    for hz in HORIZONS:
        c = df[f"ioh_{hz}"]
        print(f"  ioh_{hz:2d}min  positive {int(c.sum()):5d} / {int(c.notna().sum()):5d}"
              f"  ({100*c.mean():.1f}%)")
