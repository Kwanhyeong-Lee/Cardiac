-- ================================================================
-- pH-PINN v5 External Validation: eICU Hemodynamic Extraction
-- 스키마 전수검증 완료 (2026-06-14)
-- ================================================================
-- 전략: Swan-Ganz 실측 CO + vitals로 hemodynamic cross-validation
-- eICU에 에코(EF/EDV/ESV) 없음 → 혈역학 물리 일관성 검증으로 전환

WITH hemodynamics AS (
    -- vitalaperiodic: Swan-Ganz 실측 CO, CI, SVR, PAOP
    SELECT
        patientunitstayid,
        observationoffset,
        cardiacoutput   AS co,
        cardiacinput    AS ci,
        svr,
        CAST(svri AS FLOAT64) AS svri,
        paop
    FROM `physionet-data.eicu_crd.vitalaperiodic`
    WHERE cardiacoutput IS NOT NULL
      AND cardiacoutput BETWEEN 1.0 AND 15.0
),

vitals AS (
    -- vitalperiodic: SBP, DBP, HR
    SELECT
        patientunitstayid,
        observationoffset,
        systemicsystolic  AS sbp,
        systemicdiastolic AS dbp,
        heartrate         AS hr
    FROM `physionet-data.eicu_crd.vitalperiodic`
    WHERE systemicsystolic  BETWEEN 60  AND 250
      AND systemicdiastolic BETWEEN 30  AND 150
      AND heartrate         BETWEEN 30  AND 200
),

-- 같은 환자의 hemodynamics + vitals 매칭 (±60분 이내)
matched AS (
    SELECT
        h.patientunitstayid,
        h.observationoffset AS hemo_offset,
        v.observationoffset AS vital_offset,
        h.co, h.ci, h.svr, h.svri, h.paop,
        v.sbp, v.dbp, v.hr,
        ROW_NUMBER() OVER (
            PARTITION BY h.patientunitstayid, h.observationoffset
            ORDER BY ABS(h.observationoffset - v.observationoffset)
        ) AS rn
    FROM hemodynamics h
    JOIN vitals v
      ON h.patientunitstayid = v.patientunitstayid
      AND ABS(h.observationoffset - v.observationoffset) <= 60
),

closest AS (
    SELECT * FROM matched WHERE rn = 1
),

-- 환자별 첫 24시간 평균
patient_avg AS (
    SELECT
        patientunitstayid,
        AVG(co)   AS co,
        AVG(ci)   AS ci,
        AVG(svr)  AS svr,
        AVG(svri) AS svri,
        AVG(paop) AS paop,
        AVG(sbp)  AS sbp,
        AVG(dbp)  AS dbp,
        AVG(hr)   AS hr,
        COUNT(*)  AS n_measurements
    FROM closest
    WHERE hemo_offset BETWEEN 0 AND 1440
    GROUP BY patientunitstayid
    HAVING COUNT(*) >= 3
),

patients AS (
    SELECT patientunitstayid, uniquepid, hospitalid,
           age, gender, unitdischargestatus
    FROM `physionet-data.eicu_crd.patient`
),

-- BNP, Troponin도 있으면 같이 가져오기
biomarkers AS (
    SELECT
        patientunitstayid,
        MAX(CASE WHEN labname = 'BNP' THEN labresult END) AS bnp,
        MAX(CASE WHEN labname = 'troponin - I' THEN labresult END) AS troponin_i,
        MAX(CASE WHEN labname = 'troponin - T' THEN labresult END) AS troponin_t
    FROM `physionet-data.eicu_crd.lab`
    WHERE labname IN ('BNP', 'troponin - I', 'troponin - T')
      AND labresultoffset BETWEEN -360 AND 1440
    GROUP BY patientunitstayid
)

SELECT
    pa.patientunitstayid,
    p.uniquepid, p.hospitalid, p.age, p.gender, p.unitdischargestatus,
    pa.n_measurements,

    -- Raw hemodynamics (Swan-Ganz measured)
    ROUND(pa.co, 2)   AS measured_CO,
    ROUND(pa.ci, 2)   AS measured_CI,
    ROUND(pa.svr, 0)  AS measured_SVR,
    ROUND(pa.svri, 0) AS measured_SVRI,
    ROUND(pa.paop, 1) AS measured_PAOP,

    -- Vitals
    ROUND(pa.sbp, 1) AS sbp,
    ROUND(pa.dbp, 1) AS dbp,
    ROUND(pa.hr, 1)  AS hr,

    -- Derived hemodynamics (physics formulas — same as pH-PINN)
    ROUND(pa.co * 1000.0 / pa.hr, 1)                          AS derived_SV,
    ROUND(0.9 * pa.sbp / (pa.co * 1000.0 / pa.hr), 4)         AS derived_Ea,
    ROUND(0.9 * pa.sbp * (pa.co * 1000.0 / pa.hr) * 0.0133322, 2)  AS derived_SW_J,
    ROUND((pa.sbp - pa.dbp) / 3.0 + pa.dbp, 1)                AS derived_MAP,
    ROUND(80.0 * ((pa.sbp - pa.dbp) / 3.0 + pa.dbp) / pa.co, 0)  AS computed_SVR,

    -- Biomarkers (if available)
    ROUND(b.bnp, 1)        AS bnp,
    ROUND(b.troponin_i, 3) AS troponin_i,
    ROUND(b.troponin_t, 3) AS troponin_t

FROM patient_avg pa
JOIN patients p USING (patientunitstayid)
LEFT JOIN biomarkers b USING (patientunitstayid)
ORDER BY pa.patientunitstayid;
