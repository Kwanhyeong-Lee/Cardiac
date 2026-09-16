# 프리프린트 제출 — 오늘 밤 바로 (arXiv 1순위 / TechRxiv 대안)

## 업로드 파일
- `pH_PINN_JBHI_arXiv_source.tar.gz`  ← arXiv용 LaTeX 소스(main.tex + figures/). IEEEtran/패키지는 arXiv에 내장돼 있어 그대로 컴파일됨. 참고문헌은 inline이라 .bbl 불필요.
- (TechRxiv로 가면 PDF `pH_PINN_JBHI_main.pdf` 하나만 올리면 됨)

## 메타데이터 (복붙용)

**Title**
Port-Hamiltonian Physics-Informed Neural Networks for Cardiac Hemodynamic Inference with Architecturally Guaranteed Energy Consistency

**Authors**  Kwanhyeong Lee (Soonchunhyang University College of Medicine) — sole author
**Email**  alex026376@sch.ac.kr

**arXiv categories**
- Primary: eess.SP  (Signal Processing)
- Cross-list: cs.LG , q-bio.QM   (원하면 physics.med-ph 추가)

**License**  arXiv non-exclusive license to distribute (기본값 권장 — IEEE와 충돌 없음)

**Comments 필드** (여기에 코드 링크·페이지수)
`8 pages, 4 figures. Code and reproducibility package: https://github.com/<YOUR-ID>/pH-PINN-cardiac . Submitted to IEEE J-BHI.`

**Abstract** (plain text, 그대로 붙여넣기)
Cardiac digital twins aim to individualize cardiovascular care, but most approaches model anatomy, hemodynamics, and parameter inference in isolation and, in the machine-learning setting, give no guarantee that the physiological states they predict are physically admissible. We present a port-Hamiltonian physics-informed neural network (pH-PINN) framework that couples two components: (1) a patient-anchored multi-structure reconstruction combining patient-specific CT segmentation with atlas-based registration (13 structures, 957,608 mesh elements); and (2) a Windkessel-coupled PINN in which cardiovascular energy balance is imposed as an architectural inductive bias through a scalar port-Hamiltonian dissipation R(x)=r_diss*I, with r_diss fixed by the Windkessel characteristic impedance Z_c rather than fit freely. Evaluated on the eICU (n=3,991) and MIMIC-IV (n=5,851) databases -- keeping directly measured quantities strictly separate from surrogate-derived indices -- the pH-PINN attained R^2=0.975 for cardiac output and R^2=0.951 for end-systolic elastance, distribution overlaps of 80.5% (stroke volume) and 83.4% (stroke work), and Pearson r=0.916 for systemic vascular resistance (measured via Swan-Ganz catheterization). The Windkessel-PINN bridge recovered physiologically consistent ventricular-arterial coupling (Ea/Ees=0.60) and a complete energy partition: gross mechanical efficiency 64.8% (SW/PVA) and net efficiency 62.3% once the port-Hamiltonian dissipation is subtracted (E_diss=137 mmHg*mL per beat, 2.4% of PVA). In a four-way ablation of matched-capacity models, the hard architectural constraints matched baseline predictive accuracy (R^2 ~ 0.97) while guaranteeing physically valid internal states by construction, whereas identical-capacity unconstrained baselines produced negative energies and non-positive-semidefinite dissipation in up to 100% of test cases. The framework supports non-invasive cardiac digital twins whose internal states respect fundamental energy constraints by construction.

## 올리기 전 30초 결정 2개
1. **GitHub Public 전환** — 프리프린트를 올리는 순간 저자 신원은 어차피 공개됩니다(그리고 JBHI는 single-blind라 익명성 이슈 없음). 그러니 지금 repo를 Public으로 돌리고 위 Comments에 URL을 넣는 게 재현성 시그널 최대화 + 일관됨. (`gh repo edit --visibility public`)
   - Public 싫으면 Comments의 GitHub 줄만 지우면 됨.
2. **서버 선택** — arXiv endorsement 있으면 arXiv, 없거나 애매하면 TechRxiv(무마찰). 한 서버에만 올리세요(중복 금지).

## arXiv 업로드 순서
1. arxiv.org 로그인 → Start New Submission
2. License 선택 → tar.gz 업로드 → arXiv가 자동 컴파일 → **미리보기 PDF 반드시 눈으로 확인**
3. Primary=eess.SP, cross-list cs.LG/q-bio.QM
4. Title/Authors/Abstract/Comments 붙여넣기 → Submit
   - 제출은 오늘 되지만 공개 announce는 다음 영업일 스케줄(마감 ~14:00 ET). 주말이면 지연.

## TechRxiv 업로드 순서 (arXiv 막히면)
1. techrxiv.org 로그인(IEEE 계정) → Upload → PDF(`pH_PINN_JBHI_main.pdf`) 업로드
2. Title/Authors/Abstract/keywords 입력 → 제출 → 짧은 스크리닝 후 공개. endorsement 불필요.

---

# ✅ TechRxiv 상세 (오늘 밤 실제 순서)

**업로드 파일**
- 본문: `pH_PINN_JBHI_main.pdf` (필수)
- 보조자료(선택): `pH_PINN_JBHI_Supplementary.docx` — supporting/supplementary로 함께 올리면 좋음

**단계**
1. techrxiv.org 접속 → 로그인 (IEEE 계정 그대로 사용). 없으면 무료 가입.
2. "Submit"/"New submission" → PDF 업로드
3. 폼 채우기:
   - **Title**: (위 메타데이터 그대로)
   - **Authors**: Kwanhyeong Lee (단독) / 소속 Soonchunhyang University College of Medicine / alex026376@sch.ac.kr
   - **Abstract**: 위 plain-text 초록 붙여넣기
   - **Keywords**: physics-informed neural network; cardiac digital twin; port-Hamiltonian systems; ventricular-arterial coupling; hemodynamic inference; energy dissipation
   - **Category/Subject**: Bioengineering (필요시 Computing and Processing 추가)
   - **License**: CC BY 4.0 (기본값, IEEE와 호환)
   - **Associated/Submitted-to journal**(필드 있으면): IEEE Journal of Biomedical and Health Informatics
   - **Competing interests**: None
   - **Code link**: repo가 Public/push 완료면 description에 GitHub URL, 아니면 오늘은 생략 후 게시 뒤 수정
4. 약관 동의 → Submit → **스크리닝 1~2 영업일** 후 DOI와 함께 공개

**주의**
- Author Consent Form은 *저널(JBHI)* 제출용이지 프리프린트엔 불필요.
- 게시 후 DOI 나오면, 나중에 JBHI 본제출 cover letter/시스템에 "preprint DOI"를 밝히면 됨(IEEE 정책상 정상, 문제 없음).

---

# ⚠️ TechRxiv 임시 제출 중단 → 대안 (오늘 밤)

TechRxiv가 플랫폼 이전으로 제출을 잠시 닫음. 아래 순서로 대체:

1. **arXiv 먼저 시도** (리치 최고). `pH_PINN_JBHI_arXiv_source.tar.gz` 업로드.
   - endorsement 팝업 안 뜨면 진행 (Primary eess.SP, cross-list cs.LG/q-bio.QM).
   - **endorsement 요구하면 → 아래로 이동.**
2. **Preprints.org (MDPI)** — 무마찰·DOI·~1영업일. `pH_PINN_JBHI_main.pdf` + 같은 메타데이터.
   - preprints.org → Submit → PDF 업로드 → Title/Authors/Abstract/Keywords → Subject area(예: Medicine & Pharmacology 또는 Engineering) → License CC BY → Submit.
3. **Research Square** — 동급 대안(무마찰·DOI).
4. **Zenodo** — 즉시 DOI/타임스탬프가 지금 당장 필요할 때. 스크리닝 없음, 단 검색 노출 약함. (arXiv/Preprints와 병행 가능하나 중복 게시는 지양.)

**한 서버에만 최종 게시**. 오늘 확실히 내는 게 목표면 Preprints.org 권장.
