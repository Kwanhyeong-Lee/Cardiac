# Discarded first extraction — 2026-07-30

`wave_features2_MISALIGNED_discard.csv` and `results_paper2_MISALIGNED_discard.json`
are kept, not deleted, because the defect they contain is worth being able to point at.

## What was wrong

Reference values (`CO_pc`, `SV_pc`, `CO_td`, `EDV`, `ESV`, `RVEF`) were whole-case
medians taken over the entire operation, while the morphology descriptors came from a
single 3-minute window in the middle third of the record. Within-case cardiac output
varies with a coefficient of variation of 13-19% — comparable to the between-patient
spread — so pairing the two was close to pairing each patient's waveform with a random
draw from their own CO distribution.

Measured on six cases: whole-case median vs window median differed by up to 1.7 L/min
(case 25: 5.8 vs 7.5).

## What it produced

| Run | Internal R2 | TD PE |
|---|---|---|
| primary: CO, full morphology | 0.029 | 66.6% |
| control: level only | 0.002 | 68.8% |
| control: permuted labels | -0.667 | 59.4% |
| control: linear baseline | 0.185 | 58.0% |

## Why it was caught

Two things did not fit. An internal R2 of 0.03 is not credible when the reference device
computes cardiac output from the very waveform supplied as input. And the linear baseline
beat the network by an order of magnitude, which is the signature of a target carrying
almost no learnable signal rather than of a model that is too weak.

The negative controls behaved correctly throughout — label permutation collapsed to
-0.667 — so the pipeline itself was sound. That is what localised the fault to the
target, not the model.

Had the alignment defect gone unnoticed, this would have been reported as a false
negative on the primary endpoint: "waveform morphology does not transfer to
thermodilution cardiac output."

Fixed in `extract_features2.window_reference()`. See `PROTOCOL.md` section 6.
