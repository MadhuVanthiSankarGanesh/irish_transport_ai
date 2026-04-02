import pandas as pd
import json
import os

INPUT_PATH = r"E:\irish_transport_ai\data\processed\dublin_graph_features.csv"
OUTPUT_PATH = r"E:\irish_transport_ai\data\processed\transit_knowledge_base.json"

print("Loading graph features...")
df = pd.read_csv(INPUT_PATH)

print("Creating LLM knowledge documents...")

documents = []

for _, row in df.iterrows():

    text = f"""
Stop ID: {row['stop_id']}
Stop Name: {row['stop_name']}

Population near stop: {row['population']}

Service frequency score: {row['service_frequency']}

Demand supply ratio: {row['demand_supply_ratio']}

Graph centrality: {row['degree_centrality']}

Network importance: {row['betweenness_centrality']}

Graph underserved score: {row['graph_gap_score']}

Interpretation:
Higher population with lower service frequency indicates underserved areas.
High betweenness indicates critical network hubs.
"""

    documents.append({
        "stop_id": row["stop_id"],
        "text": text
    })

os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

with open(OUTPUT_PATH, "w") as f:
    json.dump(documents, f, indent=2)

print("Knowledge base created:")
print(OUTPUT_PATH)
print("Documents:", len(documents))