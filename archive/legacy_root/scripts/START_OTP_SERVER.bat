@echo off
REM Start OTP Server for Dublin Transit Routing
REM This script must be run in CMD (NOT PowerShell)

echo.
echo ============================================
echo Starting OTP Server v2.8.1
echo ============================================
echo.
echo Location: E:\irish_transport_ai\otp\graphs\default
echo Command: java -Xmx10G -jar otp-shaded-2.8.1.jar --load --serve .
echo.
echo This will take 30-60 seconds to initialize...
echo Look for: "OTP 2.8.1 is ready for routing!"
echo.
echo Once started, the chatbot will use REAL routing instead of demo mode
echo.
echo ============================================
echo.

cd /d E:\irish_transport_ai\otp\graphs\default

echo Loading graph...
java -Xmx10G -jar E:\OpenTripPlanner\otp-shaded\target\otp-shaded-2.8.1.jar --load --serve .

echo.
echo OTP Server stopped.
pause
