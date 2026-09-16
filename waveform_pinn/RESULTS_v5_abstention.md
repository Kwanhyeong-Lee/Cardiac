# v5 — abstention instead of recalibration

Motivated by the question of whether transplant patients need their own correction
factor. They do not, and the reason points somewhere more useful.

---

## 1. Why a correction factor cannot work

Decomposing the transplant failure by type, on patient medians:

| Group | slope | offset | r | residual SD |
|---|---|---|---|---|
| general surgery (in-dist) | 1.043 | −0.02 | 0.897 | 0.66 |
| thoracic | 1.014 | −0.02 | 0.901 | 0.57 |
| **transplant** | **1.051** | −0.32 | **0.665** | **1.39** |

The slope is 1.05 and the offset is −0.32 L/min against a mean CO of 5.7. Calibration is
close to intact. What doubles is the **scatter**.

| Transplant (n = 175) | R² |
|---|---|
| as-is | 0.490 |
| offset removed | 0.513 |
| optimal affine (slope + intercept) | **0.519** |
| ceiling = r² | 0.519 |

**Any linear recalibration buys 0.028 of R².** A correction factor is a tool for
systematic error; this error is not systematic.

That distinction matters clinically. A consistent bias is something a user learns to
allow for. Irregular error is not — the reading is wrong at unpredictable moments, and
nothing on the screen says which.

## 2. What the model does know

Distance from the training distribution predicts the model's own error.

| Score | Spearman ρ (transplant) | p |
|---|---|---|
| Mahalanobis | 0.298 | 8×10⁻¹²⁴ |
| Ensemble SD (3 inits) | 0.301 | 3×10⁻¹²⁶ |
| Mahalanobis (thoracic) | 0.165 | 6×10⁻³⁹ |

Risk–coverage on the transplant set, abstaining on the highest-scoring windows:

| Coverage | Mahalanobis median | p90 | >1 L/min | Random median |
|---|---|---|---|---|
| 100% | 0.558 | 1.98 | 29.8% | 0.558 |
| 90% | 0.512 | 1.67 | 26.1% | 0.563 |
| 80% | 0.487 | 1.58 | 24.5% | 0.562 |
| 70% | 0.469 | 1.50 | 23.3% | 0.551 |
| 50% | 0.439 | 1.41 | 20.6% | 0.562 |
| 30% | 0.416 | 1.30 | 17.7% | 0.585 |

The random-abstention control is flat (0.558 → 0.585), so the curve is not an artefact of
discarding data and landing on easier leftovers. The score is doing real work.

## 3. But the operating point is poor, and that is the honest headline

To cut the 90th-percentile error from 1.98 to 1.30 L/min you must discard **70% of
readings**. At a more plausible 30% abstention the tail falls from 1.98 to 1.50, and
**23% of what remains is still wrong by more than 1 L/min**.

The ensemble score is no better than the input-distance score (ρ 0.301 vs 0.298; median
0.459 vs 0.469 at 70% coverage), despite costing three models. On thoracic — barely out of
distribution to begin with, median error 0.364 against 0.324 in-distribution — both scores
are weak and the gain is 0.04 L/min.

So: the signal is real and highly significant, and it is not strong enough to make the
model safe on transplant patients by abstention alone. Reported as a working component
with a stated operating cost, not as a solution.

## 4. What this contributes to the argument

It completes the picture of what the architecture does and does not buy.

- The energy constraints guarantee that the internal state is **admissible**, at every
  input, including two surgical populations never seen in training.
- They say nothing about whether the number is **accurate**. Transplant R² of 0.49
  against 0.81 in-distribution is untouched by them.
- Accuracy under shift needs a separate mechanism. Distance-based abstention is one, it
  measurably works, and on this problem it is not sufficient.

Three properties, three mechanisms, none substituting for another. That is the same
lesson as the output-scope result in `RESULTS_v4_scope.md`, arriving from the other
direction: a constraint delivers the predicate it encodes, and every other property you
want has to be built and validated on its own.

## 5. Limitations

Single seed for the underlying model; the abstention scores are computed on one trained
model per group. The ensemble used three initialisations on one split, not three splits.
Coverage thresholds here are descriptive — no threshold was pre-specified, and none should
be adopted from this analysis without a calibration set held out for that purpose.
