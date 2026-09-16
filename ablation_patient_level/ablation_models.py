"""Shared model definitions for ablation study."""
import torch, torch.nn as nn, torch.nn.functional as F
import numpy as np, json, time
from sklearn.metrics import r2_score

CLIN_COLS = ['pre_pinn_Ees','pre_pinn_Eed','pre_pinn_Ea','pre_pinn_coupling',
             'pre_pinn_EDP','pre_pinn_efficiency','pre_pinn_tau']
ENERGY_COLS = ['pre_H_total','pre_T_kinetic','pre_V_potential',
               'pre_mech_eff','pre_VA_coupling','pre_SW_J']
TARGET_COLS = CLIN_COLS + ENERGY_COLS

class PHPINN(nn.Module):
    """Model A: Full Port-Hamiltonian with hard constraints."""
    def __init__(self):
        super().__init__()
        self.enc = nn.Sequential(nn.Linear(11,256),nn.GELU(),nn.LayerNorm(256),
                                 nn.Linear(256,128),nn.GELU(),nn.LayerNorm(128),
                                 nn.Linear(128,64),nn.GELU())
        self.q_head = nn.Sequential(nn.Linear(64,32),nn.GELU(),nn.Linear(32,3))
        self.p_head = nn.Sequential(nn.Linear(64,32),nn.GELU(),nn.Linear(32,2))
        self.T_net = nn.Sequential(nn.Linear(5,64),nn.GELU(),nn.Linear(64,64),nn.GELU(),nn.Linear(64,1))
        self.V_net = nn.Sequential(nn.Linear(3,64),nn.GELU(),nn.Linear(64,64),nn.GELU(),nn.Linear(64,1))
        self.R_net = nn.Sequential(nn.Linear(5,32),nn.GELU(),nn.Linear(32,25))
        self.clin_dec = nn.Sequential(nn.Linear(67,128),nn.GELU(),nn.Linear(128,7))
        self.energy_dec = nn.Sequential(nn.Linear(67,64),nn.GELU(),nn.Linear(64,6))

    def forward(self, x):
        h = self.enc(x); q = self.q_head(h); p = self.p_head(h)
        qp = torch.cat([q,p],-1)
        T = F.softplus(self.T_net(qp).squeeze(-1))
        V = F.softplus(self.V_net(q).squeeze(-1))
        H = T + V
        L_flat = self.R_net(qp).view(-1,5,5)
        L_lo = torch.tril(L_flat); R = torch.bmm(L_lo, L_lo.transpose(1,2))
        dec_in = torch.cat([h, H.unsqueeze(-1), T.unsqueeze(-1), V.unsqueeze(-1)],-1)
        return torch.cat([self.clin_dec(dec_in), self.energy_dec(dec_in)],-1), H, T, V, R

class VanillaMLP(nn.Module):
    """Model B: Plain MLP, no physics."""
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(11,256),nn.GELU(),nn.LayerNorm(256),
                                 nn.Linear(256,256),nn.GELU(),nn.LayerNorm(256),
                                 nn.Linear(256,128),nn.GELU(),nn.Linear(128,64),nn.GELU(),
                                 nn.Linear(64,13))
    def forward(self, x):
        out = self.net(x)
        return out, out[:,7], out[:,8], out[:,9], None

class NoStructurePINN(nn.Module):
    """Model C: Same topology, no softplus/Cholesky/H=T+V."""
    def __init__(self):
        super().__init__()
        self.enc = nn.Sequential(nn.Linear(11,256),nn.GELU(),nn.LayerNorm(256),
                                 nn.Linear(256,128),nn.GELU(),nn.LayerNorm(128),
                                 nn.Linear(128,64),nn.GELU())
        self.q_head = nn.Sequential(nn.Linear(64,32),nn.GELU(),nn.Linear(32,3))
        self.p_head = nn.Sequential(nn.Linear(64,32),nn.GELU(),nn.Linear(32,2))
        self.T_net = nn.Sequential(nn.Linear(5,64),nn.GELU(),nn.Linear(64,64),nn.GELU(),nn.Linear(64,1))
        self.V_net = nn.Sequential(nn.Linear(3,64),nn.GELU(),nn.Linear(64,64),nn.GELU(),nn.Linear(64,1))
        self.R_net = nn.Sequential(nn.Linear(5,32),nn.GELU(),nn.Linear(32,25))
        self.clin_dec = nn.Sequential(nn.Linear(67,128),nn.GELU(),nn.Linear(128,7))
        self.energy_dec = nn.Sequential(nn.Linear(67,64),nn.GELU(),nn.Linear(64,6))

    def forward(self, x):
        h = self.enc(x); q = self.q_head(h); p = self.p_head(h)
        qp = torch.cat([q,p],-1)
        T = self.T_net(qp).squeeze(-1)  # NO softplus
        V = self.V_net(q).squeeze(-1)    # NO softplus
        H = T + V  # computed but unconstrained
        R_flat = self.R_net(qp).view(-1,5,5)
        R = (R_flat + R_flat.transpose(1,2))/2  # symmetric, NOT guaranteed PSD
        dec_in = torch.cat([h, H.unsqueeze(-1), T.unsqueeze(-1), V.unsqueeze(-1)],-1)
        return torch.cat([self.clin_dec(dec_in), self.energy_dec(dec_in)],-1), H, T, V, R

class SoftConstraintPINN(nn.Module):
    """Model D: Same as NoStructure but with loss penalties."""
    def __init__(self):
        super().__init__()
        self.enc = nn.Sequential(nn.Linear(11,256),nn.GELU(),nn.LayerNorm(256),
                                 nn.Linear(256,128),nn.GELU(),nn.LayerNorm(128),
                                 nn.Linear(128,64),nn.GELU())
        self.q_head = nn.Sequential(nn.Linear(64,32),nn.GELU(),nn.Linear(32,3))
        self.p_head = nn.Sequential(nn.Linear(64,32),nn.GELU(),nn.Linear(32,2))
        self.T_net = nn.Sequential(nn.Linear(5,64),nn.GELU(),nn.Linear(64,64),nn.GELU(),nn.Linear(64,1))
        self.V_net = nn.Sequential(nn.Linear(3,64),nn.GELU(),nn.Linear(64,64),nn.GELU(),nn.Linear(64,1))
        self.R_net = nn.Sequential(nn.Linear(5,32),nn.GELU(),nn.Linear(32,25))
        self.clin_dec = nn.Sequential(nn.Linear(67,128),nn.GELU(),nn.Linear(128,7))
        self.energy_dec = nn.Sequential(nn.Linear(67,64),nn.GELU(),nn.Linear(64,6))

    def forward(self, x):
        h = self.enc(x); q = self.q_head(h); p = self.p_head(h)
        qp = torch.cat([q,p],-1)
        T = self.T_net(qp).squeeze(-1)
        V = self.V_net(q).squeeze(-1)
        H = T + V
        R_flat = self.R_net(qp).view(-1,5,5)
        R = (R_flat + R_flat.transpose(1,2))/2
        dec_in = torch.cat([h, H.unsqueeze(-1), T.unsqueeze(-1), V.unsqueeze(-1)],-1)
        return torch.cat([self.clin_dec(dec_in), self.energy_dec(dec_in)],-1), H, T, V, R

def load_data(path="ablation_data.npz"):
    d = np.load(path)
    return {k: d[k] for k in d.files}

def train_and_eval(model, data, split='random', soft_penalty=False, epochs=150):
    if split == 'random':
        Xtr, Xte = data['X_tr_s'], data['X_te_s']
        Ytr_s, Yte = data['Y_tr_s'], data['Y_te']
        sc_mean, sc_scale = data['sc_Y_mean'], data['sc_Y_scale']
    else:
        Xtr, Xte = data['Xt_tr_s'], data['Xt_te_s']
        Ytr_s, Yte = data['Yt_tr_s'], data['Yt_te']
        sc_mean, sc_scale = data['sc_Yt_mean'], data['sc_Yt_scale']

    ds = torch.utils.data.TensorDataset(torch.tensor(Xtr), torch.tensor(Ytr_s))
    dl = torch.utils.data.DataLoader(ds, batch_size=256, shuffle=True)
    opt = torch.optim.AdamW(model.parameters(), lr=2e-3, weight_decay=1e-4)
    sch = torch.optim.lr_scheduler.CosineAnnealingLR(opt, epochs)
    best_loss=1e9; best_state=None; best_ep=0; t0=time.time()

    for ep in range(epochs):
        model.train(); ep_loss=0
        for bx, by in dl:
            opt.zero_grad()
            pred, H, T, V, R = model(bx)
            loss = F.mse_loss(pred, by)
            if soft_penalty:
                loss += 1.0*(F.relu(-T).mean() + F.relu(-V).mean())
                if R is not None:
                    loss += 1.0*F.relu(-torch.linalg.eigvalsh(R)).mean()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step(); ep_loss += loss.item()
        sch.step()
        if ep_loss < best_loss:
            best_loss=ep_loss; best_ep=ep
            best_state={k:v.clone() for k,v in model.state_dict().items()}

    model.load_state_dict(best_state); model.eval()
    elapsed = time.time()-t0

    with torch.no_grad():
        pred_s, H, T, V, R = model(torch.tensor(Xte))
        pred_np = pred_s.numpy() * sc_scale + sc_mean
        H_np, T_np, V_np = H.numpy(), T.numpy(), V.numpy()

    r2s = {c: float(r2_score(Yte[:,i], pred_np[:,i])) for i,c in enumerate(TARGET_COLS)}
    htv_mse = float(np.mean((H_np - T_np - V_np)**2))
    t_neg = int((T_np < 0).sum())
    v_neg = int((V_np < 0).sum())
    r_psd = 0
    if R is not None:
        R_np = R.numpy()
        for ri in range(R_np.shape[0]):
            if np.linalg.eigvalsh(R_np[ri]).min() < -1e-6: r_psd += 1
    else:
        r_psd = -1

    return {
        'n_params': sum(p.numel() for p in model.parameters()),
        'best_ep': best_ep, 'time_s': round(elapsed,1),
        'r2': r2s,
        'mean_r2_clin': round(np.mean([r2s[c] for c in CLIN_COLS]),4),
        'mean_r2_energy': round(np.mean([r2s[c] for c in ENERGY_COLS]),4),
        'mean_r2_all': round(np.mean(list(r2s.values())),4),
        'H_T_V_MSE': htv_mse, 'T_neg': t_neg, 'V_neg': v_neg, 'R_PSD_viol': r_psd,
    }
