import time
import socket
from datetime import datetime

import psutil
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


BACKEND_URL = "http://127.0.0.1:8000/ingest"


def make_session(retries=3, backoff=0.6):
    s = requests.Session()
    retry = Retry(
        total=retries,
        backoff_factor=backoff,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["POST", "GET"]
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    return s

_session = make_session(retries=4, backoff=0.8)

def post_with_retries(url, json_payload, timeout=10):
    """
    Returns (True, elapsed_seconds) on success,
            (False, exception) on failure.
    """
    try:
        t0 = time.time()
        r = _session.post(url, json=json_payload, timeout=timeout)
        r.raise_for_status()
        return True, (time.time() - t0)
    except Exception as e:
        return False, e

# --- metric collector ---
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
        ok, info = post_with_retries(BACKEND_URL, metrics, timeout=10)
        if ok:
            print(f"[{i+1:02d}/20] Sent OK | CPU={metrics['cpu_percent']}% | took {info:.2f}s")
        else:
            print(f"[{i+1:02d}/20] Failed to send: {info}")

        time.sleep(4)

    print("\nDone sending metrics for Stage 3.")


if __name__ == "__main__":
    main()
