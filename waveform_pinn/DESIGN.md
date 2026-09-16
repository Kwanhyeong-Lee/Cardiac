# Paper 2 — Waveform-Input pH-PINN (설계)

## 1. 왜 이 논문이 필요한가 (Paper 1의 근본 한계)
Paper 1: 입력 = 대리공식의 **인자**(EF, EDV, ESV, SBP, DBP, HR, CO…),
타깃 = 그 **공식의 출력**(Ees, Ea, coupling…).
→ 결정론적 사상이라 R²=0.97이 정보량을 거의 갖지 않음(순환성).
환자 단위 split으로 바꿔도 R²가 안 떨어진 것이 그 증거.

## 2. 순환성을 깨는 방법
**입력을 파형 형태(morphology)로 교체**한다. 형태 특징은 어떤 타깃 공식에도
등장하지 않으므로 사상이 더 이상 항등식이 아니다.

### 입력 (VitalDB SNUADC/ART, 침습 동맥압 500Hz → 100Hz)
beat 검출 → 앙상블 평균 beat → 형태 특징:
- dicrotic notch 시각/압력, notch_frac (augmentation-like)
- max dP/dt, min dP/dt (수축성·이완 대리)
- 수축기/확산기 면적 및 비, form factor, upstroke time
- beat-to-beat SD (신호 품질)
※ 파일럿 확인: beat간 SD 1.74 mmHg (재현성 높음),
  환자간 분산 큼 (notch_frac 0.26–0.65, max dP/dt 476–1130)

### 타깃 (멀티타깃 — 사용자 선택)
(a) **Windkessel 물리 파라미터**: R_tot, C(τ법·PP법), τ
    → 같은 파형에서 독립적으로 식별. 물리 동정(identification) 과제.
(b) **기기 측정 CO / SV**: EV1000 / Vigileo / Vigilance
    → 별도 계측기 산출물. 입력의 공식값이 아님 → 완전 비순환.
두 타깃을 pH 에너지 구조(H=T+V, R⪰0)로 연결.

## 3. 코호트
- ART 파형 + CO + SV: **964 케이스** (CVP까지: 531)
- 성인 98.3%, 57.9±15.4세, **비-ICU 수술환자** → Paper 1의 ICU 편향도 해소
- 진짜 독립 gold standard: Vigilance(열희석 PAC) CO 65 / EDV·ESV 49

## 4. Paper 1에서 그대로 가져오는 것
- 하드 구조 제약(softplus T,V≥0 / H=T+V / Cholesky R⪰0)
- 4-way matched-capacity ablation 설계
- 환자 단위 GroupShuffleSplit (leakage 차단)

## 5. 정직하게 유지할 한계
- **Zc(3-element) 분리 불가**: 수술환자 확산기 창(~0.48s) < 필요 τ(~1.03s),
  비율 0.40 → 구조적 한계. 2-element(R_tot, C, τ)만 식별 가능으로 한정.
- 기기 CO(EV1000/Vigileo)는 동맥파형 기반이라 완전 독립은 아님
  → **Vigilance 열희석 65건**을 별도 서브셋 검증으로 사용.
- LV Ees의 침습 검증은 여전히 불가(공개 데이터 부재) → 전향적 연구 과제.

## 6. 파이프라인
1. `extract_features.py` — 파형 → 형태 특징 + Windkessel 타깃 (완성, 검증됨)
2. `train_waveform_pinn.py` — 멀티타깃 pH-PINN + ablation (다음 단계)
3. 검증: 환자 단위 split, Vigilance 서브셋, notch_frac 등 형태특징의 기여도 분석

## 7. 실행
```bash
cd "/mnt/c/work/Cardiac/waveform_pinn"
python3 extract_features.py 964 0      # 케이스당 ~5초, 약 1시간
```
결과: `wave_features_0.csv` → 이걸로 학습/ablation 진행

## 8. 타겟 저널
순환성이 깨지고 기기 측정 타깃이 있으므로 **IEEE JBHI 재도전이 현실적**.
(Paper 1은 TBME/ML4H로 먼저 내고, 이 논문이 확장판이 됨)
