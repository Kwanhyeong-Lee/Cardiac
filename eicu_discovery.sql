-- ================================================================
-- eICU-CRD: 심장/에코 데이터 전수조사 (스키마 검증 완료)
-- ================================================================

-- ① customlab (labothername / labotherresult)
SELECT 'customlab' AS tbl, labothername AS field, COUNT(*) AS cnt,
    ROUND(AVG(labotherresult),2) AS mean_v,
    ROUND(MIN(labotherresult),2) AS min_v,
    ROUND(MAX(labotherresult),2) AS max_v
FROM `physionet-data.eicu_crd.customlab`
WHERE LOWER(labothername) LIKE ANY (
    '%ejection%','%lvef%','%ef %','%ef(%',
    '%edv%','%esv%','%lvedv%','%lvesv%',
    '%end diastolic%','%end systolic%',
    '%e/e%','%e prime%','%e-prime%',
    '%lavi%','%la vol%','%left atrial%',
    '%e/a%','%mitral%','%decel%',
    '%cardiac output%','%cardiac index%',
    '%stroke vol%','%echo%',
    '%rvsp%','%pasp%','%tapse%','%lv mass%'
)
GROUP BY labothername

UNION ALL

-- ② lab (labname / labresult)
SELECT 'lab', labname, COUNT(*),
    ROUND(AVG(labresult),2),
    ROUND(MIN(labresult),2),
    ROUND(MAX(labresult),2)
FROM `physionet-data.eicu_crd.lab`
WHERE LOWER(labname) LIKE ANY (
    '%ejection%','%cardiac%','%stroke%',
    '%bnp%','%troponin%','%nt-pro%','%ntpro%',
    '%cpk%','%ck-mb%','%ckmb%','%creatine kinase%'
)
GROUP BY labname

UNION ALL

-- ③ vitalaperiodic (직접 컬럼 — cardiacoutput, cardiacinput, svr, svri, pvr, pvri, paop)
SELECT 'vitalaperiodic', col, cnt, mean_v, min_v, max_v FROM (
    SELECT 'cardiacoutput' AS col, COUNT(*) AS cnt,
        ROUND(AVG(cardiacoutput),2) AS mean_v, ROUND(MIN(cardiacoutput),2) AS min_v, ROUND(MAX(cardiacoutput),2) AS max_v
    FROM `physionet-data.eicu_crd.vitalaperiodic` WHERE cardiacoutput IS NOT NULL
    UNION ALL
    SELECT 'cardiacinput', COUNT(*), ROUND(AVG(cardiacinput),2), ROUND(MIN(cardiacinput),2), ROUND(MAX(cardiacinput),2)
    FROM `physionet-data.eicu_crd.vitalaperiodic` WHERE cardiacinput IS NOT NULL
    UNION ALL
    SELECT 'paop', COUNT(*), ROUND(AVG(paop),2), ROUND(MIN(paop),2), ROUND(MAX(paop),2)
    FROM `physionet-data.eicu_crd.vitalaperiodic` WHERE paop IS NOT NULL
    UNION ALL
    SELECT 'svr', COUNT(*), ROUND(AVG(svr),2), ROUND(MIN(svr),2), ROUND(MAX(svr),2)
    FROM `physionet-data.eicu_crd.vitalaperiodic` WHERE svr IS NOT NULL
    UNION ALL
    SELECT 'svri', COUNT(*), ROUND(AVG(svri),2), ROUND(MIN(svri),2), ROUND(MAX(svri),2)
    FROM `physionet-data.eicu_crd.vitalaperiodic` WHERE svri IS NOT NULL
)

UNION ALL

-- ④ nursecharting (nursingchartcelltypevallabel / nursingchartvalue) — 넓은 cardiac 스캔
SELECT 'nursecharting', nursingchartcelltypevallabel, COUNT(*),
    ROUND(AVG(SAFE_CAST(nursingchartvalue AS FLOAT64)),2),
    ROUND(MIN(SAFE_CAST(nursingchartvalue AS FLOAT64)),2),
    ROUND(MAX(SAFE_CAST(nursingchartvalue AS FLOAT64)),2)
FROM `physionet-data.eicu_crd.nursecharting`
WHERE LOWER(nursingchartcelltypevallabel) LIKE ANY (
    '%ejection%','%cardiac output%','%stroke vol%',
    '%echo%','%edv%','%esv%','%lv %'
)
AND SAFE_CAST(nursingchartvalue AS FLOAT64) IS NOT NULL
GROUP BY nursingchartcelltypevallabel

UNION ALL

-- ⑤ physicalexam (physicalexampath / physicalexamvalue)
SELECT 'physicalexam', physicalexampath, COUNT(*),
    NULL, NULL, NULL
FROM `physionet-data.eicu_crd.physicalexam`
WHERE LOWER(physicalexampath) LIKE ANY (
    '%ejection%','%echo%','%cardiac%','%heart%','%edv%','%esv%'
)
GROUP BY physicalexampath

ORDER BY tbl, cnt DESC;
