-- ============================================================
-- PINN v4 × MIMIC-III: Comprehensive HF Medication Matching
-- BigQuery 원샷 쿼리
-- chartevents (echo EF) + prescriptions + inputevents_mv/cv
-- ============================================================
--
-- 전체 HF GDMT + 관련 약물 13개 카테고리 매칭
-- MIMIC-III 구조에 맞춤 (테이블명, 컬럼명 차이 반영)
-- ============================================================

-- STEP 1: Echo times from chartevents (EF measurements)
WITH echo_times AS (
  SELECT DISTINCT
    ce.subject_id,
    ce.hadm_id,
    ce.charttime AS echo_time
  FROM `physionet-data.mimiciii_clinical.chartevents` ce
  WHERE ce.itemid IN (228152, 220088)  -- EF MetaVision items
    AND ce.valuenum IS NOT NULL
    AND ce.valuenum BETWEEN 5 AND 90
),

-- STEP 2: Echo pairs
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
-- STEP 3: ALL HF medications from prescriptions
-- ============================================================
rx_all AS (
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
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'eplerenone|inspra') THEN 'eplerenone'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'hydrochlorothiazide|hctz') THEN 'HCTZ'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'chlorthalidone') THEN 'chlorthalidone'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'metolazone|zaroxolyn') THEN 'metolazone'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'lisinopril|zestril|prinivil') THEN 'lisinopril'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'enalapril|vasotec') THEN 'enalapril'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'ramipril|altace') THEN 'ramipril'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'captopril|capoten') THEN 'captopril'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'benazepril|lotensin') THEN 'benazepril'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'fosinopril|monopril') THEN 'fosinopril'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'quinapril|accupril') THEN 'quinapril'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'perindopril|aceon') THEN 'perindopril'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'trandolapril|mavik') THEN 'trandolapril'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'moexipril|univasc') THEN 'moexipril'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'losartan|cozaar') THEN 'losartan'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'valsartan|diovan') AND NOT REGEXP_CONTAINS(LOWER(p.drug), r'sacubitril|entresto') THEN 'valsartan'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'irbesartan|avapro') THEN 'irbesartan'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'candesartan|atacand') THEN 'candesartan'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'olmesartan|benicar') THEN 'olmesartan'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'telmisartan|micardis') THEN 'telmisartan'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'azilsartan|edarbi') THEN 'azilsartan'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'eprosartan|teveten') THEN 'eprosartan'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'sacubitril|entresto') THEN 'sacubitril_valsartan'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'carvedilol|coreg') THEN 'carvedilol'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'metoprolol|lopressor|toprol') THEN 'metoprolol'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'bisoprolol|zebeta') THEN 'bisoprolol'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'atenolol|tenormin') THEN 'atenolol'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'propranolol|inderal') THEN 'propranolol'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'labetalol|trandate|normodyne') THEN 'labetalol'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'nebivolol|bystolic') THEN 'nebivolol'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'nadolol|corgard') THEN 'nadolol'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'sotalol|betapace') THEN 'sotalol'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'empagliflozin|jardiance') THEN 'empagliflozin'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'dapagliflozin|farxiga') THEN 'dapagliflozin'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'canagliflozin|invokana') THEN 'canagliflozin'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'ertugliflozin|steglatro') THEN 'ertugliflozin'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'digoxin|lanoxin') THEN 'digoxin'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'hydralazine|apresoline') THEN 'hydralazine'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'isosorbide dinitrate|isordil|bidil') THEN 'isosorbide_dinitrate'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'isosorbide mononitrate|imdur|ismo') THEN 'isosorbide_mononitrate'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'nitroglycerin|nitro|ntg') AND REGEXP_CONTAINS(LOWER(p.route), r'oral|sublingual|patch|topical|transdermal') THEN 'nitroglycerin'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'amlodipine|norvasc') THEN 'amlodipine'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'diltiazem|cardizem|tiazac') THEN 'diltiazem'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'verapamil|calan|isoptin') THEN 'verapamil'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'nifedipine|procardia|adalat') THEN 'nifedipine'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'felodipine|plendil') THEN 'felodipine'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'ivabradine|corlanor') THEN 'ivabradine'
      ELSE NULL
    END AS drug_class,

    CASE
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'furosemide|lasix|bumetanide|bumex|torsemide|demadex') THEN 'loop_diuretic'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'spironolactone|aldactone|eplerenone|inspra') THEN 'MRA'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'hydrochlorothiazide|hctz|chlorthalidone|metolazone|zaroxolyn') THEN 'thiazide'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'lisinopril|zestril|prinivil|enalapril|vasotec|ramipril|altace|captopril|capoten|benazepril|lotensin|fosinopril|monopril|quinapril|accupril|perindopril|aceon|trandolapril|mavik|moexipril|univasc') THEN 'ACEi'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'losartan|cozaar|irbesartan|avapro|candesartan|atacand|olmesartan|benicar|telmisartan|micardis|azilsartan|edarbi|eprosartan|teveten') THEN 'ARB'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'valsartan|diovan') AND NOT REGEXP_CONTAINS(LOWER(p.drug), r'sacubitril|entresto') THEN 'ARB'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'sacubitril|entresto') THEN 'ARNI'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'carvedilol|coreg|metoprolol|lopressor|toprol|bisoprolol|zebeta|atenolol|tenormin|propranolol|inderal|labetalol|trandate|normodyne|nebivolol|bystolic|nadolol|corgard|sotalol|betapace') THEN 'beta_blocker'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'empagliflozin|jardiance|dapagliflozin|farxiga|canagliflozin|invokana|ertugliflozin|steglatro') THEN 'SGLT2i'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'digoxin|lanoxin') THEN 'digoxin'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'hydralazine|apresoline') THEN 'hydralazine'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'isosorbide|isordil|imdur|ismo|bidil') THEN 'nitrate'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'nitroglycerin|nitro|ntg') AND REGEXP_CONTAINS(LOWER(p.route), r'oral|sublingual|patch|topical|transdermal') THEN 'nitrate'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'amlodipine|norvasc|diltiazem|cardizem|tiazac|verapamil|calan|isoptin|nifedipine|procardia|adalat|felodipine|plendil') THEN 'CCB'
      WHEN REGEXP_CONTAINS(LOWER(p.drug), r'ivabradine|corlanor') THEN 'ivabradine'
      ELSE NULL
    END AS drug_category

  FROM `physionet-data.mimiciii_clinical.prescriptions` p
  WHERE (
    REGEXP_CONTAINS(LOWER(p.drug), r'furosemide|lasix|bumetanide|bumex|torsemide|demadex')
    OR REGEXP_CONTAINS(LOWER(p.drug), r'spironolactone|aldactone|eplerenone|inspra')
    OR REGEXP_CONTAINS(LOWER(p.drug), r'hydrochlorothiazide|hctz|chlorthalidone|metolazone|zaroxolyn')
    OR REGEXP_CONTAINS(LOWER(p.drug), r'lisinopril|zestril|prinivil|enalapril|vasotec|ramipril|altace|captopril|capoten|benazepril|lotensin|fosinopril|monopril|quinapril|accupril|perindopril|aceon|trandolapril|mavik|moexipril|univasc')
    OR REGEXP_CONTAINS(LOWER(p.drug), r'losartan|cozaar|valsartan|diovan|irbesartan|avapro|candesartan|atacand|olmesartan|benicar|telmisartan|micardis|azilsartan|edarbi|eprosartan|teveten')
    OR REGEXP_CONTAINS(LOWER(p.drug), r'sacubitril|entresto')
    OR REGEXP_CONTAINS(LOWER(p.drug), r'carvedilol|coreg|metoprolol|lopressor|toprol|bisoprolol|zebeta|atenolol|tenormin|propranolol|inderal|labetalol|trandate|normodyne|nebivolol|bystolic|nadolol|corgard|sotalol|betapace')
    OR REGEXP_CONTAINS(LOWER(p.drug), r'empagliflozin|jardiance|dapagliflozin|farxiga|canagliflozin|invokana|ertugliflozin|steglatro')
    OR REGEXP_CONTAINS(LOWER(p.drug), r'digoxin|lanoxin')
    OR REGEXP_CONTAINS(LOWER(p.drug), r'hydralazine|apresoline')
    OR REGEXP_CONTAINS(LOWER(p.drug), r'isosorbide|isordil|imdur|ismo|bidil')
    OR (REGEXP_CONTAINS(LOWER(p.drug), r'nitroglycerin|nitro|ntg') AND REGEXP_CONTAINS(LOWER(p.route), r'oral|sublingual|patch|topical|transdermal'))
    OR REGEXP_CONTAINS(LOWER(p.drug), r'amlodipine|norvasc|diltiazem|cardizem|tiazac|verapamil|calan|isoptin|nifedipine|procardia|adalat|felodipine|plendil')
    OR REGEXP_CONTAINS(LOWER(p.drug), r'ivabradine|corlanor')
  )
),

rx_filtered AS (
  SELECT * FROM rx_all WHERE drug_class IS NOT NULL
),

-- ============================================================
-- STEP 4: IV meds — inputevents_mv (MetaVision)
-- ============================================================
iv_mv AS (
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
      WHEN ie.itemid = 225974 THEN 'metoprolol'
      WHEN ie.itemid = 221468 THEN 'diltiazem'
      WHEN ie.itemid = 222056 THEN 'esmolol'
      WHEN ie.itemid = 225153 THEN 'labetalol'
      WHEN ie.itemid = 227692 THEN 'enalapril'
      WHEN ie.itemid = 228339 THEN 'digoxin'
      WHEN ie.itemid = 221828 THEN 'hydralazine'
      ELSE NULL
    END AS drug_class,
    CASE
      WHEN ie.itemid IN (221794, 228340, 221986) THEN 'loop_diuretic'
      WHEN ie.itemid IN (225974, 222056, 225153) THEN 'beta_blocker'
      WHEN ie.itemid = 221468 THEN 'CCB'
      WHEN ie.itemid = 227692 THEN 'ACEi'
      WHEN ie.itemid = 228339 THEN 'digoxin'
      WHEN ie.itemid = 221828 THEN 'hydralazine'
      ELSE NULL
    END AS drug_category
  FROM `physionet-data.mimiciii_clinical.inputevents_mv` ie
  JOIN `physionet-data.mimiciii_clinical.d_items` di ON ie.itemid = di.itemid
  WHERE ie.itemid IN (221794, 228340, 221986, 225974, 221468, 222056, 225153, 227692, 228339, 221828)
),

-- STEP 5: IV meds — inputevents_cv (CareVue)
iv_cv AS (
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
      WHEN REGEXP_CONTAINS(LOWER(di.label), r'metoprolol') THEN 'metoprolol'
      WHEN REGEXP_CONTAINS(LOWER(di.label), r'diltiazem') THEN 'diltiazem'
      WHEN REGEXP_CONTAINS(LOWER(di.label), r'labetalol') THEN 'labetalol'
      WHEN REGEXP_CONTAINS(LOWER(di.label), r'enalapril') THEN 'enalapril'
      WHEN REGEXP_CONTAINS(LOWER(di.label), r'digoxin') THEN 'digoxin'
      WHEN REGEXP_CONTAINS(LOWER(di.label), r'hydralazine') THEN 'hydralazine'
      ELSE NULL
    END AS drug_class,
    CASE
      WHEN REGEXP_CONTAINS(LOWER(di.label), r'furosemide|lasix|bumetanide|bumex') THEN 'loop_diuretic'
      WHEN REGEXP_CONTAINS(LOWER(di.label), r'metoprolol|labetalol') THEN 'beta_blocker'
      WHEN REGEXP_CONTAINS(LOWER(di.label), r'diltiazem') THEN 'CCB'
      WHEN REGEXP_CONTAINS(LOWER(di.label), r'enalapril') THEN 'ACEi'
      WHEN REGEXP_CONTAINS(LOWER(di.label), r'digoxin') THEN 'digoxin'
      WHEN REGEXP_CONTAINS(LOWER(di.label), r'hydralazine') THEN 'hydralazine'
      ELSE NULL
    END AS drug_category
  FROM `physionet-data.mimiciii_clinical.inputevents_cv` ie
  JOIN `physionet-data.mimiciii_clinical.d_items` di ON ie.itemid = di.itemid
  WHERE REGEXP_CONTAINS(LOWER(di.label), r'furosemide|lasix|bumetanide|bumex|metoprolol|diltiazem|labetalol|enalapril|digoxin|hydralazine')
),

-- STEP 6: Union all
all_meds AS (
  SELECT subject_id, rx_start, rx_stop, drug, dose_val_rx, dose_unit_rx,
         route, source, drug_class, drug_category
  FROM rx_filtered
  UNION ALL
  SELECT subject_id, rx_start, rx_stop, drug, dose_val_rx, dose_unit_rx,
         route, source, drug_class, drug_category
  FROM iv_mv WHERE drug_class IS NOT NULL
  UNION ALL
  SELECT subject_id, rx_start, rx_stop, drug, dose_val_rx, dose_unit_rx,
         route, source, drug_class, drug_category
  FROM iv_cv WHERE drug_class IS NOT NULL
),

-- ============================================================
-- STEP 7: Match medications between echo pairs
-- ============================================================
matched AS (
  SELECT
    ep.subject_id,
    ep.pre_echo_time,
    ep.post_echo_time,
    ep.days_between,
    d.drug_class,
    d.drug_category,
    d.dose_val_rx,
    d.dose_unit_rx,
    d.route,
    d.source,
    d.rx_start
  FROM echo_pairs ep
  JOIN all_meds d
    ON ep.subject_id = d.subject_id
    AND d.rx_start >= TIMESTAMP_SUB(ep.pre_echo_time, INTERVAL 1 DAY)
    AND d.rx_start <= ep.post_echo_time
),

-- ============================================================
-- STEP 8: Aggregate per echo pair
-- ============================================================
echo_pair_rx AS (
  SELECT
    subject_id,
    pre_echo_time,
    post_echo_time,
    days_between,

    MAX(CASE WHEN drug_category = 'loop_diuretic' THEN 1 ELSE 0 END) AS has_loop,
    MAX(CASE WHEN drug_class = 'furosemide' THEN 1 ELSE 0 END) AS has_furosemide,
    MAX(CASE WHEN drug_class = 'bumetanide' THEN 1 ELSE 0 END) AS has_bumetanide,
    MAX(CASE WHEN drug_class = 'torsemide' THEN 1 ELSE 0 END) AS has_torsemide,
    MAX(CASE WHEN drug_category = 'MRA' THEN 1 ELSE 0 END) AS has_MRA,
    MAX(CASE WHEN drug_category = 'thiazide' THEN 1 ELSE 0 END) AS has_thiazide,
    MAX(CASE
      WHEN drug_class = 'furosemide' THEN SAFE_CAST(dose_val_rx AS FLOAT64)
      WHEN drug_class = 'bumetanide' THEN SAFE_CAST(dose_val_rx AS FLOAT64) * 40
      WHEN drug_class = 'torsemide' THEN SAFE_CAST(dose_val_rx AS FLOAT64) * 2
      ELSE NULL
    END) AS max_furosemide_equiv_mg,

    MAX(CASE WHEN drug_category = 'ACEi' THEN 1 ELSE 0 END) AS has_ACEi,
    MAX(CASE WHEN drug_category = 'ARB' THEN 1 ELSE 0 END) AS has_ARB,
    MAX(CASE WHEN drug_category = 'ARNI' THEN 1 ELSE 0 END) AS has_ARNI,
    MAX(CASE WHEN drug_category IN ('ACEi', 'ARB', 'ARNI') THEN 1 ELSE 0 END) AS has_RAASi,

    MAX(CASE WHEN drug_category = 'beta_blocker' THEN 1 ELSE 0 END) AS has_BB,
    MAX(CASE WHEN drug_class = 'carvedilol' THEN 1 ELSE 0 END) AS has_carvedilol,
    MAX(CASE WHEN drug_class = 'metoprolol' THEN 1 ELSE 0 END) AS has_metoprolol,
    MAX(CASE WHEN drug_class = 'bisoprolol' THEN 1 ELSE 0 END) AS has_bisoprolol,

    MAX(CASE WHEN drug_category = 'SGLT2i' THEN 1 ELSE 0 END) AS has_SGLT2i,

    MAX(CASE WHEN drug_category = 'digoxin' THEN 1 ELSE 0 END) AS has_digoxin,
    MAX(CASE WHEN drug_category = 'hydralazine' THEN 1 ELSE 0 END) AS has_hydralazine,
    MAX(CASE WHEN drug_category = 'nitrate' THEN 1 ELSE 0 END) AS has_nitrate,
    MAX(CASE WHEN drug_category = 'hydralazine' THEN 1 ELSE 0 END) *
    MAX(CASE WHEN drug_category = 'nitrate' THEN 1 ELSE 0 END) AS has_HISDN,

    MAX(CASE WHEN drug_category = 'CCB' THEN 1 ELSE 0 END) AS has_CCB,
    MAX(CASE WHEN drug_class IN ('diltiazem', 'verapamil') THEN 1 ELSE 0 END) AS has_CCB_nonDHP,
    MAX(CASE WHEN drug_class IN ('amlodipine', 'nifedipine', 'felodipine') THEN 1 ELSE 0 END) AS has_CCB_DHP,

    MAX(CASE WHEN drug_category = 'ivabradine' THEN 1 ELSE 0 END) AS has_ivabradine,

    COUNT(*) AS total_rx_events,
    COUNT(DISTINCT drug_class) AS n_drug_classes,
    COUNT(DISTINCT drug_category) AS n_drug_categories,
    MAX(CASE WHEN route = 'IV' THEN 1 ELSE 0 END) AS has_iv,

    (MAX(CASE WHEN drug_category IN ('ACEi', 'ARB', 'ARNI') THEN 1 ELSE 0 END)
     + MAX(CASE WHEN drug_category = 'beta_blocker' THEN 1 ELSE 0 END)
     + MAX(CASE WHEN drug_category = 'MRA' THEN 1 ELSE 0 END)
     + MAX(CASE WHEN drug_category = 'SGLT2i' THEN 1 ELSE 0 END)
    ) AS gdmt_pillar_count,

    STRING_AGG(DISTINCT drug_class, ', ' ORDER BY drug_class) AS drug_list,
    STRING_AGG(DISTINCT drug_category, ', ' ORDER BY drug_category) AS category_list

  FROM matched
  GROUP BY subject_id, pre_echo_time, post_echo_time, days_between
),

-- STEP 9: Control group
no_rx_pairs AS (
  SELECT
    ep.subject_id,
    ep.pre_echo_time,
    ep.post_echo_time,
    ep.days_between,
    0 AS has_loop, 0 AS has_furosemide, 0 AS has_bumetanide, 0 AS has_torsemide,
    0 AS has_MRA, 0 AS has_thiazide,
    CAST(NULL AS FLOAT64) AS max_furosemide_equiv_mg,
    0 AS has_ACEi, 0 AS has_ARB, 0 AS has_ARNI, 0 AS has_RAASi,
    0 AS has_BB, 0 AS has_carvedilol, 0 AS has_metoprolol, 0 AS has_bisoprolol,
    0 AS has_SGLT2i,
    0 AS has_digoxin, 0 AS has_hydralazine, 0 AS has_nitrate, 0 AS has_HISDN,
    0 AS has_CCB, 0 AS has_CCB_nonDHP, 0 AS has_CCB_DHP,
    0 AS has_ivabradine,
    0 AS total_rx_events, 0 AS n_drug_classes, 0 AS n_drug_categories, 0 AS has_iv,
    0 AS gdmt_pillar_count,
    CAST(NULL AS STRING) AS drug_list,
    CAST(NULL AS STRING) AS category_list
  FROM echo_pairs ep
  WHERE NOT EXISTS (
    SELECT 1 FROM all_meds d
    WHERE d.subject_id = ep.subject_id
      AND d.rx_start >= TIMESTAMP_SUB(ep.pre_echo_time, INTERVAL 1 DAY)
      AND d.rx_start <= ep.post_echo_time
  )
)

-- ============================================================
-- FINAL
-- ============================================================
SELECT * FROM echo_pair_rx
UNION ALL
SELECT * FROM no_rx_pairs
ORDER BY subject_id, pre_echo_time;
