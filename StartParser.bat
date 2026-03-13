@echo off
echo ==============================================
echo [STARTING PARSER ON AMAZON EC2]
echo ==============================================
echo.
echo Connecting to server...
ssh -i "E:\Shop_Na_Ali\shop_key.pem" ubuntu@13.62.55.57 "sudo systemctl start parser.service"
echo.
echo Waiting 2 seconds...
timeout /t 2 /nobreak >nul
echo.
echo Service status after start:
ssh -i "E:\Shop_Na_Ali\shop_key.pem" ubuntu@13.62.55.57 "systemctl status parser.service --no-pager"
echo.
echo ==============================================
echo DONE! Parser is started.
echo ==============================================
pause
