import zipfile
import csv
from datetime import datetime, timedelta

# Check Dublin Bus GTFS
print("Checking Dublin Bus GTFS...")
print("=" * 60)
try:
    with zipfile.ZipFile("e:\\irish_transport_ai\\otp\\graphs\\default\\dublin_bus.gtfs.zip") as z:
        # Read calendar.txt to see service dates
        if "calendar.txt" in z.namelist():
            with z.open("calendar.txt") as f:
                reader = csv.DictReader(t.decode('utf-8') for t in f)
                rows = list(reader)
                if rows:
                    for row in rows[:5]:  # Show first 5
                        print(f"Service ID: {row.get('service_id')}")
                        print(f"  Start: {row.get('start_date')} End: {row.get('end_date')}")
                        print(f"  Mon-Sun: {row.get('monday', '')}-{row.get('sunday', '')}")
                        print()
        
        # Also check calendar_dates.txt for exception dates
        if "calendar_dates.txt" in z.namelist():
            print("Has calendar_dates.txt (exception dates)")
            
        # Check trips.txt for some actual dates
        if "trips.txt" in z.namelist():
            with z.open("trips.txt") as f:
                trips = list(csv.DictReader(t.decode('utf-8') for t in f))
                print(f"Total trips: {len(trips)}")
                if trips:
                    print(f"Sample service_id: {trips[0].get('service_id')}")
except Exception as e:
    print(f"Error reading Dublin Bus: {e}")

print("\n\nChecking Luas GTFS...")
print("=" * 60)
try:
    with zipfile.ZipFile("e:\\irish_transport_ai\\otp\\graphs\\default\\luas.gtfs.zip") as z:
        if "calendar.txt" in z.namelist():
            with z.open("calendar.txt") as f:
                reader = csv.DictReader(t.decode('utf-8') for t in f)
                rows = list(reader)
                if rows:
                    for row in rows[:5]:
                        print(f"Service ID: {row.get('service_id')}")
                        print(f"  Start: {row.get('start_date')} End: {row.get('end_date')}")
                        print(f"  Mon-Sun: {row.get('monday', '')}-{row.get('sunday', '')}")
                        print()
except Exception as e:
    print(f"Error reading Luas: {e}")
