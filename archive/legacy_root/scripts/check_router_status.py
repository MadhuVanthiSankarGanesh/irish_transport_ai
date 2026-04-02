import requests

# Try to check if router is properly loaded
urls_to_test = [
    "/otp/routers",           # List available routers
    "/otp/routers/default",   # Details for default router
    "/otp/routers/default/index", # Router index info
]

print("Checking router status...")
print("=" * 60)

for path in urls_to_test:
    try:
        r = requests.get(f"http://localhost:8080{path}", timeout=5)
        print(f"{r.status_code} | {path}")
        if r.status_code == 200:
            try:
                print(f"  Response: {r.text[:200]}")
            except:
                print(f"  (binary/complex response)")
    except Exception as e:
        print(f"ERR | {path}: {e}")

print("\n\nTrying transmodel API...")
try:
    r = requests.get("http://localhost:8080/otp/routers/default/transmodel", timeout=5)
    print(f"{r.status_code} | transmodel")
except:
    pass
