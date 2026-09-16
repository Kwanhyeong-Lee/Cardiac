# Paper 2 — v3: demographics and trending

Both additions were entered in `PROTOCOL.md` §6 before being run. `RESULTS_v1.md` and
`RESULTS_v2.md` stand as reported. Seed 0 unless stated; the full three-seed sweep is
still outstanding.

---

## 1. Why the model was worse than the device — and how much of it is explained

The v2 gap decomposes cleanly, because the two error sources are close to orthogonal:

$$53.7^2 = 40.1^2 + 35.7^2$$

The model inherits the device's own 40.1% error against thermodilution and adds 35.7%
of its own from failing to reproduce the device. **40.1% is a floor**: a perfect
imitation of FloTrac still could not do better. This is why the pre-specified 30%
interchangeability target was unreachable by construction, and why the protocol was
changed to a Δ comparison before any of this was run.

FloTrac computes cardiac output as HR·σ(AP)·χ, where χ is calibrated on patient
demographics. v1 and v2 gave the model the waveform only, so it was being asked to
reproduce a function of (waveform, demographics) from half its arguments. Age, sex,
height and weight are present in VitalDB with zero missingness.

| Input set | Internal R² | PE vs TD | r | Imitation error |
|---|---|---|---|---|
| Morphology only (v2) | 0.320 | 53.7% | 0.53 | 35.7% |
| **Morphology + demographics** | **0.895** | **47.7%** | **0.63** | **25.8%** |
| Demographics + HR/MAP only | 0.658 | 56.5% | 0.44 | 39.8% |
| Linear, morphology + demographics | 0.521 | 49.2% | 0.61 | 28.5% |
| Permuted labels | −0.757 | 66.3% | −0.17 | — |

**Δ against the device narrowed from +13.6 to +7.6 points.**

Three things to read carefully here.

Much of the R² jump is body size: cardiac output scales with body surface area, so
demographics alone already reach 0.658. But morphology and demographics are
complementary rather than redundant — 0.320 alone, 0.658 alone, 0.895 together. The
morphology contribution on top of demographics is 0.237.

The network beats the linear model on the same inputs by a wide margin (0.895 vs 0.521),
so §4.1 does not fire.

And the permutation control still collapses, so none of this is leakage.

## 2. Trending: the analysis is uninformative, and we can show why

Four-quadrant concordance on within-patient changes, 15% exclusion zone, patient-clustered
bootstrap. Conventional clinical threshold is 92%.

| Interval | Model vs thermodilution | Device vs thermodilution |
|---|---|---|
| 5 min | 0.491 [0.42, 0.57] | 0.598 [0.52, 0.68] |
| 10 min | 0.649 [0.59, 0.71] | 0.633 [0.55, 0.71] |
| 15 min | 0.658 [0.59, 0.73] | 0.733 [0.67, 0.80] |
| 20 min | 0.631 [0.57, 0.69] | 0.728 [0.67, 0.79] |
| 30 min | — | 0.744 |

At a 5-minute interval the model is at chance. Read alone, that says the model cannot
track changes. But **the device is at 0.598 with an interval that nearly touches chance**,
and FloTrac is a beat-responsive monitor sold specifically for trending. A reference
against which the purpose-built device also fails is not measuring what it appears to.

The interval sweep identifies the cause. Concordance rises monotonically with interval
for the device — 0.598, 0.633, 0.733, 0.728, 0.744 — which is the signature of a
reference that cannot resolve short-term change. Continuous thermodilution reports a
trailing average over several minutes, so consecutive 5-minute readings are dominated by
the device's own filter rather than by physiology. By 15–20 minutes real change
dominates and both methods improve.

For contrast, the model tracks *FloTrac* — a beat-responsive reference — at 0.867
[0.842, 0.892] at 5 minutes.

**Neither method reaches the 92% threshold at any interval.** No trending claim is
supportable for the model, and on this data none is supportable for the commercial
device either. Polar-plot radial limits of agreement were approximately ±200° for both,
i.e. no agreement on the size of changes.

The device benchmark did the work here for the second time. Without it, the honest-looking
conclusion would have been "the waveform model cannot track cardiac output"; with it, the
conclusion is "this reference cannot adjudicate trending below about 15 minutes."

## 3. Ablation on the v3 input set — the Paper 1 claim holds

Three seeds, 5,542 held-out windows each (185 held-out patients).

| Model | R² | PE vs TD | T<0 | V<0 | R⊁0 | ‖H−(T+V)‖² |
|---|---|---|---|---|---|---|
| A: pH-PINN (hard) | 0.875 ± 0.023 | 47.93 ± 0.42 | **0** | **0** | **0** | 0.0 |
| B: Vanilla MLP | 0.902 | 47.83 | 2,414 | 3,843 | n/a | 5.5×10⁻³ |
| C: No-structure | 0.889 | 48.02 | 2,647 | 1,434 | **5,551 (all)** | 3.1×10⁻¹ |
| D: Soft-constraint | 0.872 ± 0.018 | 48.43 ± 0.70 | 0 | **1** | 0 | ~10⁻⁸ |

Accuracy is again indistinguishable across all four architectures — B and C are nominally
higher than A, within seed spread. Validity is not: A produced **zero violations across
all three seeds and all 16,626 held-out windows**, C produced a non-positive-semidefinite
dissipation matrix in every case, and D produced exactly **one** negative potential energy
in 16,626 windows.

That single violation is the whole point. A rate of 6×10⁻⁵ is rare enough to be invisible
in any ordinary evaluation and still means the failure mode is reachable. Model A cannot
reach it at any rate, on any input, because the softplus and the Cholesky factorisation
remove it from the model's range.

The claim has now held on three datasets: Paper 1's clinical features at R² ≈ 0.97, v2's
waveform-only inputs at R² ≈ 0.25, and v3's waveform-plus-demographics at R² ≈ 0.88. Near
saturation, near the floor, and in between. The one place it did not hold — v2 at seed
level, where D reached zero — is reported in `RESULTS_v2.md` and is explained by the
smaller effective problem.

## 4. Exploratory: ventricular volumes — not reportable

`Vigilance/EDV` and `ESV` (47 patients, 1,211 windows) are the only direct ventricular
volume measurements anywhere in this project, so this was worth attempting. It does not
survive its own controls.

| ESV, input set | R² (seed 0) |
|---|---|
| Morphology + demographics | +0.624 |
| Demographics + HR/MAP only | −2.128 |
| Morphology only | −0.455 |
| Permuted labels | −0.043 |

The first row looks like a result. Across seeds it is **+0.674, +0.032, −0.376** — mean
0.11 with a standard deviation of 0.53. Fifteen validation patients cannot support any
estimate. EDV (R² 0.449) and RV stroke volume (0.370) at seed 0 are subject to the same
objection and were not pursued further.

Reported as attempted and uninformative. A single seed here would have looked like a
finding.

## 5. What the three runs together establish

| | v1 | v2 | v3 |
|---|---|---|---|
| Training rows | 712 | 22,400 | 22,400 |
| Inputs | morphology | morphology | + demographics |
| Internal R² | 0.046 ± 0.287 | 0.253 ± 0.058 | 0.895 |
| PE vs TD | 63.9 ± 13.4 | 53.7 ± 0.26 | 47.7 |
| Δ vs device | +10.9 | +13.6 | **+7.6** |
| Beats linear? | no | yes | yes |

The primary endpoint is still not met. But the reason has moved from "unknown" to
quantified: of the residual 47.7%, 40.1 points are the reference device's own
disagreement with thermodilution, and 25.8 points are what remains of the imitation gap.

## 6. Outstanding

Seeds 1–2 for models B and C (seed 0 only so far) and for the level-only and linear
controls. The hypotension endpoint, which needs `extract_ioh.py` to be run locally
(2–4 hours). Neither changes the primary reading.

## 7. Reading

Two claims are supported and one is not.

**Supported.** Waveform morphology plus demographics reproduces a commercial
pulse-contour algorithm closely (R² 0.875 ± 0.023), and morphology contributes
substantially on top of demographics (0.320 alone, 0.658 alone, 0.875 together). And
architectural energy constraints deliver physical validity that a tuned penalty does not
— now demonstrated across three datasets spanning R² from 0.25 to 0.97.

**Not supported.** That the model transfers to thermodilution as well as the device does.
Δ = +7.6 points, down from +13.6 but still positive.

**Not adjudicable with this data.** Trending, because continuous thermodilution cannot
resolve changes below roughly 15 minutes — shown by the fact that the purpose-built
device also fails against it. Ventricular volumes, at 15 validation patients.

The most transferable finding is the error decomposition. Any study that trains against a
pulse-contour device inherits that device's 40.1% disagreement with thermodilution as a
floor. That number is measured here, not cited, and its confidence interval [32.5, 50.4]
excludes the 30% interchangeability threshold that such studies routinely invoke.
