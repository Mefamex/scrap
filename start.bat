@echo off
chcp 65001
call .venv\Scripts\activate.bat
python -c "import os; print('Python RUN DIR:', os.getcwd())"
echo    CURRENT DIR: %CD%
timeout /t 3 /nobreak >nul


echo.
echo ===============================================
echo       SCRAPY BRIDGE - WEB SCRAPER
echo ===============================================
echo.

:: echo 1. Installing requirements...
:: pip install -r requirements.txt
:: if %errorlevel% neq 0 (
::     echo.
::     echo ERROR: Failed to install requirements!
::     echo Please make sure Python and pip are installed.
::     pause
::     exit /b 1
:: )


echo.
echo 2. Starting ScrapyBridge

python run.py

echo.
echo ScrapyBridge has been closed.
pause
