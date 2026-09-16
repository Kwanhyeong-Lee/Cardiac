# -*- coding: utf-8 -*-
"""H1 — sample efficiency. Pre-specified in PROTOCOL_v2_benefit.md before running.

Physics structure acts as a prior, so any benefit should be largest when data are scarce and
should vanish as data grow. With 101,688 INSPIRE transitions the four architectures span
0.0017 in one-step R²; if the structure helps at all, it should show on a learning curve.

DESIGN (fixed in advance)
    test set   fixed per seed, never subsampled
    subsample  at the OPERATION level, not the row level -- scarce data means fewer
               patients, which is the regime that actually occurs
    fractions  0.02, 0.05, 0.10, 0.25, 0.50, 1.00 of training operations
    models     P, Pm, U, F
    seeds      0..4   (five; the n=3 limitation of every earlier run is fixed here)

ENDPOINTS
    primary    one-step skill against persistence on the fixed test set
    secondary  12-step (60-minute) skill against persistence

DECISION RULE (fixed in advance -- see PROTOCOL_v2_benefit.md)
    H1 is supported only if BOTH:
      1. at f <= 0.05 the better constrained model beats F by > 0.01, same sign in >= 4/5
         seeds; and
      2. that gap shrinks monotonically in f to <= 0.005 at f = 1.00.
    A constant offset at every fraction is not sample efficiency. The claim is an
    interaction and it must look like one.

Usage:  python3 h1_sample_efficiency.py --list | --job N | --summary
"""
import argparse, json, os, sys, time
import numpy as np, pandas as pd
import torch, torch.nn as nn, torch.nn.functional as F
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import r2_score

from port_rollout import MODELS, NX, NU, EPOCHS, BATCH, LR, WD, PATIENCE
from port_rollout_inspire import load, SCOLS

HERE = os.path.dirname(os.path.abspath(__file__))
STORE = os.path.join(HERE, "results_h1_sample_efficiency.json")
FRACTIONS = [0.02, 0.05, 0.10, 0.25, 0.50, 1.00]
LETTERS = ["P", "Pm", "U", "F"]
SEEDS = [0, 1, 2, 3, 4]
H_LONG = 12


def skill_multistep(net, d, te_idx, scX, U, h=H_LONG, cap=1500):
    g = d.iloc[te_idx].reset_index(drop=True)
    pos = {(o, s): i for i, (o, s) in enumerate(zip(g.op_id, g.slot))}
    starts = np.array([i for i, (o, s) in enumerate(zip(g.op_id, g.slot))
                       if all((o, s + k) in pos for k in range(1, h + 1))])
    if len(starts) < 50:
        return None
    if len(starts) > cap:
        starts = np.random.default_rng(0).choice(starts, cap, replace=False)
    gu = U[te_idx]
    x = torch.tensor(scX.transform(g.loc[starts, SCOLS].to_numpy(np.float32)))
    for k in range(h):
        ui = np.array([pos[(g.op_id[i], g.slot[i] + k)] for i in starts])
        x = net(x, torch.tensor(gu[ui]))[0].detach()
        x = torch.nan_to_num(x, nan=0.0, posinf=1e4, neginf=-1e4).clamp(-1e4, 1e4)
    ti = np.array([pos[(g.op_id[i], g.slot[i] + h)] for i in starts])
    true = scX.transform(g.loc[ti, SCOLS].to_numpy(np.float32))
    pers = scX.transform(g.loc[starts, SCOLS].to_numpy(np.float32))
    mse = float(np.mean((x.numpy() - true) ** 2))
    pmse = float(np.mean((pers - true) ** 2))
    return round(1 - mse / pmse, 4), int(len(starts))


def _save(r):
    prev = json.load(open(STORE)) if os.path.exists(STORE) else []
    old = next((x for x in prev if x["model"] == r["model"] and x["seed"] == r["seed"]), None)
    if old:
        old["curve"].update(r["curve"]); r = old
    prev = [x for x in prev if not (x["model"] == r["model"] and x["seed"] == r["seed"])]
    json.dump(prev + [r], open(STORE, "w"), indent=1, default=float)


def run(letter, seed, fracs=None):
    X0, _, Y0, g0, _ = load()
    gss = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=seed)
    trv, te = next(gss.split(X0, Y0, g0))
    mask = np.zeros(len(X0), bool); mask[trv] = True
    X, U, Y, grp, d = load(train_mask=mask)          # normaliser on the training pool only

    pool_ops = np.array(sorted(set(grp[trv])))
    rng = np.random.default_rng(1000 + seed)
    perm = rng.permutation(pool_ops)                 # one nested ordering, so the f=0.02
                                                     # subset is contained in f=0.05, etc.
    out = {"model": letter, "seed": seed, "n_pool_ops": int(len(pool_ops)),
           "n_test_rows": int(len(te)), "n_test_ops": int(len(set(grp[te]))),
           "curve": {}}

    for f in (fracs or FRACTIONS):
        k = max(int(round(f * len(pool_ops))), 12)
        keep = set(perm[:k].tolist())
        sel = np.array([i for i in trv if grp[i] in keep])
        gin = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=seed + 100)
        itr, iva = next(gin.split(X[sel], Y[sel], grp[sel]))
        tr, va = sel[itr], sel[iva]
        assert not (set(grp[tr]) & set(grp[te])), "operation leakage"

        scX = StandardScaler().fit(X[tr])
        Xtr, Xva, Xte = (scX.transform(X[i]).astype(np.float32) for i in (tr, va, te))
        Ytr, Yva, Yte = (scX.transform(Y[i]).astype(np.float32) for i in (tr, va, te))

        torch.manual_seed(seed)
        net = MODELS[letter]()
        opt = torch.optim.AdamW(net.parameters(), lr=LR, weight_decay=WD)
        bs = int(np.clip(len(tr) // 40, BATCH, BATCH * 8))
        dl = torch.utils.data.DataLoader(
            torch.utils.data.TensorDataset(torch.tensor(Xtr), torch.tensor(U[tr]),
                                           torch.tensor(Ytr)), batch_size=bs, shuffle=True)
        sch = torch.optim.lr_scheduler.CosineAnnealingLR(opt, EPOCHS)
        xv, uv, yv = torch.tensor(Xva), torch.tensor(U[va]), torch.tensor(Yva)
        t0 = time.time()
        best, bstate, bep, since = np.inf, None, -1, 0
        for ep in range(EPOCHS):
            net.train()
            for bx, bu, by in dl:
                opt.zero_grad()
                F.mse_loss(net(bx, bu)[0], by).backward()
                nn.utils.clip_grad_norm_(net.parameters(), 1.0)
                opt.step()
            sch.step()
            net.eval()
            v = float(F.mse_loss(net(xv, uv)[0], yv).detach())
            if v < best - 1e-6:
                best, bep, since = v, ep, 0
                bstate = {k2: t.clone() for k2, t in net.state_dict().items()}
            else:
                since += 1
                if since >= PATIENCE:
                    break
        net.load_state_dict(bstate); net.eval()

        pred = net(torch.tensor(Xte), torch.tensor(U[te]))[0].detach().numpy()
        mse = float(np.mean((pred - Yte) ** 2))
        pmse = float(np.mean((Xte - Yte) ** 2))
        ms = skill_multistep(net, d, te, scX, U)
        out["curve"][f"{f:.2f}"] = {
            "frac": f, "n_train_ops": int(len(set(grp[tr]))), "n_train_rows": int(len(tr)),
            "skill_1step": round(1 - mse / pmse, 4),
            "r2_1step": round(float(np.mean(
                [r2_score(Yte[:, i], pred[:, i]) for i in range(NX)])), 4),
            "skill_h12": ms[0] if ms else None, "n_h12": ms[1] if ms else None,
            "best_epoch": int(bep), "seconds": round(time.time() - t0, 1)}
        print(f"    f={f:.2f}  ops={len(set(grp[tr])):>4}  rows={len(tr):>6}  "
              f"skill1={out['curve'][f'{f:.2f}']['skill_1step']:+.4f}  "
              f"skill12={out['curve'][f'{f:.2f}']['skill_h12']}  "
              f"({out['curve'][f'{f:.2f}']['seconds']}s)", flush=True)
        _save({"model": letter, "seed": seed, "n_pool_ops": out["n_pool_ops"],
               "n_test_rows": out["n_test_rows"], "n_test_ops": out["n_test_ops"],
               "curve": {f"{f:.2f}": out["curve"][f"{f:.2f}"]}})   # incremental
    return out


def jobs():
    return [dict(letter=L, seed=s) for s in SEEDS for L in LETTERS]


def summary():
    rows = json.load(open(STORE))
    rec = []
    for r in rows:
        for f, c in r["curve"].items():
            rec.append({"model": r["model"], "seed": r["seed"], "frac": float(f),
                        "ops": c["n_train_ops"], "skill1": c["skill_1step"],
                        "skill12": c["skill_h12"]})
    d = pd.DataFrame(rec)
    pd.set_option("display.width", 200)
    for tgt, name in [("skill1", "PRIMARY: one-step skill"),
                      ("skill12", "SECONDARY: 12-step (60 min) skill")]:
        p = d.pivot_table(index="frac", columns="model", values=tgt, aggfunc="mean")
        n = d.groupby("frac").ops.first()
        p.insert(0, "train_ops", n)
        print(f"\n--- {name} (mean over {d.seed.nunique()} seeds) ---")
        print(p.round(4).to_string())
        if {"P", "Pm", "F"} <= set(p.columns):
            best = p[["P", "Pm"]].max(axis=1)
            print("  gap (best constrained - F):",
                  (best - p["F"]).round(4).to_dict())
    print("\n--- DECISION RULE (PROTOCOL_v2_benefit.md) ---")
    p = d.pivot_table(index="frac", columns="model", values="skill1", aggfunc="mean")
    gap = p[["P", "Pm"]].max(axis=1) - p["F"]
    lowf = [f for f in gap.index if f <= 0.05]
    c1_val = float(gap.loc[lowf].max()) if lowf else float("nan")
    per_seed = []
    for s in sorted(d.seed.unique()):
        ds = d[(d.seed == s) & (d.frac <= 0.05)].pivot_table(
            index="frac", columns="model", values="skill1")
        if {"P", "Pm", "F"} <= set(ds.columns):
            per_seed.append(float((ds[["P", "Pm"]].max(axis=1) - ds["F"]).max()))
    c1 = (c1_val > 0.01) and (sum(v > 0 for v in per_seed) >= 4)
    c2 = float(gap.loc[1.00]) <= 0.005 and gap.is_monotonic_decreasing
    print(f"  1. gap > 0.01 at f<=0.05 and same sign in >=4/5 seeds : "
          f"max gap {c1_val:+.4f}, positive in {sum(v>0 for v in per_seed)}/5  -> {c1}")
    print(f"  2. gap shrinks monotonically to <=0.005 at f=1.00     : "
          f"gap@1.00 {float(gap.loc[1.00]):+.4f}, monotone {gap.is_monotonic_decreasing}  -> {c2}")
    print(f"\n  H1 {'SUPPORTED' if (c1 and c2) else 'NOT SUPPORTED'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", type=int, default=None)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--fracs", default=None, help="comma list, e.g. 0.02,0.05,0.10")
    ap.add_argument("--models", default=None, help="comma list, e.g. P,Pm,U,F")
    ap.add_argument("--seed", type=int, default=None)
    a = ap.parse_args()
    J = jobs()
    if a.list:
        for k, j in enumerate(J):
            print(f"{k:2d}  {j['letter']:2s}  seed {j['seed']}")
        sys.exit(0)
    if a.summary:
        summary(); sys.exit(0)
    fr = [float(x) for x in a.fracs.split(",")] if a.fracs else None
    if a.seed is not None:
        for L in (a.models.split(",") if a.models else LETTERS):
            print(f"-- {L} seed {a.seed} fracs={fr or FRACTIONS}", flush=True)
            run(L, a.seed, fr)
        sys.exit(0)
    j = J[a.job]
    print(f"[{a.job}] {j['letter']} seed {j['seed']}", flush=True)
    run(j["letter"], j["seed"], fr)
    print(f"[{a.job}] done")
