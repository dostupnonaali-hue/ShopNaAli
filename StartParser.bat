@echo off
chcp 65001 > nul
echo ==============================================
echo 🚀 ЗУПУСК ПАРСЕРА НА СЕРВЕРІ AMAZON EC2
echo ==============================================
echo.
echo Підключення до сервера...
ssh -i "E:\Shop_Na_Ali\shop_key.pem" ubuntu@13.62.55.57 "sudo systemctl start parser.service"
echo.
echo Зачекайте 2 секунди...
timeout /t 2 /nobreak >nul
echo.
echo Статус сервісу після запуску:
ssh -i "E:\Shop_Na_Ali\shop_key.pem" ubuntu@13.62.55.57 "systemctl status parser.service --no-pager"
echo.
echo ==============================================
echo Готово! Парсер запущено.
echo Ви можете перевірити логі за допомогою файла LogsParser.bat.
echo ==============================================
pause
