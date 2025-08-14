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
timeout /t 2 /nobreak >nul

echo.
echo ===============================================
echo       SCRAPY BRIDGE - WEB SCRAPER
echo ===============================================
echo.





REM Eğer .venv varsa -> korunacak; yoksa oluşturulacak
if exist ".venv" (
    echo .venv bulundu. Varsayilan: korunuyor.
    echo Gerekli paketler mevcut venv icine yukleniyor...
    call .venv\Scripts\activate
    ".venv\Scripts\python.exe" -m pip install -U pip
    if exist "requirements.txt" (
        ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    ) else (
        echo requirements.txt bulunamadi, atlaniliyor.
    )
) else (
    echo .venv bulunamadi. Yeni bir sanal ortam olusturuluyor...
    python.exe -m venv .venv
    if errorlevel 1 (
        echo venv olusturma sirasinda hata olustu.
        echo Lutfen Python ve pip'in kurulu oldugundan emin olun.
        pause
        exit /b 1
    )
    echo .venv olusturuldu. Paketler yukleniyor...
    call .venv\Scripts\activate
    python -m pip install -U pip
    if exist "requirements.txt" (
        python -m pip install -r requirements.txt
    ) else (
        echo requirements.txt bulunamadi, atlaniliyor.
        echo. 
        echo Bu bir sorun olabilir. lütfen ileşime geçin.
        echo.
        timeout /t 2 /nobreak >nul
    )
)


echo.
echo Kurulum tamamlandi.













echo.
echo.
echo.
echo Otomatik olarak 2 saniye içinde program başlatılacak.
echo.
echo Bu pencereyi 2 saniye sonra kapatabilirisniz. 
echo.
timeout /t 1 /nobreak >nul
echo Bu pencereyi 1 saniye sonra kapatabilirsiniz.
echo.
timeout /t 1 /nobreak >nul


REM START: aynı dizinde start.bat var ise onu yeni bir cmd penceresinde cagir
set "SCRIPT_DIR=%~dp0"
if exist "%SCRIPT_DIR%start.bat" (
    echo Yeni pencere acilarak start.bat calistirilacak...
    start "" cmd /k "cd /d "%SCRIPT_DIR%" && call start.bat"
) else (
    echo start.bat bulunamadi. Calistirmak icin manuel olarak run.py ya da start.bat calistirin.
)


echo. 
echo BU PENCEREYI KAPAT !!!
echo.
pause
exit /b 0
