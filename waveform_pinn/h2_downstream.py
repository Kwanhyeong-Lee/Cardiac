# -*- coding: utf-8 -*-
"""H2 — incremental value of the learned physical state for a clinical outcome.
Pre-specified in PROTOCOL_v2_benefit.md before running.

QUESTION. Do the learned Hamiltonian H, dissipation R and effort variables dH/dx carry
information about the patient beyond the raw vital signs they were computed from? If they
do, the architecture produces something an informatics reader can use, which is the
contribution IEEE JBHI's scope asks for and which the paper otherwise lacks.

DESIGN (fixed in advance)
    outcome    postoperative ICU admission within 24 h (operations.icuin_time non-null)
    features   BASE  raw state summaries + drug exposure + demographics
               +PH   BASE plus H, T, V and trace/min-eigenvalue of R, from model P
               +LAT  BASE plus the effort variables dH/dx
    control    the same +PH block taken from the UNCONSTRAINED model U. If U's block helps
               as much as P's, the information is in network capacity, not in the physics,
               and H2 is refuted however large the increment.
    splits     operation level; the dynamics model is fitted on training operations only,
               so no test operation influences either the features or the classifier
    seeds      0..4

DECISION RULE (fixed in advance)
    H2 is supported only if mean AUROC(+PH) - AUROC(BASE) > 0.02 with DeLong p < 0.05 in at
    least 4 of 5 seeds, AND the increment from P exceeds the increment from the U control.

Usage:  python3 h2_downstream.py --seed S   |   --summary
"""
import argparse, gzip, io, json, os, sys, time, zipfile
import numpy as np, pandas as pd
import torch, torch.nn as nn, torch.nn.functional as F
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import GroupShuffleSplit
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

from port_rollout import MODELS, NX, EPOCHS, BATCH, LR, WD, PATIENCE
from port_rollout_inspire import load, SCOLS, DRUG
from agreement import delong_auc

HERE = os.path.dirname(os.path.abspath(__file__))
STORE = os.path.join(HERE, "results_h2_downstream.json")
# INSPIRE zip lives outside the repository: default D:\data\INSPIRE\,
# override the root with CARDIAC_DATA (HANDOVER.md section 3).
ZIP = os.path.join(os.environ.get("CARDIAC_DATA", r"D:\data"), "INSPIRE",
                   "inspire-a-publicly-available-research-dataset-for-perioperative-medicine-1.4.2.zip")
BASE = "inspire-a-publicly-available-research-dataset-for-perioperative-medicine-1.4.2/"


def outcomes():
    z = zipfile.ZipFile(ZIP)
    op = pd.read_csv(gzip.open(io.BytesIO(z.read(BASE + "operations.csv.gz"))),
                     usecols=["op_id", "icuin_time", "inhosp_death_time", "asa", "emop"])
    op["icu"] = op.icuin_time.notna().astype(int)
    op["death"] = op.inhosp_death_time.notna().astype(int)
    return op.set_index("op_id")[["icu", "death", "asa", "emop"]]


def agg(df, cols, pref=""):
    g = df.groupby("op_id")[cols]
    out = pd.concat([g.mean().add_suffix(f"_{pref}mean"), g.std().add_suffix(f"_{pref}sd"),
                     g.min().add_suffix(f"_{pref}min"), g.max().add_suffix(f"_{pref}max")],
                    axis=1)
    return out


def fit_dynamics(letter, seed, X, U, Y, grp, tr, va):
    scX = StandardScaler().fit(X[tr])
    Xtr, Xva = scX.transform(X[tr]).astype(np.float32), scX.transform(X[va]).astype(np.float32)
    Ytr, Yva = scX.transform(Y[tr]).astype(np.float32), scX.transform(Y[va]).astype(np.float32)
    torch.manual_seed(seed)
    net = MODELS[letter]()
    opt = torch.optim.AdamW(net.parameters(), lr=LR, weight_decay=WD)
    sch = torch.optim.lr_scheduler.CosineAnnealingLR(opt, EPOCHS)
    dl = torch.utils.data.DataLoader(
        torch.utils.data.TensorDataset(torch.tensor(Xtr), torch.tensor(U[tr]),
                                       torch.tensor(Ytr)), batch_size=BATCH * 8, shuffle=True)
    xv, uv, yv = torch.tensor(Xva), torch.tensor(U[va]), torch.tensor(Yva)
    best, bstate, since = np.inf, None, 0
    for ep in range(EPOCHS):
        net.train()
        for bx, bu, by in dl:
            opt.zero_grad()
            F.mse_loss(net(bx, bu)[0], by).backward()
            nn.utils.clip_grad_norm_(net.parameters(), 1.0)
            opt.step()
        sch.step(); net.eval()
        v = float(F.mse_loss(net(xv, uv)[0], yv).detach())
        if v < best - 1e-6:
            best, since = v, 0
            bstate = {k: t.clone() for k, t in net.state_dict().items()}
        else:
            since += 1
            if since >= PATIENCE:
                break
    net.load_state_dict(bstate); net.eval()
    return net, scX


def ph_features(net, X, U, scX, op_ids):
    """H, T, V, trace(R), min eig(R) and the effort variables dH/dx, per row."""
    x = torch.tensor(scX.transform(X).astype(np.float32)).requires_grad_(True)
    H = net.hamiltonian(x)
    dH = torch.autograd.grad(H.sum(), x)[0].detach().numpy()
    with torch.no_grad():
        h = net.enc(x)
        R, _ = net.RJ(h)
        T = F.softplus(net.T_head(h)) if hasattr(net, "T_head") else None
        ev = torch.linalg.eigvalsh(R.double())
    d = pd.DataFrame({"op_id": op_ids, "H": H.detach().numpy().ravel(),
                      "Rtr": R.diagonal(dim1=1, dim2=2).sum(1).numpy(),
                      "Rmin": ev.min(1).values.numpy()})
    for j in range(NX):
        d[f"dH{j}"] = dH[:, j]
    return d


def run(seed, only=None):
    X0, _, Y0, g0, _ = load()
    gss = GroupShuffleSplit(n_splits=1, test_size=0.3, random_state=seed)
    trv, te = next(gss.split(X0, Y0, g0))
    mask = np.zeros(len(X0), bool); mask[trv] = True
    X, U, Y, grp, d = load(train_mask=mask)
    gin = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=seed + 100)
    itr, iva = next(gin.split(X[trv], Y[trv], grp[trv]))
    tr, va = trv[itr], trv[iva]
    assert not (set(grp[tr]) & set(grp[te])), "operation leakage"

    out = {"seed": seed, "n_train_ops": int(len(set(grp[tr]))),
           "n_test_ops": int(len(set(grp[te])))}

    # ---- BASE features ----
    base = agg(d, SCOLS)
    drugs = d.groupby("op_id")[list(DRUG)].mean().add_suffix("_exposure")
    dem = d.groupby("op_id")[["age", "weight", "height", "bsa"]].first()
    dem["sex"] = (d.groupby("op_id").sex.first() == "M").astype(int)
    dem["n_slots"] = d.groupby("op_id").size()
    oc = outcomes()
    B = base.join(drugs).join(dem).join(oc[["asa", "emop"]]).dropna(how="all")

    y = oc.icu.reindex(B.index)
    ok = y.notna()
    B, y = B[ok], y[ok].astype(int)
    out["n_ops"] = int(len(B)); out["icu_rate"] = round(float(y.mean()), 4)
    out["death_rate"] = round(float(oc.death.reindex(B.index).mean()), 4)

    tr_ops = np.array(sorted(set(grp[tr]) | set(grp[va])))
    te_ops = np.array(sorted(set(grp[te])))
    tr_ops = np.array([o for o in tr_ops if o in B.index])
    te_ops = np.array([o for o in te_ops if o in B.index])

    blocks = {"BASE": B}
    for letter in ["P", "U"]:
        cache = os.path.join(HERE, f".h2_ph_{letter}_s{seed}.pkl")
        if only and letter != only:
            if not os.path.exists(cache):
                continue
        if not os.path.exists(cache):
            t0 = time.time()
            net, scX = fit_dynamics(letter, seed, X, U, Y, grp, tr, va)
            ph = ph_features(net, X, U, scX, d.op_id.to_numpy())
            pa = agg(ph, ["H", "Rtr", "Rmin"] + [f"dH{j}" for j in range(NX)],
                     pref=f"{letter}_")
            pa.to_pickle(cache)
            print(f"  [{letter}] features cached ({time.time()-t0:.0f}s)", flush=True)
        blocks[f"+PH_{letter}"] = B.join(pd.read_pickle(cache))
    if only:
        return None

    res = {}
    for name, Fm in blocks.items():
        Xtr = Fm.reindex(tr_ops).to_numpy(np.float32)
        Xte = Fm.reindex(te_ops).to_numpy(np.float32)
        ytr, yte = y.reindex(tr_ops).to_numpy(), y.reindex(te_ops).to_numpy()
        clf = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.06,
                                             max_depth=4, random_state=seed)
        clf.fit(Xtr, ytr)
        p = clf.predict_proba(Xte)[:, 1]
        res[name] = {"auroc": round(float(roc_auc_score(yte, p)), 4),
                     "n_features": int(Fm.shape[1]), "pred": p.tolist()}
    yte = y.reindex(te_ops).to_numpy()
    for k in ["+PH_P", "+PH_U"]:
        dl = delong_auc(yte, np.array(res[k]["pred"]), np.array(res["BASE"]["pred"]))
        res[k]["delta_vs_base"] = round(res[k]["auroc"] - res["BASE"]["auroc"], 4)
        res[k]["delong_z"] = dl.get("z")
        res[k]["delong_p"] = round(float(dl.get("p", float("nan"))), 4)
    for v in res.values():
        v.pop("pred")
    out["auroc"] = res
    out["n_test_events"] = int(yte.sum())
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--only", default=None, help="P or U: train+cache that block only")
    a = ap.parse_args()
    if a.summary:
        rows = json.load(open(STORE))
        d = pd.DataFrame([{"seed": r["seed"], "events": r["n_test_events"],
                           "BASE": r["auroc"]["BASE"]["auroc"],
                           "+PH_P": r["auroc"]["+PH_P"]["auroc"],
                           "dP": r["auroc"]["+PH_P"]["delta_vs_base"],
                           "pP": r["auroc"]["+PH_P"]["delong_p"],
                           "+PH_U": r["auroc"]["+PH_U"]["auroc"],
                           "dU": r["auroc"]["+PH_U"]["delta_vs_base"],
                           "pU": r["auroc"]["+PH_U"]["delong_p"]} for r in rows])
        print(d.sort_values("seed").to_string(index=False))
        print(f"\nICU rate in cohort: {rows[0]['icu_rate']}   "
              f"in-hospital death: {rows[0]['death_rate']}")
        m = d[["BASE", "+PH_P", "+PH_U", "dP", "dU"]].mean()
        print(f"\nmean  BASE {m['BASE']:.4f}   +PH_P {m['+PH_P']:.4f} "
              f"(delta {m['dP']:+.4f})   +PH_U {m['+PH_U']:.4f} (delta {m['dU']:+.4f})")
        c1 = m["dP"] > 0.02 and int((d.pP < 0.05).sum()) >= 4
        c2 = m["dP"] > m["dU"]
        print(f"\nDECISION RULE")
        print(f"  1. mean delta > 0.02 and DeLong p<0.05 in >=4/5 seeds : "
              f"delta {m['dP']:+.4f}, p<0.05 in {int((d.pP<0.05).sum())}/{len(d)}  -> {c1}")
        print(f"  2. P increment exceeds the unconstrained-U control    : "
              f"{m['dP']:+.4f} vs {m['dU']:+.4f}  -> {c2}")
        print(f"\n  H2 {'SUPPORTED' if (c1 and c2) else 'NOT SUPPORTED'}")
        sys.exit(0)
    r = run(a.seed, only=a.only)
    if r is None:
        sys.exit(0)
    prev = json.load(open(STORE)) if os.path.exists(STORE) else []
    prev = [x for x in prev if x["seed"] != r["seed"]]
    json.dump(prev + [r], open(STORE, "w"), indent=1, default=float)
    A = r["auroc"]
    print(f"[seed {r['seed']}] ops={r['n_ops']} ICU={r['icu_rate']} events(test)={r['n_test_events']}"
          f" | BASE {A['BASE']['auroc']} | +PH_P {A['+PH_P']['auroc']} "
          f"({A['+PH_P']['delta_vs_base']:+.4f}, p={A['+PH_P']['delong_p']}) "
          f"| +PH_U {A['+PH_U']['auroc']} ({A['+PH_U']['delta_vs_base']:+.4f})")
