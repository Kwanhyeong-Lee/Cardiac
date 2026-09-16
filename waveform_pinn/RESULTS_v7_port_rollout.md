# v7 — connecting the port, and what the parameterisation does that the constraint does not

`PAPER_B_OUTLINE.md` names its own weakness: *"The benefit of an admissible internal state
is not demonstrated here. It follows only if the state is consumed downstream — a forward
rollout, a controller, a simulator — **and no such consumer was built.**"* Every other Paper
B model is a static per-sample map with no exogenous input, so `xdot = [J−R]∂H/∂x + g(x)u`
was used with `u` absent — the *port* was never connected. This connects it and iterates the
learned map.

> **Rewritten 2026-08-12 after an independent adversarial audit.** The first version
> concluded that the constraint delivers passivity but makes state boundedness *worse*.
> The passivity half survives; the boundedness half was wrong, and the audit identified why
> before the corrected experiment was run. Six defects are fixed below. Superseded run:
> `results_port_rollout_PREAUDIT_discard.json`.

## Setup

`eicu_drug_response.csv` — 2,720 vasoactive-drug episodes in 1,445 eICU patients, each a
supervised one-step transition `(x_t, u) → x_{t+1}`.
`x = (CO, SBP, DBP, HR)`; `u = onehot(mechanism)·r`, `r` the within-drug-class z-score of
`log1p(rate)`, fit on training rows only.

| model | H | R | J |
|---|---|---|---|
| **P** | `T+V`, softplus ≥ 0 | `LLᵀ` — **quadratic** in the head output | `S−Sᵀ` skew |
| **Pm** | `T+V`, softplus ≥ 0 | `diag(softplus(d))` — PSD but **linear** in the head output | `S−Sᵀ` skew |
| **U** | free linear head | `(M+Mᵀ)/2`, symmetric not PSD — linear | free |
| **F** | *none* | *none* | *none* |

Patient-level three-way split; checkpoint on an inner validation split. Three seeds.

## Six defects, fixed

1. **Frozen steps.** 77–93% of the counted steps were exact numerical fixed points, inflating
   the denominator ~4×, and the cumulative-path "control" could not detect the frozen case it
   was written to exclude. Passivity is now counted over *moving* steps (‖Δx‖ > 1% of that
   trajectory's first step); both denominators are reported.
2. **float32 + absolute threshold.** `dH > 1e-6` suppressed real gains by the unconstrained
   model and hid float32 roundoff in the constrained one. Now float64, relative threshold.
3. **Model F had no trained Hamiltonian.** F's `H_head` never entered the loss, so every
   energy statistic reported for F — including "9.31% energy-gaining steps" — described a
   randomly initialised network. F now has no H and makes no energy claim.
4. **U's energy has no sign.** `(J−R)∇H` is exactly invariant under `(H,J,R)→(−H,−J,−R)`, so
   "U gains energy on x% of steps" can be reported as `100−x` for a bit-identical model.
   Both conventions are now reported.
5. **Growth-order confound — the one that reversed the conclusion.** See below.
6. **The displacement conditions did not test boundedness.** At 6σ only 19.0% of starts were
   inside the physiological box and at 24σ only 0.25%, so the metric measured *recovery* from
   an already-impossible state. A `box_uniform` condition was added whose starts are
   admissible by construction, and the denominator is now trajectories that started inside.

Also: trajectories are frozen at the step they leave the box rather than clamped and
integrated onward — the old `nan_to_num(...).clamp(±1e6)` produced artefacts such as a
median path length of 1.2 × 10¹⁴ and a terminal energy of 1.7 × 10⁶.

## 1. One-step accuracy — the control

| model | one-step R² | skill vs persistence |
|---|---|---|
| F  | 0.3704 ± 0.0025 | 0.287 |
| **Pm** | **0.3612 ± 0.0073** | 0.277 |
| U  | 0.3596 ± 0.0062 | 0.276 |
| P  | 0.3540 ± 0.0061 | 0.269 |
| persistence | 0.0982 ± 0.0382 | 0 |

All four carry real signal. **Pm and U are indistinguishable** (Δ = +0.0016, two seeds each
way). The first version reported the constraint costing 0.021 R²; that was model P
specifically, and Pm closes most of it. With three seeds the only difference worth stating
is that all structured models sit slightly below the free MLP by an amount comparable to
the seed spread.

## 2. Passivity at zero input — the guarantee, delivered exactly

With `u = 0`, `dH/dt = −(∂H/∂x)ᵀ R (∂H/∂x) ≤ 0` whenever `R ⪰ 0`. P and Pm guarantee
`R ⪰ 0` by construction; U does not.

| model | energy-gaining moving steps | max relative ΔH | non-PSD R | negative H |
|---|---|---|---|---|
| **P**  | **0 / 105,007  (0.000%)** | −0.000 (never positive) | 0 | 0 |
| **Pm** | **0 / 31,824  (0.000%)** | −0.000 (never positive) | 0 | 0 |
| U  | 48.6% | +96, +17, +5,286 | 2,042 | 1,121 |
| F  | — no Hamiltonian — | | | |

**The sign-gauge check.** Under the flipped convention `(H,J,R)→(−H,−J,−R)` the same numbers
become: P and Pm gain on 99.96–100.0% of steps, U on 46–62%. P and Pm have a *canonical*
sign — softplus fixes `H ≥ 0` and Cholesky fixes `R ⪰ 0`, so the flip is not available to
them. U's near-symmetry under the flip is the signature of what it actually is: **U does not
have an energy function, only a function labelled H whose sign is a gauge choice.** The
honest comparison is therefore not "constraint delivers, no-constraint fails" but "the
constrained model has a monotone energy; the unconstrained model has no energy at all."

## 3. State boundedness — and the finding that reversed

Fraction of trajectories still inside the physiological box after 200 steps, denominator =
trajectories that *started* inside.

| condition | starts inside | P | **Pm** | U | F |
|---|---|---|---|---|---|
| real drug input *(primary)* | 100% | 0.986 | 1.000 | 0.998 | 1.000 |
| zero input *(primary)* | 100% | 1.000 | 1.000 | 1.000 | 1.000 |
| **uniform over the box** | 100% | **0.629** | **0.924** | 0.917 | 0.957 |
| dose ×5 | 100% | 0.783 | 0.861 | 0.758 | 0.963 |
| recovery from 6σ | 19.0% | 0.758 | 0.952 | 0.911 | 0.955 |
| recovery from 24σ | 0.25% | — uninformative, ~1.7 trajectories start inside — |

**First-step magnitude at 6σ, the diagnostic:** P **8.43**, Pm 5.76, U 4.99, F 5.26.

**The previous conclusion was wrong.** It said the constraint makes the simulator less
bounded. What actually happens is that `R = LLᵀ` is *quadratic* in its head output while
`R = (M+Mᵀ)/2` is *linear*, so P's vector field grows one polynomial order faster and P
takes 1.7× larger steps far from the data. Model Pm imposes **exactly the same mathematical
guarantees** — PSD dissipation, non-negative composed energy, skew-symmetric interconnection
— through a parameterisation whose growth order matches U's, and the effect disappears:
Pm 0.924 against U 0.917 on the box-uniform condition, and 0.952 against 0.911 on recovery.

**What this adds, and it is new.** *How a hard constraint is parameterised matters more here
than whether it is imposed.* P and Pm are equivalent as mathematics and materially different
as models — on boundedness (0.629 vs 0.924, Pm higher in 3 of 3 seeds) and on step
magnitude (8.43 vs 5.76). The physics-informed literature reports Cholesky parameterisation
as an implementation detail. It is not one.

**And Paper B's thesis still holds, now cleanly.** With the confound removed, the guarantee
buys exactly what it encodes and nothing more: Pm's passivity is perfect and its
boundedness is *equal to*, not better than, an unconstrained model with no energy function
at all. The constraint is free — and it is also, on this axis, worth nothing.

## Revisions forced on `PAPER_B_OUTLINE.md`

1. *"No downstream consumer was built"* — removed. One is built.
2. *"Constraints cost nothing"* — holds, once the parameterisation is matched (Pm ≈ U). The
   unmatched Cholesky version does cost something, on both accuracy and boundedness.
3. **New contribution: parameterisation dominates imposition.** Two mathematically identical
   guarantees, implemented differently, give a 0.30 gap in simulator admissibility.
4. Contribution 5 (the PSD diagnostic tolerance) gains a sibling: not only is a fixed
   absolute tolerance wrong for *measuring* PSD-ness, the *homogeneity degree* of the PSD
   parameterisation is a design decision with first-order consequences.

## Limitations

Supervision is one step: each episode gives a single `pre → post` pair, so iterating beyond
one step is extrapolation of the learned map, not a validated physiological trajectory. The
claim is about the model as a consumer of its own state — what a digital twin, controller or
simulator is — not about the clinical accuracy of the simulated course. The 24σ recovery
condition is reported but carries no information (≈1.7 admissible starts). With three seeds
only the large, sign-consistent differences are interpretable: P vs Pm on boundedness (3/3,
Δ ≈ 0.30) qualifies; Pm vs U on accuracy (Δ = 0.0016) does not.

## Files

`port_rollout.py`, `results_port_rollout.json` (12 runs),
superseded `results_port_rollout_PREAUDIT_discard.json`.
Reproduce: `python3 port_rollout.py --job 0..11`, then `--summary`.
