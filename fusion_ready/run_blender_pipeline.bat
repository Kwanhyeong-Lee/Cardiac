@echo off
REM Runs blender_pipeline.py headless with the Blender installed on this Windows machine.
REM Double-click, or run from cmd. Output lands in BLENDER_OUT\ next to this file.
setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "BL="
where blender >nul 2>&1 && set "BL=blender"
if not defined BL (
  for /d %%D in ("%ProgramFiles%\Blender Foundation\Blender*") do (
    if exist "%%D\blender.exe" set "BL=%%D\blender.exe"
  )
)
if not defined BL (
  for /d %%D in ("%LocalAppData%\Programs\Blender Foundation\Blender*") do (
    if exist "%%D\blender.exe" set "BL=%%D\blender.exe"
  )
)
if not defined BL (
  for /d %%D in ("%ProgramFiles%\WindowsApps\BlenderFoundation.Blender*") do (
    if exist "%%D\Blender\blender.exe" set "BL=%%D\Blender\blender.exe"
  )
)
if not defined BL (
  echo blender.exe not found. Edit this file and set BL to the full path, e.g.
  echo   set "BL=C:\Program Files\Blender Foundation\Blender 4.2\blender.exe"
  pause & exit /b 1
)

echo using: "%BL%"
if not exist BLENDER_OUT mkdir BLENDER_OUT
"%BL%" --background --python "%~dp0blender_pipeline.py" > "BLENDER_OUT\run.log" 2>&1
set "RC=%ERRORLEVEL%"
type "BLENDER_OUT\run.log"
echo.
echo exit code %RC%   (report: BLENDER_OUT\blender_report.json)
pause
