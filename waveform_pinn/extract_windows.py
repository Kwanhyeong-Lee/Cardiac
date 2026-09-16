# -*- coding: utf-8 -*-
"""Paper 2 v2 — multiple analysis windows per case (PROTOCOL.md §6, entry of 2026-07-30).

v1 used one 3-minute window per case: 866 training rows for a 56,000-parameter network,
with hours of waveform per case discarded. This extracts an anchor every ANCHOR_MIN
minutes and pairs each window's morphology with the reference values measured over that
same window, giving roughly 30-40 rows per case.

Grouping is by `caseid` throughout, so `GroupShuffleSplit` still guarantees that no
patient appears on both sides of a split. The extra rows add within-patient variation,
not extra patients: the effective number of independent subjects is unchanged, and every
confidence interval must still be computed at the patient level.

Usage:  python3 extract_windows.py [n_cases] [start_index]
"""
import os, sys, time, warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
import vitaldb

import extract_features2 as E

HERE = os.path.dirname(os.path.abspath(__file__))
FS = E.FS
WIN_MIN = 3.0          # window length, minutes
ANCHOR_MIN = 5.0       # spacing between window starts, minutes
MAX_WIN = 40           # per case, so one long operation cannot dominate the set
LEAD_IN = 5.0          # minutes skipped at the start of the record


def process_case(cid, tier):
    art = vitaldb.load_case(int(cid), ["SNUADC/ART"], 1 / FS)
    if art is None or art.size == 0:
        return []
    a = art[:, 0].astype(float)
    refs = vitaldb.load_case(int(cid), E.REF_TRACKS, 1)
    if refs is None or refs.size == 0:
        return []

    dur_s = int(min(len(a) / FS, len(refs)))
    starts = np.arange(int(LEAD_IN * 60), dur_s - int(WIN_MIN * 60),
                       int(ANCHOR_MIN * 60), dtype=int)
    if starts.size == 0:
        return []
    if starts.size > MAX_WIN:                      # even thinning, not truncation
        starts = starts[np.linspace(0, starts.size - 1, MAX_WIN).astype(int)]

    def med(j, s, e):
        if j >= refs.shape[1]:
            return np.nan
        c = refs[s:e, j]
        c = c[np.isfinite(c) & (c > 0)]
        return float(np.median(c)) if c.size >= 10 else np.nan

    rows = []
    for t in starts:
        seg = a[int(t * FS):int((t + WIN_MIN * 60) * FS)]
        seg = seg[np.isfinite(seg) & (seg > E.PHYS[0]) & (seg < E.PHYS[1])]
        if len(seg) < FS * 60:
            continue
        onsets = E.detect_beats(seg)
        mb, sd, nb = E.ensemble_beat(seg, onsets)
        if mb is None:
            continue
        f = E.morphology(mb)
        if f is None:
            continue
        rr = np.diff(onsets) / FS
        rr = rr[(rr > 0.3) & (rr < 2.0)]
        if len(rr) < 5:
            continue

        s, e = int(t), int(t + WIN_MIN * 60)
        co_ev, sv_ev, co_vg, sv_vg = med(0, s, e), med(1, s, e), med(2, s, e), med(3, s, e)
        co_pc = co_ev if np.isfinite(co_ev) else co_vg
        sv_pc = sv_ev if np.isfinite(sv_ev) else sv_vg
        co_td = med(4, s, e)
        if not (np.isfinite(co_pc) or np.isfinite(co_td)):
            continue                                # no reference in this window
        cvp = med(8, s, e)
        cvp = cvp if np.isfinite(cvp) else (med(9, s, e) if np.isfinite(med(9, s, e)) else 0.0)

        row = dict(caseid=int(cid), tier=tier, t_win_start=int(t), n_beats=int(nb),
                   beat_sd=float(np.median(sd)), HR=60.0 / float(np.median(rr)), **f,
                   CO_pc=co_pc, SV_pc=sv_pc, CO_td=co_td,
                   EDV=med(5, s, e), ESV=med(6, s, e), RVEF=med(7, s, e), CVP=cvp)
        if np.isfinite(row["EDV"]) and np.isfinite(row["ESV"]):
            row["SV_vol"] = row["EDV"] - row["ESV"]
        co_ref = co_td if np.isfinite(co_td) else co_pc
        row.update(E.windkessel(mb, f, cvp, co_ref))
        rows.append(row)
    return rows


if __name__ == "__main__":
    coh = pd.read_csv(os.path.join(HERE, "cohort4.csv"))
    coh = coh[coh.tier != "DROP"].reset_index(drop=True)
    n = int(sys.argv[1]) if len(sys.argv) > 1 else len(coh)
    start = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    sub = coh.iloc[start:start + n]
    print(f"v2 window extraction over {len(sub)} cases "
          f"(window {WIN_MIN} min, anchor every {ANCHOR_MIN} min, max {MAX_WIN}/case)",
          flush=True)

    out, t0 = [], time.time()
    for k, r in enumerate(sub.itertuples()):
        try:
            out.extend(process_case(r.caseid, r.tier))
        except Exception:
            pass
        if k % 20 == 0 and k:
            el = time.time() - t0
            print(f"  {k}/{len(sub)}  rows={len(out)}  {el:.0f}s"
                  f"  eta={el/k*(len(sub)-k):.0f}s", flush=True)

    if not out:
        print("no windows extracted"); sys.exit(1)
    df = pd.DataFrame(out)
    p = os.path.join(HERE, f"wave_windows_{start}.csv")
    df.to_csv(p, index=False)
    print(f"\nsaved {len(df)} windows from {df.caseid.nunique()} cases "
          f"-> {os.path.basename(p)}")
    print(df.groupby('tier').agg(cases=('caseid', 'nunique'),
                                 windows=('caseid', 'size')).to_string())
    print("\nreference coverage (windows):")
    for c in ["CO_pc", "SV_pc", "CO_td", "EDV", "ESV", "R_tot"]:
        if c in df:
            print(f"  {c:7s} {int(np.isfinite(df[c]).sum()):6d}")
