import time
import socket
from datetime import datetime
import csv
import os

import psutil


CSV_FILE = "metrics_log.csv"


def collect_metrics():
    host = socket.gethostname()
    cpu = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory().percent
    disk = psutil.disk_usage("/").percent
    net_io = psutil.net_io_counters()

    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "host": host,
        "cpu_percent": cpu,
        "memory_percent": memory,
        "disk_percent": disk,
        "net_bytes_sent": net_io.bytes_sent,
        "net_bytes_recv": net_io.bytes_recv,
    }


def init_csv(file_path):
    """Create CSV with header if it doesn't exist."""
    file_exists = os.path.isfile(file_path)
    if not file_exists:
        with open(file_path, mode="w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "timestamp",
                    "host",
                    "cpu_percent",
                    "memory_percent",
                    "disk_percent",
                    "net_bytes_sent",
                    "net_bytes_recv",
                ]
            )


def append_metrics(file_path, metrics: dict):
    """Append one row of metrics to CSV."""
    with open(file_path, mode="a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                metrics["timestamp"],
                metrics["host"],
                metrics["cpu_percent"],
                metrics["memory_percent"],
                metrics["disk_percent"],
                metrics["net_bytes_sent"],
                metrics["net_bytes_recv"],
            ]
        )


def main():
    init_csv(CSV_FILE)
    print(f"Logging metrics to {CSV_FILE} (Stage 2)...")
    print("This will run 50 iterations and then stop.\n")

    for i in range(50):  # collect 50 samples
        metrics = collect_metrics()
        append_metrics(CSV_FILE, metrics)
        print(
            f"[{i+1:02d}/50] Logged: "
            f"CPU={metrics['cpu_percent']}% | "
            f"RAM={metrics['memory_percent']}% | "
            f"Disk={metrics['disk_percent']}%"
        )
        time.sleep(4)  # 4 seconds pause between samples

    print("\nDone logging! You should now have metrics_log.csv in this folder.")


if __name__ == "__main__":
    main()
