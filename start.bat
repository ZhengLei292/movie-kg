@echo off
cd /d "%~dp0"
set PYTHONUTF8=1
if not exist ".venv\Scripts\python.exe" (
  python -m venv .venv
  if errorlevel 1 goto fail
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 goto fail
)
".venv\Scripts\python.exe" scripts\manage.py start
if errorlevel 1 goto fail
exit /b 0
:fail
echo Startup failed. See the error above and logs folder.
pause
exit /b 1

