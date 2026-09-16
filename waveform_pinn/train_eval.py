# -*- coding: utf-8 -*-
"""Paper 2 — train on pulse contour, freeze, then evaluate against thermodilution.

Execution order is enforced by the script, not by discipline: the TD-only set is loaded
only after the model has been trained and put in eval mode (PROTOCOL.md §4).

Usage
-----
    python3 train_eval.py                 # primary + secondary + negative controls
    python3 train_eval.py --seeds 0 1 2
    python3 train_eval.py --ablation      # also run models B, C, D
"""
import argparse, json, os, sys, time
import numpy as np, pandas as pd
import torch, torch.nn as nn, torch.nn.functional as F
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import r2_score
from sklearn.linear_model import LinearRegression

import models as M
import agreement as A

HERE = os.path.dirname(os.path.abspath(__file__))
EPOCHS, BATCH, LR, WD = 200, 64, 2e-3, 1e-4
EPOCHS_V2, BATCH_V2 = 40, 512   # window data has ~35x the rows; fewer passes, larger batches


# --------------------------------------------------------------------- data
def load(features="wave_features2_0.csv"):
    df = pd.read_csv(os.path.join(HERE, features))
    pc = df[df.tier.isin(["PC", "BOTH"])].copy()
    td = df[df.tier == "TD_ONLY"].copy()
    both = df[df.tier == "BOTH"].copy()
    return df, pc, td, both


def by_patient(pred, truth, groups):
    """Collapse multiple windows per case to one prediction and one reference per patient.

    With v2 window extraction a case contributes ~35 rows. Computing agreement over rows
    would report n in the hundreds when the number of independent patients is unchanged,
    and every confidence interval would be too narrow by roughly sqrt(windows per case).
    All agreement statistics are therefore computed on patient medians."""
    d = pd.DataFrame({"g": groups, "p": pred, "y": truth})
    a = d.groupby("g").median()
    return a.p.to_numpy(), a.y.to_numpy()


def matrices(frame, cols, target):
    X = frame[cols].to_numpy(np.float32)
    y = frame[target].to_numpy(np.float32).reshape(-1, 1)
    ok = np.isfinite(X).all(1) & np.isfinite(y).ravel()
    return X[ok], y[ok], frame.loc[ok, "caseid"].to_numpy()


# -------------------------------------------------------------------- train
def fit(model, Xtr, Ytr, seed, soft=False, epochs=EPOCHS, batch=BATCH):
    torch.manual_seed(seed)
    dl = torch.utils.data.DataLoader(
        torch.utils.data.TensorDataset(torch.tensor(Xtr), torch.tensor(Ytr)),
        batch_size=batch, shuffle=True)
    opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=WD)
    sch = torch.optim.lr_scheduler.CosineAnnealingLR(opt, epochs)
    best, best_state = np.inf, None
    for _ in range(epochs):
        model.train(); tot = 0.0
        for bx, by in dl:
            opt.zero_grad()
            pred, H, T, V, R = model(bx)
            loss = F.mse_loss(pred, by)
            if soft:
                loss = loss + M.physics_penalty(H, T, V, R)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step(); tot += loss.item()
        sch.step()
        if tot < best:
            best = tot
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
    model.load_state_dict(best_state)
    model.eval()
    return model


def predict(model, X, scX, scY):
    with torch.no_grad():
        p, H, T, V, R = model(torch.tensor(scX.transform(X).astype(np.float32)))
    return (p.numpy() * scY.scale_ + scY.mean_).ravel(), (H, T, V, R)


# ---------------------------------------------------------------- experiment
def run_target(pc, td, cols, target, td_target, seed, letter="A", soft=False,
               permute=False, label=""):
    Xtr, Ytr, gtr = matrices(pc, cols, target)
    if len(Xtr) < 50:
        return None
    if permute:                                  # negative control §4.1
        Ytr = Ytr[np.random.default_rng(seed).permutation(len(Ytr))]

    gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=seed)
    tr, va = next(gss.split(Xtr, Ytr, gtr))
    assert not (set(gtr[tr]) & set(gtr[va])), "case leakage"

    scX = StandardScaler().fit(Xtr[tr]); scY = StandardScaler().fit(Ytr[tr])
    net = M.MODELS[letter](len(cols), 1)
    v2 = len(tr) > 5000                       # window-level dataset
    net = fit(net, scX.transform(Xtr[tr]).astype(np.float32),
              scY.transform(Ytr[tr]).astype(np.float32), seed, soft=soft,
              epochs=EPOCHS_V2 if v2 else EPOCHS, batch=BATCH_V2 if v2 else BATCH)

    res = {"label": label, "target": target, "model": letter, "seed": seed,
           "n_train": int(len(tr)), "n_val": int(len(va)), "n_features": len(cols)}

    # ---- internal validation on held-out pulse-contour cases (SECONDARY) ----
    pv, _ = predict(net, Xtr[va], scX, scY)
    pv_p, yv_p = by_patient(pv, Ytr[va].ravel(), gtr[va])
    res["n_val_patients"] = int(len(pv_p))
    res["internal_r2"] = round(float(r2_score(yv_p, pv_p)), 4)          # patient level
    res["internal_r2_window"] = round(float(r2_score(Ytr[va].ravel(), pv)), 4)
    res["internal_agreement"] = A.full_report(pv_p, yv_p, "PC held-out (patient)", ci=False)

    # ---- physical-validity diagnostics ----
    with torch.no_grad():
        _, H, T, V, R = net(torch.tensor(scX.transform(Xtr[va]).astype(np.float32)))
    res["violations"] = M.violations(H, T, V, R)

    # ---- model is now frozen; only now is thermodilution touched (PRIMARY) ----
    if td_target is not None and len(td):
        Xte, Yte, gte = matrices(td, cols, td_target)
        if len(Xte) >= 8:
            pt, _ = predict(net, Xte, scX, scY)
            pt_p, yt_p = by_patient(pt, Yte.ravel(), gte)
            res["n_test_patients"] = int(len(pt_p))
            res["external_agreement"] = A.full_report(
                pt_p, yt_p, "thermodilution (TD-only, patient level)")
    return res


def device_benchmark(both, td_report):
    """PROTOCOL.md §3.1 — non-inferiority to the deployed pulse-contour device.

    The 24 BOTH cases carry pulse-contour and thermodilution CO for the same patient,
    giving the device's own agreement with the reference. Delta <= 0 means a model that
    never saw thermodilution matches or beats the device it was trained to imitate."""
    if both is None or len(both) < 8 or not td_report or "pct_error" not in td_report:
        return None
    d = both.dropna(subset=["CO_pc", "CO_td"])
    if len(d) < 8:
        return None
    dev = A.full_report(d.CO_pc.to_numpy(), d.CO_td.to_numpy(),
                        "device (FloTrac) vs thermodilution")
    return {"label": "PRIMARY: non-inferiority to device",
            "model_pe": td_report["pct_error"], "model_pe_ci": td_report["pct_error_ci"],
            "device_pe": dev["pct_error"], "device_pe_ci": dev["pct_error_ci"],
            "delta_pe": round(td_report["pct_error"] - dev["pct_error"], 3),
            "n_model": td_report["n"], "n_device": dev["n"],
            "verdict": ("model matches or beats the device"
                        if td_report["pct_error"] <= dev["pct_error"]
                        else "device retains an advantage of "
                             f"{td_report['pct_error'] - dev['pct_error']:.1f} pp"),
            "device_detail": dev}


def linear_baseline(pc, td, cols, target, td_target, seed):
    """Negative control §4.1 — if a linear model matches the network, the network
    is not what produced the result."""
    Xtr, Ytr, gtr = matrices(pc, cols, target)
    gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=seed)
    tr, va = next(gss.split(Xtr, Ytr, gtr))
    lm = LinearRegression().fit(Xtr[tr], Ytr[tr].ravel())
    pv_p, yv_p = by_patient(lm.predict(Xtr[va]), Ytr[va].ravel(), gtr[va])
    out = {"label": "linear baseline", "target": target, "seed": seed,
           "n_val_patients": int(len(pv_p)),
           "internal_r2": round(float(r2_score(yv_p, pv_p)), 4)}
    if td_target is not None and len(td):
        Xte, Yte, gte = matrices(td, cols, td_target)
        if len(Xte) >= 8:
            pt_p, yt_p = by_patient(lm.predict(Xte), Yte.ravel(), gte)
            out["n_test_patients"] = int(len(pt_p))
            out["external_agreement"] = A.full_report(
                pt_p, yt_p, "thermodilution (TD-only, patient level)")
    return out


def job_list(seeds, ablation):
    """One dict per experiment. Jobs are run individually so that a long sweep can be
    resumed, and so no single invocation has to complete the whole protocol."""
    jobs = []
    for s in seeds:
        jobs += [
            dict(kind="net", cols="MORPH", target="CO_pc", td="CO_td", seed=s, letter="A",
                 label="primary: CO, full morphology"),
            dict(kind="net", cols="LEVEL", target="CO_pc", td="CO_td", seed=s, letter="A",
                 label="control: level only (no morphology)"),
            dict(kind="net", cols="MORPH", target="CO_pc", td="CO_td", seed=s, letter="A",
                 permute=True, label="control: permuted labels"),
            dict(kind="linear", cols="MORPH", target="CO_pc", td="CO_td", seed=s,
                 label="control: linear baseline"),
            dict(kind="net", cols="MORPH_DEMO", target="CO_pc", td="CO_td", seed=s,
                 letter="A", label="v3: morphology + demographics"),
            dict(kind="net", cols="DEMO", target="CO_pc", td="CO_td", seed=s, letter="A",
                 label="v3 control: demographics + HR/MAP only"),
            dict(kind="linear", cols="MORPH_DEMO", target="CO_pc", td="CO_td", seed=s,
                 label="v3 control: linear on morphology + demographics"),
            dict(kind="net", cols="MORPH", target="SV_pc", td=None, seed=s, letter="A",
                 label="secondary: SV"),
            dict(kind="net", cols="MORPH", target="R_tot", td=None, seed=s, letter="A",
                 label="secondary: R_tot"),
        ]
        if ablation:
            for L in "BCD":
                jobs.append(dict(kind="net", cols="MORPH_DEMO", target="CO_pc",
                                 td="CO_td", seed=s, letter=L, soft=(L == "D"),
                                 label=f"ablation {L} (v3 inputs)"))
    return jobs


def run_job(j, pc, td):
    cols = {"MORPH": M.MORPH_COLS, "LEVEL": M.LEVEL_COLS,
            "MORPH_DEMO": M.MORPH_DEMO_COLS, "DEMO": M.DEMO_ONLY_COLS}[j["cols"]]
    if j["kind"] == "linear":
        return linear_baseline(pc, td, cols, j["target"], j["td"], j["seed"])
    return run_target(pc, td, cols, j["target"], j["td"], j["seed"],
                      letter=j.get("letter", "A"), soft=j.get("soft", False),
                      permute=j.get("permute", False), label=j["label"])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--ablation", action="store_true")
    ap.add_argument("--features", default="wave_features2_0.csv")
    ap.add_argument("--job", type=int, default=None,
                    help="run a single job by index and append it to results_paper2.json")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    jobs = job_list(args.seeds, args.ablation)
    if args.list:
        for k, j in enumerate(jobs):
            print(f"{k:3d}  seed{j['seed']}  {j['label']}")
        sys.exit(0)

    df, pc, td, both = load(args.features)
    print(f"PC (train)      : {len(pc)}", flush=True)
    print(f"TD_ONLY (primary): {len(td)}")
    print(f"BOTH (paired)   : {len(both)}")
    if len(td) < 8:
        print("\nTD-only set too small to evaluate the primary endpoint.")

    store = os.path.join(HERE, "results_paper2.json")
    if args.job is not None:
        prev = json.load(open(store)) if os.path.exists(store) else []
        j = jobs[args.job]
        t0 = time.time()
        r = run_job(j, pc, td)
        if r:
            r["job"] = args.job
            prev = [x for x in prev if x.get("job") != args.job] + [r]
            json.dump(prev, open(store, "w"), indent=1, default=float)
        ext = (r or {}).get("external_agreement", {})
        print(f"[{args.job}] {j['label']}  R2={r.get('internal_r2') if r else None}"
              f"  {('TD n=%s r=%s PE=%s%%' % (ext.get('n'), ext.get('pearson_r'), ext.get('pct_error'))) if ext.get('n') else ''}"
              f"  ({time.time()-t0:.0f}s)", flush=True)
        sys.exit(0)

    results, t0 = [], time.time()
    for seed in args.seeds:
        # PRIMARY: cardiac output, trained on pulse contour, tested on thermodilution
        results.append(run_target(pc, td, M.MORPH_COLS, "CO_pc", "CO_td", seed,
                                  label="primary: CO, full morphology"))
        # negative controls (PROTOCOL.md §4.1)
        results.append(run_target(pc, td, M.LEVEL_COLS, "CO_pc", "CO_td", seed,
                                  label="control: level only (no morphology)"))
        results.append(run_target(pc, td, M.MORPH_COLS, "CO_pc", "CO_td", seed,
                                  permute=True, label="control: permuted labels"))
        results.append(linear_baseline(pc, td, M.MORPH_COLS, "CO_pc", "CO_td", seed))
        # SECONDARY: stroke volume and Windkessel resistance
        for tgt in ["SV_pc", "R_tot"]:
            if tgt in pc and np.isfinite(pc[tgt]).sum() > 50:
                results.append(run_target(pc, td, M.MORPH_COLS, tgt, None, seed,
                                          label=f"secondary: {tgt}"))
        if args.ablation:
            for L in "BCD":
                results.append(run_target(pc, td, M.MORPH_COLS, "CO_pc", "CO_td", seed,
                                          letter=L, soft=(L == "D"),
                                          label=f"ablation {L}"))
        print(f"  seed {seed} done ({time.time()-t0:.0f}s)", flush=True)

    results = [r for r in results if r]

    # pre-specified primary comparison, once per seed's primary run
    for r in list(results):
        if r.get("label", "").startswith("primary"):
            bench = device_benchmark(both, r.get("external_agreement"))
            if bench:
                bench["seed"] = r["seed"]
                results.append(bench)

    out = os.path.join(HERE, "results_paper2.json")
    json.dump(results, open(out, "w"), indent=1, default=float)
    print(f"\nsaved {len(results)} runs -> results_paper2.json\n")

    for r in results:
        if r.get("label", "").startswith("PRIMARY"):
            print(f"\n{r['label']}: model PE={r['model_pe']}% {r['model_pe_ci']} "
                  f"(n={r['n_model']})  vs  device PE={r['device_pe']}% "
                  f"{r['device_pe_ci']} (n={r['n_device']})")
            print(f"  delta = {r['delta_pe']} pp  ->  {r['verdict']}\n")
            continue
        line = f"{r.get('label','?'):42s} R2_int={r.get('internal_r2')}"
        ext = r.get("external_agreement")
        if ext and "pct_error" in ext:
            line += (f"  | TD n={ext['n']} r={ext['pearson_r']} "
                     f"PE={ext['pct_error']}% {ext['pct_error_ci']}")
        print(line)
