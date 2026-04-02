from geopy.geocoders import Nominatim
import pandas as pd
from sklearn.neighbors import KDTree
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

stops_path = os.path.join(BASE_DIR, "data/gtfs/stops.txt")

stops = pd.read_csv(stops_path)

tree = KDTree(stops[["stop_lat", "stop_lon"]].values)

geolocator = Nominatim(user_agent="smart_mobility_ai")


def place_to_coordinates(place_name):

    location = geolocator.geocode(place_name)

    if location:
        return location.latitude, location.longitude

    return None, None


def find_nearest_stop(lat, lon):

    dist, ind = tree.query([[lat, lon]], k=1)

    stop = stops.iloc[ind[0][0]]

    return stop["stop_id"], stop["stop_lat"], stop["stop_lon"]