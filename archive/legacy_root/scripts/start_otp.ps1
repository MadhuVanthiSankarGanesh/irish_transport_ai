# Start OTP Server for Dublin Transport
Write-Host "Starting OTP Server..."
Write-Host "Location: E:\irish_transport_ai\otp\graphs\default"
Write-Host "Command: java -Xmx10G -jar otp-shaded-2.8.1.jar --load --serve ."
Write-Host ""
Write-Host "Waiting for server to start (this takes ~30 seconds)..."
Write-Host ""

cd E:\irish_transport_ai\otp\graphs\default

# Start the process and capture output
& "java" `
    -Xmx10G `
    -jar "E:\OpenTripPlanner\otp-shaded\target\otp-shaded-2.8.1.jar" `
    --load --serve . `
    2>&1 | Tee-Object -FilePath otp_startup.log | Where-Object {
        $_ -match "ready|listening|shutdown|ERROR|WARN|Graph|8080"
    }
