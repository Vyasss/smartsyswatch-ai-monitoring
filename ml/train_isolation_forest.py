import os

import pandas as pd
import sqlalchemy as sa
from sklearn.ensemble import IsolationForest
import joblib

DB_URL = "sqlite:///../metrics.db"  # go one level up from ml/ to project root
MODEL_PATH = "iso_forest_cpu.pkl"


def load_data():
    engine = sa.create_engine(DB_URL)
    query = "SELECT * FROM metrics ORDER BY timestamp ASC"
    df = pd.read_sql(query, engine, parse_dates=["timestamp"])
    return df


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    For now we keep features simple:
    - cpu_percent
    - memory_percent
    - disk_percent
    Later we could add rolling stats / deltas.
    """
    features = df[["cpu_percent", "memory_percent", "disk_percent"]].copy()
    return features


def main():
    print("Loading data from metrics.db ...")
    df = load_data()
    print(f"Loaded {len(df)} rows.")

    if len(df) < 50:
        print("Not enough data (<50 rows). Run the agent more, then retry.")
        return

    X = build_features(df)

    print("Training Isolation Forest model...")
    # contamination is expected proportion of anomalies (tunable)
    model = IsolationForest(
        n_estimators=200,
        contamination=0.05,
        random_state=42,
    )
    model.fit(X)

    # Use the model on the training data just to see how many it flags
    preds = model.predict(X)  # 1 = normal, -1 = anomaly
    anomaly_mask = preds == -1
    num_anomalies = anomaly_mask.sum()

    print(f"Model trained.")
    print(f"Flagged {num_anomalies} / {len(X)} points as anomalies "
          f"({num_anomalies / len(X) * 100:.2f}%).")

    # Save model
    joblib.dump(model, MODEL_PATH)
    print(f"Saved model to {MODEL_PATH}.")


if __name__ == "__main__":
    main()
