# v4 — clinical out-of-distribution holdout

Entered in `PROTOCOL.md` §6 before running, specifically to test whether the v4 synthetic
probe survives a real distribution shift. It does not, and that is the result.

Train: general surgery only (389 patients, ~11,700 windows).
Evaluate: thoracic surgery (226 patients) and transplantation (175 patients), neither
seen in training. Three seeds. Model A = constrained state, C = unconstrained,
E = constraint propagated to the output.

---

## 1. Result

Seed means over three seeds; counts are windows.

| Model | Set | R² (patient) | CO range | **CO < 0** | T<0 | R⊁0 |
|---|---|---|---|---|---|---|
| A | general surgery (in-dist) | 0.80 | 2.2 ~ 10.3 | **0** | 0 | 0 |
| A | **thoracic** | 0.84 | 2.0 ~ 10.9 | **0** | 0 | 0 |
| A | **transplant** | 0.50 | 2.0 ~ 10.5 | **0** | 0 | 0 |
| C | general surgery | 0.81 | 2.2 ~ 10.5 | **0** | 1,848 | 2,969 |
| C | **thoracic** | 0.84 | 1.8 ~ 10.4 | **0** | 4,032 | 6,202 |
| C | **transplant** | 0.51 | 1.9 ~ 10.6 | **0** | 2,743 | 6,007 |
| E | general surgery | 0.77 | 3.8 ~ 11.0 | **0** | 0 | 0 |
| E | **thoracic** | 0.80 | 3.8 ~ 10.6 | **0** | 0 | 0 |
| E | **transplant** | 0.40 | 3.8 ~ 11.2 | **0** | 0 | 0 |

## 2. The synthetic probe does not replicate

The Gaussian probe reported model A emitting cardiac outputs down to −29.6 L/min in 94 of
400 cases at 24σ, and model E fixing it. **Under a real clinical shift, no model produces
a single negative output.** Not A, not the entirely unconstrained C, not E. Output ranges
stay between roughly 1.8 and 12 L/min in every group.

The objection anticipated against the synthetic probe was correct. Displacing standardised
features by 24σ produces combinations that cannot occur — systolic below diastolic,
negative areas — and a model's behaviour there says nothing about deployment. Two
surgical specialities with genuinely different hemodynamics do not come close to
provoking the failure.

**So model E's contribution is mathematically real and practically undemonstrated.** It
guarantees CO > 0 by construction; nothing in this data shows a case where that guarantee
is what stopped a bad output. It should be reported as a construction with a proof, not as
a fix for an observed problem.

## 3. What the real shift does confirm

The internal-validity result replicates, and more strongly than before. Model C violates
non-negativity of kinetic energy in 4,032 thoracic windows and emits a non-positive-
semidefinite dissipation matrix in **all 6,202**, on patients it has never seen. Models A
and E are at zero everywhere. This is now demonstrated under a shift no reviewer can call
artificial.

Accuracy is again indistinguishable: A 0.84, C 0.84, E 0.80 on thoracic. The constraint
costs nothing and buys internal admissibility, which is the claim.

## 4. A generalisation gap the constraint does not touch

R² falls from about 0.82 on thoracic to about 0.47 on transplant, equally for all three
models. Transplant hemodynamics — anhepatic phase, reperfusion — are genuinely harder, and
architectural energy constraints do nothing about it. Worth stating plainly: the constraint
governs admissibility, not accuracy, and this is what that looks like.

## 5. Something that should have been noticed when the cohorts were defined

**All 33 thermodilution cases and all 24 paired cases are transplant patients.** Every
number reported for the primary endpoint in v1–v3 was therefore measured under
distribution shift, against the training population.

That was not deliberate and was not flagged. It cuts both ways: the PE of 47.7% is a
harder test than it appeared, but the cohorts are also less comparable than the protocol
implied. It must be stated in the paper, and it is a reason the transplant R² of 0.47 is
the relevant generalisation figure rather than the 0.87 reported in v3.

---

## 6. Where this leaves the argument

**Stronger than before.** Architectural constraints deliver internal physical validity
under real clinical distribution shift, at no accuracy cost, where an identical-capacity
unconstrained model fails in every window. Three datasets, three surgical populations.

**Weaker than yesterday's draft.** The claim that the guarantee's failure to reach the
output is a practical problem is not supported. It is a scoping observation, provable in
principle and visible only under inputs that cannot occur.

**New and honest.** The evaluation cohort was a distribution shift all along.

This is the third time a pre-specified control has overturned an apparent finding — after
the v1 alignment defect and the v3 volumetric noise. The pattern is worth stating in the
paper's discussion: each headline that survived did so because something was in place that
could have killed it.
