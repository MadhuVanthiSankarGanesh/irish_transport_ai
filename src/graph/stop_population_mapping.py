import os
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

# =========================
# FILE PATHS
# =========================

STOPS_PATH = r"E:\irish_transport_ai\data\clean\stops.csv"

CSO_GPKG_PATH = r"E:\irish_transport_ai\data\raw\cso_boundaries\Small_Area_National_Statistical_Boundaries_2022_Ungeneralised_view_-7354763930310470674 (1).gpkg"

POPULATION_PATH = r"E:\irish_transport_ai\data\raw\SAPS_2022_Small_Area_UR_171024 (1).csv"

OUTPUT_PATH = r"E:\irish_transport_ai\data\processed\dublin_stops_with_population.csv"


# =========================
# LOAD SMALL AREA POLYGONS
# =========================

print("Loading CSO Small Area boundaries...")
sa_gdf = gpd.read_file(CSO_GPKG_PATH)

print("Filtering Dublin areas...")
sa_gdf = sa_gdf[
    sa_gdf["COUNTY_ENGLISH"].str.contains("Dublin", case=False, na=False)
]

print("Dublin Small Areas:", len(sa_gdf))


# =========================
# LOAD STOPS
# =========================

print("Loading stops...")
stops_df = pd.read_csv(STOPS_PATH)

geometry = [
    Point(xy) for xy in zip(stops_df["stop_lon"], stops_df["stop_lat"])
]

stops_gdf = gpd.GeoDataFrame(
    stops_df,
    geometry=geometry,
    crs="EPSG:4326"
)

stops_gdf = stops_gdf.to_crs(sa_gdf.crs)


# =========================
# LOAD POPULATION
# =========================

print("Loading population dataset...")
pop_df = pd.read_csv(POPULATION_PATH)

pop_df["GEOGID"] = pop_df["GEOGID"].astype(str).str.split("/").str[0]

# Sum all age columns to compute population
age_cols = [c for c in pop_df.columns if c.startswith("T1_1AGE")]

print("Age columns used:", len(age_cols))

pop_df["population"] = pop_df[age_cols].sum(axis=1)

pop_df = pop_df[["GEOGID", "population"]]


# =========================
# SPATIAL JOIN
# =========================

print("Mapping stops to Small Areas...")

stops_sa = gpd.sjoin(
    stops_gdf,
    sa_gdf[["SA_PUB2016", "geometry"]],
    how="left",
    predicate="within"
)


# =========================
# MERGE POPULATION
# =========================

print("Merging population...")

stops_pop = stops_sa.merge(
    pop_df,
    left_on="SA_PUB2016",
    right_on="GEOGID",
    how="left"
)


# =========================
# CLEAN OUTPUT
# =========================

final_df = stops_pop.drop(
    columns=["geometry", "index_right", "GEOGID"],
    errors="ignore"
)

os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

final_df.to_csv(OUTPUT_PATH, index=False)

print("\nSaved file:")
print(OUTPUT_PATH)

print("\nSummary:")
print("Total stops:", len(final_df))
print("Stops with population:", final_df["population"].notna().sum())