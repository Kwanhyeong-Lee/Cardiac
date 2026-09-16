# Paper A — outline

**Working title.** The reference standard sets the floor: quantifying the error a
pulse-contour-trained cardiac output model inherits

**Target.** *British Journal of Anaesthesia*, *Journal of Clinical Monitoring and
Computing*, or *Anesthesiology*. Short report or original article, 2,500–3,500 words.

**One-sentence claim.** Studies that train or validate cardiac output methods against an
uncalibrated pulse-contour device inherit that device's 40.1% disagreement with
thermodilution as an error floor, and this floor exceeds the 30% interchangeability
threshold those studies routinely invoke.

---

## Why this is worth publishing

That FloTrac agrees poorly with thermodilution is known. Three things here are not
routinely stated:

1. The floor is **quantified with an interval that excludes 30%** — [32.5, 50.4] — in an
   open, reproducible cohort, rather than asserted from a meta-analytic range.
2. The inheritance is made **arithmetic**: 53.7² = 40.1² + 35.7², so a reader can compute
   what their own model's imitation error must be to reach any target.
3. Continuous thermodilution is shown, from the data, to be **unable to adjudicate
   trending below roughly 15 minutes** — and the demonstration is that a purpose-built
   trending monitor also fails against it, which no single-method study can show.

## Data

VitalDB, open access, CC BY-NC-SA. 956 surgical cases with `SNUADC/ART` at 500 Hz;
28,814 three-minute analysis windows. Of these, 24 patients carry simultaneous
pulse-contour (EV1000/Vigileo) and continuous thermodilution (Vigilance) cardiac output.
All agreement statistics on patient medians.

Note for Methods: all 24 paired and all 33 thermodilution-only cases are liver transplant
patients. State it; do not generalise beyond that population without saying so.

## Results, in order

**1. Device against reference.** PE 40.1% [32.5, 50.4], r 0.80 [0.55, 0.94], bias −1.11,
LoA −3.93 to +1.71, n = 24. Bland–Altman figure.

**2. Error inheritance.** A model trained on the device's output, evaluated against
thermodilution: PE 53.7%. Decomposition into the inherited 40.1% and the model's own
25.8–35.7% depending on whether demographics are supplied. Table.

**3. Demographics.** FloTrac's calibration uses them; a model denied them cannot
reproduce it. Internal R² 0.320 → 0.875 on adding age, sex, height, weight, BMI, BSA;
imitation error 35.7% → 25.8%. Includes the demographics-only control (R² 0.658) showing
the two input sets are complementary rather than redundant.

**4. Trending resolution.** Four-quadrant concordance versus interval, for the device:
0.598 / 0.633 / 0.733 / 0.728 / 0.744 at 5 / 10 / 15 / 20 / 30 min. Monotone. Neither the
device nor the model reaches 92% at any interval; polar radial LoA ≈ ±200° for both.
Figure: concordance against interval, two curves.

**5. Transplant.** Slope 1.05 and offset −0.32 but residual SD doubled; optimal affine
recalibration buys 0.028 of R². Distance-based abstention reduces the 90th-percentile
error from 1.98 to 1.50 L/min at 70% coverage, against a flat random-abstention control.
Risk–coverage figure.

## Discussion

The practical guidance is short. If you validate against a pulse-contour device, report
the device's own agreement with an independent reference in your cohort, and interpret
your percentage error relative to that floor rather than to 30%. If you report trending,
state the interval and show that your reference can resolve it.

Limitations: 24 paired patients, single centre, all transplant, one device family.

## What is already computed

Everything in §Results. `device_benchmark_v2.json`, `trending_results.json`,
`RESULTS_v3.md`, `RESULTS_v5_abstention.md`. Figures are drawn; no new runs required.

## Figures

All four are drawn and in `figures/`; captions in `FIGURE_CAPTIONS.md`.
Regenerate with `python3 make_figures.py A`.

| Figure | Content |
|---|---|
| A1 | Device vs thermodilution: scatter + Bland–Altman |
| A2 | Error inheritance, own-error in quadrature, complementarity |
| A3 | Concordance vs interval — the reference cannot resolve short changes |
| A4 | Risk–coverage with random-abstention control |

## Remaining before submission

- Literature framing: how many recent waveform-CO papers cite the 30% threshold while
  using a pulse-contour reference — a citation count, not a systematic review
- Confirm VitalDB licence terms permit the derived tables in a supplement
