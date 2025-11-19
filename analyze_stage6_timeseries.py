import pandas as pd
import matplotlib.pyplot as plt
import sqlalchemy as sa

DB_URL = "sqlite:///metrics.db"  # our SQLite DB in project root


def load_data():
    # Create SQLAlchemy engine
    engine = sa.create_engine(DB_URL)

    # Read entire metrics table, oldest first
    query = "SELECT * FROM metrics ORDER BY timestamp ASC"
    df = pd.read_sql(query, engine, parse_dates=["timestamp"])
    return df


def add_anomaly_flags(df, window_size=10, z_threshold=2.0):
    """
    Very simple anomaly detection:
    - Compute rolling mean & std of CPU
    - A point is "anomaly" if:
        cpu > rolling_mean + z_threshold * rolling_std
    """
    ts_df = df.copy()
    ts_df = ts_df.set_index("timestamp")

    # Rolling stats on CPU
    ts_df["cpu_roll_mean"] = ts_df["cpu_percent"].rolling(window=window_size).mean()
    ts_df["cpu_roll_std"] = ts_df["cpu_percent"].rolling(window=window_size).std()

    # Define upper threshold line
    ts_df["cpu_upper_threshold"] = ts_df["cpu_roll_mean"] + z_threshold * ts_df["cpu_roll_std"]

    # Anomaly flag (boolean)
    ts_df["is_anomaly"] = ts_df["cpu_percent"] > ts_df["cpu_upper_threshold"]

    return ts_df


def plot_cpu_with_anomalies(ts_df):
    plt.figure()

    # Plot CPU
    plt.plot(ts_df.index, ts_df["cpu_percent"], label="CPU (%)")

    # Plot rolling mean & threshold if available
    if "cpu_roll_mean" in ts_df.columns:
        plt.plot(ts_df.index, ts_df["cpu_roll_mean"], label="Rolling mean", linestyle="--")
    if "cpu_upper_threshold" in ts_df.columns:
        plt.plot(
            ts_df.index,
            ts_df["cpu_upper_threshold"],
            label="Upper threshold",
            linestyle=":"
        )

    # Scatter anomalies
    anomalies = ts_df[ts_df["is_anomaly"] == True]
    if not anomalies.empty:
        plt.scatter(
            anomalies.index,
            anomalies["cpu_percent"],
            marker="o",
            s=60,
            label="Anomaly",
        )

    plt.xlabel("Time")
    plt.ylabel("CPU Usage (%)")
    plt.title("CPU Usage with Simple Anomaly Detection (Stage 6)")
    plt.xticks(rotation=45)
    plt.legend()
    plt.tight_layout()
    plt.show()


def main():
    print("Loading data from metrics.db...")
    df = load_data()
    print(f"Loaded {len(df)} rows.")
    print(df.head())

    if len(df) < 20:
        print("Not enough data (<20 rows). Run the agent more to collect data.")
        return

    ts_df = add_anomaly_flags(df, window_size=10, z_threshold=2.0)

    # Print some anomalies in console
    anomalies = ts_df[ts_df["is_anomaly"] == True]
    print(f"\nDetected {len(anomalies)} anomaly points.")
    if not anomalies.empty:
        print(anomalies[["host", "cpu_percent"]].head())

    plot_cpu_with_anomalies(ts_df)


if __name__ == "__main__":
    main()
