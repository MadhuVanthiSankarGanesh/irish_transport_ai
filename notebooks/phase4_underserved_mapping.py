from pathlib import Path

import folium
import pandas as pd
from folium.plugins import MarkerCluster
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

project_root = Path(__file__).resolve().parents[1]

accessibility_candidates = [
    project_root / "dublin_stops_accessibility_full.csv",
    project_root / "data" / "clean" / "dublin_stops_accessibility_full.csv",
]
accessibility_file = next(
    (p for p in accessibility_candidates if p.exists()), accessibility_candidates[0]
)

# -----------------------------
# 1) Load Accessibility Data
# -----------------------------
access_df = pd.read_csv(accessibility_file)
print(f"Total stops loaded: {len(access_df)}")

# -----------------------------
# 2) Prepare Features for Clustering
# -----------------------------
# Use network-based reachability normalized
features = ["reachable_30min_norm", "reachable_45min_norm"]
X = access_df[features].fillna(0)

# Scale features
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# -----------------------------
# 3) KMeans Clustering
# -----------------------------
n_clusters = 4
kmeans = KMeans(n_clusters=n_clusters, random_state=42)
access_df["cluster"] = kmeans.fit_predict(X_scaled)

# Identify cluster with lowest average 45min reach as underserved
cluster_means = access_df.groupby("cluster")["reachable_45min_norm"].mean()
underserved_cluster = cluster_means.idxmin()
print(f"Cluster {underserved_cluster} is underserved (lowest reach)")

# -----------------------------
# 4) Save Clustered Data
# -----------------------------
access_df.to_csv(project_root / "dublin_stops_accessibility_clusters.csv", index=False)
print("Clustered stops saved as dublin_stops_accessibility_clusters.csv")

# -----------------------------
# 5) Interactive Folium Map
# -----------------------------
dublin_map = folium.Map(location=[53.3498, -6.2603], zoom_start=12)
colors = ["green", "blue", "orange", "red"]
marker_cluster = MarkerCluster().add_to(dublin_map)

for _, row in access_df.iterrows():
    cluster_idx = row["cluster"]
    color = colors[cluster_idx % len(colors)]

    popup_text = (
        f"Stop: {row['stop_id']}<br>"
        f"Reachable 30min: {row['reachable_30min']}<br>"
        f"Reachable 45min: {row['reachable_45min']}<br>"
        f"Cluster: {cluster_idx}"
    )

    folium.CircleMarker(
        location=[row["stop_lat"], row["stop_lon"]],
        radius=4,
        color=color,
        fill=True,
        fill_color=color,
        fill_opacity=0.7,
        popup=popup_text,
    ).add_to(marker_cluster)

# -----------------------------
# 6) Save Interactive Map
# -----------------------------
dublin_map.save(project_root / "dublin_underserved_stops_map.html")
print("Interactive Folium map saved as dublin_underserved_stops_map.html")
