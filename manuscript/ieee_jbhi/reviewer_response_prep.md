# Reviewer-Response Preparation — pH-PINN Cardiac Digital Twin (IEEE J-BHI)

Internal rebuttal-prep sheet. For each anticipated reviewer comment: **status** (addressed in current manuscript / partially / open limitation), **where** it is handled, and a **prepared response**.

---

## A. Likely comments now ADDRESSED (defensible)

**A1. "Does the port-Hamiltonian structure actually contribute beyond raw network capacity?"** *(the classic methods question)*
- Status: **Addressed.** Where: Sec. II ("Ablation Design"), Sec. III ("Ablation: Physics Constraints as Inductive Bias"), Table II, Fig. 6.
- Response: We ran a 4-model, matched-capacity ablation (3 seeds). Models A/C/D share an identical 73,773-parameter architecture. Predictive accuracy is comparable across all four (R² 0.970–0.973; between-model spread ≤0.003 ≈ seed SD), so accuracy is not the discriminating axis. The discriminator is physical validity: the hard-constrained model (A) has zero violations by construction, whereas the identical-capacity unconstrained model (C) has a non-PSD dissipation matrix in **all** 1,171 held-out cases and hundreds of negative-energy cases. This isolates the structural contribution.

**A2. "Statistical rigor — single run, no variance."**
- Status: **Addressed.** Where: Table II, Fig. 6A error bars, Data & Code Availability.
- Response: Ablation repeated over 3 random seeds; we report mean ± SD.

**A3. "Parameter count is inconsistent (61,169 vs 73,773)."**
- Status: **Addressed.** Where: Sec. II ("Ablation Design").
- Response: 61,169 is the production pH-PINN; the ablation uses a capacity-matched re-implementation (73,773, identical across variants) so the four models differ only in constraints, not capacity. Explicitly stated.

**A4. "Reproducibility / data provenance."**
- Status: **Addressed.** Where: "Data and Code Availability."
- Response: All data are public/credentialed (MIMIC-IV, eICU, MM-WHS, STACOM); training hyperparameters and code availability stated.

**A5. "Overstated patient-specificity."**
- Status: **Addressed.** Where: Sec. II-A (three-tier), Sec. II ("Model Applicability"), Limitations.
- Response: We use "patient-anchored," not "patient-specific"; only the LV is Tier-1. Scope explicitly limited to LV-centric pump function; inclusion/exclusion criteria given.

---

## B. Genuine LIMITATIONS — acknowledged, defended by framing (cannot be closed without new data)

**B1. "Surrogate-target circularity: Ees/Ea/efficiency are computed from inputs by formulas, so R²≈0.97 is partly re-learning the formula. What is the added value?"** *(the deepest critique)*
- Status: **Open limitation, honestly framed.** Where: Sec. II-D (provenance), Sec. III-C, Discussion ("Validation scope").
- Response: Agreed and stated explicitly. We do **not** claim independent measurement of these indices; we frame the pH-PINN as a differentiable, physics-consistent **emulator** of these relationships — useful for counterfactual/sensitivity analysis under guaranteed energy constraints. The independent, gold-standard evidence is SVR (r = 0.916), derived entirely from directly measured (Swan–Ganz) quantities. Table III separates direct vs surrogate provenance.
- If pushed further: offer to add a held-out subset where a target is compared against an *alternative* formula/measurement, or reduce emphasis on surrogate targets in the headline claims.

**B2. "No independent invasive PV-loop ground truth."**
- Status: **Open (proof-of-concept).** Where: Discussion, Future Work.
- Response: Acknowledged as the critical next step (prospective conductance-catheter validation). Positioned as proof-of-concept; the SVR result is the strongest current external anchor.

**B3. "Cross-database distribution overlap (80.5%, 83.4%) is not model-accuracy validation."**
- Status: **Partially — framing.** Where: Sec. III-C.
- Response: Correct; overlap is a cross-cohort *consistency* check, not the accuracy claim. The accuracy evidence is the SVR Bland–Altman (r = 0.916, MAE 182.7 dyn·s/cm⁵, n = 2,704). We can soften the wording so overlap is clearly secondary.

**B4. "ICU-only cohort; generalizability to ambulatory patients."**
- Status: **Open limitation.** Where: Limitations ("ICU population bias").
- Response: Acknowledged; outpatient echocardiography validation planned.

**B5. "Tier-3 atlas registration error (ICP 0.35–0.58 > target 0.15)."**
- Status: **Open, disclosed.** Where: Sec. II-A, Limitations.
- Response: Disclosed numerically; far-field anatomy is context, not a patient-specific hemodynamic constraint. Scope limited accordingly.

---

## C. Novelty / positioning (be ready)

**C1. "PINNs and Hamiltonian NNs already exist — what's new?"**
- Response: (i) a *port*-Hamiltonian formulation with an explicit, physically grounded dissipation R(x)=r_diss·I estimated from the Windkessel characteristic impedance Zc (not energy conservation, which is non-physical here); (ii) **hard** architectural guarantees of physical validity (T,V≥0; H=T+V; R⪰0) shown by ablation to matter; (iii) an integrated anatomy→lumped-model→inference pipeline validated at ICU scale with explicit provenance separation.

**C2. "Why remove CFD / why is CFD still mentioned?"**
- Response: The exploratory CFD did not converge and is not required for any reported result; it has been removed to avoid an incomplete component. The two remaining "CFD" mentions are generic field context motivating the lumped-parameter/PINN choice.

---

## D. Quick wins if a reviewer asks (low effort, high goodwill)
- Add per-target R² table for the ablation (already computed; can expand Table II).
- Add 5-fold CV in addition to the single random split.
- Soften "validation" → "consistency check" for the distribution-overlap sentences.
- Add ORCID and a formal ethics/data-use statement.

---

### One-line honest self-assessment
The **methodological** claim (physics structure as an inductive bias that guarantees validity at no accuracy cost) is now **well-supported** by the ablation. The **clinical** claims remain **proof-of-concept**, resting on real MIMIC-IV/eICU data but surrogate-derived targets — defended by honest provenance separation and the direct-measure SVR result, not yet by independent invasive validation.
