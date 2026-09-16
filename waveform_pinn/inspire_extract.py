# -*- coding: utf-8 -*-
"""Paper B task 5 — INSPIRE trajectories for the port-Hamiltonian rollout.

WHY THIS DATASET. `RESULTS_v7_port_rollout.md` carries one limitation above all others:

    "Supervision is one step. Each eICU episode gives a single pre -> post pair, so
     iterating beyond one step is extrapolation of the learned map rather than a validated
     physiological trajectory."

INSPIRE removes it. The `vitals` table is a 5-minute time series over the whole operation,
and the vasoactive drugs are recorded as continuous infusion *rates* in ug/kg/min. That is a
genuine multi-step trajectory with a genuine exogenous input, in a different country, a
different care setting and a different institution from eICU.

COHORT (established by a full scan of all 66,029,310 vitals rows):

    art_mbp AND hr                                  49,230 operations
    at least one continuous vasoactive infusion      5,033
    both                                             4,944
    both + cardiac index                             2,511   <- primary

The primary cohort uses cardiac index because it reproduces the eICU state exactly:

    eICU     x = (CO, SBP, DBP, HR)          pre/post pair, 1,445 patients, 208 US hospitals
    INSPIRE  x = (CI*BSA, art_sbp, art_dbp, hr)   5-min series, 2,511 operations, SNUH

so the INSPIRE run is an external replication of the same state and the same drug classes,
not a new experiment that happens to use the same code.

    u = (vasopressor, vasodilator, inotrope, vasopressor_inotrope)
        one channel per mechanism, carrying the summed within-drug z-scored infusion rate,
        matching the eICU encoding.

`pepi` (phenylephrine infusion) is declared in `parameters.csv` but has zero rows in the
released data; it is dropped rather than silently contributing an all-zero channel.

Usage:  python3 inspire_extract.py           # writes inspire_traj.csv
"""
import gzip, io, json, os, sys, time, zipfile
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
# INSPIRE zip lives outside the repository: default D:\data\INSPIRE\,
# override the root with CARDIAC_DATA (HANDOVER.md section 3).
ZIP = os.path.join(os.environ.get("CARDIAC_DATA", r"D:\data"), "INSPIRE",
                   "inspire-a-publicly-available-research-dataset-for-perioperative-medicine-1.4.2.zip")
BASE = "inspire-a-publicly-available-research-dataset-for-perioperative-medicine-1.4.2/"
OUT = os.path.join(HERE, "inspire_traj.csv")

# mechanism map, matching the eICU drug_class -> mechanism map exactly
MECH = {"nepi": "vasopressor", "ntgi": "vasodilator",
        "dobui": "inotrope", "mlni": "inotrope",
        "epii": "vasopressor_inotrope", "dopai": "vasopressor_inotrope"}
MECHS = ["vasopressor", "vasodilator", "inotrope", "vasopressor_inotrope"]
STATE_ITEMS = ["ci", "art_sbp", "art_dbp", "hr"]
NEED = set(STATE_ITEMS) | set(MECH)

GRID = 5.0          # minutes; the released resolution
LOCF_STATE = 4      # carry a state value forward at most 4 grid steps (20 min)
LOCF_RATE = 12      # an infusion rate persists until changed; 60 min cap
# physiological box, same variables and same spirit as the eICU cohort filter
BOX = {"co": (0.5, 20.0), "art_sbp": (40.0, 260.0),
       "art_dbp": (15.0, 160.0), "hr": (20.0, 220.0)}


def main():
    z = zipfile.ZipFile(ZIP)
    op = pd.read_csv(gzip.open(io.BytesIO(z.read(BASE + "operations.csv.gz"))))
    op = op.set_index("op_id")
    # DuBois body surface area, to turn cardiac index into cardiac output
    bsa = 0.007184 * op.height.clip(lower=100) ** 0.725 * op.weight.clip(lower=20) ** 0.425

    have = json.load(open("/tmp/insp_itemops.json"))
    cohort = (set(have["art_mbp"]) & set(have["hr"]) & set(have["ci"])
              & set().union(*[set(have[k]) for k in MECH]))
    print(f"cohort: {len(cohort):,} operations", flush=True)

    t0, n, kept = time.time(), 0, 0
    rows = []
    f = gzip.open(io.BytesIO(z.read(BASE + "vitals.csv.gz")), "rt")
    f.readline()
    for line in f:
        n += 1
        i = line.index(",")
        opid = line[:i]
        if opid not in cohort:
            continue
        j = line.rindex(",")
        k = line.rindex(",", 0, j)
        item = line[k + 1: j]
        if item not in NEED:
            continue
        m = line.index(",", i + 1)
        rows.append((int(opid), float(line[m + 1: k]), item, float(line[j + 1:])))
        kept += 1
    print(f"scanned {n:,} rows, kept {kept:,}  ({time.time()-t0:.0f}s)", flush=True)

    d = pd.DataFrame(rows, columns=["op_id", "chart_time", "item", "value"])
    d["slot"] = np.round(d.chart_time / GRID).astype(int)
    w = (d.groupby(["op_id", "slot", "item"]).value.median()
         .unstack("item").sort_index())
    print(f"pivot: {w.shape[0]:,} op-slots x {w.shape[1]} items", flush=True)

    out = []
    for opid, g in w.groupby(level=0):
        g = g.droplevel(0)
        full = g.reindex(range(int(g.index.min()), int(g.index.max()) + 1))
        st = full.reindex(columns=STATE_ITEMS).ffill(limit=LOCF_STATE)
        rt = full.reindex(columns=list(MECH)).ffill(limit=LOCF_RATE).fillna(0.0)
        b = float(bsa.get(opid, np.nan))
        if not np.isfinite(b):
            continue
        fr = pd.DataFrame({
            "op_id": opid, "slot": st.index,
            "co": st.ci.to_numpy() * b,
            "art_sbp": st.art_sbp.to_numpy(),
            "art_dbp": st.art_dbp.to_numpy(),
            "hr": st.hr.to_numpy()})
        for k in MECH:
            fr[k] = rt[k].to_numpy()
        out.append(fr)
    t = pd.concat(out, ignore_index=True)

    ok = np.ones(len(t), bool)
    for v, (lo, hi) in BOX.items():
        ok &= t[v].between(lo, hi)
    t = t[ok].copy()

    # consecutive-slot transitions only; a gap breaks the pair
    t = t.sort_values(["op_id", "slot"])
    nxt = t.groupby("op_id").shift(-1)
    step_ok = (nxt.slot - t.slot == 1)
    for v in BOX:
        t[f"next_{v}"] = nxt[v]
    t["contiguous"] = step_ok.fillna(False)

    dem = op.reindex(t.op_id.to_numpy())
    for c in ["age", "sex", "weight", "height", "asa", "emop", "department", "antype"]:
        t[c] = dem[c].to_numpy()
    t["bsa"] = bsa.reindex(t.op_id.to_numpy()).to_numpy()

    t.to_csv(OUT, index=False)
    tr = t[t.contiguous]
    print(f"\nsaved {len(t):,} grid rows -> {os.path.basename(OUT)}")
    print(f"  operations            : {t.op_id.nunique():,}")
    print(f"  usable transitions    : {len(tr):,}")
    print(f"  transitions/operation : median {tr.groupby('op_id').size().median():.0f}, "
          f"max {tr.groupby('op_id').size().max():,}")
    print(f"  runs of >=10 steps    : "
          f"{(tr.groupby('op_id').size() >= 10).sum():,} operations")
    print("\n  drug-rate coverage (fraction of rows with a non-zero rate):")
    for k in MECH:
        print(f"    {k:6s} ({MECH[k]:20s}) {100*(t[k] > 0).mean():5.2f}%")
    print("\n  state summary:")
    print(t[["co", "art_sbp", "art_dbp", "hr"]].describe().T[
        ["count", "mean", "std", "min", "50%", "max"]].round(2).to_string())


if __name__ == "__main__":
    main()
