import pandas as pd
import os
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
import xgboost as xgb
import joblib

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

event_path = os.path.join(BASE_DIR, "data", "features", "event_demand.csv")
congestion_path = os.path.join(BASE_DIR, "data", "features", "realtime_congestion.csv")

print("Loading datasets...")

events = pd.read_csv(event_path)
congestion = pd.read_csv(congestion_path)

print("Events:", len(events))
print("Congestion rows:", len(congestion))

# Merge datasets
data = events.merge(congestion, on="stop_id", how="left")

data["vehicle_count"] = data["vehicle_count"].fillna(0)
data["congestion_score"] = data["congestion_score"].fillna(0)

print("Merged dataset:", len(data))

time_col = None
for candidate in ["event_time", "start_date", "end_date"]:
    if candidate in data.columns:
        time_col = candidate
        break

if time_col is None:
    raise KeyError("No timestamp column found. Expected one of: event_time, start_date, end_date.")

if "event_demand" not in data.columns:
    if "demand_score" in data.columns:
        data["event_demand"] = data["demand_score"]
    elif "estimated_passengers" in data.columns:
        data["event_demand"] = data["estimated_passengers"]
    else:
        raise KeyError("No demand column found. Expected event_demand, demand_score, or estimated_passengers.")

# Feature engineering
data["hour"] = pd.to_datetime(data[time_col], errors="coerce").dt.hour
data["day_of_week"] = pd.to_datetime(data[time_col], errors="coerce").dt.dayofweek

data["hour"] = data["hour"].fillna(12)
data["day_of_week"] = data["day_of_week"].fillna(3)

# Target variable
data["target_demand"] = (
    data["event_demand"]
    + data["vehicle_count"] * 2
    + data["congestion_score"] * 0.5
)

features = [
    "event_demand",
    "vehicle_count",
    "congestion_score",
    "hour",
    "day_of_week"
]

X = data[features]
y = data["target_demand"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

print("Training model...")

model = xgb.XGBRegressor(
    n_estimators=200,
    learning_rate=0.05,
    max_depth=6
)

model.fit(X_train, y_train)

preds = model.predict(X_test)

rmse = mean_squared_error(y_test, preds) ** 0.5

print("Model RMSE:", rmse)

model_path = os.path.join(BASE_DIR, "data", "models", "demand_predictor.pkl")

os.makedirs(os.path.dirname(model_path), exist_ok=True)

joblib.dump(model, model_path)

print("Model saved:", model_path)
