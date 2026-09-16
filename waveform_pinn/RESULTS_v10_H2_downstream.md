# v10 — H2 (incremental clinical value): refuted

Pre-specified in `PROTOCOL_v2_benefit.md` before running, together with its decision rule
and the recorded prior expectation ("less likely than H1"). Reported in full as committed.

## Question

Do the learned Hamiltonian H, the dissipation R and the effort variables ∂H/∂x carry
information about the patient beyond the raw vital signs they were computed from? If they
do, the architecture produces an informatics output — the contribution IEEE JBHI's scope
asks for and the one the paper otherwise lacks.

## Result

Outcome: postoperative ICU admission. Operation-level splits; the dynamics model is fitted
on training operations only, so no test operation influences either the features or the
classifier. `HistGradientBoostingClassifier`, identical for all feature sets.

| seed | test events | BASE | +PH from P | Δ | DeLong p | +PH from U *(control)* | Δ |
|---|---|---|---|---|---|---|---|
| 0 | 669 | 0.7932 | 0.7982 | +0.0050 | 0.75 | 0.7886 | −0.0046 |
| 1 | 669 | 0.8025 | 0.8053 | +0.0028 | 0.83 | 0.8112 | +0.0087 |
| 2 | 676 | 0.8211 | 0.8046 | **−0.0165** | 0.44 | 0.8119 | −0.0092 |
| **mean** | | **0.8056** | **0.8027** | **−0.0029** | — | 0.8039 | −0.0017 |

**Decision rule, applied as written.**

1. Mean increment > 0.02 with DeLong p < 0.05 in ≥ 4 of 5 seeds → observed **−0.0029**,
   significant in **0 of 3**. Fails, and with the wrong sign.
2. The P increment must exceed the unconstrained-U control → **−0.0029 vs −0.0017**. Fails.

**H2 is not supported.** The physical quantities add nothing to a gradient-boosted model
that already has the raw state summaries, and the unconstrained model's equivalent block is
no worse — which was the pre-specified control for exactly this outcome.

## A design flaw found on execution, and it matters more than the numbers

The protocol assumed an ICU-admission base rate of 14.66%, taken from the whole INSPIRE
cohort. **In this cohort the rate is 89.2%.** The cohort is defined by the presence of a
continuous vasoactive infusion, and almost every patient who receives one goes to intensive
care. The outcome is therefore close to degenerate: 669–676 events in roughly 750 test
operations.

This was not foreseeable from the protocol's base rate but it should have been foreseeable
from the cohort definition, and it is recorded here rather than in a footnote. Two
consequences:

- The test as run is weakly informative in the negative direction. A near-constant outcome
  is easy to predict from anything, which compresses the room any feature block has to add
  value. AUROC 0.81 from BASE alone is consistent with that.
- **Re-running with more seeds would not fix it.** The limitation is the cohort, not the
  sample. A fair test of H2 needs an outcome with a usable event rate in a vasoactive-treated
  population — in-hospital death is 5.3% here, about 130 events, which is closer to usable
  but still thin, or an intraoperative outcome such as sustained hypotension, which would
  need separate extraction.

Three seeds were run rather than five. That is a deviation, recorded: the mean increment is
−0.0029 against a +0.02 threshold, the sign is wrong, and no seed approaches significance,
so two more seeds cannot change the verdict. The cohort issue above is the reason not to
invest further in this design rather than the seed count.

## Where this leaves the two benefit tests

| | hypothesis | verdict |
|---|---|---|
| H1 | physics structure buys sample efficiency | **refuted, reverse effect larger** (`RESULTS_v9`) |
| H2 | learned physical state adds clinical predictive value | **refuted** (this file) |

Both were pre-specified with decision rules fixed in advance, and both were reported
whatever they showed. Combined with `RESULTS_v6`–`v8`, the position is now fully
characterised:

**Across five tasks, three independent data sources, two countries and two care settings,
the port-Hamiltonian architecture is never measurably better than an unconstrained network
of the same size, is worse when data are scarce, and produces a passivity guarantee whose
scope is exactly the predicate it encodes.**

That is the paper. There is no version of these results that supports a
"physics-constrained model performs better" claim, and no further axis will be tested —
the protocol committed to two and both are done.

## Files

`h2_downstream.py`, `results_h2_downstream.json`, pre-specification in
`PROTOCOL_v2_benefit.md`.
Reproduce: `python3 h2_downstream.py --seed S --only P`, `--only U`, then `--seed S`,
then `--summary`.
