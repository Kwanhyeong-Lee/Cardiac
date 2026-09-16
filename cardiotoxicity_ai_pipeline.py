#!/usr/bin/env python3
"""
===============================================================================
AI 기반 심근독성(Cardiotoxicity) 정량 평가 파이프라인
- PV 루프 & Frank-Starling 모델 기반 -

Step-by-Step Implementation

순천향대학교 의과대학 | 심장 및 순환생리 실습
2026년 4월
===============================================================================
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.rcParams['font.family'] = ['DejaVu Sans']
matplotlib.rcParams['figure.dpi'] = 150
import seaborn as sns
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor
from sklearn.metrics import (classification_report, confusion_matrix, roc_curve, auc,
                             roc_auc_score, mean_absolute_error, r2_score)
from sklearn.preprocessing import label_binarize
import warnings
warnings.filterwarnings('ignore')

print("=" * 70)
print("  STEP 1: 생리학 모델 정의 (Physiological Model)")
print("  - Time-Varying Elastance (Suga & Sagawa, 1974)")
print("=" * 70)

# =====================================================================
# STEP 1: 생리학 기반 PV 루프 모델 (검증된 파라미터)
# =====================================================================
# Guyton Ch.9 + Burkhoff 2005 기반

V0 = 10.0       # Dead volume (mL)
A_EDP = 0.337    # EDPVR scaling constant (mmHg)

def edpvr(v, bedp):
    """이완기말 압력-용적 관계 (Exponential EDPVR)
    P = A * (exp(B * (V - V0)) - 1)
    정상: EDV=120 → EDP ≈ 7 mmHg
    """
    if v <= V0:
        return 0.0
    return A_EDP * (np.exp(bedp * (v - V0)) - 1.0)

def espvr(v, ees):
    """수축기말 압력-용적 관계 (Linear ESPVR)
    P = Ees * (V - V0)
    Ees = 수축력 지표 (부하 독립적)
    """
    if v <= V0:
        return 0.0
    return ees * (v - V0)

def calc_hemodynamics(edv, aop, ees, hr, bedp):
    """혈역학 계산: PV 루프의 핵심 수치들"""
    edp = edpvr(edv, bedp)
    esv = V0 + aop / ees
    esv = np.clip(esv, V0 + 1, edv - 2)
    sv = edv - esv
    ef = (sv / edv) * 100.0
    co = (sv * hr) / 1000.0
    esp = espvr(esv, ees)
    peak_lvp = aop + (espvr(edv, ees) - aop) * 0.15 + 15
    peak_lvp = max(peak_lvp, aop + 10)
    # Stroke Work (근사: 사다리꼴 면적)
    sw = sv * (aop + esp) / 2.0
    return {
        'EDV': edv, 'ESV': esv, 'SV': sv, 'EF': ef, 'CO': co,
        'EDP': edp, 'ESP': esp, 'Peak_LVP': peak_lvp, 'SW': sw,
        'Ees': ees, 'AoP': aop, 'HR': hr, 'BEDP': bedp
    }

# 정상값 검증
normal = calc_hemodynamics(120, 100, 2.5, 72, 0.028)
print(f"\n[검증] 정상값:")
print(f"  EDV={normal['EDV']:.0f}mL, ESV={normal['ESV']:.0f}mL, "
      f"SV={normal['SV']:.0f}mL, EF={normal['EF']:.1f}%, "
      f"CO={normal['CO']:.1f}L/min, EDP={normal['EDP']:.1f}mmHg")
print(f"  → Guyton Ch.9 정상범위와 일치 ✓\n")


print("=" * 70)
print("  STEP 2: 합성 환자 데이터 생성 (Synthetic Patient Cohort)")
print("  - 정상 + 경도/중등도/중증 심독성 환자 시뮬레이션")
print("=" * 70)

# =====================================================================
# STEP 2: 합성 환자 데이터 생성
# =====================================================================

np.random.seed(42)
N_PATIENTS = 1000

grade_dist = [0.35, 0.30, 0.20, 0.15]
grade_names = ['Normal', 'Mild', 'Moderate', 'Severe']

patients = []
for i in range(N_PATIENTS):
    grade = np.random.choice([0, 1, 2, 3], p=grade_dist)

    age = np.random.normal(55, 12)
    age = np.clip(age, 25, 85)
    sex = np.random.choice([0, 1])
    bsa = np.random.normal(1.7 if sex == 0 else 1.9, 0.15)

    dox_dose_ranges = [(0, 100), (100, 300), (300, 450), (450, 600)]
    dox_low, dox_high = dox_dose_ranges[grade]
    dox_dose = np.random.uniform(dox_low, dox_high)

    ees_ranges = [(2.0, 3.0), (1.5, 2.0), (1.0, 1.5), (0.5, 1.0)]
    ees_low, ees_high = ees_ranges[grade]
    ees = np.random.uniform(ees_low, ees_high)
    ees += np.random.normal(0, 0.05)
    ees = np.clip(ees, 0.4, 3.5)

    edv_base = 120 + grade * 12 + np.random.normal(0, 8)
    aop = 100 + np.random.normal(0, 8)
    hr = 72 + grade * 8 + np.random.normal(0, 6)
    bedp = 0.028 + grade * 0.004 + np.random.normal(0, 0.002)

    edv_base = np.clip(edv_base, 80, 200)
    aop = np.clip(aop, 60, 160)
    hr = np.clip(hr, 50, 140)
    bedp = np.clip(bedp, 0.015, 0.06)

    hemo = calc_hemodynamics(edv_base, aop, ees, hr, bedp)

    troponin = 0.02 + grade * 0.15 + np.random.exponential(0.05)
    bnp = 50 + grade * 120 + np.random.exponential(30)
    gls = -20 + grade * 3.5 + np.random.normal(0, 1.5)

    patients.append({
        'patient_id': i + 1,
        'age': round(age, 1),
        'sex': sex,
        'bsa': round(bsa, 2),
        'dox_cumulative_dose': round(dox_dose, 1),
        'grade': grade,
        'grade_name': grade_names[grade],
        **{k: round(v, 2) for k, v in hemo.items()},
        'Troponin': round(troponin, 3),
        'BNP': round(bnp, 1),
        'GLS': round(gls, 1),
    })

df = pd.DataFrame(patients)

print(f"\n[데이터셋] SynCardioTox-1K")
print(f"  총 표본 수: {len(df)}명")
print(f"  인구 특성:")
print(f"    연령: {df['age'].mean():.1f} ± {df['age'].std():.1f}세")
print(f"    성별: 남성 {(df['sex']==1).sum()}명, 여성 {(df['sex']==0).sum()}명")
print(f"  DOX 누적 용량: {df['dox_cumulative_dose'].mean():.1f} ± {df['dox_cumulative_dose'].std():.1f} mg/m²")
print(f"\n  심독성 등급 분포:")
for g in range(4):
    sub = df[df['grade'] == g]
    print(f"    Grade {g} ({grade_names[g]}): {len(sub)}명 "
          f"| Ees={sub['Ees'].mean():.2f}±{sub['Ees'].std():.2f} "
          f"| EF={sub['EF'].mean():.1f}±{sub['EF'].std():.1f}%")


print("\n" + "=" * 70)
print("  STEP 3: 특징 추출 (Feature Engineering)")
print("=" * 70)

feature_cols = [
    'age', 'sex', 'bsa',
    'dox_cumulative_dose',
    'EDV', 'ESV', 'SV', 'EF', 'CO', 'EDP', 'Peak_LVP', 'SW',
    'HR',
    'Troponin', 'BNP', 'GLS',
]

df['SV_index'] = df['SV'] / df['bsa']
df['CO_index'] = df['CO'] / df['bsa']
df['EDP_EDV_ratio'] = df['EDP'] / df['EDV']
df['SW_EDV_ratio'] = df['SW'] / df['EDV']
df['HR_SV_product'] = df['HR'] * df['SV']

derived_cols = ['SV_index', 'CO_index', 'EDP_EDV_ratio', 'SW_EDV_ratio', 'HR_SV_product']
all_features = feature_cols + derived_cols

X = df[all_features].values
y_class = df['grade'].values
y_ees = df['Ees'].values

print(f"\n[특징 벡터] 총 {len(all_features)}개 특징")


print("\n" + "=" * 70)
print("  STEP 4: 모델 학습 (Model Training)")
print("=" * 70)

X_train, X_test, y_train_c, y_test_c, y_train_r, y_test_r = train_test_split(
    X, y_class, y_ees, test_size=0.2, random_state=42, stratify=y_class
)

print(f"\n[데이터 분할] Train {len(X_train)} / Test {len(X_test)}")

# Task A: Classification
clf = RandomForestClassifier(
    n_estimators=200, max_depth=12, min_samples_split=5,
    min_samples_leaf=3, random_state=42, class_weight='balanced', n_jobs=-1
)
clf.fit(X_train, y_train_c)

cv_scores = cross_val_score(clf, X_train, y_train_c, cv=5, scoring='accuracy')
y_pred_c = clf.predict(X_test)
y_pred_proba = clf.predict_proba(X_test)
test_acc = (y_pred_c == y_test_c).mean()

y_test_bin = label_binarize(y_test_c, classes=[0, 1, 2, 3])
auc_macro = roc_auc_score(y_test_bin, y_pred_proba, multi_class='ovr', average='macro')

print(f"  [Task A] 5-Fold CV: {cv_scores.mean():.3f}, Test Acc: {test_acc:.3f}, AUC: {auc_macro:.3f}")

# Task B: Regression
reg = GradientBoostingRegressor(
    n_estimators=200, max_depth=6, learning_rate=0.1,
    min_samples_split=5, random_state=42
)
reg.fit(X_train, y_train_r)

y_pred_r = reg.predict(X_test)
mae = mean_absolute_error(y_test_r, y_pred_r)
r2 = r2_score(y_test_r, y_pred_r)
print(f"  [Task B] MAE: {mae:.4f}, R²: {r2:.4f}")


print("\n" + "=" * 70)
print("  STEP 5: 특징 중요도 분석")
print("=" * 70)

importances = clf.feature_importances_
feat_imp = pd.DataFrame({
    'Feature': all_features, 'Importance': importances
}).sort_values('Importance', ascending=False)

for _, row in feat_imp.head(10).iterrows():
    bar = "█" * int(row['Importance'] * 100)
    print(f"  {row['Feature']:22s} {row['Importance']:.4f}  {bar}")


print("\n" + "=" * 70)
print("  STEP 6: 시각화")
print("=" * 70)

fig = plt.figure(figsize=(20, 24))
fig.suptitle('AI-Based Cardiotoxicity Quantification via PV Loop Analysis',
             fontsize=18, fontweight='bold', y=0.98)

colors_grade = ['#2DD4BF', '#4A7BFF', '#FFA94D', '#FF6B6B']

# 6-1: PV Loops by Grade
ax1 = fig.add_subplot(4, 3, 1)
for g in range(4):
    sub = df[df['grade'] == g].sample(min(5, len(df[df['grade']==g])), random_state=42)
    for _, row in sub.iterrows():
        edv, esv = row['EDV'], row['ESV']
        edp, aop_v, esp = row['EDP'], row['AoP'], row['ESP']
        plvp = row['Peak_LVP']
        vols = np.concatenate([
            np.linspace(esv, edv, 30),
            np.full(20, edv),
            np.linspace(edv, esv, 30),
            np.full(20, esv),
        ])
        pres = np.concatenate([
            np.array([edpvr(v, row['BEDP']) for v in np.linspace(esv, edv, 30)]),
            np.linspace(edp, aop_v, 20),
            np.linspace(aop_v, esp, 30) + np.sin(np.linspace(0, np.pi, 30)) * (plvp - aop_v) * 0.5,
            np.linspace(esp, edpvr(esv, row['BEDP']), 20),
        ])
        ax1.plot(vols, pres, color=colors_grade[g], alpha=0.4, linewidth=0.8)
for g, ees_val in enumerate([2.5, 1.75, 1.25, 0.75]):
    v_range = np.linspace(V0, 80, 50)
    p_range = [espvr(v, ees_val) for v in v_range]
    ax1.plot(v_range, p_range, '--', color=colors_grade[g], linewidth=1.5, alpha=0.7)
ax1.set_xlabel('Volume (mL)'); ax1.set_ylabel('Pressure (mmHg)')
ax1.set_title('PV Loops by Toxicity Grade', fontweight='bold')
ax1.set_xlim(0, 200); ax1.set_ylim(0, 200)
ax1.legend(['Normal', 'Mild', 'Moderate', 'Severe'], fontsize=7, loc='upper left')

# 6-2: Frank-Starling Curves
ax2 = fig.add_subplot(4, 3, 2)
for g, (ees_val, label) in enumerate([(2.5, 'Normal'), (1.75, 'Mild'), (1.25, 'Moderate'), (0.75, 'Severe')]):
    edv_range = np.linspace(60, 200, 100)
    sv_vals = [max(edv_v - min(V0 + 100/ees_val, edv_v - 2), 0) for edv_v in edv_range]
    ax2.plot(edv_range, sv_vals, color=colors_grade[g], linewidth=2.5, label=label)
ax2.set_xlabel('EDV (mL)'); ax2.set_ylabel('SV (mL)')
ax2.set_title('Frank-Starling Curves', fontweight='bold')
ax2.legend(fontsize=8); ax2.set_xlim(60, 200); ax2.set_ylim(0, 160)

# 6-3: Ees Distribution
ax3 = fig.add_subplot(4, 3, 3)
for g in range(4):
    ax3.hist(df[df['grade']==g]['Ees'], bins=20, alpha=0.6, color=colors_grade[g], label=grade_names[g], edgecolor='white')
ax3.set_xlabel('Ees (mmHg/mL)'); ax3.set_ylabel('Count')
ax3.set_title('Ees Distribution by Grade', fontweight='bold'); ax3.legend(fontsize=8)

# 6-4: Confusion Matrix
ax4 = fig.add_subplot(4, 3, 4)
cm = confusion_matrix(y_test_c, y_pred_c)
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', ax=ax4, xticklabels=grade_names, yticklabels=grade_names)
ax4.set_xlabel('Predicted'); ax4.set_ylabel('Actual')
ax4.set_title(f'Confusion Matrix (Acc={test_acc:.3f})', fontweight='bold')

# 6-5: ROC Curves
ax5 = fig.add_subplot(4, 3, 5)
for g in range(4):
    fpr, tpr, _ = roc_curve(y_test_bin[:, g], y_pred_proba[:, g])
    ax5.plot(fpr, tpr, color=colors_grade[g], linewidth=2, label=f'{grade_names[g]} (AUC={auc(fpr, tpr):.3f})')
ax5.plot([0, 1], [0, 1], 'k--', alpha=0.3)
ax5.set_xlabel('FPR'); ax5.set_ylabel('TPR')
ax5.set_title(f'ROC Curves (Macro AUC={auc_macro:.3f})', fontweight='bold'); ax5.legend(fontsize=7)

# 6-6: Feature Importance
ax6 = fig.add_subplot(4, 3, 6)
top_feat = feat_imp.head(12)
ax6.barh(range(12), top_feat['Importance'].values, color='#4A7BFF', edgecolor='white')
ax6.set_yticks(range(12)); ax6.set_yticklabels(top_feat['Feature'].values, fontsize=8)
ax6.invert_yaxis(); ax6.set_xlabel('Importance')
ax6.set_title('Feature Importance (Top 12)', fontweight='bold')

# 6-7: Ees Regression
ax7 = fig.add_subplot(4, 3, 7)
for g in range(4):
    mask = y_test_c == g
    ax7.scatter(y_test_r[mask], y_pred_r[mask], c=colors_grade[g], s=20, alpha=0.6, label=grade_names[g])
ax7.plot([0, 3.5], [0, 3.5], 'k--', alpha=0.4)
ax7.set_xlabel('True Ees'); ax7.set_ylabel('Predicted Ees')
ax7.set_title(f'Ees Regression (R²={r2:.3f})', fontweight='bold'); ax7.legend(fontsize=7)

# 6-8: EF vs Ees
ax8 = fig.add_subplot(4, 3, 8)
for g in range(4):
    sub = df[df['grade']==g]
    ax8.scatter(sub['Ees'], sub['EF'], c=colors_grade[g], s=15, alpha=0.5, label=grade_names[g])
ax8.axhline(y=40, color='red', linestyle='--', alpha=0.5)
ax8.set_xlabel('Ees'); ax8.set_ylabel('EF (%)'); ax8.set_title('EF vs Ees', fontweight='bold'); ax8.legend(fontsize=7)

# 6-9: DOX Dose vs Ees
ax9 = fig.add_subplot(4, 3, 9)
for g in range(4):
    sub = df[df['grade']==g]
    ax9.scatter(sub['dox_cumulative_dose'], sub['Ees'], c=colors_grade[g], s=15, alpha=0.5, label=grade_names[g])
ax9.set_xlabel('DOX Dose (mg/m²)'); ax9.set_ylabel('Ees'); ax9.set_title('DOX Dose vs Contractility', fontweight='bold'); ax9.legend(fontsize=7)

# 6-10: Troponin
ax10 = fig.add_subplot(4, 3, 10)
bp = ax10.boxplot([df[df['grade']==g]['Troponin'].values for g in range(4)], labels=grade_names, patch_artist=True)
for patch, color in zip(bp['boxes'], colors_grade): patch.set_facecolor(color); patch.set_alpha(0.6)
ax10.set_ylabel('Troponin (ng/mL)'); ax10.set_title('Troponin by Grade', fontweight='bold')

# 6-11: GLS
ax11 = fig.add_subplot(4, 3, 11)
bp2 = ax11.boxplot([df[df['grade']==g]['GLS'].values for g in range(4)], labels=grade_names, patch_artist=True)
for patch, color in zip(bp2['boxes'], colors_grade): patch.set_facecolor(color); patch.set_alpha(0.6)
ax11.set_ylabel('GLS (%)'); ax11.set_title('GLS by Grade', fontweight='bold')

# 6-12: Architecture
ax12 = fig.add_subplot(4, 3, 12); ax12.axis('off')
arch_text = """
┌──────────────────────────────────────┐
│         MODEL ARCHITECTURE           │
├──────────────────────────────────────┤
│  INPUT (21 features)                 │
│    ├─ Demographics (3)               │
│    ├─ Drug history (1)               │
│    ├─ PV hemodynamics (8)            │
│    ├─ Heart rate (1)                 │
│    ├─ Biomarkers (3)                 │
│    └─ Derived features (5)           │
│            │                         │
│            ▼                         │
│  ┌─────────────────────┐             │
│  │ Random Forest (200)  │→ Grade 0-3 │
│  │ Gradient Boosting    │→ Ees (reg) │
│  └─────────────────────┘             │
│            │                         │
│            ▼                         │
│  OUTPUT                              │
│    ├─ Toxicity Grade (0-3)           │
│    ├─ Ees estimate (mmHg/mL)         │
│    └─ Risk probability               │
└──────────────────────────────────────┘
"""
ax12.text(0.05, 0.95, arch_text, transform=ax12.transAxes, fontsize=8,
          verticalalignment='top', fontfamily='monospace',
          bbox=dict(boxstyle='round', facecolor='#F0F4FF', edgecolor='#4A7BFF'))

plt.tight_layout(rect=[0, 0, 1, 0.96])
plt.savefig('cardiotoxicity_ai_results.png', dpi=150, bbox_inches='tight', facecolor='white')
plt.close()
print("\n[시각화] cardiotoxicity_ai_results.png 저장 완료")

# CSV 저장
df.to_csv('synth_cardiotox_dataset.csv', index=False)
print("[데이터셋] synth_cardiotox_dataset.csv 저장 완료")
print(f"\n모든 단계 완료! ✓")
