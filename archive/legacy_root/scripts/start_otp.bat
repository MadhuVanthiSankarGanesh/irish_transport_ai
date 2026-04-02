@echo off
REM Start OTP server for Dublin transit routing
cd /d E:\irish_transport_ai\otp\graphs\default
java -Xmx10G -jar E:\OpenTripPlanner\otp-shaded\target\otp-shaded-2.8.1.jar --load --serve .
pause
