#!/bin/bash
# ============================================================
# 환자 내 RV 추출 파이프라인 (TotalSegmentator -> STL -> CFD frame)
# ============================================================
# STATUS §19-D 결론: 교차환자 STACOM RV는 해부학적 부적합(RV-LV 35mm gap).
# 정답 = 동일 환자(Case 1009) CT에 TotalSegmentator로 in-patient RV 분할.
#
# 실행 (WSL Ubuntu, GPU 권장):
#   bash ".../run_rv_extraction.sh"
# 요구: TotalSegmentator, python(nibabel scikit-image scipy trimesh)
# ============================================================
set -uo pipefail

# ── 경로 자동 감지 ──
PROJ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# MM-WHS CT는 저장소 밖. 기본 /mnt/d/data (= Windows D:\data), CARDIAC_DATA로 바꾼다 (HANDOVER.md §3).
DATA="${CARDIAC_DATA:-/mnt/d/data}"
CT="$DATA/MM-WHS/ct_train/ct_train_1009_image.nii.gz"
SEG_DIR="$PROJ/totalseg_output"

echo "PROJ    = $PROJ"
echo "CT      = $CT"
echo "SEG_DIR = $SEG_DIR"

# ── 사전 점검 ──
[ -f "$CT" ] || { echo "✗ CT 없음: $CT  (사용자명/경로 확인)"; exit 1; }
command -v TotalSegmentator >/dev/null || { echo "✗ TotalSegmentator 미설치 → pip install TotalSegmentator"; exit 1; }
python3 -c "import nibabel, skimage, scipy, trimesh" 2>/dev/null || \
  { echo "✗ 파이썬 의존성 부족 → pip install nibabel scikit-image scipy trimesh --break-system-packages"; exit 1; }
[ -f "$PROJ/mm_to_cfd_transform.npy" ] || { echo "✗ mm_to_cfd_transform.npy 없음 (STACOM 정합 세션 산출물 필요)"; exit 1; }

# ── 1. TotalSegmentator (heartchambers_highres) ──
if [ -f "$SEG_DIR/heart_ventricle_right.nii.gz" ]; then
    echo "[1] RV mask 이미 존재 → TotalSegmentator 스킵"
else
    echo "[1] TotalSegmentator 실행 (heartchambers_highres)..."
    DEVICE="gpu"; command -v nvidia-smi >/dev/null || DEVICE="cpu"
    echo "    device=$DEVICE"
    TotalSegmentator -i "$CT" -o "$SEG_DIR" --task heartchambers_highres --device "$DEVICE" \
      || { echo "✗ TotalSegmentator 실패 (VRAM 부족 시 --device cpu 재시도)"; exit 1; }
fi

echo "    출력 구조:"; ls "$SEG_DIR"/*.nii.gz 2>/dev/null | xargs -n1 basename | sed 's/^/      /'

# ── 2. RV mask -> STL -> CFD frame + 검증 ──
echo "[2] RV STL 추출 + CFD 좌표계 배치 + 검증..."
python3 "$PROJ/extract_rv_totalseg.py" --project "$PROJ" --seg_dir "$SEG_DIR"

echo ""
echo "완료. 산출물:"
echo "  - lv_cfd_anatomical/constant/triSurface/rv_insegment_registered.stl"
echo "  - rv_insegment_report.json  (프레임 검증 + RV-LV 인접거리)"
echo ""
echo "다음: assemble_cardiac_geometry.py 의 RV 참조를 rv_stacom → rv_insegment_registered 로 교체."
