# PROTOCOL v2 — pre-specification of the two remaining benefit tests

Written **2026-08-13, before either experiment was run.** Registered here because the
question being asked is "is there any axis on which the constrained architecture is better,"
and that question invites fishing. Two hypotheses are named, their endpoints and decision
rules are fixed here, and **both are reported in full whatever they show.** No third axis
will be added after seeing these results; if both fail, that is the finding.

## Why this exists

Across five tasks the constrained and unconstrained architectures are indistinguishable in
accuracy. On INSPIRE, with 101,688 transitions, the four architectures span 0.0017 in
one-step R² and the free MLP is nominally the best of them. There is at present **no axis on
which the port-Hamiltonian architecture outperforms a plain MLP.** Two axes on which physics
priors are conventionally expected to help have not been tested.

## H1 — sample efficiency

**Hypothesis.** Physics structure acts as a prior, so its benefit should be largest when
data are scarce and should vanish as data grow. With 101,688 transitions the benefit, if it
exists, is invisible; it should appear on a subsampled learning curve.

**Design.** INSPIRE, task 5. The test set is fixed once per seed and never subsampled. The
training-plus-validation pool is subsampled **at the operation level**, not the row level,
because the realistic scarce-data regime is fewer patients, not fewer rows per patient.

    fractions f in {0.02, 0.05, 0.10, 0.25, 0.50, 1.00} of training operations
    models    P, Pm, U, F
    seeds     0..4   (five, not three -- the n=3 limitation is fixed here)

**Primary endpoint.** One-step skill against persistence, `1 - MSE_model / MSE_persistence`,
evaluated on the fixed test set.

**Secondary endpoint.** 12-step (60-minute) skill against persistence at the same horizon.

**Decision rule, fixed in advance.** H1 is supported only if *both* hold:

1. at f ≤ 0.05, mean skill of the better constrained model (P or Pm) exceeds F by more than
   0.01, with the same sign in at least 4 of 5 seeds; **and**
2. the gap *shrinks* monotonically in f, reaching ≤ 0.005 at f = 1.00.

Condition 2 matters as much as condition 1. A constant offset at every fraction is not
sample efficiency; it is a different model being slightly better everywhere, which the
full-data result has already ruled out. The claim is an **interaction**, and it must look
like one.

**What refutes H1.** A flat difference across fractions, or a gap that does not exceed 0.01
at f ≤ 0.05.

## H2 — incremental value of the learned physical state for a clinical outcome

**Hypothesis.** The learned Hamiltonian H, dissipation R and latent state x carry
information about patient condition beyond the raw vital signs they were computed from. If
so, the architecture produces something an informatics reader can use, which is the
contribution IEEE JBHI's scope asks for and which the paper currently lacks.

**Design.** INSPIRE outcomes present in `operations`: postoperative ICU admission (14.66% of
operations) as primary; in-hospital death (1.19%) as secondary, reported but expected to be
underpowered at 2,501 operations (~30 events).

Three nested feature sets, operation level, all summarised over the operation:

    BASE   raw state summaries: mean/min/max/sd of CO, art_sbp, art_dbp, hr,
           plus time-weighted vasoactive exposure, age, sex, ASA, emergency
    +PH    BASE plus H, T, V, and the trace and minimum eigenvalue of R
    +LAT   BASE plus the 4-dimensional learned latent state summaries

Same gradient-boosted classifier for all three; operation-level splits; five seeds.

**Primary endpoint.** AUROC of `+PH` minus AUROC of `BASE`, with a DeLong test on the paired
test set.

**Decision rule, fixed in advance.** H2 is supported only if the mean AUROC increment
exceeds **0.02** with a DeLong p < 0.05 in at least 4 of 5 seeds. An increment that is
positive but smaller than 0.02 is reported as null: at this cohort size it is not separable
from the noise of refitting.

**Mandatory control.** The same features extracted from the **unconstrained** model U. If
`+PH` from U helps as much as `+PH` from P, the information is in the network's capacity and
not in the physics, and H2 is refuted even if the increment is large.

## Reporting commitment

Both hypotheses are reported with all fractions, all seeds and both directions, in
`RESULTS_v9_benefit.md`, whether they succeed or fail. If both fail, the conclusion recorded
will be that on these tasks the port-Hamiltonian architecture delivers a guarantee and no
measurable performance benefit — which is the honest reading and the one the paper will
carry.

## Prior expectation, recorded before running

Stated so it cannot be revised afterwards: **H1 roughly even odds, H2 less likely than that.**
Four architectures sitting within 0.0017 on 101,688 transitions is weak evidence that the
structure has little left to capture on this task at any sample size.
