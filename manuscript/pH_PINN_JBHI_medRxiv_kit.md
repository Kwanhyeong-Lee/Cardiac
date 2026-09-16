# medRxiv 제출 키트 — 폼 칸마다 그대로 붙여넣기

## 1) 업로드 파일
- Manuscript (PDF): `pH_PINN_JBHI_main.pdf`
- Supplementary (선택): `pH_PINN_JBHI_Supplementary.docx`

## 2) 기본 필드
- **Article type:** New Results (research article)
- **Subject area / Category:** Health Informatics  *(대안: Cardiovascular Medicine)*
- **Title:**
  Port-Hamiltonian Physics-Informed Neural Networks for Cardiac Hemodynamic Inference with Architecturally Guaranteed Energy Consistency
- **Author (sole / corresponding):** Kwanhyeong Lee — Soonchunhyang University College of Medicine, Republic of Korea — alex026376@sch.ac.kr  *(ORCID 있으면 입력)*
- **Keywords:** physics-informed neural network; cardiac digital twin; port-Hamiltonian systems; ventricular–arterial coupling; hemodynamic inference; energy dissipation

## 3) Abstract (plain text — 그대로 붙여넣기)
Cardiac digital twins aim to individualize cardiovascular care, but most approaches model anatomy, hemodynamics, and parameter inference in isolation and, in the machine-learning setting, give no guarantee that the physiological states they predict are physically admissible. We present a port-Hamiltonian physics-informed neural network (pH-PINN) framework that couples two components: (1) a patient-anchored multi-structure reconstruction combining patient-specific CT segmentation with atlas-based registration (13 structures, 957,608 mesh elements); and (2) a Windkessel-coupled PINN in which cardiovascular energy balance is imposed as an architectural inductive bias through a scalar port-Hamiltonian dissipation R(x)=r_diss*I, with r_diss fixed by the Windkessel characteristic impedance Z_c rather than fit freely. Evaluated on the eICU (n=3,991) and MIMIC-IV (n=5,851) databases -- keeping directly measured quantities strictly separate from surrogate-derived indices -- the pH-PINN attained R^2=0.975 for cardiac output and R^2=0.951 for end-systolic elastance, distribution overlaps of 80.5% (stroke volume) and 83.4% (stroke work), and Pearson r=0.916 for systemic vascular resistance (measured via Swan-Ganz catheterization). The Windkessel-PINN bridge recovered physiologically consistent ventricular-arterial coupling (Ea/Ees=0.60) and a complete energy partition: gross mechanical efficiency 64.8% (SW/PVA) and net efficiency 62.3% once the port-Hamiltonian dissipation is subtracted (E_diss=137 mmHg*mL per beat, 2.4% of PVA). In a four-way ablation of matched-capacity models, the hard architectural constraints matched baseline predictive accuracy (R^2 ~ 0.97) while guaranteeing physically valid internal states by construction, whereas identical-capacity unconstrained baselines produced negative energies and non-positive-semidefinite dissipation in up to 100% of test cases. The framework supports non-invasive cardiac digital twins whose internal states respect fundamental energy constraints by construction.

## 4) 필수 Statements (medRxiv가 요구 — 그대로 붙여넣기)
- **Competing Interest Statement:** The author declares no competing interests.
- **Funding Statement:** The author received no specific funding for this work.
- **Author Declarations / Ethics:** This study used only publicly available, fully de-identified datasets — MIMIC-IV and the eICU Collaborative Research Database (PhysioNet, accessed under their data use agreements), the MM-WHS Challenge dataset, and the STACOM whole-heart atlas. It did not involve new human-subjects research or the collection of identifiable patient data; institutional review board approval was therefore not required (exempt).
- **IRB / oversight question:** Not applicable — secondary analysis of publicly available, de-identified data (IRB exemption).
- **Patient-identifiable information:** None. Only aggregate statistics are reported.
- **Clinical trial?** No — this is not a clinical trial.
- **Data Availability:** All datasets are publicly available (MIMIC-IV and eICU-CRD via PhysioNet; MM-WHS Challenge; STACOM atlas). Model, training, ablation, and figure-generation code plus the derived result files needed to reproduce every figure are provided as a reproducibility package, to be released in a public repository (GitHub/Zenodo) upon acceptance.

## 5) License
- 권장: **CC-BY-NC-ND 4.0** (IEEE 저널 진행 중 재사용/파생 충돌 최소화). CC-BY 4.0도 허용됨.

## 6) 저널 관련 질문
- "Submitted/intended for a journal?" → Yes — **IEEE Journal of Biomedical and Health Informatics**.

## 7) 제출 후
- 스크리너가 위 statement 중 빠진 것 / PII / 카테고리를 물으면 → 이 문서 내용 그대로 회신하면 통과.
- 승인되면 DOI + 공개 링크 이메일 도착. 그 링크만 나한테 주면 최종 점검.

---
## ⬆️ 최종본 안내 (두 버전)
- **프리프린트 업로드용:** `pH_PINN_preprint_fullrefs.pdf` (9쪽, 전체 저자명 + DOI 완비) — 프리프린트는 쪽수 제한 없음.
- **IEEE J-BHI 제출용:** `pH_PINN_JBHI_main.pdf` (8쪽, "et al." 압축 서지 + DOI) — 무료 쪽수 유지.
- 본문·수치·그림은 두 버전이 완전히 동일하며, 레퍼런스 표기만 다릅니다.
