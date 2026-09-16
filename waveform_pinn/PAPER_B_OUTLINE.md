# Paper B — outline (v2, 2026-08-12)

**Working title.** Architectural energy constraints in physiological neural networks:
what they guarantee, what they do not, and why the parameterisation matters more than the
imposition

**Target.** *IEEE Transactions on Biomedical Engineering*, or *TMLR* / *Machine Learning
for Health*. Full paper.

**One-sentence claim.** Imposing port-Hamiltonian energy structure architecturally rather
than by penalty makes physically inadmissible internal states unrepresentable at no cost in
accuracy — across five tasks, four data sources, two countries and two care settings — and
the guarantee extends to exactly the predicates it encodes and no further; how those
predicates are parameterised turns out to matter more than whether they are imposed.

---

## What changed in v2

Three things, two of them forced by an independent adversarial audit on 2026-08-12.

1. **The two limitations the outline listed are gone.** Model E is capacity matched (E2),
   and the missing downstream consumer is built (`port_rollout.py`).
2. **The output guarantee turned out not to be one.** E and E2 obtained positivity from a
   free learned offset, not from the softplus, and paid for it by being unable to represent
   13–15% of the reference values. E3 fixes it architecturally. See `RESULTS_v6`.
3. **A new contribution replaced a wrong one.** The claim that the constraint harms
   simulator boundedness was an artefact of `R = LLᵀ` being quadratic in its head output.
   The growth-matched control Pm removes it. See `RESULTS_v7`.

## The framing decision, and why

The obvious paper is "physics-constrained networks are more trustworthy." That paper cannot
be written from this data: under real clinical distribution shift the entirely unconstrained
model produces no inadmissible outputs either, and under iteration a growth-matched
constrained model is no more bounded than an unconstrained one. Writing it anyway would put
the weakest claim in the abstract.

The paper that can be written is narrower and, in the physics-informed literature, more
useful: **the guarantee is free, it is real, its scope is exactly the set of constrained
predicates, and its behaviour away from the data is set by the parameterisation rather than
by the constraint.** Papers in this area routinely report "hard constraints" without
separating the constrained quantities from the reported ones, and treat the Cholesky factor
as an implementation detail. Both distinctions are invisible in-distribution; this study
makes them visible.

## Contributions

1. **Free.** Capacity-matched architectures are indistinguishable in accuracy on every
   dataset tested, including the output-constrained variant once its parameter deficit is
   repaired (E2 56,986 vs A 56,983) and its guarantee made architectural (E3).
2. **Real, and penalties are not equivalent.** Zero violations in 16,626 held-out windows by
   construction, against 1 for a tuned penalty and 6,202 for no constraint. Rare is not
   impossible.
3. **Replicated under real shift.** Train on general surgery, evaluate on thoracic and
   transplant: the separation holds on populations never seen.
4. **Scoped — twice over.**
   - *Static*: the guarantee covers the constrained internal quantities; the output is not
     among them. Propagating it closes the gap at no cost, and even propagated it delivers
     positivity, not plausibility — E3 emits no negative cardiac output at 40σ and 5,658 of
     12,000 physiologically impossible ones, up to 18,751 L/min.
   - *Dynamic*: with the port connected, passivity at zero input is delivered exactly
     (0 of 106,007 moving steps for P, 0 of 31,824 for Pm) and buys nothing in state
     boundedness (Pm 0.924 vs unconstrained 0.917).
5. **A guarantee can be a learned artefact.** E and E2's "zero negative outputs" came from an
   unconstrained affine parameter, verified by a one-sided probe that the floor made
   trivially zero. The methodological point generalises: check whether the quantity you
   constrained is the quantity your probe measures.
6. **Parameterisation dominates imposition — replicated on two datasets.** P and Pm impose
   mathematically identical guarantees. P's `R = LLᵀ` is quadratic in its head output, Pm's
   `R = diag(softplus)` is linear; P takes ~1.7× larger steps far from the data and holds
   0.629 of trajectories admissible against Pm's 0.924 on eICU, and 0.751 against 0.846 on
   INSPIRE. The homogeneity degree of a PSD parameterisation is a design decision with
   first-order consequences.
7. **Multi-step forecasting is not improved by structure.** With genuine trajectories
   (INSPIRE) the constrained and free models are indistinguishable at 5, 15, 30 and 60
   minutes. The unconstrained model produced one catastrophic 60-minute failure in three
   seeds against none in six constrained runs — reported as suggestive, not established
   (Fisher p ≈ 0.33).
8. **Two diagnostic corrections.** A fixed absolute tolerance manufactures PSD violations
   when eigenvalues span orders of magnitude; a fixed absolute energy tolerance in float32
   suppresses real violations and hides roundoff. Both require relative tolerances, the
   second in float64.

## Experimental structure

**Static models.** A hard-constrained (softplus T,V; H = T+V; R = LLᵀ). B vanilla MLP.
C identical topology to A without constraints. D soft-constrained by penalty.
E output-constrained via CO = SV/T_period. E2 = E capacity matched. E3 = E2 with the affine
map fixed to the inverse target standardisation.

**Dynamical models.** P port-Hamiltonian with a real input `u`. Pm identical guarantees,
growth-matched PSD parameterisation. U identical topology, unconstrained. F free MLP.

| # | task | data | source | setting | R² |
|---|---|---|---|---|---|
| 1 | clinical features → haemodynamics | eICU + MIMIC-IV, 4,241 subjects | **208 US hospitals** + BIDMC | ICU | ≈0.97 |
| 2 | waveform morphology → CO | VitalDB, 22,400 windows / 866 patients | SNUH | theatre | ≈0.25 |
| 3 | waveform + demographics → CO | VitalDB, 28,814 windows / 956 cases | SNUH | theatre | ≈0.87 |
| 4 | drug input → haemodynamic transition | eICU, 2,720 episodes / 1,445 patients | 208 US hospitals | ICU | 0.35 (1-step) |
| 5 | **same, on 5-min trajectories** | **INSPIRE, 101,688 transitions / 2,501 operations** | **SNUH** | **theatre** | **0.74 (1-step)** |

Task 5 is a deliberate external replication of task 4 — identical state, identical drug
mechanisms, identical encoding and models — in a different country, institution and care
setting, and it supplies the multi-step supervision eICU could not. See `RESULTS_v8`.

**Frame this as five tasks, not five validations of one task.** Tasks 1-3 are different
endpoints; only task 5 is a deliberate replication of another (task 4). The claim is that
the architectural property is task-agnostic, and a reader who reads "five datasets" as five
replications of a single endpoint will be misled. Independent sources are three, not four:
VitalDB and INSPIRE are both SNUH, and PhysioNet lists VitalDB as INSPIRE's parent project.

**Distribution shift.** Train on general surgery (389 patients), evaluate on thoracic (226)
and transplantation (175). Accuracy indistinguishable; A and E at zero violations, C failing
in every window.

**Accuracy is a separate problem.** Transplant R² 0.50 against 0.81 in-distribution,
identically for all architectures. Recalibration cannot fix it (affine ceiling 0.519 vs
0.490). Distance-based abstention helps measurably against a flat random control and is not
sufficient. Three properties, three mechanisms, none substituting for another.

## What the discussion must say plainly

The benefit of an admissible internal state is now tested, not assumed. It was tested by
building the consumer the previous version said was missing, and the answer is that the
encoded predicate is delivered perfectly and the assumed one is not delivered at all. A
practitioner who adopts a port-Hamiltonian architecture expecting a simulator that stays
physiological will not get one; they will get a monotone energy, which is a different thing.

## Limitations to state, not bury

Dynamical supervision is one step per episode, so iteration beyond one step is extrapolation
of the learned map rather than a validated trajectory. The primary cohort for the CO
endpoint is entirely transplant patients, so every accuracy figure was measured under shift.
`L_head` receives no gradient in the static models — R enters no loss term there, so PSD-ness
is a property of the parameterisation rather than of training, which is the claim but must
be stated. Three seeds throughout: only large, sign-consistent differences are interpretable.
Abstention thresholds are descriptive, with no held-out calibration set.

## Relationship to Paper 1

Paper 1's manuscript becomes experiment 1. Its anatomical pipeline moves to supplementary in
full — it never entered inference. Its abstract needs the state/output distinction added,
which §4 turns from a caveat into a result.

## Figures

| Figure | Content | Status |
|---|---|---|
| B1 | Ablation: accuracy across datasets, validity, A vs D at scale | drawn |
| B2 | Scope: synthetic probe versus real clinical shift | drawn |
| B3 | Shift: accuracy degrades for all, validity for none | drawn |
| **B4** | **Output constraint: the learned floor, the two-sided probe, unchanged accuracy** | **drawn** |
| **B5** | **Port rollout: passivity, boundedness, and the growth-order explanation** | **drawn** |

Regenerate: `python3 make_figures.py B` and `python3 make_figures_v2.py`.

## Remaining before submission

- More seeds on the INSPIRE 12-step rollout: one unconstrained failure in three is the only
  result in the paper that would change materially with n = 10
- Merge Paper 1's LaTeX skeleton, move anatomy to supplementary
- Rebuild `PaperB_constraint_scope.docx` from v2
- `operations.case_id` is documented as a VitalDB linker but published as a randomised
  int16; if a matching VitalDB-side field exists, tasks 3 and 5 could be joined at the
  patient level, which no other work has done
