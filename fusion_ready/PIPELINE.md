# PIPELINE — 세그멘테이션에서 프린트·팬텀·CFD 도메인까지 (2026-09-16 기준)

한 케이스(MM-WHS case 1009)에 대해 아래 순서대로 돌리면 모든 산출물이 재현된다. 각 단계는
**어디서 돌아가는지**(샌드박스 Linux / Windows Blender)와 **무엇을 검증하는지**를 적었다.
다른 케이스에 쓰려면 1→13을 그대로, 상수는 각 스크립트 상단에서만 바꾼다.

## 환경

| 환경 | 용도 | 준비 |
|---|---|---|
| Python 3.10 + trimesh 4.12 (샌드박스 또는 아무 Linux/WSL) | 1–4, 6–13 | `pip install --target /tmp/pylibs fast-simplification rtree pymeshfix shapely mapbox-earcut manifold3d scikit-image` 후 `PYTHONPATH=/tmp/pylibs` |
| Blender 5.2 (Windows) | 5만 | `run_blender_pipeline.bat` 또는 Claude Code에서 `blender --background --python blender_pipeline.py` |

샌드박스는 3 GB RAM. **큰 메시(≥40k면)에 `trimesh contains()`/`volume_mesh()`(ray-cast)를
쓰지 말 것** — 두 번 OOM. 대신 `lv_sdf_grid.npz`(단계 4)의 SDF 보간이나 작은 파트에만 `contains()`.

## 단계

| # | 스크립트 | 입력 → 출력 | 검증 / 판정 기록 |
|---|---|---|---|
| 1 | `normalise_assembly.py` | `lv_cfd_anatomical/constant/triSurface/*.stl` (m·mm 혼재, 4개 프레임) → `frame_A_patient/`, `frame_B_papillary/`, `frame_C_stacom_UNREGISTERED/`, `frame_D_orphan/`, `MANIFEST.json` | 단위·프레임 진단; **frame A만 해부학적으로 일관** |
| 2 | `build_fusion_sets.py` | frame A → `PRINT/` (≤40k면, pymeshfix로 수밀 복원), `CAD/` (≤10k면) | `VERIFY.json`: 감면 오차·수밀·컴포넌트 |
| 3 | `refit_valves.py` | `generate_valves.py` 상수 3개를 실측 LV 축·판륜 위치로 교체 → `*_refit_v1.stl`, `valve_refit.json` | 첨판 LV 내부 비율 87.5% (게이트 90% 미달 → v1 병기). Claude Code의 shrink-wrap v2 97.8% 통과 → `mitral_valve.stl` 승격 (`valve_refit_v2.json`) |
| 4 | `build_sdf_grid.py` | `PRINT/frame_A_patient/lv_surface.stl` → `lv_sdf_grid.npz` (2.5 mm, +12 mm 여유) | 이후 모든 포함 검사의 기반 |
| 5 | `blender_pipeline.py` **(Windows)** | frame A LV + 승격 판막 → `BLENDER_OUT/{LV_bloodpool, mitral_valve, aortic_valve}.stl`, `LV_myocardium_frameA.stl`(cardiac_meshes를 X-반사로 frame A에 정합), `frame_transform.json` | `FINDINGS.md`: 판막은 두께 0 시트 → Solidify 1.2 → voxel 0.25; `cardiac_meshes/`는 **좌우 거울상** |
| 6 | `make_av_plate.py` | 심근 기저 단면 + 승모판 시트의 실제 판륜 → `frame_A_patient/av_plane_plate.stl`, `av_plate.json` | 판 12.5 mm(+4.5~−8.0), D자 승모판 구멍(판륜 −1.5 mm 오프셋), 원형 대동맥 구멍; **실제 판륜 87% 매립**(나머지 13% = 대동맥 구멍 구간, 의도) |
| 7 | `build_hollow_v2.py` | 심근 ∪ 판 ∪ 승모판 ∪ 대동맥판 (manifold3d) → `BLENDER_OUT/hollow_ventricle_v2_fixed_valves.stl`, `hollow_v2_check.json` | 751,754면, 수밀, 단일, 163.9 mL; 공동 차단 1.7%, 두 구멍 축 통과 |
| 8 | `extract_pm.py` | 심근 ∩ closing(혈액풀) → `pm_extract.json` | **판정: 유두근이 심근 라벨에 없음**(교집합 = 0.63 mm 필름 하나, closing이 채운 부피 0.4 mL). 환자 유두근 추출 불가 — 팬텀/CFD 공동은 "유두근 포함 공동" |
| 8′ | `pm_register.py` | frame B 유두근의 6-DOF 강체 정련 → `pm_registration.json`, `*_bestfit_NOTACCEPTED.stl` | **강체 정합 불가** — 모든 게이트 근소 동시 위반. 사용 안 함 |
| 9 | `generate_subvalvular.py` | 교과서 해부 위치의 **이상화** 유두근 2개 + 건삭 10개 → `frame_A_patient/{pm_*,chordae}_IDEALISED.stl`, `BLENDER_OUT/hollow_ventricle_v3_IDEALISED_subvalvular.stl`, `subvalvular.json` | 754,854면, 수밀, 단일, +2.9 mL; 건삭 10/10 공동 내 경로; 구멍 축 통과 |
| 10 | `make_cutaway.py v2` / `v3` | 장축+MV–AV 선을 포함하는 면으로 반절 → `BLENDER_OUT/hollow_v*_cutaway_{A,B}[_PRINT_ORIENTED].stl`, `cutaway_v*.json` | 각 반쪽 수밀·단일; 부피 합 = 전체 |
| 11 | `make_flow_phantom_mold.py` | 혈액풀 + 포트(Ø19 / Ø15.8) → `PHANTOM/core_LV_with_ports.stl`, `mould_box.stl`, `*_PRINT_ORIENTED.stl`, `phantom_design.json` | 코어-상자 접촉 0, 실리콘 ≥15 mm, 주입면 열림·포트면 닫힘, 다리 > 스터브 돌출 |
| 12 | `export_cfd_domain.py` | 코어 → `PHANTOM/cfd/LV_phantom_{m,mm}.stl` (`inlet`/`outlet`/`LV` 패치), `cfd_domain.json`, snappyHexMesh 스니펫 | 유입 2.83 cm², 유출 1.96 cm², 재조립 시 열린 모서리 0 |
| 14 | `ct_refine_lv.py` | **원본 CT** `MM-WHS/ct_train/ct_train_1009_{image,label}.nii.gz` → 라벨 500 안에서 Otsu(235 HU) → `CT/lv_bloodpool_CT.stl`(진짜 혈액 132.5 mL), `CT/LV_myocardium_CT_with_PMs.stl`(라벨 205 + 공동 안 근육 17.8 mL), `CT/pm_candidate_*_CT.stl`, `ct_refine.json` | 영상→frame A: **회전 없음, 평행이동 (37.08, −31.48, 159.46), 평균 0.19 mm** (assert < 1 mm). 환자 유두근 2개: 전측 2.1 mL(−121°), 후내측 3.1 mL(+153°) |
| 15 | `ct_prepare_parts.py` | Taubin 10회 + 감면(316k/149k) + 수밀 복원 → `CT/*_smooth.stl`, `CT/blood_sdf_grid.npz`, `CT/pm_tips.json` | 부피 보존 (143.4→142.8, 132.7→132.9 mL) |
| 16 | `build_hollow_v4_CT.py` | CT 심근(유두근·육주 포함) ∪ 판 ∪ 판막 ∪ 진짜 유두근 첨부에서 나가는 건삭 10개 → `BLENDER_OUT/hollow_ventricle_v4_CT.stl`, `hollow_v4_check.json` | 712,322면, 수밀, 단일, 181.8 mL; 차단 2.5%, 구멍 축 통과. `make_cutaway.py v4` → 절개 모형, `hollow_v4_cutaway_render.png` |
| 13 | `render_sections.py v2|v3|v4`, `render_check.py` | 검증 그림 (`BLENDER_OUT/hollow_v*_sections.png` 등) | 단면 그림은 **패널당 하나의 2D 프레임** 사용 (초기 그림의 결함 수정) |

## 산출물 → 용도

| 용도 | 파일 | 주의 |
|---|---|---|
| 혈액풀 단독 프린트 | `CT/lv_bloodpool_CT_smooth.stl` (진짜 혈액, 육주 음각) 또는 `PRINT/frame_A_patient/lv_surface.stl` (라벨 그대로, 유두근 포함 공동) | 팬텀 코어는 아직 라벨 버전 — 아래 참고 |
| 판막 달린 속 빈 심실 프린트 | `BLENDER_OUT/hollow_ventricle_v2_fixed_valves.stl` | 판막은 파라메트릭(환자 것 아님) |
| **전체 어셈블리 — 환자 내부 (권장)** | `BLENDER_OUT/hollow_ventricle_v4_CT.stl` | 벽·내막·육주·유두근 = 환자(CT 0.49 mm). 첨판·판·건삭 경로 = 파라메트릭 |
| 전체 어셈블리 — 이상화 유두근 (구버전) | `BLENDER_OUT/hollow_ventricle_v3_IDEALISED_subvalvular.stl` | v4가 나오기 전 버전. 유두근·건삭 **이상화** — 비교용으로만 |
| 교육용 절개 모형 | `BLENDER_OUT/hollow_v4_cutaway_{A,B}_PRINT_ORIENTED.stl` | 절단면 아래로 출력. 내벽에 육주·유두근이 보임 |
| 실리콘 유동 팬텀 | `PHANTOM/core_PRINT_ORIENTED.stl` (PVA) + `mould_box_PRINT_ORIENTED.stl` (PLA/PETG) | 절차는 `phantom_design.json → procedure` |
| CFD (OpenFOAM) | `PHANTOM/cfd/LV_phantom_m.stl` + 스니펫 | frame A 좌표(m); 기존 `lv_cfd_patient`와 프레임 다름 |
| Fusion 360 / CAD | `CAD/frame_A_patient/*.stl`, `PHANTOM/*.stl` | 몰드 파트는 정확한 원기둥·상자라 BRep 변환 용이 |

## 남은 선택지 (2026-09-16 저녁 기준)
- **팬텀 코어를 CT 혈액풀로 교체**: `make_flow_phantom_mold.py`의 LV 경로를 `CT/lv_bloodpool_CT_smooth.stl`로 바꾸면 되지만, 1 mm 미만 육주 틈은 PVA 코어에서 부러지고 실리콘에 기포를 가둔다. 반경 1.5 mm closing으로 미세 틈만 메운 버전을 코어로 쓰는 것이 맞다(유두근 형상은 유지됨).
- 판막은 여전히 파라메트릭. CT에는 판막 첨판이 거의 안 보이므로(이완기 정지 영상) 여기서 더 나아가려면 4D CT나 문헌 템플릿이 필요하다.
