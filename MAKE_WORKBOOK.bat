@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
python make_workbook.py --merge "Miramisu Eng.xlsx"
if errorlevel 1 (type logs\latest.log 2>nul)
pause
