# -*- coding: utf-8 -*-
"""Paper B — the missing downstream consumer: a port-Hamiltonian model with a real input,
iterated as a simulator.

`PAPER_B_OUTLINE.md` names its own weakness: "The benefit of an admissible internal state is
not demonstrated here. It follows only if the state is consumed downstream ... and no such
consumer was built." Every other Paper B model is a static per-sample map with no exogenous
input, so `xdot = [J-R] dH/dx + g(x)u` was used with u absent -- the *port* was never
connected. This connects it and iterates the learned map.

REVISION 2026-08-12, after an independent adversarial audit of the first version. Six
defects were found; all are fixed here and each fix is marked [AUDIT-n] at its site.

 1. FROZEN STEPS. 77-93% of the counted rollout steps were exact numerical fixed points, so
    the denominator "406,358 steps" was inflated about fourfold, and the cumulative-path
    control could not detect the frozen case it was written to exclude. Passivity is now
    counted over *moving* steps and both denominators are reported.
 2. FLOAT32 + ABSOLUTE THRESHOLD. `dH > 1e-6` in float32 suppressed genuine small gains by
    the unconstrained models and hid float32 roundoff in the constrained one. Energy
    differences are now computed in float64 against a *relative* threshold.
 3. MODEL F HAS NO HAMILTONIAN. F's `H_head` never entered the loss, so its gradient was
    always None and its weights never moved. Every energy statistic reported for F was a
    measurement of a randomly initialised network. F now returns no H and is used only as a
    one-step accuracy comparator.
 4. U's ENERGY HAS NO SIGN. For U, H, J and R are all free heads and the dynamics
    `(J-R)grad H` is exactly invariant under `(H,J,R) -> (-H,-J,-R)`. "U gains energy on x%
    of steps" can be reported as `100-x` for a bit-identical model. Both conventions are
    now reported, which is the honest statement: U has no energy function, only a function
    labelled H.
 5. GROWTH-ORDER CONFOUND. P's `R = LL^T` is quadratic in its head output while U's
    `R = (M+M^T)/2` is linear, so P's vector field grows one polynomial order faster and
    takes ~9x larger steps under displacement. The displacement result was therefore
    attributable to the parameterisation, not the constraint. Model **Pm** is added: PSD by
    a softplus diagonal, hence linear in its head output like U, with everything else
    identical. Pm is the control that separates the two explanations.
 6. THE DISPLACEMENT CONDITIONS DID NOT TEST BOUNDEDNESS. At 6 sigma only 20.3% of the
    initial states were inside the physiological box and at 24 sigma only 0.44%, so the
    metric measured recovery from an already-impossible state. A `box_uniform` condition is
    added whose starts are admissible by construction; the sigma conditions are retained but
    relabelled as recovery tests with their admissible fraction reported.

Also fixed: trajectories are frozen at the moment they leave the box rather than clamped and
integrated onward, so terminal energy and path length are no longer clamp artefacts; the
input normaliser is fit on training rows only; and the persistence baseline is averaged over
seeds instead of being read from the first run.

Data: `eicu_drug_response.csv` -- 2,720 vasoactive-drug episodes in 1,445 eICU patients,
each a supervised one-step transition (x_t, u) -> x_{t+1}.
    x = (CO, SBP, DBP, HR);  u = onehot(mechanism) * within-class z-score of log1p(rate)

Usage:  python3 port_rollout.py --list | --job N | --summary
"""
import argparse, json, os, sys, time
import numpy as np, pandas as pd
import torch, torch.nn as nn, torch.nn.functional as F
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import r2_score

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.dirname(HERE), "eicu_drug_response.csv")
STORE = os.path.join(HERE, "results_port_rollout.json")

STATE = ["co", "sbp", "dbp", "hr"]
NX, NU = 4, 4
MECHS = ["vasopressor", "vasodilator", "inotrope", "vasopressor_inotrope"]
BOX = {"co": (0.5, 20.0), "sbp": (40.0, 260.0), "dbp": (15.0, 160.0), "hr": (20.0, 220.0)}
EPOCHS, BATCH, LR, WD, PATIENCE = 300, 128, 1e-3, 1e-3, 40
LETTERS = ["P", "Pm", "U", "F"]
SEEDS = [0, 1, 2]
MOVE_FRAC = 0.01          # a step counts as motion if |dx| > 1% of that trajectory's first
REL_TOL = 1e-6            # relative energy tolerance, |dH| > REL_TOL * |H_t|


# ------------------------------------------------------------------ data
def load(train_mask=None):
    """[AUDIT] The within-class rate z-score is fit on `train_mask` rows only. Fitting it
    over the whole file, as the first version did, lets the test rows influence their own
    normalisation."""
    d = pd.read_csv(SRC)
    keep = np.ones(len(d), bool)
    for v, (lo, hi) in BOX.items():
        keep &= d[f"pre_{v}"].between(lo, hi) & d[f"post_{v}"].between(lo, hi)
    d = d[keep].reset_index(drop=True)
    lr = np.log1p(d.avg_rate.to_numpy())
    fitmask = np.ones(len(d), bool) if train_mask is None else train_mask
    r = np.zeros(len(d))
    for cls in d.drug_class.unique():
        m = (d.drug_class == cls).to_numpy()
        ref = lr[m & fitmask]
        mu, sd = (ref.mean(), ref.std()) if ref.size > 1 else (lr[m].mean(), lr[m].std())
        r[m] = (lr[m] - mu) / (sd + 1e-9)
    U = np.zeros((len(d), NU), np.float32)
    for k, mch in enumerate(MECHS):
        U[:, k] = (d.mechanism.to_numpy() == mch) * r
    X = d[[f"pre_{v}" for v in STATE]].to_numpy(np.float32)
    Y = d[[f"post_{v}" for v in STATE]].to_numpy(np.float32)
    return X, U, Y, d.patientunitstayid.to_numpy(), d


# ---------------------------------------------------------------- models
class Enc(nn.Module):
    def __init__(self, n_in, width=96, depth=3):
        super().__init__()
        L, dd = [], n_in
        for _ in range(depth):
            L += [nn.Linear(dd, width), nn.SiLU()]
            dd = width
        self.net, self.out_dim = nn.Sequential(*L), width

    def forward(self, z):
        return self.net(z)


class PortBase(nn.Module):
    HAS_H = True

    def __init__(self, width=96):
        super().__init__()
        self.enc = Enc(NX, width)
        h = self.enc.out_dim
        self.J_head = nn.Linear(h, NX * NX)
        self.g_head = nn.Linear(h, NX * NU)
        idx = torch.tril_indices(NX, NX)
        self.register_buffer("ti", idx[0])
        self.register_buffer("tj", idx[1])

    def forward(self, x, u):
        x = x.requires_grad_(True)
        H = self.hamiltonian(x)
        dH = torch.autograd.grad(H.sum(), x, create_graph=self.training)[0]
        h = self.enc(x)
        R, J = self.RJ(h)
        g = self.g_head(h).view(-1, NX, NU)
        xdot = (torch.bmm(J - R, dH.unsqueeze(2)).squeeze(2)
                + torch.bmm(g, u.unsqueeze(2)).squeeze(2))
        return x + xdot, H, R, J


class PortConstrained(PortBase):
    """Model P — H = T+V with T,V >= 0; R = LL^T PSD (quadratic in the head); J skew."""

    def __init__(self, width=96):
        super().__init__(width)
        h = self.enc.out_dim
        self.T_head = nn.Linear(h, 1)
        self.V_head = nn.Linear(h, 1)
        self.L_head = nn.Linear(h, NX * (NX + 1) // 2)

    def hamiltonian(self, x):
        h = self.enc(x)
        return F.softplus(self.T_head(h)) + F.softplus(self.V_head(h))

    def RJ(self, h):
        v = self.L_head(h)
        L = h.new_zeros(h.shape[0], NX, NX)
        L[:, self.ti, self.tj] = v
        d = torch.arange(NX, device=h.device)
        L[:, d, d] = F.softplus(L[:, d, d]) + 1e-6
        S = self.J_head(h).view(-1, NX, NX)
        return L @ L.transpose(1, 2), S - S.transpose(1, 2)


class PortConstrainedMatched(PortConstrained):
    """Model Pm — [AUDIT-5] the growth-order control.

    P's `R = LL^T` is quadratic in the L_head output; U's `R = (M+M^T)/2` is linear. P's
    vector field therefore grows one polynomial order faster in ||h||, which on its own
    explains the ~9x larger steps P took under displacement. Pm keeps every guarantee -- R
    is positive semidefinite, H = T+V >= 0, J skew -- but obtains PSD from a softplus
    diagonal, which is asymptotically *linear* in its head output, matching U.

    If the displacement result is caused by the constraint it should survive in Pm. If it is
    caused by the parameterisation's growth order it should disappear.
    """

    def RJ(self, h):
        d = F.softplus(self.L_head(h)[:, :NX]) + 1e-6      # linear growth, still >= 0
        R = torch.diag_embed(d)
        S = self.J_head(h).view(-1, NX, NX)
        return R, S - S.transpose(1, 2)


class PortUnconstrained(PortBase):
    """Model U — identical topology, every guarantee removed.

    [AUDIT-4] H, J and R are all free, and the dynamics is invariant under the joint sign
    flip (H,J,R) -> (-H,-J,-R). U therefore has no energy function, only a function labelled
    H whose sign is a gauge choice. Results are reported under both conventions.
    """

    def __init__(self, width=96):
        super().__init__(width)
        h = self.enc.out_dim
        self.H_head = nn.Linear(h, 1)
        self.R_head = nn.Linear(h, NX * NX)

    def hamiltonian(self, x):
        return self.H_head(self.enc(x))

    def RJ(self, h):
        Mr = self.R_head(h).view(-1, NX, NX)
        J = self.J_head(h).view(-1, NX, NX)
        return 0.5 * (Mr + Mr.transpose(1, 2)), J


class FreeMLP(nn.Module):
    """Model F — no port-Hamiltonian structure. [AUDIT-3] F has no Hamiltonian at all; the
    previous version carried an `H_head` that received no gradient and whose statistics were
    therefore those of a random network. It is removed. F is a one-step accuracy comparator
    only and contributes no energy result."""

    HAS_H = False

    def __init__(self, width=96):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(NX + NU, width), nn.SiLU(),
                                 nn.Linear(width, width), nn.SiLU(),
                                 nn.Linear(width, width), nn.SiLU(),
                                 nn.Linear(width, NX))

    def forward(self, x, u):
        return x + self.net(torch.cat([x, u], 1)), None, None, None


MODELS = {"P": PortConstrained, "Pm": PortConstrainedMatched,
          "U": PortUnconstrained, "F": FreeMLP}


# --------------------------------------------------------------- helpers
def psd_violations(R):
    if R is None:
        return -1, float("nan")
    ev = torch.linalg.eigvalsh(R.detach().double())
    lo, hi = ev.min(1).values, ev.max(1).values.clamp_min(1e-30)
    return int((lo < -1e-6 * hi).sum()), float((lo / hi).min())


def skew_error(J):
    if J is None:
        return float("nan")
    Jd = J.detach()
    return float((Jd + Jd.transpose(1, 2)).abs().max())


def in_box(phys):
    lo = torch.tensor([[BOX[v][0] for v in STATE]])
    hi = torch.tensor([[BOX[v][1] for v in STATE]])
    return ((phys >= lo) & (phys <= hi)).all(1)


def rollout(net, x0, u, n_steps, scX):
    """Iterate the learned map.

    [AUDIT-6/clamp] A trajectory is FROZEN at the step it leaves the physiological box: it
    is neither integrated further nor clamped. The previous version repaired the state with
    `nan_to_num(...).clamp(+-1e6)` every step and then reported terminal energy and path
    length computed over the repaired trajectory, which produced artefacts such as a median
    path length of 1.2e14. Divergence is recorded at the moment it happens instead.
    """
    mu = torch.tensor(scX.mean_, dtype=torch.float32)
    sd = torch.tensor(scX.scale_, dtype=torch.float32)
    n = len(x0)

    x = x0.clone()
    start = x0.clone()
    live = in_box(x * sd + mu).clone()          # trajectories still being integrated
    started_inside = live.clone()
    first_exit = torch.where(live, torch.full((n,), n_steps), torch.zeros(n, dtype=torch.long))
    diverged = torch.zeros(n, dtype=torch.bool)
    path = torch.zeros(n)
    step_norms, H_list, move_list = [], [], []
    first_step = None

    for t in range(n_steps):
        if not live.any():
            break
        out = net(x, u)
        xn = out[0].detach()
        H = out[1].detach() if out[1] is not None else None
        bad = ~torch.isfinite(xn).all(1)
        xn = torch.where(bad.unsqueeze(1), x, xn)           # do not propagate nan/inf
        dx = (xn - x).norm(dim=1)
        if first_step is None:
            first_step = dx.clone().clamp_min(1e-12)
        # [AUDIT-1] a step counts only if the state actually moved
        moved = (dx > MOVE_FRAC * first_step) & live
        move_list.append(moved.clone())
        step_norms.append(torch.where(live, dx, torch.zeros_like(dx)))
        path = path + torch.where(live, dx, torch.zeros_like(dx))
        if H is not None:
            H_list.append(torch.where(live, H.squeeze(1), torch.full((n,), float("nan"))))
        x = torch.where(live.unsqueeze(1), xn, x)
        inside = in_box(x * sd + mu)
        newly = live & (~inside | bad)
        first_exit[newly] = t
        diverged = diverged | (live & bad)
        live = live & inside & ~bad

    res = dict(
        n_traj=int(n), n_started_inside=int(started_inside.sum()),
        frac_started_inside=round(float(started_inside.float().mean()), 4),
        frac_admissible=round(float((live & started_inside).float().sum()
                                    / max(int(started_inside.sum()), 1)), 4),
        frac_diverged=round(float(diverged.float().mean()), 4),
        median_steps_to_exit=float(first_exit[started_inside].float().median())
        if started_inside.any() else float("nan"),
        median_path_length=round(float(path[started_inside].median()), 4)
        if started_inside.any() else float("nan"),
        median_net_displacement=round(float((x - start)[started_inside].norm(dim=1).median()), 4)
        if started_inside.any() else float("nan"),
        n_steps_counted=int(torch.stack(step_norms).numel()) if step_norms else 0,
        n_steps_moving=int(torch.stack(move_list).sum()) if move_list else 0,
    )
    res["frac_steps_moving"] = round(res["n_steps_moving"] / max(res["n_steps_counted"], 1), 4)
    res["_H"] = torch.stack(H_list, 1) if H_list else None
    res["_move"] = torch.stack(move_list, 1) if move_list else None
    return res


def energy_report(Ht, move):
    """[AUDIT-1,2,4] Energy accounting in float64, against a relative threshold, over moving
    steps as well as all steps, and under both sign conventions."""
    if Ht is None:
        return None
    H = Ht.double()
    dH = H[:, 1:] - H[:, :-1]
    base = H[:, :-1].abs().clamp_min(1e-12)
    mv = move[:, 1:] if move is not None else torch.ones_like(dH, dtype=torch.bool)
    ok = torch.isfinite(dH) & torch.isfinite(base)
    out = {}
    for tag, sel in [("all_steps", ok), ("moving_steps", ok & mv)]:
        nsel = int(sel.sum())
        if nsel == 0:
            out[tag] = None
            continue
        gain_rel = ((dH > REL_TOL * base) & sel).sum().item()
        loss_rel = ((dH < -REL_TOL * base) & sel).sum().item()
        out[tag] = {
            "n_steps": nsel,
            "frac_gain_relative": round(gain_rel / nsel, 6),
            "frac_gain_strict_positive": round(float(((dH > 0) & sel).sum().item() / nsel), 6),
            # sign gauge: for a model with no sign convention the alternative reading
            "frac_gain_under_sign_flip": round(loss_rel / nsel, 6),
            "max_dH": float(dH[sel].max()), "min_dH": float(dH[sel].min()),
            "max_dH_relative": float((dH / base)[sel].max()),
        }
    return out


# ------------------------------------------------------------------- run
def run(letter, seed):
    X0, _, Y0, grp0, _ = load()
    gss = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=seed)
    trv, te = next(gss.split(X0, Y0, grp0))
    mask = np.zeros(len(X0), bool); mask[trv] = True
    X, U, Y, grp, _ = load(train_mask=mask)          # normaliser fit on training rows only

    gin = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=seed + 100)
    itr, iva = next(gin.split(X[trv], Y[trv], grp[trv]))
    tr, va = trv[itr], trv[iva]
    for a, b, nm in [(tr, te, "train/test"), (tr, va, "train/val"), (va, te, "val/test")]:
        assert not (set(grp[a]) & set(grp[b])), f"patient leakage: {nm}"

    scX = StandardScaler().fit(X[tr])
    Xtr, Xva, Xte = (scX.transform(X[i]).astype(np.float32) for i in (tr, va, te))
    Ytr, Yva, Yte = (scX.transform(Y[i]).astype(np.float32) for i in (tr, va, te))
    Utr, Uva, Ute = U[tr], U[va], U[te]

    torch.manual_seed(seed)
    net = MODELS[letter]()
    opt = torch.optim.AdamW(net.parameters(), lr=LR, weight_decay=WD)
    sch = torch.optim.lr_scheduler.CosineAnnealingLR(opt, EPOCHS)
    dl = torch.utils.data.DataLoader(
        torch.utils.data.TensorDataset(torch.tensor(Xtr), torch.tensor(Utr), torch.tensor(Ytr)),
        batch_size=BATCH, shuffle=True)
    xv, uv, yv = torch.tensor(Xva), torch.tensor(Uva), torch.tensor(Yva)

    t0 = time.time()
    best, best_state, best_ep, since = np.inf, None, -1, 0
    for ep in range(EPOCHS):
        net.train()
        for bx, bu, by in dl:
            opt.zero_grad()
            F.mse_loss(net(bx, bu)[0], by).backward()
            nn.utils.clip_grad_norm_(net.parameters(), 1.0)
            opt.step()
        sch.step()
        net.eval()
        vmse = float(F.mse_loss(net(xv, uv)[0], yv).detach())
        if vmse < best - 1e-6:
            best, best_ep, since = vmse, ep, 0
            best_state = {k: v.clone() for k, v in net.state_dict().items()}
        else:
            since += 1
            if since >= PATIENCE:
                break
    net.load_state_dict(best_state); net.eval()

    n_par = sum(p.numel() for p in net.parameters())
    dead = sorted(n for n, p in net.named_parameters() if p.grad is None)
    n_dead = int(sum(p.numel() for n, p in net.named_parameters() if p.grad is None))
    res = {"model": letter, "seed": seed, "has_hamiltonian": bool(MODELS[letter].HAS_H
           if hasattr(MODELS[letter], "HAS_H") else True),
           "n_params": int(n_par), "n_params_dead": n_dead, "dead_tensors": dead,
           "n_params_active": int(n_par - n_dead),
           "n_train": int(len(tr)), "n_val": int(len(va)), "n_test": int(len(te)),
           "n_train_patients": int(len(set(grp[tr]))),
           "n_test_patients": int(len(set(grp[te]))),
           "best_epoch": int(best_ep), "val_mse": round(best, 5),
           "train_seconds": round(time.time() - t0, 1)}

    # ---- 1. ONE-STEP ACCURACY (the control) ----
    xt, ut = torch.tensor(Xte), torch.tensor(Ute)
    pred, H, R, J = net(xt, ut)
    pred = pred.detach().numpy()
    res["onestep_mse"] = round(float(np.mean((pred - Yte) ** 2)), 5)
    res["onestep_r2_per_dim"] = {v: round(float(r2_score(Yte[:, i], pred[:, i])), 4)
                                 for i, v in enumerate(STATE)}
    res["onestep_r2_mean"] = round(float(np.mean(list(res["onestep_r2_per_dim"].values()))), 4)
    pmse = float(np.mean((Xte - Yte) ** 2))
    res["persistence_mse"] = round(pmse, 5)
    res["persistence_r2_mean"] = round(float(np.mean(
        [r2_score(Yte[:, i], Xte[:, i]) for i in range(NX)])), 4)
    res["skill_vs_persistence"] = round(1.0 - res["onestep_mse"] / pmse, 4)

    nps, rmin = psd_violations(R)
    res["structure"] = {"R_nonpsd": nps, "R_min_rel": rmin, "J_skew_maxerr": skew_error(J),
                        "H_negative": int((H.detach() < 0).sum()) if H is not None else None,
                        "n": int(len(xt))}
    # first-step magnitude, the growth-order diagnostic [AUDIT-5]
    res["first_step_norm"] = {}

    # ---- 2. ROLLOUT ----
    gen = torch.Generator().manual_seed(seed + 7)
    lo = torch.tensor([[BOX[v][0] for v in STATE]])
    hi = torch.tensor([[BOX[v][1] for v in STATE]])
    mu_t = torch.tensor(scX.mean_, dtype=torch.float32)
    sd_t = torch.tensor(scX.scale_, dtype=torch.float32)
    box_u = ((torch.rand(len(xt), NX, generator=gen) * (hi - lo) + lo) - mu_t) / sd_t

    conditions = [
        ("drug",            ut,                   xt,    200),   # primary
        ("zero_input",      torch.zeros_like(ut), xt,    200),   # primary, passivity
        ("box_uniform",     ut,                   box_u, 200),   # admissible-by-construction
        ("dose_x5",         ut * 5.0,             xt,    200),   # stress
        ("recover_6sig",    ut, torch.randn(len(xt), NX, generator=gen) * 6.0,  200),
        ("recover_24sig",   ut, torch.randn(len(xt), NX, generator=gen) * 24.0, 200),
    ]
    for tag, uu, x0, ns in conditions:
        with torch.no_grad():
            pass
        d0 = net(x0.clone(), uu)[0].detach() - x0
        res["first_step_norm"][tag] = round(float(d0.norm(dim=1).median()), 4)
        r = rollout(net, x0.clone(), uu, ns, scX)
        Ht, mv = r.pop("_H"), r.pop("_move")
        r["n_steps_requested"] = ns
        if tag == "zero_input":
            # Passivity. With u = 0, dH/dt = -(dH/dx)^T R (dH/dx) <= 0 whenever R >= 0.
            # P and Pm guarantee R >= 0 by construction; U does not. Falsifiable.
            r["energy"] = energy_report(Ht, mv)
        res[f"rollout_{tag}"] = r
    return res


def jobs():
    return [dict(letter=L, seed=s) for s in SEEDS for L in LETTERS]


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
        CONDS = ["drug", "zero_input", "box_uniform", "dose_x5",
                 "recover_6sig", "recover_24sig"]
        rec = []
        for r in rows:
            e = r["rollout_zero_input"].get("energy")
            em = (e or {}).get("moving_steps") or {}
            ea = (e or {}).get("all_steps") or {}
            rec.append({
                "model": r["model"], "seed": r["seed"],
                "act_par": r["n_params_active"],
                "R2": r["onestep_r2_mean"], "skill": r["skill_vs_persistence"],
                "Rnpsd": r["structure"]["R_nonpsd"], "Hneg": r["structure"]["H_negative"],
                "mov%": r["rollout_zero_input"]["frac_steps_moving"],
                "gain_mov": em.get("frac_gain_relative"),
                "gain_all": ea.get("frac_gain_relative"),
                "gain_flip": em.get("frac_gain_under_sign_flip"),
                "maxdH_rel": None if not em else round(em["max_dH_relative"], 3),
                "step1_6s": r["first_step_norm"]["recover_6sig"],
                **{f"ok_{c}": r[f"rollout_{c}"]["frac_admissible"] for c in CONDS},
                **{f"in0_{c}": r[f"rollout_{c}"]["frac_started_inside"] for c in CONDS},
            })
        d = pd.DataFrame(rec)
        pd.set_option("display.width", 250)
        print("--- one-step accuracy and structure ---")
        print(d[["model", "seed", "act_par", "R2", "skill", "Rnpsd", "Hneg"]]
              .sort_values(["model", "seed"]).to_string(index=False))
        print(f"\npersistence one-step R2 (mean over runs): "
              f"{np.mean([r['persistence_r2_mean'] for r in rows]):.4f} "
              f"(sd {np.std([r['persistence_r2_mean'] for r in rows]):.4f})")
        print("\n--- passivity at u=0: relative threshold, float64 ---")
        print(d[["model", "seed", "mov%", "gain_mov", "gain_all", "gain_flip", "maxdH_rel"]]
              .sort_values(["model", "seed"]).to_string(index=False))
        print("\n--- rollout admissibility (denominator = trajectories starting inside) ---")
        print(d[["model", "seed"] + [f"ok_{c}" for c in CONDS]]
              .sort_values(["model", "seed"]).to_string(index=False))
        print("\nfraction of starts that were admissible, by condition:")
        print(d.groupby("model")[[f"in0_{c}" for c in CONDS]].mean().round(4).to_string())
        print("\n--- first-step magnitude at 6 sigma (growth-order diagnostic) ---")
        print(d.groupby("model")["step1_6s"].mean().round(4).to_string())
        print("\n--- by model ---")
        print(d.groupby("model").agg(
            act_par=("act_par", "first"), R2=("R2", "mean"), R2sd=("R2", "std"),
            gain_mov=("gain_mov", "mean"), gain_all=("gain_all", "mean"),
            Rnpsd=("Rnpsd", "sum"), Hneg=("Hneg", "sum"),
            **{f"ok_{c}": (f"ok_{c}", "mean") for c in CONDS}).round(4).to_string())
        sys.exit(0)

    j = J[args.job]
    r = run(j["letter"], j["seed"])
    prev = json.load(open(STORE)) if os.path.exists(STORE) else []
    prev = [x for x in prev if not (x["model"] == r["model"] and x["seed"] == r["seed"])]
    json.dump(prev + [r], open(STORE, "w"), indent=1, default=float)
    e = (r["rollout_zero_input"].get("energy") or {}).get("moving_steps") or {}
    print(f"[{args.job}] {r['model']:2s} s{r['seed']} act_par={r['n_params_active']:,} "
          f"R2={r['onestep_r2_mean']} skill={r['skill_vs_persistence']} | "
          f"u0 moving={r['rollout_zero_input']['frac_steps_moving']} "
          f"gain={e.get('frac_gain_relative')} (n={e.get('n_steps')}) | "
          f"ok box={r['rollout_box_uniform']['frac_admissible']} "
          f"6s={r['rollout_recover_6sig']['frac_admissible']} | "
          f"step1@6s={r['first_step_norm']['recover_6sig']} ({r['train_seconds']}s)")
