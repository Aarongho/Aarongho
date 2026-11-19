@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Scraping MIMS: semua kelas + alfabet a-z. Jangan tutup jendela Chrome.
python mims_brand_generic.py
pause
