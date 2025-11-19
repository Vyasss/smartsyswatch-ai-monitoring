import os

import pandas as pd
import sqlalchemy as sa
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error
import joblib

DB_URL = "sqlite:///../metrics.db"   
MODEL_PATH = "cpu_forecast_rf.pkl"

WINDOW_SIZE = 5      # how many past points to use
HORIZON_STEPS = 3    # predict 3 steps into the future


def load_data():
    engine = sa.create_engine(DB_URL)
    query = "SELECT timestamp, cpu_percent FROM metrics ORDER BY timestamp ASC"
    df = pd.read_sql(query, engine, parse_dates=["timestamp"])
    return df


def build_supervised(df: pd.DataFrame):
    """
    Turn a time series into supervised learning dataset.

    Features: cpu_{t-1}, cpu_{t-2}, ..., cpu_{t-WINDOW_SIZE}
    Target:   cpu_{t+HORIZON_STEPS}
    """
    s = df["cpu_percent"].values
    n = len(s)

    rows = []
    for t in range(WINDOW_SIZE, n - HORIZON_STEPS):
        past = s[t - WINDOW_SIZE:t]          # last WINDOW_SIZE points
        target = s[t + HORIZON_STEPS]        # future point
        rows.append(list(past) + [target])

    if not rows:
        return None, None

    cols = [f"cpu_t-{i}" for i in range(WINDOW_SIZE, 0, -1)] + [f"cpu_t+{HORIZON_STEPS}"]
    sup_df = pd.DataFrame(rows, columns=cols)

    X = sup_df.iloc[:, :-1].values
    y = sup_df.iloc[:, -1].values
    return X, y


def main():
    print("Loading data from metrics.db ...")
    df = load_data()
    print(f"Loaded {len(df)} rows.")

    if len(df) < 80:
        print("Not enough data (<80 rows). Run the agent more, then retry.")
        return

    X, y = build_supervised(df)
    if X is None:
        print("Could not build supervised dataset (not enough points).")
        return

    print(f"Supervised dataset: X={X.shape}, y={y.shape}")

    # Train / test split: last 20% as test
    split_idx = int(len(X) * 0.8)
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    print("Training RandomForestRegressor for CPU forecasting...")
    model = RandomForestRegressor(
        n_estimators=200,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    # Evaluate
    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    print(f"Test MAE: {mae:.3f} CPU percentage points")

    # Save model
    joblib.dump(model, MODEL_PATH)
    print(f"Saved forecast model to {MODEL_PATH}.")


if __name__ == "__main__":
    main()
