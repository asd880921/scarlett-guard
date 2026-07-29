@echo off
REM Launch Scarlett Guard with administrator rights.
REM Resetting a PnP device requires elevation. Without it the app still opens,
REM but the reset button stays disabled.
REM
REM NOTE: keep this file pure ASCII. cmd.exe reads batch files using the system
REM OEM code page, so non-ASCII bytes get mis-decoded and break parsing.
setlocal
set "ROOT=%~dp0"
set "PYW=%ROOT%.venv\Scripts\pythonw.exe"

if not exist "%PYW%" (
  echo [ERROR] Virtual environment not found:
  echo   %PYW%
  echo.
  echo Create it first:
  echo   py -m venv .venv
  echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
  echo.
  pause
  exit /b 1
)

REM Pass the directory via -WorkingDirectory and keep the argument a bare
REM filename, so no nested quote escaping is needed. PowerShell single-quoted
REM strings do not honour \" escapes -- writing them makes Python receive a
REM broken path and fail silently under pythonw.exe.
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Start-Process -FilePath '%PYW%' -ArgumentList 'run.py' -WorkingDirectory '%ROOT%' -Verb RunAs -ErrorAction Stop } catch { Write-Host ('Launch failed: ' + $_.Exception.Message) -ForegroundColor Red; exit 1 }"

if errorlevel 1 (
  echo.
  echo If you dismissed the UAC prompt, that is expected.
  echo To run without elevation ^(reset will be disabled^):
  echo   .venv\Scripts\python.exe run.py
  echo.
  pause
  exit /b 1
)

endlocal
