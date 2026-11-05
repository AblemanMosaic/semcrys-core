@echo off
setlocal
cd /d "%~dp0"
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONPATH=%CD%\src"
python -B -m semcrys --help
if errorlevel 1 pause

