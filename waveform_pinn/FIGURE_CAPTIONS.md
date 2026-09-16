# Figure captions

Draft captions. Every number is read from the saved result files by `make_figures.py`;
none is typed by hand into the plotting code.

---

## Paper A — the reference standard sets the floor

### Figure A1 — Pulse-contour cardiac output against continuous thermodilution

Twenty-four liver transplant patients carrying both an uncalibrated pulse-contour monitor
(EV1000/Vigileo) and a continuous thermodilution pulmonary artery catheter (Vigilance),
aggregated to one value per patient. **(A)** Method comparison against the line of
identity; Pearson r = 0.80 [0.55, 0.94]. **(B)** Bland–Altman: bias −1.11 L/min, limits of
agreement −3.93 to +1.71, percentage error 40.1% [32.5, 50.4] by bias-corrected and
accelerated bootstrap. The interval excludes the conventional 30% interchangeability
threshold, so the device that these studies commonly treat as a reference does not itself
meet the criterion they apply to new methods.

### Figure A2 — Error inherited from the reference, and what demographics recover

**(A)** Percentage error against thermodilution for four input configurations, with the
device's own 40.1% marked. Errors do not add linearly: a model trained on the device's
output inherits the device's disagreement and adds its own in quadrature. **(B)** The
model's own contribution, √(PE² − 40.1²). Supplying the patient demographics that the
device's calibration uses — age, sex, height, weight, BMI, body surface area — reduces it
from 35.7% to 25.8%. **(C)** Internal R² for reproducing the device. Morphology alone
reaches 0.320 and demographics alone 0.658, but together 0.875: the two input sets carry
complementary information rather than the same information twice.

### Figure A3 — Continuous thermodilution cannot adjudicate short-interval trending

**(A)** Four-quadrant concordance of the pulse-contour device against continuous
thermodilution, as a function of the interval between compared readings; 15% exclusion
zone, n above each point. The device is beat-responsive and is sold for trending, yet its
concordance rises monotonically with interval (0.598 → 0.744). **(B)** A reference whose
own averaging window exceeds the compared interval will produce exactly this pattern.
Neither the device nor a waveform model reaches the conventional 92% threshold at any
interval, and polar radial limits of agreement are approximately ±200° for both.

### Figure A4 — Selective prediction in the population where the model degrades

Transplant patients, 6,007 windows. Readings are abstained on in order of Mahalanobis
distance from the training distribution. **(A)** Median absolute error against coverage;
random abstention is flat (0.558 → 0.585), so the score is doing real work rather than
leaving easier cases behind. **(B)** Ninetieth-percentile error and the share of retained
readings still wrong by more than 1 L/min. Halving the tail requires discarding 70% of
readings; at a more plausible 30% abstention, 23% of what remains is still wrong by more
than 1 L/min. The mechanism works and is not sufficient.

---

## Paper B — what architectural constraints guarantee

### Figure B1 — Accuracy is not the discriminating axis; physical validity is

Four capacity-matched architectures. A imposes non-negative kinetic and potential energy
through softplus, forms H = T + V by composition, and factors the dissipation as R = LLᵀ.
B has no physics structure. C shares A's topology with the constraints removed. D adds the
same constraints as a training penalty. **(A)** Mean R² on three datasets spanning two
input modalities and an order of magnitude in difficulty — clinical features (Paper 1),
waveform morphology, and waveform plus demographics. The four architectures are
indistinguishable on all three. **(B)** Physical-validity violations on 5,539 held-out
windows, seed means over three seeds. **(C)** Models A and D at scale: A is at zero because
the violating region is not in the architecture's range, while D — a tuned penalty —
produced one violation in 16,626 windows. Rare is not impossible.

### Figure B2 — The guarantee covers the constrained quantities, and stops there

**(A)** Held-out inputs displaced by Gaussian noise in standardised feature space.
Model A's internal state remains admissible at every displacement, while the quantity a
clinician reads — cardiac output — reaches −29.6 L/min at 24σ, no better than the
unconstrained model C. Model E, which forms CO = SV / T_period from strictly positive
components, is at zero throughout. **(B)** The same models under a real distribution shift:
trained on general surgery, evaluated on thoracic surgery and transplantation. **No model
produces a single negative output**, including C. Displacing standardised features by 24σ
produces physiologically impossible combinations, and the behaviour there does not
transfer to populations a monitor actually encounters. Model E's guarantee is
mathematically real and its practical benefit is undemonstrated.

### Figure B3 — Validity transfers under clinical shift; accuracy does not

Trained on 389 general-surgery patients, evaluated on 226 thoracic and 175 transplant
patients never seen in training. **(A)** R² falls by 0.34 on transplant, identically for
every architecture: the constraints govern admissibility, not accuracy. **(B)**
Non-positive-semidefinite dissipation matrices. Models A and E are at zero on every set;
the unconstrained model C fails in every window of every set. The separation established
in-distribution holds on populations the model has never seen, which is the claim that a
synthetic probe cannot support.

---

## Figure B4 — The output constraint: a learned floor, and what a real guarantee buys

**(A)** Models E and E2 map the positive quotient `CO = softplus/softplus` to the target
scale through a free affine layer, `y = _scale·CO + _shift`. Positivity therefore depends on
`_scale > 0`, which nothing enforces, and the fitted `_shift` placed a floor at 3.38–3.39
L/min — above 13.9% of the reference cardiac outputs, at the clinically dangerous low end.
Model E3 replaces the free layer with the exact inverse of the target standardisation,
`y = (CO − μ)/σ`, so `CO > 0` holds by algebra with a floor of exactly zero.
**(B)** Two-sided range probe at 40σ displacement, 12,000 probes per model. Counting only
negative outputs — the metric used before the audit — scores E, E2 and E3 at zero. Counting
both bounds shows what the guarantee actually covers: E3's positivity is genuine and 5,658
of its 12,000 probes still land outside 0.5–20 L/min, reaching 18,751 L/min. Positivity is
not plausibility. E and E2 appear better here only because the learned floor compresses the
output range, which is the same defect seen in (A).
**(C)** Held-out R² at patient level, three seeds each. Neither repairing E's 17,263-parameter
deficit nor making the guarantee architectural changes accuracy; every difference sits inside
the between-seed spread.

## Figure B5 — Connecting the port: passivity is delivered, boundedness is not, and the parameterisation decides

Model P is port-Hamiltonian with hard constraints (`H = T+V ≥ 0`, `R = LLᵀ ⪰ 0`, `J` skew).
Pm imposes mathematically identical guarantees but obtains PSD from a softplus diagonal,
which is linear in its head output where `LLᵀ` is quadratic. U has the same topology with
every guarantee removed; F is a free MLP with no Hamiltonian.

**(A)** Energy change at zero input, computed in float64 against a relative threshold and
counted over steps in which the state actually moved. With `u = 0`, passivity requires
`dH/dt ≤ 0` whenever `R ⪰ 0`. P and Pm never gain energy — 0 of 106,007 and 0 of 31,824
steps. U gains on 48.6%. The hatched bars give the same counts under the sign flip
`(H,J,R) → (−H,−J,−R)`, which leaves the dynamics bit-identical: P and Pm cannot use it
because softplus and Cholesky fix their signs, while U's near-symmetry under it shows that
U has no energy function at all, only a function labelled H.
**(B)** Fraction of trajectories still inside the physiological box after 200 steps,
denominator restricted to trajectories that started inside. Pm and U are indistinguishable;
P alone is worse.
**(C)** The explanation. Admissibility plotted against the median first-step magnitude at 6σ;
circles are seeds, crosses are model means. P's quadratic dissipation parameterisation makes
its vector field grow one polynomial order faster than U's, giving 1.7× larger steps far from
the data. Matching the growth order in Pm — with every guarantee intact — removes the effect.
The constraint is not what harmed boundedness; the parameterisation was.
