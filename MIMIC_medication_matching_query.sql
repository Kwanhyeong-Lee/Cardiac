-- ============================================================
-- PINN v4 × MIMIC-IV: Diuretic Treatment-Response Matching
-- BigQuery 원샷 쿼리
-- echo_study_list (mimiciv_echo) + prescriptions (mimiciv_3_1_hosp)
-- ============================================================

-- STEP 1: Echo measurements with timestamps
WITH echo_with_time AS (
  SELECT
    esl.subject_id,
    esl.study_id,
    esl.measurement_id,
    esl.measurement_datetime,
    esl.study_datetime
  FROM `physionet-data.mimiciv_echo.echo_study_list` esl
  WHERE esl.measurement_datetime IS NOT NULL
),

-- STEP 2: Echo pairs (연속 2개, 같은 환자)
echo_ordered AS (
  SELECT
    subject_id,
    measurement_id,
    measurement_datetime,
    study_id,
    ROW_NUMBER() OVER (PARTITION BY subject_id ORDER BY measurement_datetime) AS echo_seq,
    COUNT(*) OVER (PARTITION BY subject_id) AS total_echos
  FROM echo_with_time
),

echo_pairs AS (
  SELECT
    e1.subject_id,
    e1.measurement_id AS pre_measurement_id,
    e1.measurement_datetime AS pre_echo_time,
    e2.measurement_id AS post_measurement_id,
    e2.measurement_datetime AS post_echo_time,
    DATETIME_DIFF(e2.measurement_datetime, e1.measurement_datetime, DAY) AS days_between
  FROM echo_ordered e1
  JOIN echo_ordered e2
    ON e1.subject_id = e2.subject_id
    AND e2.echo_seq = e1.echo_seq + 1
  WHERE e1.total_echos >= 2
    AND DATETIME_DIFF(e2.measurement_datetime, e1.measurement_datetime, DAY) >= 1
),

-- STEP 3: Diuretics from prescriptions
rx_diuretics AS (
  SELECT
    subject_id,
    hadm_id,
    starttime,
    stoptime,
    drug,
    dose_val_rx,
    dose_unit_rx,
    route,
    CASE
      WHEN REGEXP_CONTAINS(LOWER(drug), r'furosemide|lasix') THEN 'furosemide'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'bumetanide|bumex') THEN 'bumetanide'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'torsemide|demadex') THEN 'torsemide'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'spironolactone|aldactone') THEN 'spironolactone'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'eplerenone') THEN 'eplerenone'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'metolazone') THEN 'metolazone'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'chlorthalidone') THEN 'chlorthalidone'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'hydrochlorothiazide|hctz') THEN 'HCTZ'
      ELSE 'other_diuretic'
    END AS drug_class,
    CASE
      WHEN REGEXP_CONTAINS(LOWER(drug), r'furosemide|lasix|bumetanide|bumex|torsemide|demadex') THEN 'loop'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'spironolactone|aldactone|eplerenone') THEN 'MRA'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'metolazone|chlorthalidone') THEN 'thiazide_like'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'hydrochlorothiazide|hctz') THEN 'thiazide'
      ELSE 'other'
    END AS diuretic_type
  FROM `physionet-data.mimiciv_3_1_hosp.prescriptions`
  WHERE REGEXP_CONTAINS(LOWER(drug), r'furosemide|lasix|bumetanide|bumex|torsemide|demadex|spironolactone|aldactone|eplerenone|metolazone|chlorthalidone|hydrochlorothiazide|hctz')
),

-- STEP 4: IV diuretics from ICU inputevents
iv_diuretics AS (
  SELECT
    subject_id,
    hadm_id,
    starttime,
    endtime AS stoptime,
    CAST(itemid AS STRING) AS drug,
    CAST(amount AS STRING) AS dose_val_rx,
    amountuom AS dose_unit_rx,
    'IV' AS route,
    CASE
      WHEN itemid IN (221794, 228340) THEN 'furosemide'
      WHEN itemid = 221986 THEN 'bumetanide'
      ELSE 'other_iv'
    END AS drug_class,
    'loop' AS diuretic_type
  FROM `physionet-data.mimiciv_3_1_icu.inputevents`
  WHERE itemid IN (221794, 228340, 221986)
),

-- STEP 5: Union all diuretics
all_diuretics AS (
  SELECT subject_id, starttime, stoptime, drug, dose_val_rx, dose_unit_rx,
         route, drug_class, diuretic_type
  FROM rx_diuretics
  UNION ALL
  SELECT subject_id, starttime, stoptime, drug, dose_val_rx, dose_unit_rx,
         route, drug_class, diuretic_type
  FROM iv_diuretics
),

-- STEP 6: Match diuretics between echo pairs
matched AS (
  SELECT
    ep.subject_id,
    ep.pre_measurement_id,
    ep.pre_echo_time,
    ep.post_measurement_id,
    ep.post_echo_time,
    ep.days_between,
    d.drug_class,
    d.diuretic_type,
    d.dose_val_rx,
    d.dose_unit_rx,
    d.route,
    d.starttime AS rx_start
  FROM echo_pairs ep
  JOIN all_diuretics d
    ON ep.subject_id = d.subject_id
    AND CAST(d.starttime AS DATETIME) >= ep.pre_echo_time
    AND CAST(d.starttime AS DATETIME) <= ep.post_echo_time
),

-- STEP 7: Aggregate per echo pair
echo_pair_rx AS (
  SELECT
    subject_id,
    pre_measurement_id,
    pre_echo_time,
    post_measurement_id,
    post_echo_time,
    days_between,
    MAX(CASE WHEN diuretic_type = 'loop' THEN 1 ELSE 0 END) AS has_loop,
    MAX(CASE WHEN drug_class = 'furosemide' THEN 1 ELSE 0 END) AS has_furosemide,
    MAX(CASE WHEN drug_class = 'bumetanide' THEN 1 ELSE 0 END) AS has_bumetanide,
    MAX(CASE WHEN drug_class = 'torsemide' THEN 1 ELSE 0 END) AS has_torsemide,
    MAX(CASE WHEN diuretic_type = 'MRA' THEN 1 ELSE 0 END) AS has_MRA,
    MAX(CASE WHEN diuretic_type IN ('thiazide', 'thiazide_like') THEN 1 ELSE 0 END) AS has_thiazide,
    MAX(CASE
      WHEN drug_class = 'furosemide' THEN SAFE_CAST(dose_val_rx AS FLOAT64)
      WHEN drug_class = 'bumetanide' THEN SAFE_CAST(dose_val_rx AS FLOAT64) * 40
      WHEN drug_class = 'torsemide' THEN SAFE_CAST(dose_val_rx AS FLOAT64) * 2
      ELSE NULL
    END) AS max_furosemide_equiv_mg,
    COUNT(*) AS total_rx_events,
    COUNT(DISTINCT drug_class) AS n_drug_classes,
    MAX(CASE WHEN route = 'IV' THEN 1 ELSE 0 END) AS has_iv
  FROM matched
  GROUP BY subject_id, pre_measurement_id, pre_echo_time,
           post_measurement_id, post_echo_time, days_between
),

-- STEP 8: Control group (no diuretics between echos)
no_rx_pairs AS (
  SELECT
    ep.subject_id,
    ep.pre_measurement_id,
    ep.pre_echo_time,
    ep.post_measurement_id,
    ep.post_echo_time,
    ep.days_between,
    0 AS has_loop, 0 AS has_furosemide, 0 AS has_bumetanide,
    0 AS has_torsemide, 0 AS has_MRA, 0 AS has_thiazide,
    CAST(NULL AS FLOAT64) AS max_furosemide_equiv_mg,
    0 AS total_rx_events, 0 AS n_drug_classes, 0 AS has_iv
  FROM echo_pairs ep
  WHERE NOT EXISTS (
    SELECT 1 FROM all_diuretics d
    WHERE d.subject_id = ep.subject_id
      AND CAST(d.starttime AS DATETIME) >= ep.pre_echo_time
      AND CAST(d.starttime AS DATETIME) <= ep.post_echo_time
  )
)

-- ============================================================
-- FINAL: 전체 echo pair + medication exposure
-- pre/post measurement_id 포함 → Python에서 PINN 결과와 바로 조인 가능
-- ============================================================
SELECT * FROM echo_pair_rx
UNION ALL
SELECT * FROM no_rx_pairs
ORDER BY subject_id, pre_echo_time;
