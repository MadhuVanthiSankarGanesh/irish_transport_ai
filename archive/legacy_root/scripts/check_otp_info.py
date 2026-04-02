import requests
import json

# Check server info
url = "http://localhost:8080/otp"
response = requests.get(url, timeout=5)
server_info = response.json()

print("OTP Server Info:")
print(json.dumps(server_info, indent=2))
