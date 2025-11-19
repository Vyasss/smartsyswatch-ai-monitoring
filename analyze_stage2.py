import pandas as pd
import matplotlib.pyplot as plt

CSV_FILE = "metrics_log.csv"


def main():
    print(f"Loading data from {CSV_FILE}...")
    df = pd.read_csv(CSV_FILE)

    # Convert timestamp column to datetime type
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    print("First 5 rows:")
    print(df.head())

    # Set timestamp as index (common in time series)
    df = df.set_index("timestamp")

    # Simple line plot of CPU percentage over time
    plt.figure()
    plt.plot(df.index, df["cpu_percent"])
    plt.xlabel("Time")
    plt.ylabel("CPU Usage (%)")
    plt.title("CPU Usage Over Time (Stage 2)")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
