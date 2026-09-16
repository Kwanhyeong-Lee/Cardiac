# Paper 2 — local execution guide

The VitalDB API is throttled from the analysis sandbox (it stalled at 50/965 cases), so
the two download stages must run on the local machine. Everything downstream of them is
CPU-only and fast.

Read `PROTOCOL.md` first. The endpoints, cohorts, and decision rules are fixed there and
are not to be renegotiated after seeing results.

```powershell
cd "C:\work\Cardiac\waveform_pinn"
```

## Stage 1 — cohorts  (~15 min)

```bash
python3 build_cohort4.py --index      # counts only, no download; sanity check first
python3 build_cohort4.py              # writes cohort4.csv
```

Expected index output, verified 2026-07-30:

```
SNUADC/ART             : 3645
PC  (pulse contour)    : 924
TD  (thermodilution)   : 65
  TD_ONLY = TD \ PC    : 41     <-- PRIMARY
  BOTH    = TD & PC    : 24
VOL (Vigilance EDV/ESV): 49
IOH (ART_MBP)          : 3644
```

If `TD_ONLY` is not 41, stop and check the API before going further — the whole primary
analysis rests on that set.

## Stage 2 — waveform features  (~40 min)  ← **RE-RUN REQUIRED 2026-07-30**

```bash
python3 extract_features2.py          # writes wave_features2_0.csv
```

Smoke-tested 8/8 on a mixed TD/PC sample; timed at 20 s per 8 cases. Resumable by chunk:
`python3 extract_features2.py 200 400` processes 200 cases from index 400.

> **The first extraction must be discarded and this stage re-run.** Reference values were
> being taken as whole-case medians while the morphology came from a single 3-minute
> window. Within-case cardiac output varies with a CV of 13–19%, so the two were
> effectively unpaired, and the first run returned an internal R² of 0.03 where the
> reference device computes CO from the very waveform used as input. `window_reference()`
> now reads every reference track over the same interval as the waveform, and keeps the
> whole-case value in a `*_case` column for the alignment sensitivity analysis.
> Recorded in `PROTOCOL.md` §6.

## Stage 2b — v2 multi-window extraction  (~55 min)  ← **run this next**

```bash
python3 extract_windows.py            # writes wave_windows_0.csv
```

One 3-minute window every 5 minutes, up to 40 per case: roughly 33,000 rows from 958
cases, versus 921 in v1. Timed at 3.5 s per case; resumable by chunk
(`python3 extract_windows.py 200 400`), then concatenate the `wave_windows_*.csv` files.

Grouping stays at `caseid`, so `GroupShuffleSplit` still keeps every patient on one side
of the split. The extra rows add within-patient variation, not extra patients — which is
why `train_eval.by_patient()` collapses predictions to patient medians before computing
any agreement statistic. Without that collapse the primary endpoint would report n in the
hundreds when there are still only 31 independent patients, and every confidence interval
would be too narrow by about √35.

Then:

```bash
python3 train_eval.py --ablation --seeds 0 1 2 --features wave_windows_0.csv --list
python3 train_eval.py --ablation --seeds 0 1 2 --features wave_windows_0.csv --job N
```

Training switches automatically to 60 epochs at batch 256 once the training set exceeds
5,000 rows.

## Stage 3 — hypotension anchors  (~2–4 h, exploratory)

```bash
python3 extract_ioh.py                # writes ioh_anchors_0.csv
```

Slowest stage: it loads the full-length waveform per case. Safe to run overnight or to
skip until the primary analysis is settled. Chunking works the same way.

Sanity check on 6 cases gave 176 anchors with hypotension rates of 13.1% / 18.8% / 26.1%
at 5 / 10 / 15 min, and `ctrl_map_now` within 60–195 mmHg.

## Stage 4 — models and agreement  (minutes, no network)

```bash
python3 train_eval.py --ablation      # writes results_paper2.json
```

Trains on the PC cohort only, freezes, and only then touches the TD-only set. Runs the
four negative controls from `PROTOCOL.md` §4.1 in the same pass.

---

## Two known pitfalls, already fixed — do not reintroduce

**`Solar8000/ART_MBP` is 0.5 Hz.** Requesting it at 1 s returns 50% `NaN`. The `NaN`s
break every sustained-run test, so the hypotension mask silently returned zero events for
every case. `extract_ioh.py` now loads at `MBP_DT = 2.0 s`. If the hypotension rate ever
comes back as 0%, this is the first thing to check.

**Raw MBP contains values from −70 to 346 mmHg.** Filter to 20–200 before use;
`ctrl_map_now` was reading 323 mmHg before the filter was added.

---

## What each output feeds

| File | Feeds |
|---|---|
| `cohort4.csv` | tier assignment for every case |
| `wave_features2_0.csv` | primary + secondary endpoints |
| `ioh_anchors_0.csv` | exploratory endpoint §3.3.2 |
| `results_paper2.json` | tables and figures |

## First things to read in `results_paper2.json`

1. **`control: permuted labels`** — internal R² must be ≈ 0. If it is not, there is
   leakage and nothing else in the file is interpretable.
2. **`control: level only`** — if this matches the full model, waveform *shape* is
   contributing nothing and the paper's framing has to change.
3. **`linear baseline`** — if this matches the network, the network is not what produced
   the result.
4. Only then, the primary external agreement against thermodilution.
