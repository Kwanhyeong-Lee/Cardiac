# fusion_ready — 심장 어셈블리, 정리본

**2026-09-15.** 원본 `lv_cfd_anatomical/constant/triSurface/`의 16개 STL을 단위 통일(mm)·정리하고,
좌표계별로 분류한 뒤, 두 가지 감면 세트를 만들었습니다. 모든 수치는 `VERIFY.json`에 있습니다.

## 폴더

```
frame_A_patient/               원본 해상도, mm, LV 중심 = 원점      ← 유일하게 일관된 해부학 프레임
frame_B_papillary/             원본 해상도, mm, 별도 프레임 (복원 실패)
frame_C_stacom_UNREGISTERED/   원본 해상도, mm, 아틀라스 프레임 (정합 검증 실패)
frame_D_orphan/                원본 해상도, mm, 위치 불명
PRINT/<frame>/                 ≤40,000면/부위. 프린팅·슬라이서용. 원본이 닫혀 있으면 수밀 보장
CAD/<frame>/                   ≤10,000면/부위. 메쉬→BRep 변환용
MANIFEST.json                  프레임별 상태 + 부위별 치수
VERIFY.json                    감면 전후 면수·면적·부피 보존율·최근접거리(mean/p95/max mm)
pm_recovery.json               유두근 프레임 복원 시도 기록 (실패, 사유 포함)
MCP_CONNECT.md                 Fusion MCP 진단과 등록 절차
```

## 프레임 상태 — 이걸 먼저 읽으세요

| 프레임 | 부위 | 쓸 수 있나 |
|---|---|---|
| **A** | LV, 승모판, 대동맥판 | **예.** 같은 CT 좌표계. 단, 판막 *안착*은 미검증 — MV–AV 중심 간격 48mm(정상 20–30mm), 승모판이 LV 밖으로 돌출. 파라메트릭 판막이 환자 LV에 맞게 배치되지 않았을 가능성 큼. **프린팅 전 확인 필요.** |
| B | 유두근 2, 건삭 3 | 아니오. LV에서 ~260mm 떨어진 별도 프레임. 24개 고유회전 시험 → 식별 실패(상위5 spread 0.044). 해부학적 제약 기반 정합 필요. |
| C | RV, RA, PA, PV, LAA, 관상동맥 | 아니오(해부학적으로). 프로젝트 자체 검증에서 PA RMS 28.2mm, RV–LV 간격 34.9mm. 시각용 배치만. |
| D | 대동맥근 | 아니오. x=+204mm, 원인 불명. |

## 감면 품질 (VERIFY.json 요약)

- **LV**: PRINT 39,992면 수밀, 부피 100.0%, 최대 오차 0.017mm. CAD 9,998면 수밀, 최대 0.053mm.
- **STACOM 6개**: 전부 수밀 유지, PRINT 최대 오차 <0.05mm, CAD <0.24mm (pv 1.3mm — 컴포넌트별 재감면 후).
- **판막·유두근·건삭**: 원본부터 열린 면(수밀 아님). 닫지 않았습니다 — 닫으면 형상을 지어내는 것.
- **최악 편차**: papillary_muscles CAD 2.55mm (얇은 구조를 10k면으로 줄인 대가; PRINT는 0.55mm).

## 처리 중 잡은 것

1. LV 40k 감면이 비다양체 모서리 4개를 남김 → fill_holes는 제자리걸음 → **MeshFix**로 해결.
2. pv_stacom CAD가 4,948면·면적 51%·오차 66mm로 붕괴 → 7개 관을 통째로 감면한 탓 → **컴포넌트별 비례 감면**으로 재작업.
3. 유두근 복원이 문턱값 0.85를 0.0015 차이로 넘어 "RECOVERED" 판정 → 상위 5개 회전이 0.807~0.852로 **판별력 없음** → 판정 철회, 스크립트에 판별 조건 추가.

## 재현

```
PYTHONPATH=/tmp/pylibs python3 normalise_assembly.py
PYTHONPATH=/tmp/pylibs python3 build_fusion_sets.py frame_A_patient frame_B_papillary frame_C_stacom_UNREGISTERED frame_D_orphan
```
(`fast-simplification`, `rtree`, `pymeshfix` 필요)

## 2026-09-16 추가 — 판막 재생성과 Blender 파이프라인

**판막 결함의 진짜 원인**: `generate_valves.py` 83행 `lv_axis = [0,0,-1]` 하드코딩. 실측 LV 장축
`[0.448, −0.768, 0.458]`과 약 60° 어긋남. 크기가 아니라 방향이 문제였음.

**재생성(`refit_valves.py`)**: 형상은 그대로, 위치 상수 3개만 LV 실측치로 교체.

| 승모판 | 원본 | refit_v1 |
|---|---|---|
| 첨판 구역 LV 내부 비율 | 77.9% | 87.5% |
| 벽 밖 초과 (중앙값 / 최대) | 8.8 / 22.1 mm | 1.5 / 5.8 mm |
| 장축 span | 56.3 mm | 31.4 mm |
| 기저면 위 돌출 | 12.3 mm | 4.1 mm |

사전 기준(첨판 90% 내부)에 2.5p 미달 → `mitral_valve.stl`은 원본 유지, 재생성본은
`*_refit_v1.stl`로 병기. 잔여 12.6%는 얕고(깊이 5–12mm) 작고(1.5mm) 한 방향(타원 LV의 단축)
에 집중 — v2에서 D-형상 방향을 LV 단면 주축에 맞추면 해결될 성질. **프린팅에는 refit_v1 권장.**
원본은 60° 틀어져 있어 해부 모형으로 쓰면 안 됨. 전부 `valve_refit.json`.

**Blender (`blender_pipeline.py` + `run_blender_pipeline.bat`)**: LV(PRINT) + refit 판막 임포트 →
판막을 0.25mm voxel remesh로 닫힌 단일 솔리드화 → 비다양체·부피·bbox 검사 → 부위별 STL +
통합 STL + .blend → `BLENDER_OUT/blender_report.json`. Windows에서 .bat 더블클릭 또는
Claude Code에서 `blender --background --python blender_pipeline.py`. 이 세션의 샌드박스에는
Blender가 없어 실행 결과는 `blender_report.json`으로 돌려받아 검증함.

## 2026-09-16 (이어서) — Claude Code 실행 결과 반영 + 세 가지 마무리 작업

Claude Code(Windows Blender 5.2.1)가 파이프라인을 실행했고 그 결과는 `FINDINGS.md` §1–8.
핵심: 판막은 1mm 껍질이 아니라 **두께 0의 시트**(오일러 수 1/0)라 Solidify 1.2mm를 먼저 넣어야
했고, `cardiac_meshes/`는 **좌우 거울상**(X 반사 0.044mm)이며 frame A가 옳음. v2 승모판
(97.8%)이 게이트를 통과해 `mitral_valve.stl`로 승격됨. 아래 세 작업은 그 위에서 진행.

### 1. 유두근 6-DOF 정합 — `pm_register.py` → **강체 정합 불가 판정**
축정렬 최적 후보(perm (0,2,1), 부호 −−−)에서 회전벡터+평행이동 Powell 정련. 비용 = 기저부
내막 부착 + 비기저부 공동 내부(준-경성) + 첨부→판륜 15–40mm + 조준 + 15° 회전 상한.
1차 실행은 연성 제약 탓에 근육의 24%를 벽 밖으로 묻으며 46.7° 회전(후보 포기) → 비용 재규정.
2차 실행은 모든 게이트를 근소하게 동시 위반 — 어느 하나를 만족시키면 다른 게 깨지는 구조라
"덜 수렴한 최적점"이 아니라 **frame B 유두근이 이 LV와 강체로 맞지 않는 것**으로 판정.
출력은 `*_bestfit_NOTACCEPTED.stl`로 이름을 바꿔 남김(`pm_registration.json`). 권장 대안:
`BLENDER_OUT/LV_myocardium_frameA.stl`에서 혈액풀 볼록껍질 안쪽으로 돌출한 근육을 잘라내
**환자 본인의 유두근**을 얻는 것 — frame B는 다른 심장이므로 어차피 참고용.

### 2. 속 빈 심실 + 판막 고정 — `make_av_plate.py` → `BLENDER_OUT/hollow_ventricle_v2_fixed_valves.stl`
실측상 방사형 칼라는 붙을 곳이 없음(근육 기저 개구가 승모판륜면 0.8mm 위에서 끝나고, 대동맥판은
근육 위 1.2mm에 떠 있으며, 36방향 중 28방향에서 20mm 내 근육 없음). 그래서 해부학적으로 두
판막을 잡아주는 구조인 **방실면 섬유 골격 = 판(plate)**을 만듦: 근육 기저 단면(4/8/12mm 깊이의
볼록껍질) 윤곽, 두께 6mm(판륜면 1.5mm 아래 → 4.5mm 위), 승모판 구멍 r 13.7 / 대동맥판 구멍
r 9.9(각 판륜링 1.5mm 매립). 두 구멍이 60° 구간에서 겹치는 것은 실제 대동맥-승모판 커튼 위치.
manifold3d로 근육+판+승모판+대동맥판 합집합: **787,492면, 수밀, 단일 컴포넌트, 147.0 mL**.
공동 차단율 1.8%(열림), 두 구멍 축 통과 확인(`hollow_v2_check.json`, `hollow_v2_sections.png`).

### 3. CAD — LV 유동 팬텀 lost-core 몰드 — `make_flow_phantom_mold.py` → `PHANTOM/`
유동 팬텀은 실리콘 **안의 공동**이 필요하므로 2분할 음각(→ 속 찬 복제품)이 아니라 lost-core:
| 파트 | 내용 | 수치 |
|---|---|---|
| `core_LV_with_ports.stl` | 혈액풀 + 승모판 포트(⌀19, 3/4″) + 대동맥판 포트(⌀12.7, 1/2″), LV 장축 방향 45mm | 41,016면, 수밀, 170.2 mL, PVA/왁스 출력 |
| `mould_box.stl` | 벽 4mm 상자, 포트면에 보어 2개(반경 여유 0.4), 반대면 개방(주입, 여유고 8mm), 모서리 다리 4개 32mm | 868면, 수밀, 102×95×141mm(+다리) |
| `*_PRINT_ORIENTED.stl` | 위 두 파트를 출력 자세로 | |
설계 검사(`phantom_design.json`): 코어-상자 벽 접촉 0%, 실리콘 최소 두께 15.0mm, 스터브 돌출
25mm < 다리 32mm, 주입면 열림·포트면 닫힘 모두 통과. 실리콘 약 0.98 L. 모든 치수는 스크립트
상단 상수 — 포트 지름·여유·마진을 바꾸고 다시 돌리면 됨. 절차는 JSON `procedure`.
`phantom_sections.png`가 조립 단면.

**샌드박스 메모**: manifold3d·shapely·pymeshfix는 `/tmp/pylibs`에 설치 → 재시작마다 사라짐.
`PYTHONPATH=/tmp/pylibs python3 <script>`.

## 2026-09-16 (밤) — "심장 내부가 너무 대강" → 원본 CT로 돌아가서 해결

지적이 맞았고 원인은 세그멘테이션 라벨이었다: MM-WHS 라벨 500(LV 공동)이 유두근·육주를 삼켜서
메시에는 애초에 내부 구조가 없었다(`extract_pm.py`: 심근 ∩ 매끈화 공동 = 0.63 mm 필름 하나).
원본 CT(0.49 × 0.49 × 0.63 mm)는 혈액 340 HU / 심근 120 HU로 깨끗이 갈리므로 라벨 안에서 다시
분할했다(`ct_refine_lv.py`): 라벨 150.4 mL = **진짜 혈액 132.5 mL + 공동 안 근육 17.8 mL**.
영상→frame A는 **평행이동만, 평균 0.19 mm**로 맞아떨어졌다(같은 라벨에서 온 것이므로 당연하지만
assert로 걸어 둠). 환자 유두근 2개 회수: 전측 2.1 mL(대동맥판 방향 −121°, 29 mm), 후내측
3.1 mL(+153°, 31 mm). 이걸로 **v4** (`build_hollow_v4_CT.py`):

| | v3 (이상화) | **v4 (환자 CT)** |
|---|---|---|
| 벽·내막 | 라벨 메시(매끈) | CT 재분할, 육주 있음 |
| 유두근 | 원뿔 2개, 교과서 위치 | 환자 것 2개 |
| 건삭 | 이상화 첨부에서 10개 | **환자 유두근 첨부**에서 10개 (경로만 파라메트릭) |
| 판막·판 | 파라메트릭 | 파라메트릭 (변화 없음) |
| 솔리드 | 754,854면, 166.8 mL | **712,322면, 수밀, 단일, 181.8 mL** |

절개 모형 `BLENDER_OUT/hollow_v4_cutaway_{A,B}_PRINT_ORIENTED.stl`, 렌더 `hollow_v4_cutaway_render.png`.
파이프라인 전체 순서와 산출물별 용도는 `PIPELINE.md`, 논문용 Methods 골격은 `METHODS_DRAFT.md`.

이 세션에서 잡은 그림/검사 버그 3개(재발 방지용 기록): 단면 그림을 메시마다 다른 2D 프레임에 그린 것,
marching cubes 메시를 복셀 인덱스 좌표에 둔 채 불리언(→ 빈 결과 → 거짓 "없음" 판정), `np.False_ is False`.

**다른 PC(RTX 3060/32 GB)로 이전**: 루트의 `GIT_SETUP.md`와 `.gitignore`. MIMIC/eICU/INSPIRE/MM-WHS는
git에 절대 올리지 말 것(DUA·라이선스); 코드·문서만 git, 데이터는 외장 SSD.
