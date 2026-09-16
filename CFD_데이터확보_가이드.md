# Cardiac CFD 데이터 확보 & 파이프라인 가이드

## 1. 데이터셋 확보 (우선순위 순)

### ★ MM-WHS (최우선 — CFD에 최적)
- **내용**: Cardiac CT 60개 + MRI 60개, 7개 하부구조 라벨
  - LV, RV, LA, RA, Myocardium, Aorta, Pulmonary Artery
- **해상도**: In-plane 0.78×0.78mm, slice 1.60mm
- **병리**: MI, AF, TR, AS, DCM 등 다양
- **접근**: 등록폼 서명 후 이메일 제출
  - 사이트: https://zmiclab.github.io/zxh/0/mmwhs/
  - 등록폼 다운로드 → 서명 → Lingchao XU & Lei LI에게 이메일
  - 보통 1-3일 내 다운로드 링크 수신
- **포맷**: NIfTI (.nii.gz), 3D volume + segmentation mask

### ★ ACDC (LV 중심 분석에 적합)
- **내용**: Cardiac MRI 150개 (100 training + 50 test)
  - 5그룹: DCM, HCM, MINF, RV-abnormal, Normal
- **라벨**: LV cavity, RV cavity, Myocardium (ED/ES frame)
- **접근**: 웹사이트 등록 후 즉시 다운로드
  - 사이트: https://www.creatis.insa-lyon.fr/Challenge/acdc/databases.html
- **포맷**: NIfTI, 4D cine MRI

### RAS Dataset (보조 — Right Atrium)
- **내용**: LGE-MRI 50개, Right Atrial cavity segmentation
- **접근**: Zenodo에서 즉시 다운로드 (등록 불필요)
  - https://doi.org/10.5281/zenodo.10781134

### HVSMR-2.0 (선천성 심장질환)
- **내용**: CMR 60개, 4 chambers + 4 great vessels
- **접근**: 공개 다운로드
  - DOI: 10.1038/s41597-024-03469-9


## 2. 즉시 실행 가능한 작업

### (A) ACDC 다운로드 → LV geometry 추출
ACDC는 웹 등록만 하면 바로 받을 수 있음.
DCM (확장성 심근병증) 케이스가 HF 환자와 가장 유사 → CFD 대상으로 적합

### (B) TotalSegmentator로 MIMIC-IV CT 활용 (향후)
MIMIC-IV에 연결된 흉부 CT가 있는 경우:
```bash
pip install TotalSegmentator
TotalSegmentator -i chest_ct.nii.gz -o segmentation/ --task total
# 2025 업데이트: 11개 심혈관 구조 자동 segmentation
```

### (C) 대기 중 — parametric LV로 파이프라인 프로토타입
데이터 도착 전까지 idealized LV geometry (prolate spheroid)로
전체 CFD 파이프라인 테스트 가능


## 3. CFD 파이프라인 소프트웨어

| 단계 | 도구 | 비고 |
|------|------|------|
| Segmentation | TotalSegmentator v2 | CT → 심장 구조 자동 추출 |
| Surface mesh | marching cubes (Python) | NIfTI mask → STL |
| Mesh repair | MeshLab / trimesh | watertight 보장 |
| Volume mesh | GMSH | tetrahedral volume mesh |
| CFD solver | OpenFOAM | Navier-Stokes (pulsatile) |
| Post-process | ParaView / Python | WSS, pressure, flow |
| Lumped params | Python script | CFD → R, C → pH-PINN 비교 |

전체 파이프라인 오픈소스. SimVascular도 대안 (end-to-end).


## 4. 즉시 해야 할 액션

- [ ] ACDC 웹사이트 가입 & 데이터 다운로드
- [ ] MM-WHS 등록폼 서명 & 이메일 제출
- [ ] (선택) RAS dataset Zenodo 다운로드
- [ ] OpenFOAM / GMSH 설치 확인
- [ ] Parametric LV prototype로 파이프라인 검증
