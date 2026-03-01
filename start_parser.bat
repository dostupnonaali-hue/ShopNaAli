@echo off
chcp 65001 >nul
title Shop Na Ali — Parser
echo.
echo  ==============================
echo   🛒 Shop Na Ali — Parser
echo  ==============================
echo.
echo  Запуск Telegram парсера...
echo  Канали: @theCheapestAliExpress, @AliReviewers, @halyavaZaliExpress
echo  Webhook: n8n.21000.online
echo.
echo  Для зупинки натисніть Ctrl+C
echo  ==============================
echo.

cd /d "%~dp0parser"
python main.py

if %errorlevel% neq 0 (
    echo.
    echo  ❌ Помилка! Перевірте:
    echo     1. Чи встановлений Python: python --version
    echo     2. Чи встановлені залежності: pip install -r requirements.txt
    echo     3. Чи заповнений файл .env
    echo.
)

pause
