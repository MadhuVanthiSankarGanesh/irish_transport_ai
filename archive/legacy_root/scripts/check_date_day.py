from datetime import datetime, timedelta

# Check what day of week March 24, 2026 is
target_date = datetime(2026, 3, 24)
day_name = target_date.strftime("%A")
print(f"March 24, 2026 is a {day_name}")

# Check calendar coverage and find good dates
print("\nGTFS Service Coverage:")
print("Service 1: Feb 22-23, all days")
print("Service 2: Feb 23, all days")
print("Service 3: Feb 22, weekend only")
print("Service 4: Feb 27 - Sept 4, no days (0-0)")
print("Service 5: Feb 23 - Sept 7, Monday only")

# Since service 5 runs Feb 23 - Sept 7 and only on Mondays,
# we need to find a Monday in that range
start = datetime(2026, 2, 23)
for i in range(200):
    check_date = start + timedelta(days=i)
    if check_date.weekday() == 0:  # Monday
        print(f"Monday in range: {check_date.strftime('%Y-%m-%d (%A)')}")
        if i < 5:
            candidate = check_date.strftime('%Y-%m-%d')
            print(f"  -> Good test date: {candidate}")
            break

# Let's try Feb 24, 2026 (Tuesday after Feb 22 Mon start)
test_date = datetime(2026, 2, 24)
print(f"\nTesting with: {test_date.strftime('%Y-%m-%d (%A)')}")
print("This should be covered by Service 1 (all days Feb 22-23... wait, that ends Feb 23)")
print("So Feb 24 won't work")

# Try Feb 23 (should work - all services active)
test_date = datetime(2026, 2, 23)
print(f"\nTesting with: {test_date.strftime('%Y-%m-%d (%A)')}")
print("Services 1, 2, 5 are active on this date")
