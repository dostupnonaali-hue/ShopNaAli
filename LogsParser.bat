@echo off
echo ==============================================
echo [PARSER LOGS FROM AMAZON EC2]
echo ==============================================
echo Fetching the last 100 log lines...
echo.
ssh -i "E:\Shop_Na_Ali\shop_key.pem" ubuntu@13.62.55.57 "journalctl -u parser.service -n 100 --no-pager"
echo.
echo ==============================================
echo End of logs.
echo ==============================================
pause
