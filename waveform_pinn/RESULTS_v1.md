# Paper 2 — first complete run against the pre-specified protocol

Data: `wave_features2_0.csv` (time-aligned re-extraction, 2026-07-30).
Cohorts: PC 866 train / TD-only 31 primary / BOTH 24 device benchmark.
Three seeds. Analysis exactly as fixed in `PROTOCOL.md` before any result was seen.

---

## 1. Negative controls — all pass

| Control | Internal R² (3 seeds) | TD PE |
|---|---|---|
| Permuted labels | **−0.687 ± 0.225** | 78.0% |
| Level only (no morphology) | −0.061 ± 0.120 | 63.7% |
| Linear baseline | 0.153 ± 0.147 | **50.1% ± 0.6** |

Permutation collapses as it must, so there is no leakage through the pipeline and
everything below is a real measurement rather than an artefact.

## 2. Primary endpoint — not met

| | PE vs thermodilution | 95% CI | n |
|---|---|---|---|
| pH-PINN (waveform) | **63.9% ± 13.4** | [45.6, 102.2] across seeds | 31 |
| FloTrac device | **53.0%** | [40.6, 77.6] | 24 |
| **Δ** | **+10.9 pp** | — | — |

The model does not match the device it was trained to imitate. Pearson r against
thermodilution was 0.46 for the model versus 0.71 for the device.

## 3. The result that decides the paper

**The linear model beats the network, and is twenty times more stable.**

| | R² mean ± SD | PE mean ± SD |
|---|---|---|
| pH-PINN | 0.046 ± **0.287** | 63.9 ± **13.4** |
| Linear | 0.153 ± 0.147 | 50.1 ± **0.6** |

Per-seed pH-PINN R²: 0.26, 0.15, **−0.28**. A spread that large on a fixed dataset is
the signature of an under-determined fit, not of a target without signal.

`PROTOCOL.md` §4.1 states that if the linear baseline matches the network, the network is
not what produced the result. §5 states that if the morphology-removed control matches
the full model, waveform shape adds nothing. **Both conditions have fired.**

## 4. Ablation — physical validity holds, but discriminates less than in Paper 1

Per 178 held-out cases, seed means over three seeds:

| Model | R² | T<0 | V<0 | R⊁0 | ‖H−(T+V)‖² |
|---|---|---|---|---|---|
| A: pH-PINN (hard) | 0.046 ± 0.287 | **0** | **0** | **0** | 0.0 |
| B: Vanilla MLP | 0.050 ± 0.232 | 59.3 | 50.0 | n/a | 1.5×10⁻¹ |
| C: No-structure | 0.055 ± 0.208 | 61.3 | 72.3 | **178 (all)** | 1.6 |
| D: Soft-constraint | 0.035 ± 0.246 | **0** | **0** | **0** | 0.0 |

The architectural guarantee holds exactly, and the unconstrained model C again violates
positive semidefiniteness in every single case. But **model D reached zero violations on
all three seeds here**, whereas in Paper 1 it retained 0.3 negative-energy and 1.3
non-PSD cases per seed. On this smaller, lower-dimensional problem the penalty was
sufficient. This weakens the "penalty makes violations rare, architecture makes them
impossible" claim in the regime tested here, and must be reported as such rather than
carried over from Paper 1 unchanged.

## 5. A finding worth keeping regardless

**FloTrac versus continuous thermodilution in this cohort: PE = 53.0% [40.6, 77.6],
r = 0.71, bias −1.03 L/min, limits of agreement −4.62 to +2.57.**

The commercial device fails the conventional 30% interchangeability standard by a wide
margin, and the open linear model on published waveform features matches it (50.1%).
This reframes what "good agreement" can mean for any waveform-derived cardiac output
method, and it is measured here rather than cited.

---

## 6. Reading

The negative result on the primary endpoint is real and will be reported. But the design
almost certainly under-powered the model: each case contributes **one** 3-minute window,
giving 866 training rows for a 56,000-parameter network on 21 features, while hours of
waveform per case go unused. The evidence that this is the binding constraint, rather
than absence of signal, is that the linear model is both better and far more stable —
the classic signature of variance rather than bias.

The natural correction is multiple windows per case, which `extract_ioh.py` already
implements as anchors: roughly 30–40 rows per case, patient-level grouping preserved, on
the order of 30,000 training rows. That is a design correction, not a second attempt at a
better number, and it must be entered in `PROTOCOL.md` §6 **before** it is run — together
with a statement that the v1 result above stands as reported whatever v2 shows.
