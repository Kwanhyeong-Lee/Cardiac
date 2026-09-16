# Cerebrovascular CFD — Digital Twin Extension

## Project Goal
심장 digital twin 파이프라인(pH-PINN + anatomical CFD)을 뇌혈관으로 확장.
핵심 타겟: 뇌동맥류 파열 위험 예측 & 치료 시뮬레이션 (coiling/clipping/stenting)

## Folder Structure
```
cerebrovascular_cfd/
├── data/          # Raw imaging data (CTA/MRA, AneuRisk65 등)
├── geometry/      # Segmented vessel STL, centerlines, VMTK outputs
├── openfoam_case/ # OpenFOAM case directory (mesh, BC, solver settings)
├── results/       # Post-processing outputs (WSS maps, flow fields)
└── scripts/       # Python/bash scripts (segmentation, meshing, analysis)
```

## Pipeline (cardiac 대비)
| Step | Cardiac (현재) | Cerebrovascular (확장) |
|------|---------------|----------------------|
| Data | MM-WHS CT | AneuRisk65 STL or CTA/MRA |
| Segmentation | label map → marching cubes | VMTK level-set or pre-segmented |
| Meshing | snappyHexMesh | snappyHexMesh (동일) |
| CFD solver | pimpleFoam | pimpleFoam (동일) |
| Blood properties | ρ=1060, μ=0.0035 | 동일 (Newtonian 근사) |
| BC | E/A wave mitral inlet | ICA flow waveform |
| Key output | LV WSS, Windkessel R,C,L | Aneurysm WSS, OSI, RRT |
| pH-PINN | cardiac energy H(q,p) | cerebrovascular impedance → H |

## Key Biomarkers
- **WSS (Wall Shear Stress)**: 낮은 WSS → 동맥류 성장/파열 위험
- **OSI (Oscillatory Shear Index)**: 혈류 방향 불안정성 → 내피 손상
- **RRT (Relative Residence Time)**: 혈류 정체 → 혈전 위험
- **Pressure ratio**: 동맥류 dome vs parent artery

## Data Sources
1. **AneuRisk65** (prototyping): ecm2.org/aneurisk-dataset — 65 cases, STL ready
2. **ADAM Challenge** (segmentation practice): MRA + aneurysm annotations
3. **SimVascular VMR** (reference CFD models): pre-meshed cases
4. **Clinical CTA** (validation): IRB 승인 후 병원 PACS에서 확보

## Dependencies
- OpenFOAM 2312 (ESI) — 이미 설치됨
- VMTK — `pip install vmtk` or conda
- 3D Slicer + SlicerVMTK extension (GUI segmentation)
- ParaView (visualization)

## Status
- [ ] AneuRisk65 데이터 다운로드
- [ ] VMTK 설치 & 테스트
- [ ] 첫 번째 케이스 geometry 로드 & 시각화
- [ ] OpenFOAM case setup (ICA flow BC)
- [ ] CFD 실행 & WSS 추출
- [ ] pH-PINN cerebrovascular impedance model 설계
