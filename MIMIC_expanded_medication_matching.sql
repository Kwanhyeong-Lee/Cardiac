-- ============================================================
-- PINN v4 × MIMIC-IV: Comprehensive HF Medication Matching
-- BigQuery 원샷 쿼리 — 모든 HF 관련 약물 한번에 매칭
-- structured_measurement 기반 (v2 dataset과 measurement_id 일치)
-- ============================================================
--
-- Drug Classes Covered:
--   1. Loop diuretics: furosemide, bumetanide, torsemide
--   2. MRA: spironolactone, eplerenone
--   3. Thiazide/like: HCTZ, chlorthalidone, metolazone
--   4. ACEi: lisinopril, enalapril, ramipril, captopril, benazepril,
--           fosinopril, quinapril, perindopril, trandolapril, moexipril
--   5. ARB: losartan, valsartan, irbesartan, candesartan, olmesartan,
--          telmisartan, azilsartan, eprosartan
--   6. ARNI: sacubitril/valsartan (Entresto)
--   7. Beta-blockers: carvedilol, metoprolol, bisoprolol, atenolol,
--                     propranolol, labetalol, nebivolol, nadolol
--   8. SGLT2i: empagliflozin, dapagliflozin, canagliflozin, ertugliflozin
--   9. Digoxin
--  10. Hydralazine
--  11. Nitrates: isosorbide dinitrate/mononitrate, nitroglycerin
--  12. CCB: amlodipine, diltiazem, verapamil, nifedipine, felodipine
--  13. Ivabradine (Corlanor)
-- ============================================================

-- STEP 1: Echo times from structured_measurement (v2 기준)
-- EF가 있는 measurement만 (v2 WHERE 조건과 동일)
WITH echo_times AS (
  SELECT DISTINCT
    sm.subject_id,
    sm.measurement_id,
    sm.measurement_datetime
  FROM `physionet-data.mimiciv_echo.structured_measurement` sm
  WHERE sm.measurement IN ('biplane_lvef', 'lvef')
    AND SAFE_CAST(sm.result AS FLOAT64) IS NOT NULL
    AND sm.measurement_datetime IS NOT NULL
),

-- STEP 2: Echo pairs (연속 2개, 같은 환자)
echo_ordered AS (
  SELECT
    subject_id,
    measurement_id,
    measurement_datetime,
    ROW_NUMBER() OVER (PARTITION BY subject_id ORDER BY measurement_datetime) AS echo_seq,
    COUNT(*) OVER (PARTITION BY subject_id) AS total_echos
  FROM echo_times
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

-- ============================================================
-- STEP 3: ALL HF-relevant medications from prescriptions
-- ============================================================
rx_all AS (
  SELECT
    subject_id,
    hadm_id,
    starttime,
    stoptime,
    drug,
    dose_val_rx,
    dose_unit_rx,
    route,

    -- === Drug class (specific agent) ===
    CASE
      -- Loop diuretics
      WHEN REGEXP_CONTAINS(LOWER(drug), r'furosemide|lasix') THEN 'furosemide'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'bumetanide|bumex') THEN 'bumetanide'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'torsemide|demadex') THEN 'torsemide'
      -- MRA
      WHEN REGEXP_CONTAINS(LOWER(drug), r'spironolactone|aldactone') THEN 'spironolactone'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'eplerenone|inspra') THEN 'eplerenone'
      -- Thiazide
      WHEN REGEXP_CONTAINS(LOWER(drug), r'hydrochlorothiazide|hctz') THEN 'HCTZ'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'chlorthalidone') THEN 'chlorthalidone'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'metolazone|zaroxolyn') THEN 'metolazone'
      -- ACEi
      WHEN REGEXP_CONTAINS(LOWER(drug), r'lisinopril|zestril|prinivil') THEN 'lisinopril'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'enalapril|vasotec') THEN 'enalapril'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'ramipril|altace') THEN 'ramipril'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'captopril|capoten') THEN 'captopril'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'benazepril|lotensin') THEN 'benazepril'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'fosinopril|monopril') THEN 'fosinopril'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'quinapril|accupril') THEN 'quinapril'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'perindopril|aceon') THEN 'perindopril'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'trandolapril|mavik') THEN 'trandolapril'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'moexipril|univasc') THEN 'moexipril'
      -- ARB
      WHEN REGEXP_CONTAINS(LOWER(drug), r'losartan|cozaar') THEN 'losartan'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'valsartan|diovan') AND NOT REGEXP_CONTAINS(LOWER(drug), r'sacubitril|entresto') THEN 'valsartan'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'irbesartan|avapro') THEN 'irbesartan'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'candesartan|atacand') THEN 'candesartan'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'olmesartan|benicar') THEN 'olmesartan'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'telmisartan|micardis') THEN 'telmisartan'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'azilsartan|edarbi') THEN 'azilsartan'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'eprosartan|teveten') THEN 'eprosartan'
      -- ARNI
      WHEN REGEXP_CONTAINS(LOWER(drug), r'sacubitril|entresto') THEN 'sacubitril_valsartan'
      -- Beta-blockers
      WHEN REGEXP_CONTAINS(LOWER(drug), r'carvedilol|coreg') THEN 'carvedilol'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'metoprolol|lopressor|toprol') THEN 'metoprolol'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'bisoprolol|zebeta') THEN 'bisoprolol'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'atenolol|tenormin') THEN 'atenolol'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'propranolol|inderal') THEN 'propranolol'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'labetalol|trandate|normodyne') THEN 'labetalol'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'nebivolol|bystolic') THEN 'nebivolol'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'nadolol|corgard') THEN 'nadolol'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'sotalol|betapace') THEN 'sotalol'
      -- SGLT2i
      WHEN REGEXP_CONTAINS(LOWER(drug), r'empagliflozin|jardiance') THEN 'empagliflozin'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'dapagliflozin|farxiga') THEN 'dapagliflozin'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'canagliflozin|invokana') THEN 'canagliflozin'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'ertugliflozin|steglatro') THEN 'ertugliflozin'
      -- Digoxin
      WHEN REGEXP_CONTAINS(LOWER(drug), r'digoxin|lanoxin') THEN 'digoxin'
      -- Hydralazine
      WHEN REGEXP_CONTAINS(LOWER(drug), r'hydralazine|apresoline') THEN 'hydralazine'
      -- Nitrates
      WHEN REGEXP_CONTAINS(LOWER(drug), r'isosorbide dinitrate|isordil|bidil') THEN 'isosorbide_dinitrate'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'isosorbide mononitrate|imdur|ismo') THEN 'isosorbide_mononitrate'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'nitroglycerin|nitro|ntg') AND REGEXP_CONTAINS(LOWER(route), r'oral|sublingual|patch|topical|transdermal') THEN 'nitroglycerin'
      -- CCB
      WHEN REGEXP_CONTAINS(LOWER(drug), r'amlodipine|norvasc') THEN 'amlodipine'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'diltiazem|cardizem|tiazac') THEN 'diltiazem'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'verapamil|calan|isoptin') THEN 'verapamil'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'nifedipine|procardia|adalat') THEN 'nifedipine'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'felodipine|plendil') THEN 'felodipine'
      -- Ivabradine
      WHEN REGEXP_CONTAINS(LOWER(drug), r'ivabradine|corlanor') THEN 'ivabradine'
      ELSE NULL
    END AS drug_class,

    -- === Drug category (therapeutic class) ===
    CASE
      WHEN REGEXP_CONTAINS(LOWER(drug), r'furosemide|lasix|bumetanide|bumex|torsemide|demadex') THEN 'loop_diuretic'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'spironolactone|aldactone|eplerenone|inspra') THEN 'MRA'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'hydrochlorothiazide|hctz|chlorthalidone|metolazone|zaroxolyn') THEN 'thiazide'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'lisinopril|zestril|prinivil|enalapril|vasotec|ramipril|altace|captopril|capoten|benazepril|lotensin|fosinopril|monopril|quinapril|accupril|perindopril|aceon|trandolapril|mavik|moexipril|univasc') THEN 'ACEi'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'losartan|cozaar|irbesartan|avapro|candesartan|atacand|olmesartan|benicar|telmisartan|micardis|azilsartan|edarbi|eprosartan|teveten') THEN 'ARB'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'valsartan|diovan') AND NOT REGEXP_CONTAINS(LOWER(drug), r'sacubitril|entresto') THEN 'ARB'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'sacubitril|entresto') THEN 'ARNI'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'carvedilol|coreg|metoprolol|lopressor|toprol|bisoprolol|zebeta|atenolol|tenormin|propranolol|inderal|labetalol|trandate|normodyne|nebivolol|bystolic|nadolol|corgard|sotalol|betapace') THEN 'beta_blocker'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'empagliflozin|jardiance|dapagliflozin|farxiga|canagliflozin|invokana|ertugliflozin|steglatro') THEN 'SGLT2i'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'digoxin|lanoxin') THEN 'digoxin'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'hydralazine|apresoline') THEN 'hydralazine'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'isosorbide|isordil|imdur|ismo|bidil') THEN 'nitrate'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'nitroglycerin|nitro|ntg') AND REGEXP_CONTAINS(LOWER(route), r'oral|sublingual|patch|topical|transdermal') THEN 'nitrate'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'amlodipine|norvasc|diltiazem|cardizem|tiazac|verapamil|calan|isoptin|nifedipine|procardia|adalat|felodipine|plendil') THEN 'CCB'
      WHEN REGEXP_CONTAINS(LOWER(drug), r'ivabradine|corlanor') THEN 'ivabradine'
      ELSE NULL
    END AS drug_category

  FROM `physionet-data.mimiciv_3_1_hosp.prescriptions`
  WHERE (
    -- Loop diuretics
    REGEXP_CONTAINS(LOWER(drug), r'furosemide|lasix|bumetanide|bumex|torsemide|demadex')
    -- MRA
    OR REGEXP_CONTAINS(LOWER(drug), r'spironolactone|aldactone|eplerenone|inspra')
    -- Thiazide
    OR REGEXP_CONTAINS(LOWER(drug), r'hydrochlorothiazide|hctz|chlorthalidone|metolazone|zaroxolyn')
    -- ACEi
    OR REGEXP_CONTAINS(LOWER(drug), r'lisinopril|zestril|prinivil|enalapril|vasotec|ramipril|altace|captopril|capoten|benazepril|lotensin|fosinopril|monopril|quinapril|accupril|perindopril|aceon|trandolapril|mavik|moexipril|univasc')
    -- ARB
    OR REGEXP_CONTAINS(LOWER(drug), r'losartan|cozaar|valsartan|diovan|irbesartan|avapro|candesartan|atacand|olmesartan|benicar|telmisartan|micardis|azilsartan|edarbi|eprosartan|teveten')
    -- ARNI
    OR REGEXP_CONTAINS(LOWER(drug), r'sacubitril|entresto')
    -- Beta-blockers
    OR REGEXP_CONTAINS(LOWER(drug), r'carvedilol|coreg|metoprolol|lopressor|toprol|bisoprolol|zebeta|atenolol|tenormin|propranolol|inderal|labetalol|trandate|normodyne|nebivolol|bystolic|nadolol|corgard|sotalol|betapace')
    -- SGLT2i
    OR REGEXP_CONTAINS(LOWER(drug), r'empagliflozin|jardiance|dapagliflozin|farxiga|canagliflozin|invokana|ertugliflozin|steglatro')
    -- Digoxin
    OR REGEXP_CONTAINS(LOWER(drug), r'digoxin|lanoxin')
    -- Hydralazine
    OR REGEXP_CONTAINS(LOWER(drug), r'hydralazine|apresoline')
    -- Nitrates (excluding IV nitro drips — those are ICU hemodynamic management)
    OR REGEXP_CONTAINS(LOWER(drug), r'isosorbide|isordil|imdur|ismo|bidil')
    OR (REGEXP_CONTAINS(LOWER(drug), r'nitroglycerin|nitro|ntg') AND REGEXP_CONTAINS(LOWER(route), r'oral|sublingual|patch|topical|transdermal'))
    -- CCB
    OR REGEXP_CONTAINS(LOWER(drug), r'amlodipine|norvasc|diltiazem|cardizem|tiazac|verapamil|calan|isoptin|nifedipine|procardia|adalat|felodipine|plendil')
    -- Ivabradine
    OR REGEXP_CONTAINS(LOWER(drug), r'ivabradine|corlanor')
  )
),

-- Filter out rows where drug_class is NULL (false positives from broad regex)
rx_filtered AS (
  SELECT * FROM rx_all WHERE drug_class IS NOT NULL
),

-- ============================================================
-- STEP 4: IV medications from ICU inputevents
-- ============================================================
iv_meds AS (
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
      -- IV metoprolol
      WHEN itemid = 225974 THEN 'metoprolol'
      -- IV diltiazem
      WHEN itemid = 221468 THEN 'diltiazem'
      -- IV esmolol (ultra-short BB, include for completeness)
      WHEN itemid = 222056 THEN 'esmolol'
      -- IV labetalol
      WHEN itemid = 225153 THEN 'labetalol'
      -- IV enalaprilat
      WHEN itemid = 227692 THEN 'enalapril'
      -- IV digoxin
      WHEN itemid = 228339 THEN 'digoxin'
      -- IV hydralazine
      WHEN itemid = 221828 THEN 'hydralazine'
      ELSE NULL
    END AS drug_class,
    CASE
      WHEN itemid IN (221794, 228340, 221986) THEN 'loop_diuretic'
      WHEN itemid IN (225974, 222056, 225153) THEN 'beta_blocker'
      WHEN itemid = 221468 THEN 'CCB'
      WHEN itemid = 227692 THEN 'ACEi'
      WHEN itemid = 228339 THEN 'digoxin'
      WHEN itemid = 221828 THEN 'hydralazine'
      ELSE NULL
    END AS drug_category
  FROM `physionet-data.mimiciv_3_1_icu.inputevents`
  WHERE itemid IN (
    221794, 228340,  -- furosemide
    221986,          -- bumetanide
    225974,          -- metoprolol IV
    221468,          -- diltiazem IV
    222056,          -- esmolol IV
    225153,          -- labetalol IV
    227692,          -- enalaprilat IV
    228339,          -- digoxin IV
    221828           -- hydralazine IV
  )
),

iv_filtered AS (
  SELECT * FROM iv_meds WHERE drug_class IS NOT NULL
),

-- ============================================================
-- STEP 5: Union all medications
-- ============================================================
all_meds AS (
  SELECT subject_id, starttime, stoptime, drug, dose_val_rx, dose_unit_rx,
         route, drug_class, drug_category
  FROM rx_filtered
  UNION ALL
  SELECT subject_id, starttime, stoptime, drug, dose_val_rx, dose_unit_rx,
         route, drug_class, drug_category
  FROM iv_filtered
),

-- ============================================================
-- STEP 6: Match medications between echo pairs
-- ============================================================
matched AS (
  SELECT
    ep.subject_id,
    ep.pre_measurement_id,
    ep.pre_echo_time,
    ep.post_measurement_id,
    ep.post_echo_time,
    ep.days_between,
    d.drug_class,
    d.drug_category,
    d.dose_val_rx,
    d.dose_unit_rx,
    d.route,
    d.starttime AS rx_start
  FROM echo_pairs ep
  JOIN all_meds d
    ON ep.subject_id = d.subject_id
    AND CAST(d.starttime AS DATETIME) >= ep.pre_echo_time
    AND CAST(d.starttime AS DATETIME) <= ep.post_echo_time
),

-- ============================================================
-- STEP 7: Aggregate per echo pair — one row per pair
-- ============================================================
echo_pair_rx AS (
  SELECT
    subject_id,
    pre_measurement_id,
    pre_echo_time,
    post_measurement_id,
    post_echo_time,
    days_between,

    -- === Diuretics ===
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

    -- === RAAS inhibitors ===
    MAX(CASE WHEN drug_category = 'ACEi' THEN 1 ELSE 0 END) AS has_ACEi,
    MAX(CASE WHEN drug_category = 'ARB' THEN 1 ELSE 0 END) AS has_ARB,
    MAX(CASE WHEN drug_category = 'ARNI' THEN 1 ELSE 0 END) AS has_ARNI,
    -- Any RAAS blockade
    MAX(CASE WHEN drug_category IN ('ACEi', 'ARB', 'ARNI') THEN 1 ELSE 0 END) AS has_RAASi,

    -- === Beta-blockers ===
    MAX(CASE WHEN drug_category = 'beta_blocker' THEN 1 ELSE 0 END) AS has_BB,
    MAX(CASE WHEN drug_class = 'carvedilol' THEN 1 ELSE 0 END) AS has_carvedilol,
    MAX(CASE WHEN drug_class = 'metoprolol' THEN 1 ELSE 0 END) AS has_metoprolol,
    MAX(CASE WHEN drug_class = 'bisoprolol' THEN 1 ELSE 0 END) AS has_bisoprolol,

    -- === SGLT2i ===
    MAX(CASE WHEN drug_category = 'SGLT2i' THEN 1 ELSE 0 END) AS has_SGLT2i,

    -- === Other HF meds ===
    MAX(CASE WHEN drug_category = 'digoxin' THEN 1 ELSE 0 END) AS has_digoxin,
    MAX(CASE WHEN drug_category = 'hydralazine' THEN 1 ELSE 0 END) AS has_hydralazine,
    MAX(CASE WHEN drug_category = 'nitrate' THEN 1 ELSE 0 END) AS has_nitrate,
    -- H-ISDN combo (hydralazine + nitrate = BiDil equivalent)
    MAX(CASE WHEN drug_category = 'hydralazine' THEN 1 ELSE 0 END) *
    MAX(CASE WHEN drug_category = 'nitrate' THEN 1 ELSE 0 END) AS has_HISDN,

    -- === CCB ===
    MAX(CASE WHEN drug_category = 'CCB' THEN 1 ELSE 0 END) AS has_CCB,
    MAX(CASE WHEN drug_class IN ('diltiazem', 'verapamil') THEN 1 ELSE 0 END) AS has_CCB_nonDHP,
    MAX(CASE WHEN drug_class IN ('amlodipine', 'nifedipine', 'felodipine') THEN 1 ELSE 0 END) AS has_CCB_DHP,

    -- === Ivabradine ===
    MAX(CASE WHEN drug_category = 'ivabradine' THEN 1 ELSE 0 END) AS has_ivabradine,

    -- === Summary stats ===
    COUNT(*) AS total_rx_events,
    COUNT(DISTINCT drug_class) AS n_drug_classes,
    COUNT(DISTINCT drug_category) AS n_drug_categories,
    MAX(CASE WHEN route = 'IV' THEN 1 ELSE 0 END) AS has_iv,

    -- === GDMT pillar count (4-pillar HF therapy) ===
    -- Pillar 1: RAASi (ACEi/ARB/ARNI)
    -- Pillar 2: BB (evidence-based: carvedilol, metoprolol, bisoprolol)
    -- Pillar 3: MRA
    -- Pillar 4: SGLT2i
    (MAX(CASE WHEN drug_category IN ('ACEi', 'ARB', 'ARNI') THEN 1 ELSE 0 END)
     + MAX(CASE WHEN drug_category = 'beta_blocker' THEN 1 ELSE 0 END)
     + MAX(CASE WHEN drug_category = 'MRA' THEN 1 ELSE 0 END)
     + MAX(CASE WHEN drug_category = 'SGLT2i' THEN 1 ELSE 0 END)
    ) AS gdmt_pillar_count,

    -- === Specific drug lists (for detailed analysis) ===
    STRING_AGG(DISTINCT drug_class, ', ' ORDER BY drug_class) AS drug_list,
    STRING_AGG(DISTINCT drug_category, ', ' ORDER BY drug_category) AS category_list

  FROM matched
  GROUP BY subject_id, pre_measurement_id, pre_echo_time,
           post_measurement_id, post_echo_time, days_between
),

-- ============================================================
-- STEP 8: Control group (no HF medications between echos)
-- ============================================================
no_rx_pairs AS (
  SELECT
    ep.subject_id,
    ep.pre_measurement_id,
    ep.pre_echo_time,
    ep.post_measurement_id,
    ep.post_echo_time,
    ep.days_between,
    -- All flags = 0
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
      AND CAST(d.starttime AS DATETIME) >= ep.pre_echo_time
      AND CAST(d.starttime AS DATETIME) <= ep.post_echo_time
  )
)

-- ============================================================
-- FINAL: All echo pairs + comprehensive medication exposure
-- pre/post measurement_id → Python에서 v2 PINN data와 바로 조인
-- ============================================================
SELECT * FROM echo_pair_rx
UNION ALL
SELECT * FROM no_rx_pairs
ORDER BY subject_id, pre_echo_time;
