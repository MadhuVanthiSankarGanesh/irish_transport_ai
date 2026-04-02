import zipfile
import csv

# Find Dublin city center stops (lat ~53.3-53.4, lon ~-6.2 to -6.3)
print("Finding Dublin city center stops...")
with zipfile.ZipFile("e:\\irish_transport_ai\\otp\\graphs\\default\\dublin_bus.gtfs.zip") as z:
    if "stops.txt" in z.namelist():
        with z.open("stops.txt") as f:
            reader = csv.DictReader(t.decode('utf-8') for t in f)
            stops = list(reader)
            
            # Filter for Dublin area (rough bounds)
            dublin_stops = [
                s for s in stops
                if 53.3 < float(s['stop_lat']) < 53.4 and -6.3 < float(s['stop_lon']) < -6.2
            ]
            
            print(f"Found {len(dublin_stops)} Dublin city center stops\n")
            print("Sample Dublin stops:")
            for i, stop in enumerate(dublin_stops[:15]):
                print(f"  ID: {stop['stop_id']:<15} Name: {stop['stop_name']:<50}")
            
            # Also check Luas
print("\n\nLooking for Luas stops...")
with zipfile.ZipFile("e:\\irish_transport_ai\\otp\\graphs\\default\\luas.gtfs.zip") as z:
    if "stops.txt" in z.namelist():
        with z.open("stops.txt") as f:
            reader = csv.DictReader(t.decode('utf-8') for t in f)
            stops = list(reader)
            dublin_stops = [
                s for s in stops
                if 53.3 < float(s['stop_lat']) < 53.4 and -6.3 < float(s['stop_lon']) < -6.2
            ]
            print(f"Found {len(dublin_stops)} Luas stops in Dublin\n")
            for i, stop in enumerate(dublin_stops[:10]):
                print(f"  ID: {stop['stop_id']:<15} Name: {stop['stop_name']:<50}")
