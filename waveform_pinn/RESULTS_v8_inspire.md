# v8 — INSPIRE: external replication, and the multi-step test eICU could not support

`RESULTS_v7_port_rollout.md` closes with one limitation above the others:

> "Supervision is one step. Each eICU episode gives a single `pre → post` pair, so iterating
> beyond one step is extrapolation of the learned map rather than a validated physiological
> trajectory."

INSPIRE removes it, and does so in a different country, care setting and institution.

| | eICU | INSPIRE |
|---|---|---|
| state | `(CO, SBP, DBP, HR)` | `(CI×BSA, art_sbp, art_dbp, hr)` — same |
| input | 4 mechanisms, z-scored rate | same 4 mechanisms, same encoding |
| unit of data | one `pre → post` pair | **5-minute trajectory** |
| n | 2,720 pairs / 1,445 patients | **101,688 transitions / 2,501 operations** |
| source | 208 US hospitals | SNUH |
| setting | ICU | operating theatre |

## Cohort

Established by a full scan of all **66,029,310** `vitals` rows:

| filter | operations |
|---|---|
| `art_mbp` and `hr` | 49,230 |
| ≥1 continuous vasoactive infusion | 5,033 |
| both | 4,944 |
| **both + cardiac index** *(primary, reproduces the eICU state)* | **2,511** |

After the physiological filter and the requirement of consecutive 5-minute slots:
**2,501 operations, 101,688 transitions**, median 36 per operation, max 182; 2,319
operations contribute a run of ≥10 steps. Infusion coverage: norepinephrine 34.9% of rows,
nitroglycerin 15.4%, dobutamine 6.0%, dopamine 2.3%, milrinone 2.2%, epinephrine 1.7%.

`pepi` (phenylephrine infusion) is declared in `parameters.csv` and has **zero rows** in the
released data. It is dropped rather than contributing a silent all-zero channel.

## 1. One-step accuracy — constraints cost nothing, most cleanly yet

| model | one-step R² | skill vs persistence |
|---|---|---|
| F  (free MLP) | 0.7403 | 0.135 |
| P  (`R = LLᵀ`) | 0.7394 | 0.132 |
| Pm (`R = diag softplus`) | 0.7390 | 0.131 |
| U  (unconstrained) | 0.7386 | 0.130 |
| persistence | 0.6997 | 0 |

A spread of 0.0017 across four architectures on 101,688 transitions. On eICU the same
comparison spanned 0.016 with 2,720 pairs; the larger, denser dataset collapses it.
**"The constraint is free" is now supported on the dynamical task as well as the static ones.**

## 2. Passivity — replicated exactly

| model | energy-gaining steps at u=0 | non-PSD R |
|---|---|---|
| **P** | **0.000** (all three seeds) | **0** |
| **Pm** | **0.000** (all three seeds) | **0** |
| U | 0.593 (0.592 / 0.476 / 0.711) | 25,274 |
| F | no Hamiltonian | — |

Identical to eICU: the constrained models never gain energy at zero input; the unconstrained
one gains on roughly half of steps, which remains the signature of a quantity with no sign
convention rather than of a physical violation.

## 3. Multi-step rollout against the observed trajectory — the new test

Skill against persistence at the same horizon; the true input is supplied at each step, so
this measures the dynamics rather than input forecasting.

| horizon | F | P | Pm | U |
|---|---|---|---|---|
| 1 step (5 min) | 0.129 | 0.134 | 0.132 | 0.131 |
| 3 steps (15 min) | 0.204 | 0.207 | 0.206 | 0.202 |
| 6 steps (30 min) | 0.181 | 0.183 | 0.183 | 0.170 |
| **12 steps (60 min)** | **0.180** | **0.180** | **0.179** | **0.039** |

Per seed at 12 steps: F 0.160/0.202/0.178, P 0.156/0.202/0.181, Pm 0.161/0.193/0.183,
**U 0.173 / −0.221 / 0.165**.

**Read this carefully.** The unconstrained model produced **one catastrophic 60-minute
failure in three seeds** — skill −0.221, i.e. worse than assuming nothing changes — while
the six constrained runs produced none. That is suggestive and it is **not established**:
one failure in three against zero in six gives a Fisher exact p ≈ 0.33. Two of U's three
seeds are perfectly ordinary. The defensible statement is that the constrained models were
uniformly stable across six runs and the unconstrained model was not across three, and that
resolving this needs more seeds, not more prose.

What *is* established is the negative: **at every horizon the constrained models are neither
better nor worse than the free MLP.** Structure does not improve multi-step forecasting.

## 4. The growth-order finding replicates

Fraction of trajectories still admissible after 200 steps, starts uniform over the
physiological box, and the first-step magnitude at 6σ:

| model | admissible | first step at 6σ |
|---|---|---|
| F  | 0.858 | 3.45 |
| **Pm** | **0.846** | 3.72 |
| P  | 0.751 | **6.39** |
| U  | 0.734 | 3.01 |

Exactly the eICU pattern. P and Pm impose identical guarantees; P's quadratic Cholesky
parameterisation takes 1.7× larger steps and loses 0.10 of admissibility, while Pm sits with
the free MLP. **The parameterisation, not the constraint, is what governs behaviour away
from the data — now shown on two independent datasets.**

One difference from eICU worth stating: there Pm and U tied (0.924 vs 0.917); here Pm leads
U by 0.112, in 3 of 3 seeds (0.789/0.890/0.858 against 0.735/0.694/0.774). Across the two
datasets the honest summary is *no worse, possibly slightly better* — not a demonstrated
advantage.

## A property of the data that must be stated

INSPIRE winsorises every measurement to its 2.5–97.5 percentile before release, so
`art_sbp` spans only 72–160 mmHg and `hr` only 46–108 /min in this cohort. Trajectories
therefore start well inside the physiological box, and any exit during rollout is generated
by the model rather than inherited from the data — which makes the admissibility test
cleaner than eICU's, and makes the absolute exit rates **not comparable** between the two
datasets. Only the ordering across architectures is comparable, and it replicates.

## Two corrections to earlier statements about INSPIRE

1. **A VitalDB linker is published.** `schema.csv` documents `operations.case_id` as
   "A linker to VitalDB Open Dataset"; the Sci Data paper describing v1.3 does not mention
   it. **But it is not directly usable as published**: 21,099 of 130,960 operations carry a
   value, and those values are spread uniformly over the full int16 range including 7,261
   negatives, while VitalDB case IDs run 1–6,388. Only 2,595 fall inside that range. It is a
   randomised surrogate key, and joining on it requires a corresponding field on the VitalDB
   side that has not been verified here.
2. **A `race` column exists** — and is `Asian` for all 130,960 operations. The conclusion
   that the pulse-oximetry racial-bias literature cannot be addressed with INSPIRE stands,
   for a different reason than originally given.

## Files

`inspire_extract.py` (cohort + trajectories), `inspire_traj.csv` (107,185 grid rows),
`port_rollout_inspire.py`, `results_port_rollout_inspire.json` (12 runs).
Reproduce: `python3 inspire_extract.py`, then `port_rollout_inspire.py --job 0..11`,
then `--summary`.
