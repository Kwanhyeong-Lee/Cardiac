# Waveform pH-PINN — reproducibility package

2026-07-30. Read `SUMMARY.md` first.

## Reading order

1. `SUMMARY.md` — everything, ranked by how well supported
2. `PROTOCOL.md` — pre-specified endpoints; **§6 is the deviation log**, every change
   with its date and reason, entered before the corresponding run
3. `manuscripts/` — **full draft manuscripts in .docx**, figures embedded
   (`build_paper*.js` regenerate them; outlines in `PAPER_*_OUTLINE.md`)
4. `FIGURE_CAPTIONS.md` + `figures/` — seven figures, all drawn; regenerate with
   `python3 make_figures.py`
5. `RESULTS_v1.md` → `RESULTS_v5_abstention.md` — per-stage detail, in order
6. `DISCARDED.md` — the v1 alignment defect, kept rather than deleted

## Reproducing

`RUN.md` has the sequence and the two pitfalls that must not be reintroduced
(0.5 Hz MBP sampling; absolute versus relative PSD tolerance).

Data download requires the VitalDB open API and runs locally, roughly 1.5 hours end to
end. Everything after extraction is CPU-only and takes minutes.

## Claims and where they are evidenced

| Claim | Evidence |
|---|---|
| Device error floor, PE 40.1% [32.5, 50.4] | `device_benchmark_v2.json`, `RESULTS_v3.md` §1 |
| Error decomposition 53.7² = 40.1² + 35.7² | `RESULTS_v3.md` §1 |
| Constraints free across R² 0.25–0.97 | `RESULTS_v2.md` §4, `RESULTS_v3.md` §3 |
| Zero violations vs 1 (penalty) vs 6,202 (none) | `RESULTS_v3.md` §3, `ood_clinical_*.json` |
| Holds under real clinical shift | `RESULTS_v4_clinical_ood.md` |
| Guarantee scope stops at the output | `RESULTS_v4_scope.md` |
| Synthetic OOD does not replicate clinically | `RESULTS_v4_clinical_ood.md` §2 |
| Recalibration ceiling 0.519 | `RESULTS_v5_abstention.md` §1 |
| Abstention works, insufficient | `RESULTS_v5_abstention.md` §2–3 |

## Not claimed

The model is not a usable cardiac output monitor (PE 47.7%, against a device at 40.1%
that itself fails its field's 30% threshold). The benefit of an admissible internal state
is not demonstrated — no downstream consumer was built. Physical constraints are not shown
to make predictions more trustworthy; `RESULTS_v4_clinical_ood.md` refutes that reading.

## Superseded, retained deliberately

`extract_features.py` (v1), `wave_features2_MISALIGNED_discard.csv`,
`results_paper2_MISALIGNED_discard.json`, `results_paper2_v1.json`,
`results_paper2_v2.json`, `device_benchmark.json`, `DESIGN.md`.
