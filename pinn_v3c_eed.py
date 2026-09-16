"""
PINN v3c: Non-invasive Diastolic Stiffness (Eed) Estimation
============================================================
Physics-Informed Neural Network for estimating end-diastolic
chamber stiffness from non-invasive hemodynamic + echo parameters.

Core Innovation:
  - Eed (diastolic stiffness) has NO existing non-invasive formula
  - Currently requires invasive catheterization + IVC occlusion
  - PINN embeds EDPVR physics: P = A * exp(Eed * (V - V0))
  - Uses diastolic echo panel (E/e', E/A, DT, LAVI) as key inputs

Architecture:
  11 inputs -> Encoder MLP -> 7 latent params -> Physics Decoder -> 6 outputs

  Inputs: EF, EDV, ESV, SBP, DBP, HR, CO, E/e', E/A, DT, LAVI
  Latent: Ees_delta, Eed, V0, A, Ea, gate_Ea, gate_EDP
  Outputs: Ees, Eed, Ea, Ea/Ees coupling, EDP, efficiency

Author: Kwanhyeong Lee
Date: 2026-04
"""

import torch
import torch.nn as nn
import numpy as np
from sklearn.preprocessing import StandardScaler
from scipy.stats import pearsonr
from sklearn.metrics import roc_auc_score, mean_absolute_error
from torch.utils.data import TensorDataset, DataLoader

# ============================================================
# Constants
# ============================================================
FEAT_NAMES = ['EF', 'EDV', 'ESV', 'SBP', 'DBP', 'HR', 'CO',
              'Ee_prime', 'EA_ratio', 'DT', 'LAVI']
TARGS = ['Ees', 'Eed', 'Ea', 'coupling', 'EDP', 'efficiency']

# ============================================================
# Simulator: 6-phenotype cohort generator
# ============================================================
def generate_training_data(N=15000, seed=42):
    """
    Generate simulated hemodynamic data from 6 cardiac phenotypes.
    Each phenotype has characteristic diastolic echo parameter patterns.

    Phenotypes:
      Normal (25%), HFrEF (15%), HFpEF (20%), HTN (15%), Elderly (15%), Athlete (10%)

    Returns: X (N x 11 features), Y (dict of target arrays)
    """
    rng = np.random.RandomState(seed)

    n_norm = int(N * 0.25)
    n_hfref = int(N * 0.15)
    n_hfpef = int(N * 0.20)
    n_htn = int(N * 0.15)
    n_eld = int(N * 0.15)
    n_ath = N - n_norm - n_hfref - n_hfpef - n_htn - n_eld

    def make_cohort(n, ees_r, eed_r, edv_r, hr_r, v0_r, A_r, sbp_r, ea_r, dt_r, lavi_r):
        return tuple(rng.uniform(*r, n) for r in
                     [ees_r, eed_r, edv_r, hr_r, v0_r, A_r, sbp_r, ea_r, dt_r, lavi_r])

    cohorts = [
        # Normal: E/A 1.0-2.0, DT 160-220, LAVI 16-28
        make_cohort(n_norm,
                    (1.5, 4.0), (0.02, 0.08), (90, 160), (55, 90),
                    (-10, 20), (0.2, 1.5), (100, 140), (1.0, 2.0), (160, 220), (16, 28)),
        # HFrEF: variable E/A, short DT if restrictive, elevated LAVI
        make_cohort(n_hfref,
                    (0.5, 1.8), (0.03, 0.12), (150, 280), (70, 110),
                    (0, 30), (0.3, 2.0), (80, 130), (0.8, 3.0), (120, 280), (28, 50)),
        # HFpEF: low E/A (impaired relaxation), prolonged DT, elevated LAVI
        make_cohort(n_hfpef,
                    (1.5, 4.5), (0.08, 0.30), (80, 150), (60, 100),
                    (-5, 25), (0.5, 3.0), (110, 170), (0.5, 1.2), (200, 300), (28, 48)),
        # HTN: low-normal E/A, prolonged DT, mildly elevated LAVI
        make_cohort(n_htn,
                    (2.0, 6.0), (0.05, 0.15), (80, 140), (60, 95),
                    (-5, 15), (0.3, 2.0), (140, 200), (0.7, 1.5), (180, 260), (22, 36)),
        # Elderly: low E/A, prolonged DT, mildly elevated LAVI
        make_cohort(n_eld,
                    (1.0, 3.5), (0.06, 0.20), (90, 170), (55, 85),
                    (0, 25), (0.4, 2.5), (100, 160), (0.6, 1.3), (200, 280), (24, 40)),
        # Athlete: normal-high E/A, normal DT, normal LAVI
        make_cohort(n_ath,
                    (2.0, 5.0), (0.01, 0.05), (120, 200), (40, 65),
                    (-15, 10), (0.1, 1.0), (100, 130), (1.2, 2.5), (160, 220), (18, 30)),
    ]

    # Concatenate all cohorts
    arrs = [np.concatenate([c[i] for c in cohorts]) for i in range(10)]
    Ees, Eed, EDV, HR, V0, A, SBP, EA_ratio, DT, LAVI = arrs
    Nt = len(Ees)

    # Derive hemodynamic variables from physics
    ESP = 0.9 * SBP
    ESV = np.clip(V0 + ESP / Ees, 20, EDV - 10)
    SV = EDV - ESV
    EF = SV / EDV
    EDP = np.clip(A * np.exp(Eed * np.clip(EDV - V0, 0, 100)), 2, 40)
    Ee_prime = np.clip((EDP - 1.9) / 1.24, 3, 30)  # inverse Nagueh
    DBP = rng.uniform(0.5, 0.65, Nt) * SBP
    MAP = (SBP + 2 * DBP) / 3
    CO = SV * HR / 1000
    Ea = ESP / np.clip(SV, 1, None)
    coupling = Ea / np.clip(Ees, 0.1, None)
    SW = SV * MAP * 0.0133
    PE = 0.5 * Ees * np.clip(ESV - V0, 0, None) ** 2 * 0.0133
    PVA = SW + PE
    eff = np.clip(SW / np.clip(PVA, 0.01, None), 0.1, 0.95)

    # Add measurement noise
    ns = lambda a, p: a * (1 + rng.randn(Nt) * p)
    EDV_n = ns(EDV, .05)
    ESV_n = ns(ESV, .05)
    SBP_n = ns(SBP, .03)
    DBP_n = ns(DBP, .03)
    HR_n = ns(HR, .02)
    Ee_n = np.clip(Ee_prime + rng.randn(Nt) * 1.5, 3, 35)
    EA_n = np.clip(EA_ratio + rng.randn(Nt) * 0.2, 0.3, 4.0)
    DT_n = np.clip(DT + rng.randn(Nt) * 15, 80, 350)
    LAVI_n = np.clip(LAVI + rng.randn(Nt) * 3, 10, 60)
    SV_n = EDV_n - ESV_n
    EF_n = SV_n / EDV_n
    CO_n = SV_n * HR_n / 1000

    # Filter physiologically valid samples
    mask = ((EF_n > 0.10) & (EF_n < 0.90) & (SBP_n > 60) &
            (SV_n > 10) & (Ea > 0.3) & (Ea < 8) &
            (Eed > 0.005) & (EDP > 1) & (EDP < 45))
    idx = np.where(mask)[0]

    X = np.column_stack([EF_n[idx], EDV_n[idx], ESV_n[idx], SBP_n[idx],
                         DBP_n[idx], HR_n[idx], CO_n[idx], Ee_n[idx],
                         EA_n[idx], DT_n[idx], LAVI_n[idx]])
    Y = {t: v[idx] for t, v in zip(TARGS, [Ees, Eed, Ea, coupling, EDP, eff])}

    print(f"Generated {len(idx)}/{Nt} valid samples, "
          f"Eed [{Y['Eed'].min():.3f}, {Y['Eed'].max():.3f}]")
    return X, Y


# ============================================================
# Physics Decoder
# ============================================================
class PhysicsDecoder(nn.Module):
    """
    Converts 7 latent parameters into 6 physiological outputs
    using embedded cardiovascular physics equations.
    """
    def forward(self, lat, raw):
        # Unpack 11 raw inputs
        EF, EDV, ESV, SBP, DBP, HR, CO, Ee, EA, DT, LAVI = \
            [raw[:, i:i+1] for i in range(11)]

        ESP = 0.9 * SBP
        SV = torch.clamp(EDV - ESV, min=1.0)
        MAP = (SBP + 2 * DBP) / 3

        # --- Systolic: Chen/Shishido + learned correction ---
        chen_denom = torch.clamp(torch.abs(ESV - 0.1 * EDV), min=1.0)
        Chen_Ees = torch.clamp(ESP / chen_denom, 0.3, 12.0)
        Ees = torch.clamp(
            Chen_Ees * (1 + 0.3 * torch.tanh(lat[:, 0:1])),
            0.3, 10.0
        )

        # --- Diastolic: EDPVR physics P = A * exp(Eed * (V - V0)) ---
        Eed = 0.005 + 0.495 * torch.sigmoid(lat[:, 1:2])   # [0.005, 0.50]
        V0 = -20 + 50 * torch.sigmoid(lat[:, 2:3])          # [-20, 30]
        A = 0.1 + 4.9 * torch.sigmoid(lat[:, 3:4])          # [0.1, 5.0]

        # EDP: blend Nagueh formula with EDPVR prediction
        EDP_nagueh = torch.clamp(1.24 * Ee + 1.9, 2.0, 40.0)
        edpvr_arg = torch.clamp(Eed * (EDV - V0), -5, 5)
        EDP_edpvr = torch.clamp(A * torch.exp(edpvr_arg), 1.0, 45.0)
        edp_gate = torch.sigmoid(lat[:, 6:7])
        EDP = edp_gate * EDP_edpvr + (1 - edp_gate) * EDP_nagueh

        # --- Arterial: gated Ea ---
        Ea_learned = 0.3 + 5.7 * torch.sigmoid(lat[:, 4:5])
        gate = torch.sigmoid(lat[:, 5:6])
        Ea_phys = torch.clamp(ESP / SV, 0.3, 6.0)
        Ea = gate * Ea_learned + (1 - gate) * Ea_phys

        # --- Derived metrics ---
        coupling = Ea / torch.clamp(Ees, min=0.1)
        SW = SV * MAP * 0.0133
        PE = 0.5 * Ees * torch.clamp(ESV - V0, min=0.0) ** 2 * 0.0133
        PVA = SW + PE
        eff = torch.clamp(SW / torch.clamp(PVA, min=0.01), 0.1, 0.95)

        return torch.cat([Ees, Eed, Ea, coupling, EDP, eff], dim=-1)


# ============================================================
# PINN v3c Model
# ============================================================
class PINNv3c(nn.Module):
    """
    Physics-Informed Neural Network for diastolic stiffness estimation.

    Encoder: 11 -> 256 -> 128 -> 64 -> 7 (latent physiological parameters)
    Decoder: Physics equations (EDPVR, Chen/Shishido, Nagueh)
    """
    def __init__(self):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(11, 256), nn.SiLU(), nn.BatchNorm1d(256), nn.Dropout(0.1),
            nn.Linear(256, 128), nn.SiLU(), nn.BatchNorm1d(128), nn.Dropout(0.1),
            nn.Linear(128, 64), nn.SiLU(), nn.BatchNorm1d(64),
            nn.Linear(64, 7)
        )
        self.decoder = PhysicsDecoder()

    def forward(self, x_scaled, x_raw):
        latent = self.encoder(x_scaled)
        return self.decoder(latent, x_raw)


# ============================================================
# Training
# ============================================================
def train_model(X, Y, epochs=150, batch_size=256, lr=1e-3, verbose=True):
    """Train PINN v3c on simulation data. Returns (model, scaler)."""
    scaler = StandardScaler().fit(X)

    Xt = torch.tensor(scaler.transform(X), dtype=torch.float32)
    Xr = torch.tensor(X, dtype=torch.float32)
    Ys = torch.tensor(
        np.column_stack([Y[t] for t in TARGS]), dtype=torch.float32
    )

    ds = TensorDataset(Xt, Xr, Ys)
    dl = DataLoader(ds, batch_size, shuffle=True)

    model = PINNv3c()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, epochs)

    # Loss weights: Eed (5x), EDP (3x) > Ees, Ea (1x) > coupling, eff (0.5x)
    weights = torch.tensor([1.0, 5.0, 1.0, 0.5, 3.0, 0.5])

    model.train()
    for ep in range(epochs):
        for bx, bxr, by in dl:
            pred = model(bx, bxr)
            loss = sum(weights[i] * nn.functional.mse_loss(pred[:, i], by[:, i])
                       for i in range(6))
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
        scheduler.step()

        if verbose and (ep + 1) % 50 == 0:
            model.eval()
            with torch.no_grad():
                fp = model(Xt, Xr).numpy()
            model.train()
            rs = [f"{t}={pearsonr(Ys[:, i].numpy(), fp[:, i])[0]:.3f}"
                  for i, t in enumerate(TARGS)]
            print(f"  Epoch {ep+1}: {', '.join(rs)}")

    return model, scaler


def evaluate_model(model, scaler, X_test, Y_test):
    """Evaluate model on test set. Returns dict of metrics per target."""
    model.eval()
    Xts = torch.tensor(scaler.transform(X_test), dtype=torch.float32)
    Xtr = torch.tensor(X_test, dtype=torch.float32)

    with torch.no_grad():
        pred = model(Xts, Xtr).numpy()

    results = {}
    for i, t in enumerate(TARGS):
        r, p = pearsonr(Y_test[t], pred[:, i])
        mae = mean_absolute_error(Y_test[t], pred[:, i])
        results[t] = {'R': r, 'p': p, 'MAE': mae, 'pred': pred[:, i]}

    return results


# ============================================================
# Clinical utility: Eed classification
# ============================================================
def evaluate_clinical_utility(Y_test, pred_eed):
    """AUC for detecting elevated diastolic stiffness."""
    thresholds = [
        (0.08, "Eed>0.08 (mild diastolic dysfunction)"),
        (0.10, "Eed>0.10 (moderate)"),
        (0.15, "Eed>0.15 (severe)"),
    ]
    results = {}
    for thresh, label in thresholds:
        true_label = (Y_test['Eed'] > thresh).astype(int)
        if true_label.sum() > 10 and (1 - true_label).sum() > 10:
            auc = roc_auc_score(true_label, pred_eed)
            results[label] = auc
    return results


# ============================================================
# Main: train + evaluate on simulation
# ============================================================
if __name__ == '__main__':
    print("=" * 60)
    print("PINN v3c: Non-invasive Diastolic Stiffness Estimation")
    print("=" * 60)

    # Generate data
    X, Y = generate_training_data(N=15000)

    # Train/test split
    n_tr = int(len(X) * 0.8)
    idx = np.random.RandomState(0).permutation(len(X))
    X_train, X_test = X[idx[:n_tr]], X[idx[n_tr:]]
    Y_train = {k: v[idx[:n_tr]] for k, v in Y.items()}
    Y_test = {k: v[idx[n_tr:]] for k, v in Y.items()}

    # Train
    print("\nTraining...")
    model, scaler = train_model(X_train, Y_train, epochs=150)

    # Evaluate
    print("\n" + "=" * 60)
    print(f"TEST RESULTS (N={len(X_test)})")
    print("=" * 60)
    results = evaluate_model(model, scaler, X_test, Y_test)
    for t in TARGS:
        r = results[t]
        key = " << KEY" if t == 'Eed' else ""
        print(f"  {t:>12}: R={r['R']:.4f}, MAE={r['MAE']:.4f}{key}")

    # Clinical utility
    print("\n" + "=" * 60)
    print("CLINICAL UTILITY: Diastolic Stiffness Classification")
    print("=" * 60)
    clin = evaluate_clinical_utility(Y_test, results['Eed']['pred'])
    for label, auc in clin.items():
        print(f"  {label}: AUC = {auc:.3f}")

    # Save model
    torch.save({
        'model_state': model.state_dict(),
        'scaler_mean': scaler.mean_,
        'scaler_scale': scaler.scale_,
        'feature_names': FEAT_NAMES,
        'target_names': TARGS,
    }, 'pinn_v3c_model.pt')
    print("\nModel saved to pinn_v3c_model.pt")
