# Paper 2 — Pre-specified analysis protocol

**Locked:** 2026-07-30, before any model was trained on these targets.
**Purpose:** fix the endpoints, the cohorts, and the success criteria in advance, so that
the choice of what to report cannot be influenced by what the results turn out to be.

Companion to Paper 1 (*Port-Hamiltonian PINN … Architecturally Guaranteed Energy
Consistency*), whose stated principal limitation this study is designed to remove.

---

## 1. The problem being addressed

Paper 1's hemodynamic targets are closed-form functions of the network's own inputs
(e.g. `E_a = P_es/SV` with `P_es ≈ 0.9·SBP`; `SVR = 80(MAP−CVP)/CO`). Its R² ≈ 0.97
therefore measures how well a smooth approximator recovers an algebraic identity, not
how well an unobserved physiological state is estimated.

Paper 2 replaces the input modality: the **shape of the invasive arterial pressure
waveform** (dicrotic notch timing, dP/dt_max, systolic/diastolic area ratio, form
factor, …). None of these quantities appear in any target formula.

### 1.1 A circularity that is *not* removed by this change — stated up front

`EV1000/CO` and `Vigileo/CO` are **FloTrac-family uncalibrated pulse-contour** devices:
they compute cardiac output *from the same arterial waveform* we use as input. Learning
to predict them is closer to distilling a proprietary algorithm than to estimating an
independent measurement. This is a weaker form of circularity than Paper 1's algebraic
identity, but it is a real one and it is **not** claimed as the study's validation.

`Vigilance/CO` is **continuous thermodilution via pulmonary artery catheter** — a
different physical measurement principle (thermal indicator dilution), with no
algorithmic dependence on the arterial pressure waveform. It is the only genuinely
independent flow reference available in this data source.

---

## 2. Cohorts (VitalDB open API, CC BY-NC-SA)

Counts verified against `https://api.vitaldb.net/trks` on 2026-07-30.

| Cohort | Definition | n | Role |
|---|---|---|---|
| **PC** | `SNUADC/ART` ∩ (`EV1000`\|`Vigileo`) CO **and** SV | 924 | training / internal validation |
| **TD** | `SNUADC/ART` ∩ `Vigilance/CO` | 65 | external validation |
| **TD‑only** | TD \ PC | **41** | **primary analysis set** |
| **VOL** | `SNUADC/ART` ∩ `Vigilance/EDV` ∩ `Vigilance/ESV` | 49 | exploratory |
| **IOH** | `SNUADC/ART` ∩ `Solar8000/ART_MBP` | 3,644 | exploratory |

TD ∩ PC = 24 cases. These 24 are **excluded from the primary analysis set** and are
reported separately as a paired within-patient comparison of the two reference methods,
because a case seen during training cannot serve as external validation.

Splits are by `caseid` throughout; one case contributes one record, so patient-level
and record-level splits coincide.

---

## 3. Endpoints

### 3.1 Primary

**Agreement between waveform-derived cardiac output and continuous thermodilution CO on
the TD-only set (n = 41), for a model trained exclusively on the PC set.**

Reported as: Pearson r, concordance correlation coefficient, Bland–Altman bias and
95% limits of agreement, and percentage error (Critchley–Critchley). **All with 95%
confidence intervals**, bootstrap (10,000 resamples, BCa). The point estimate alone is
not reportable at this sample size.

#### Power, established before any model was fitted

Simulation at n = 41 (1,500 bootstrap resamples, 3 repetitions per point) gives the
following interval widths for percentage error:

| True PE | Observed | 95% CI | Verdict available? |
|---|---|---|---|
| 15% | 14.6% | [11.7, 17.2] | yes — interchangeable |
| 20% | 19.6% | [14.4, 24.0] | yes — interchangeable |
| 25% | 23.3% | [18.1, 27.5] | yes — interchangeable |
| 30% | 27.4% | [22.2, 32.9] | **no** |
| 40% | 45.1% | [33.6, 54.5] | **no** |
| 50% | 52.8% | [40.3, 63.0] | **no** |
| 60% | 65.3% | [47.1, 77.5] | yes — not transferable |

**At this sample size the entire range from roughly 25% to 60% is uninformative
against fixed thresholds.** Since the plausible outcome for any cardiac output method
falls squarely inside that band, a decision rule based on the 30% / 45% cut-points would
almost certainly return "inconclusive". Applying it anyway, and then interpreting the
point estimate as though the interval did not exist, is exactly the error this protocol
exists to prevent.

#### Reframed decision rule: non-inferiority to the deployed device

The Critchley 30% threshold presupposes a near-perfect reference. Thermodilution is not
one, and published comparisons of FloTrac-family pulse contour against thermodilution
report percentage errors in the 40–50% range. The meaningful question is therefore not
whether the model reaches an absolute threshold, but **whether a model that never sees
thermodilution agrees with it at least as well as the commercial device does.**

This is computable. The 24 BOTH cases carry pulse-contour *and* thermodilution CO for the
same patient, giving a within-cohort estimate of the device's own agreement with the
reference. The pre-specified primary comparison is:

> Δ = PE(model vs thermodilution, TD-only n = 41) − PE(device vs thermodilution, BOTH n = 24)

with a 95% interval. Δ ≤ 0 means the model matches or beats the device it was trained to
imitate, on a reference neither was fitted to — a substantive result. Δ > 0 quantifies
how much is lost.

*Interpretation is fixed in advance.* The absolute percentage error and its interval are
reported regardless, alongside Δ. **All outcomes are publishable and will be reported as
found**, including Δ > 0 and including "inconclusive at this sample size", which the
power table above makes a likely outcome for the absolute comparison.

### 3.2 Secondary

1. **Pulse-contour CO and SV** on a held-out split of PC (n = 924). Framed as
   *agreement with a deployed device*, never as independent validation.
2. **Windkessel identification** — `R_tot` and `C` from the same waveform.
   `τ`-derived `Z_c` is **excluded by pre-specification**: Paper 1 established it is
   identifiable in only 1.7% of an 841-patient cohort, and reporting a quantity our own
   prior work found unidentifiable would be indefensible.
3. **Physical-validity diagnostics** — negative `T`, negative `V`, non-PSD `R`, under
   the Paper 1 ablation design (hard / vanilla / no-structure / soft), now on waveform
   inputs.

### 3.3 Exploratory

1. **Ventricular volumes** — `Vigilance/EDV`, `ESV`, `RVEF` (n = 49). This is the first
   direct ventricular volume measurement available anywhere in this project. Right
   ventricular, whereas the model state is left-ventricular, so no quantitative
   agreement is expected or claimed; the question is whether the learned volume state
   carries *any* signal about measured volume.
2. **Intraoperative hypotension** — MAP < 65 mmHg sustained ≥ 1 min, predicted 5 / 10 /
   15 min ahead (n = 3,644).

   **Mandatory control.** A model using *baseline MAP alone* will be fitted and reported
   alongside every hypotension result. Published critiques of commercial hypotension
   prediction have shown that most apparent performance is explained by the current
   pressure level and by label-selection artefacts. Any claimed improvement is the
   increment over this control, not the raw AUC. If the increment is not significant,
   that is the reported result.

---

## 4. Model and training

Architecture is inherited unchanged from Paper 1: softplus non-negativity on `T` and
`V`, `H = T + V` by construction, Cholesky-parameterized `R = LLᵀ ⪰ 0`. Only the input
encoder changes, from an 11-dimensional clinical feature vector to the waveform
morphology descriptors.

Training on the PC set only. Three seeds (0, 1, 2). AdamW, cosine schedule, gradient
clipping at 1.0. **The TD-only set is not touched until the model is frozen.**

### 4.1 Negative controls, fixed in advance

| Control | Purpose |
|---|---|
| Label permutation | R² must collapse to ≈ 0; guards against leakage through the pipeline |
| Morphology features removed (SBP/DBP/HR only) | isolates the contribution of *shape* over *level* |
| Linear model on the same features | establishes that any gain requires the network |
| Baseline-MAP-only (IOH) | see §3.3 |

---

## 5. What would falsify the study's premise

Stated so that it cannot be renegotiated later.

- If percentage error against thermodilution exceeds 45%, the waveform model has not
  demonstrated transferable estimation of flow, and the paper reports that.
- If the label-permutation control does not collapse to R² ≈ 0, there is leakage and
  no result is reportable until it is found.
- If the morphology-removed control matches the full model, waveform *shape* adds
  nothing and the framing must change from "morphology-driven" to "level-driven".

---

## 6. Deviations

Any departure from this protocol is to be recorded below with its date and reason,
rather than by silently editing the sections above.

| Date | Section | Change | Reason |
|---|---|---|---|
| 2026-07-30 | §3, §4 | **v4, entered before running.** (a) The out-of-distribution probe moves from synthetic Gaussian displacement to a **clinical subgroup holdout**: train on general surgery, evaluate on thoracic surgery and on transplantation, which are never seen in training. (b) Model E (output-constrained) and the probe are run over **three seeds**, and the probe over three noise realisations. (c) A **capacity-matched** output-constrained variant is added. | (a) Adding Gaussian noise in standardised feature space at 24σ produces physiologically impossible combinations (SBP below DBP, negative areas). The correct objection is that a model fed nonsense may output nonsense without that saying anything about deployment. Surgical speciality is a real and clinically meaningful shift — one-lung ventilation and the anhepatic phase produce hemodynamics absent from general surgery — and it cannot be dismissed as an artefact of the probe. The synthetic probe is retained as a secondary, stress-test result. (b) The v4 conclusion currently rests on seed 0 alone, which is the error that produced the spurious volumetric result in v3. (c) Model E has 39,720 parameters against model A's 56,215, so the comparison confounds the constraint with capacity. |
| 2026-07-30 | §3, §4 | **v3, entered before running.** (a) Patient demographics (age, sex, height, weight, BMI) added as model inputs. (b) A **trending analysis** added as a co-primary: four-quadrant concordance and polar-plot angular agreement on within-patient changes in cardiac output. | (a) Decomposing the v2 result gives 53.7² = 40.1² + 35.7²: the model inherits the device's own 40.1% error and adds 35.7% of its own. FloTrac computes CO as HR·σ(AP)·χ where χ is calibrated on demographics, so the model was being asked to reproduce a function of (waveform, demographics) from waveform alone. Demographics are not arguments of the thermodilution measurement, so this does not reintroduce circularity into the primary endpoint. (b) Absolute agreement and trending ability are distinct, and for hemodynamic monitoring trending is the clinically decisive property; it is standard to report both. The v2 window data already contains ~30 time-ordered windows per patient, so no new data is required. **Not reporting trending because the absolute result was negative would be selective reporting; it is therefore fixed here as a co-primary, before the trending numbers are computed.** v1 and v2 stand as reported. |
| 2026-07-30 | §4 | **v2: multiple analysis windows per case** (anchors every 5 min, up to 40 per case, patient-level grouping preserved) instead of one 3-minute window. Entered *before* v2 was run. | The v1 design gave 866 training rows for a 56,000-parameter network while discarding hours of waveform per case. Seed-to-seed R² spread was 0.287 on a fixed dataset, and the linear baseline was both more accurate and twenty times more stable — the signature of variance, not of an absent signal. **The v1 result in `RESULTS_v1.md` stands as reported whatever v2 shows, and both are reported together.** v2 is not a second attempt at a better number; if v2 does not improve on v1, that is itself the answer to whether the v1 negative was a power problem. |
| 2026-07-30 | §2 | **Reference values are now read over the same 3-minute window as the waveform**, not as a whole-case median. Whole-case medians are retained as `*_case` columns for a sensitivity analysis. Requires full re-extraction. | Found while investigating an implausible first result (internal R² = 0.03 for pulse-contour CO, where the reference device computes CO from the very waveform being used as input). Within-case CO varies with a coefficient of variation of 13–19%, comparable to the between-patient spread, so pairing a whole-case median with a single 3-minute window was close to pairing each patient's waveform with a random draw of their own CO. This is a data-alignment defect, not a finding: it would have produced a false negative on the primary endpoint. Detected and corrected before any result was interpreted. |
| 2026-07-30 | §2 | Realised cohort sizes are smaller than the track index implied: **TD-only 31** (not 41), BOTH 24, PC 866. Seven cases carried a `Vigilance/CO` track whose values were entirely non-finite or non-positive, and three more failed waveform quality control (fewer than 10 usable beats in the analysis window). No case was excluded on the basis of its values. | Track presence in the index does not guarantee usable data. Recorded because the primary set is now smaller than the one the §3.1 power analysis was computed for, which widens every interval further and makes the fixed-threshold comparison even less informative — reinforcing, not undermining, the move to the Δ comparison. |
| 2026-07-30 | §3.1 | Added the power table; replaced the fixed-threshold decision rule with non-inferiority to the pulse-contour device (Δ), estimated on the 24 BOTH cases | Simulation performed before any model was fitted showed that at n = 41 the 95% interval for percentage error spans a threshold everywhere between ≈25% and ≈60%, so the original rule would have returned "inconclusive" for essentially any realistic result. Recorded here rather than by silent edit. |
