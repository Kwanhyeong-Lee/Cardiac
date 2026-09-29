<#
.SYNOPSIS
  Build the transfer folder for the RTX 3060 machine on an external drive.  Run on the WORK computer (alex0),
  in Windows PowerShell -- not WSL: only native Windows reliably downloads OneDrive "cloud-only" files on read.

.DESCRIPTION
  What git cannot carry, and therefore goes on the drive:
    geometry\  sync_assets_2026-09-17.zip  (402 MB)  case-1009 meshes: prints, Unreal pack source.  MM-WHS-derived:
               for your own machines only, never redistributed.
    mmwhs\     ct_train\ct_train_*.nii.gz  (20 images + 20 labels)  the raw CT for the geometry pipeline.
               Research licence: your own machines only.
    patient\   ONLY with -IncludePatientData and explicit paths.  PhysioNet-credentialed data (MIMIC, eICU,
               INSPIRE ...): allowed on the credentialed user's own secure machines, nowhere else.  Use an
               encrypted drive (BitLocker To Go) and never copy it into the repository or any cloud folder.
  Writes SHA256SUMS.txt in `sha256sum -c` format so unpack_transfer.sh can verify every byte on the other side.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File tools\setup\make_transfer.ps1 -Drive E:\
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File tools\setup\make_transfer.ps1 -Drive E:\ -IncludePatientData -PatientDataPaths "D:\data\waveform_csv"
#>
param(
    [Parameter(Mandatory = $true)][string]$Drive,
    [switch]$SkipMMWHS,
    [switch]$SkipGeometry,
    [switch]$IncludePatientData,
    [string[]]$PatientDataPaths = @()
)
$ErrorActionPreference = "Stop"
# ASCII-only on purpose: Windows PowerShell 5.1 reads BOM-less scripts in the ANSI code page, which would mangle the
# Korean project-folder name.  The folder is found by wildcard instead of being spelled out.
$od = $env:OneDrive
if (-not $od) { throw "OneDrive is not configured on this machine (env:OneDrive is empty)" }
$proj = Get-ChildItem -LiteralPath (Join-Path $od "PINN") -Directory | Where-Object { $_.Name -like "260421*main" } | Select-Object -First 1
if (-not $proj) { throw "project folder PINN\260421*main not found under $od" }
$assets = Join-Path $proj.FullName "_handover\sync_2026-09-17\sync_assets_2026-09-17.zip"
$mmwhs  = Join-Path $od "PINN heart\MM-WHS\ct_train"
$dst    = Join-Path $Drive ("cardiac_transfer_" + (Get-Date -Format "yyyy-MM-dd"))

Write-Host "project : $($proj.FullName)"
Write-Host "target  : $dst"
New-Item -ItemType Directory -Force -Path $dst | Out-Null

function Copy-Tree($src, $to, $pattern) {
    New-Item -ItemType Directory -Force -Path $to | Out-Null
    # robocopy reads through the Windows filesystem, so OneDrive placeholders are downloaded as they are copied.
    robocopy $src $to $pattern /E /NFL /NDL /NJH /NP /R:2 /W:5 | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy $src -> $to failed (exit $LASTEXITCODE)" }
}

if (-not $SkipGeometry) {
    if (-not (Test-Path -LiteralPath $assets)) { throw "assets zip not found: $assets" }
    New-Item -ItemType Directory -Force -Path (Join-Path $dst "geometry") | Out-Null
    Write-Host "copying geometry assets (402 MB) ..."
    Copy-Item -LiteralPath $assets -Destination (Join-Path $dst "geometry") -Force
}
if (-not $SkipMMWHS) {
    if (-not (Test-Path -LiteralPath $mmwhs)) { throw "MM-WHS ct_train not found: $mmwhs" }
    Write-Host "copying MM-WHS ct_train (downloads cloud-only files first; tip: right-click the folder > Always keep on this device) ..."
    Copy-Tree $mmwhs (Join-Path $dst "mmwhs\ct_train") "ct_train_*.nii.gz"
    $n = (Get-ChildItem -LiteralPath (Join-Path $dst "mmwhs\ct_train") -Filter "*.nii.gz").Count
    if ($n -ne 40) { Write-Warning "expected 40 files (20 images + 20 labels), got $n" }
}
if ($IncludePatientData) {
    if ($PatientDataPaths.Count -eq 0) { throw "-IncludePatientData needs -PatientDataPaths (explicit folders; nothing is guessed)" }
    Write-Warning "PATIENT-LEVEL DATA: PhysioNet DUA -- your own secure machines only, encrypted drive, never into git or a cloud folder."
    foreach ($p in $PatientDataPaths) {
        $leaf = Split-Path $p -Leaf
        Write-Host "copying patient data: $p"
        Copy-Tree $p (Join-Path $dst "patient\$leaf") "*"
    }
}

Write-Host "hashing (sha256) ..."
$files = Get-ChildItem -LiteralPath $dst -Recurse -File | Where-Object { $_.Name -ne "SHA256SUMS.txt" -and $_.Name -ne "README.txt" }
$lines = foreach ($f in $files) {
    $h = (Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash.ToLower()
    $rel = $f.FullName.Substring($dst.Length).TrimStart('\').Replace('\', '/')
    "$h  $rel"
}
[IO.File]::WriteAllLines((Join-Path $dst "SHA256SUMS.txt"), [string[]]$lines)

$sizeGB = [math]::Round((($files | Measure-Object Length -Sum).Sum) / 1GB, 2)
$readme = @(
    "cardiac transfer $(Get-Date -Format s) from $env:COMPUTERNAME",
    "geometry/  case-1009 meshes (MM-WHS-derived; own machines only)",
    "mmwhs/     MM-WHS ct_train (research licence; own machines only)",
    "patient/   present only if you asked for it: PhysioNet DUA applies",
    "On the RTX 3060 machine, in WSL, from the repo root:",
    "    bash tools/setup/unpack_transfer.sh /mnt/<drive letter>/$(Split-Path $dst -Leaf) --unreal",
    "$($files.Count) files, $sizeGB GB"
)
[IO.File]::WriteAllLines((Join-Path $dst "README.txt"), [string[]]$readme)
Write-Host "done: $($files.Count) files, $sizeGB GB -> $dst"
if ($IncludePatientData) { Write-Warning "the drive now holds patient-level data: keep it encrypted and wipe it after unpacking" }
