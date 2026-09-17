# HeartTeach — 사양서 (2026-09-17)

`fusion_ready/UNREAL/<case>/` 에셋 팩 위에 올리는 데스크톱 교육 앱. **왜 이렇게 설계했는지**와 **무엇이 정답인지**를
적어 둔 문서로, 구현 중 판단이 갈리면 여기를 기준으로 한다. 케이스 1009 숫자 기준.

## 1. 설계 원칙

**모든 것이 텍스트에서 재생성된다.** Blueprint·머티리얼·위젯은 바이너리 `.uasset`이라 diff도 리뷰도 안 되므로,
로직은 C++, 에셋 생성은 에디터 Python으로 한다. 손으로 클릭해 만든 것은 UMG 레이아웃(M4)뿐이어야 한다.

**해부는 데이터, 코드가 아니다.** 부위 목록·색·출처·부피·관류 수치는 전부 DataTable에서 온다.
다른 환자(1001 등)로 바꾸는 것은 **재임포트이지 코드 수정이 아니다.**

**정직함이 기능이다.** 이 모형은 성격이 다른 세 가지 형상이 섞여 있고, 교육적 가치는 그것을 흐리지 않는 데 있다.
부위를 보여줄 때 출처 배지를 항상 같이 띄운다.

## 2. 좌표계 (틀리면 조용히 망한다)

파이프라인 RAS mm → glTF(오른손, Y-up, m): `X=-X_ras, Y=Z_ras, Z=Y_ras`, 행렬식 +1. Unreal의 glTF 임포터가
좌손·Z-up·cm로 바꾸는 것은 **보이는 대로 보존**하므로 손대지 않는다. **Unreal에서 음수 스케일 금지.**

수치를 Unreal 공간으로 옮길 때(절단면 등)는 `03_build_level.py`의 `gltf_to_unreal`을 쓴다: `(x, -z, y) × 100`.

**검수 규칙 — 매 빌드마다 눈으로 확인:** 정면(`ResetView`)에서 **두꺼운 짙은 붉은 벽(좌심실)이 화면 오른쪽**에 있어야 한다.
1009에서 LV 중심은 RV보다 +34 mm다. 좌우가 뒤집힌 심장은 그냥 봐서는 구분이 안 되고, 이 프로젝트의
`cardiac_meshes/`가 실제로 그렇게 망가진 적이 있다.

## 3. 에셋

| 에셋 | 만든 것 | 비고 |
|---|---|---|
| `/Game/Heart/Parts/*` | 01 | 부위 16종, 정점 색 포함, Combine 끔, Nanite 끔 |
| `/Game/Heart/Assemblies/*` | 01 | whole_heart, half_A, half_B, perfusion_territories |
| `DT_HeartParts` | 01 | `FHeartPartRow` |
| `DT_HeartTerritories` | 01 | `FHeartTerritoryRow` — 폐색 시나리오 7개 |
| `DT_HeartTerritoryColours` | 01 | `FHeartTerritoryColourRow` — 정확한 정점 색 6종(그중 5종만 실제 출현) |
| `MPC_HeartClip` | 02 | ClipEnabled(s), ClipOrigin(v), ClipNormal(v) |
| `M_HeartPart` | 02 | Masked + Two Sided + 월드 노멀 |
| `L_Heart` | 03 | 레벨, 조명, HeartAssembly, HeartPawn |

## 4. 머티리얼 (핵심)

`M_HeartPart`의 셰이딩은 Custom HLSL 노드 세 개에 들어 있고, 그 HLSL이 사양 그 자체다(`02_build_materials.py`).

- **Opacity Mask** — `dot(WorldPos − ClipOrigin, normalize(ClipNormal)) ≥ 0` 이면 남긴다. `ClipEnabled`가 0이면 전부 남긴다.
  부위 격리용 `Opacity`는 디더(Masked라 반투명이 안 되므로)로 처리한다.
- **Base Color** — `lerp(Tint, VertexColor, UseVertexColour)` → 관류 회색 처리 → **뒷면이면 `c*0.82 + 0.18`**.
  이 0.82/0.18은 matplotlib 렌더에서 절단면에 쓴 값과 같다. 화면과 문서 그림이 같은 톤으로 보인다.
- **Normal** — 뒷면이면 `−ClipNormal`. 이걸 빼먹으면 잘린 면이 곡면처럼 음영져서 "속이 파인 것"으로 읽힌다.
  머티리얼의 Tangent Space Normal을 **꺼야** 월드 노멀을 넣을 수 있다.

**실제 캡 지오메트리를 만들지 않고 이 착시가 성립하는 전제는 메시가 닫혀 있다는 것이다.** 29단계에서 4방 절단면을
재삼각분할하고 pymeshfix로 봉합해 A/B 반절을 수밀로 맞춰 둔 이유가 이것이다(134.8 / 178.7 mL, 합 313.5 = 전체 313.6).
나중에 진짜 캡이 필요하면 Custom Stencil로 마스크를 만들고 평면 쿼드를 그 영역에만 그리는 방식으로 올린다.

## 5. 관류 — 색이 곧 데이터

`LV_myocardium_territories.ply`의 정점 색은 **정확히 이 값들만** 나온다(1009):

| RGB8 | 의미 | 정점 |
|---|---|---|
| 216,38,38 | LAD, **실측** | 494,080 |
| 242,153,25 | LCx, 실측 | 53,222 |
| 38,102,216 | RCA, 실측 | 19,417 |
| 247,198,128 | LCx, **고랑 사전정보로 배정** | 276,481 |
| 135,170,233 | RCA, 사전정보로 배정 | 656,626 |
| 233,135,135 | LAD, 사전정보 | **0 — 1009에는 없음** |

연한 색 = `0.55·c + 0.45` (파이프라인의 `PRIOR_TINT`). 즉 **영역과 신뢰도가 둘 다 색에 들어 있어서**,
머티리얼이 정점 색을 이 상수들과 비교하는 것만으로 "선택한 혈관 영역만 회색으로 죽이기"와
"실측 vs 가정 구분해 보여주기"가 된다. 추가 메시도, 추가 정점 속성도 필요 없다.

폐색 시 위험 심근량(LV 147.6 g 기준): LM 79.0 g (53.5 %), 근위 LAD 45.7 (31.0), 중간 LAD 43.7 (29.6),
원위 LAD 29.6 (20.0), 근위 LCx 33.3 (22.6), 근위·중간 RCA 66.9 (45.3).

**UI에 반드시 같이 띄울 것:** 이 환자 심근의 **65.3 %가 보이는 혈관에서 25 mm보다 멀다** — 즉 상당 부분이 고랑
사전정보로 배정됐고, 특히 RCA 영역은 대부분(657k vs 19k) 가정이다. 1009에서 PDA가 안 보였기 때문이다.
이게 화면에서 연한 색으로 그냥 보인다는 점이 이 앱의 교육적 강점이다. 숨기지 말 것.

## 6. 마일스톤

1. **M1 돌아가는 것** — 임포트(01·02·03) → 부위 스폰 → 궤도 카메라 → 절단 슬라이더. UI는 C++ 디버그 키/온스크린 텍스트.
   **완료 기준**: 좌우 검수 통과, 절단면이 단면으로 보임, 60 fps.
2. **M2 상호작용** — 부위 토글/격리/분해, 클릭 → 이름 + 출처 배지.
3. **M3 관류** — 영역 토글, 혈관 클릭 → 영역 회색 + 위험 심근량 + 실측/가정 표시.
4. **M4 UI** — UMG. C++이 API를 전부 노출하므로 레이아웃만.
5. **M5 퀴즈** — 이름 맞히기, 폐색 부위 ↔ 벽운동 이상 연결.

## 7. 알려진 취약점 (초기 빌드에서 깨질 곳)

- `01`의 Interchange 파이프라인 프로퍼티 이름, `DataTableFunctionLibrary.fill_data_table_from_csv_string`
- `02`의 `MaterialExpressionCustom` 프로퍼티(`inputs`/`code`/`output_type`), `MaterialProperty` 열거자 이름
- `03`의 `EditorLevelLibrary` / `EditorActorSubsystem` (5.x에서 이동이 잦음)
- 레거시 Input 바인딩: 프로젝트가 Enhanced Input만 쓰도록 설정돼 있으면 `DefaultInput.ini`가 무시된다
  (`DefaultEngine.ini`에서 `DefaultPlayerInputClass`/`DefaultInputComponentClass` 확인)

스크립트는 단계마다 로그를 찍으므로 어디서 멈췄는지 바로 나온다. 이름이 바뀐 것뿐이면 그 줄만 고친다.

## 8. 라이선스

형상은 MM-WHS 공개 연구용 CT에서 나왔다. **메시 재배포 금지 → 지오메트리가 들어간 패키지 빌드 공개 배포 불가.**
교내 설치·시연·스크린샷·영상은 가능. 이 문장은 `unreal_manifest.json`의 `licence`에 있고 앱 안에도 띄운다.
