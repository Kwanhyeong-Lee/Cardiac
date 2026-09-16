"""
eICU Phase 3 v2: Enhanced Drug Response Validation
====================================================
개선사항:
  1. Baseline-adjusted relative change (% change)
  2. Dose-response stratification (tertiles)
  3. Energy Recovery Ratio (post/pre)
  4. Non-linear model (GradientBoosting + RandomForest)
  5. Subgroup analysis by baseline severity
  6. Pharmacological concordance with dose stratification
  7. Composite energy response score
"""
import pandas as pd, numpy as np, json, warnings, sys
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score
warnings.filterwarnings('ignore')

EXPECTED_EFFECTS = {
    'norepinephrine': {'category':'vasopressor','delta_sbp':'+','delta_co':'~','delta_svr':'+','delta_Ea':'+','delta_SW':'+','delta_hr':'~'},
    'dobutamine':     {'category':'inotrope','delta_sbp':'~','delta_co':'+','delta_svr':'-','delta_Ea':'-','delta_SW':'+','delta_hr':'+'},
    'milrinone':      {'category':'inotrope','delta_sbp':'-','delta_co':'+','delta_svr':'-','delta_Ea':'-','delta_SW':'~','delta_hr':'+'},
    'phenylephrine':  {'category':'vasopressor','delta_sbp':'+','delta_co':'-','delta_svr':'+','delta_Ea':'+','delta_SW':'~','delta_hr':'-'},
    'vasopressin':    {'category':'vasopressor','delta_sbp':'+','delta_co':'~','delta_svr':'+','delta_Ea':'+','delta_SW':'~','delta_hr':'~'},
    'nitroglycerin':  {'category':'vasodilator','delta_sbp':'-','delta_co':'~','delta_svr':'-','delta_Ea':'-','delta_SW':'-','delta_hr':'+'},
    'nitroprusside':  {'category':'vasodilator','delta_sbp':'-','delta_co':'+','delta_svr':'-','delta_Ea':'-','delta_SW':'~','delta_hr':'+'},
    'dopamine':       {'category':'vasopressor_inotrope','delta_sbp':'+','delta_co':'+','delta_svr':'~','delta_Ea':'~','delta_SW':'+','delta_hr':'+'},
    'epinephrine':    {'category':'vasopressor_inotrope','delta_sbp':'+','delta_co':'+','delta_svr':'~','delta_Ea':'~','delta_SW':'+','delta_hr':'+'},
}

def load_and_engineer(path):
    df = pd.read_csv(path)
    print(f"Loaded: {len(df)} episodes, {df['drug_class'].nunique()} drugs")
    
    # Compute energy if needed
    if 'pre_SW_J' not in df.columns:
        for pfx in ['pre','post']:
            co, sbp, hr = df[f'{pfx}_co'], df[f'{pfx}_sbp'], df[f'{pfx}_hr']
            sv = co*1000.0/hr
            esp = 0.9*sbp
            df[f'{pfx}_SW_J'] = esp*sv*0.000133322
            df[f'{pfx}_Ea'] = esp/sv
            df[f'{pfx}_CPO_W'] = df[f'{pfx}_SW_J']*hr/60
        df['delta_SW_J'] = df['post_SW_J'] - df['pre_SW_J']
        df['delta_CPO_W'] = df['post_CPO_W'] - df['pre_CPO_W']
        df['delta_Ea'] = df['post_Ea'] - df['pre_Ea']
    
    # ── NEW FEATURES ──
    # 1) Relative changes (% change from baseline)
    for col in ['SW_J','CPO_W','Ea']:
        base = df[f'pre_{col}'].replace(0, np.nan)
        df[f'pct_{col}'] = (df[f'post_{col}'] - df[f'pre_{col}']) / base * 100
    
    for col in ['co','sbp','hr','svr']:
        base = df[f'pre_{col}'].replace(0, np.nan)
        df[f'pct_{col}'] = (df[f'delta_{col}'] if f'delta_{col}' in df.columns 
                            else df[f'post_{col}'] - df[f'pre_{col}']) / base * 100
    
    # 2) Energy Recovery Ratio
    df['SW_ratio'] = df['post_SW_J'] / df['pre_SW_J'].replace(0, np.nan)
    df['CPO_ratio'] = df['post_CPO_W'] / df['pre_CPO_W'].replace(0, np.nan)
    
    # 3) Ventriculo-arterial coupling change
    df['pre_VA'] = df['pre_Ea']  # simplified: Ea as VA coupling proxy
    df['post_VA'] = df['post_Ea']
    df['delta_VA'] = df['post_VA'] - df['pre_VA']
    df['pct_VA'] = df['delta_VA'] / df['pre_VA'].replace(0, np.nan) * 100
    
    # 4) Composite Energy Response Score (z-score normalized)
    energy_cols = ['pct_SW_J','pct_CPO_W','pct_co']
    valid = df[energy_cols].dropna()
    if len(valid) > 10:
        for c in energy_cols:
            mu, sd = df[c].mean(), df[c].std()
            if sd > 0:
                df[f'z_{c}'] = (df[c] - mu) / sd
        z_cols = [f'z_{c}' for c in energy_cols]
        df['energy_response_score'] = df[z_cols].mean(axis=1)
    
    # 5) Dose tertiles per drug
    df['dose_tertile'] = np.nan
    for drug in df['drug_class'].unique():
        mask = df['drug_class'] == drug
        if mask.sum() >= 9:
            df.loc[mask, 'dose_tertile'] = pd.qcut(
                df.loc[mask, 'avg_rate'], q=3, labels=['low','mid','high'], duplicates='drop'
            )
    
    # 6) Baseline severity (pre_CPO_W quartile)
    df['severity_q'] = pd.qcut(df['pre_CPO_W'], q=4, labels=['Q1_sickest','Q2','Q3','Q4_healthiest'], duplicates='drop')
    
    # 7) Mortality
    df['mortality'] = (df['unitdischargestatus'] == 'Expired').astype(int)
    
    print(f"Deaths: {df['mortality'].sum()}/{len(df)} ({df['mortality'].mean()*100:.1f}%)")
    return df


def phase3a_enhanced(df):
    """Phase 3a enhanced: dose-stratified pharmacological concordance."""
    print(f"\n{'='*70}")
    print("PHASE 3a ENHANCED: DOSE-STRATIFIED PHARMACOLOGICAL CONCORDANCE")
    print(f"{'='*70}")
    
    concordance_total = 0
    concordance_correct = 0
    results = {}
    
    for drug in sorted(df['drug_class'].unique()):
        sub = df[df['drug_class'] == drug]
        n = len(sub)
        if n < 10: continue
        expected = EXPECTED_EFFECTS.get(drug, {})
        
        print(f"\n{'─'*60}")
        print(f"{drug.upper()} (n={n}, {expected.get('category','?')})")
        print(f"{'─'*60}")
        
        drug_result = {'n': n, 'overall': {}, 'by_dose': {}}
        
        # Overall concordance
        checks = []
        for metric, col in [('delta_sbp','delta_sbp'),('delta_co','delta_co'),
                            ('delta_hr','delta_hr'),('delta_svr','delta_svr'),
                            ('delta_SW','delta_SW_J'),('delta_Ea','delta_Ea')]:
            if col not in sub.columns: continue
            vals = sub[col].dropna()
            if len(vals) < 5: continue
            mean = vals.mean()
            t_stat, p_val = stats.ttest_1samp(vals, 0)
            exp = expected.get(metric, '?')
            
            if exp == '+': concordant = mean > 0
            elif exp == '-': concordant = mean < 0
            elif exp == '~': concordant = True
            else: concordant = None
            
            if concordant is not None:
                concordance_total += 1
                if concordant: concordance_correct += 1
                checks.append(concordant)
            
            sig = '***' if p_val<0.001 else '**' if p_val<0.01 else '*' if p_val<0.05 else 'ns'
            match = '✓' if concordant else ('✗' if concordant is False else '?')
            print(f"  {metric:12s}: {mean:+8.2f}  p={p_val:.2e} {sig}  exp={exp} {match}")
        
        drug_result['overall_concordance'] = sum(checks)/len(checks) if checks else None
        
        # Dose-stratified analysis
        for dose in ['low','mid','high']:
            dose_sub = sub[sub['dose_tertile'] == dose]
            if len(dose_sub) < 5: continue
            
            dose_checks = []
            dose_results = {}
            for metric, col in [('delta_sbp','delta_sbp'),('delta_co','delta_co'),
                                ('delta_SW','delta_SW_J')]:
                if col not in dose_sub.columns: continue
                vals = dose_sub[col].dropna()
                if len(vals) < 3: continue
                mean = vals.mean()
                exp = expected.get(metric, '?')
                if exp == '+': c = mean > 0
                elif exp == '-': c = mean < 0
                elif exp == '~': c = True
                else: c = None
                if c is not None: dose_checks.append(c)
                dose_results[metric] = float(mean)
            
            if dose_checks:
                dc = sum(dose_checks)/len(dose_checks)
                drug_result['by_dose'][dose] = {'concordance': dc, 'n': len(dose_sub), 'metrics': dose_results}
        
        # Print dose-response trend for key metrics
        if drug_result['by_dose']:
            print(f"  Dose-response:")
            for metric in ['delta_sbp','delta_co','delta_SW']:
                vals = []
                for dose in ['low','mid','high']:
                    if dose in drug_result['by_dose'] and metric in drug_result['by_dose'][dose].get('metrics',{}):
                        vals.append(f"{dose}={drug_result['by_dose'][dose]['metrics'][metric]:+.2f}")
                if vals:
                    print(f"    {metric}: {' → '.join(vals)}")
        
        results[drug] = drug_result
    
    overall = concordance_correct/concordance_total if concordance_total > 0 else 0
    print(f"\n{'='*70}")
    print(f"OVERALL CONCORDANCE: {concordance_correct}/{concordance_total} = {overall:.1%}")
    print(f"{'='*70}")
    return results, overall


def phase3b_enhanced(df):
    """Phase 3b enhanced: multi-model energy response → mortality."""
    print(f"\n{'='*70}")
    print("PHASE 3b ENHANCED: ENERGY RESPONSE → MORTALITY")
    print(f"{'='*70}")
    
    results = {}
    
    # ── 1. Per-mechanism analysis with relative changes ──
    print("\n[1] Relative Energy Change by Outcome")
    for mech in ['vasopressor','inotrope','vasodilator','vasopressor_inotrope']:
        sub = df[df['mechanism'] == mech]
        if len(sub) < 20 or sub['mortality'].sum() < 3: continue
        alive, dead = sub[sub['mortality']==0], sub[sub['mortality']==1]
        
        print(f"\n  {mech.upper()} (n={len(sub)}, deaths={len(dead)})")
        for col, label in [('pct_SW_J','%ΔSW'),('pct_CPO_W','%ΔCPO'),
                           ('SW_ratio','SW ratio'),('energy_response_score','E-score')]:
            if col not in sub.columns: continue
            a, d = alive[col].dropna(), dead[col].dropna()
            if len(a)<5 or len(d)<3: continue
            t, p = stats.ttest_ind(a, d, equal_var=False)
            cohens_d = (a.mean()-d.mean()) / np.sqrt((a.std()**2+d.std()**2)/2) if a.std()>0 else 0
            sig = '***' if p<0.001 else '**' if p<0.01 else '*' if p<0.05 else ''
            print(f"    {label:12s}: Alive {a.mean():+7.2f}  Expired {d.mean():+7.2f}  d={cohens_d:+.3f}  p={p:.3f} {sig}")
    
    # ── 2. Severity-stratified analysis ──
    print(f"\n[2] Severity-Stratified Energy Response")
    for sq in ['Q1_sickest','Q2','Q3','Q4_healthiest']:
        sub = df[df['severity_q'] == sq]
        if len(sub) < 20 or sub['mortality'].sum() < 2: continue
        alive, dead = sub[sub['mortality']==0], sub[sub['mortality']==1]
        if 'pct_SW_J' in sub.columns:
            a, d = alive['pct_SW_J'].dropna(), dead['pct_SW_J'].dropna()
            if len(a)>=5 and len(d)>=2:
                t, p = stats.ttest_ind(a, d, equal_var=False)
                print(f"  {sq}: Alive %ΔSW={a.mean():+.1f}%  Expired %ΔSW={d.mean():+.1f}%  p={p:.3f}  (n={len(sub)}, d={len(dead)})")
    
    # ── 3. Multi-model mortality prediction ──
    print(f"\n[3] Multi-Model Mortality Prediction")
    
    # Feature sets
    feature_sets = {
        'v1_raw_delta': ['delta_SW_J','delta_CPO_W','delta_Ea','delta_co','delta_sbp','delta_hr'],
        'v2_pct_change': ['pct_SW_J','pct_CPO_W','pct_co','pct_sbp','pct_hr','pct_Ea'],
        'v3_ratio+baseline': ['SW_ratio','CPO_ratio','pre_SW_J','pre_CPO_W','pre_Ea'],
        'v4_comprehensive': ['pct_SW_J','pct_CPO_W','pct_co','pct_Ea','SW_ratio',
                             'pre_SW_J','pre_CPO_W','pre_Ea','pre_co','pre_sbp','pre_hr'],
    }
    
    if 'energy_response_score' in df.columns:
        feature_sets['v5_e_score+base'] = ['energy_response_score','pre_SW_J','pre_CPO_W','pre_Ea','pre_co']
    
    models = {
        'LogReg': LogisticRegression(max_iter=1000, class_weight='balanced', C=0.1),
        'GBM': GradientBoostingClassifier(n_estimators=100, max_depth=3, learning_rate=0.05,
                                           subsample=0.8, min_samples_leaf=10, random_state=42),
        'RF': RandomForestClassifier(n_estimators=200, max_depth=4, min_samples_leaf=10,
                                      class_weight='balanced', random_state=42),
    }
    
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    best_auc = 0
    best_config = ""
    
    for fname, fcols in feature_sets.items():
        avail = [c for c in fcols if c in df.columns]
        if len(avail) < 3: continue
        
        tmp = df[avail + ['mortality']].dropna()
        X, y = tmp[avail], tmp['mortality']
        if y.sum() < 5 or len(y) < 30: continue
        
        scaler = StandardScaler()
        X_s = scaler.fit_transform(X)
        
        print(f"\n  {fname} ({len(avail)} features, n={len(X)}, deaths={y.sum()}):")
        for mname, model in models.items():
            try:
                aucs = cross_val_score(model, X_s, y, cv=cv, scoring='roc_auc')
                mean_auc = aucs.mean()
                print(f"    {mname:8s}: AUC = {mean_auc:.3f} ± {aucs.std():.3f}")
                if mean_auc > best_auc:
                    best_auc = mean_auc
                    best_config = f"{fname} + {mname}"
            except Exception as e:
                print(f"    {mname:8s}: Error - {e}")
    
    print(f"\n  ★ Best: {best_config} → AUC {best_auc:.3f}")
    results['best_auc'] = best_auc
    results['best_config'] = best_config
    
    # ── 4. Energy Responder vs Non-Responder survival ──
    print(f"\n[4] Energy Responder Classification")
    if 'pct_SW_J' in df.columns:
        # Define "energy responder" = top tertile of %ΔSW improvement
        df['e_responder'] = (df['pct_SW_J'] > df['pct_SW_J'].quantile(0.67)).astype(int)
        resp = df[df['e_responder']==1]
        nonresp = df[df['e_responder']==0]
        
        mort_resp = resp['mortality'].mean()
        mort_nonresp = nonresp['mortality'].mean()
        
        # Fisher's exact test
        a = resp['mortality'].sum()
        b = len(resp) - a
        c = nonresp['mortality'].sum()
        d_count = len(nonresp) - c
        odds_ratio, p_fisher = stats.fisher_exact([[a, b], [c, d_count]])
        
        print(f"  Energy Responders (top 33% %ΔSW):")
        print(f"    Responders:     mortality {mort_resp:.1%} ({a}/{len(resp)})")
        print(f"    Non-responders: mortality {mort_nonresp:.1%} ({c}/{len(nonresp)})")
        print(f"    OR = {odds_ratio:.3f}, p(Fisher) = {p_fisher:.4f}")
        
        results['responder_mortality'] = float(mort_resp)
        results['nonresponder_mortality'] = float(mort_nonresp)
        results['responder_OR'] = float(odds_ratio)
        results['responder_p'] = float(p_fisher)
    
    # ── 5. Dose-response mortality interaction ──
    print(f"\n[5] Dose-Response Mortality Interaction")
    for mech in ['vasopressor','inotrope']:
        sub = df[(df['mechanism']==mech) & df['dose_tertile'].notna()]
        if len(sub) < 30: continue
        print(f"  {mech}:")
        for dose in ['low','mid','high']:
            ds = sub[sub['dose_tertile']==dose]
            if len(ds) < 5: continue
            m = ds['mortality'].mean()
            sw = ds['pct_SW_J'].mean() if 'pct_SW_J' in ds.columns else np.nan
            print(f"    {dose:4s}: n={len(ds):3d}, mort={m:.1%}, %ΔSW={sw:+.1f}%")
    
    return results


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else 'eicu_drug_response.csv'
    df = load_and_engineer(path)
    
    pharm_results, concordance = phase3a_enhanced(df)
    mortality_results = phase3b_enhanced(df)
    
    # Save comprehensive results
    output = {
        'version': 'v2_enhanced',
        'n_episodes': len(df),
        'n_deaths': int(df['mortality'].sum()),
        'mortality_rate': float(df['mortality'].mean()),
        'pharmacological_concordance': concordance,
        'best_mortality_auc': mortality_results.get('best_auc'),
        'best_config': mortality_results.get('best_config'),
        'responder_analysis': {
            'responder_mortality': mortality_results.get('responder_mortality'),
            'nonresponder_mortality': mortality_results.get('nonresponder_mortality'),
            'odds_ratio': mortality_results.get('responder_OR'),
            'p_value': mortality_results.get('responder_p'),
        },
        'drug_concordance': {k: v.get('overall_concordance') for k, v in pharm_results.items()},
    }
    
    out_path = path.replace('.csv', '_v2_results.json')
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\nSaved: {out_path}")


if __name__ == '__main__':
    main()
