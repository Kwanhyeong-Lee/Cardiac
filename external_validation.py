"""
External Validation Pipeline for pH-PINN v5
============================================
Usage:
  1. Extract eICU data using eicu_extraction_query.sql
  2. Save as eicu_cardiac.csv (same 11 columns as MIMIC-IV)
  3. Run: python external_validation.py --data eicu_cardiac.csv

Outputs:
  - external_validation_results.csv  (summary table)
  - external_validation_comparison.png (visualization)
  - external_validation_detail.json  (per-output R²)
"""
import torch, torch.nn as nn, torch.nn.functional as F
import numpy as np, pandas as pd, json, argparse, os, warnings
warnings.filterwarnings('ignore')
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error

# ============================================================
# CONFIG
# ============================================================
INPUT_COLS = ['pre_EF','pre_EDV','pre_ESV','pre_SBP','pre_DBP','pre_HR',
              'pre_Ee_prime','pre_LAVI','pre_EA_ratio','pre_DT','pre_CO']
CLIN_COLS = ['pre_pinn_Ees','pre_pinn_Eed','pre_pinn_Ea','pre_pinn_coupling',
             'pre_pinn_EDP','pre_pinn_efficiency','pre_pinn_tau']
ENERGY_COLS = ['pre_H_total','pre_T_kinetic','pre_V_potential',
               'pre_mech_eff','pre_VA_coupling','pre_SW_J']
TARGET_COLS = CLIN_COLS + ENERGY_COLS

# ============================================================
# PHYSICS: Compute target variables from raw measurements
# (Same formulas used for MIMIC-IV dataset generation)
# ============================================================
def compute_targets(df):
    """Compute 13 cardiac energetics targets from 11 raw echo measurements."""
    EF = df['pre_EF']
    EDV = df['pre_EDV']
    ESV = df['pre_ESV']
    SBP = df['pre_SBP']
    DBP = df['pre_DBP']
    HR  = df['pre_HR']
    Ee  = df['pre_Ee_prime']
    LAVI = df['pre_LAVI']
    EA  = df['pre_EA_ratio']
    DT  = df['pre_DT']
    CO  = df['pre_CO']

    SV = EDV - ESV
    ESP = 0.9 * SBP  # end-systolic pressure approximation
    MAP = DBP + (SBP - DBP) / 3

    # === Clinical targets ===
    Ees = ESP / ESV                      # end-systolic elastance
    Eed = (Ee * 0.596 + 11.96) / EDV     # end-diastolic elastance (Nagueh EDP → Eed)
    Ea  = ESP / SV                       # arterial elastance
    coupling = Ees / Ea                  # ventriculo-arterial coupling
    EDP = Ee * 0.596 + 11.96            # end-diastolic pressure (Nagueh formula)
    efficiency = SV / EDV                # ~ EF/100 (mechanical efficiency proxy)
    tau = DT * 0.5                       # relaxation time constant (simplified)

    # === Energy targets ===
    SW = ESP * SV * 0.0133322           # stroke work (mmHg·mL → Joules)
    PE = 0.5 * ESP * ESV * 0.0133322   # potential energy
    PVA = SW + PE                       # pressure-volume area
    H_total = PVA                       # total Hamiltonian ≈ PVA
    T_kinetic = SW                      # kinetic component ≈ stroke work
    V_potential = PE                    # potential component
    mech_eff = SW / (PVA + 1e-8)       # mechanical efficiency
    VA_coupling = Ea / Ees              # V-A coupling ratio (inverse of Ees/Ea)
    SW_J = SW                           # stroke work in Joules

    out = pd.DataFrame({
        'pre_pinn_Ees': Ees, 'pre_pinn_Eed': Eed, 'pre_pinn_Ea': Ea,
        'pre_pinn_coupling': coupling, 'pre_pinn_EDP': EDP,
        'pre_pinn_efficiency': efficiency, 'pre_pinn_tau': tau,
        'pre_H_total': H_total, 'pre_T_kinetic': T_kinetic,
        'pre_V_potential': V_potential, 'pre_mech_eff': mech_eff,
        'pre_VA_coupling': VA_coupling, 'pre_SW_J': SW_J,
    })
    return out

# ============================================================
# MODELS (same as ablation study)
# ============================================================
class PHPINN(nn.Module):
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
        L = torch.tril(self.R_net(qp).view(-1,5,5))
        R = torch.bmm(L, L.transpose(1,2))
        dec_in = torch.cat([h, H.unsqueeze(-1), T.unsqueeze(-1), V.unsqueeze(-1)],-1)
        return torch.cat([self.clin_dec(dec_in), self.energy_dec(dec_in)],-1), H, T, V, R

class VanillaMLP(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(11,256),nn.GELU(),nn.LayerNorm(256),
                                 nn.Linear(256,256),nn.GELU(),nn.LayerNorm(256),
                                 nn.Linear(256,128),nn.GELU(),nn.Linear(128,64),nn.GELU(),nn.Linear(64,13))
    def forward(self, x):
        out = self.net(x)
        return out, out[:,7], out[:,8], out[:,9], None

class NoStructurePINN(nn.Module):
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
        T = self.T_net(qp).squeeze(-1); V = self.V_net(q).squeeze(-1); H = T + V
        R_flat = self.R_net(qp).view(-1,5,5); R = (R_flat + R_flat.transpose(1,2))/2
        dec_in = torch.cat([h, H.unsqueeze(-1), T.unsqueeze(-1), V.unsqueeze(-1)],-1)
        return torch.cat([self.clin_dec(dec_in), self.energy_dec(dec_in)],-1), H, T, V, R

class SoftConstraintPINN(NoStructurePINN):
    pass  # Same architecture, different training (penalty-based)

# ============================================================
# VALIDATION PIPELINE
# ============================================================
def validate_model(model, X_ext, Y_ext, sc_X, sc_Y):
    """Run external validation for one model."""
    X_s = sc_X.transform(X_ext).astype(np.float32)
    model.eval()
    with torch.no_grad():
        pred_s, H, T, V, R = model(torch.tensor(X_s))
        pred = pred_s.numpy() * sc_Y.scale_ + sc_Y.mean_

    results = {}
    for i, col in enumerate(TARGET_COLS):
        r2 = r2_score(Y_ext[:, i], pred[:, i])
        mae = mean_absolute_error(Y_ext[:, i], pred[:, i])
        results[col] = {'R2': round(r2, 4), 'MAE': round(mae, 4)}

    # Physics violations
    H_np, T_np, V_np = H.numpy(), T.numpy(), V.numpy()
    physics = {
        'H_T_V_MSE': float(np.mean((H_np - T_np - V_np)**2)),
        'T_neg': int((T_np < 0).sum()),
        'V_neg': int((V_np < 0).sum()),
        'R_PSD_viol': 0
    }
    if R is not None:
        R_np = R.numpy()
        for ri in range(R_np.shape[0]):
            if np.linalg.eigvalsh(R_np[ri]).min() < -1e-6:
                physics['R_PSD_viol'] += 1
    else:
        physics['R_PSD_viol'] = -1

    mean_r2 = np.mean([v['R2'] for v in results.values()])
    mean_r2_clin = np.mean([results[c]['R2'] for c in CLIN_COLS])
    mean_r2_energy = np.mean([results[c]['R2'] for c in ENERGY_COLS])

    return {
        'per_output': results,
        'mean_r2': round(mean_r2, 4),
        'mean_r2_clin': round(mean_r2_clin, 4),
        'mean_r2_energy': round(mean_r2_energy, 4),
        'physics': physics,
        'n_samples': len(X_ext),
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', required=True, help='Path to eICU CSV (11 input columns)')
    parser.add_argument('--mimic', default='cardiac_energetics_hamiltonian.csv',
                        help='Path to MIMIC-IV training data')
    parser.add_argument('--outdir', default='.', help='Output directory')
    args = parser.parse_args()

    print("="*60)
    print("EXTERNAL VALIDATION: pH-PINN v5 on eICU")
    print("="*60)

    # Load MIMIC-IV for scaler fitting
    print("\n1. Loading MIMIC-IV training data...")
    df_mimic = pd.read_csv(args.mimic)
    X_mimic = df_mimic[INPUT_COLS].values.astype(np.float32)
    Y_mimic = df_mimic[TARGET_COLS].values.astype(np.float32)
    sc_X = StandardScaler().fit(X_mimic)
    sc_Y = StandardScaler().fit(Y_mimic)
    print(f"   MIMIC-IV: {len(df_mimic)} samples")

    # Load eICU
    print("\n2. Loading eICU data...")
    df_ext = pd.read_csv(args.data)
    print(f"   eICU raw: {len(df_ext)} samples")

    # Check if targets already exist or need computation
    has_targets = all(c in df_ext.columns for c in TARGET_COLS)
    if has_targets:
        print("   Targets found in CSV — using provided values")
        Y_ext = df_ext[TARGET_COLS].values.astype(np.float32)
    else:
        print("   Computing targets from raw measurements...")
        targets_df = compute_targets(df_ext)
        df_ext = pd.concat([df_ext, targets_df], axis=1)
        Y_ext = df_ext[TARGET_COLS].values.astype(np.float32)

    X_ext = df_ext[INPUT_COLS].values.astype(np.float32)

    # Remove NaN rows
    valid = ~(np.isnan(X_ext).any(axis=1) | np.isnan(Y_ext).any(axis=1))
    X_ext, Y_ext = X_ext[valid], Y_ext[valid]
    print(f"   After NaN removal: {len(X_ext)} samples")

    # Train all 4 models on FULL MIMIC-IV, then evaluate on eICU
    print("\n3. Training models on full MIMIC-IV...")
    X_mimic_s = sc_X.transform(X_mimic).astype(np.float32)
    Y_mimic_s = sc_Y.transform(Y_mimic).astype(np.float32)
    ds = torch.utils.data.TensorDataset(torch.tensor(X_mimic_s), torch.tensor(Y_mimic_s))
    dl = torch.utils.data.DataLoader(ds, batch_size=256, shuffle=True)

    model_configs = [
        ('A: pH-PINN v5 (Hard)', PHPINN, False),
        ('B: Vanilla MLP', VanillaMLP, False),
        ('C: No-Structure PINN', NoStructurePINN, False),
        ('D: Soft-Constraint PINN', SoftConstraintPINN, True),
    ]

    all_results = {}
    for name, cls, soft in model_configs:
        print(f"   Training {name}...")
        model = cls()
        opt = torch.optim.AdamW(model.parameters(), lr=2e-3, weight_decay=1e-4)
        sch = torch.optim.lr_scheduler.CosineAnnealingLR(opt, 150)
        best_loss = 1e9; best_state = None
        for ep in range(150):
            model.train(); ep_loss = 0
            for bx, by in dl:
                opt.zero_grad()
                pred, H, T, V, R = model(bx)
                loss = F.mse_loss(pred, by)
                if soft:
                    loss += F.relu(-T).mean() + F.relu(-V).mean()
                    if R is not None: loss += F.relu(-torch.linalg.eigvalsh(R)).mean()
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                opt.step(); ep_loss += loss.item()
            sch.step()
            if ep_loss < best_loss:
                best_loss = ep_loss
                best_state = {k:v.clone() for k,v in model.state_dict().items()}
        model.load_state_dict(best_state)

        res = validate_model(model, X_ext, Y_ext, sc_X, sc_Y)
        all_results[name] = res
        p = res['physics']
        print(f"     R²={res['mean_r2']:.4f} (clin={res['mean_r2_clin']:.4f}, energy={res['mean_r2_energy']:.4f})")
        print(f"     Physics: T<0={p['T_neg']}, V<0={p['V_neg']}, R_PSD={p['R_PSD_viol']}")

    # Save results
    print("\n4. Saving results...")
    rows = []
    for name, res in all_results.items():
        p = res['physics']
        rows.append({
            'Model': name,
            'Dataset': 'eICU (External)',
            'N': res['n_samples'],
            'Mean R²': res['mean_r2'],
            'Clinical R²': res['mean_r2_clin'],
            'Energy R²': res['mean_r2_energy'],
            'T<0': p['T_neg'], 'V<0': p['V_neg'],
            'R PSD viol': p['R_PSD_viol'],
        })
    pd.DataFrame(rows).to_csv(f"{args.outdir}/external_validation_results.csv", index=False)

    with open(f"{args.outdir}/external_validation_detail.json", 'w') as f:
        json.dump(all_results, f, indent=2)

    print(f"\n✓ Results: {args.outdir}/external_validation_results.csv")
    print(f"✓ Details: {args.outdir}/external_validation_detail.json")
    print("\nDone!")

if __name__ == '__main__':
    main()
