import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

FILES = {
    "start.bat": r"""
REM filepath: c:\Users\Mefamex\Desktop\scrap\start.bat
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
    echo Paket yöneticisi bulunamadı. 
    echo Lutfen Python ve pip'in kurulu oldugundan emin olun.
    echo doğru dizinde çalıştırdığınızdan emin olun
    pause
    exit /b 1
)

echo.
REM venv aktif mi kontrolü
if defined VIRTUAL_ENV (
    echo Sanallaştırma aktif:  %VIRTUAL_ENV%
) else (
    echo Sanallaştırma aktif değil. .venv\\Scripts\\python.exe ile denenecek...
    set "VENV_PY=%~dp0.venv\Scripts\python.exe"
    if exist "%VENV_PY%" (
        "%VENV_PY%" -m pip -V >nul 2>&1
        if errorlevel 1 (
            echo .venv icindeki python ile pip calistirilamadi.
            echo Lutfen .venv'in tam olarak olusturuldugunu ve kilitlenmedigini kontrol edin.
            pause
            exit /b 1
        ) else (
            echo .venv python calistirildi: %VENV_PY%
            rem Bu oturum icin PATH'e venv Scripts klasorunu ekle (opsiyonel)
            set "PATH=%~dp0.venv\Scripts;%PATH%"
        )
    ) else (
        echo .venv yok veya %VENV_PY% bulunamadi.
        echo .venv olusturmak icin: python -m venv .venv
        pause
        exit /b 1
    )
)
timeout /t 4 /nobreak >nul

echo UYGULAMA BAŞLATILIYOR...
echo.
timeout /t 2 /nobreak >nul

python.exe run.py

echo.
echo.
echo UYGULAMA SONLANDIRILDI
pause
""",
    "install.bat": r"""
REM filepath: c:\Users\Mefamex\Desktop\scrap\install.bat
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
""",
}

def write_if_changed(path: Path, content: str) -> bool:
    # Her durumda dosyayı yeniden yaz (CRLF Windows uyumu)
    try:
        path.write_text(content, encoding="utf-8", newline="\r\n")
        print(f"WROTE: {path.name}")
        return True
    except Exception as e:
        print(f"HATA yazarken {path.name}: {e}", file=sys.stderr)
        return False

def main():
    for name, txt in FILES.items():
        p = SCRIPT_DIR / name
        write_if_changed(p, txt)

if __name__ == "__main__":
    main()