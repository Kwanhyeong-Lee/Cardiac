# Case 1009 — LV perfusion territories (frame A)

LV mass 148 g (1.05 g/mL).

| map | LAD g | LCx g | RCA g |
|---|---|---|---|
| visible tree only | 85.9 | 49.3 | 12.5 |
| visible + groove priors, right-dominant (used below) | 45.7 | 33.3 | 68.6 |
| visible + groove priors, left-dominant | 45.7 | 100.2 | 1.7 |

Myocardium farther than 25 mm from any *visible* vessel point: 96.3 g (65.3 %) — there the map is groove-prior extrapolation.

| seg | name | mass g | AHA standard | patient map (RD) | visible-only | LAD/LCx/RCA frac | via prior | far from visible | agree |
|---|---|---|---|---|---|---|---|---|---|
| 1 | basal anterior | 10.2 | LAD | LAD (0.56) | LAD (0.66) | 0.56/0.44/0.0 | 0.29 | 0.01 | ✓ |
| 2 | basal anteroseptal | 6.7 | LAD | LAD (0.6) | LAD (0.61) | 0.6/0.02/0.39 | 0.13 | 0.23 | ✓ |
| 3 | basal inferoseptal | 6.8 | RCA | RCA (1.0) | RCA (0.94) | 0.0/0.0/1.0 | 1.0 | 0.97 | ✓ (prior) |
| 4 | basal inferior | 7.1 | RCA | RCA (1.0) | LCx (0.97) | 0.0/0.0/1.0 | 1.0 | 1.0 | ✓ (prior) |
| 5 | basal inferolateral | 9.2 | LCx | LCx (0.87) | LCx (1.0) | 0.0/0.87/0.13 | 0.98 | 0.49 | ✓ |
| 6 | basal anterolateral | 9.7 | LCx | LCx (1.0) | LCx (0.99) | 0.0/1.0/0.0 | 0.86 | 0.21 | ✓ |
| 7 | mid anterior | 10.0 | LAD | LAD (0.99) | LAD (1.0) | 0.99/0.01/0.0 | 0.01 | 0.02 | ✓ |
| 8 | mid anteroseptal | 10.2 | LAD | LAD (0.82) | LAD (0.98) | 0.82/0.0/0.18 | 0.18 | 0.39 | ✓ |
| 9 | mid inferoseptal | 9.9 | RCA | RCA (1.0) | LAD (0.71) | 0.0/0.0/1.0 | 1.0 | 1.0 | ✓ (prior) |
| 10 | mid inferior | 12.2 | RCA | RCA (1.0) | LCx (0.68) | 0.0/0.0/1.0 | 1.0 | 1.0 | ✓ (prior) |
| 11 | mid inferolateral | 10.4 | LCx | LCx (0.58) | LCx (0.81) | 0.0/0.58/0.42 | 1.0 | 1.0 | ✓ (prior) |
| 12 | mid anterolateral | 11.0 | LCx | LAD (0.55) | LAD (0.74) | 0.55/0.44/0.01 | 0.45 | 0.92 | ✗ (prior) |
| 13 | apical anterior | 9.2 | LAD | LAD (0.84) | LAD (1.0) | 0.84/0.0/0.16 | 0.16 | 0.49 | ✓ |
| 14 | apical septal | 9.1 | LAD | RCA (0.7) | LAD (1.0) | 0.3/0.0/0.7 | 0.7 | 0.78 | ✗ (prior) |
| 15 | apical inferior | 8.3 | RCA | RCA (1.0) | LAD (1.0) | 0.0/0.0/1.0 | 1.0 | 1.0 | ✓ (prior) |
| 16 | apical lateral | 7.2 | LCx | RCA (0.82) | LAD (1.0) | 0.18/0.0/0.82 | 0.82 | 1.0 | ✗ (prior) |
| 17 | apex | 0.5 | LAD | RCA (1.0) | LAD (1.0) | 0.0/0.0/1.0 | 1.0 | 1.0 | ✗ (prior) |

✓/✗ vs the AHA standard; '(prior)' = segment mostly beyond 25 mm of the visible tree, assignment rests on the groove prior + dominance assumption

## Mass at risk per occlusion site (RD map)

| site | g | % LV |
|---|---|---|
| LM occlusion | 79.0 | 53.5 |
| proximal LAD (after LM) | 45.7 | 31.0 |
| mid LAD (after first diagonal, 36 mm) | 43.7 | 29.6 |
| distal LAD (70 mm) | 29.6 | 20.0 |
| proximal LCx | 33.3 | 22.6 |
| proximal RCA | 66.9 | 45.3 |
| mid RCA (beyond 25 mm) | 66.9 | 45.3 |

- territories from the VISIBLE proximal-mid tree only: no PDA/PLV, RCA to ~48 mm, LCx to ~30 mm -> inferior and inferolateral segments are extrapolated (see uncertain_frac)
- dominance unknown from this scan (faint distal RCA); the AHA standard column assumes the common right-dominant pattern
- Voronoi rule (nearest centreline point) ignores vessel calibre and flow; it is the accepted first-order territory model, not a perfusion measurement
- mass at risk is anatomical (downstream territory mass); it says nothing about collaterals or viability
