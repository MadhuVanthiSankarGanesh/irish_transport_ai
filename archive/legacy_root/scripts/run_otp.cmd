@echo off
REM Start OTP Server - Real Transit Routing

cd /d E:\irish_transport_ai\otp\graphs\default

echo.
echo ========================================
echo Starting OTP 2.8.1 Server
echo ========================================
echo.
echo This enables REAL Dublin transit routing
echo Waiting for "ready" message (30-60 sec)...
echo.

java -Xmx10G -jar E:\OpenTripPlanner\otp-shaded\target\otp-shaded-2.8.1.jar --load --serve .
