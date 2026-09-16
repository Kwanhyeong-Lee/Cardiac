<#
  ECG 통합 파이프라인 오케스트레이터 (Windows PowerShell)
  사용: 프로젝트 폴더의 ecg_integration/ 에서
        powershell -ExecutionPolicy Bypass -File .\run_ecg_pipeline.ps1 [-Stage all|0|1|2|3|4]
  전제: config.json 의 paths 채움(특히 ecg_root = MIMIC-IV-ECG pull 폴더).
#>
param([string]$Stage = "all")

$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Here

# python 탐색
$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { $py = (Get-Command py -ErrorAction SilentlyContinue).Source }
if (-not $py) { Write-Error "python 없음. Python 3.10+ 설치 필요."; exit 1 }
Write-Host "python: $py"

function Run-Stage($script, $label) {
  Write-Host "`n===== $label =====" -ForegroundColor Cyan
  & $py $script
  if ($LASTEXITCODE -ne 0) { Write-Error "$label 실패(exit $LASTEXITCODE)"; exit $LASTEXITCODE }
}

switch ($Stage) {
  "0" { Run-Stage "00_env_check.py" "Stage 0 환경점검" }
  "1" { Run-Stage "01_link_cohort.py" "Stage 1 코호트 링크" }
  "2" { Run-Stage "02_extract_ecg_features.py" "Stage 2 ECG 지표추출" }
  "3" { Run-Stage "03_merge_and_qc.py" "Stage 3 병합/QC" }
  "4" { Run-Stage "04_ablation_identifiability.py" "Stage 4 식별성 ablation" }
  default {
    Run-Stage "00_env_check.py" "Stage 0 환경점검"
    Run-Stage "01_link_cohort.py" "Stage 1 코호트 링크"
    Run-Stage "02_extract_ecg_features.py" "Stage 2 ECG 지표추출"
    Run-Stage "03_merge_and_qc.py" "Stage 3 병합/QC"
    Run-Stage "04_ablation_identifiability.py" "Stage 4 식별성 ablation"
  }
}
Write-Host "`n완료. 산출물: config.json paths.out_dir" -ForegroundColor Green
