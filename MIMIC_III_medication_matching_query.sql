-- ============================================================
-- PINN v4 × MIMIC-III: Diuretic Treatment-Response Matching
-- BigQuery 문법 (physionet-data 프로젝트)
-- 한 번에 돌리면 최종 테이블 나옴
-- ============================================================

-- ============================================================
-- STEP 1: Diuretics - Prescriptions (경구/퇴원처방)
-- ============================================================
WITH rx_diuretics AS (
  SELECT
    p.subject_id,
    p.hadm_id,
    CAST(p.startdate AS TIMESTAMP) AS rx_start,
    COALESCE(CAST(p.enddate AS TIMESTAMP), TIMESTAMP_ADD(CAST(p.startdate AS TIMESTAMP), INTERVAL 1 DAY)) AS rx_stop,
    p.drug,
    p.dose_val_rx,
    p.dose_unit_rx,
    p.route,
    'prescription' AS source,
    CASE
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'furosemide|lasix') THEN 'furosemide'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'bumetanide|bumex') THEN 'bumetanide'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'torsemide|demadex') THEN 'torsemide'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'spironolactone|aldactone') THEN 'spironolactone'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'eplerenone') THEN 'eplerenone'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'metolazone') THEN 'metolazone'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'chlorthalidone') THEN 'chlorthalidone'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'hydrochlorothiazide|hctz') THEN 'HCTZ'
      ELSE 'other_diuretic'
    END AS drug_class,
    CASE
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'furosemide|lasix|bumetanide|bumex|torsemide|demadex') THEN 'loop'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'spironolactone|aldactone|eplerenone') THEN 'MRA'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'metolazone|chlorthalidone') THEN 'thiazide_like'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'hydrochlorothiazide|hctz') THEN 'thiazide'
      ELSE 'other'
    END AS diuretic_type
  FROM `physionet-data.mimiciii_clinical.prescriptions` p
  WHERE REGEXP_CONTAINS(LOWER(p.drug), r'furosemide|lasix|bumetanide|bumex|torsemide|demadex|spironolactone|aldactone|eplerenone|metolazone|chlorthalidone|hydrochlorothiazide|hctz')
),

-- ============================================================
-- STEP 2: IV Diuretics - inputevents_mv (MetaVision ICU)
-- ============================================================
iv_diuretics_mv AS (
  SELECT
    ie.subject_id,
    ie.hadm_id,
    ie.starttime AS rx_start,
    ie.endtime AS rx_stop,
    di.label AS drug,
    CAST(ie.amount AS STRING) AS dose_val_rx,
    ie.amountuom AS dose_unit_rx,
    'IV' AS route,
    'inputevents_mv' AS source,
    CASE
      WHEN ie.itemid IN (221794, 228340) THEN 'furosemide'
      WHEN ie.itemid = 221986 THEN 'bumetanide'
      ELSE 'other_iv_diuretic'
    END AS drug_class,
    'loop' AS diuretic_type
  FROM `physionet-data.mimiciii_clinical.inputevents_mv` ie
  JOIN `physionet-data.mimiciii_clinical.d_items` di ON ie.itemid = di.itemid
  WHERE ie.itemid IN (221794, 228340, 221986)
),

-- ============================================================
-- STEP 3: IV Diuretics - inputevents_cv (CareVue ICU)
-- ============================================================
iv_diuretics_cv AS (
  SELECT
    ie.subject_id,
    ie.hadm_id,
    ie.charttime AS rx_start,
    TIMESTAMP_ADD(ie.charttime, INTERVAL 1 HOUR) AS rx_stop,
    di.label AS drug,
    CAST(ie.amount AS STRING) AS dose_val_rx,
    ie.amountuom AS dose_unit_rx,
    'IV' AS route,
    'inputevents_cv' AS source,
    CASE
      WHEN REGEXP_CONTAINS(LOWER(di.label), r'furosemide|lasix') THEN 'furosemide'
      WHEN REGEXP_CONTAINS(LOWER(di.label), r'bumetanide|bumex') THEN 'bumetanide'
      ELSE 'other_iv_diuretic'
    END AS drug_class,
    'loop' AS diuretic_type
  FROM `physionet-data.mimiciii_clinical.inputevents_cv` ie
  JOIN `physionet-data.mimiciii_clinical.d_items` di ON ie.itemid = di.itemid
  WHERE REGEXP_CONTAINS(LOWER(di.label), r'furosemide|lasix|bumetanide|bumex')
),

-- ============================================================
-- STEP 4: Union 모든 diuretics
-- ============================================================
all_diuretics AS (
  SELECT * FROM rx_diuretics
  UNION ALL
  SELECT * FROM iv_diuretics_mv
  UNION ALL
  SELECT * FROM iv_diuretics_cv
),

-- ============================================================
-- STEP 5: Echo 시점 추출
-- MIMIC-III chartevents에서 EF 기록 시점 = echo 시점
-- ============================================================
echo_times AS (
  SELECT DISTINCT
    ce.subject_id,
    ce.hadm_id,
    ce.charttime AS echo_time
  FROM `physionet-data.mimiciii_clinical.chartevents` ce
  WHERE ce.itemid IN (
    228152,  -- Ejection Fraction (MetaVision)
    220088   -- EF alternative
    -- 부록A 결과 보고 필요하면 여기 itemid 추가
  )
  AND ce.valuenum IS NOT NULL
  AND ce.valuenum BETWEEN 5 AND 90
),

-- ============================================================
-- STEP 6: Echo pairs (연속 2개)
-- ============================================================
echo_ordered AS (
  SELECT
    subject_id,
    hadm_id,
    echo_time,
    ROW_NUMBER() OVER (PARTITION BY subject_id ORDER BY echo_time) AS echo_seq,
    COUNT(*) OVER (PARTITION BY subject_id) AS total_echos
  FROM echo_times
),

echo_pairs AS (
  SELECT
    e1.subject_id,
    e1.echo_time AS pre_echo_time,
    e1.hadm_id AS pre_hadm_id,
    e2.echo_time AS post_echo_time,
    e2.hadm_id AS post_hadm_id,
    TIMESTAMP_DIFF(e2.echo_time, e1.echo_time, DAY) AS days_between
  FROM echo_ordered e1
  JOIN echo_ordered e2
    ON e1.subject_id = e2.subject_id
    AND e2.echo_seq = e1.echo_seq + 1
  WHERE e1.total_echos >= 2
    AND TIMESTAMP_DIFF(e2.echo_time, e1.echo_time, DAY) >= 1
),

-- ============================================================
-- STEP 7: Echo pair ↔ Diuretic 매칭
-- ============================================================
matched_triplets AS (
  SELECT
    ep.subject_id,
    ep.pre_echo_time,
    ep.post_echo_time,
    ep.days_between,
    d.drug_class,
    d.diuretic_type,
    d.dose_val_rx,
    d.dose_unit_rx,
    d.route,
    d.source,
    d.rx_start,
    d.rx_stop
  FROM echo_pairs ep
  JOIN all_diuretics d
    ON ep.subject_id = d.subject_id
    AND d.rx_start >= TIMESTAMP_SUB(ep.pre_echo_time, INTERVAL 1 DAY)
    AND d.rx_start <= ep.post_echo_time
),

-- ============================================================
-- STEP 8: Echo pair별 diuretic 요약
-- ============================================================
echo_pair_rx_summary AS (
  SELECT
    subject_id,
    pre_echo_time,
    post_echo_time,
    days_between,
    MAX(CASE WHEN diuretic_type = 'loop' THEN 1 ELSE 0 END) AS has_loop_diuretic,
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
    COUNT(DISTINCT drug_class) AS n_diuretic_classes,
    MAX(CASE WHEN route = 'IV' THEN 1 ELSE 0 END) AS has_iv_diuretic
  FROM matched_triplets
  GROUP BY subject_id, pre_echo_time, post_echo_time, days_between
),

-- ============================================================
-- STEP 9: Control group (diuretic 없는 echo pairs)
-- ============================================================
no_diuretic_pairs AS (
  SELECT
    ep.subject_id,
    ep.pre_echo_time,
    ep.post_echo_time,
    ep.days_between,
    0 AS has_loop_diuretic,
    0 AS has_furosemide,
    0 AS has_bumetanide,
    0 AS has_torsemide,
    0 AS has_MRA,
    0 AS has_thiazide,
    CAST(NULL AS FLOAT64) AS max_furosemide_equiv_mg,
    0 AS total_rx_events,
    0 AS n_diuretic_classes,
    0 AS has_iv_diuretic
  FROM echo_pairs ep
  WHERE NOT EXISTS (
    SELECT 1 FROM all_diuretics d
    WHERE d.subject_id = ep.subject_id
      AND d.rx_start >= TIMESTAMP_SUB(ep.pre_echo_time, INTERVAL 1 DAY)
      AND d.rx_start <= ep.post_echo_time
  )
)

-- ============================================================
-- FINAL: 전체 echo pair + medication exposure
-- ============================================================
SELECT * FROM echo_pair_rx_summary
UNION ALL
SELECT * FROM no_diuretic_pairs
ORDER BY subject_id, pre_echo_time;
