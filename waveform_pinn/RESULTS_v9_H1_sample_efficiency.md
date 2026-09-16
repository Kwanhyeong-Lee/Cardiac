# v9 — H1 (sample efficiency): refuted, and the reverse effect is larger

Pre-specified in `PROTOCOL_v2_benefit.md` **before running**, including the decision rule and
a recorded prior expectation of "roughly even odds". Reported here in full, as committed.

## Verdict

**H1 is not supported.** The gap runs the other way, at every fraction, and it is largest
exactly where the prior was supposed to help.

## Primary endpoint — one-step skill against persistence

| train fraction | train ops | F (free MLP) | P | Pm | U | **gap: best constrained − F** |
|---|---|---|---|---|---|---|
| 0.02 | 30 | **0.0912** | 0.0608 | 0.0671 | 0.0656 | **−0.0241** |
| 0.05 | 75 | **0.1164** | 0.0800 | 0.0884 | 0.0895 | **−0.0280** |
| 0.10 | 150 | **0.1175** | 0.1093 | 0.1130 | 0.1121 | −0.0044 |
| 0.25 | 375 | **0.1251** | 0.1207 | 0.1222 | 0.1216 | −0.0029 |
| 0.50 | 750 | 0.1229 | 0.1215 | 0.1211 | 0.1209 | −0.0014 |
| 1.00 | 1,500 | **0.1325** | 0.1280 | 0.1258 | 0.1273 | −0.0045 |

Per seed at the decision fractions:

| | f = 0.02 | f = 0.05 |
|---|---|---|
| seeds where any constrained model beats F | **1 / 5** | **0 / 5** |
| mean gap | −0.024 | −0.028 |

**Decision rule, applied as written.** Condition 1 required the better constrained model to
exceed F by more than +0.01 at f ≤ 0.05 with the same sign in ≥ 4 of 5 seeds. The observed
gap is −0.024 and −0.028, with the *wrong* sign in 9 of 10 seed×fraction cells. Condition 1
fails decisively, so H1 fails regardless of condition 2.

## The interaction exists — pointing the other way

This is not a flat offset. The penalty for imposing structure is **−0.028 at 75 training
operations and −0.004 by 150**, converging to roughly −0.004 at full data. Physics structure
behaves here like a *mis-specified* prior: it costs most when data are scarce and the cost
washes out as data accumulate. That is the mirror image of the textbook expectation, and it
is a cleaner result than the one the hypothesis predicted.

## Secondary endpoint — 12-step (60-minute) rollout: the structured models blow up

Runs whose 60-minute skill fell below −1, i.e. the rollout diverged:

| train fraction | F | P | Pm | U |
|---|---|---|---|---|
| 0.02 | **0 / 5** | 3 / 5 | 4 / 5 | 3 / 5 |
| 0.05 | **0 / 5** | 3 / 5 | 4 / 5 | 4 / 5 |
| 0.10 | 0 / 5 | 0 / 5 | 0 / 5 | 0 / 5 |
| 0.25 | 0 / 4 | 0 / 5 | 0 / 5 | 0 / 5 |
| ≥ 0.50 | 0 | 0 | 0 | 0 |

Median 60-minute skill at f = 0.05: F **+0.154**, against P −237,106, Pm −53,499,
U −25,959. The free MLP never diverged in any of the 21 runs at any fraction; the three
port-Hamiltonian-form models diverged in 17 of 40 runs below f = 0.10.

**A mechanism, consistent with `RESULTS_v7`.** The port form composes the update as a
*product* of separately learned objects, `xdot = (J − R)∂H/∂x + g·u`. Each factor is poorly
determined at 30–75 operations and the errors multiply. The free MLP parameterises `Δx`
directly — one estimated object, no compounding. This is the same phenomenon that made
`R = LLᵀ` (quadratic in its head output) behave worse than `R = diag(softplus)` (linear) in
v7: **what is multiplied matters more than what is constrained.** v7 found it across
parameterisations at full data; v9 finds it across sample sizes.

## Deviations from the protocol, recorded

`f = 0.50` and `f = 1.00` were completed for seed 0 only; `f ≤ 0.25` is complete at all five
seeds. This is a compute limit, not a choice made after seeing results. It does not affect
the verdict: condition 1 depends only on `f ≤ 0.05`, which is complete at five seeds, and it
failed in the wrong direction by a margin of roughly 3× the threshold. Condition 2 is moot.
Three independent full-data runs from `RESULTS_v8` (seeds 0–2, identical configuration)
agree with the seed-0 value here.

## What this means for the paper

**There is no axis on which the port-Hamiltonian architecture outperforms a plain MLP on
these tasks.** Accuracy: equal at full data, worse when scarce. Robustness under iteration:
worse when scarce, equal otherwise. Admissibility: equal at best. The only thing the
architecture delivers that the MLP cannot is the passivity guarantee itself, and v7 showed
that guarantee does not extend to the properties a practitioner would assume follow from it.

A "pure pHNN, we-have-a-better-method" paper cannot honestly be written from this evidence.

What *can* be written is stronger than a marginal win: a quantified account of what
architectural physics constraints cost and deliver in perioperative haemodynamic modelling,
with the mechanism identified — multiplicative composition of learned operators — and
replicated across parameterisations, sample sizes, two datasets and two countries.

## Files

`h1_sample_efficiency.py`, `results_h1_sample_efficiency.json`,
pre-specification in `PROTOCOL_v2_benefit.md`.
Reproduce: `python3 h1_sample_efficiency.py --seed S --fracs F`, then `--summary`.
