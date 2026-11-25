@echo off
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 (set "PY=python") else (set "PY=py -3")
if not exist .venv\Scripts\python.exe %PY% -m venv .venv
if errorlevel 1 goto error
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto error
.venv\Scripts\python.exe tvrtk_scraper.py
if errorlevel 1 goto error
exit /b 0
:error
echo Pokretanje nije uspjelo. Provjerite instalaciju Python 3.10+ i mrezu.
pause
exit /b 1
