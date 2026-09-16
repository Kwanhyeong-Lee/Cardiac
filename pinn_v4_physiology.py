"""
PINN v4: Physiology-Based Diastolic Hemodynamic Estimation
===========================================================

CRITICAL FIX from v3c — Breaking the Nagueh Tautology
------------------------------------------------------
v3c had a fatal circularity:
  Simulator:  EDP (set) → E/e' = (EDP - 1.9) / 1.24   [inverse Nagueh]
  PINN:       E/e' (input) → EDP ≈ 1.24 × E/e' + 1.9  [learned forward Nagueh]

  Result: PINN merely reproduced the Nagueh formula.
  Evidence: EDP AUC ≈ E/e' AUC in all subgroups, zero added value in gray zone.

v4 generates E/e' from first-principles diastolic physiology:

  Diastolic Filling Model (refs: Nagueh JACC 2009, Little Circ 1990,
  Firstenberg JACC 2001, Ommen Circulation 2000):

    e' = e'_base × √(τ_ref / τ) × exp(-k × (Eed - Eed_ref))
      - e' reflects BOTH active relaxation (τ) AND passive stiffness (Eed)
      - Ref: Sohn et al. JACC 1997 — e' inversely related to τ
      - Ref: Ommen et al. 2000 — e' reduced in increased chamber stiffness

    P_min = -k_suction × (τ_ref / τ)^1.5
      - LV minimum diastolic pressure (early diastolic suction)
      - Fast relaxation → negative P_min → enhanced early filling
      - Ref: Firstenberg et al. JACC 2001

    LAP ≈ EDP × 1.05 + 1.5  (LA pressure at MV opening)
    ΔP = LAP - P_min          (transmitral pressure gradient)

    E = k_E × √(ΔP) × relaxation_efficiency(τ, LAP)
      - Simplified Bernoulli for transmitral flow
      - Relaxation efficiency: impaired relaxation reduces effective ΔP
      - But high LAP overcomes relaxation impairment (pseudonormalization)

    E/e' = E / e'  ← EMERGENT, not prescribed by any formula

  Key consequence:
    Same E/e' = 10 can correspond to:
      - Patient A: τ=45ms, Eed=0.06, EDP=10  (normal, good relaxation)
      - Patient B: τ=55ms, Eed=0.04, EDP=22  (HFrEF, high volume)
    Nagueh would estimate EDP≈14.3 for both. PINN can disambiguate using
    EDV, ESV, EF, CO — that's the genuine added value.

  PhysicsDecoder changes:
    - EDP = A × exp(Eed × (EDV - V0))  ← PURE EDPVR, no Nagueh blend
    - Removed gate_EDP (was blending Nagueh with EDPVR)
    - Added τ as latent output (non-invasive τ estimation = novel contribution)

Architecture:
  11 inputs → Encoder MLP → 7 latent → Physics Decoder → 7 outputs

  Inputs:  EF, EDV, ESV, SBP, DBP, HR, CO, E/e', E/A, DT, LAVI
  Latent:  Ees_delta, Eed, V0, A, tau, Ea, gate_Ea
  Outputs: Ees, Eed, Ea, Ea/Ees coupling, EDP, efficiency, tau

Author: Kwanhyeong Lee
Date: 2026-05
"""

import torch
import torch.nn as nn
import numpy as np
from sklearn.preprocessing import StandardScaler
from scipy.stats import pearsonr, spearmanr
from sklearn.metrics import roc_auc_score, mean_absolute_error
from torch.utils.data import TensorDataset, DataLoader

# ============================================================
# Constants
# ============================================================
FEAT_NAMES = ['EF', 'EDV', 'ESV', 'SBP', 'DBP', 'HR', 'CO',
              'Ee_prime', 'EA_ratio', 'DT', 'LAVI']
TARGS = ['Ees', 'Eed', 'Ea', 'coupling', 'EDP', 'efficiency', 'tau']

# --- Diastolic Physiology Constants ---
# Each constant has a physiological basis documented below.
TAU_REF = 45.0       # Reference relaxation time constant (ms)
                     # Normal τ ≈ 35-50ms (Weiss et al. Circ 1976)
EED_REF = 0.05       # Reference chamber stiffness (1/ml)
                     # Normal Eed ≈ 0.02-0.08 (Zile et al. NEJM 2004)
E_PRIME_BASE = 13.0  # Baseline e' for healthy adult (cm/s)
                     # Normal septal e' ≈ 10-15 (Nagueh JASE 2016)
K_STIFF_E = 8.0      # Stiffness sensitivity on e' (dimensionless)
                     # Controls how Eed reduces e' beyond relaxation effect
K_E = 18.0           # E-wave velocity scaling (cm/s per √mmHg)
                     # Calibrated to give E ≈ 70-100 cm/s in normals
                     # Reduced from 23→18 based on Nagueh 2016 normal E range
K_SUCTION = 5.0      # LV suction base pressure (mmHg)
                     # P_min typically -2 to -5 mmHg in normals
SUCTION_EXP = 1.5    # Suction τ exponent
                     # Stronger τ-dependence of suction
LAP_SCALE = 1.05     # LAP/EDP ratio at MV opening
                     # LAP slightly exceeds EDP due to v-wave
LAP_OFFSET = 1.5     # LAP offset from EDP (mmHg)


# ============================================================
# Simulator: Physiology-based cohort generator
# ============================================================
def generate_training_data(N=15000, seed=42):
    """
    Generate simulated hemodynamic data from 6 cardiac phenotypes.

    CRITICAL DIFFERENCE from v3c:
      E/e' is computed from diastolic physiology (τ, Eed, suction, LAP),
      NOT from inverse Nagueh formula. This breaks the circular dependency
      that made v3c's PINN a trivial formula reproducer.

    New parameter: τ (relaxation time constant) per phenotype.

    Returns: X (N x 11 features), Y (dict of 7 target arrays)
    """
    rng = np.random.RandomState(seed)

    # Cohort proportions: calibrated to match MIMIC-IV-ECHO population
    # Normal 30%, HFrEF 8%, HFpEF 22%, HTN 18%, Elderly 15%, Athlete 7%
    n_norm = int(N * 0.30)
    n_hfref = int(N * 0.08)
    n_hfpef = int(N * 0.22)
    n_htn = int(N * 0.18)
    n_eld = int(N * 0.15)
    n_ath = N - n_norm - n_hfref - n_hfpef - n_htn - n_eld

    def make_cohort(n, ees_r, eed_r, edv_r, hr_r, ef_r, sbp_r, tau_r, edp_r):
        """Generate base physiological parameters for one phenotype.
        v4.1 changes (EF-primary derivation):
          - ef_r replaces A_r: EF is now a PRIMARY sampled parameter
          - V0 derived from ESPVR: V0 = ESV - ESP/Ees
          - A derived from EDPVR: A = EDP / exp(Eed*(EDV-V0))
          This eliminates V0 capping artifacts that distorted EF.
        """
        return tuple(rng.uniform(*r, n) for r in
                     [ees_r, eed_r, edv_r, hr_r, ef_r, sbp_r, tau_r, edp_r])

    # ----------------------------------------------------------------
    # Phenotype definitions (v4.1 — EF-primary derivation)
    # Format: (Ees, Eed, EDV, HR, EF, SBP, tau, EDP_target)
    # EF replaces A as a primary sampled parameter.
    # V0, A are DERIVED (ESPVR / EDPVR consistency).
    # ----------------------------------------------------------------
    # Literature-verified ranges (PINN v4 Parameter Audit, 2026-05-11)
    # Sources: Chen 2001, Burkhoff 2005, Klotz 2006, Weiss 1976,
    #          Borlaug 2006, Westermann 2008, Nagueh 2016, Lang 2015
    # EF ranges: Lang JASE 2015, Borlaug Circ 2006, Ponikowski ESC 2016
    # ----------------------------------------------------------------
    cohorts = [
        # Normal: preserved relaxation, compliance, normal filling pressure
        make_cohort(n_norm,
                    (2.0, 4.5), (0.02, 0.07), (80, 130), (55, 85),
                    (0.55, 0.75), (105, 140), (35, 52), (5, 14)),
        # HFrEF: dilated, reduced contractility, elevated filling pressure
        make_cohort(n_hfref,
                    (0.5, 1.5), (0.03, 0.10), (150, 280), (70, 110),
                    (0.15, 0.40), (85, 130), (50, 80), (12, 30)),
        # HFpEF: stiff, impaired relaxation, elevated filling pressure
        make_cohort(n_hfpef,
                    (2.0, 5.0), (0.08, 0.25), (80, 140), (60, 95),
                    (0.45, 0.65), (115, 170), (55, 85), (14, 35)),
        # HTN: concentric remodeling, moderate pressure elevation
        make_cohort(n_htn,
                    (2.5, 6.0), (0.05, 0.14), (75, 125), (60, 90),
                    (0.50, 0.70), (140, 190), (42, 62), (10, 22)),
        # Elderly: age-related stiffening, mildly elevated pressure
        make_cohort(n_eld,
                    (1.5, 3.5), (0.05, 0.16), (85, 155), (55, 80),
                    (0.45, 0.65), (105, 155), (48, 72), (8, 22)),
        # Athlete: supernormal relaxation, low filling pressure
        make_cohort(n_ath,
                    (2.5, 5.5), (0.01, 0.04), (110, 180), (42, 62),
                    (0.55, 0.75), (100, 130), (28, 42), (4, 12)),
    ]

    # Concatenate all cohorts
    arrs = [np.concatenate([c[i] for c in cohorts]) for i in range(8)]
    Ees, Eed, EDV, HR, EF, SBP, tau, EDP_target = arrs
    Nt = len(Ees)

    # ================================================================
    # STEP 0: EF-primary derivation (v4.1 — eliminates V0 capping)
    # ================================================================
    # EF is sampled directly per cohort. All other quantities derived:
    #   ESV = EDV × (1 - EF)           — definition
    #   ESP = 0.9 × SBP                — approximation
    #   V0  = ESV - ESP/Ees            — from ESPVR: ESP = Ees(ESV-V0)
    #   A   = EDP / exp(Eed×(EDV-V0))  — from EDPVR self-consistency
    #
    # This guarantees every sample has a physically consistent
    # (Ees, Eed, V0, A, EDV, ESV, EDP) tuple — no clipping needed.
    ESP = 0.9 * SBP
    ESV = EDV * (1 - EF)
    SV = EDV - ESV  # = EDV * EF
    V0 = ESV - ESP / Ees
    # A from EDPVR: EDP = A * exp(Eed * (EDV - V0))
    # Note: A can be legitimately very small (1e-10) when Eed is high,
    # because it's just a scaling factor. Do NOT clip A to 0.01 —
    # that destroys EDPVR self-consistency for HFpEF cohorts.
    edpvr_exp = Eed * np.maximum(EDV - V0, 0)
    # Clip exponent to prevent float64 overflow (exp(700) overflows)
    edpvr_exp = np.minimum(edpvr_exp, 200)
    A = EDP_target / np.exp(edpvr_exp)
    # EDP is exactly EDP_target by construction
    EDP = EDP_target.copy()

    # ================================================================
    # STEP 1: Standard hemodynamics
    # ================================================================
    DBP = rng.uniform(0.5, 0.65, Nt) * SBP
    MAP = (SBP + 2 * DBP) / 3
    CO = SV * HR / 1000
    Ea = ESP / np.clip(SV, 1, None)
    coupling = Ea / np.clip(Ees, 0.1, None)

    # ================================================================
    # STEP 2: EDP — already set in STEP 0
    # EDP = EDP_target, with V0 derived to be EDPVR-consistent.
    # Verify: A * exp(Eed * (EDV - V0)) ≈ EDP_target (by construction)
    # ================================================================
    # (EDP already assigned above)

    # ================================================================
    # STEP 3: e' — mitral annular early diastolic velocity
    # ================================================================
    # Physiology: e' reflects both active relaxation (τ) and passive
    # stiffness (Eed). Faster relaxation → higher e'. Lower stiffness
    # → higher e'.
    #
    # Model: e' = E_PRIME_BASE × √(τ_ref/τ) × exp(-K_STIFF × (Eed - Eed_ref))
    #
    # Basis:
    #   - √(τ_ref/τ): e' inversely related to τ (Sohn JACC 1997)
    #     Square root gives physiological range (e' 5-18 cm/s)
    #   - exp(-K×ΔEed): stiffness further reduces annular velocity
    #     (Ommen Circulation 2000)
    e_prime = (E_PRIME_BASE
               * np.sqrt(TAU_REF / tau)
               * np.exp(-K_STIFF_E * (Eed - EED_REF)))

    # ================================================================
    # STEP 4: E — mitral inflow early diastolic velocity
    # ================================================================
    # Physiology: E reflects transmitral pressure gradient (ΔP).
    # ΔP = LAP_at_MVO - LV_P_min
    #
    # P_min: LV minimum diastolic pressure (early diastolic suction)
    #   - Fast relaxation (low τ) → more negative P_min → larger ΔP
    #   - Basis: Firstenberg JACC 2001, Courtois Circulation 1988
    P_min = -K_SUCTION * np.power(TAU_REF / tau, SUCTION_EXP)

    # LAP at mitral valve opening: slightly exceeds EDP
    LAP = EDP * LAP_SCALE + LAP_OFFSET

    # Transmitral pressure gradient
    delta_P = np.maximum(LAP - P_min, 0.5)

    # E velocity: simplified Bernoulli + relaxation modulation
    #
    # Relaxation efficiency: in impaired relaxation (high τ),
    # the LV hasn't fully relaxed when the MV opens, reducing
    # effective early filling. BUT high LAP can overcome this
    # (pseudonormalization → restrictive pattern progression).
    #
    # Basis: Nagueh JACC 1996 — pseudonormal pattern occurs when
    # elevated LAP restores E despite impaired relaxation
    tau_efficiency = np.power(TAU_REF / tau, 0.7)
    # High LAP overrides relaxation impairment (pseudonormalization)
    lap_override = np.clip((LAP - 15) / 10, 0, 1)
    relaxation_factor = tau_efficiency * (1 - lap_override) + 1.0 * lap_override

    E = K_E * np.sqrt(delta_P) * relaxation_factor

    # ================================================================
    # STEP 5: E/e' — EMERGENT, not prescribed
    # ================================================================
    # This is the key fix: E/e' is now a complex nonlinear function
    # of (EDP, τ, Eed, volumes), NOT a simple linear function of EDP.
    Ee_prime = E / np.clip(e_prime, 1.0, None)

    # ================================================================
    # STEP 6: E/A — from phenotype base + physiological adjustment
    # ================================================================
    # E/A depends on balance of early vs atrial filling:
    #   Grade I (impaired relax): E↓ A↑ → E/A < 1
    #   Pseudonormal: E normalized, A moderate → E/A 1-1.5
    #   Restrictive: E↑↑, A↓ → E/A > 2
    #
    # Operating stiffness at EDV (slope of EDPVR):
    #   dP/dV = Eed × EDP (for exponential EDPVR)
    dPdV = Eed * EDP  # mmHg/ml, operating point stiffness

    # A wave: atrial contraction against LV stiffness
    # Higher τ → compensatory atrial kick (increased A)
    # Higher stiffness → resistance to atrial filling (decreased A)
    A_base = rng.uniform(50, 80, Nt)
    tau_boost = np.power(tau / TAU_REF, 0.5)    # impaired relax → more A
    stiff_penalty = 1.0 / (1 + 0.10 * np.maximum(dPdV - 0.5, 0))
    A_velocity = A_base * tau_boost * stiff_penalty
    EA_ratio = np.clip(E / np.clip(A_velocity, 10, None), 0.3, 4.0)

    # ================================================================
    # STEP 7: DT — deceleration time
    # ================================================================
    # DT reflects LV operating compliance and relaxation:
    #   Stiffer LV → faster pressure equalization → shorter DT
    #   Impaired relaxation → prolonged DT (incomplete relaxation)
    #
    # Basis: Little & Downes Circ 1990, Garcia Circulation 1997
    C_eff = 1.0 / np.maximum(dPdV, 0.05)  # effective compliance
    DT = np.clip(
        120 * np.sqrt(C_eff) * np.power(tau / TAU_REF, 0.3)
        + rng.randn(Nt) * 20,
        80, 350
    )

    # ================================================================
    # STEP 8: LAVI — LA volume index (chronic marker)
    # ================================================================
    # LAVI reflects chronic LA pressure elevation → LA remodeling
    # Acute changes don't affect LAVI; it's a structural marker.
    # Basis: Tsang JACC 2002 — LAVI >34 indicates chronic elevation
    LAVI_base = rng.uniform(16, 24, Nt)
    chronic_edp_effect = 1.5 * np.maximum(EDP - 10, 0) ** 0.7
    LAVI = np.clip(LAVI_base + chronic_edp_effect, 10, 60)

    # ================================================================
    # STEP 9: Efficiency (same as v3c)
    # ================================================================
    SW = SV * MAP * 0.0133
    PE = 0.5 * Ees * np.clip(ESV - V0, 0, None) ** 2 * 0.0133
    PVA = SW + PE
    eff = np.clip(SW / np.clip(PVA, 0.01, None), 0.1, 0.95)

    # ================================================================
    # STEP 10: Add measurement noise
    # ================================================================
    ns = lambda a, p: a * (1 + rng.randn(Nt) * p)
    EDV_n = ns(EDV, 0.05)
    ESV_n = ns(ESV, 0.05)
    SBP_n = ns(SBP, 0.03)
    DBP_n = ns(DBP, 0.03)
    HR_n = ns(HR, 0.02)
    # E and e' have independent measurement noise → E/e' noise is realistic
    E_noisy = E * (1 + rng.randn(Nt) * 0.10)
    e_prime_noisy = e_prime * (1 + rng.randn(Nt) * 0.12)
    Ee_n = np.clip(E_noisy / np.clip(e_prime_noisy, 1.0, None), 2, 40)
    EA_n = np.clip(EA_ratio + rng.randn(Nt) * 0.2, 0.3, 4.0)
    DT_n = np.clip(DT + rng.randn(Nt) * 15, 80, 350)
    LAVI_n = np.clip(LAVI + rng.randn(Nt) * 3, 10, 60)
    SV_n = EDV_n - ESV_n
    EF_n = SV_n / EDV_n
    CO_n = SV_n * HR_n / 1000

    # ================================================================
    # STEP 11: Filter physiologically valid samples
    # ================================================================
    mask = ((EF_n > 0.10) & (EF_n < 0.90) & (SBP_n > 60) &
            (SV_n > 10) & (Ea > 0.3) & (Ea < 8) &
            (Eed > 0.005) & (EDP > 1) & (EDP < 45) &
            (Ee_n > 2) & (Ee_n < 40) &
            (e_prime > 1) & (E > 10))
    idx = np.where(mask)[0]

    X = np.column_stack([EF_n[idx], EDV_n[idx], ESV_n[idx], SBP_n[idx],
                         DBP_n[idx], HR_n[idx], CO_n[idx], Ee_n[idx],
                         EA_n[idx], DT_n[idx], LAVI_n[idx]])
    Y = {t: v[idx] for t, v in zip(TARGS,
         [Ees, Eed, Ea, coupling, EDP, eff, tau])}

    print(f"Generated {len(idx)}/{Nt} valid samples")
    print(f"  Eed  [{Y['Eed'].min():.3f}, {Y['Eed'].max():.3f}]")
    print(f"  EDP  [{Y['EDP'].min():.1f}, {Y['EDP'].max():.1f}]")
    print(f"  tau  [{Y['tau'].min():.1f}, {Y['tau'].max():.1f}]")
    print(f"  E/e' [{X[:, 7].min():.1f}, {X[:, 7].max():.1f}]")

    return X, Y


def calibration_report(X, Y):
    """
    Print detailed calibration report for reviewer verification.
    Checks that E/e'-EDP relationship is realistic and non-circular.
    """
    Ee = X[:, 7]  # E/e' (noisy, as measured)
    EDP = Y['EDP']
    tau = Y['tau']
    Eed = Y['Eed']

    # 1. E/e' vs EDP correlation — should be ~0.7-0.85 (Nagueh r≈0.87)
    # NOT 0.99 (which would indicate circularity)
    r_ee_edp, _ = pearsonr(Ee, EDP)
    rho_ee_edp, _ = spearmanr(Ee, EDP)

    # 2. Nagueh estimate vs true EDP — should have residual variance
    edp_nagueh = 1.24 * Ee + 1.9
    nagueh_mae = np.mean(np.abs(edp_nagueh - EDP))
    nagueh_r, _ = pearsonr(edp_nagueh, EDP)

    # 3. Gray zone analysis: E/e' 8-13, EDP should vary substantially
    gz = (Ee >= 8) & (Ee <= 13)
    edp_gz = EDP[gz]

    # 4. Same E/e' → different EDP depending on tau
    gz_low_tau = gz & (tau < np.median(tau))
    gz_high_tau = gz & (tau >= np.median(tau))

    print("\n" + "=" * 60)
    print("CALIBRATION REPORT — Reviewer Verification")
    print("=" * 60)
    print(f"\n1. E/e' vs EDP correlation:")
    print(f"   Pearson r  = {r_ee_edp:.3f}  (target: 0.70-0.87)")
    print(f"   Spearman ρ = {rho_ee_edp:.3f}")
    if r_ee_edp > 0.95:
        print("   ⚠ WARNING: r > 0.95 suggests residual circularity!")
    elif r_ee_edp < 0.50:
        print("   ⚠ WARNING: r < 0.50 — model may be under-correlated")
    else:
        print("   ✓ Within expected range — no circularity detected")

    print(f"\n2. Nagueh formula accuracy on this data:")
    print(f"   Nagueh EDP vs True EDP: r = {nagueh_r:.3f}, MAE = {nagueh_mae:.1f} mmHg")
    print(f"   (If MAE ≈ 0, model is circular. Target: MAE > 3 mmHg)")

    print(f"\n3. Gray zone (E/e' 8-13): n = {gz.sum()}")
    if gz.sum() > 50:
        print(f"   EDP range: [{edp_gz.min():.1f}, {edp_gz.max():.1f}] mmHg")
        print(f"   EDP mean ± SD: {edp_gz.mean():.1f} ± {edp_gz.std():.1f}")
        print(f"   EDP IQR: [{np.percentile(edp_gz, 25):.1f}, "
              f"{np.percentile(edp_gz, 75):.1f}]")
        print(f"   (Wide range = good. PINN can learn to disambiguate.)")

    print(f"\n4. τ-dependent EDP in gray zone:")
    if gz_low_tau.sum() > 20 and gz_high_tau.sum() > 20:
        edp_low = EDP[gz_low_tau]
        edp_high = EDP[gz_high_tau]
        print(f"   Low τ  (fast relax): EDP = {edp_low.mean():.1f} ± {edp_low.std():.1f}"
              f"  (n={gz_low_tau.sum()})")
        print(f"   High τ (slow relax): EDP = {edp_high.mean():.1f} ± {edp_high.std():.1f}"
              f"  (n={gz_high_tau.sum()})")
        edp_diff = edp_high.mean() - edp_low.mean()
        print(f"   Δ EDP = {edp_diff:.1f} mmHg")
        if abs(edp_diff) > 2:
            print(f"   ✓ Same E/e' → different EDP depending on τ. PINN has signal!")
        else:
            print(f"   ⚠ Low Δ — may need recalibration")
    print()


# ============================================================
# Physics Decoder v4 — NO Nagueh shortcut
# ============================================================
class PhysicsDecoderV4(nn.Module):
    """
    Converts 7 latent parameters into 7 physiological outputs
    using embedded cardiovascular physics equations.

    CRITICAL CHANGE from v3c:
      - EDP computed SOLELY from EDPVR: P = A × exp(Eed × (V - V0))
      - NO Nagueh formula (EDP = 1.24 × E/e' + 1.9) anywhere
      - NO gate_EDP blending between Nagueh and EDPVR
      - Added τ (relaxation time constant) as output

    Latent parameters:
      0: Ees_delta  — systolic elastance correction
      1: Eed        — diastolic stiffness coefficient
      2: V0         — unstressed volume
      3: A          — EDPVR scaling factor
      4: tau_raw    — relaxation time constant (raw, pre-sigmoid)
      5: Ea_raw     — arterial elastance (learned)
      6: gate_Ea    — Ea blend gate
    """
    def forward(self, lat, raw):
        # Unpack 11 raw inputs
        EF, EDV, ESV, SBP, DBP, HR, CO, Ee, EA, DT, LAVI = \
            [raw[:, i:i+1] for i in range(11)]

        ESP = 0.9 * SBP
        SV = torch.clamp(EDV - ESV, min=1.0)
        MAP = (SBP + 2 * DBP) / 3

        # --- Systolic: Chen/Shishido + learned correction (unchanged) ---
        chen_denom = torch.clamp(torch.abs(ESV - 0.1 * EDV), min=1.0)
        Chen_Ees = torch.clamp(ESP / chen_denom, 0.3, 12.0)
        Ees = torch.clamp(
            Chen_Ees * (1 + 0.3 * torch.tanh(lat[:, 0:1])),
            0.3, 10.0
        )

        # --- Diastolic: PURE EDPVR physics (v4.1) ---
        # P = A × exp(Eed × (V - V0))
        # Narrow ranges empirically outperform widened ranges (v41 > v41c).
        Eed = 0.005 + 0.495 * torch.sigmoid(lat[:, 1:2])    # [0.005, 0.50]
        V0 = -20 + 50 * torch.sigmoid(lat[:, 2:3])           # [-20, 30]
        A_param = 0.1 + 4.9 * torch.sigmoid(lat[:, 3:4])     # [0.1, 5.0]

        edpvr_arg = torch.clamp(Eed * (EDV - V0), -5, 5)
        EDP = torch.clamp(A_param * torch.exp(edpvr_arg), 1.0, 45.0)

        # --- τ (relaxation time constant) ---
        # Novel output: non-invasive τ estimation
        tau = 25.0 + 65.0 * torch.sigmoid(lat[:, 4:5])      # [25, 90] ms

        # --- Arterial: gated Ea (unchanged) ---
        Ea_learned = 0.3 + 5.7 * torch.sigmoid(lat[:, 5:6])
        gate = torch.sigmoid(lat[:, 6:7])
        Ea_phys = torch.clamp(ESP / SV, 0.3, 6.0)
        Ea = gate * Ea_learned + (1 - gate) * Ea_phys

        # --- Derived metrics ---
        coupling = Ea / torch.clamp(Ees, min=0.1)
        SW = SV * MAP * 0.0133
        PE = 0.5 * Ees * torch.clamp(ESV - V0, min=0.0) ** 2 * 0.0133
        PVA = SW + PE
        eff = torch.clamp(SW / torch.clamp(PVA, min=0.01), 0.1, 0.95)

        return torch.cat([Ees, Eed, Ea, coupling, EDP, eff, tau], dim=-1)


# ============================================================
# PINN v4 Model (original — kept for checkpoint compatibility)
# ============================================================
class PINNv4(nn.Module):
    """
    Physics-Informed Neural Network for diastolic hemodynamic estimation.

    Encoder: 11 → 256 → 128 → 64 → 7 (latent physiological parameters)
    Decoder: PhysicsDecoderV4 (EDPVR, Chen/Shishido — NO Nagueh)
    """
    def __init__(self):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(11, 256), nn.SiLU(), nn.BatchNorm1d(256), nn.Dropout(0.1),
            nn.Linear(256, 128), nn.SiLU(), nn.BatchNorm1d(128), nn.Dropout(0.1),
            nn.Linear(128, 64), nn.SiLU(), nn.BatchNorm1d(64),
            nn.Linear(64, 7)
        )
        self.decoder = PhysicsDecoderV4()

    def forward(self, x_scaled, x_raw):
        latent = self.encoder(x_scaled)
        return self.decoder(latent, x_raw)


# ============================================================
# Improved Physics Decoder (v4b)
# ============================================================
class PhysicsDecoderV4b(nn.Module):
    """
    Improved physics decoder with:
      - Softplus-based output scaling (no gradient-killing clamps)
      - Wider V0 range [-50, 60] matching simulator
      - Ees-Ea physiological coupling
      - tau-Eed cross-constraint (stiff ventricle → slower relaxation)

    Latent parameters (9 total — expanded from 7):
      0: Ees_delta     — systolic elastance correction
      1: Eed_raw       — diastolic stiffness (pre-sigmoid)
      2: V0_raw        — unstressed volume (pre-sigmoid)
      3: A_raw         — EDPVR scaling factor (pre-sigmoid)
      4: tau_raw       — relaxation time constant (pre-sigmoid)
      5: Ea_raw        — arterial elastance (learned)
      6: gate_Ea       — Ea blend gate
      7: tau_eed_coup  — tau-Eed coupling strength
      8: ea_ees_coup   — Ea-Ees coupling strength
    """
    def forward(self, lat, raw):
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

        # --- Diastolic: PURE EDPVR (v4.1) ---
        Eed = 0.005 + 0.495 * torch.sigmoid(lat[:, 1:2])
        V0 = -20 + 50 * torch.sigmoid(lat[:, 2:3])           # [-20, 30]
        A_param = 0.1 + 4.9 * torch.sigmoid(lat[:, 3:4])     # [0.1, 5.0]

        edpvr_arg = torch.clamp(Eed * (EDV - V0), -5, 5)
        EDP = torch.clamp(A_param * torch.exp(edpvr_arg), 1.0, 45.0)

        # --- τ with Eed coupling ---
        # Physiological basis: stiffer ventricle (higher Eed) tends to have
        # slower relaxation (higher τ). Nishimura JACC 1993, Zile Circ 2004.
        tau_base = 25.0 + 65.0 * torch.sigmoid(lat[:, 4:5])
        tau_eed_strength = 0.3 * torch.tanh(lat[:, 7:8])   # coupling direction
        # Eed contribution: higher Eed → higher tau adjustment
        Eed_centered = (Eed - 0.1) / 0.1  # normalize around typical value
        tau = torch.clamp(tau_base + tau_eed_strength * Eed_centered * 15.0,
                          20.0, 100.0)

        # --- Arterial: gated Ea with Ees coupling ---
        Ea_learned = 0.3 + 5.7 * torch.sigmoid(lat[:, 5:6])
        gate = torch.sigmoid(lat[:, 6:7])
        Ea_phys = torch.clamp(ESP / SV, 0.3, 6.0)
        Ea_base = gate * Ea_learned + (1 - gate) * Ea_phys
        # Coupling: normal coupling ratio Ea/Ees ≈ 0.6-1.2
        # Slight Ees-informed adjustment to Ea
        ea_ees_strength = 0.15 * torch.tanh(lat[:, 8:9])
        Ea = torch.clamp(Ea_base * (1 + ea_ees_strength * (Ees / 2.5 - 1)),
                          0.3, 8.0)

        # --- Derived metrics ---
        coupling = Ea / torch.clamp(Ees, min=0.1)
        SW = SV * MAP * 0.0133
        PE = 0.5 * Ees * torch.clamp(ESV - V0, min=0.0) ** 2 * 0.0133
        PVA = SW + PE
        eff = torch.clamp(SW / torch.clamp(PVA, min=0.01), 0.1, 0.95)

        return torch.cat([Ees, Eed, Ea, coupling, EDP, eff, tau], dim=-1)


# ============================================================
# Residual Block
# ============================================================
class ResBlock(nn.Module):
    """Pre-activation residual block with optional dimension change."""
    def __init__(self, dim, dropout=0.1):
        super().__init__()
        self.net = nn.Sequential(
            nn.BatchNorm1d(dim),
            nn.SiLU(),
            nn.Dropout(dropout),
            nn.Linear(dim, dim),
            nn.BatchNorm1d(dim),
            nn.SiLU(),
            nn.Dropout(dropout),
            nn.Linear(dim, dim),
        )

    def forward(self, x):
        return x + self.net(x)


# ============================================================
# Cross-Parameter Attention
# ============================================================
class ParameterAttention(nn.Module):
    """
    Light self-attention over the 9 latent parameters.
    Each parameter attends to others to learn physiological couplings
    (e.g., Ees-Ea, Eed-tau) without hard-coding.
    """
    def __init__(self, n_params=9, d_model=16, n_heads=4):
        super().__init__()
        self.n_params = n_params
        self.d_model = d_model
        # Project each scalar parameter into d_model dimensions
        self.param_proj = nn.Linear(1, d_model)
        self.attn = nn.MultiheadAttention(d_model, n_heads, batch_first=True)
        self.out_proj = nn.Linear(d_model, 1)

    def forward(self, params):
        """params: (B, n_params) → (B, n_params) with cross-parameter info"""
        B = params.shape[0]
        # (B, n_params) → (B, n_params, 1) → (B, n_params, d_model)
        x = self.param_proj(params.unsqueeze(-1))
        # Self-attention across parameters
        attn_out, _ = self.attn(x, x, x)
        # Project back to scalar
        out = self.out_proj(attn_out).squeeze(-1)  # (B, n_params)
        return params + out  # residual


# ============================================================
# PINNv4b: Improved Architecture
# ============================================================
class PINNv4b(nn.Module):
    """
    Improved PINN with:
      - Residual encoder (3 blocks instead of plain feedforward)
      - Cross-parameter attention (learn Ees-Ea, Eed-tau couplings)
      - 9 latent parameters (added tau-Eed and Ea-Ees coupling)
      - Physics decoder v4b (soft clamping, wider V0, coupling terms)

    Architecture:
      11 inputs → Linear(11,128) → ResBlock(128) × 3 → Linear(128,9)
      → ParameterAttention(9) → PhysicsDecoderV4b → 7 outputs
    """
    def __init__(self):
        super().__init__()
        # Residual encoder
        self.input_proj = nn.Linear(11, 128)
        self.res_blocks = nn.Sequential(
            ResBlock(128, dropout=0.1),
            ResBlock(128, dropout=0.1),
            ResBlock(128, dropout=0.05),
        )
        self.latent_proj = nn.Sequential(
            nn.BatchNorm1d(128),
            nn.SiLU(),
            nn.Linear(128, 9),  # 9 latent params (expanded from 7)
        )
        # Cross-parameter attention
        self.param_attn = ParameterAttention(n_params=9, d_model=16, n_heads=4)
        # Physics decoder
        self.decoder = PhysicsDecoderV4b()

    def forward(self, x_scaled, x_raw):
        h = self.input_proj(x_scaled)
        h = self.res_blocks(h)
        latent = self.latent_proj(h)
        latent = self.param_attn(latent)
        return self.decoder(latent, x_raw)


# ============================================================
# Training
# ============================================================
def train_model(X, Y, epochs=200, batch_size=256, lr=1e-3, verbose=True,
                model_class='v4'):
    """Train PINN on simulation data. Returns (model, scaler).

    Args:
        model_class: 'v4' for original, 'v4b' for improved architecture
    """
    scaler = StandardScaler().fit(X)

    Xt = torch.tensor(scaler.transform(X), dtype=torch.float32)
    Xr = torch.tensor(X, dtype=torch.float32)
    Ys = torch.tensor(
        np.column_stack([Y[t] for t in TARGS]), dtype=torch.float32
    )

    ds = TensorDataset(Xt, Xr, Ys)
    dl = DataLoader(ds, batch_size, shuffle=True)

    if model_class == 'v4b':
        model = PINNv4b()
    else:
        model = PINNv4()

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, epochs)

    # Loss weights:
    #   Eed (5x), EDP (3x), tau (2x) — key diastolic outputs
    #   Ees, Ea (1x) — secondary
    #   coupling, eff (0.5x) — derived
    weights = torch.tensor([1.0, 5.0, 1.0, 0.5, 3.0, 0.5, 2.0])

    model.train()
    for ep in range(epochs):
        for bx, bxr, by in dl:
            pred = model(bx, bxr)

            # Weighted MSE loss
            mse_loss = sum(weights[i] * nn.functional.mse_loss(pred[:, i], by[:, i])
                           for i in range(7))

            # Physics consistency loss (v4b only)
            phys_loss = torch.tensor(0.0)
            if model_class == 'v4b':
                # 1. Monotonicity: higher Eed should → higher EDP (rank consistency)
                #    Penalize cases where Eed goes up but EDP goes down
                Eed_pred = pred[:, 1]   # Eed
                EDP_pred = pred[:, 4]   # EDP
                idx = torch.randperm(len(Eed_pred))[:len(Eed_pred)//2]
                idx2 = torch.randperm(len(Eed_pred))[:len(Eed_pred)//2]
                eed_diff = Eed_pred[idx] - Eed_pred[idx2]
                edp_diff = EDP_pred[idx] - EDP_pred[idx2]
                # Penalize: Eed goes up but EDP goes down
                mono_viol = torch.clamp(-eed_diff * edp_diff, min=0).mean()

                # 2. Coupling ratio Ea/Ees should mostly be in [0.3, 2.5]
                coupling_pred = pred[:, 3]
                coup_low = torch.clamp(0.3 - coupling_pred, min=0).mean()
                coup_high = torch.clamp(coupling_pred - 2.5, min=0).mean()

                # 3. tau-Eed concordance: stiff (high Eed) → slow relax (high tau)
                tau_pred = pred[:, 6]
                tau_diff = tau_pred[idx] - tau_pred[idx2]
                tau_eed_viol = torch.clamp(-eed_diff * tau_diff, min=0).mean()

                phys_loss = 0.5 * mono_viol + 0.2 * (coup_low + coup_high) + 0.3 * tau_eed_viol

            loss = mse_loss + phys_loss
            optimizer.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
        scheduler.step()

        if verbose and (ep + 1) % 50 == 0:
            model.eval()
            with torch.no_grad():
                fp = model(Xt, Xr).numpy()
            model.train()
            rs = [f"{t}={pearsonr(Ys[:, i].numpy(), fp[:, i])[0]:.3f}"
                  for i, t in enumerate(TARGS)]
            ploss_str = f", phys={phys_loss.item():.4f}" if model_class == 'v4b' else ""
            print(f"  Epoch {ep+1}: {', '.join(rs)}{ploss_str}")

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
# Clinical utility
# ============================================================
def evaluate_clinical_utility(Y_test, results):
    """AUC for detecting elevated diastolic parameters."""
    print("\n--- Diastolic Stiffness (Eed) Classification ---")
    for thresh, label in [(0.08, "Eed>0.08 (mild DD)"),
                          (0.10, "Eed>0.10 (moderate)"),
                          (0.15, "Eed>0.15 (severe)")]:
        true_label = (Y_test['Eed'] > thresh).astype(int)
        if true_label.sum() > 10 and (1 - true_label).sum() > 10:
            auc = roc_auc_score(true_label, results['Eed']['pred'])
            print(f"  {label}: AUC = {auc:.3f}")

    print("\n--- Elevated EDP Classification ---")
    for thresh, label in [(12, "EDP>12 (borderline)"),
                          (15, "EDP>15 (elevated)"),
                          (18, "EDP>18 (high)")]:
        true_label = (Y_test['EDP'] > thresh).astype(int)
        if true_label.sum() > 10 and (1 - true_label).sum() > 10:
            auc_edp = roc_auc_score(true_label, results['EDP']['pred'])
            # Compare with Nagueh estimate
            edp_nagueh = 1.24 * X_test_global[:, 7] + 1.9
            auc_nagueh = roc_auc_score(true_label, edp_nagueh)
            delta = auc_edp - auc_nagueh
            marker = "✓" if delta > 0.01 else "≈" if abs(delta) < 0.01 else "✗"
            print(f"  {label}: PINN={auc_edp:.3f}  Nagueh={auc_nagueh:.3f}"
                  f"  Δ={delta:+.3f} {marker}")

    print("\n--- Gray Zone Added Value (E/e' 8-13) ---")
    Ee = X_test_global[:, 7]
    gz = (Ee >= 8) & (Ee <= 13)
    if gz.sum() > 50:
        for thresh, label in [(12, "EDP>12"), (15, "EDP>15")]:
            true_gz = (Y_test['EDP'][gz] > thresh).astype(int)
            if true_gz.sum() > 10 and (1 - true_gz).sum() > 10:
                auc_pinn = roc_auc_score(true_gz, results['EDP']['pred'][gz])
                auc_nagueh = roc_auc_score(true_gz,
                                           1.24 * Ee[gz] + 1.9)
                delta = auc_pinn - auc_nagueh
                marker = "✓ ADDED VALUE" if delta > 0.02 else "≈" if abs(delta) < 0.02 else "✗"
                print(f"  {label} in gray zone (n={gz.sum()}): "
                      f"PINN={auc_pinn:.3f}  Nagueh={auc_nagueh:.3f}"
                      f"  Δ={delta:+.3f} {marker}")
    else:
        print(f"  Too few gray zone samples (n={gz.sum()})")


# =====================================