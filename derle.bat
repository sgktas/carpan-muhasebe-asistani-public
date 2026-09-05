@echo off
setlocal
cd /d "%~dp0"

REM Muhasebe Asistani - Windows .exe derleme betigi
REM Her zaman proje klasorundeki sanal ortami kullanir; yoksa aktif Python'u kullanir.

set "PYTHON=python"
if exist ".venv\Scripts\python.exe" set "PYTHON=.venv\Scripts\python.exe"

echo Python ortami: %PYTHON%
echo.
echo Gerekli paketler kuruluyor...
"%PYTHON%" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto :error

"%PYTHON%" -m pip install -r requirements.txt
if errorlevel 1 goto :error

REM pywin32 hizli COM yoludur; kurulamasa bile program PowerShell COM yedegiyle calisir.
echo.
echo Windows Excel COM paketi kontrol ediliyor...
"%PYTHON%" -m pip install --upgrade pywin32
if errorlevel 1 (
    echo UYARI: pywin32 kurulamadi. Program yerlesik PowerShell Excel koprusunu kullanacak.
)

echo.
echo Eski derleme klasorleri temizleniyor...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

echo.
echo .exe dosyasi derleniyor ^(birkac dakika surebilir^)...
"%PYTHON%" -m PyInstaller muhasebe_asistani.spec --noconfirm --clean
if errorlevel 1 goto :error

if not exist "dist\MuhasebeAsistani\MuhasebeAsistani.exe" (
    echo HATA: Derleme tamamlandi ancak EXE bulunamadi.
    goto :error
)

echo.
echo Bitti! Program "dist\MuhasebeAsistani\MuhasebeAsistani.exe" konumunda olusturuldu.
echo Program pywin32 olmasa bile Windows PowerShell ve Microsoft Excel ile cikti uretebilir.
pause
exit /b 0

:error
echo.
echo DERLEME BASARISIZ. Yukaridaki hata mesajini kontrol edin.
pause
exit /b 1
