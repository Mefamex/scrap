@echo off
chcp 65001 >nul 2>&1
echo.
echo BEFORE DIR : %cd%
echo.
cd /d "%~dp0"
echo CURRENT DIR: %CD%
echo.
echo 2. yazılan dizin projenin dizini olması gerekiyor. 
echo                 Eğer değilse sıkıntı büyük kral...
echo                                   kapat dükkanı...
echo.
timeout /t 4 /nobreak >nul



echo.
echo ===============================================
echo       SCRAPY BRIDGE - WEB SCRAPER
echo ===============================================

echo 1. Starting virtual environment...
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo.
    echo ❌Paket yöneticisi bulunamadı. 
    echo ❌Lutfen Python ve pip'in kurulu oldugundan emin olun.
    echo ❌doğru dizinde çalıştırdığınızdan emin olun
    pause
    exit /b 1
)

echo.
REM venv aktif mi kontrolü
if defined VIRTUAL_ENV (
    echo ✅ Sanallaştırma aktif:  %VIRTUAL_ENV%
) else (
    echo ⚠️ Sanallaştırma aktif değil. .venv\\Scripts\\python.exe ile denenecek...
    set "VENV_PY=%~dp0.venv\Scripts\python.exe"
    if exist "%VENV_PY%" (
        "%VENV_PY%" -m pip -V >nul 2>&1
        if errorlevel 1 (
            echo ❌ .venv icindeki python ile pip calistirilamadi.
            echo ❌ Lutfen .venv'in tam olarak olusturuldugunu ve kilitlenmedigini kontrol edin.
            pause
            exit /b 1
        ) else (
            echo .venv python calistirildi: %VENV_PY%
            rem Bu oturum icin PATH'e venv Scripts klasorunu ekle (opsiyonel)
            set "PATH=%~dp0.venv\Scripts;%PATH%"
        )
    ) else (
        echo ❌ .venv yok veya %VENV_PY% bulunamadi.
        echo ❌ .venv olusturmak icin: python -m venv .venv
        pause
        exit /b 1
    )
)
timeout /t 4 /nobreak >nul

echo ✅ UYGULAMA BAŞLATILIYOR...
echo.
timeout /t 2 /nobreak >nul

python.exe run.py

echo.
echo.
echo ✅ UYGULAMA SONLANDIRILDI
pause
