# Paper 2 — v2 (multi-window) results

Data: `wave_windows_0.csv` — 28,814 windows from 956 cases (PC 899 / TD-only 33 / BOTH 24).
~22,400 training rows per split, against 712 in v1.
All agreement statistics are computed on **patient medians**, so n is still the number of
independent patients (33 for the primary endpoint), not the number of windows.

`RESULTS_v1.md` stands as reported. Both are reported together, as fixed in
`PROTOCOL.md` §6 before v2 was run.

---

## 1. The v1 diagnosis was correct: it was variance, not absent signal

| | v1 (1 window/case) | v2 (~30 windows/case) |
|---|---|---|
| Training rows | 712 | 22,400 |
| pH-PINN R² | 0.046 ± **0.287** | **0.253 ± 0.058** |
| pH-PINN PE | 63.9 ± **13.4** | **53.7 ± 0.26** |
| Linear R² | 0.153 ± 0.147 | 0.180 |
| Linear PE | 50.1 | 58.0 |

Seed-to-seed spread in percentage error fell from 13.4 to **0.26** points. Two of the
pre-specified falsification conditions that fired in v1 no longer fire:

- **§4.1 (linear baseline).** The network now beats it — R² 0.253 vs 0.180, PE 53.7% vs
  58.0%. In v1 the ordering was reversed.
- **§5 (morphology-removed control).** Full morphology 0.320 vs level-only 0.190 at
  seed 0, and PE 53.6% vs 55.1%. Waveform *shape* contributes beyond pressure level.

The permutation control still collapses (R² −0.776), so there is no leakage introduced by
having several windows from the same patient — `GroupShuffleSplit` on `caseid` holds.

## 2. Primary endpoint: still not met, and by a wider margin

| | PE vs thermodilution | 95% CI | r | n |
|---|---|---|---|---|
| pH-PINN (waveform) | 53.7% ± 0.26 | [45.0, 63.6] | 0.53 | 33 |
| FloTrac device | **40.1%** | [32.5, 50.4] | **0.80** | 24 |
| **Δ** | **+13.6 pp** | — | | |

The model improved (63.9 → 53.7%), but **the device benchmark improved more** (53.0 →
40.1%), so Δ went from +10.9 to +13.6 points. This is easy to misread as a regression: it
is not. The v2 device figure is the more accurate of the two, because aggregating ~28
windows per patient removes noise from the device's own estimate exactly as it does from
the model's. The v1 figure of 53.0% was inflated by that noise. The honest reading is that
**FloTrac agrees with thermodilution better than v1 suggested, and the gap to an open
model built from published waveform features is real.**

## 3. Ablation: the Paper 1 claim is restored at this scale

Seed means over 5,551 held-out windows (185 held-out patients):

| Model | R² | T<0 | V<0 | R⊁0 | ‖H−(T+V)‖² |
|---|---|---|---|---|---|
| A: pH-PINN (hard) | 0.253 ± 0.058 | **0** | **0** | **0** | 0.0 |
| B: Vanilla MLP | 0.308 | 405 | 2,222 | n/a | 4.9×10⁻² |
| C: No-structure | 0.314 | 1,395 | 1,457 | **5,551 (all)** | 2.7×10⁻¹ |
| D: Soft-constraint | 0.318 / 0.236 | **8, 1** | **4, 3** | 0 | 1.7×10⁻⁷ |

Model A produced zero violations on every seed and every window. Model C again produced a
non-positive-semidefinite dissipation matrix in **every single case**.

**Model D fails here.** It reached 8 and 1 negative kinetic energies and 4 and 3 negative
potential energies on the two seeds tested — after reaching exactly zero in v1. The
v1 finding that a penalty was sufficient was an artefact of the smaller, easier problem.
On 22,400 training rows the penalty again makes violations rare but not impossible, which
is the Paper 1 result and the one claim in this line of work that has now held under two
independent input modalities.

Accuracy remains indistinguishable across all four architectures (0.25–0.32, within
seed spread), so the discriminating axis is validity, not accuracy — again as in Paper 1.

## 4. The most citable number

**FloTrac versus continuous thermodilution, 24 patients, patient-median aggregation:
PE = 40.1% [32.5, 50.4], r = 0.80, bias −1.11 L/min, limits of agreement −3.93 to +1.71.**

Even with the noise-reduced estimate, the commercial device does not meet the
conventional 30% interchangeability threshold, and its confidence interval excludes it.

---

## 5. Where this leaves the paper

Three claims are now supported and one is not.

**Supported.** Waveform morphology carries information about cardiac output beyond
pressure level. A network extracts more of it than a linear model. Hard architectural
constraints deliver physical validity that a tuned penalty does not, on a second input
modality independent of Paper 1.

**Not supported.** That a model trained only on pulse-contour output transfers to
thermodilution as well as the device itself. It does not: Δ = +13.6 points.

The remaining question is whether the gap is a ceiling of the feature set or of the
sample. 33 patients for the primary endpoint is small, and the CI [45.0, 63.6] still
spans the range in which no verdict against a fixed threshold is possible (`PROTOCOL.md`
§3.1 power table). Nothing in this dataset can settle that; a larger thermodilution
cohort would be required.

## 6. Not yet run

Seeds 1–2 for the level-only, linear, and B/C ablation arms; the R_tot secondary; the
exploratory volumetric (`Vigilance/EDV`, `ESV`, n=49) and hypotension endpoints. None of
these change the primary reading, but the ablation table should be completed to three
seeds before the numbers go into a manuscript.
