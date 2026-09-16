"""
Cardiac Digital Twin — 구조 보완 전략 & 데이터 확보 로드맵
============================================================
현재 상태: LV cavity shell + rigid wall (12개 구조물 누락)
목표: 임상 수준 patient-specific 4-chamber cardiac digital twin
"""
import json

roadmap = {
    "title": "Cardiac Digital Twin — Gap Analysis & Data Acquisition Roadmap",
    "date": "2026-07-04",
    "current_state": {
        "model": "LV cavity (Case 1009, MM-WHS CT)",
        "present": ["LV blood cavity", "LV wall (rigid)", "myocardium geometry"],
        "boundary_conditions_only": ["LA (inlet pressure)", "Ascending aorta (outlet pressure)"],
        "missing_count": 12,
        "fidelity_score": "~15% of full cardiac anatomy"
    },

    # ============================================================
    # SECTION 1: 데이터 소스 전수 목록
    # ============================================================
    "data_sources": {
        
        # --- 1A. RV Segmentation ---
        "RV_segmentation": {
            "gap": "MM-WHS에 RV(label 620) 없음 — 전체 케이스에서 0 voxels",
            "sources": [
                {
                    "name": "TotalSegmentator (heartchambers_highres)",
                    "url": "https://github.com/wasserth/TotalSegmentator",
                    "type": "AI segmentation tool",
                    "access": "pip install TotalSegmentator → TotalSegmentator -i ct_image.nii.gz -o output/ --task heartchambers_highres",
                    "structures": "LV, RV, LA, RA, LV myocardium, RV myocardium, ascending aorta",
                    "license": "Apache 2.0 (code), non-commercial (weights)",
                    "quality": "RV myocardium Dice ~0.58, 다른 구조 ~0.89+",
                    "action": "기존 MM-WHS CT에 즉시 적용 가능 — 추가 데이터 필요 없음",
                    "priority": "★★★ IMMEDIATE"
                },
                {
                    "name": "ACDC (Automated Cardiac Diagnosis Challenge)",
                    "url": "https://www.creatis.insa-lyon.fr/Challenge/acdc/",
                    "type": "Cardiac MRI dataset",
                    "access": "웹사이트 등록 후 다운로드",
                    "structures": "LV cavity, RV cavity, LV myocardium (ED + ES frames)",
                    "patients": 100,
                    "modality": "1.5T/3T cardiac MRI (cine SSFP)",
                    "license": "연구용 무료",
                    "limitation": "MRI 기반 — CT geometry와 직접 호환 안됨",
                    "priority": "★★ REFERENCE"
                },
                {
                    "name": "M&Ms (Multi-Centre Multi-Vendor Multi-Disease)",
                    "url": "https://www.ub.edu/mnms/",
                    "type": "Cardiac MRI dataset",
                    "access": "웹사이트 등록",
                    "structures": "LV, RV, Myocardium",
                    "patients": 375,
                    "license": "연구용",
                    "priority": "★★ REFERENCE"
                },
                {
                    "name": "nnU-Net cardiac (자체 학습)",
                    "url": "https://github.com/MIC-DKFZ/nnUNet",
                    "type": "Auto-configuration segmentation framework",
                    "access": "pip install nnunetv2",
                    "action": "MM-WHS training data로 RV 포함 재학습 가능 (수동 annotation 필요)",
                    "priority": "★ LONG-TERM"
                }
            ]
        },

        # --- 1B. Coronary Arteries ---
        "coronary_arteries": {
            "gap": "관상동맥 전체 부재 — MM-WHS CT 해상도(0.488mm)로는 불충분",
            "sources": [
                {
                    "name": "ImageCAS (1,000 CTA)",
                    "url": "https://github.com/XiaoweiXu/ImageCAS-A-Large-Scale-Dataset-and-Benchmark-for-Coronary-Artery-Segmentation-based-on-CT",
                    "kaggle": "https://www.kaggle.com/datasets/xiaoweixumedicalai/imagecas",
                    "type": "Coronary CTA dataset",
                    "access": "Kaggle 계정 → 다운로드 (약 200GB)",
                    "structures": "LM, LAD, LCx, RCA, diagonal, OM, PDA — AHA 17-segment model",
                    "patients": 1000,
                    "format": "NIfTI (image + label)",
                    "resolution": "0.3-0.5mm isotropic",
                    "license": "연구용",
                    "priority": "★★★ PRIMARY"
                },
                {
                    "name": "ASOCA (Automated Segmentation of Coronary Arteries)",
                    "url": "https://asoca.grand-challenge.org/",
                    "type": "MICCAI 2020 challenge dataset",
                    "access": "Grand Challenge 등록 → request access",
                    "patients": 40,
                    "structures": "Coronary artery lumen + centerline",
                    "priority": "★★ SUPPLEMENTARY"
                },
                {
                    "name": "Public Cardiac CT Dataset (LAA + Coronary + PV)",
                    "url": "https://github.com/Bjonze/Public-Cardiac-CT-Dataset",
                    "arxiv": "https://arxiv.org/abs/2510.06090",
                    "type": "Multi-structure annotation on ImageCAS base",
                    "structures": "LAA + coronary arteries + pulmonary veins — 동일 1000 CTA",
                    "priority": "★★★ HIGHEST VALUE — 3개 gap 동시 해결"
                },
                {
                    "name": "SimVascular + Vascular Model Repository",
                    "url_tool": "https://simvascular.github.io/",
                    "url_models": "https://www.vascularmodel.com/",
                    "type": "CFD-ready vascular models + simulation pipeline",
                    "structures": "120+ patient-specific models (coronary, aorta, cerebral)",
                    "features": "Segmentation → meshing → FE solver → RCR Windkessel BC",
                    "license": "BSD-like",
                    "priority": "★★★ CFD PIPELINE"
                },
                {
                    "name": "vmtk (Vascular Modeling Toolkit)",
                    "url": "http://www.vmtk.org/",
                    "type": "Centerline extraction + meshing tool",
                    "access": "pip install vmtk 또는 conda install -c vmtk vmtk",
                    "features": "Centerline computation, branch splitting, mesh generation",
                    "priority": "★★ TOOLING"
                }
            ]
        },

        # --- 1C. Valve Geometry ---
        "valve_geometry": {
            "gap": "MV leaflet, AV cusp 전무 — CT 해상도 한계 (0.3-0.7mm 구조)",
            "sources": [
                {
                    "name": "MVAA 2026 (Mitral Valve Multimodal Analysis)",
                    "url": "https://www.codabench.org/competitions/15662/",
                    "type": "MICCAI 2026 challenge",
                    "access": "Codabench 등록 → training data 다운로드",
                    "structures": "Mitral valve (CT + 3D TEE + surgical video)",
                    "modality": "Multi-modal (CT, echocardiography, video)",
                    "priority": "★★★ BEST FOR MV"
                },
                {
                    "name": "4D CT Aortic Valve Dataset (138 patients)",
                    "url": "https://www.mdpi.com/2313-433X/8/1/11",
                    "type": "ECG-gated 4D CT",
                    "structures": "Aortic valve cusps (3), aortic root, calcification",
                    "frames": "10-20 phases per cardiac cycle",
                    "access": "논문 supplementary 또는 저자 contact",
                    "priority": "★★ AV GEOMETRY"
                },
                {
                    "name": "Idealized valve geometries (literature-based)",
                    "approach": "해부학 치수 기반 parametric valve 생성",
                    "tools": "GMSH, FreeCAD, or custom Python",
                    "parameters": {
                        "MV": "annulus D=30mm, leaflet height=15mm, thickness=1mm, saddle height=8mm",
                        "AV": "annulus D=23mm, cusp height=15mm, thickness=0.5mm, sinus D=32mm"
                    },
                    "references": "Kunzelman 1993, Votta 2013, Marom 2016",
                    "priority": "★★★ FASTEST PATH — 즉시 구현 가능"
                },
                {
                    "name": "Echo-derived valve (환자 echocardiography)",
                    "approach": "3D TEE에서 MV leaflet surface 추출",
                    "tools": "TomTec, Philips QLAB, or open-source SlicerHeart",
                    "url_slicer": "https://github.com/SlicerHeart/SlicerHeart",
                    "note": "Patient-specific이지만 echo 데이터 필요",
                    "priority": "★★ PATIENT-SPECIFIC"
                }
            ]
        },

        # --- 1D. LAA (Left Atrial Appendage) ---
        "left_atrial_appendage": {
            "gap": "LAA가 LA label(420)에 합쳐져 있어 별도 분리 필요",
            "sources": [
                {
                    "name": "Public Cardiac CT Dataset (위 coronary와 동일)",
                    "url": "https://github.com/Bjonze/Public-Cardiac-CT-Dataset",
                    "structures": "LAA segmentation on 1000 CTA scans",
                    "priority": "★★★"
                },
                {
                    "name": "LAA Morphology Classification (연구 데이터)",
                    "approach": "기존 LA label에서 shape analysis로 LAA 분리",
                    "method": "LA label → connected component → narrowing point detection → LAA isolation",
                    "tools": "scipy.ndimage + skimage",
                    "priority": "★★ SELF-EXTRACTION"
                },
                {
                    "name": "Atritrack / LA segmentation tools",
                    "url": "https://github.com/KCL-BMEIS/atlas",
                    "type": "LA + LAA + PV segmentation from CT/MRI",
                    "priority": "★★"
                }
            ]
        },

        # --- 1E. Chordae Tendineae ---
        "chordae_tendineae": {
            "gap": "어떤 영상 모달리티로도 직접 segmentation 불가 (0.3-2.5mm)",
            "sources": [
                {
                    "name": "Parametric chordae models (literature)",
                    "approach": "해부학 문헌 기반 idealized chordae tree 생성",
                    "references": "Kunzelman 1993, Cochran 1991, Lam 1970",
                    "parameters": {
                        "primary_count": "25-30 (to leaflet edge)",
                        "secondary_count": "8-12 (to leaflet belly)",
                        "tertiary_count": "3-5 (to leaflet base, posterior only)",
                        "diameter_mm": "primary 0.4-0.9, secondary 1.0-2.5",
                        "length_mm": "15-25",
                        "E_MPa": "40-80 (marginal), 20-50 (strut)"
                    },
                    "priority": "★★★ ONLY PRACTICAL OPTION"
                },
                {
                    "name": "Micro-CT ex vivo (연구용)",
                    "note": "적출 심장의 micro-CT (~10μm resolution)로만 직접 가시화 가능",
                    "datasets": "거의 공개 데이터 없음 — 개별 연구 그룹 contact 필요",
                    "priority": "★ ACADEMIC ONLY"
                }
            ]
        },

        # --- 1F. Papillary Muscles & Trabeculae ---
        "papillary_trabeculae": {
            "gap": "CT에 보이지만 segmentation label 없음 (blood pool에 합산)",
            "sources": [
                {
                    "name": "HU thresholding from existing CT (자체 추출)",
                    "method": "LV cavity mask AND HU < 150 → tissue in blood pool",
                    "status": "이미 시도 완료 — 24.8% tissue voxels, STL 추출됨",
                    "quality": "papillary 2개 분리 필요, trabeculae는 coarse",
                    "priority": "★★★ ALREADY DONE (refinement needed)"
                },
                {
                    "name": "High-resolution cardiac MRI (LVNC studies)",
                    "approach": "T1-weighted MRI에서 trabeculated vs compacted 구분",
                    "datasets": "LVNC 연구 데이터 — 개별 연구 그룹",
                    "priority": "★ SPECIALIZED"
                },
                {
                    "name": "Fractal trabeculation model",
                    "approach": "fractal branching algorithm으로 synthetic trabeculae 생성",
                    "reference": "Captur et al., Circ Cardiovasc Imaging 2014",
                    "priority": "★★ SYNTHETIC OPTION"
                }
            ]
        },

        # --- 1G. Full 4-Chamber Geometry ---
        "four_chamber": {
            "gap": "현재 LV-only → 4-chamber 확장 필요",
            "sources": [
                {
                    "name": "Whole Heart segmentation (TotalSegmentator 기반)",
                    "approach": "기존 CT에서 4 chamber + great vessels 전부 추출",
                    "action": "TotalSegmentator heartchambers_highres → 7 classes",
                    "priority": "★★★"
                },
                {
                    "name": "Zygote 3D Heart Model (상용)",
                    "url": "https://www.zygote.com/cad-models/body-systems/cardiovascular-system",
                    "type": "Anatomically complete 3D heart model",
                    "structures": "ALL — 4 chambers, valves, chordae, papillary, coronary, pericardium",
                    "format": "STL, OBJ, STEP",
                    "price": "$1,000-5,000 (academic discount 가능)",
                    "use_case": "Idealized reference geometry → patient-specific deformation",
                    "priority": "★★ COMMERCIAL OPTION"
                },
                {
                    "name": "Living Heart Project (Dassault Systèmes)",
                    "url": "https://www.3ds.com/products-services/simulia/solutions/life-sciences-healthcare/the-living-heart-project/",
                    "type": "Complete cardiac digital twin platform",
                    "features": "FEA + CFD + electrophysiology, validated against clinical",
                    "access": "Consortium membership (academic ~$10K/yr)",
                    "priority": "★ BENCHMARK REFERENCE"
                }
            ]
        },

        # --- 1H. Electrophysiology (향후 확장) ---
        "electrophysiology": {
            "gap": "전기적 활성화 순서 없음 → wall motion timing에 영향",
            "sources": [
                {
                    "name": "openCARP",
                    "url": "https://opencarp.org/",
                    "type": "Cardiac electrophysiology simulator",
                    "access": "오픈소스, GitLab 다운로드",
                    "features": "Action potential propagation, ECG simulation",
                    "priority": "★ FUTURE PHASE"
                },
                {
                    "name": "PhysioNet ECG databases",
                    "url": "https://physionet.org/",
                    "databases": [
                        "MIMIC-IV-ECG (800K+ ECGs)",
                        "PTB-XL (21,837 ECGs)",
                        "PhysioNet/CinC Challenge datasets"
                    ],
                    "access": "PhysioNet credentialed access (CITI training 필요)",
                    "priority": "★ FUTURE PHASE"
                }
            ]
        },

        # --- 1I. Hemodynamic Validation Data ---
        "validation_data": {
            "gap": "CFD 결과 검증용 in vivo 혈류 데이터",
            "sources": [
                {
                    "name": "4D Flow MRI datasets",
                    "description": "시간 분해 3D velocity field — CFD 검증의 gold standard",
                    "datasets": [
                        {
                            "name": "STACOM 4D Flow Challenge",
                            "url": "https://www.cardiacatlas.org/challenges/",
                            "patients": "10-20, LV + aorta",
                            "access": "Challenge registration"
                        },
                        {
                            "name": "UK Biobank Cardiac MRI (4D flow subset)",
                            "url": "https://www.ukbiobank.ac.uk/",
                            "patients": "~5,000 with 4D flow",
                            "access": "Application required (연구계획서 제출)"
                        }
                    ],
                    "priority": "★★★ VALIDATION ESSENTIAL"
                },
                {
                    "name": "PhysioNet hemodynamic databases",
                    "url": "https://physionet.org/",
                    "databases": [
                        "MIMIC-IV (ICU hemodynamics — 이미 사용 중)",
                        "eICU-CRD (이미 Phase 3 validation 완료)"
                    ],
                    "status": "이미 활용 중 — Phase 1-3 validation 완료",
                    "priority": "★★★ ALREADY INTEGRATED"
                }
            ]
        }
    },

    # ============================================================
    # SECTION 2: 구현 전략 로드맵
    # ============================================================
    "implementation_strategy": {
        
        "phase_0_immediate": {
            "title": "즉시 실행 (1주)",
            "description": "추가 데이터 없이 현재 CT에서 즉시 할 수 있는 것",
            "tasks": [
                {
                    "task": "TotalSegmentator로 RV + 4-chamber 추출",
                    "command": "pip install TotalSegmentator && TotalSegmentator -i ct_train_1009_image.nii.gz -o seg_output/ --task heartchambers_highres",
                    "output": "RV, RA, LA, LV, myocardium (LV+RV), aorta segmentation",
                    "effort": "2시간"
                },
                {
                    "task": "Papillary muscle STL 정합 및 정제",
                    "method": "좌표계 변환 → LV STL과 정합 → 2개 PM 분리 → mesh quality check",
                    "effort": "1일"
                },
                {
                    "task": "LAA 분리 (LA label에서 shape analysis)",
                    "method": "LA mask → morphological narrowing detection → LAA isolation",
                    "effort": "1일"
                },
                {
                    "task": "Idealized valve geometry 생성",
                    "method": "MV: D=30mm, 2-leaflet parametric → AV: D=23mm, 3-cusp",
                    "tool": "Python + GMSH or FreeCAD",
                    "effort": "2일"
                }
            ]
        },

        "phase_1_data_acquisition": {
            "title": "데이터 확보 (2주)",
            "tasks": [
                {
                    "task": "ImageCAS + Public Cardiac CT Dataset 다운로드",
                    "url": "https://github.com/Bjonze/Public-Cardiac-CT-Dataset",
                    "output": "1,000 CTA with coronary + LAA + PV annotations",
                    "size": "~200GB",
                    "effort": "다운로드 2-3일 (네트워크 의존)"
                },
                {
                    "task": "MVAA 2026 challenge 등록 + MV training data 확보",
                    "url": "https://www.codabench.org/competitions/15662/",
                    "effort": "등록 1일, 다운로드 1일"
                },
                {
                    "task": "SimVascular 설치 + Vascular Model Repository 탐색",
                    "url": "https://simvascular.github.io/",
                    "purpose": "Coronary CFD pipeline 학습 + reference model 확보"
                },
                {
                    "task": "4D Flow MRI challenge data 접근",
                    "url": "https://www.cardiacatlas.org/challenges/",
                    "purpose": "CFD validation용 velocity field"
                }
            ]
        },

        "phase_2_geometry_assembly": {
            "title": "형상 조립 (3-4주)",
            "description": "개별 구조물 STL → 통합 multi-body geometry",
            "tasks": [
                "4-chamber geometry 통합 (LV + RV + LA + RA)",
                "Valve geometry 삽입 (MV at annulus, AV at LVOT)",
                "Coronary ostia 위치 지정 (aortic root에 outlet)",
                "Aortic root complex 재구성 (Valsalva sinus + STJ)",
                "Papillary muscles + trabeculae 벽면 통합",
                "LAA geometry 분리 및 연결"
            ],
            "tools": "MeshLab, GMSH, cfMesh, snappyHexMesh",
            "output": "patient_specific_heart_v2.stl (multi-region)"
        },

        "phase_3_material_properties": {
            "title": "물성 부여 (2주)",
            "description": "각 구조물에 구조별 탄성값/두께 할당",
            "tasks": [
                "LV wall: Holzapfel-Ogden fiber-reinforced (transmural fiber rotation)",
                "RV wall: 얇은 벽 (3-5mm), lower E",
                "MV leaflets: Fung-type anisotropic (E_circ=5000, E_rad=1000 kPa)",
                "AV cusps: stiffer (E_circ=8000 kPa)",
                "Chordae: 1D nonlinear (E=40-80 MPa)",
                "Coronary walls: HGO model (E=500-2000 kPa)",
                "Pericardial constraint: nonlinear spring BC"
            ],
            "constitutive_library": "FEBio material database + literature values"
        },

        "phase_4_valve_dynamics": {
            "title": "판막 동역학 (4-6주)",
            "tiers": {
                "tier_1": {
                    "method": "Time-varying resistance (fvOptions)",
                    "description": "판막을 porous zone으로 모델링, 개폐에 따라 resistance 변화",
                    "effort": "1주",
                    "fidelity": "Low — 벌크 유량은 맞지만 jet pattern 부정확"
                },
                "tier_2": {
                    "method": "Prescribed kinematics (overPimpleDyMFoam)",
                    "description": "Echo에서 측정한 개폐 시점/각도로 leaflet 움직임 처방",
                    "effort": "3주",
                    "fidelity": "Medium — realistic jet, 역류 패턴 재현"
                },
                "tier_3": {
                    "method": "Full FSI (preCICE + CalculiX + OpenFOAM)",
                    "description": "유체-구조 양방향 커플링, leaflet 변형 + chordae tension",
                    "effort": "2-3개월",
                    "fidelity": "High — 완전한 valve dynamics"
                }
            }
        },

        "phase_5_validation": {
            "title": "검증 (지속적)",
            "levels": [
                "Level 1: Conservation checks (mass, momentum, energy)",
                "Level 2: Physiological range (peak velocity, pressure gradient, CO)",
                "Level 3: 4D Flow MRI comparison (velocity field correlation)",
                "Level 4: Clinical outcome prediction (eICU Phase 3 확장)",
                "Level 5: FDA V&V 40 compliance (computational credibility)"
            ]
        }
    },

    # ============================================================
    # SECTION 3: Samsung Notebook 7 Force 활용 전략
    # ============================================================
    "compute_strategy": {
        "samsung_notebook": {
            "specs": "i7-8565U (4C/8T), GTX 1650 4GB, 40GB RAM",
            "suitable_for": [
                "TotalSegmentator inference (GPU)",
                "pH-PINN training (GPU)",
                "Valve parametric geometry (CPU)",
                "Mesh generation (RAM-dependent)",
                "Small-scale OpenFOAM (<1M cells)"
            ],
            "not_suitable_for": [
                "Large OpenFOAM (>3M cells) — U-series CPU throttle",
                "4-chamber CFD (>10M cells)",
                "FSI coupling (preCICE + 2 solvers simultaneously)"
            ],
            "recommendation": "Phase 0-1은 Samsung 가능, Phase 2+ 이후는 HPC/Cloud 고려"
        },
        "cloud_options": [
            {
                "name": "Google Colab Pro+ (A100 GPU)",
                "cost": "$50/month",
                "use": "TotalSegmentator, nnU-Net, PINN training"
            },
            {
                "name": "AWS EC2 (c5.4xlarge for OpenFOAM)",
                "cost": "~$0.68/hr (16 vCPU, 32GB RAM)",
                "use": "Large-scale CFD, 4-chamber simulation"
            },
            {
                "name": "연구실 HPC 클러스터",
                "note": "의대/병원 연구 인프라 활용 가능 여부 확인",
                "use": "Production-scale 시뮬레이션"
            }
        ]
    },

    # ============================================================
    # SECTION 4: 타임라인 총괄
    # ============================================================
    "timeline": {
        "week_1_2": "Phase 0 — TotalSegmentator RV 추출, PM 정제, idealized valve",
        "week_3_4": "Phase 1 — ImageCAS/MVAA 데이터 다운로드, SimVascular 설치",
        "week_5_8": "Phase 2 — Multi-structure geometry 조립, mesh 생성",
        "week_9_10": "Phase 3 — Material properties 할당, BC 설정",
        "week_11_16": "Phase 4 — Valve dynamics (Tier 1→2 순차 구현)",
        "week_17_onward": "Phase 5 — Validation cycle, FSI 확장, 논문 준비"
    },

    "target_fidelity": {
        "current": "~15% (LV shell + rigid wall)",
        "after_phase_0": "~35% (4-chamber + PM + idealized valves)",
        "after_phase_2": "~60% (multi-structure geometry + coronary ostia)",
        "after_phase_4": "~80% (dynamic valves + material properties)",
        "after_phase_5": "~90% (validated, FSI-capable digital twin)"
    }
}

# Save
out = "cardiac_digital_twin_roadmap.json"
with open(out, 'w', encoding='utf-8') as f:
    json.dump(roadmap, f, indent=2, ensure_ascii=False)

# Print executive summary
print("=" * 70)
print("CARDIAC DIGITAL TWIN — DATA ACQUISITION & ROADMAP")
print("=" * 70)

print("\n📊 현재 모델 완성도: ~15% (LV shell + rigid wall)")
print("🎯 목표: ~90% (validated 4-chamber digital twin)")

print("\n" + "=" * 70)
print("🔑 핵심 데이터 소스 (즉시 접근 가능)")
print("=" * 70)

immediate = [
    ("TotalSegmentator", "RV + 4-chamber", "pip install", "★★★"),
    ("ImageCAS + Public Cardiac CT", "Coronary + LAA + PV", "Kaggle + GitHub", "★★★"),
    ("MVAA 2026 Challenge", "Mitral valve", "Codabench 등록", "★★★"),
    ("SimVascular", "Coronary CFD pipeline", "Open source", "★★★"),
    ("CT HU thresholding", "Papillary + trabeculae", "자체 추출 (완료)", "★★★"),
    ("Parametric models", "Idealized valve + chordae", "문헌 기반 생성", "★★★"),
]
for name, covers, access, priority in immediate:
    print(f"  {priority} {name:30s} → {covers:25s} ({access})")

print("\n" + "=" * 70)
print("📈 구현 로드맵")
print("=" * 70)
phases = [
    ("Phase 0", "1주", "TotalSegmentator + PM 정제 + valve 생성", "→ 35%"),
    ("Phase 1", "2주", "ImageCAS/MVAA 데이터 확보", ""),
    ("Phase 2", "3-4주", "Multi-structure geometry 조립", "→ 60%"),
    ("Phase 3", "2주", "Material properties + BC", ""),
    ("Phase 4", "4-6주", "Valve dynamics (Tier 1→2→3)", "→ 80%"),
    ("Phase 5", "지속", "Validation + FSI + 논문", "→ 90%"),
]
for phase, dur, desc, fid in phases:
    print(f"  {phase} ({dur:5s}): {desc} {fid}")

print(f"\nSaved: {out}")
