import requests

endpoints = [
    '/',
    '/otp',
    '/api',
    '/routers',
    '/graphql',
    '/gtfs',
    '/transmodel',
    '/routers/default',
]

print("Checking OTP endpoints...")
print("=" * 60)

for endpoint in endpoints:
    try:
        r = requests.get(f'http://localhost:8080{endpoint}', timeout=2)
        status = r.status_code
        ctype = r.headers.get('content-type', '')[:30]
        print(f"{status} | {endpoint:30} | {ctype}")
    except Exception as e:
        print(f"ERR | {endpoint:30} | {str(e)[:30]}")
