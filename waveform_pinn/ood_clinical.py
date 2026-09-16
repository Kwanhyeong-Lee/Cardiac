# -*- coding: utf-8 -*-
"""v4 — out-of-distribution probe using a clinical subgroup holdout (PROTOCOL.md §6).

The earlier probe displaced held-out inputs by Gaussian noise in standardised feature
space. At large displacements that produces physiologically impossible feature
combinations, and the fair objection is that a model fed nonsense may return nonsense
without that implying anything about deployment.

Here the shift is real. Models are trained on **general surgery only** and evaluated on
two surgical populations they have never seen:

    THORACIC     226 cases   one-lung ventilation, open chest
    TRANSPLANT   151 cases   anhepatic phase, reperfusion syndrome

Neither can be dismissed as an artefact of the probe: these are patients the same
monitor is used on every day.

One observation that matters for the whole study: **all 33 thermodilution cases and all
24 paired cases are transplant patients.** The primary endpoint has therefore always been
measured under distribution shift, which was not appreciated when the cohorts were
defined.

Usage:  python3 ood_clinical.py <seed>        # writes ood_clinical_<seed>.json
"""
import json, os, sys
import numpy as np, pandas as pd, torch
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import r2_score

import models as M
import train_eval as T

HERE = os.path.dirname(os.path.abspath(__file__))
COLS = M.MORPH_DEMO_COLS
LETTERS = ["A", "C", "E"]        # constrained-state / unconstrained / constrained-output


def evaluate(net, frame, scX, scY, label):
    X, Y, g = T.matrices(frame, COLS, "CO_pc")
    if len(X) < 50:
        return None
    p, (H, Tt, V, R) = T.predict(net, X, scX, scY)
    v = M.violations(H, Tt, V, R)
    pp, yy = T.by_patient(p, Y.ravel(), g)
    return {
        "set": label, "n_windows": int(len(X)), "n_patients": int(len(pp)),
        "r2_patient": round(float(r2_score(yy, pp)), 4),
        "co_min": round(float(p.min()), 2), "co_max": round(float(p.max()), 2),
        "co_negative": int((p < 0).sum()),
        "co_negative_pct": round(100.0 * float((p < 0).mean()), 3),
        "co_over_25": int((p > 25).sum()),
        "T_neg": v["T_neg"], "V_neg": v["V_neg"], "R_nonpsd": v["R_nonpsd"],
    }


def main(seed):
    d = pd.read_csv(os.path.join(HERE, "wave_windows_ood.csv"))
    train = d[d.ood_group == "TRAIN"]                       # general surgery only
    holdouts = {"THORACIC": d[d.ood_group == "THORACIC"],
                "TRANSPLANT": d[d.ood_group == "TRANSPLANT"]}

    Xtr, Ytr, gtr = T.matrices(train, COLS, "CO_pc")
    # in-distribution validation: 20% of the training speciality, patient-disjoint
    from sklearn.model_selection import GroupShuffleSplit
    tr, va = next(GroupShuffleSplit(1, test_size=0.2, random_state=seed)
                  .split(Xtr, Ytr, gtr))
    assert not (set(gtr[tr]) & set(gtr[va])), "case leakage"
    scX = StandardScaler().fit(Xtr[tr]); scY = StandardScaler().fit(Ytr[tr])

    out = {"seed": seed, "n_train_windows": int(len(tr)),
           "n_train_patients": int(len(set(gtr[tr]))), "runs": []}
    for L in LETTERS:
        net = T.fit(M.MODELS[L](len(COLS), 1),
                    scX.transform(Xtr[tr]).astype(np.float32),
                    scY.transform(Ytr[tr]).astype(np.float32),
                    seed, soft=False, epochs=40, batch=512)
        # in-distribution reference point
        pv, (H, Tt, V, R) = T.predict(net, Xtr[va], scX, scY)
        pp, yy = T.by_patient(pv, Ytr[va].ravel(), gtr[va])
        v = M.violations(H, Tt, V, R)
        rows = [{"set": "IN-DIST (general surgery)", "n_windows": int(len(va)),
                 "n_patients": int(len(pp)),
                 "r2_patient": round(float(r2_score(yy, pp)), 4),
                 "co_min": round(float(pv.min()), 2), "co_max": round(float(pv.max()), 2),
                 "co_negative": int((pv < 0).sum()),
                 "co_negative_pct": round(100.0 * float((pv < 0).mean()), 3),
                 "co_over_25": int((pv > 25).sum()),
                 "T_neg": v["T_neg"], "V_neg": v["V_neg"], "R_nonpsd": v["R_nonpsd"]}]
        for name, frame in holdouts.items():
            r = evaluate(net, frame, scX, scY, name)
            if r:
                rows.append(r)
        out["runs"].append({"model": L,
                            "n_params": sum(q.numel() for q in net.parameters()),
                            "results": rows})

    p = os.path.join(HERE, f"ood_clinical_{seed}.json")
    json.dump(out, open(p, "w"), indent=1)
    print(f"seed {seed}: trained on {out['n_train_patients']} general-surgery patients")
    for run in out["runs"]:
        print(f"\n  model {run['model']}  ({run['n_params']:,} params)")
        for r in run["results"]:
            print(f"    {r['set']:26s} n={r['n_patients']:3d}  R2={r['r2_patient']:+.3f}"
                  f"  CO {r['co_min']:7.1f}~{r['co_max']:7.1f}"
                  f"  neg={r['co_negative']:5d} ({r['co_negative_pct']:5.2f}%)"
                  f"  T<0={r['T_neg']:5d} R⊁0={r['R_nonpsd']:5d}")
    return out


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 0)
