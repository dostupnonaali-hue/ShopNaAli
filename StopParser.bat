@echo off
echo ==============================================
echo 🛑 ЗУПИНКА ПАРСЕРА НА СЕРВЕРІ AMAZON EC2
echo ==============================================
echo.
echo Підключення до сервера та зупинка процесу...
ssh -i "E:\Shop_Na_Ali\shop_key.pem" ubuntu@13.62.55.57 "sudo systemctl stop parser.service"
echo.
echo Зачекайте 2 секунди...
timeout /t 2 /nobreak >nul
echo.
echo Статус сервісу після зупинки:
ssh -i "E:\Shop_Na_Ali\shop_key.pem" ubuntu@13.62.55.57 "systemctl status parser.service --no-pager"
echo.
echo ==============================================
echo Готово! Парсер повністю зупинено.
echo ==============================================
pause
