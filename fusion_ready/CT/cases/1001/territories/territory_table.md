# Case 1009 — LV perfusion territories (frame A)

LV mass 150 g (1.05 g/mL).

| map | LAD g | LCx g | RCA g |
|---|---|---|---|
| visible tree only | 42.5 | 43.7 | 63.9 |
| visible + groove priors, right-dominant (used below) | 42.5 | 43.8 | 63.8 |
| visible + groove priors, left-dominant | 42.5 | 61.1 | 46.5 |

Myocardium farther than 25 mm from any *visible* vessel point: 63.2 g (42.1 %) — there the map is groove-prior extrapolation.

| seg | name | mass g | AHA standard | patient map (RD) | visible-only | LAD/LCx/RCA frac | via prior | far from visible | agree |
|---|---|---|---|---|---|---|---|---|---|
| 1 | basal anterior | 9.1 | LAD | LCx (0.78) | LCx (0.78) | 0.22/0.78/0.0 | 0.26 | 0.0 | ✗ |
| 2 | basal anteroseptal | 4.3 | LAD | LAD (0.54) | LAD (0.54) | 0.54/0.16/0.3 | 0.11 | 0.61 | ✓ (prior) |
| 3 | basal inferoseptal | 7.7 | RCA | RCA (1.0) | RCA (0.98) | 0.0/0.0/1.0 | 0.51 | 0.23 | ✓ |
| 4 | basal inferior | 11.6 | RCA | RCA (0.99) | RCA (0.88) | 0.0/0.01/0.99 | 0.9 | 0.39 | ✓ |
| 5 | basal inferolateral | 9.7 | LCx | LCx (0.89) | LCx (0.97) | 0.0/0.89/0.11 | 1.0 | 0.45 | ✓ |
| 6 | basal anterolateral | 9.0 | LCx | LCx (1.0) | LCx (1.0) | 0.0/1.0/0.0 | 0.8 | 0.02 | ✓ |
| 7 | mid anterior | 10.7 | LAD | LAD (0.78) | LAD (0.78) | 0.78/0.22/0.0 | 0.0 | 0.02 | ✓ |
| 8 | mid anteroseptal | 9.0 | LAD | LAD (0.9) | LAD (0.9) | 0.9/0.0/0.1 | 0.0 | 0.43 | ✓ |
| 9 | mid inferoseptal | 9.5 | RCA | RCA (1.0) | RCA (1.0) | 0.0/0.0/1.0 | 0.0 | 0.2 | ✓ |
| 10 | mid inferior | 11.8 | RCA | RCA (1.0) | RCA (1.0) | 0.0/0.0/1.0 | 0.09 | 0.21 | ✓ |
| 11 | mid inferolateral | 9.6 | LCx | LCx (0.7) | RCA (0.55) | 0.0/0.7/0.3 | 0.71 | 1.0 | ✓ (prior) |
| 12 | mid anterolateral | 10.2 | LCx | LCx (0.87) | LCx (0.87) | 0.13/0.87/0.0 | 0.11 | 0.46 | ✓ |
| 13 | apical anterior | 10.0 | LAD | LAD (1.0) | LAD (1.0) | 1.0/0.0/0.0 | 0.0 | 0.39 | ✓ |
| 14 | apical septal | 9.6 | LAD | LAD (0.5) | LAD (0.5) | 0.5/0.0/0.5 | 0.0 | 0.83 | ✓ (prior) |
| 15 | apical inferior | 9.6 | RCA | RCA (0.99) | RCA (0.99) | 0.01/0.0/0.99 | 0.0 | 0.69 | ✓ (prior) |
| 16 | apical lateral | 7.5 | LCx | LAD (0.68) | LAD (0.68) | 0.68/0.03/0.3 | 0.0 | 1.0 | ✗ (prior) |
| 17 | apex | 1.0 | LAD | RCA (0.51) | RCA (0.51) | 0.49/0.0/0.51 | 0.0 | 1.0 | ✗ (prior) |

✓/✗ vs the AHA standard; '(prior)' = segment mostly beyond 25 mm of the visible tree, assignment rests on the groove prior + dominance assumption

## Mass at risk per occlusion site (RD map)

| site | g | % LV |
|---|---|---|
| LM occlusion | 86.3 | 57.5 |
| proximal LAD (after LM) | 41.1 | 27.4 |
| mid LAD (after first diagonal, 40 mm) | 19.8 | 13.2 |
| distal LAD (70 mm) | 0.0 | 0.0 |
| proximal LCx | 43.8 | 29.2 |
| proximal RCA | 63.8 | 42.5 |
| mid RCA (beyond 25 mm) | 63.4 | 42.2 |

- territories from the VISIBLE proximal-mid tree only: no PDA/PLV, RCA to ~48 mm, LCx to ~30 mm -> inferior and inferolateral segments are extrapolated (see uncertain_frac)
- dominance unknown from this scan (faint distal RCA); the AHA standard column assumes the common right-dominant pattern
- Voronoi rule (nearest centreline point) ignores vessel calibre and flow; it is the accepted first-order territory model, not a perfusion measurement
- mass at risk is anatomical (downstream territory mass); it says nothing about collaterals or viability
