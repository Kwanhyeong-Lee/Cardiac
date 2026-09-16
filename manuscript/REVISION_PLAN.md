# 개정 계획 — 코드 대조 감사 후 (2026-07-30)

## A. 이미 원고에 반영 완료 (오늘)
- 미구현이던 식 (3) L_H 서술 제거 → R⪰0에 의한 **구조적 passivity 보장**으로 정정
- 실제 학습 손실을 정확히 기술 (L_data + partition + positivity + PSD), float32 명시
- Fig.1(C)를 "Hamiltonian partition consistency ‖H−(T+V)‖²"로 정정 (에너지밸런스 잔차 아님)
- per-beat(정상상태) 추론임을 명시, 시간미분 없음을 명시
- 해부 메시가 추론에 쓰이지 않음을 본문·한계에 명시
- 참고문헌 22개 전수 검증 + 오류 3건 수정

## B. 계산 완료 — 원고 반영 대기 (energy_partition_corrected.json)
문헌 근거: PVA = SW(≈사각형 work loop) + PE(≈삼각형). 기존 SW는 삼각형(½)이라 과소.
E_diss는 차원오류(mmHg²·s) → r·Q̄²·T_sys 로 정정.

| 항목 | 기존(오류) | 정정 |
|---|---|---|
| SW | 3,675 (½·Ea·SV²) | **7,000** (Pes·SV) |
| PE | 2,000 | 2,000 (동일) |
| PVA | 5,675 | **9,000** |
| E_diss | 137.1 (차원오류) | **524.6** (r·SV²/T_sys) |
| E_diss %PVA | 2.4% | **5.8%** |
| SW_net | 3,538 | **6,475** |
| gross η | 64.8% | **77.8%** |
| net η | 62.3% | **71.9%** |
| Ea/Ees | 0.60 | 0.60 (불변) |

반영 대상: Abstract, §III-D(Windkessel/PV), Fig.4 캡션·패널C 막대, Discussion, Conclusion,
그리고 "η=1/(1+PE/SW)=64.8%" 문장 → 77.8%로.

## C. 재실행 필요 — 스크립트 준비 완료, 이 환경에서 미완주
`outputs/ablation_patient.py` (GroupShuffleSplit by subject_id, 80 epochs)
근거: cardiac_energetics_hamiltonian.csv → 5,851행 / **subject_id 4,241명 = 1.38행/환자**
→ 기존 `train_test_split` 행 단위 분할은 **환자 leakage 발생**. 재실행 필수.
실행: `for L in A B C D; do for S in 0 1 2; do python3 ablation_patient.py $L $S; done; done`
(로컬/WSL 권장. 결과 12개 JSON → 표 I·Fig.2 갱신)

## D. 서술 변경 필요 (계산 불필요, 판단 사항)
1. **순환성 명시** — 입력(EF,EDV,ESV,SBP,DBP,HR,CO…)이 타깃 Ees/Ea 대리공식의 인자를 모두 포함.
   → R²는 "대리공식 재현(sanity check)"으로 격하하고, 논문 축을 **ablation(구조적 유효성 보장)**으로 이동.
2. **SVR Bland–Altman** — measured_SVR vs computed_SVR (= 공식 검증). 모델 검증 아님.
   → "strongest validation evidence" 표현 삭제, "surrogate formula agreement"로 정정.
3. **운동량 p** — Windkessel L=0이므로 물리적 관성 근거 없음 → "latent state"로 재정의.
4. **g(x)u** — 코드에 없음(u=0 자율계) → 본문에 명시.
5. **H=T+V 열** — 모델 C도 구성상 만족 → A/C 판별 지표 아님을 각주로.
6. **제외기준 vs n** — 원고의 exclusion criteria가 실제 코호트 추출에 적용됐는지 확인 후 서술 일치시킬 것.

## E. 권고 순서
D-1,2 (서술) → B (에너지 재계산 반영) → C (환자 단위 재실행) → 그림·표 재생성 → 재감사 → 그 후 공개.
