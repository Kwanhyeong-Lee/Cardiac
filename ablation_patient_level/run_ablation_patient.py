"""Patient-level (GroupShuffleSplit by subject_id) ablation - ONE model per call.
Usage: python3 ablation_patient.py <A|B|C|D> <seed>
Fixes row-level leakage: 5851 rows / 4241 patients = 1.38 rows/patient."""
import sys, json, time, warnings
import torch, torch.nn as nn, torch.nn.functional as F
import numpy as np, pandas as pd
warnings.filterwarnings('ignore')
from sklearn.model_selection import GroupShuffleSplit
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import r2_score
import ablation_models as M

L = sys.argv[1]; SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 0
torch.manual_seed(SEED); np.random.seed(SEED)
EPOCHS = 80; BATCH = 512
import os
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(HERE)   # project folder (holds the CSV)
df = pd.read_csv(OUT + "/cardiac_energetics_hamiltonian.csv")

INPUT_COLS = ['pre_EF','pre_EDV','pre_ESV','pre_SBP','pre_DBP','pre_HR',
              'pre_Ee_prime','pre_LAVI','pre_EA_ratio','pre_DT','pre_CO']
X = df[INPUT_COLS].values.astype(np.float32)
Y = df[M.TARGET_COLS].values.astype(np.float32)
groups = df['subject_id'].values

# ---- PATIENT-LEVEL split: no subject appears in both train and test ----
gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=SEED)
tr, te = next(gss.split(X, Y, groups))
assert len(set(groups[tr]) & set(groups[te])) == 0, "patient leakage!"

X_tr, X_te, Y_tr, Y_te = X[tr], X[te], Y[tr], Y[te]
scX = StandardScaler().fit(X_tr); scY = StandardScaler().fit(Y_tr)
Xtr, Xte = scX.transform(X_tr).astype(np.float32), scX.transform(X_te).astype(np.float32)
Ytr = scY.transform(Y_tr).astype(np.float32)

model = {"A": M.PHPINN, "B": M.VanillaMLP, "C": M.NoStructurePINN, "D": M.SoftConstraintPINN}[L]()
soft = (L == "D")
ds = torch.utils.data.TensorDataset(torch.tensor(Xtr), torch.tensor(Ytr))
dl = torch.utils.data.DataLoader(ds, batch_size=BATCH, shuffle=True)
opt = torch.optim.AdamW(model.parameters(), lr=2e-3, weight_decay=1e-4)
sch = torch.optim.lr_scheduler.CosineAnnealingLR(opt, EPOCHS)
best = 1e9; best_state = None; t0 = time.time()
for ep in range(EPOCHS):
    model.train(); tot = 0
    for bx, by in dl:
        opt.zero_grad()
        pred, H, T, V, R = model(bx)
        loss = F.mse_loss(pred, by)
        if soft:
            loss = loss + 1.0 * (F.relu(-T).mean() + F.relu(-V).mean())
            if R is not None:
                loss = loss + 1.0 * F.relu(-torch.linalg.eigvalsh(R)).mean()
        loss.backward(); nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step(); tot += loss.item()
    sch.step()
    if tot < best: best = tot; best_state = {k: v.clone() for k, v in model.state_dict().items()}
model.load_state_dict(best_state); model.eval()

with torch.no_grad():
    pred_s, H, T, V, R = model(torch.tensor(Xte))
    pred = pred_s.numpy() * scY.scale_ + scY.mean_
    Hn, Tn, Vn = H.numpy(), T.numpy(), V.numpy()
r2s = {c: float(r2_score(Y_te[:, i], pred[:, i])) for i, c in enumerate(M.TARGET_COLS)}
r_psd = -1
if R is not None:
    Rn = R.numpy(); r_psd = int(sum(np.linalg.eigvalsh(Rn[i]).min() < -1e-6 for i in range(Rn.shape[0])))
res = {"letter": L, "seed": SEED, "split": "patient-level GroupShuffleSplit",
       "n_train_rows": int(len(tr)), "n_test_rows": int(len(te)),
       "n_train_patients": int(len(set(groups[tr]))), "n_test_patients": int(len(set(groups[te]))),
       "n_params": sum(p.numel() for p in model.parameters()),
       "mean_r2_all": float(np.mean(list(r2s.values()))),
       "mean_r2_clin": float(np.mean([r2s[c] for c in M.CLIN_COLS])),
       "H_T_V_MSE": float(np.mean((Hn - Tn - Vn) ** 2)),
       "T_neg": int((Tn < 0).sum()), "V_neg": int((Vn < 0).sum()), "R_PSD_viol": r_psd,
       "time_s": round(time.time() - t0, 1), "r2": r2s}
json.dump(res, open(os.path.join(HERE, f"pat_{L}_{SEED}.json"), "w"), indent=1)
print(f"{L} seed{SEED}: R2={res['mean_r2_all']:.4f} Tneg={res['T_neg']} Vneg={res['V_neg']} "
      f"PSD={res['R_PSD_viol']} testpts={res['n_test_patients']} ({res['time_s']}s)")
