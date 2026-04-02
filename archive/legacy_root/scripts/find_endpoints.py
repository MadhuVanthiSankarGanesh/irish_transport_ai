import requests

# Try various endpoint patterns
endpoints = [
    '/otp/',
    '/otp/routers',
    '/otp/routers/default',
    '/otp/routers/default/index/graphql',
    '/otp/graphql',
    '/otp/index/graph ql',
    '/otp/v1/routers/default/plan',
    '/otp/v2/routers/default/plan',
    '/otp/plan',
]

print("Testing OTP with /otp prefix...")
print("=" * 60)

for endpoint in endpoints:
    try:
        r = requests.get(f'http://localhost:8080{endpoint}', timeout=2)
        print(f"{r.status_code} | {endpoint}")
    except Exception as e:
        print(f"ERR | {endpoint}")
