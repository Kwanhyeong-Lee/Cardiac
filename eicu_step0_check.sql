-- ================================================================
-- STEP 0: 테이블 접근 확인 + 에코 label 탐색
-- 이것부터 돌려서 결과 알려주세요
-- ================================================================

-- 먼저 테이블 목록 확인
SELECT table_name
FROM `physionet-data.eicu_crd.INFORMATION_SCHEMA.TABLES`
ORDER BY table_name;
