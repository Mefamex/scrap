@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

REM =============================
REM  AYAR BLOĞU (İsteğe göre değiştirilebilir)
REM =============================
set "MIN_PY_VERSION=3.9"
set "APP_NAME=ScrapyBridge"
set "DEFAULT_ICON=icon.ico"
set "SOURCE_DIR=src"
set "VENV_DIR=.venv"
set "ENABLE_CONSOLE=1"  REM 0 yaparsaniz --noconsole eklenir
set "EXTRA_HIDDEN=selenium bs4 soupsieve pydantic pydantic_settings webdriver_manager"
set "COLLECT_SUBMODULES=selenium bs4 webdriver_manager"

REM Argümanlar: --noconsole / --clean / --strip
for %%A in (%*) do (
    if /I "%%~A"=="--noconsole" set "ENABLE_CONSOLE=0"
    if /I "%%~A"=="--clean" set "OPT_CLEAN=1"
    if /I "%%~A"=="--strip" set "OPT_STRIP=1"
)

REM Script dizinine geç
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

cls
echo ==================================================================
echo                      SCRAPY BRIDGE - WEB SCRAPER
echo                   Python -> EXE Donusturucu
echo ==================================================================
echo  Uygulama: %APP_NAME%
echo  Giris dosyasi: run.py veya main.py (otomatik secim)
echo  Konsol: !ENABLE_CONSOLE!
echo ==================================================================
echo.

title %APP_NAME% - Python to EXE Converter

REM 1) Python kontrolü
echo [1/10] Python kontrol ediliyor...
python --version >nul 2>&1 || goto :NoPython
for /f "tokens=2 delims= " %%V in ('python --version 2^>^&1') do set "FOUND_PY_VER=%%V"
echo Bulunan Python Surumu: !FOUND_PY_VER!
echo ✅ Python bulundu
echo.

REM 2) Virtual environment kontrolü
echo [2/10] Virtual environment kontrol ediliyor...
if exist "%VENV_DIR%" (
    call "%VENV_DIR%\Scripts\activate.bat" >nul 2>&1
    if not errorlevel 1 (
        echo ✅ Virtual environment aktif: %VENV_DIR%
        python -m pip -V
    ) else (
        echo ⚠️  Virtual environment etkinlestirilemedi, sistem Python kullanilacak
    )
) else (
    echo ⚠️  Virtual environment yok, sistem Python kullanilacak
)
echo.

REM 3) Pip guncelleme
echo [3/10] Pip guncelleniyor...
python -m pip install --upgrade pip >nul 2>&1 && echo ✅ Pip guncellendi || echo ⚠️  Pip guncellenemedi (devam)
echo.

REM 4) PyInstaller kontrol/kurulum
echo [4/10] PyInstaller kontrol ediliyor...
pip show pyinstaller >nul 2>&1 || (
    echo Kurulum yapiliyor...
    pip install --upgrade pyinstaller || goto :PyInstallerFail
)
pip install --upgrade pyinstaller >nul 2>&1 && echo ✅ PyInstaller hazir || echo ⚠️  Guncelleme atlandi
echo.

REM 5) Gereksinimler
echo [5/10] requirements.txt (varsa) yukleniyor...
if exist requirements.txt (
    pip install -r requirements.txt || echo ⚠️  Bazı paketler yuklenemedi, devam edilecek
) else (
    echo (requirements.txt bulunamadı - atlandi)
)
echo.

REM 6) Temizlik
echo [6/10] Onceki build temizlik yapiliyor...
if exist build (rmdir /s /q build)
if exist dist (rmdir /s /q dist)
del /q *.spec >nul 2>&1
echo ✅ Temizlendi
echo.

REM 7) PyInstaller komutu hazirlaniyor
echo [7/10] PyInstaller komutu olusturuluyor...
if exist run.py (
    set "ENTRY_SCRIPT=run.py"
) else if exist main.py (
    set "ENTRY_SCRIPT=main.py"
) else (
    echo ❌ HATA: run.py veya main.py bulunamadi!
    goto :FailFatal
)

set "PYINSTALLER_CMD=pyinstaller --onefile"
if %ENABLE_CONSOLE%==1 (set "PYINSTALLER_CMD=%PYINSTALLER_CMD% --console") else (set "PYINSTALLER_CMD=%PYINSTALLER_CMD% --noconsole")
set "PYINSTALLER_CMD=%PYINSTALLER_CMD% --name %APP_NAME%"
if exist "%DEFAULT_ICON%" set "PYINSTALLER_CMD=%PYINSTALLER_CMD% --icon=%DEFAULT_ICON%"
set "PYINSTALLER_CMD=%PYINSTALLER_CMD% --paths %SOURCE_DIR%"
if defined OPT_CLEAN set "PYINSTALLER_CMD=%PYINSTALLER_CMD% --clean"
if defined OPT_STRIP set "PYINSTALLER_CMD=%PYINSTALLER_CMD% --strip"
if exist requirements.txt set "PYINSTALLER_CMD=%PYINSTALLER_CMD% --add-data requirements.txt;."
if exist .env set "PYINSTALLER_CMD=%PYINSTALLER_CMD% --add-data .env;."

for %%I in (%EXTRA_HIDDEN%) do set "PYINSTALLER_CMD=%PYINSTALLER_CMD% --hidden-import %%I"
for %%I in (%COLLECT_SUBMODULES%) do set "PYINSTALLER_CMD=%PYINSTALLER_CMD% --collect-submodules %%I"

set "PYINSTALLER_CMD=%PYINSTALLER_CMD% --distpath dist --workpath build --specpath . %ENTRY_SCRIPT%"
echo Komut: %PYINSTALLER_CMD%
echo.

REM 8) Derleme
echo [8/10] Derleniyor (bu surebilir)...
%PYINSTALLER_CMD%
if errorlevel 1 goto :BuildFail
echo ✅ Derleme tamamlandi
echo.

REM 9) Cikti dogrulama
echo [9/10] Cikti dogrulaniyor...
set "OUTPUT_EXE=dist\%APP_NAME%.exe"
if not exist "!OUTPUT_EXE!" goto :NoExe
for %%F in ("!OUTPUT_EXE!") do (
    set "FILE_SIZE=%%~zF"
    set /a "SIZE_MB=%%~zF/1024/1024"
)
echo ✅ Olusan dosya: !OUTPUT_EXE!  (^!SIZE_MB! MB ~ !FILE_SIZE! bytes^)
echo.

REM 10) Basit calisma testi
echo [10/10] Basit test calistiriliyor...
"!OUTPUT_EXE!" --version >nul 2>&1 && echo ✅ Test ( --version ) komutu calisti || echo ⚠️  Test komutu basarisiz (bu normal olabilir)
echo.

echo ================================================================
echo                          BASARILI
echo ================================================================
echo Cikti: !OUTPUT_EXE!
echo Ornek kullanim:
echo   %APP_NAME%.exe
echo   %APP_NAME%.exe --help
echo   %APP_NAME%.exe url_liste.txt
echo ---------------------------------------------------------------
echo Ek Secenekler:
echo   toExe.bat --noconsole   (GUI modunda calistir)
echo   toExe.bat --clean       (PyInstaller temiz build)
echo   toExe.bat --strip       (Ikiliyi kucult - Windows etkisi sinirli)
echo ================================================================
goto :EndOk

REM ===================== HATA ETIKETLERI =====================
:NoPython
echo ❌ HATA: Python bulunamadi. Lutfen %MIN_PY_VERSION%+ kurun: https://www.python.org/downloads/
goto :FailFatal

:PyInstallerFail
echo ❌ HATA: PyInstaller kurulamadı.
goto :FailFatal

:BuildFail
echo ❌ HATA: Derleme basarisiz (PyInstaller hata verdi)
goto :FailFatal

:NoExe
echo ❌ HATA: Beklenen exe bulunamadi: dist\%APP_NAME%.exe
goto :FailFatal

:FailFatal
echo.
echo ====================== ISLEM BASARISIZ ======================
echo Log'u inceleyin ve tekrar deneyin.
echo =============================================================
echo.
pause
exit /b 1

:EndOk
echo.
pause
exit /b 0

