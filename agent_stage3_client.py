import time
import socket
from datetime import datetime

import psutil
import requests

BACKEND_URL = "http://127.0.0.1:8000/ingest"


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


def main():
    print("Stage 3 agent started. Sending metrics to backend...")
    print("This will send 20 samples and then stop.\n")

    for i in range(20):
        metrics = collect_metrics()
        try:
            response = requests.post(BACKEND_URL, json=metrics, timeout=3)
            if response.status_code == 200:
                print(f"[{i+1:02d}/20] Sent OK | CPU={metrics['cpu_percent']}%")
            else:
                print(f"[{i+1:02d}/20] ERROR status={response.status_code}")
        except Exception as e:
            print(f"[{i+1:02d}/20] Failed to send: {e}")

        time.sleep(4)

    print("\nDone sending metrics for Stage 3.")


if __name__ == "__main__":
    main()
