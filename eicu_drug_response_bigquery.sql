-- ================================================================
-- eICU Phase 3: Drug Response Pattern Validation
-- Swan-Ganz hemodynamic 환자의 vasopressor/inotrope 투여 추출
-- pH-PINN δH(drug) perturbation 검증용
-- ================================================================
-- 전략: 기존 hemodynamic 3,991명에서 약물 투여 전/후 혈역학 변화 분석
-- eICU infusiondrug: 지속 정맥주사 (vasopressors, inotropes)
-- 단위 보정: mmHg·mL → J 는 0.000133322 (정확한 물리 단위)

-- ===============================================
-- PART A: IV Vasopressors/Inotropes (infusiondrug)
-- ===============================================
WITH hemo_patients AS (
    SELECT DISTINCT patientunitstayid
    FROM `physionet-data.eicu_crd.vitalaperiodic`
    WHERE cardiacoutput IS NOT NULL
      AND cardiacoutput BETWEEN 1.0 AND 15.0
),

iv_drugs AS (
    SELECT
        i.patientunitstayid,
        i.infusionoffset,
        LOWER(i.drugname) AS drugname,
        SAFE_CAST(i.drugrate AS FLOAT64) AS drugrate,
        SAFE_CAST(i.infusionrate AS FLOAT64) AS infusionrate,
        SAFE_CAST(i.drugamount AS FLOAT64) AS drugamount,
        CASE
            WHEN LOWER(i.drugname) LIKE '%norepinephrine%' OR LOWER(i.drugname) LIKE '%levophed%'
                THEN 'norepinephrine'
            WHEN LOWER(i.drugname) LIKE '%epinephrine%' AND LOWER(i.drugname) NOT LIKE '%norepinephrine%'
                THEN 'epinephrine'
            WHEN LOWER(i.drugname) LIKE '%dopamine%'
                THEN 'dopamine'
            WHEN LOWER(i.drugname) LIKE '%dobutamine%'
                THEN 'dobutamine'
            WHEN LOWER(i.drugname) LIKE '%vasopressin%'
                THEN 'vasopressin'
            WHEN LOWER(i.drugname) LIKE '%phenylephrine%' OR LOWER(i.drugname) LIKE '%neosynephrine%'
                THEN 'phenylephrine'
            WHEN LOWER(i.drugname) LIKE '%milrinone%' OR LOWER(i.drugname) LIKE '%primacor%'
                THEN 'milrinone'
            WHEN LOWER(i.drugname) LIKE '%nitroglycerin%' OR LOWER(i.drugname) LIKE '%ntg%'
                THEN 'nitroglycerin'
            WHEN LOWER(i.drugname) LIKE '%nitroprusside%' OR LOWER(i.drugname) LIKE '%nipride%'
                THEN 'nitroprusside'
            ELSE NULL
        END AS drug_class,
        CASE
            WHEN LOWER(i.drugname) LIKE '%norepinephrine%' OR LOWER(i.drugname) LIKE '%levophed%'
                OR LOWER(i.drugname) LIKE '%phenylephrine%' OR LOWER(i.drugname) LIKE '%neosynephrine%'
                OR LOWER(i.drugname) LIKE '%vasopressin%'
                THEN 'vasopressor'
            WHEN LOWER(i.drugname) LIKE '%dobutamine%'
                OR LOWER(i.drugname) LIKE '%milrinone%' OR LOWER(i.drugname) LIKE '%primacor%'
                THEN 'inotrope'
            WHEN LOWER(i.drugname) LIKE '%dopamine%'
                THEN 'vasopressor_inotrope'
            WHEN LOWER(i.drugname) LIKE '%epinephrine%' AND LOWER(i.drugname) NOT LIKE '%norepinephrine%'
                THEN 'vasopressor_inotrope'
            WHEN LOWER(i.drugname) LIKE '%nitroglycerin%' OR LOWER(i.drugname) LIKE '%ntg%'
                OR LOWER(i.drugname) LIKE '%nitroprusside%' OR LOWER(i.drugname) LIKE '%nipride%'
                THEN 'vasodilator'
            ELSE NULL
        END AS mechanism
    FROM `physionet-data.eicu_crd.infusiondrug` i
    JOIN hemo_patients h USING (patientunitstayid)
    WHERE i.drugrate IS NOT NULL
      AND SAFE_CAST(i.drugrate AS FLOAT64) > 0
),

drug_episodes AS (
    SELECT
        patientunitstayid,
        drug_class,
        mechanism,
        MIN(infusionoffset) AS first_infusion_offset,
        MAX(infusionoffset) AS last_infusion_offset,
        COUNT(*) AS n_records,
        AVG(drugrate) AS avg_rate,
        MAX(drugrate) AS max_rate
    FROM iv_drugs
    WHERE drug_class IS NOT NULL
    GROUP BY patientunitstayid, drug_class, mechanism
),

-- ===============================================
-- PART B: 약물 투여 전/후 혈역학 변화
-- ===============================================
hemodynamics_raw AS (
    SELECT
        h.patientunitstayid,
        h.observationoffset,
        h.cardiacoutput AS co,
        h.svr,
        h.paop,
        v.systemicsystolic AS sbp,
        v.systemicdiastolic AS dbp,
        v.heartrate AS hr,
        ROW_NUMBER() OVER (
            PARTITION BY h.patientunitstayid, h.observationoffset
            ORDER BY ABS(h.observationoffset - v.observationoffset)
        ) AS rn
    FROM `physionet-data.eicu_crd.vitalaperiodic` h
    JOIN `physionet-data.eicu_crd.vitalperiodic` v
        ON h.patientunitstayid = v.patientunitstayid
        AND ABS(h.observationoffset - v.observationoffset) <= 30
    WHERE h.cardiacoutput IS NOT NULL
      AND h.cardiacoutput BETWEEN 1.0 AND 15.0
      AND v.systemicsystolic BETWEEN 60 AND 250
      AND v.systemicdiastolic BETWEEN 30 AND 150
      AND v.heartrate BETWEEN 30 AND 200
),

hemo_clean AS (
    SELECT * FROM hemodynamics_raw WHERE rn = 1
),

-- Pre-drug: 약물 시작 전 120분 이내 가장 가까운 측정
-- Post-drug: 약물 시작 후 120~360분 (2~6시간) 첫 측정
pre_drug AS (
    SELECT
        de.patientunitstayid,
        de.drug_class,
        de.mechanism,
        de.avg_rate,
        de.max_rate,
        de.n_records,
        de.first_infusion_offset,
        hc.co AS pre_co, hc.sbp AS pre_sbp, hc.dbp AS pre_dbp,
        hc.hr AS pre_hr, hc.svr AS pre_svr, hc.paop AS pre_paop,
        hc.observationoffset AS pre_offset,
        ROW_NUMBER() OVER (
            PARTITION BY de.patientunitstayid, de.drug_class
            ORDER BY ABS(hc.observationoffset - de.first_infusion_offset) ASC
        ) AS rn_pre
    FROM drug_episodes de
    JOIN hemo_clean hc
        ON hc.patientunitstayid = de.patientunitstayid
        AND hc.observationoffset BETWEEN (de.first_infusion_offset - 120) AND de.first_infusion_offset
),

post_drug AS (
    SELECT
        de.patientunitstayid,
        de.drug_class,
        hc.co AS post_co, hc.sbp AS post_sbp, hc.dbp AS post_dbp,
        hc.hr AS post_hr, hc.svr AS post_svr, hc.paop AS post_paop,
        hc.observationoffset AS post_offset,
        ROW_NUMBER() OVER (
            PARTITION BY de.patientunitstayid, de.drug_class
            ORDER BY hc.observationoffset ASC
        ) AS rn_post
    FROM drug_episodes de
    JOIN hemo_clean hc
        ON hc.patientunitstayid = de.patientunitstayid
        AND hc.observationoffset BETWEEN (de.first_infusion_offset + 120) AND (de.first_infusion_offset + 360)
),

drug_response AS (
    SELECT
        pre.patientunitstayid,
        pre.drug_class,
        pre.mechanism,
        pre.avg_rate,
        pre.max_rate,
        pre.n_records,
        pre.first_infusion_offset,
        pre.pre_co, pre.pre_sbp, pre.pre_dbp, pre.pre_hr, pre.pre_svr, pre.pre_paop,
        post.post_co, post.post_sbp, post.post_dbp, post.post_hr, post.post_svr, post.post_paop,
        ROUND(post.post_co - pre.pre_co, 2) AS delta_co,
        ROUND(post.post_sbp - pre.pre_sbp, 1) AS delta_sbp,
        ROUND(post.post_hr - pre.pre_hr, 1) AS delta_hr,
        ROUND(post.post_svr - pre.pre_svr, 0) AS delta_svr
    FROM pre_drug pre
    JOIN post_drug post
        ON pre.patientunitstayid = post.patientunitstayid
        AND pre.drug_class = post.drug_class
    WHERE pre.rn_pre = 1 AND post.rn_post = 1
),

patients AS (
    SELECT patientunitstayid, unitdischargestatus, age, gender
    FROM `physionet-data.eicu_crd.patient`
)

SELECT
    dr.*,
    p.unitdischargestatus,
    p.age,
    p.gender,

    -- Energy metrics (pre) — correct unit: 0.000133322 J per mmHg·mL
    ROUND(0.9 * dr.pre_sbp * (dr.pre_co * 1000.0 / dr.pre_hr) * 0.000133322, 4) AS pre_SW_J,
    ROUND(0.9 * dr.pre_sbp / (dr.pre_co * 1000.0 / dr.pre_hr), 4) AS pre_Ea,
    ROUND(0.9 * dr.pre_sbp * (dr.pre_co * 1000.0 / dr.pre_hr) * 0.000133322 * dr.pre_hr / 60, 4) AS pre_CPO_W,

    -- Energy metrics (post)
    ROUND(0.9 * dr.post_sbp * (dr.post_co * 1000.0 / dr.post_hr) * 0.000133322, 4) AS post_SW_J,
    ROUND(0.9 * dr.post_sbp / (dr.post_co * 1000.0 / dr.post_hr), 4) AS post_Ea,
    ROUND(0.9 * dr.post_sbp * (dr.post_co * 1000.0 / dr.post_hr) * 0.000133322 * dr.post_hr / 60, 4) AS post_CPO_W,

    -- Energy deltas
    ROUND(
        0.9 * dr.post_sbp * (dr.post_co * 1000.0 / dr.post_hr) * 0.000133322
      - 0.9 * dr.pre_sbp * (dr.pre_co * 1000.0 / dr.pre_hr) * 0.000133322
    , 4) AS delta_SW_J,
    ROUND(
        0.9 * dr.post_sbp * (dr.post_co * 1000.0 / dr.post_hr) * 0.000133322 * dr.post_hr / 60
      - 0.9 * dr.pre_sbp * (dr.pre_co * 1000.0 / dr.pre_hr) * 0.000133322 * dr.pre_hr / 60
    , 4) AS delta_CPO_W

FROM drug_response dr
JOIN patients p USING (patientunitstayid)
ORDER BY dr.drug_class, dr.patientunitstayid;
