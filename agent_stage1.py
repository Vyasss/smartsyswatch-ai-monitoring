import time
import socket
from datetime import datetime

import psutil  # make sure psutil is installed

def collect_metrics():
    """Collect basic system metrics and return as a dictionary."""
    host = socket.gethostname()
    cpu = psutil.cpu_percent(interval=1)  # % CPU over 1 second
    memory = psutil.virtual_memory().percent  # % RAM used
    disk = psutil.disk_usage("/").percent  # % Disk used on root
    net_io = psutil.net_io_counters()

    metrics = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "host": host,
        "cpu_percent": cpu,
        "memory_percent": memory,
        "disk_percent": disk,
        "net_bytes_sent": net_io.bytes_sent,
        "net_bytes_recv": net_io.bytes_recv,
    }
    return metrics

def main():
    print("Starting simple system monitor (Stage 1)...")
    print("Press Ctrl+C to stop.\n")

    while True:
        metrics = collect_metrics()
        # Pretty print the metrics
        print(
            f"[{metrics['timestamp']}] "
            f"Host={metrics['host']} | "
            f"CPU={metrics['cpu_percent']}% | "
            f"RAM={metrics['memory_percent']}% | "
            f"Disk={metrics['disk_percent']}% | "
            f"Net(sent={metrics['net_bytes_sent']}, recv={metrics['net_bytes_recv']})"
        )
        time.sleep(4)  # wait 4 seconds before collecting again

if __name__ == "__main__":
    main()
