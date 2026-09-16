# -*- coding: utf-8 -*-
"""Paper 2 — build the four pre-specified cohorts (see PROTOCOL.md §2).

Writes `cohort4.csv` next to this script with one row per case:
    caseid, tier, CO_pc, SV_pc, CO_td, EDV, ESV, RVEF, CVP, has_mbp

tier is one of:
    PC       pulse-contour only            (training / internal validation)
    TD_ONLY  thermodilution, not in PC     (PRIMARY analysis set)
    BOTH     in both PC and TD             (paired method comparison, excluded from primary)

Usage:  python3 build_cohort4.py            # full build (~15-25 min, network bound)
        python3 build_cohort4.py --index    # track index only, no per-case download
"""
import os, sys, time
import numpy as np, pandas as pd
import vitaldb

HERE = os.path.dirname(os.path.abspath(__file__))
TRKS = "https://api.vitaldb.net/trks"


def track_index():
    tr = pd.read_csv(TRKS)
    S = lambda t: set(tr.loc[tr.tname == t, "caseid"])
    art = S("SNUADC/ART")
    pc = art & (S("EV1000/CO") | S("Vigileo/CO")) & (S("EV1000/SV") | S("Vigileo/SV"))
    td = art & S("Vigilance/CO")
    vol = art & S("Vigilance/EDV") & S("Vigilance/ESV")
    mbp = art & S("Solar8000/ART_MBP")
    return dict(art=art, pc=pc, td=td, vol=vol, mbp=mbp)


TRACKS = ["EV1000/CO", "EV1000/SV", "EV1000/CVP",
          "Vigileo/CO", "Vigileo/SV",
          "Vigilance/CO", "Vigilance/EDV", "Vigilance/ESV", "Vigilance/RVEF",
          "Solar8000/CVP"]


def med(v, j):
    """Median of a track column, ignoring non-finite and non-positive samples."""
    if v is None or v.size == 0 or j >= v.shape[1]:
        return np.nan
    col = v[:, j]
    col = col[np.isfinite(col) & (col > 0)]
    return float(np.median(col)) if col.size else np.nan


def summarise(cid):
    v = vitaldb.load_case(int(cid), TRACKS, 1)
    if v is None or v.size == 0:
        return None
    g = lambda j: med(v, j)
    CO_pc = g(0) if np.isfinite(g(0)) else g(3)
    SV_pc = g(1) if np.isfinite(g(1)) else g(4)
    CVP = g(2) if np.isfinite(g(2)) else (g(9) if np.isfinite(g(9)) else 0.0)
    return dict(caseid=int(cid), CO_pc=CO_pc, SV_pc=SV_pc, CO_td=g(5),
                EDV=g(6), ESV=g(7), RVEF=g(8), CVP=CVP)


if __name__ == "__main__":
    ix = track_index()
    pc, td, vol, mbp = ix["pc"], ix["td"], ix["vol"], ix["mbp"]
    print(f"SNUADC/ART            : {len(ix['art'])}")
    print(f"PC  (pulse contour)   : {len(pc)}")
    print(f"TD  (thermodilution)  : {len(td)}")
    print(f"  TD_ONLY = TD \\ PC   : {len(td - pc)}   <-- PRIMARY")
    print(f"  BOTH    = TD & PC   : {len(td & pc)}")
    print(f"VOL (Vigilance EDV/ESV): {len(vol)}")
    print(f"IOH (ART_MBP)         : {len(mbp)}")
    if "--index" in sys.argv:
        sys.exit(0)

    ids = sorted(pc | td | vol)
    print(f"\ndownloading summaries for {len(ids)} cases ...")
    rows, t0 = [], time.time()
    for k, cid in enumerate(ids):
        try:
            r = summarise(cid)
        except Exception:
            r = None
        if r:
            r["tier"] = ("BOTH" if cid in pc and cid in td
                         else "TD_ONLY" if cid in td
                         else "PC" if cid in pc else "VOL_ONLY")
            r["has_mbp"] = cid in mbp
            r["has_vol"] = cid in vol
            rows.append(r)
        if k % 50 == 0:
            el = time.time() - t0
            print(f"  {k}/{len(ids)}  ok={len(rows)}  {el:.0f}s"
                  f"  eta={el/max(k,1)*(len(ids)-k):.0f}s", flush=True)

    df = pd.DataFrame(rows)
    # a case is usable for a tier only if that tier's reference value is present
    df.loc[df.tier.isin(["PC", "BOTH"]) & ~np.isfinite(df.CO_pc), "tier"] = "DROP"
    df.loc[df.tier.isin(["TD_ONLY", "BOTH"]) & ~np.isfinite(df.CO_td), "tier"] = "DROP"
    out = os.path.join(HERE, "cohort4.csv")
    df.to_csv(out, index=False)
    print(f"\nsaved {len(df)} rows -> cohort4.csv")
    print(df.tier.value_counts().to_string())
    print("\nreference values present:")
    for c in ["CO_pc", "SV_pc", "CO_td", "EDV", "ESV", "RVEF"]:
        print(f"  {c:6s} {int(np.isfinite(df[c]).sum()):4d}")
