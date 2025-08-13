@echo off
chcp 65001
cd /d "%~dp0"
echo    CURRENT DIR: %CD%
timeout /t 2 /nobreak >nul

echo.
echo ===============================================
echo       SCRAPY BRIDGE - WEB SCRAPER
echo ===============================================
echo.



python.exe -m venv .venv

call .venv\Scripts\activate
echo.
echo    CURRENT DIR: %CD%
echo.
python.exe -m pip -V
echo.
echo.
echo.

python.exe -m pip install -U pip 


python.exe -m pip install -r requirements.txt
