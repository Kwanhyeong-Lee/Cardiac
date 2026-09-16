"""
Cardiac Ion Channel Distribution Map
======================================
심장 각 부위별 이온 채널 발현 밀도, 전도 특성, 약물 반응
→ openCARP electrophysiology 연동 및 pH-PINN 확장용 사전 조사

Reference cell models:
  - ten Tusscher-Panfilov 2006 (human ventricular)
  - Courtemanche-Ramirez-Nattel 1998 (human atrial)
  - O'Hara-Rudy 2011 (human ventricular, most recent)
"""
import json

ion_channel_map = {
    "title": "Cardiac Ion Channel Distribution — Region-Specific Expression",
    "date": "2026-07-04",
    "purpose": "심장 각 부위별 이온 채널 밀도 매핑 → electromechanical coupling 준비",
    
    # ============================================================
    # A. 주요 이온 채널 목록
    # ============================================================
    "ion_channels": {
        
        # --- Na+ channels ---
        "Nav1.5": {
            "gene": "SCN5A",
            "current": "I_Na (fast sodium)",
            "role": "Phase 0 rapid depolarization (action potential upstroke)",
            "conductance_nS_pF": 14.838,  # O'Hara-Rudy model
            "regional_expression": {
                "LV_endocardium": 1.0,
                "LV_midmyocardium": 1.0,
                "LV_epicardium": 1.0,
                "RV": 1.0,
                "septum": 1.0,
                "atrium": 0.7,  # lower density
                "SA_node": 0.1,  # minimal — SA node uses Ca2+ for upstroke
                "AV_node": 0.15,
                "Purkinje": 1.5,  # highest — fast conduction
            },
            "conduction_velocity_m_s": {
                "ventricular_longitudinal": 0.7,
                "ventricular_transverse": 0.2,
                "atrial": 0.5,
                "purkinje": 2.0,
                "SA_node": 0.05,
                "AV_node": 0.02
            },
            "drug_targets": ["lidocaine (class IB)", "flecainide (class IC)", "amiodarone (class III/multi)"],
            "clinical": "SCN5A mutation → Brugada syndrome, Long QT type 3"
        },
        
        # --- L-type Ca2+ channels ---
        "Cav1.2": {
            "gene": "CACNA1C",
            "current": "I_CaL (L-type calcium)",
            "role": "Phase 2 plateau, Ca2+-induced Ca2+ release (CICR) trigger, E-C coupling",
            "conductance_nS_pF": 0.0398,  # O'Hara-Rudy
            "regional_expression": {
                "LV_endocardium": 1.0,
                "LV_midmyocardium": 1.0,
                "LV_epicardium": 0.7,  # shorter plateau → shorter APD
                "RV": 0.9,
                "septum": 1.0,
                "atrium": 0.6,
                "SA_node": 1.2,  # important for pacemaker diastolic depol.
                "AV_node": 1.0,
                "Purkinje": 0.8
            },
            "drug_targets": ["verapamil (class IV)", "diltiazem (class IV)", "nifedipine (dihydropyridine)"],
            "clinical": "Timothy syndrome (gain-of-function), Brugada-like (loss-of-function)"
        },
        
        # --- T-type Ca2+ channels ---
        "Cav3.1_3.2": {
            "gene": "CACNA1G / CACNA1H",
            "current": "I_CaT (T-type calcium)",
            "role": "Pacemaker activity, low-threshold depolarization",
            "regional_expression": {
                "LV_endocardium": 0.1,
                "LV_epicardium": 0.05,
                "RV": 0.1,
                "atrium": 0.3,
                "SA_node": 1.0,  # crucial for pacemaker
                "AV_node": 0.8,
                "Purkinje": 0.5
            },
            "clinical": "SA node dysfunction"
        },
        
        # --- hERG (rapid delayed rectifier K+) ---
        "hERG": {
            "gene": "KCNH2 (hERG)",
            "current": "I_Kr (rapid delayed rectifier K+)",
            "role": "Phase 3 repolarization — QT interval 결정의 핵심",
            "conductance_nS_pF": 0.046,
            "regional_expression": {
                "LV_endocardium": 1.0,
                "LV_midmyocardium": 0.5,  # M-cells: LOW I_Kr → long APD
                "LV_epicardium": 1.0,
                "RV": 1.0,
                "septum": 1.0,
                "atrium": 0.8,
                "SA_node": 0.3,
                "Purkinje": 0.6
            },
            "drug_targets": ["sotalol (class III)", "dofetilide", "amiodarone", "MANY non-cardiac drugs (off-target)"],
            "clinical": "Long QT syndrome type 2 (most common drug-induced QT prolongation target)",
            "safety_pharmacology": "hERG inhibition assay = MANDATORY for all new drugs (ICH S7B)"
        },
        
        # --- KCNQ1 (slow delayed rectifier K+) ---
        "KCNQ1": {
            "gene": "KCNQ1 + KCNE1 (KvLQT1/minK)",
            "current": "I_Ks (slow delayed rectifier K+)",
            "role": "Phase 3 late repolarization, adrenergic response의 repolarization reserve",
            "conductance_nS_pF": 0.0034,
            "regional_expression": {
                "LV_endocardium": 0.5,
                "LV_midmyocardium": 0.2,  # M-cells: LOW I_Ks → long APD
                "LV_epicardium": 1.0,
                "RV": 0.8,
                "atrium": 0.3,
                "SA_node": 0.5,
                "Purkinje": 0.3
            },
            "drug_targets": ["chromanol 293B (experimental)"],
            "clinical": "Long QT syndrome type 1 (exercise-triggered)"
        },
        
        # --- Kir2.1 (inward rectifier K+) ---
        "Kir2.1": {
            "gene": "KCNJ2",
            "current": "I_K1 (inward rectifier K+)",
            "role": "Resting membrane potential 유지 (-85 to -90 mV), Phase 4 stability",
            "conductance_nS_pF": 0.1908,
            "regional_expression": {
                "LV_endocardium": 1.2,
                "LV_midmyocardium": 1.0,
                "LV_epicardium": 1.0,
                "RV": 1.0,
                "septum": 1.0,
                "atrium": 0.4,  # lower → more depolarized resting potential
                "SA_node": 0.0,  # ABSENT — enables pacemaker diastolic depol.
                "AV_node": 0.1,
                "Purkinje": 1.0
            },
            "clinical": "Andersen-Tawil syndrome (loss of function)"
        },
        
        # --- Kv4.3 (transient outward K+) ---
        "Kv4.3": {
            "gene": "KCND3 + KChIP2",
            "current": "I_to (transient outward K+)",
            "role": "Phase 1 early repolarization (notch) — Epi vs Endo APD 차이의 주인공",
            "regional_expression": {
                "LV_endocardium": 0.2,   # LOW → no notch → long plateau
                "LV_midmyocardium": 0.5,
                "LV_epicardium": 1.0,     # HIGH → prominent notch → short plateau
                "RV": 1.2,               # RV epi > LV epi
                "septum": 0.6,
                "atrium": 0.8,            # I_to,fast variant
                "SA_node": 0.2,
                "Purkinje": 0.3
            },
            "clinical": "Brugada syndrome (J-point elevation due to epi-endo I_to gradient)",
            "transmural_gradient": "CRITICAL — epicardium >> endocardium, 이 차이가 T-wave polarity 결정"
        },
        
        # --- HCN4 (funny current) ---
        "HCN4": {
            "gene": "HCN4",
            "current": "I_f (funny/pacemaker current)",
            "role": "Phase 4 diastolic depolarization — 자동능(automaticity)의 핵심",
            "regional_expression": {
                "LV_endocardium": 0.0,  # ABSENT in ventricular myocytes
                "LV_epicardium": 0.0,
                "RV": 0.0,
                "atrium": 0.1,  # minimal
                "SA_node": 1.0,  # HIGHEST — primary pacemaker driver
                "AV_node": 0.5,
                "Purkinje": 0.3  # subsidiary pacemaker
            },
            "drug_targets": ["ivabradine (specific I_f blocker, heart rate reduction)"],
            "clinical": "Sick sinus syndrome (loss of function)"
        },
        
        # --- RyR2 (ryanodine receptor) ---
        "RyR2": {
            "gene": "RYR2",
            "current": "Ca2+ release from SR (not a membrane current)",
            "role": "CICR — sarcoplasmic reticulum Ca2+ release → contraction",
            "regional_expression": {
                "LV_endocardium": 1.0,
                "LV_epicardium": 1.0,
                "RV": 1.0,
                "atrium": 0.7,
                "SA_node": 0.5,
                "Purkinje": 0.8
            },
            "clinical": "CPVT (catecholaminergic polymorphic VT) — gain of function"
        },
        
        # --- SERCA2a (SR Ca2+ ATPase) ---
        "SERCA2a": {
            "gene": "ATP2A2",
            "current": "Ca2+ re-uptake into SR (not a membrane current)",
            "role": "Relaxation (diastole) — Ca2+ removal from cytoplasm",
            "regional_expression": {
                "LV_endocardium": 1.0,
                "LV_epicardium": 1.0,
                "RV": 0.9,
                "atrium": 0.8,
                "heart_failure": 0.4  # ★ REDUCED in HF → impaired relaxation
            },
            "clinical": "Heart failure의 핵심 분자적 변화 — SERCA2a gene therapy 임상시험 진행됨"
        },
        
        # --- NCX (Na+/Ca2+ exchanger) ---
        "NCX1": {
            "gene": "SLC8A1",
            "current": "I_NaCa (Na+/Ca2+ exchanger)",
            "role": "Ca2+ extrusion (1 Ca2+ out : 3 Na+ in) — relaxation + late depolarizing current",
            "regional_expression": {
                "LV_endocardium": 1.0,
                "LV_epicardium": 0.8,
                "RV": 0.9,
                "atrium": 1.2,
                "SA_node": 1.5,  # important for pacemaker Ca2+ clock
                "heart_failure": 1.8  # ★ UPREGULATED in HF → compensatory but arrhythmogenic
            },
            "clinical": "HF에서 upregulation → delayed afterdepolarizations (DADs)"
        },
        
        # --- Gap junctions ---
        "Connexin43": {
            "gene": "GJA1 (Cx43)",
            "current": "Gap junction conductance (cell-to-cell coupling)",
            "role": "세포 간 전기적 coupling — 전도속도 결정",
            "regional_expression": {
                "LV_endocardium": 1.0,
                "LV_epicardium": 1.0,
                "RV": 0.8,
                "septum": 1.0,
                "atrium": 0.6,  # Cx40 dominant in atria
                "SA_node": 0.05,  # very low → slow conduction (protective)
                "AV_node": 0.1,   # low → conduction delay
                "Purkinje": 1.5,
                "border_zone_post_MI": 0.3  # ★ REDUCED at infarct border → reentry substrate
            },
            "variants": {
                "Cx43": "ventricular dominant",
                "Cx40": "atrial + Purkinje dominant (faster conduction)",
                "Cx45": "SA/AV node (low conductance)"
            },
            "clinical": "Cx43 remodeling after MI → ventricular arrhythmia substrate"
        }
    },
    
    # ============================================================
    # B. 부위별 Action Potential 특성
    # ============================================================
    "regional_AP_characteristics": {
        "SA_node": {
            "resting_potential_mV": "-60 to -65 (no stable rest)",
            "APD90_ms": "100-200",
            "upstroke_velocity_V_s": "1-10 (Ca2+-dependent, slow)",
            "rate_bpm": "60-100 (intrinsic)",
            "dominant_channels": ["HCN4 (I_f)", "Cav1.2 (I_CaL)", "Cav3.1 (I_CaT)"],
            "cell_model": "Fabbri-Severi 2017"
        },
        "atrium": {
            "resting_potential_mV": "-75 to -80",
            "APD90_ms": "150-300 (shorter than ventricle)",
            "upstroke_velocity_V_s": "100-200",
            "dominant_channels": ["Nav1.5", "Kv1.5 (I_Kur, atria-specific)", "Kv4.3 (I_to)", "Kir2.1"],
            "atria_specific": "I_Kur (Kv1.5/KCNA5) — 심방에만 있음 → 심방세동 선택적 치료 타겟",
            "cell_model": "Courtemanche-Ramirez-Nattel 1998"
        },
        "AV_node": {
            "resting_potential_mV": "-60 to -70",
            "APD90_ms": "150-250",
            "conduction_delay_ms": "120-200 (PR interval)",
            "role": "심방→심실 전도 지연 (filling time 확보)",
            "dominant_channels": ["Cav1.2", "Cav3.1", "HCN4"],
            "drug_targets": "verapamil, diltiazem, adenosine, digoxin"
        },
        "Purkinje": {
            "resting_potential_mV": "-90 to -95",
            "APD90_ms": "300-400 (longest)",
            "upstroke_velocity_V_s": "500-800 (fastest)",
            "conduction_velocity_m_s": 2.0,
            "dominant_channels": ["Nav1.5 (high density)", "Cx40 (fast coupling)"],
            "cell_model": "Stewart et al. 2009"
        },
        "LV_endocardium": {
            "resting_potential_mV": "-85 to -90",
            "APD90_ms": "300-350",
            "upstroke_velocity_V_s": "200-350",
            "features": "No phase 1 notch (low I_to), long plateau",
            "cell_model": "O'Hara-Rudy 2011 (endo variant)"
        },
        "LV_midmyocardium": {
            "resting_potential_mV": "-85 to -90",
            "APD90_ms": "350-450 (LONGEST in ventricle)",
            "features": "M-cells: low I_Ks + low I_Kr → very long APD, U-wave origin",
            "clinical": "M-cell APD prolongation → drug-induced QT prolongation의 주 기전",
            "cell_model": "O'Hara-Rudy 2011 (mid variant)"
        },
        "LV_epicardium": {
            "resting_potential_mV": "-85 to -90",
            "APD90_ms": "250-300 (shortest)",
            "features": "Prominent phase 1 notch (high I_to), spike-and-dome morphology",
            "cell_model": "O'Hara-Rudy 2011 (epi variant)"
        },
        "RV": {
            "resting_potential_mV": "-85 to -90",
            "APD90_ms": "240-300",
            "features": "Higher I_to than LV epi → more prominent notch",
            "clinical": "Brugada syndrome preferentially affects RV outflow tract (RVOT)"
        }
    },
    
    # ============================================================
    # C. openCARP 연동 계획
    # ============================================================
    "opencarp_integration": {
        "url": "https://opencarp.org/",
        "models_supported": [
            "O'Hara-Rudy 2011 (recommended for ventricle)",
            "Courtemanche 1998 (atrium)",
            "ten Tusscher-Panfilov 2006 (ventricle, faster)",
            "Fabbri-Severi 2017 (SA node)"
        ],
        "workflow": [
            "1. 4-chamber mesh → openCARP format (CARP elements)",
            "2. Region tags: endo/mid/epi/atrium/SA/AV/Purkinje/RV",
            "3. Fiber orientation assignment (rule-based: Bayer et al. 2012)",
            "4. Assign cell model per region",
            "5. Stimulation protocol (SA node → atria → AV → His-Purkinje → ventricles)",
            "6. Solve monodomain/bidomain PDE → activation times",
            "7. Map activation times → wall motion timing in CFD (prescribed displacement)"
        ],
        "coupling_to_mechanics": {
            "method": "Active tension model (Land et al. 2017)",
            "flow": "Ca2+ transient → troponin binding → cross-bridge → active stress",
            "parameters": {
                "peak_active_stress_kPa": "50-100",
                "time_to_peak_ms": "180-200",
                "relaxation_time_ms": "200-400"
            }
        },
        "coupling_to_CFD": {
            "method": "Electromechanical → prescribed wall displacement → CFD inlet BC",
            "pipeline": "openCARP → FEBio/CalculiX → wall displacement field → OpenFOAM (ALE mesh)",
            "alternative": "Direct pH-PINN integration — encode activation sequence as PINN input"
        }
    },
    
    # ============================================================
    # D. Heart Failure 리모델링 (향후 확장)
    # ============================================================
    "heart_failure_remodeling": {
        "description": "HF에서의 이온 채널 발현 변화 — digital twin의 disease modeling 핵심",
        "changes": {
            "I_to (Kv4.3)": "↓↓ 50-70% (APD 연장의 주 원인)",
            "I_K1 (Kir2.1)": "↓ 20-40%",
            "I_Ks (KCNQ1)": "↓ 30-50%",
            "I_CaL (Cav1.2)": "→ (변화 적음, 하지만 인산화 변화)",
            "SERCA2a": "↓↓ 40-60% (relaxation 장애의 핵심)",
            "NCX1": "↑↑ 50-100% (보상적 upregulation → DAD 유발)",
            "RyR2": "leaky (인산화 변화 → diastolic Ca2+ leak)",
            "Cx43": "↓ lateralization (longitudinal 감소, lateral 증가 → 전도 장애)"
        },
        "clinical_implications": {
            "APD_prolongation": "QT 연장 → Torsades de Pointes 위험 ↑",
            "arrhythmia_substrate": "Cx43 remodeling + APD dispersion → reentry",
            "contractile_dysfunction": "SERCA2a ↓ + RyR2 leak → systolic + diastolic failure",
            "drug_sensitivity": "HF 환자는 QT-prolonging drugs에 특히 취약"
        }
    }
}

with open("ion_channel_cardiac_map.json", 'w', encoding='utf-8') as f:
    json.dump(ion_channel_map, f, indent=2, ensure_ascii=False)

# Summary
print("=" * 70)
print("CARDIAC ION CHANNEL DISTRIBUTION MAP")
print("=" * 70)

channels = ion_channel_map['ion_channels']
print(f"\n{len(channels)} ion channels/transporters mapped:\n")

for name, ch in channels.items():
    gene = ch.get('gene', '')
    current = ch.get('current', '')
    role = ch.get('role', '')[:60]
    expr = ch.get('regional_expression', {})
    
    # Find highest and lowest expression regions
    regions = {k: v for k, v in expr.items() if isinstance(v, (int, float))}
    if regions:
        hi = max(regions, key=regions.get)
        lo = min(regions, key=regions.get)
        print(f"  {name:12s} ({gene:10s}): {current}")
        print(f"    → {role}")
        print(f"    Highest: {hi} ({regions[hi]:.1f}), Lowest: {lo} ({regions[lo]:.1f})")
        print()

print(f"\nRegional AP characteristics: {len(ion_channel_map['regional_AP_characteristics'])} regions")
print("Saved: ion_channel_cardiac_map.json")
