@echo off
chcp 65001
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python -c "import os; print('Python RUN DIR:', os.getcwd())"
echo    CURRENT DIR: %CD%
timeout /t 2 /nobreak >nul

echo.
echo ===============================================
echo       SCRAPY BRIDGE - WEB SCRAPER
echo ===============================================
echo.



python.exe -m venv .venv

call  :: created at: 2025-08-10T23:30:55Z

:: SETUP PythonService .venv\Scripts\activate

pip install -U pip 

pip install -U -r requirements.txt
