@echo off
cd /d e:\irish_transport_ai
echo Starting OTP rebuild...
echo This will take 5-15 minutes
java -Xmx10G -jar otp\otp-shaded-2.8.1.jar --build otp/graphs/default --serve
pause
