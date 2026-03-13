@echo off
echo ==============================================
echo [STOPPING PARSER ON AMAZON EC2]
echo ==============================================
echo.
echo Connecting to server and stopping service...
ssh -i "E:\Shop_Na_Ali\shop_key.pem" ubuntu@13.62.55.57 "sudo systemctl stop parser.service"
echo.
echo Waiting 2 seconds...
timeout /t 2 /nobreak >nul
echo.
echo Service status after stop:
ssh -i "E:\Shop_Na_Ali\shop_key.pem" ubuntu@13.62.55.57 "systemctl status parser.service --no-pager"
echo.
echo ==============================================
echo DONE! Parser is completely stopped.
echo ==============================================
pause
