# -*- coding: utf-8 -*-
"""Paper B — the output-constraint claim, rebuilt after the 2026-08-12 audit.

Three defects were found in the first version of this experiment and all three are fixed
here.

1. CAPACITY. `PAPER_B_OUTLINE.md` listed "Model E is not capacity matched to A". E drops
   A's 17,537-parameter decoder for two linear heads (272 parameters) and so ran 30.3%
   smaller. E2 restores the deficit inside the positive heads: 56,986 against A's 56,983.

2. THE GUARANTEE WAS NOT ARCHITECTURAL. E and E2 map the positive quotient to the target
   scale with free parameters, `y = _scale*co + _shift`. Positivity therefore depended on
   `_scale > 0`, which nothing enforces, and the observed "0 negative outputs" came from a
   learned offset that placed a floor at 3.43-3.49 L/min -- above 15.9% of the reference
   values. E3 replaces the free affine map with the exact inverse of the target
   standardisation, so CO > 0 holds by algebra with no learned quantity involved.

3. ONE-SIDED PROBE. Counting negative outputs only is trivially zero once a positive floor
   exists. The probe is now two-sided: outputs are also impossible above 20 L/min.

Model selection also moved off training loss onto an inner patient-level validation split,
matching `port_rollout.py`; `train_eval.fit` selects on training loss, which is defensible
on the 22k-row static task but is not what this comparison should rest on.

Usage:  python3 capacity_match.py --list | --job N | --summary
"""
import argparse, json, os, sys, time
import numpy as np, pandas as pd
import torch, torch.nn as nn, torch.nn.functional as F
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import r2_score

import models as M
import agreement as A
from train_eval import matrices, by_patient

HERE = os.path.dirname(os.path.abspath(__file__))
STORE = os.path.join(HERE, "results_capacity_match.json")
DATA = "wave_windows_demo.csv"
LETTERS = ["A", "E", "E2", "E3"]
SEEDS = [0, 1, 2]
EPOCHS, BATCH, LR, WD, PATIENCE = 60, 512, 2e-3, 1e-4, 10
SIGMAS = [0, 6, 12, 24, 40]


def jobs():
    return [dict(letter=L, seed=s) for s in SEEDS for L in LETTERS]


def fit_val(net, Xtr, Ytr, Xva, Yva, seed):
    """Train with checkpoint selection on a held-out validation split, not training loss."""
    torch.manual_seed(seed)
    dl = torch.utils.data.DataLoader(
        torch.utils.data.TensorDataset(torch.tensor(Xtr), torch.tensor(Ytr)),
        batch_size=BATCH, shuffle=True)
    xv, yv = torch.tensor(Xva), torch.tensor(Yva)
    opt = torch.optim.AdamW(net.parameters(), lr=LR, weight_decay=WD)
    sch = torch.optim.lr_scheduler.CosineAnnealingLR(opt, EPOCHS)
    best, best_state, best_ep, since = np.inf, None, -1, 0
    for ep in range(EPOCHS):
        net.train()
        for bx, by in dl:
            opt.zero_grad()
            F.mse_loss(net(bx)[0], by).backward()
            nn.utils.clip_grad_norm_(net.parameters(), 1.0)
            opt.step()
        sch.step()
        net.eval()
        with torch.no_grad():
            v = float(F.mse_loss(net(xv)[0], yv))
        if v < best - 1e-7:
            best, best_ep, since = v, ep, 0
            best_state = {k: t.clone() for k, t in net.state_dict().items()}
        else:
            since += 1
            if since >= PATIENCE:
                break
    net.load_state_dict(best_state)
    net.eval()
    return net, best, best_ep


def run(letter, seed):
    df = pd.read_csv(os.path.join(HERE, DATA))
    pc = df[df.tier.isin(["PC", "BOTH"])].copy()
    td = df[df.tier == "TD_ONLY"].copy()
    cols = M.MORPH_DEMO_COLS

    X, Y, g = matrices(pc, cols, "CO_pc")
    gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=seed)
    trv, te = next(gss.split(X, Y, g))
    gin = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=seed + 100)
    itr, iva = next(gin.split(X[trv], Y[trv], g[trv]))
    tr, va = trv[itr], trv[iva]
    for a, b, nm in [(tr, te, "train/test"), (tr, va, "train/val"), (va, te, "val/test")]:
        assert not (set(g[a]) & set(g[b])), f"case leakage: {nm}"

    scX = StandardScaler().fit(X[tr])
    scY = StandardScaler().fit(Y[tr])
    Xs = {k: scX.transform(X[i]).astype(np.float32) for k, i in
          [("tr", tr), ("va", va), ("te", te)]}
    Ys = {k: scY.transform(Y[i]).astype(np.float32) for k, i in
          [("tr", tr), ("va", va), ("te", te)]}

    net = M.MODELS[letter](len(cols), 1)
    if hasattr(net, "set_target_scale"):
        net.set_target_scale(scY.mean_[0], scY.scale_[0])
    n_par = sum(p.numel() for p in net.parameters())

    t0 = time.time()
    net, vmse, bep = fit_val(net, Xs["tr"], Ys["tr"], Xs["va"], Ys["va"], seed)
    train_s = time.time() - t0

    # parameters that never received a gradient -- the audit found L_head dead in A/E/E2
    dead = sorted(n for n, p in net.named_parameters() if p.grad is None)
    n_dead = int(sum(p.numel() for n, p in net.named_parameters() if p.grad is None))

    res = {"model": letter, "seed": seed, "n_params": int(n_par),
           "n_params_dead": n_dead, "dead_tensors": dead,
           "n_params_active": int(n_par - n_dead),
           "n_train": int(len(tr)), "n_val": int(len(va)), "n_test": int(len(te)),
           "n_train_cases": int(len(set(g[tr]))), "n_test_cases": int(len(set(g[te]))),
           "best_epoch": int(bep), "val_mse": round(vmse, 5),
           "train_seconds": round(train_s, 1)}

    with torch.no_grad():
        pt = net(torch.tensor(Xs["te"]))[0].numpy().ravel() * scY.scale_ + scY.mean_
    pv_p, yv_p = by_patient(pt, Y[te].ravel(), g[te])
    res["internal_r2"] = round(float(r2_score(yv_p, pv_p)), 4)
    res["internal_r2_window"] = round(float(r2_score(Y[te].ravel(), pt)), 4)
    res["n_test_patients"] = int(len(pv_p))

    with torch.no_grad():
        _, H, T, V, R = net(torch.tensor(Xs["te"]))
    res["violations"] = M.violations(H, T, V, R)
    res["violations_note"] = ("R enters no loss term in these runs (soft=False), so a PSD "
                              "or non-PSD outcome is a property of the parameterisation, "
                              "not of training -- which is the claim being made.")

    # ---- two-sided output-range probe ----
    rng = torch.Generator().manual_seed(seed)
    probe = {}
    for s in SIGMAS:
        Z = torch.tensor(Xs["te"]) if s == 0 else torch.randn(4000, len(cols), generator=rng) * s
        probe[f"sigma{s}"] = M.output_range_probe(net, Z, scY)
    res["output_range_probe"] = probe

    # ---- is the floor learned or architectural? ----
    floor = None
    if letter in ("E", "E2"):
        sc, sh = float(net._scale), float(net._shift)
        floor = sh * scY.scale_[0] + scY.mean_[0]        # co -> 0+ gives y -> _shift
        res["affine"] = {"scale": round(sc, 4), "shift": round(sh, 4),
                         "implied_floor_Lmin": round(float(floor), 3),
                         "guarantee_valid_only_if_scale_positive": bool(sc > 0)}
    elif letter == "E3":
        floor = 0.0
        res["affine"] = {"scale": "fixed 1/sigma_y", "shift": "fixed -mu_y/sigma_y",
                         "implied_floor_Lmin": 0.0,
                         "guarantee_valid_only_if_scale_positive": True}
    if floor is not None:
        y_all = Y[tr].ravel()
        res["floor_cost"] = {
            "floor_Lmin": round(float(floor), 3),
            "frac_train_targets_below_floor": round(float((y_all < floor).mean()), 4),
            "frac_test_pred_within_0p10_of_floor": round(
                float((np.abs(pt - floor) < 0.10).mean()), 4)}

    # frozen; thermodilution touched only now
    Xte2, Yte2, gte2 = matrices(td, cols, "CO_td")
    if len(Xte2) >= 8:
        with torch.no_grad():
            q = net(torch.tensor(scX.transform(Xte2).astype(np.float32)))[0]
        q = q.numpy().ravel() * scY.scale_ + scY.mean_
        qp, yp = by_patient(q, Yte2.ravel(), gte2)
        res["n_td_patients"] = int(len(qp))
        res["external_agreement"] = A.full_report(qp, yp, "thermodilution (patient level)")
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", type=int, default=None)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--summary", action="store_true")
    args = ap.parse_args()
    J = jobs()

    if args.list:
        for k, j in enumerate(J):
            print(f"{k:2d}  model {j['letter']:2s}  seed {j['seed']}")
        sys.exit(0)

    if args.summary:
        rows = json.load(open(STORE))
        d = pd.DataFrame([{
            "model": r["model"], "seed": r["seed"], "params": r["n_params"],
            "active": r["n_params_active"], "R2": r["internal_r2"],
            "PE": r.get("external_agreement", {}).get("pct_error"),
            "floor": r.get("floor_cost", {}).get("floor_Lmin"),
            "neg40": r["output_range_probe"]["sigma40"]["n_negative"],
            "outside40": r["output_range_probe"]["sigma40"]["n_outside"],
            "max40": r["output_range_probe"]["sigma40"]["max"],
            "min40": r["output_range_probe"]["sigma40"]["min"],
        } for r in rows])
        print("--- per run (probe n = 4,000 per seed) ---")
        print(d.sort_values(["model", "seed"]).to_string(index=False))
        print()
        print("--- by model, mean over 3 seeds; neg/outside summed ---")
        print(d.groupby("model").agg(
            params=("params", "first"), active=("active", "first"),
            R2=("R2", "mean"), R2sd=("R2", "std"),
            PE=("PE", "mean"), PEsd=("PE", "std"),
            floor=("floor", "mean"),
            neg40=("neg40", "sum"), outside40=("outside40", "sum")).round(4).to_string())
        print()
        for r in sorted(rows, key=lambda z: (z["model"], z["seed"])):
            if "floor_cost" in r:
                fc = r["floor_cost"]
                print(f"{r['model']:3s} s{r['seed']}  floor {fc['floor_Lmin']:>6.3f} L/min "
                      f"| targets below floor {100*fc['frac_train_targets_below_floor']:5.1f}% "
                      f"| predictions pinned to floor {100*fc['frac_test_pred_within_0p10_of_floor']:5.1f}%")
        sys.exit(0)

    j = J[args.job]
    r = run(j["letter"], j["seed"])
    prev = json.load(open(STORE)) if os.path.exists(STORE) else []
    prev = [x for x in prev if not (x["model"] == r["model"] and x["seed"] == r["seed"])]
    json.dump(prev + [r], open(STORE, "w"), indent=1, default=float)
    p40 = r["output_range_probe"]["sigma40"]
    print(f"[{args.job}] {r['model']:2s} s{r['seed']} par={r['n_params']:,} "
          f"(dead {r['n_params_dead']:,}) R2={r['internal_r2']} "
          f"PE={r.get('external_agreement',{}).get('pct_error')}% | 40sig: neg={p40['n_negative']} "
          f"outside[0.5,20]={p40['n_outside']} range=[{p40['min']},{p40['max']}] "
          f"| floor={r.get('floor_cost',{}).get('floor_Lmin')} ({r['train_seconds']}s)")
