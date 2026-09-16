# v4 — what an architectural guarantee actually covers

This is the result the methods paper is built on. It was not planned; it came from asking
whether the physical-validity guarantee established in v1–v3 buys anything a user would
notice.

---

## 1. The probe

Take a held-out batch (n = 400 windows) and displace it from the training distribution by
adding noise of 0, 6 and 24 training standard deviations per feature. Then ask two
separate questions of each model: are the *internal* energy quantities still admissible,
and is the *output* — the cardiac output number a clinician would read — still physical.

| Shift | Model | CO min ~ max (L/min) | CO<0 | T<0 | V<0 | R⊁0 |
|---|---|---|---|---|---|---|
| 0σ | A: hard constraints | 2.6 ~ 9.6 | 0 | 0 | 0 | 0 |
| 0σ | C: unconstrained | 2.6 ~ 9.5 | 0 | 283 | 275 | 400 |
| 0σ | **E: constraint propagated** | 3.4 ~ 9.4 | **0** | 0 | 0 | 0 |
| 6σ | A | **−7.8** ~ 27.0 | **24** | 0 | 0 | 0 |
| 6σ | C | −10.8 ~ 26.6 | 26 | 118 | 261 | 400 |
| 6σ | **E** | 3.4 ~ 17.4 | **0** | 0 | 0 | 0 |
| 24σ | A | **−29.6** ~ 92.5 | **94** | 0 | 0 | 0 |
| 24σ | C | −38.2 ~ 103.7 | 104 | 120 | 302 | 400 |
| 24σ | **E** | 3.4 ~ 386.4 | **0** | 0 | 0 | 0 |

## 2. What it shows

**Model A's guarantee does not reach its output.** T, V and R stay admissible at every
input — that part is exactly as claimed in Paper 1 and in v1–v3. But cardiac output
reaches −29.6 L/min at 24σ, and does so in 94 of 400 cases, which is no better than the
unconstrained model C (104). The softplus and the Cholesky factorisation constrain the
internal energy objects; the decoder that produces the output is an ordinary linear map
with nothing attached to it.

**Propagating the construction closes it exactly.** Model E emits stroke volume and heart
period as strictly positive quantities and forms CO = SV / T_period. Positivity then holds
for the same reason T ≥ 0 holds — it is a property of the architecture's range, not of the
data. Zero negative outputs at every displacement tested, out to 24σ.

**And it costs nothing.** Internal R² 0.869 against A's 0.895; percentage error against
thermodilution 46.7% [37.5, 59.2] against A's 47.7%. Within seed spread, with 39,720
parameters against A's 56,215.

## 3. The limit of the fix — stated, because it is the actual thesis

Model E guarantees CO > 0. It does **not** guarantee CO < anything: at 24σ the maximum
reaches 386 L/min, roughly seventy times a physiological value. The bulk still behaves
(median 3.4, 11 of 400 above 25 L/min), but no upper bound exists because none was
constructed.

This is the general lesson, and it is sharper than "hard constraints are better than
penalties":

> **An architectural constraint guarantees exactly the predicate it is built from, and
> nothing adjacent to it.** Softplus on T and V guarantees non-negative energy — not a
> sensible output. SV/T_period guarantees positive cardiac output — not a bounded one.
> Every property that matters needs its own construction, and a paper claiming a
> "physically constrained" model owes the reader the list of predicates it actually
> enforces.

Much of the physics-informed literature reports hard constraints without separating the
constrained quantities from the reported ones. The distinction is invisible in-distribution
— all three models look identical at 0σ — and only appears under displacement.

## 4. A diagnostic error found along the way

The first version of this probe reported model E violating R ⪰ 0 in 14, 42, 77 and 106
cases as the shift increased, which made no sense: E inherits `dissipation()` from A
unchanged, and R = LLᵀ is positive semidefinite as a matter of algebra.

It was the diagnostic. At extreme inputs the eigenvalues of R span 10³–10⁴, and a float32
eigendecomposition returns minima around −1×10⁻⁴ — a relative magnitude of 9.2×10⁻⁸,
which is float32 epsilon. Judged against the fixed −1×10⁻⁶ threshold in `violations()`
those registered as breaches of a property that cannot be breached.

`violations()` now uses a relative tolerance, λ_min < −10⁻⁶·λ_max, computed in float64.
All phantom counts disappear, including the 4 and 7 previously attributed to model A at
12σ and 24σ. The counts for model C are unaffected: its R is symmetric but not
factorised, and its violations are real.

Worth reporting rather than silently fixing. A fixed absolute tolerance on a quantity
whose scale varies by four orders of magnitude will manufacture violations, and any study
that counts PSD breaches this way is exposed to the same artefact.

## 5. Bearing on Paper 1

Paper 1 says the network guarantees that the *states* it predicts are admissible, and
measures exactly that. It is accurate as written. But a reader will reasonably extend it
to the reported quantities, and §2 above shows that extension is false for the
architecture as published.

The manuscript should say which predicates are enforced and which are not, and the E
result gives it something better than a caveat — a construction that closes the gap at no
accuracy cost.
