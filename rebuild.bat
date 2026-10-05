@echo off
cd /d "%~dp0"
set PYTHONUTF8=1
".venv\Scripts\python.exe" scripts\manage.py rebuild
if errorlevel 1 pause

