-- ============================================================
-- eICU External Validation: Data Extraction Query
-- Target: 11 input variables matching MIMIC-IV cardiac dataset
-- ============================================================
-- NOTE: Adjust project/dataset path to your BigQuery setup
-- physionet-data.eicu_crd  OR  your_project.eicu_crd

WITH echo_raw AS (
    -- Echo parameters from nurseCharting
    SELECT
        nc.patientunitstayid,
        nc.nursingchartcelllabel AS param,
        SAFE_CAST(nc.nursingchartvalue AS FLOAT64) AS val,
        nc.nursingchartoffset AS chart_offset
    FROM `physionet-data.eicu_crd.nurseCharting` nc
    WHERE nc.nursingchartcelllabel IN (
        -- Adjust these labels based on your eICU instance
        'EF', 'Ejection Fraction', 'LVEF',
        'EDV', 'LVEDV', 'LV End Diastolic Volume',
        'ESV', 'LVESV', 'LV End Systolic Volume',
        'E/e''', 'E/e'' ratio', 'Ee_prime',
        'LAVI', 'LA Volume Index',
        'E/A', 'E/A ratio',
        'DT', 'Deceleration Time',
        'Cardiac Output', 'CO'
    )
    AND SAFE_CAST(nc.nursingchartvalue AS FLOAT64) IS NOT NULL
),

vitals AS (
    -- SBP, DBP, HR from vitalPeriodic (first stable set per stay)
    SELECT
        patientunitstayid,
        AVG(systemicsystolic) AS pre_SBP,
        AVG(systemicdiastolic) AS pre_DBP,
        AVG(heartrate) AS pre_HR
    FROM `physionet-data.eicu_crd.vitalPeriodic`
    WHERE systemicsystolic IS NOT NULL
      AND systemicdiastolic IS NOT NULL
      AND heartrate IS NOT NULL
      AND observationoffset BETWEEN 0 AND 1440  -- first 24h
    GROUP BY patientunitstayid
),

echo_pivot AS (
    SELECT
        patientunitstayid,
        MAX(CASE WHEN param IN ('EF','Ejection Fraction','LVEF') THEN val END) AS pre_EF,
        MAX(CASE WHEN param IN ('EDV','LVEDV','LV End Diastolic Volume') THEN val END) AS pre_EDV,
        MAX(CASE WHEN param IN ('ESV','LVESV','LV End Systolic Volume') THEN val END) AS pre_ESV,
        MAX(CASE WHEN param IN ('E/e''','E/e'' ratio','Ee_prime') THEN val END) AS pre_Ee_prime,
        MAX(CASE WHEN param IN ('LAVI','LA Volume Index') THEN val END) AS pre_LAVI,
        MAX(CASE WHEN param IN ('E/A','E/A ratio') THEN val END) AS pre_EA_ratio,
        MAX(CASE WHEN param IN ('DT','Deceleration Time') THEN val END) AS pre_DT,
        MAX(CASE WHEN param IN ('Cardiac Output','CO') THEN val END) AS pre_CO
    FROM echo_raw
    GROUP BY patientunitstayid
)

SELECT
    e.patientunitstayid,
    e.pre_EF,
    e.pre_EDV,
    e.pre_ESV,
    v.pre_SBP,
    v.pre_DBP,
    v.pre_HR,
    e.pre_Ee_prime,
    e.pre_LAVI,
    e.pre_EA_ratio,
    e.pre_DT,
    COALESCE(e.pre_CO, (e.pre_EDV - e.pre_ESV) * v.pre_HR / 1000) AS pre_CO
FROM echo_pivot e
JOIN vitals v USING (patientunitstayid)
WHERE e.pre_EF IS NOT NULL
  AND e.pre_EDV IS NOT NULL
  AND e.pre_ESV IS NOT NULL
  -- Sanity filters
  AND e.pre_EF BETWEEN 5 AND 90
  AND e.pre_EDV BETWEEN 30 AND 500
  AND e.pre_ESV BETWEEN 10 AND 400
  AND v.pre_SBP BETWEEN 60 AND 250
  AND v.pre_DBP BETWEEN 30 AND 150
  AND v.pre_HR BETWEEN 30 AND 200
;
