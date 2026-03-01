@echo off
chcp 65001 >nul
title Shop Na Ali — Site Server
echo.
echo  ==============================
echo   🌐 Shop Na Ali — Сайт
echo  ==============================
echo.
echo  Відкрийте у браузері: http://localhost:8080
echo  Для зупинки натисніть Ctrl+C
echo  ==============================
echo.

cd /d "%~dp0site"
start http://localhost:8080
python -m http.server 8080

pause
