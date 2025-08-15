@echo off
REM Çalışma dizinini bat dosyasının bulunduğu klasöre al (kalıcı olarak değiştirme)
pushd "%~dp0" >nul 2>&1

chcp 65001 >nul 2>&1
echo.
echo ===============================================
echo       SCRAPY BRIDGE - WEB SCRAPER
echo                  UPDATER
echo ===============================================

timeout /t 1 /nobreak >nul

echo UPDATER BAŞLATILIYOR...
echo.
timeout /t 1 /nobreak >nul

REM Öncelikle scripts\github_sync_improved.py'yi tercih et, yoksa github_sync_improved.py çalıştır
if exist "%~dp0scripts\github_sync_improved.py" (
    python.exe "%~dp0scripts\github_sync_improved.py"
) else if exist "%~dp0github_sync_improved.py" (
    python.exe "%~dp0github_sync_improved.py"
) else (
    echo HATA: github_sync_improved.py bulunamadi.
)

echo.
echo.
echo UPDATER OKKEYYY
echo.
echo installer'i calistirsan iyi olabilir. (scripts klasorunde de olabilir)

REM Orjinal cwd'ye don
popd >nul 2>&1

pause
exit /b 0