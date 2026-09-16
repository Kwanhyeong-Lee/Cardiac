#!/bin/bash
# ============================================================
# pimpleFoam 실시간 안정성 모니터 (발산 조기 감지)
# 사용법: bash monitor_cfd.sh [케이스경로]
# ============================================================
CASE="${1:-$HOME/lv_cfd_anatomical}"
LOG="$CASE/log.pimpleFoam_v2"
[ -f "$LOG" ] || { echo "로그 없음: $LOG"; exit 1; }

echo "모니터 대상: $LOG   (Ctrl+C 종료)"
echo "판단 기준: maxCo<0.5 양호 / >1.0 연속이면 발산 징후,"
echo "          deltaT가 1e-10 이하로 축소되면 즉시 중단 권장"
echo "------------------------------------------------------------"

while true; do
    T=$(grep "^Time = "        "$LOG" | tail -1)
    CO=$(grep "Courant Number"  "$LOG" | tail -1)
    DT=$(grep "deltaT = "       "$LOG" | tail -1)
    CUM=$(grep "cumulative"      "$LOG" | tail -1)
    printf "\r%-90s" " "
    echo ""
    echo "[$(date +%H:%M:%S)]"
    echo "  $T"
    echo "  $CO"
    echo "  $DT"
    echo "  $CUM"

    # 발산 자동 감지: deltaT 지수부가 -10 이하
    if echo "$DT" | grep -qiE "e-1[0-9]|e-[2-9][0-9]"; then
        echo "  ⚠ deltaT 붕괴 감지 — 발산 가능성. 프로세스 확인/중단 권장:"
        echo "     pkill -f pimpleFoam   후  tail -40 $LOG"
    fi
    if grep -q "^End$" "$LOG"; then
        echo "  ✓ 시뮬레이션 정상 종료(End). 동기화 단계로 진행하세요."
        break
    fi
    if ! pgrep -f pimpleFoam >/dev/null; then
        echo "  ✗ pimpleFoam 프로세스 종료됨(End 없음) — 발산/에러 의심. tail -40 $LOG 확인"
        break
    fi
    sleep 15
done
