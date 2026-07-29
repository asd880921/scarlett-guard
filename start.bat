@echo off
REM 以系統管理員權限啟動 Scarlett Guard。
REM 重置 PnP 裝置需要提權，未提權時程式仍可開啟，但重置按鈕會停用。
setlocal
set "ROOT=%~dp0"
set "PYW=%ROOT%.venv\Scripts\pythonw.exe"

if not exist "%PYW%" (
  echo 找不到虛擬環境，請先執行：
  echo   py -m venv .venv
  echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
  pause
  exit /b 1
)

powershell -NoProfile -Command "Start-Process -FilePath '%PYW%' -ArgumentList '\"%ROOT%run.py\"' -Verb RunAs"
endlocal
