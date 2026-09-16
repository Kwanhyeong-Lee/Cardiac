
# PINN Cardiac Digital Twin Project — Complete File Inventory
## MIMIC-IV Heart Failure Cohort (n=5,851 paired echos)
## June 2026

---

## MANUSCRIPTS (3 papers)

| # | File | Target | Status |
|---|------|--------|--------|
| 1 | Paper1_PINN_Cardiac_Digital_Twin.docx | JBHI | Draft complete |
| 2 | Paper2_Treatment_Response_Prediction.docx | JBHI | Draft complete |
| 3 | Paper3_Hamiltonian_Cardiac_Digital_Twin.docx | JBHI | Draft complete |

---

## KEY DATA FILES

### Core Datasets
| File | Rows | Description |
|------|------|-------------|
| mimic_pinn_v4_inference.csv | 33,000 | PINN v4 outputs for all MIMIC echos |
| mimic_treatment_response.csv | 5,851 | Merged PINN + medication data |
| cardiac_energetics_hamiltonian.csv | 5,851 × 145 | Full energy analysis (H,T,V,SW,PVA,η) |

### Treatment Analysis
| File | Description |
|------|-------------|
| psm_treatment_effects.csv | Propensity Score Matching results |
| iptw_treatment_effects.csv | Inverse Probability of Treatment Weighting |
| master_treatment_summary.csv | Combined summary across methods |
| hfref_psm_results.csv | HFrEF-only PSM subgroup |
| drug_interactions_hfref.csv | Drug-drug interaction effects |
| digital_twin_validation.csv | Twin predicted vs observed |
| digital_twin_calibration.csv | Calibrated perturbation params |

### Hamiltonian Energy Analysis
| File | Description |
|------|-------------|
| drug_hamiltonian_perturbation.csv | 9 drugs × energy perturbation metrics |
| hamiltonian_hf_summary.csv | Energy by HF phenotype |
| counterfactual_energy_results.csv | Counterfactual ATE analysis |
| drug_energy_interactions.csv | Drug combo synergy/antagonism |
| phenotype_energy_response.csv | HF type × drug × energy ATE |
| dose_response_energy.csv | ΔH by drug count |

---

## FIGURES

### Paper 1 Figures
| File | Panels | Content |
|------|--------|---------|
| PINN_methodology_overview.png | - | Architecture overview |
| PINN_cardiac_results.png | - | Core validation |
| PINN_Ees_validation.png | - | Ees validation |
| PINN_noise_robustness_clinical.png | - | Noise robustness |
| PINN_physics_ablation.png | - | Physics ablation |
| PINN_invasive_validation.png | - | Invasive hemodynamics |
| PINN_multi_animal_validation.png | - | Multi-animal |
| PINN_EchoNet_validation.png | - | EchoNet-Dynamic |
| PINN_bootstrap_CI.png | - | Bootstrap CIs |

### Paper 2 Figures
| File | Panels | Content |
|------|--------|---------|
| fig_treatment_response_overview.png | 6 | Treatment effects overview |
| fig_adjusted_treatment_heatmap.png | - | Adjusted heatmap |
| fig_hf_phenotype_response.png | - | HF subgroup response |
| fig_psm_forest_plot.png | - | PSM forest plot |
| fig_psm_balance_love_plot.png | - | Covariate balance |
| fig_psm_hf_stratified.png | - | PSM by phenotype |
| fig_psm_vs_iptw.png | - | PSM vs IPTW comparison |
| fig_hfref_psm.png | - | HFrEF-only PSM |
| fig_responder_analysis.png | - | Responder classification |
| fig_drug_interactions.png | - | Drug interactions |
| fig_twin_scatter.png | - | Twin predicted vs actual |
| fig_twin_calibration.png | - | Calibrated twin |
| fig_digital_twin_validation.png | - | DT validation |
| fig_digital_twin_counterfactual.png | - | Counterfactual sim |
| fig_paper2_composite.png | 8 | Main composite figure |

### Paper 3 Figures
| File | Panels | Content |
|------|--------|---------|
| fig_hamiltonian_energetics.png | 11 | Energy analysis (A-K) |
| fig_counterfactual_energy.png | 14 | Counterfactual + dynamics (A-N) |

---

## MODEL CODE

| File | Description |
|------|-------------|
| pinn_v4_physiology.py | PINN v4 architecture (Paper 1-2) |
| pinn_hamiltonian_v5.py | Port-Hamiltonian PINN v5 (Paper 3) |
| pinn_cardiac.py | Original PINN implementation |

## SQL QUERIES

| File | Description |
|------|-------------|
| MIMIC_expanded_medication_matching.sql | MIMIC-IV 9-class drug extraction |
| MIMIC_III_expanded_medication_matching.sql | MIMIC-III version |
| MIMIC_echo_full_extraction.sql | Echo parameter extraction |

---

## KEY RESULTS SUMMARY

### Paper 1: PINN Cardiac Digital Twin
- Non-invasive Ees estimation: R²=0.89 vs invasive gold standard
- 7-parameter cardiac model from 11 echo inputs
- Cross-validated on EchoNet-Dynamic (n=10,030)

### Paper 2: Treatment Response Prediction
- 9 drug classes analyzed with PSM, IPTW, digital twin
- ARNI: +3.2% EF, +0.29 coupling (strongest)
- RAASi+BB synergy confirmed (ΔΔη = +0.008)
- Digital twin R²=0.72 predicted vs observed

### Paper 3: Hamiltonian Cardiac Energetics
- HFrEF: T/V = 0.00193 (energy conversion failure)
- HFpEF: T/V = 0.01170 (energy storage excess)
- ARNI: δH = −10,007*** (strongest energy modifier)
- Digoxin: only drug ↑kinetic energy (δT = +63.1)
- SGLT2i: flow modifier (T-fraction = −0.079)
- RAASi+BB synergistic on H (interaction = −3,897)
- pH-PINN v5: 57,798 params, H=T+V error < 0.001
- Dose-response: 3+ drugs → net ΔH < 0 (energy reduction)
