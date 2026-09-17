# 친구 공유용 대표 이미지 8장 (2026-09-16)

- `01_pHPINN_digital_twin_overview.png` — ① pH-PINN 심장 디지털 트윈 — 해부 → 물리 제약 신경망 → 추론 (Paper A 그래픽 초록)
- `02_LV_bloodpool_with_valves_render.png` — ② 좌심실 혈액풀(반투명)과 재배치한 승모판·대동맥판 — Blender 렌더
- `03_v4_printable_ventricle_exterior.png` — ③ 출력용 심실 v4 외형 — CT 심근(빨강), 방실면 판(회색), 파라메트릭 판막(크림)
- `04_v4_cutaway_papillary_chordae.png` — ④ 절개면 — 환자 본인의 육주·유두근과 승모판으로 가는 건삭
- `05_v4_cutaway_trabeculae.png` — ⑤ 반대쪽 절개면 — CT에서 되찾은 육주 구조
- `06_midcavity_slab_two_papillary_muscles.png` — ⑥ 중간 높이 단면 슬랩 — 벽 고리 안의 두 유두근
- `07_flow_phantom_core_in_mould.png` — ⑦ 실리콘 유동 팬텀 — PVA 코어(혈액풀+포트)와 주형 상자
- `08_CFD_results_openfoam.png` — ⑧ 같은 심실의 CFD(OpenFOAM) — 유량·압력·PV 루프
- `00_overview_8up.png` — 8장 한 눈에.

한 줄 소개: 공개 CT 세그멘테이션(MM-WHS case 1009) 한 장에서 판막·유두근·육주까지 있는 출력용 좌심실, 같은 형상의 실리콘 유동 팬텀 몰드, CFD 도메인을 스크립트로 만들었고, 별도로 ICU 신호에서 심장 역학을 추정하는 물리 제약 신경망(pH-PINN)을 만들어 검증했다.

솔직 표기: 판막 첨판·판·건삭 경로는 파라메트릭(환자 것 아님). 벽·내막·육주·유두근은 환자 CT. 아직 실물 출력·주형은 안 했음.

공유 범위: 이미지는 공유 가능. STL/VTP 형상 파일과 데이터(MM-WHS, MIMIC 등)는 라이선스상 공유 금지.
