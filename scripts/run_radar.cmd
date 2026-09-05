@echo off
REM Nightly Boring Business Acquisition Radar run (BizBuySell ingest -> packets + Telegram).
REM Invoked by the Windows Task Scheduler task "BoringBusinessRadar" (wake-to-run).
REM Paths derive from this script's own location so the task survives user/dir renames.
set "PROJ=%~dp0.."
cd /d "%PROJ%"
set PYTHONUTF8=1
if not exist "%PROJ%\logs" mkdir "%PROJ%\logs"
echo ================ %DATE% %TIME% ================ >> "%PROJ%\logs\radar.log"
"%LOCALAPPDATA%\Programs\Python\Python312\python.exe" -m src.ingest_bizbuysell >> "%PROJ%\logs\radar.log" 2>&1
echo exit=%ERRORLEVEL% >> "%PROJ%\logs\radar.log"
