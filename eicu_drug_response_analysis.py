"""
eICU Phase 3: Drug Response Pattern Validation
================================================
BigQuery에서 eicu_drug_response.csv를 추출한 후 실행:
  python eicu_drug_response_analysis.py

검증 목표:
  1. 약물별 Hamiltonian 에너지 변화 방향이 약리학적 예측과 일치하는지
  2. pH-PINN의 δH(drug) perturbation 모델 validation
  3. 에너지 변화 패턴이 사망률과 연관되는지
"""
import pandas as pd, numpy as np, json, warnings
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import StandardScaler
warnings.filterwarnings('ignore')

# ============================================================
# Expected pharmacological effects (ground truth)
# ============================================================
EXPECTED_EFFECTS = {
    'norepinephrine': {
        'category': 'vasopressor',
        'delta_sbp': '+',   # ↑ afterload (α1)
        'delta_co': '~',    # ↔ or slight ↑ (β1)
        'delta_svr': '+',   # ↑ SVR (α1 dominant)
        'delta_Ea': '+',    # ↑ arterial elastance
        'delta_SW': '+',    # ↑ stroke work (↑ afterload)
        'delta_hr': '~',    # ↔ or reflex ↓
    },
    'dobutamine': {
        'category': 'inotrope',
        'delta_sbp': '~',   # ↔ or slight ↑
        'delta_co': '+',    # ↑↑ CO (β1 inotropy + β2 vasodilation)
        'delta_svr': '-',   # ↓ SVR (β2)
        'delta_Ea': '-',    # ↓ arterial elastance
        'delta_SW': '+',    # ↑ stroke work (↑ contractility)
        'delta_hr': '+',    # ↑ HR (β1)
    },
    'milrinone': {
        'category': 'inotrope',
        'delta_sbp': '-',   # ↓ (vasodilation)
        'delta_co': '+',    # ↑ CO (inotropy + afterload reduction)
        'delta_svr': '-',   # ↓ SVR
        'delta_Ea': '-',    # ↓ arterial elastance
        'delta_SW': '~',    # ↔ (↑ SV but ↓ ESP)
        'delta_hr': '+',    # slight ↑
    },
    'phenylephrine': {
        'category': 'vasopressor',
        'delta_sbp': '+',   # ↑↑ (pure α1)
        'delta_co': '-',    # ↓ CO (reflex bradycardia + ↑ afterload)
        'delta_svr': '+',   # ↑↑ SVR
        'delta_Ea': '+',    # ↑↑ arterial elastance
        'delta_SW': '~',    # ↔
        'delta_hr': '-',    # ↓ (baroreceptor reflex)
    },
    'vasopressin': {
        'category': 'vasopressor',
        'delta_sbp': '+',   # ↑ (V1 receptor)
        'delta_co': '~',    # ↔
        'delta_svr': '+',   # ↑ SVR
        'delta_Ea': '+',    # ↑ arterial elastance
        'delta_SW': '~',    # ↔
        'delta_hr': '~',    # ↔ or slight ↓
    },
    'nitroglycerin': {
        'category': 'vasodilator',
        'delta_sbp': '-',   # ↓ (venodilation → preload ↓)
        'delta_co': '~',    # ↔ or slight ↓
        'delta_svr': '-',   # ↓ SVR (modest)
        'delta_Ea': '-',    # ↓ arterial elastance
        'delta_SW': '-',    # ↓ (↓ preload)
        'delta_hr': '+',    # reflex ↑
    },
    'nitroprusside': {
        'category': 'vasodilator',
        'delta_sbp': '-',   # ↓↓ (arterial + venous)
        'delta_co': '+',    # ↑ CO (afterload reduction)
        'delta_svr': '-',   # ↓↓ SVR
        'delta_Ea': '-',    # ↓↓ arterial elastance
        'delta_SW': '~',    # ↔
        'delta_hr': '+',    # reflex ↑
    },
    'dopamine': {
        'category': 'vasopressor_inotrope',
        'delta_sbp': '+',   # ↑ (dose-dependent)
        'delta_co': '+',    # ↑ CO
        'delta_svr': '~',   # dose-dependent
        'delta_Ea': '~',    # dose-dependent
        'delta_SW': '+',    # ↑
        'delta_hr': '+',    # ↑
    },
    'epinephrine': {
        'category': 'vasopressor_inotrope',
        'delta_sbp': '+',   # ↑ (β1+α1)
        'delta_co': '+',    # ↑↑ CO (strong β1)
        'delta_svr': '~',   # ↔ (α1 + β2 balance)
        'delta_Ea': '~',    # ↔
        'delta_SW': '+',    # ↑↑
        'delta_hr': '+',    # ↑↑
    },
}


def load_data(path='eicu_drug_response.csv'):
    df = pd.read_csv(path)
    print(f"Loaded: {len(df)} drug-response episodes")
    print(f"Drugs: {df['drug_class'].value_counts().to_dict()}")
    print(f"Mechanisms: {df['mechanism'].value_counts().to_dict()}")
    return df


def compute_energy_if_needed(df):
    """Compute energy columns if not already present from BigQuery."""
    if 'pre_SW_J' not in df.columns:
        for prefix in ['pre', 'post']:
            co = df[f'{prefix}_co']
            sbp = df[f'{prefix}_sbp']
            hr = df[f'{prefix}_hr']
            sv = co * 1000.0 / hr
            esp = 0.9 * sbp
            df[f'{prefix}_SW_J'] = esp * sv * 0.000133322
            df[f'{prefix}_Ea'] = esp / sv
            df[f'{prefix}_CPO_W'] = df[f'{prefix}_SW_J'] * hr / 60

        df['delta_SW_J'] = df['post_SW_J'] - df['pre_SW_J']
        df['delta_CPO_W'] = df['post_CPO_W'] - df['pre_CPO_W']
        df['delta_Ea'] = df['post_Ea'] - df['pre_Ea']
    return df


def validate_pharmacology(df):
    """Phase 3a: 약물별 혈역학 변화가 약리학적 예측과 일치하는지 검증."""
    print(f"\n{'='*70}")
    print("PHASE 3a: PHARMACOLOGICAL CONSISTENCY VALIDATION")
    print(f"{'='*70}")

    results = {}
    concordance_total = 0
    concordance_correct = 0

    for drug in sorted(df['drug_class'].unique()):
        sub = df[df['drug_class'] == drug]
        n = len(sub)
        if n < 5:
            print(f"\n{drug}: n={n} (too few, skipped)")
            continue

        expected = EXPECTED_EFFECTS.get(drug, {})
        print(f"\n{'─'*50}")
        print(f"{drug.upper()} (n={n}, mechanism: {expected.get('category','?')})")
        print(f"{'─'*50}")

        drug_result = {'n': n, 'metrics': {}}
        checks = []

        for metric, col in [('delta_sbp','delta_sbp'), ('delta_co','delta_co'),
                            ('delta_hr','delta_hr'), ('delta_svr','delta_svr'),
                            ('delta_SW','delta_SW_J'), ('delta_Ea','delta_Ea')]:
            if col not in sub.columns:
                continue
            vals = sub[col].dropna()
            if len(vals) < 5:
                continue

            mean = vals.mean()
            std = vals.std()
            t_stat, p_val = stats.ttest_1samp(vals, 0)
            exp = expected.get(metric, '?')

            # Concordance check
            if exp == '+':
                concordant = mean > 0
            elif exp == '-':
                concordant = mean < 0
            elif exp == '~':
                concordant = True  # neutral = always concordant
            else:
                concordant = None

            if concordant is not None:
                concordance_total += 1
                if concordant:
                    concordance_correct += 1
                checks.append(concordant)

            arrow = '↑' if mean > 0 else '↓'
            sig = '***' if p_val < 0.001 else '**' if p_val < 0.01 else '*' if p_val < 0.05 else 'ns'
            match = '✓' if concordant else ('✗' if concordant is False else '?')

            print(f"  {metric:12s}: {mean:+8.2f} ± {std:7.2f}  {arrow} p={p_val:.2e} {sig}  expected={exp} {match}")
            drug_result['metrics'][metric] = {
                'mean': float(mean), 'std': float(std), 'p': float(p_val),
                'expected': exp, 'concordant': concordant
            }

        drug_result['concordance'] = sum(checks) / len(checks) if checks else None
        results[drug] = drug_result

    overall = concordance_correct / concordance_total if concordance_total > 0 else 0
    print(f"\n{'='*70}")
    print(f"OVERALL PHARMACOLOGICAL CONCORDANCE: {concordance_correct}/{concordance_total} = {overall:.1%}")
    print(f"{'='*70}")

    return results, overall


def energy_response_mortality(df):
    """Phase 3b: 에너지 변화 패턴 → 사망률 연관."""
    print(f"\n{'='*70}")
    print("PHASE 3b: ENERGY RESPONSE → MORTALITY ASSOCIATION")
    print(f"{'='*70}")

    df['mortality'] = (df['unitdischargestatus'] == 'Expired').astype(int)

    for mech in ['vasopressor', 'inotrope', 'vasodilator', 'vasopressor_inotrope']:
        sub = df[df['mechanism'] == mech]
        if len(sub) < 20 or sub['mortality'].sum() < 3:
            print(f"\n{mech}: n={len(sub)}, deaths={sub['mortality'].sum()} (insufficient)")
            continue

        alive = sub[sub['mortality'] == 0]
        dead = sub[sub['mortality'] == 1]

        print(f"\n{mech.upper()} (n={len(sub)}, deaths={dead.shape[0]})")
        for col, label in [('delta_SW_J','ΔSW'), ('delta_CPO_W','ΔCPO'), ('delta_co','ΔCO'), ('delta_Ea','ΔEa')]:
            if col not in sub.columns:
                continue
            a_vals = alive[col].dropna()
            d_vals = dead[col].dropna()
            if len(a_vals) < 5 or len(d_vals) < 3:
                continue
            t, p = stats.ttest_ind(a_vals, d_vals)
            print(f"  {label}: Alive {a_vals.mean():+.4f}  Expired {d_vals.mean():+.4f}  p={p:.3f}")

    # Combined model: energy response predicts mortality
    energy_cols = ['delta_SW_J', 'delta_CPO_W', 'delta_Ea', 'delta_co', 'delta_sbp', 'delta_hr']
    avail = [c for c in energy_cols if c in df.columns]
    X = df[avail].dropna()
    y = df.loc[X.index, 'mortality']

    if y.sum() >= 5 and len(y) >= 30:
        scaler = StandardScaler()
        X_s = scaler.fit_transform(X)
        model = LogisticRegression(max_iter=1000, class_weight='balanced')
        aucs = cross_val_score(model, X_s, y, cv=5, scoring='roc_auc')
        print(f"\nDrug-response energy → Mortality AUC: {aucs.mean():.3f} ± {aucs.std():.3f}")
        return float(aucs.mean())
    return None


def main():
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else 'eicu_drug_response.csv'
    df = load_data(path)
    df = compute_energy_if_needed(df)

    pharm_results, concordance = validate_pharmacology(df)
    auc = energy_response_mortality(df)

    # Save
    output = {
        'n_episodes': len(df),
        'drugs': {k: v['n'] for k, v in pharm_results.items()},
        'pharmacological_concordance': concordance,
        'drug_details': pharm_results,
        'response_mortality_auc': auc,
    }
    out_path = path.replace('.csv', '_results.json')
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\nSaved: {out_path}")


if __name__ == '__main__':
    main()
