# TASK_BATCH — MM-WHS 20례 형상 파이프라인 (GPU 컴퓨터, 32 GB)

전제: `check_setup.py`에서 **geometry READY** (MM-WHS 20/20, 패키지 import OK). 샌드박스(3 GB)에서는 케이스당 ~15분이었고
1001 한 례만 끝까지 돌았다. 여기서는 20례 전부. 순수 CPU 작업이라 GPU는 안 쓴다.

## Claude Code 프롬프트 (GPU 컴퓨터, WSL, `cardiac` 로 venv 켠 뒤)

```
fusion_ready/batch_cases.py 로 MM-WHS 20례를 돌려 줘. 규칙: STL·npz·nii 는 절대 커밋하지 않는다. --force 금지.

0. python tools/setup/check_setup.py 에서 geometry 가 READY 인지 먼저 확인. 아니면 멈추고 보고.
1. 고해상도 설정(32 GB라 가능):  export TARGET_MYO=1500000 TARGET_BLOOD=800000 TAUBIN=15
2. 오래 걸리니(20례 x 5-15분) 끊겨도 살아남게 백그라운드로:
   cd fusion_ready && nohup python batch_cases.py > ../batch_$(date +%Y%m%d_%H%M).log 2>&1 &
   진행은 tail -f 로 보고, 케이스별 로그는 CT/cases/<id>/logs/. 중간에 끊겨도 다시 실행하면 끝난 단계는 건너뛴다.
3. 끝나면 python batch_cases.py --summary-only 로 CT/cases/SUMMARY.md / SUMMARY.csv / summary.png 를 갱신하고,
   SUMMARY.md 를 보여주면서 다음을 정리해 줘:
   - 실패한 케이스와 단계, 로그 마지막 20줄에서 본 원인
   - 대동맥 HU 가 300 미만인 케이스(조영이 약해 관상동맥 추출을 믿기 어려움) 목록
   - 우세형(PDA 출처)별 분포, 관상동맥 길이·관류 영역 질량의 범위
4. 커밋할 것만 골라서: CT/cases/SUMMARY.md, SUMMARY.csv, summary.png, 그리고 케이스별 *.json / *.md.
   케이스별 PNG 는 20례 x 5장이면 저장소가 무거워지니 대표 2-3례만 (어느 례를 골랐는지와 이유를 커밋 본문에).
   git status 로 .stl .npz .ply .nii.gz 가 하나도 안 잡히는지 확인한 뒤 커밋·푸시.
   메시지: "Geometry: MM-WHS 20-case batch on the 3060 box (summary + per-case reports)"
```

## 알아둘 것

- **1009**도 배치에서는 케이스별 레이아웃(`CASE_LAYOUT=cases`)으로 한 번 더 돈다 — 기존 frame-A 산출물(`CT/`)은 건드리지 않는다.
- **메모리**: 0.35 mm급 CT에서 vesselness 단계가 가장 무겁다. WSL이 16 GB만 보이면 `.wslconfig`(SETUP.md B-4).
- **결과 해석의 한계는 그대로 적는다**: IVC는 동맥기라 대부분 없음, 대동맥궁은 FOV 밖인 케이스가 많음,
  관상동맥은 근위–중간부가 신뢰 구간. SUMMARY에 새로 보이는 패턴이 있으면 그것도 이 한계와 같이 보고할 것.
