@echo off
cd /d "%~dp0"
:ulang
python mims_brand_generic.py
set KODE=%ERRORLEVEL%
if "%KODE%"=="0" goto selesai
if "%KODE%"=="2" goto perlu_kamu
echo.
echo Script berhenti karena error (kode %KODE%). Restart otomatis dalam 30 detik, lanjut dari checkpoint...
timeout /t 30
goto ulang
:perlu_kamu
echo.
echo Script berhenti karena butuh kamu (captcha / login). Jalankan lagi file ini setelah siap.
:selesai
pause
