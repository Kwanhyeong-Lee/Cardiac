# Paper 3 — pH-PINN v5 Complete Results Summary
Updated: 2026-06-08

## pH-PINN v5 Architecture
- Parameters: 61,169
- Encoder: 11 → 256 → 128 → 64 (MLP + GELU + Dropout)
- Hamiltonian: T(q,p) via MLP[5,64,64,1], V(q) via MLP[3,64,64,1]
- Dissipation: R = LL^T (Cholesky, guaranteed PSD)
- Decoders: Clinical (12→64→32→7), Energy (12→64→32→6)

## Training Results (Random Split: 4095/877/879)
- Best epoch: 115/150
- Training time: 23s
- Clinical R² mean: 0.9796
  - Ees: 0.9844, Eed: 0.9912, Ea: 0.9780
  - VA coupling: 0.9817, EDP: 0.9568
  - Efficiency: 0.9817, Tau: 0.9831
- Energy R² mean: 0.9737
  - H_total: 0.9869, T_kinetic: 0.9751
  - V_potential: 0.9870, Mech_eff: 0.9349
  - VA_coupling: 0.9800, SW: 0.9786

## Structure Guarantees
- H = T + V conservation: MSE = 3.37e-15 (machine precision)
- R PSD violations: 0/200
- T ≥ 0, V ≥ 0: enforced via softplus

## Temporal Validation (Prospective Proxy)
- Split: train on pre-median dates, test on post-median
- Train: 2488, Test: 2925
- Mean R² degradation: -0.0175
- All outputs maintain R² > 0.88
- H=T+V MSE preserved at 4.12e-15

## Drug Interaction Network
- Testable drug pairs: 21
- Synergistic: 11 (52%)
- Antagonistic: 9 (43%)
- Additive: 1 (5%)
- Top synergy: ARB+BB (interaction = -5,059 J, 280% supra-additive)
- BB = most synergistic hub (5/6 connections)
- CCB = most antagonistic hub (5/6 connections)

## New Files Created (This Session)
- phpinn_v5_trained.pt — Trained model weights + normalization stats
- phpinn_v5_metrics.json — Per-output test R² and structure metrics
- phpinn_v5_history.json — Training history (loss, R², H error per epoch)
- phpinn_v5_test_preds.npz — Test set predictions vs ground truth
- fig_phpinn_training.png — 8-panel training results figure
- fig_phpinn_comprehensive.png — 12-panel comprehensive results
- temporal_validation_metrics.json — Temporal split per-output R² + MAE
- temporal_vs_random_comparison.csv — Random vs temporal R² comparison
- drug_interaction_network.csv — 84 pairwise interactions (4 metrics × 21 pairs)
- drug_interaction_graph.json — Network graph nodes + edges
- phenotype_drug_interactions.csv — HF type-specific interactions
- Paper3_Update_Training_Results.docx — Updated manuscript sections (III-E, F, G)
