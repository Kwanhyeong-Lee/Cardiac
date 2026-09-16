# Reviewer Response — Preparation Notes
### "Port-Hamiltonian PINNs for Cardiac Hemodynamic Inference with Architecturally Guaranteed Energy Consistency" (IEEE J-BHI / TBME)

*Anticipatory rebuttal for the five most likely Major-Revision points. Each entry: the probable reviewer comment, a ready-to-adapt response, the exact in-manuscript evidence, and the preemptive change already made in this revision. Concede what is fair; defend scope precisely.*

---

## 1. Absence of invasive (conductance-catheter) PV-loop validation

**Likely comment.** The headline accuracies (R² ≥ 0.95) for E_es, E_a, and mechanical efficiency are agreement with *surrogate* single-beat estimates, not with invasively measured conductance-catheter PV loops. This is emulation of a formula, not validation against physiological ground truth.

**Response (draft).** We agree, and we have been explicit about this from the outset rather than obscuring it. Section II-D and Table II categorize *every* validation variable by provenance: cardiac output (thermodilution) and systemic vascular resistance (Swan–Ganz) are directly measured, whereas E_es, E_a, and mechanical efficiency are surrogate-derived. We therefore make no claim of invasive ground-truth agreement for the surrogate parameters; the Discussion ("Validation scope") explicitly positions the pH-PINN as a *differentiable, physics-consistent emulator* of these established relationships, suitable for counterfactual and sensitivity analysis, not as an independent measurement of them. Obtaining simultaneous conductance-catheter PV loops across a 9,842-patient MIMIC-IV/eICU cohort is neither ethically nor technically feasible; the study's aim is to recover energetically consistent trajectories from non-invasive inputs. Our strongest evidence — SVR, Pearson r = 0.916, derived entirely from invasive Swan–Ganz measurements — is reported as such. Prospective validation against conductance-catheter PV loops is stated as the primary next step.

**Evidence.** §II-D; Table II; Discussion "Validation scope"; §III-C (SVR r = 0.916); §IV-B Future Work.

**Preemptive change made.** Added Chen et al. (2001) as the citation for the single-beat surrogate; the emulator framing was sharpened in the remaster.

---

## 2. Over-simplification of the dissipation matrix R(x) = r_diss · I

**Likely comment.** Real cardiovascular dissipation (vortices, viscosity, valvular turbulence) is anisotropic and spatiotemporally varying. Collapsing it to one scalar undercuts the rigor of the port-Hamiltonian formulation; a tensor R(x) or a formal proof is expected.

**Response (draft).** The scalar form is a deliberate, physically grounded first-order choice, not a structural limitation of the framework. r_diss is derived from the Windkessel characteristic impedance Z_c (Eq. 4) — the resistive component of aortic input impedance, i.e., exactly the macroscopic energy loss that a lumped model can identify from non-invasive data. Crucially, **the same architecture already supports a fully learned, Cholesky-parameterized PSD matrix R(x) = LLᵀ**: this is precisely the dissipation used by the hard-constrained model in our ablation (Section II-F, III-B; Supplementary Fig. S2 / S3). Moving from the scalar Z_c-calibrated form to an anisotropic, state-dependent R(x) is therefore a change of *parameterization*, not of framework. A spatially resolved R(x) learned from Doppler-derived turbulence data is identified as future work.

**Evidence.** Eq. 4; §II-F (ablation uses Cholesky R = LLᵀ ⪰ 0); Supplementary Fig. S2, Table S3; Limitations "Scalar dissipation approximation."

**Preemptive change made.** Added the explicit "parameterization, not framework" sentence to Limitations; the architecture block diagram (Fig. S2) shows both the scalar production R and the learned PSD ablation R.

---

## 3. Tier-3 atlas anatomy and ICP registration distance (0.35–0.58 > target 0.15)

**Likely comment.** Only the LV is patient-specific; the other structures are atlas-registered, and the ICP distances miss the target. How much does this geometric error propagate into the mechanical-efficiency / hemodynamic inference?

**Response (draft).** We use "patient-anchored" rather than "patient-specific" precisely to signal this three-tier hierarchy (Section II-A, Supplementary Table S2), and we report the ICP distances transparently. Importantly, the hemodynamic inference is driven by the Tier-1 LV state and the lumped Windkessel parameters; the atlas-registered far-field structures (RV, atria, great vessels) contribute anatomical *context* but do not enter the LV-centric hemodynamic targets. The ICP distance therefore bounds the geometric fidelity of the whole-heart mesh, not the accuracy of the reported LV pump-function inference. Mesh refinement (e.g., diffeomorphic registration) is noted as future work.

**Evidence.** §II-A (tier definitions); Supplementary Table S2; Limitations "Patient-specificity hierarchy."

**Preemptive change made.** Added the sentence stating that far-field atlas error contributes context but does not enter the LV-centric targets.

---

## 4. Narrow inclusion / exclusion criteria and ICU-cohort bias

**Likely comment.** Excluding significant valvular disease, RV pathology, and congenital disease removes much of the real ICU population, so clinical utility looks narrow.

**Response (draft).** The exclusions define the model's *validated operating domain* — the region where its physics assumptions hold (unidirectional aortic outflow, two-chamber LV–aorta Windkessel, LV-centric geometry) — rather than a claim of universal applicability (Section II-G). Unlike a purely statistical model, a physics-constrained model offers explicit stability guarantees *within* its assumptions, which is the property that makes it trustworthy where it applies. Because the pipeline is modular, right-ventricular, valvular, and congenital physiology can be incorporated as additional layers without altering the validated LV core. We also acknowledge ICU-population bias and plan validation in ambulatory echocardiography cohorts.

**Evidence.** §II-G (inclusion/exclusion, target population); Limitations "Target population constraints" and "ICU population bias."

**Preemptive change made.** Added the "exclusions delimit the validated domain / modular extension" sentence to Limitations.

---

## 5. Explicit mathematical definition of the state x and the energy H = T + V

**Likely comment.** Equation 1's state vector x should be mapped concretely to physical quantities, and the paper should show how T(x) and V(x) are parameterized inside the network to form H = T + V.

**Response (draft).** Added. Section II-B now defines the port-Hamiltonian state x = (q, p) ∈ ℝ⁵ — generalized chamber volumes q = (V_LV, V_LA, V_art) and inertance-scaled valve-flow momenta p = (p_mv, p_ao) — together with auxiliary elastances (E_es, E_ed, V_0, τ). The energy heads are given explicitly: V(q) = softplus(f_V(q)) ≥ 0 and T(q,p) = ½ pᵀ M⁻¹(q) p with M⁻¹(q) = L(q)L(q)ᵀ + εI ≻ 0, so that T, V ≥ 0 and the partition H = T + V hold by construction rather than by penalty. The full input-feature list, state bounds, per-head definitions, and a new architecture block diagram are provided in Supplementary Section S3 (Fig. S2, Table S3).

**Evidence.** §II-B (new state/energy paragraph); Supplementary Section S3, Fig. S2, Table S3.

**Preemptive change made.** New §II-B paragraph; Supplementary S3 with the state-variable table and the architecture block diagram (Fig. S2).

---

## Bonus — the two enhancements that push acceptance toward ≥ 90%

- **Open code + reproducible data (done).** A reproducibility package (model, training, ablation, and figure code + the derived result files needed to reproduce every figure) is released with the submission; the Data and Code Availability statement now says so and commits to a public GitHub/Zenodo deposit upon acceptance. *Action for you:* create the repo and paste the URL into the statement before/at submission.
- **Architecture block diagram (done).** Added as Supplementary Fig. S2 — input → encoder → state (q, p) → energy heads (V, T → H = T + V) + R(x) → port-Hamiltonian dynamics → Suga–Sagawa decoder → clinical targets, with the by-construction guarantees banner.

## General posture
Respond point-by-point in a numbered letter; open by thanking the reviewers; concede the one fair structural point (no invasive PV-loop ground truth) while defending the study's scope and purpose; keep every claim tied to a section, number, or citation. The manuscript's own "Validation scope" and Limitations already do most of this work — quote them.
