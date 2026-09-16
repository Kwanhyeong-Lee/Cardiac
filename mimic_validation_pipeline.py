"""
MIMIC-IV-ECHO Validation Pipeline for PINN v3c Eed Estimation
==============================================================
Run this AFTER completing CITI training and obtaining MIMIC-IV-ECHO access.

Prerequisites:
  1. CITI training completed → PhysioNet credentialed access
  2. MIMIC-IV-ECHO data downloaded
  3. pinn_v3c_eed.py in same directory
  4. pip install torch numpy scipy scikit-learn pandas wfdb

Validation Strategy (3 tiers with MIMIC data):
  Tier A: EDP prediction vs PCWP (Swan-Ganz ground truth)
  Tier B: Eed discrimination of diastolic dysfunction grades
  Tier C: Eed prediction of clinical outcomes (mortality, HF readmission)

Usage:
  python mimic_validation_pipeline.py --mimic-path /path/to/mimic-iv-echo/
"""

import argparse
import numpy as np
import pandas as pd
import torch
from pathlib import Path
from scipy.stats import pearsonr, spearmanr
from sklearn.metrics import roc_auc_score, mean_absolute_error
from sklearn.calibration import calibration_curve

# Import PINN v3c
from pinn_v3c_eed import (
    PINNv3c, FEAT_NAMES, TARGS,
    generate_training_data, train_model, evaluate_model
)


# ============================================================
# Step 1: MIMIC-IV-ECHO Data Extraction
# ============================================================
def extract_mimic_echo_data(mimic_path):
    """
    Extract diastolic echo parameters from MIMIC-IV-ECHO.

    Required fields (map to PINN v3c inputs):
      - EF (ejection fraction)
      - EDV, ESV (volumes, may need to derive from EF + dimensions)
      - SBP, DBP (from vitals)
      - HR (from vitals)
      - CO (cardiac output, may need to derive: SV * HR)
      - E/e' (tissue Doppler ratio) ← KEY diastolic input
      - E/A ratio (mitral inflow)
      - DT (deceleration time)
      - LAVI (left atrial volume index)

    Ground truth for validation:
      - PCWP (pulmonary capillary wedge pressure, from Swan-Ganz)
      - Diastolic dysfunction grade (from echo report)
    """
    mimic_path = Path(mimic_path)

    # TODO: Adapt these table names to actual MIMIC-IV-ECHO schema
    # The exact table structure depends on the MIMIC-IV-ECHO release

    # Example extraction logic (modify based on actual schema):
    print("Loading MIMIC-IV-ECHO tables...")

    # Echo measurements
    # echo = pd.read_csv(mimic_path / 'echo_measurements.csv')
    # vitals = pd.read_csv(mimic_path / 'vitalsign.csv')
    # swan = pd.read_csv(mimic_path / 'swan_ganz.csv')  # or from chartevents

    # Key itemids for MIMIC-IV chartevents (approximate):
    ITEMIDS = {
        'PCWP': [220059],           # Pulmonary capillary wedge pressure
        'SBP':  [220179, 220050],   # Systolic BP (invasive/non-invasive)
        'DBP':  [220180, 220051],   # Diastolic BP
        'HR':   [220045],           # Heart rate
        'CO':   [220088],           # Cardiac output (thermodilution)
    }

    # Echo-specific fields to look for:
    ECHO_FIELDS = {
        'EF': ['ef', 'ejection_fraction', 'lvef'],
        'Ee_prime': ['e_e_prime', 'e_over_e_prime', 'e_eprime_ratio'],
        'EA_ratio': ['e_a_ratio', 'e_over_a'],
        'DT': ['deceleration_time', 'dt', 'e_wave_deceleration'],
        'LAVI': ['la_volume_index', 'lavi', 'la_vol_index'],
        'EDV': ['lv_edv', 'edv', 'lv_end_diastolic_volume'],
        'ESV': ['lv_esv', 'esv', 'lv_end_systolic_volume'],
    }

    print("\n*** ACTION REQUIRED ***")
    print("Modify this function based on actual MIMIC-IV-ECHO schema.")
    print("Key steps:")
    print("  1. Load echo measurements table")
    print("  2. Extract E/e', E/A, DT, LAVI, EF, EDV, ESV")
    print("  3. Match with ICU vitals (SBP, DBP, HR) within ±24h of echo")
    print("  4. Match with Swan-Ganz PCWP if available (ground truth)")
    print("  5. Extract diastolic dysfunction grade from echo reports")
    print(f"\nExpected columns: {FEAT_NAMES}")

    # Return placeholder - replace with actual data
    return None


def extract_pcwp_ground_truth(mimic_path):
    """
    Extract PCWP from Swan-Ganz catheterization in MIMIC-IV.
    PCWP serves as proxy for LVEDP (correlation ~0.90).

    Match window: PCWP within ±24 hours of echocardiogram.
    """
    # TODO: Implement based on MIMIC-IV chartevents
    # PCWP itemid in MIMIC-IV: 220059
    pass


def extract_dd_grade(mimic_path):
    """
    Extract diastolic dysfunction grading from echo reports.

    Grades (ASE/EACVI 2016 guidelines):
      Grade 0: Normal diastolic function
      Grade I: Impaired relaxation (mild)
      Grade II: Pseudonormal (moderate)
      Grade III: Restrictive (severe)

    Can be derived from:
      - Free-text echo reports (NLP extraction)
      - Or combination: E/e' + E/A + DT + LAVI per ASE algorithm
    """
    # TODO: Implement NLP extraction or algorithmic grading
    pass


# ============================================================
# Step 2: Train PINN on simulation, predict on MIMIC
# ============================================================
def run_sim_to_real_validation(mimic_data, pcwp_data=None, dd_grades=None):
    """
    Core validation pipeline:
      1. Train PINN v3c on simulated data
      2. Apply to MIMIC patients (sim-to-real transfer)
      3. Validate against PCWP and DD grades
    """
    print("=" * 60)
    print("PINN v3c: MIMIC-IV-ECHO Validation")
    print("=" * 60)

    # --- Train on simulation ---
    print("\n[1/4] Training on simulated data...")
    X_sim, Y_sim = generate_training_data(N=20000, seed=42)
    model, scaler = train_model(X_sim, Y_sim, epochs=200, verbose=True)

    # --- Predict on MIMIC ---
    print("\n[2/4] Predicting on MIMIC patients...")
    X_mimic = mimic_data[FEAT_NAMES].values

    model.eval()
    X_sc = torch.tensor(scaler.transform(X_mimic), dtype=torch.float32)
    X_raw = torch.tensor(X_mimic, dtype=torch.float32)
    with torch.no_grad():
        pred = model(X_sc, X_raw).numpy()

    pred_df = pd.DataFrame(pred, columns=TARGS, index=mimic_data.index)

    # --- Tier A: EDP vs PCWP ---
    if pcwp_data is not None:
        print("\n[3/4] Tier A: EDP prediction vs PCWP...")
        matched = pred_df.join(pcwp_data, how='inner')
        if len(matched) > 10:
            r, p = pearsonr(matched['EDP'], matched['PCWP'])
            mae = mean_absolute_error(matched['PCWP'], matched['EDP'])
            print(f"  N = {len(matched)}")
            print(f"  EDP vs PCWP: R = {r:.3f} (p = {p:.4f})")
            print(f"  MAE = {mae:.1f} mmHg")

            # Also check: does PINN EDP beat Nagueh alone?
            nagueh_edp = 1.24 * matched['Ee_prime'] + 1.9
            r_nag, _ = pearsonr(nagueh_edp, matched['PCWP'])
            print(f"  Nagueh E/e' alone vs PCWP: R = {r_nag:.3f}")
            print(f"  PINN added value: {'YES' if r > r_nag else 'NO'} "
                  f"(delta R = {r - r_nag:+.3f})")

    # --- Tier B: Eed vs DD grade ---
    if dd_grades is not None:
        print("\n[3/4] Tier B: Eed discrimination of DD grades...")
        matched = pred_df.join(dd_grades, how='inner')
        if len(matched) > 30:
            from sklearn.metrics import roc_auc_score

            # Binary: any DD (grade >= 1) vs normal (grade 0)
            any_dd = (matched['dd_grade'] >= 1).astype(int)
            if any_dd.sum() > 5 and (1 - any_dd).sum() > 5:
                auc_eed = roc_auc_score(any_dd, matched['Eed'])
                # Compare with E/e' alone
                auc_ee = roc_auc_score(any_dd, matched['Ee_prime'])
                print(f"  Any DD detection:")
                print(f"    PINN Eed AUC = {auc_eed:.3f}")
                print(f"    E/e' alone AUC = {auc_ee:.3f}")
                print(f"    Added value: {'YES' if auc_eed > auc_ee else 'NO'} "
                      f"(delta AUC = {auc_eed - auc_ee:+.3f})")

            # Ordinal: Eed should increase with DD grade
            for grade in sorted(matched['dd_grade'].unique()):
                mask = matched['dd_grade'] == grade
                eed_vals = matched.loc[mask, 'Eed']
                print(f"  Grade {grade} (n={mask.sum()}): "
                      f"Eed = {eed_vals.mean():.4f} +/- {eed_vals.std():.4f}")

    # --- Tier C: Prognostic value ---
    print("\n[4/4] Tier C: Save predictions for outcome analysis...")
    pred_df.to_csv('pinn_v3c_mimic_predictions.csv')
    print("  Predictions saved. Use for:")
    print("  - 1-year mortality prediction (logistic regression: Eed + age + EF)")
    print("  - HF readmission prediction")
    print("  - Incremental value over E/e' alone (likelihood ratio test)")

    return pred_df


# ============================================================
# Step 3: Isotonic calibration (sim → real domain adaptation)
# ============================================================
def calibrate_predictions(pred_df, ground_truth, target='EDP'):
    """
    Apply isotonic regression calibration to correct sim-to-real bias.
    Uses a small calibration set (20% of MIMIC data) to learn the mapping.
    """
    from sklearn.isotonic import IsotonicRegression

    # Split: 20% calibration, 80% test
    n_cal = int(len(pred_df) * 0.2)
    idx = np.random.RandomState(42).permutation(len(pred_df))
    cal_idx, test_idx = idx[:n_cal], idx[n_cal:]

    # Fit isotonic regression on calibration set
    ir = IsotonicRegression(out_of_bounds='clip')
    ir.fit(pred_df.iloc[cal_idx][target].values,
           ground_truth.iloc[cal_idx].values)

    # Apply to test set
    pred_calibrated = ir.predict(pred_df.iloc[test_idx][target].values)
    true_test = ground_truth.iloc[test_idx].values

    r_before, _ = pearsonr(pred_df.iloc[test_idx][target].values, true_test)
    r_after, _ = pearsonr(pred_calibrated, true_test)
    mae_before = mean_absolute_error(true_test, pred_df.iloc[test_idx][target].values)
    mae_after = mean_absolute_error(true_test, pred_calibrated)

    print(f"\nIsotonic Calibration ({target}):")
    print(f"  Before: R={r_before:.3f}, MAE={mae_before:.3f}")
    print(f"  After:  R={r_after:.3f}, MAE={mae_after:.3f}")

    return ir


# ============================================================
# Main
# ============================================================
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='PINN v3c MIMIC Validation')
    parser.add_argument('--mimic-path', type=str, required=True,
                        help='Path to MIMIC-IV-ECHO data directory')
    parser.add_argument('--sim-only', action='store_true',
                        help='Run simulation validation only (no MIMIC data needed)')
    args = parser.parse_args()

    if args.sim_only:
        # Simulation-only validation (can run immediately)
        print("Running simulation-only validation...")
        X, Y = generate_training_data(N=15000)
        n_tr = int(len(X) * 0.8)
        idx = np.random.RandomState(0).permutation(len(X))
        X_tr, X_te = X[idx[:n_tr]], X[idx[n_tr:]]
        Y_tr = {k: v[idx[:n_tr]] for k, v in Y.items()}
        Y_te = {k: v[idx[n_tr:]] for k, v in Y.items()}

        model, scaler = train_model(X_tr, Y_tr, epochs=150)
        results = evaluate_model(model, scaler, X_te, Y_te)

        print("\n" + "=" * 60)
        for t in TARGS:
            r = results[t]
            print(f"  {t:>12}: R={r['R']:.4f}, MAE={r['MAE']:.4f}")
    else:
        # Full MIMIC validation
        mimic_data = extract_mimic_echo_data(args.mimic_path)
        if mimic_data is not None:
            pcwp = extract_pcwp_ground_truth(args.mimic_path)
            dd = extract_dd_grade(args.mimic_path)
            run_sim_to_real_validation(mimic_data, pcwp, dd)
        else:
            print("\nMIMIC data extraction not yet implemented.")
            print("Modify extract_mimic_echo_data() for your MIMIC-IV-ECHO schema.")
            print("\nRunning simulation validation instead...")
            # Fall back to sim-only
            import subprocess
            subprocess.run(['python', __file__, '--mimic-path', args.mimic_path, '--sim-only'])
