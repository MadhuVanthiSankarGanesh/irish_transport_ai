import zipfile
import csv
import os

downloads = os.path.expanduser("~/Downloads")
otp_path = r"e:\irish_transport_ai\otp\graphs\default"

print("=" * 70)
print("SERVICE DATES IN FRESH DOWNLOADS")
print("=" * 70)

for zip_name in ['dublin_bus.zip', 'luas.zip']:
    print(f"\n{zip_name}:")
    print("-" * 50)
    
    zip_path = os.path.join(downloads, zip_name)
    with zipfile.ZipFile(zip_path) as z:
        with z.open('calendar.txt') as f:
            reader = csv.DictReader(t.decode('utf-8') for t in f)
            rows = list(reader)
            
            # Show service date ranges
            for row in rows[:8]:
                print(f"  Service {row['service_id']}: {row['start_date']}-{row['end_date']} | {row['monday']}-{row['sunday']}")

print("\n" + "=" * 70)
print("NOW IN OTP FOLDER")
print("=" * 70)

for zip_name in ['dublin_bus.gtfs.zip', 'luas.gtfs.zip']:
    print(f"\n{zip_name}:")
    print("-" * 50)
    
    zip_path = os.path.join(otp_path, zip_name)
    if os.path.exists(zip_path):
        with zipfile.ZipFile(zip_path) as z:
            with z.open('calendar.txt') as f:
                reader = csv.DictReader(t.decode('utf-8') for t in f)
                rows = list(reader)
                
                for row in rows[:8]:
                    print(f"  Service {row['service_id']}: {row['start_date']}-{row['end_date']} | {row['monday']}-{row['sunday']}")
    else:
        print(f"  ⚠️ File not found!")

print("\n✓ Today is March 24, 2026 (Tuesday)")
