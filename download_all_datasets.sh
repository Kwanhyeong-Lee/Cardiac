#!/bin/bash
# ============================================================
# Cardiac Digital Twin — 전체 데이터셋 다운로드 스크립트
# ============================================================
# 실행 방법: WSL Ubuntu 또는 Windows Python 환경에서
#   bash download_all_datasets.sh
#
# 각 데이터셋마다 다음을 명시합니다:
#   - 출처 (연구기관, 저자)
#   - 대상 인구집단 (인종, 국가, 병원)
#   - 라이선스
#   - 용도 (어떤 구조물을 보완하는지)
#   - 크기
# ============================================================
set -e

# Public datasets live outside the repository. Windows D:\data is /mnt/d/data under WSL;
# override the root with CARDIAC_DATA (HANDOVER.md section 3).
BASE_DIR="${CARDIAC_DATA:-/mnt/d/data}/external_datasets"
mkdir -p "$BASE_DIR"
cd "$BASE_DIR"

echo "============================================================"
echo " Cardiac Digital Twin — 데이터셋 다운로드"
echo " 총 8개 데이터소스 | 다양한 인구집단 커버"
echo "============================================================"

# ============================================================
# [1] STACOM2025 / Public Cardiac CT Dataset — LAA + Coronary + RV
# ============================================================
# 출처: Technical University of Denmark (DTU) + Rigshospitalet Copenhagen
# 저자: Bjørn Hansen, Jonas Pedersen, Klaus F. Kofoed, Oscar Camara,
#       Rasmus R. Paulsen, Kristine Sørensen
# 논문: "A Public Cardiac CT Dataset Featuring the Left Atrial Appendage"
#       STACOM 2025 (MICCAI workshop), arXiv:2510.06090
# 인구집단: 덴마크 코펜하겐 (Rigshospitalet) 환자, 주로 Northern European
#          CCTA 촬영 대상 → 관상동맥질환 의심 환자군
# 라이선스: MIT (labels) + ImageCAS 원본은 CC BY-NC-SA 4.0
# 크기: 576 MB (labels) + ImageCAS CTA 원본 ~200 GB (별도)
# Labels: 0=BG, 1=Myo, 2=LA, 3=LV, 4=RA, 5=RV, 6=Aorta, 7=PA,
#         8=LAA, 9=Coronary, 10=PV
# 구조물 커버: LAA(#3.7), Coronary(#3.6), RV(#3.8), PV
# 검증 완료: 998개 세그멘테이션, 685개 complete LAA
# ============================================================
echo ""
echo "[1/8] STACOM2025 — LAA + Coronary + RV + PV labels"
echo "     출처: DTU + Rigshospitalet Copenhagen (덴마크)"
echo "     인구: Northern European, CCTA 환자"
mkdir -p "$BASE_DIR/01_STACOM2025_PublicCardiacCT"
cd "$BASE_DIR/01_STACOM2025_PublicCardiacCT"

if [ ! -f "ImageCAS-STACOM2025-labels.zip" ]; then
    echo "     다운로드: 576 MB..."
    wget -q --show-progress \
        "https://people.compute.dtu.dk/rapa/STACOM2025/ImageCAS-STACOM2025-02-10-2025.zip" \
        -O ImageCAS-STACOM2025-labels.zip
    echo "     → 완료"
else
    echo "     → 이미 다운로드됨"
fi

if [ ! -d "segmentations" ]; then
    echo "     압축 해제 중..."
    unzip -q ImageCAS-STACOM2025-labels.zip
    mv ImageCAS-STACOM2025-02-10-2025/* . 2>/dev/null
    rmdir ImageCAS-STACOM2025-02-10-2025 2>/dev/null
fi

# GitHub repo (scripts + documentation)
if [ ! -d "github_repo" ]; then
    echo "     GitHub repo 클론..."
    git clone --depth 1 https://github.com/Bjonze/Public-Cardiac-CT-Dataset.git github_repo 2>/dev/null || true
fi

cat > SOURCE_INFO.txt << 'EOF'
# STACOM2025 / Public Cardiac CT Dataset
# =======================================
# 출처: Technical University of Denmark (DTU) + Rigshospitalet Copenhagen
# 저자: Bjørn Hansen, Jonas Pedersen, Klaus F. Kofoed, Oscar Camara,
#       Rasmus R. Paulsen, Kristine Sørensen
# 논문: arXiv:2510.06090 (STACOM 2025 @ MICCAI)
# 인구집단: 덴마크 코펜하겐 (Northern European), CCTA 환자
# 라이선스: MIT (labels) + CC BY-NC-SA 4.0 (ImageCAS 원본)
# 크기: 576 MB (labels), ~200 GB (CTA 원본, Kaggle 별도)
# Labels: 0=BG,1=Myo,2=LA,3=LV,4=RA,5=RV,6=Aorta,7=PA,8=LAA,9=Coronary,10=PV
# 용도: LAA, Coronary artery, RV, Pulmonary vein 세그멘테이션
# 한계: 원본 CTA 이미지는 Kaggle ImageCAS에서 별도 다운로드 필요
EOF

# ============================================================
# [2] MM-WHS (Multi-Modality Whole Heart Segmentation)
# ============================================================
# 출처: Fudan University (복단대학교, 중국 상하이)
# 저자: Xiahai Zhuang et al.
# 논문: "Multi-scale patch and multi-modality atlases for whole heart
#        segmentation of MRI" Medical Image Analysis 2016
# 인구집단: 중국 상하이 환자 (East Asian)
#          CT 20 cases + MRI 20 cases
# 라이선스: 학술용 (비상업)
# 크기: ~2 GB (이미 보유)
# Labels: 205=Myo, 420=LA, 500=LV wall, 550=LV cavity,
#         600=RA, 620=RV(결함!), 820=Aorta, 850=PA
# 한계: RV(label 620)이 모든 case에서 0 voxels — 데이터셋 결함
# ============================================================
echo ""
echo "[2/8] MM-WHS — 이미 보유 (${CARDIAC_DATA:-/mnt/d/data}/MM-WHS/)"
echo "     출처: Fudan University, 상하이 (중국)"
echo "     인구: East Asian (중국), CT+MRI 각 20 cases"
echo "     → 이미 다운로드됨: ${CARDIAC_DATA:-/mnt/d/data}/MM-WHS/"

mkdir -p "$BASE_DIR/02_MMWHS"
cat > "$BASE_DIR/02_MMWHS/SOURCE_INFO.txt" << 'EOF'
# MM-WHS (Multi-Modality Whole Heart Segmentation)
# =================================================
# 출처: Fudan University, 상하이, 중국
# 저자: Xiahai Zhuang et al.
# 논문: Medical Image Analysis 2016
# 인구집단: East Asian (중국 상하이), CT 20 + MRI 20 cases
# 라이선스: 학술용 (비상업)
# 경로: D:\data\MM-WHS\ (CARDIAC_DATA)
# Labels: 205=Myo,420=LA,500=LV wall,550=LV cavity,600=RA,620=RV,820=Aorta,850=PA
# 한계: RV(label 620) 모든 case에서 0 voxels — 데이터셋 수준 결함
# 사용 case: 1009 (현재 Digital Twin 대상)
EOF

# ============================================================
# [3] ACDC (Automated Cardiac Diagnosis Challenge)
# ============================================================
# 출처: CREATIS, INSA-Lyon + University Hospital of Dijon (프랑스)
# 저자: Olivier Bernard et al.
# 논문: "Deep Learning Techniques for Automatic MRI Cardiac
#        Multi-structures Segmentation and Diagnosis" IEEE TMI 2018
# 인구집단: 프랑스 디종 (Western European)
#          100 MRI cases, 5 병리군 (NOR/MINF/DCM/HCM/RV)
# 라이선스: CC BY-NC-SA 4.0
# 크기: ~2 GB
# 구조물: LV endo, LV epi, RV (cardiac MRI)
# 용도: RV 형태 참조, 병리별 심장 형태 비교
# ============================================================
echo ""
echo "[3/8] ACDC — Cardiac MRI, 프랑스"
echo "     출처: CREATIS INSA-Lyon + University Hospital Dijon"
echo "     인구: Western European (프랑스), 100 MRI"
mkdir -p "$BASE_DIR/03_ACDC"

cat > "$BASE_DIR/03_ACDC/SOURCE_INFO.txt" << 'EOF'
# ACDC (Automated Cardiac Diagnosis Challenge)
# =============================================
# 출처: CREATIS, INSA-Lyon + University Hospital of Dijon, 프랑스
# 저자: Olivier Bernard et al.
# 논문: IEEE TMI 2018
# 인구집단: Western European (프랑스 디종), 100 MRI cases
# 병리군: NOR(20), MINF(20), DCM(20), HCM(20), RV abnormal(20)
# 라이선스: CC BY-NC-SA 4.0
# 다운로드: https://humanheart-project.creatis.insa-lyon.fr/database/
# 크기: ~2 GB
# Labels: LV endocardium, LV epicardium, RV
# 용도: RV 형태 참조, 병리별 심장 비교 (특히 DCM, HCM)
# 주의: 다운로드 시 CREATIS 계정 필요
EOF

echo "     → 수동 다운로드 필요: https://humanheart-project.creatis.insa-lyon.fr/database/"

# ============================================================
# [4] M&Ms (Multi-Centre, Multi-Vendor & Multi-Disease)
# ============================================================
# 출처: 6개 병원 (스페인 4 + 독일 1 + 캐나다 1)
# 저자: Victor M. Campello et al.
# 논문: "Multi-Centre, Multi-Vendor and Multi-Disease Cardiac
#        Segmentation" IEEE TMI 2021
# 인구집단: 다인종 (Southern European 위주 + North American)
#          스페인: Hospital Clínic Barcelona, Hospital de la Santa Creu i Sant Pau,
#                 Hospital Universitario Virgen de la Arrixaca, Sagessa
#          독일: Universitätsklinikum Hamburg-Eppendorf
#          캐나다: Sunnybrook Health Sciences Centre (토론토)
# 라이선스: CC BY-NC-SA 4.0
# 크기: ~12 GB (345 cases)
# 구조물: LV, RV, MYO (cardiac MRI, 3 vendors: Siemens/GE/Philips)
# 용도: Multi-vendor 일반화 검증, 다인종 RV 형태 비교
# ============================================================
echo ""
echo "[4/8] M&Ms — Multi-Centre Cardiac MRI"
echo "     출처: 스페인(4) + 독일(1) + 캐나다(1) 병원"
echo "     인구: Multi-ethnic (Southern European + North American)"
mkdir -p "$BASE_DIR/04_MandMs"

cat > "$BASE_DIR/04_MandMs/SOURCE_INFO.txt" << 'EOF'
# M&Ms (Multi-Centre, Multi-Vendor & Multi-Disease)
# ====================================================
# 출처: 6개 병원
#   스페인: Hospital Clínic Barcelona, Sant Pau, Virgen de la Arrixaca, Sagessa
#   독일: Universitätsklinikum Hamburg-Eppendorf
#   캐나다: Sunnybrook Health Sciences Centre, Toronto
# 저자: Victor M. Campello et al.
# 논문: IEEE TMI 2021
# 인구집단: Multi-ethnic (Southern European + North American + Northern European)
# 라이선스: CC BY-NC-SA 4.0
# 다운로드: https://www.ub.edu/mnms/
# 크기: ~12 GB (345 cases, 3 MRI vendors)
# Labels: LV, RV, Myocardium
# 용도: 다인종/다기관 RV 형태 일반화 검증
EOF

echo "     → 수동 다운로드 필요: https://www.ub.edu/mnms/"

# ============================================================
# [5] ImageCAS — Coronary Artery CTA (원본 이미지)
# ============================================================
# 출처: 중국 여러 병원 (Nanjing Medical University 주도)
# 저자: Xiaowei Xu et al.
# 논문: "ImageCAS: A Large-Scale Dataset and Benchmark for Coronary
#        Artery Segmentation based on Computed Tomography Angiography"
# 인구집단: East Asian (중국), ~1000 CTA scans
# 라이선스: CC BY-NC-SA 4.0
# 크기: ~200 GB (Kaggle)
# 구조물: Coronary arteries (3D annotation)
# 용도: Coronary artery 3D geometry 추출
# 주의: 대용량 — 선별적 다운로드 권장
# ============================================================
echo ""
echo "[5/8] ImageCAS — Coronary Artery CTA 원본"
echo "     출처: Nanjing Medical University (중국)"
echo "     인구: East Asian (중국), ~1000 CTA"
echo "     크기: ~200 GB — 선별 다운로드 권장"
mkdir -p "$BASE_DIR/05_ImageCAS"

cat > "$BASE_DIR/05_ImageCAS/SOURCE_INFO.txt" << 'EOF'
# ImageCAS — Coronary Artery CTA
# ================================
# 출처: Nanjing Medical University + 협력 병원 (중국)
# 저자: Xiaowei Xu et al.
# 인구집단: East Asian (중국), ~1000 CTA scans
# 라이선스: CC BY-NC-SA 4.0
# 다운로드: https://www.kaggle.com/datasets/xiaoweixumedicalai/imagecas
# 크기: ~200 GB (전체) — 용량 주의, 선별적 다운로드 권장
# Labels: Coronary artery binary segmentation
# 용도: [1] STACOM2025 labels와 매칭하여 LAA/coronary/RV 추출
#        [2] 독립적으로 coronary artery 3D geometry 확보
# 주의: Kaggle 계정 + API key 필요
#   pip install kaggle
#   kaggle datasets download -d xiaoweixumedicalai/imagecas
# 선별 다운로드 (50 cases만):
#   kaggle datasets download -d xiaoweixumedicalai/imagecas -f <filename>
EOF

echo "     → Kaggle 수동 다운로드: https://www.kaggle.com/datasets/xiaoweixumedicalai/imagecas"

# ============================================================
# [6] MVAA 2026 — Mitral Valve Anatomy Analysis
# ============================================================
# 출처: Multi-center (유럽/미국 공동, MICCAI affiliated)
# 인구집단: 아직 구체 공개 안 됨 (도전과제 진행 중)
#          Expected: Western European + North American
# 데이터: CT + 3D TEE + Surgical video
# 라이선스: Challenge-specific (등록 필요)
# 크기: TBD
# 구조물: Mitral valve leaflets, annulus, chordae
# 용도: Valve geometry 실측 데이터로 parametric valve 교체
# ============================================================
echo ""
echo "[6/8] MVAA 2026 — Mitral Valve Challenge"
echo "     출처: MICCAI affiliated multi-center"
echo "     인구: Western European + North American (예상)"
mkdir -p "$BASE_DIR/06_MVAA2026"

cat > "$BASE_DIR/06_MVAA2026/SOURCE_INFO.txt" << 'EOF'
# MVAA 2026 — Mitral Valve Anatomy Analysis
# ==========================================
# 출처: MICCAI affiliated challenge (multi-center, 유럽/미국)
# 인구집단: TBD (Western European + North American 예상)
# 데이터: CT + 3D TEE + Surgical video
# 라이선스: Challenge-specific (등록 필요)
# 등록: https://www.codabench.org/competitions/15662/
#   1. Codabench 계정 생성
#   2. 'Participate' 클릭
#   3. Training data 다운로드
# 크기: TBD
# Labels: Mitral valve leaflets, annulus, chordae tendineae
# 용도: Parametric MV를 실측 geometry로 교체
# 한계: 현재 challenge 진행 중 — training set만 공개
EOF

echo "     → 수동 등록: https://www.codabench.org/competitions/15662/"

# ============================================================
# [7] Cardiac Atlas Project — Shape Models + 4D Flow
# ============================================================
# 출처: Auckland Bioengineering Institute (뉴질랜드)
#       + King's College London (영국) + 다수 협력기관
# 저자: Alistair Young et al.
# 인구집단:
#   MESA: Multi-Ethnic Study of Atherosclerosis (미국)
#         White, African American, Hispanic, Chinese American
#         6,814 participants (45-84세)
#   DETERMINE: Defibrillators to Reduce Risk (미국)
#   Sunnybrook: 캐나다 토론토
# 라이선스: 다양 (각 sub-dataset별)
# 구조물: LV/RV PCA shape models, clinical modes
# 용도: [1] 심장 형태 통계모델 (인종별 정상범위)
#        [2] 4D Flow MRI로 CFD 검증
# ============================================================
echo ""
echo "[7/8] Cardiac Atlas Project — Shape Models"
echo "     출처: Auckland (NZ) + King's College London (UK)"
echo "     인구: MESA(Multi-ethnic US), DETERMINE, Sunnybrook(CA)"
mkdir -p "$BASE_DIR/07_CardiacAtlas"

cat > "$BASE_DIR/07_CardiacAtlas/SOURCE_INFO.txt" << 'EOF'
# Cardiac Atlas Project
# ======================
# 출처: Auckland Bioengineering Institute (뉴질랜드)
#       + King's College London (영국)
# 인구집단:
#   MESA (Multi-Ethnic Study of Atherosclerosis):
#     미국 6,814명 (45-84세)
#     인종: White, African American, Hispanic, Chinese American
#     → 인종별 정상 심장 형태 참조에 매우 유용
#   DETERMINE: 미국 (ICD 적응증 환자)
#   Sunnybrook: 캐나다 토론토 (45 cases, healthy+pathology)
# 라이선스: 각 sub-dataset별 상이 (학술용)
# URL: https://www.cardiacatlas.org/
# Datasets:
#   - LV PCA modes: https://www.cardiacatlas.org/left-ventricular-modes/
#   - RVLV PCA modes: https://www.cardiacatlas.org/biventricular-modes/
#   - Sunnybrook: https://www.cardiacatlas.org/sunnybrook-cardiac-data/
#   - MESA: https://www.cardiacatlas.org/mesa/ (NHLBI 승인 필요)
# 용도: 인종별 심장 형태 정상범위, 4D Flow MRI CFD 검증
# 주의: MESA 데이터는 NHLBI(미국 국립심폐혈액연구소) 승인 필요
EOF

echo "     → 일부 수동 접근: https://www.cardiacatlas.org/"

# ============================================================
# [8] PhysioNet — eICU-CRD + MIMIC-IV (이미 사용 중)
# ============================================================
# 출처:
#   eICU-CRD: Philips eICU Research Institute (미국 전역 208 병원)
#   MIMIC-IV: MIT + Beth Israel Deaconess (미국 보스턴)
# 인구집단:
#   eICU: 미국 전역 (다인종, 다기관)
#   MIMIC: 미국 보스턴 (도시 3차병원)
# 라이선스: PhysioNet Credentialed Health Data License 1.5.0
# 크기: eICU ~7 GB, MIMIC-IV ~50 GB
# 용도: pH-PINN 외부 검증 (약물 반응 예측)
# ============================================================
echo ""
echo "[8/8] PhysioNet — eICU + MIMIC (이미 사용 중)"
echo "     출처: eICU(미국 전역 208병원), MIMIC(보스턴)"
echo "     인구: Multi-ethnic US (eICU), Urban US (MIMIC)"
mkdir -p "$BASE_DIR/08_PhysioNet"

cat > "$BASE_DIR/08_PhysioNet/SOURCE_INFO.txt" << 'EOF'
# PhysioNet — eICU-CRD + MIMIC-IV
# ==================================
# eICU-CRD 2.0:
#   출처: Philips eICU Research Institute
#   인구집단: 미국 전역 208개 병원 (2014-2015), 다인종/다기관
#   라이선스: PhysioNet Credentialed Health Data License 1.5.0
#   URL: https://physionet.org/content/eicu-crd/2.0/
#   크기: ~7 GB
#   사용: pH-PINN 약물 반응 검증 (2,720 episodes, AUC 0.837)
#
# MIMIC-IV 3.1:
#   출처: MIT Laboratory for Computational Physiology
#         + Beth Israel Deaconess Medical Center (보스턴)
#   인구집단: 미국 보스턴 도시 3차병원 (2008-2022)
#   라이선스: PhysioNet Credentialed Health Data License 1.5.0
#   URL: https://physionet.org/content/mimiciv/3.1/
#   크기: ~50 GB
#   사용: Renal PINN 확장 예정
#
# 주의: PhysioNet credential 필요 (CITI training 이수)
EOF

echo "     → 이미 접근 가능"

# ============================================================
# 인구집단 다양성 요약
# ============================================================
echo ""
echo "============================================================"
echo " 인구집단 다양성 요약"
echo "============================================================"
echo ""
echo "  East Asian (중국):  MM-WHS, ImageCAS"
echo "  Northern European:  STACOM2025 (덴마크)"
echo "  Western European:   ACDC (프랑스), M&Ms 일부 (스페인/독일)"
echo "  North American:     MESA (다인종), MIMIC (보스턴),"
echo "                      M&Ms 일부 (캐나다), eICU (전미)"
echo "  Multi-ethnic:       MESA (White/AA/Hispanic/Chinese-Am)"
echo ""
echo "  ※ 한국인/Korean 특화 데이터: 현재 공개 데이터 없음"
echo "    → 추후 서울아산/삼성서울/세브란스 등 국내 데이터 확보 필요"
echo "============================================================"

# ============================================================
# 전체 요약
# ============================================================
echo ""
echo "============================================================"
echo " 다운로드 요약"
echo "============================================================"
echo ""
echo "  [1] STACOM2025 labels    — 자동 다운로드 (576 MB)"
echo "  [2] MM-WHS              — 이미 보유"
echo "  [3] ACDC                — 수동 (CREATIS 계정)"
echo "  [4] M&Ms                — 수동 (UB 신청)"
echo "  [5] ImageCAS CTA 원본   — 수동 (Kaggle, ~200 GB)"
echo "  [6] MVAA 2026           — 수동 (Codabench 등록)"
echo "  [7] Cardiac Atlas       — 수동 (일부 NHLBI 승인)"
echo "  [8] PhysioNet           — 이미 접근 가능"
echo ""
echo "  → 각 디렉토리의 SOURCE_INFO.txt에 출처/인구/라이선스 상세"
echo "============================================================"
