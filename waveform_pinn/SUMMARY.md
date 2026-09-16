# Waveform pH-PINN — consolidated record

Everything run on 2026-07-30, in order. Read this first; the `RESULTS_v*.md` files hold
the detail and `PROTOCOL.md` §6 holds every deviation with its date and reason.

---

## 1. What was asked and what was found

The study set out to remove the surrogate circularity in Paper 1 by replacing clinical
features with invasive arterial waveform morphology, and to test whether the resulting
model estimates cardiac output. It does not, and the reasons are now quantified.

| Version | Change | Primary result |
|---|---|---|
| v1 | one 3-min window per case, 712 rows | R² 0.046 ± 0.287, PE 63.9% — **discarded**, alignment defect |
| v2 | ~30 windows per case, 22,400 rows | R² 0.253 ± 0.058, PE 53.7% ± 0.26 |
| v3 | + patient demographics | R² 0.875 ± 0.023, PE 47.7% |
| v4 | clinical subgroup holdout | thoracic R² 0.84, transplant R² 0.50 |
| v5 | abstention instead of recalibration | tail error 1.98 → 1.50 L/min at 70% coverage |

## 2. Findings, by how well they are supported

### Solid

**The reference device's own error is the floor.** FloTrac against continuous
thermodilution, 24 paired transplant patients, patient-median aggregation:
**PE = 40.1% [32.5, 50.4]**, r = 0.80, bias −1.11 L/min, LoA −3.93 to +1.71. The
confidence interval excludes the conventional 30% interchangeability threshold.

**The error decomposes.** 53.7² = 40.1² + 35.7². Any model trained against a
pulse-contour device inherits that device's disagreement with thermodilution and adds its
own imitation error on top. Adding demographics — which FloTrac's calibration uses and the
v1/v2 model did not have — cut the imitation term from 35.7% to 25.8%.

**Architectural constraints cost nothing and work.** Across Paper 1 (R² ≈ 0.97), v2
(≈ 0.25) and v3 (≈ 0.88), and across two surgical populations never seen in training, the
four capacity-matched models are indistinguishable in accuracy. Only the hard-constrained
model attains zero physical-validity violations: 0 in 16,626 held-out windows, against
4,032 negative kinetic energies and 6,202 non-PSD dissipation matrices for the
unconstrained model on thoracic patients alone. The soft-constrained model reached 1
violation in 16,626 — rare, not impossible.

**Continuous thermodilution cannot adjudicate short-interval trending.** Four-quadrant
concordance rises monotonically with interval for the *device* — 0.598, 0.633, 0.733,
0.728, 0.744 at 5–30 min. A reference against which a purpose-built trending monitor also
fails is not resolving physiology at that timescale. Neither method reaches the 92%
threshold at any interval.

**Transplant cannot be fixed by recalibration.** Slope 1.051, offset −0.32 L/min, but
residual SD 1.39 against 0.66 in-distribution. Optimal affine correction moves R² from
0.490 to 0.519 — a ceiling of r². The failure is scatter, not bias.

**The model knows when it is unreliable, weakly.** Mahalanobis distance from training
predicts absolute error (ρ = 0.298, p = 8×10⁻¹²⁴); median error falls 0.558 → 0.416 L/min
from full coverage to 30%, while random abstention stays flat. An ensemble of three
initialisations is no better (ρ = 0.301).

### Not supported

**That the model transfers to thermodilution as well as the device.** Δ = +7.6 points
after demographics. On the 24 paired patients the device is better on point estimates
(PE 40.1% vs 59.9%) but the paired test cannot distinguish them (Wilcoxon p = 0.29,
model more accurate in 9 of 24).

**That the guarantee's failure to reach the output matters in practice.** The synthetic
probe showed model A emitting −29.6 L/min at 24σ. Under real clinical shift **no model
produces a single negative output**, including the entirely unconstrained one. The
synthetic probe fed physiologically impossible inputs and the finding does not replicate.

**That abstention makes the model safe on transplant patients.** Discarding 30% of
readings leaves 23% of the remainder wrong by more than 1 L/min.

### Attempted and uninformative

**Ventricular volumes** (Vigilance EDV/ESV, 47 patients). Seed 0 gave ESV R² = 0.624;
across seeds 0.674 / 0.032 / −0.376. Fifteen validation patients support no estimate.

**Intraoperative hypotension.** Extraction implemented and smoke-tested; not run.

## 3. Five times a control overturned an apparent finding

Each was caught by something fixed in the protocol before the result existed.

| What looked true | What was true | Caught by |
|---|---|---|
| Waveform morphology carries no CO signal (R² 0.03) | Reference values were whole-case medians paired with a 3-min window; within-case CO varies with CV 13–19% | Implausibility against the device's own construction, plus the linear baseline beating the network |
| PE 30%/45% thresholds would decide the primary endpoint | At n = 41 the interval spans a threshold everywhere from 25% to 60% | Power simulation run before any model was fitted |
| The output-constrained model violates R ⪰ 0 | Float32 eigenvalues of a matrix spanning 10³–10⁴ against a fixed −10⁻⁶ tolerance | The violation was of a property that cannot be violated |
| The guarantee's gap at the output is a practical problem | Under real clinical shift nobody produces bad output | Clinical subgroup holdout replacing the synthetic probe |
| Ventricular volumes are predictable (R² 0.62) | 0.11 ± 0.53 across seeds | Multi-seed requirement |

## 4. Figures

Seven figures, four for Paper A and three for Paper B, in `figures/` with captions in
`FIGURE_CAPTIONS.md`. `make_figures.py` reads every number from the saved result files;
none is retyped into the plotting code.

## 5. What is worth writing

**Paper A — the reference-standard benchmark.** The device PE with its interval, the
error decomposition, the trending-resolution limit, and the open pipeline. Short,
self-contained, addressed to anaesthesia and monitoring. See `PAPER_A_OUTLINE.md`.

**Paper B — the scope of architectural constraints.** Constraints are free, replicated
across three datasets spanning R² 0.25–0.97 and two unseen surgical populations; the
guarantee covers exactly the predicate it encodes; propagating it to the output is
possible at no cost but its benefit is undemonstrated. Framed as capability, not benefit.
See `PAPER_B_OUTLINE.md`.

**Not worth writing.** The cardiac digital twin framing — the anatomical pipeline never
entered inference. The cardiac output estimator as a product — PE 47.7%, worse than a
device that itself fails its own field's threshold. Any claim that physical constraints
make predictions more trustworthy — v4 refutes it.

## 6. Files

| File | Contents |
|---|---|
| `PROTOCOL.md` | Pre-specified endpoints, power analysis, §6 deviation log |
| `RESULTS_v1.md` … `RESULTS_v5_abstention.md` | Per-stage results |
| `DISCARDED.md` | The v1 alignment defect, kept deliberately |
| `RUN.md` | Local execution, including the two pitfalls not to reintroduce |
| `models.py` | Models A–E, violation diagnostics with relative tolerance |
| `agreement.py` | BCa bootstrap, Bland–Altman, percentage error, DeLong |
| `trending.py` | Four-quadrant concordance, polar plot |
| `abstention.py` | Distance scores, risk–coverage with random control |
| `ood_clinical.py` | Subgroup holdout probe |
| `wave_windows_demo.csv` | 28,814 windows, 956 cases, with demographics |
