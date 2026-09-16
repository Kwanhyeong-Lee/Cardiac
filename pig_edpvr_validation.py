"""
Pig EDPVR Validation Results
=============================
Davidson et al. 5-pig PV loop data -> EDPVR fitting -> Ground truth Eed

Results Summary:
  - 24 valid windows across 5 pigs
  - Eed range: 0.011 - 0.061 (physiologically plausible for normal pig)
  - EDPVR fitting R^2: 0.378 +/- 0.124

Key Finding:
  No standard hemodynamic variable (EF, EDV, ESV, SBP, DBP, HR, CO, EDP)
  significantly correlates with Eed (all p > 0.26).
  -> Confirms diastolic echo inputs (E/e', E/A, DT, LAVI) are NECESSARY
  -> Direct sim-to-pig transfer fails due to massive domain gap

Pig EDPVR Ground Truth Eed (per pig):
  Pig 1: 0.0249 +/- 0.0057  (n=6, range 0.0172-0.0326)
  Pig 2: 0.0543 +/- 0.0065  (n=2, range 0.0478-0.0608)
  Pig 3: 0.0307 +/- 0.0057  (n=3, range 0.0227-0.0351)
  Pig 4: 0.0263 +/- 0.0009  (n=2, range 0.0254-0.0271)
  Pig 5: 0.0252 +/- 0.0105  (n=11, range 0.0109-0.0468)

Domain Gap (Pig vs Human Simulation):
  EDV:  42-72 mL  vs  80-280 mL
  ESV:  4-13 mL   vs  20-250 mL
  EDP:  41-108 mmHg vs 2-40 mmHg
  Eed:  0.01-0.06  vs  0.01-0.30
"""

# Feature-Eed correlations (all non-significant)
FEATURE_EED_CORRELATIONS = {
    'EF':  {'R': -0.138, 'p': 0.520},
    'EDV': {'R': -0.167, 'p': 0.436},
    'ESV': {'R':  0.056, 'p': 0.796},
    'SBP': {'R':  0.236, 'p': 0.266},
    'DBP': {'R':  0.236, 'p': 0.266},
    'ESP': {'R':  0.236, 'p': 0.266},
    'EDP': {'R':  0.209, 'p': 0.327},
    'SV':  {'R': -0.207, 'p': 0.332},
}
