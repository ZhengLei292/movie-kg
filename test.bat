@echo off
cd /d "%~dp0"
set PYTHONUTF8=1
".venv\Scripts\python.exe" -m scripts.test_cleaning
if errorlevel 1 goto done
".venv\Scripts\python.exe" scripts\test_system.py
:done
pause
