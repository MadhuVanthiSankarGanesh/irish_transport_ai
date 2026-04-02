import zipfile
import csv

# Extract some actual stop IDs from Dublin Bus GTFS
print("Extracting stop IDs from Dublin Bus GTFS...")
with zipfile.ZipFile("e:\\irish_transport_ai\\otp\\graphs\\default\\dublin_bus.gtfs.zip") as z:
    if "stops.txt" in z.namelist():
        with z.open("stops.txt") as f:
            reader = csv.DictReader(t.decode('utf-8') for t in f)
            stops = list(reader)
            print(f"Total stops: {len(stops)}")
            print("\nFirst 10 stops:")
            for i, stop in enumerate(stops[:10]):
                print(f"  {i}. ID: {stop['stop_id']:<10} Name: {stop['stop_name']:<50} Lat: {stop['stop_lat']:<12} Lon: {stop['stop_lon']}")
