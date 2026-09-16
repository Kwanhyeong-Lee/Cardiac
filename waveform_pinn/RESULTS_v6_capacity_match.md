# v6 — the output constraint: capacity confound removed, and the guarantee found not to be one

Dataset 3 (waveform morphology + demographics, 28,814 windows / 956 cases), four
architectures, three seeds. Patient-level three-way split; checkpoint selected on an inner
validation split of the training cases, never on training loss.

> **This file was rewritten on 2026-08-12 after an independent adversarial audit.** The
> first version reported that E and E2 emit no negative cardiac output at 40σ and concluded
> the output constraint was free and architectural. The audit found that the guarantee was
> not architectural at all, and that the probe used to verify it was one-sided in a way that
> made the answer trivially zero. Both findings are below. The superseded run is kept as
> `results_capacity_match_PREAUDIT_discard.json`.

## The three defects and their fixes

**1. Capacity.** Model E drops A's 17,537-parameter decoder for two linear heads
(272 parameters) and so ran 30.3% smaller than A. Any "the constraint is free" reading was
confounded, and in the awkward direction. **E2** restores the deficit inside the positive
heads: 56,986 against A's 56,983 (+0.005%).

**2. The guarantee was learned, not architectural.** E and E2 form `CO = softplus/softplus`
and then map it to the standardised target scale with *free* parameters,
`y = _scale·co + _shift`. Nothing forces `_scale > 0`, and if it is negative the output is
unbounded below and the guarantee is void. In the six fits, `_scale` landed near 1 and
`_shift` near −0.93, placing a **floor at 3.33–3.44 L/min**. That floor, not the softplus,
is what produced every "zero negative outputs".

**3. The probe was one-sided.** Counting only negative outputs is trivially zero once a
positive floor exists. A cardiac output of 3,432 L/min is as impossible as one of −115.
The probe is now two-sided: outside 0.5–20 L/min.

**Model E3** fixes defect 2. The map to standardised units is not a free affine layer but
the exact inverse of a known standardisation, registered as buffers:
`y = (co − μ_y)/σ_y` with `co > 0`. Then `CO > 0` holds by algebra for every input, with no
learned quantity involved and no floor above zero. 56,984 parameters.

## The cost of the learned floor

| model | floor (L/min) | training targets below it | test predictions pinned to it |
|---|---|---|---|
| E  | 3.34 / 3.39 / 3.44 | 13.7% / 12.8% / 15.1% | 12.3% / 12.6% / 20.0% |
| E2 | 3.33 / 3.37 / 3.43 | 13.7% / 12.8% / 15.1% | 11.8% / 12.9% / 19.8% |
| **E3** | **0.00** | **0%** | **0%** |

E and E2 are structurally unable to predict roughly one in seven reference values, and the
ones they cannot reach are the low-output ones — the clinically dangerous end. This is not
a free constraint. It was invisible because nobody looked below zero-crossing.

## Accuracy

| model | params (active) | R² | PE vs thermodilution |
|---|---|---|---|
| A  | 56,983 (55,048) | 0.8648 ± 0.0198 | 47.54 ± 1.52 % |
| E  | 39,720 (37,785) | 0.8411 ± 0.0154 | 46.55 ± 0.62 % |
| E2 | 56,986 (55,051) | 0.8536 ± 0.0240 | 48.05 ± 1.02 % |
| **E3** | **56,984 (55,049)** | **0.8702 ± 0.0279** | **48.02 ± 0.18 %** |

**With three seeds none of these differences is a difference.** The R² range 0.841–0.870
sits inside overlapping standard deviations of 0.015–0.028, and PE 46.6–48.1 inside
0.18–1.52. The defensible statement is the negative one: *restoring E's missing capacity
changes nothing, and making the guarantee architectural costs nothing measurable.*

E's slightly lower PE is not evidence of an advantage — a floor that truncates the low tail
mechanically reduces spread on a cohort whose reference values cluster above it.

## The guarantee, probed on both sides

Outputs at 40σ displacement, 4,000 probes per seed, 12,000 total:

| model | negative | outside 0.5–20 L/min | worst value seen |
|---|---|---|---|
| A  | 3,906 | 6,812 | −115.6 and +198.6 |
| E  | 0 | 165 | +3,432 |
| E2 | 0 | 2,257 | +734 |
| **E3** | **0** | **5,658** | **+18,751** |

**This is the sharpest form of Paper B's central claim, and it is a negative result.**
E3's positivity is genuinely architectural — zero negatives, floor exactly zero, no learned
quantity involved — and it buys nothing in plausibility. Nearly half of the extreme probes
land outside any physiological range, reaching eighteen thousand litres per minute. The
constraint encodes `CO > 0` and delivers `CO > 0`. It does not encode, and does not
deliver, `CO ∈ [0.5, 20]`.

E and E2 score *better* on the two-sided metric only because the learned floor compresses
the output range — the same defect that made their one-sided score perfect, now helping
them for the same wrong reason, and still paid for with the missing lower tail.

## A property of the parameterisation, not of training

**1,935 parameters (`L_head`) receive no gradient in any of these four models.** `R = LLᵀ`
is returned by the forward pass but enters no loss term when `soft=False`. Every
`R_nonpsd = 0` here is therefore a statement about the Cholesky parameterisation, not about
a trained matrix — which is precisely the claim the paper makes, but the paper must say so
rather than let the reader infer that training achieved it. The same applies in reverse to
model C: a free symmetric matrix is generically non-PSD whether trained or not.

## Reading it

1. The capacity confound is resolved and the conclusion survives: E2 ≈ E on accuracy, so
   the 17,263 missing parameters were not doing the work.
2. But "E guarantees a positive output" was false. The guarantee came from a learned offset
   that also removed the model's ability to represent 13–15% of the data.
3. E3 makes the guarantee real, at no measurable accuracy cost.
4. And E3 shows what a real guarantee is worth: exactly the predicate it encodes. Positivity
   is not plausibility, and the gap between them is enormous.

## Files

`capacity_match.py`, `results_capacity_match.json` (12 runs),
`models.py::TrueOutputConstrainedPHPINN`, `models.py::output_range_probe`.
Superseded: `results_capacity_match_PREAUDIT_discard.json`.
Reproduce: `python3 capacity_match.py --job 0..11`, then `--summary`.
