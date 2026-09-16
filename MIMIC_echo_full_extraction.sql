-- ============================================================
-- PINN v4 Full Echo Extraction from MIMIC-IV-Echo
-- BigQuery 원샷: structured_measurement → 11 PINN features + dd_grade
-- measurement_id 포함하여 medication matching 결과와 바로 조인 가능
-- ============================================================
--
-- Feature Mapping:
--   EF       ← biplane_lvef > lvef (COALESCE, biplane 우선)
--   EDV      ← biplane_lvedv > Teichholz(lvedd)
--   ESV      ← biplane_lvesv > Teichholz(lvesd)
--   SBP      ← resting_sbp
--   DBP      ← resting_dbp
--   HR       ← resting_hr
--   CO       ← LVOT method (lvot_diam, lvot_vti, HR) > SV×HR
--   Ee_prime ← mean_E_to_eprime > avg(lat_e_prime, sept_e_prime) > e_e_prime
--   EA_ratio ← mv_peak_e_a (direct) > mv_peak_e / mv_peak_a
--   DT       ← mv_e_decel
--   LAVI     ← la_vol / body_surface_area
--   dd_grade ← diastolic_grade
-- ============================================================

WITH pivoted AS (
  SELECT
    sm.subject_id,
    sm.measurement_id,
    sm.measurement_datetime,

    -- EF sources
    MAX(CASE WHEN sm.measurement = 'biplane_lvef' THEN SAFE_CAST(sm.result AS FLOAT64) END) AS biplane_lvef,
    MAX(CASE WHEN sm.measurement = 'lvef' THEN SAFE_CAST(sm.result AS FLOAT64) END) AS lvef_raw,
    MAX(CASE WHEN sm.measurement = 'lvef_upper' THEN SAFE_CAST(sm.result AS FLOAT64) END) AS lvef_upper,

    -- Volume sources
    MAX(CASE WHEN sm.measurement = 'biplane_lvedv' THEN SAFE_CAST(sm.result AS FLOAT64) END) AS biplane_lvedv,
    MAX(CASE WHEN sm.measurement = 'biplane_lvesv' THEN SAFE_CAST(sm.result AS FLOAT64) END) AS biplane_lvesv,
    MAX(CASE WHEN sm.measurement = 'lvedv_3d' THEN SAFE_CAST(sm.result AS FLOAT64) END) AS lvedv_3d,
    MAX(CASE WHEN sm.measurement = 'lvesv_3d' THEN SAFE_CAST(sm.result AS FLOAT64) END) AS lvesv_3d,
    MAX(CASE WHEN sm.measurement = 'lvedd' THEN SAFE_CAST(sm.result AS FLOAT64) END) AS lvedd,
    MAX(CASE WHEN sm.measurement = 'lvesd' THEN SAFE_CAST(sm.result AS FLOAT64) END) AS lvesd,

    -- Vitals
    MAX(CASE WHEN sm.measurement = 'resting_sbp' THEN SAFE_CAST(sm.result AS FLOAT64) END) AS resting_sbp,
    MAX(CASE WHEN sm.measurement = 'resting_dbp' THEN SAFE_CAST(sm.result AS FLOAT64) END) AS resting_dbp,
    MAX(CASE WHEN sm.measurement = 'resting_hr' THEN SAFE_CAST(sm.result AS FLOAT64) END) AS resting_hr,

    -- CO components (LVOT method)
    MAX(CASE WHEN sm.measurement = 'lvot_diam' THEN SAFE_CAST(sm.result AS FLOAT64) END) AS lvot_diam,
    MAX(CASE WHEN sm.measurement = 'lvot_vti' THEN SAFE_CAST(sm.result AS FLOAT64) END) AS lvot_vti,

    -- E/e' sources
    MAX(CASE WHEN sm.measurement = 'mean_E_to_eprime' THEN SAFE_CAST(sm.result AS FLOAT64) END) AS mean_Ee,
    MAX(CASE WHEN sm.measurement = 'lateral_E_to_eprime' THEN SAFE_CAST(sm.result AS FLOAT64) END) AS lat_Ee,
    MAX(CASE WHEN sm.measurement = 'septal_E_to_eprime' THEN SAFE_CAST(sm.result AS FLOAT64) END) AS sep_Ee,
    MAX(CASE WHEN sm.measurement = 'e_e_prime' THEN SAFE_CAST(sm.result AS FLOAT64) END) AS e_e_prime,
    MAX(CASE WHEN sm.measurement = 'lat_e_prime' THEN SAFE_CAST(sm.result AS FLOAT64) END) AS lat_e_prime,
    MAX(CASE WHEN sm.measurement = 'sept_e_prime' THEN SAFE_CAST(sm.result AS FLOAT64) END) AS sept_e_prime,
    MAX(CASE WHEN sm.measurement = 'mv_peak_e' THEN SAFE_CAST(sm.result AS FLOAT64) END) AS mv_peak_e,

    -- E/A
    MAX(CASE WHEN sm.measurement = 'mv_peak_e_a' THEN SAFE_CAST(sm.result AS FLOAT64) END) AS mv_peak_e_a,
    MAX(CASE WHEN sm.measurement = 'mv_peak_a' THEN SAFE_CAST(sm.result AS FLOAT64) END) AS mv_peak_a,

    -- DT
    MAX(CASE WHEN sm.measurement = 'mv_e_decel' THEN SAFE_CAST(sm.result AS FLOAT64) END) AS mv_e_decel,

    -- LAVI components
    MAX(CASE WHEN sm.measurement = 'la_vol' THEN SAFE_CAST(sm.result AS FLOAT64) END) AS la_vol,
    MAX(CASE WHEN sm.measurement = 'body_surface_area' THEN SAFE_CAST(sm.result AS FLOAT64) END) AS bsa,

    -- Diastolic grade
    MAX(CASE WHEN sm.measurement = 'diastolic_grade' THEN sm.result END) AS diastolic_grade_raw

  FROM `physionet-data.mimiciv_echo.structured_measurement` sm
  WHERE sm.measurement IN (
    'biplane_lvef', 'lvef', 'lvef_upper',
    'biplane_lvedv', 'biplane_lvesv', 'lvedv_3d', 'lvesv_3d', 'lvedd', 'lvesd',
    'resting_sbp', 'resting_dbp', 'resting_hr',
    'lvot_diam', 'lvot_vti',
    'mean_E_to_eprime', 'lateral_E_to_eprime', 'septal_E_to_eprime',
    'e_e_prime', 'lat_e_prime', 'sept_e_prime', 'mv_peak_e',
    'mv_peak_e_a', 'mv_peak_a',
    'mv_e_decel',
    'la_vol', 'body_surface_area',
    'diastolic_grade'
  )
  GROUP BY sm.subject_id, sm.measurement_id, sm.measurement_datetime
),

computed AS (
  SELECT
    subject_id,
    measurement_id,
    measurement_datetime,

    -- === EF (%) ===
    -- biplane > (lvef + lvef_upper)/2 as midpoint > lvef alone
    COALESCE(
      biplane_lvef,
      CASE WHEN lvef_raw IS NOT NULL AND lvef_upper IS NOT NULL
           THEN (lvef_raw + lvef_upper) / 2.0
           ELSE lvef_raw END
    ) / 100.0 AS EF,  -- Convert % to fraction (0-1) for PINN

    -- === EDV (mL) ===
    -- biplane > 3D > Teichholz from LVEDD (cm→mL)
    COALESCE(
      biplane_lvedv,
      lvedv_3d,
      CASE WHEN lvedd IS NOT NULL AND lvedd > 0
           THEN 7.0 * POW(lvedd, 3) / (2.4 + lvedd)  -- Teichholz
           ELSE NULL END
    ) AS EDV,

    -- === ESV (mL) ===
    COALESCE(
      biplane_lvesv,
      lvesv_3d,
      CASE WHEN lvesd IS NOT NULL AND lvesd > 0
           THEN 7.0 * POW(lvesd, 3) / (2.4 + lvesd)  -- Teichholz
           ELSE NULL END
    ) AS ESV,

    -- === Vitals ===
    resting_sbp AS SBP,
    resting_dbp AS DBP,
    resting_hr AS HR,

    -- === CO (L/min) ===
    -- LVOT method: CO = π×(d/2)²×VTI×HR/1000
    -- d in cm, VTI in cm → SV in mL → CO in L/min
    CASE
      WHEN lvot_diam IS NOT NULL AND lvot_vti IS NOT NULL AND resting_hr IS NOT NULL
           AND lvot_diam > 0 AND lvot_vti > 0 AND resting_hr > 0
      THEN ACOS(-1) * POW(lvot_diam / 2.0, 2) * lvot_vti * resting_hr / 1000.0
      ELSE NULL
    END AS CO_lvot,

    -- Fallback CO from volumes: (EDV-ESV) × HR / 1000
    COALESCE(biplane_lvedv, lvedv_3d) AS _edv_for_co,
    COALESCE(biplane_lvesv, lvesv_3d) AS _esv_for_co,
    resting_hr AS _hr_for_co,

    -- === E/e' ===
    COALESCE(
      mean_Ee,
      lat_Ee,
      sep_Ee,
      e_e_prime,
      CASE WHEN mv_peak_e IS NOT NULL AND lat_e_prime IS NOT NULL AND sept_e_prime IS NOT NULL
                AND lat_e_prime > 0 AND sept_e_prime > 0
           THEN mv_peak_e / ((lat_e_prime + sept_e_prime) / 2.0)
           WHEN mv_peak_e IS NOT NULL AND lat_e_prime IS NOT NULL AND lat_e_prime > 0
           THEN mv_peak_e / lat_e_prime
           WHEN mv_peak_e IS NOT NULL AND sept_e_prime IS NOT NULL AND sept_e_prime > 0
           THEN mv_peak_e / sept_e_prime
           ELSE NULL END
    ) AS Ee_prime,

    -- === E/A ratio ===
    COALESCE(
      mv_peak_e_a,
      CASE WHEN mv_peak_e IS NOT NULL AND mv_peak_a IS NOT NULL AND mv_peak_a > 0
           THEN mv_peak_e / mv_peak_a
           ELSE NULL END
    ) AS EA_ratio,

    -- === DT (ms) ===
    mv_e_decel AS DT,

    -- === LAVI (mL/m²) ===
    CASE WHEN la_vol IS NOT NULL AND bsa IS NOT NULL AND bsa > 0
         THEN la_vol / bsa
         ELSE NULL END AS LAVI,

    -- === Diastolic grade ===
    diastolic_grade_raw AS dd_grade_text

  FROM pivoted
)

-- ============================================================
-- FINAL OUTPUT: PINN-ready features
-- ============================================================
SELECT
  subject_id,
  measurement_id,
  measurement_datetime,
  EF,
  EDV,
  ESV,
  SBP,
  DBP,
  HR,
  -- CO: prefer LVOT, fallback to volume method
  COALESCE(
    CO_lvot,
    CASE WHEN _edv_for_co IS NOT NULL AND _esv_for_co IS NOT NULL AND _hr_for_co IS NOT NULL
              AND _edv_for_co > _esv_for_co AND _hr_for_co > 0
         THEN (_edv_for_co - _esv_for_co) * _hr_for_co / 1000.0
         ELSE NULL END
  ) AS CO,
  Ee_prime,
  EA_ratio,
  DT,
  LAVI,
  dd_grade_text AS dd_grade,
  -- Completeness flag: all 11 features non-null
  CASE WHEN EF IS NOT NULL AND EDV IS NOT NULL AND ESV IS NOT NULL
            AND SBP IS NOT NULL AND DBP IS NOT NULL AND HR IS NOT NULL
            AND Ee_prime IS NOT NULL AND EA_ratio IS NOT NULL
            AND DT IS NOT NULL AND LAVI IS NOT NULL
       THEN 1 ELSE 0 END AS is_complete
FROM computed
WHERE EF IS NOT NULL  -- 최소 EF는 있어야 함
ORDER BY subject_id, measurement_datetime;
