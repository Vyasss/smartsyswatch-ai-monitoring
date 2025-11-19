import json
from kafka import KafkaProducer
from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .database import SessionLocal, engine, Base
from .models import Metrics as MetricsModel, Alert

import joblib
import os

app = FastAPI()

# Allow requests from browser (for dashboard)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

# ----------------- Load ML models -----------------

ISO_MODEL_PATH = os.path.join("ml", "iso_forest_cpu.pkl")
FORECAST_MODEL_PATH = os.path.join("ml", "cpu_forecast_rf.pkl")

iso_forest_model = None
forecast_model = None

if os.path.exists(ISO_MODEL_PATH):
    try:
        iso_forest_model = joblib.load(ISO_MODEL_PATH)
        print(f"[ML] Loaded Isolation Forest model from {ISO_MODEL_PATH}")
    except Exception as e:
        print(f"[ML] Failed to load Isolation Forest model: {e}")
else:
    print(f"[ML] Isolation Forest model not found at {ISO_MODEL_PATH}")

if os.path.exists(FORECAST_MODEL_PATH):
    try:
        forecast_model = joblib.load(FORECAST_MODEL_PATH)
        print(f"[ML] Loaded CPU forecast model from {FORECAST_MODEL_PATH}")
    except Exception as e:
        print(f"[ML] Failed to load forecast model: {e}")
else:
    print(f"[ML] Forecast model not found at {FORECAST_MODEL_PATH}")

# Forecast config – keep in sync with train_cpu_forecast.py
FORECAST_WINDOW_SIZE = 5
FORECAST_THRESHOLD = 50.0  # predicted CPU above this => early warning

# ----------------- Kafka producer for alerts -----------------

KAFKA_BOOTSTRAP_SERVERS = "kafka:29092"  # internal listener, from inside Docker network
KAFKA_ALERTS_TOPIC = "alerts"

kafka_producer = None
try:
    kafka_producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        retries=3,
    )
    print(f"[KAFKA] Connected to {KAFKA_BOOTSTRAP_SERVERS}, topic={KAFKA_ALERTS_TOPIC}")
except Exception as e:
    print(f"[KAFKA] Failed to create producer: {e}")

def publish_alert_to_kafka(alert_dict: dict):
    if kafka_producer is None:
        return
    try:
        kafka_producer.send(KAFKA_ALERTS_TOPIC, alert_dict)
        kafka_producer.flush()  # Good for demo visibility
    except Exception as e:
        print(f"[KAFKA] Failed to publish alert: {e}")

# ----------------- Schemas & DB deps -----------------

class MetricsCreate(BaseModel):
    timestamp: str
    host: str
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    net_bytes_sent: int
    net_bytes_recv: int


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ----------------- Helpers -----------------

def build_iso_features(m: MetricsCreate):
    """Features for Isolation Forest (same as training)."""
    return [[m.cpu_percent, m.memory_percent, m.disk_percent]]


def get_recent_cpu_window(db: Session, host: str, window_size: int):
    """
    Get last `window_size` cpu_percent values for this host, oldest -> newest.
    Returns list[float] or None if not enough data.
    """
    rows = (
        db.query(MetricsModel)
        .filter(MetricsModel.host == host)
        .order_by(MetricsModel.timestamp.desc())
        .limit(window_size)
        .all()
    )
    if len(rows) < window_size:
        return None

    # rows are newest -> oldest; reverse to oldest -> newest
    rows = rows[::-1]
    return [r.cpu_percent for r in rows]

# ----------------- Routes -----------------

@app.get("/")
def root():
    return {
        "message": "System monitoring backend with DB + ML (IsolationForest + Forecast) (Stage 12)",
        "ml_anomaly_model_loaded": iso_forest_model is not None,
        "ml_forecast_model_loaded": forecast_model is not None,
    }


@app.post("/ingest")
def ingest_metrics(
    metrics: MetricsCreate,
    db: Session = Depends(get_db),
):
    ts = datetime.fromisoformat(metrics.timestamp)

    # 1) Store metrics
    row = MetricsModel(
        timestamp=ts,
        host=metrics.host,
        cpu_percent=metrics.cpu_percent,
        memory_percent=metrics.memory_percent,
        disk_percent=metrics.disk_percent,
        net_bytes_sent=metrics.net_bytes_sent,
        net_bytes_recv=metrics.net_bytes_recv,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

        # 2) ML anomaly detection (Isolation Forest)
    if iso_forest_model is not None:
        iso_features = build_iso_features(metrics)
        pred = iso_forest_model.predict(iso_features)[0]  # 1 = normal, -1 = anomaly
        if pred == -1:
            alert = Alert(
                timestamp=ts,
                host=metrics.host,
                metric="cpu_percent",
                value=metrics.cpu_percent,
                alert_type="ml_anomaly",
                severity="high",
            )
            db.add(alert)
            db.commit()
            db.refresh(alert)

            alert_event = {
                "id": alert.id,
                "timestamp": alert.timestamp.isoformat(),
                "host": alert.host,
                "metric": alert.metric,
                "value": float(alert.value),
                "alert_type": alert.alert_type,
                "severity": alert.severity,
            }
            publish_alert_to_kafka(alert_event)

            print(
                f"[ML ALERT] (Anomaly) host={metrics.host} "
                f"CPU={metrics.cpu_percent:.2f} flagged by Isolation Forest"
            )


        # 3) Forecast-based early warning
    if forecast_model is not None:
        window = get_recent_cpu_window(db, metrics.host, FORECAST_WINDOW_SIZE)
        if window is not None:
            X = [window]
            try:
                predicted_cpu = float(forecast_model.predict(X)[0])

                if predicted_cpu > FORECAST_THRESHOLD:
                    alert = Alert(
                        timestamp=ts,
                        host=metrics.host,
                        metric="cpu_percent_forecast",
                        value=predicted_cpu,
                        alert_type="forecast_high",
                        severity="high",
                    )
                    db.add(alert)
                    db.commit()
                    db.refresh(alert)

                    alert_event = {
                        "id": alert.id,
                        "timestamp": alert.timestamp.isoformat(),
                        "host": alert.host,
                        "metric": alert.metric,
                        "value": float(alert.value),
                        "alert_type": alert.alert_type,
                        "severity": alert.severity,
                    }
                    publish_alert_to_kafka(alert_event)

                    print(
                        f"[ML ALERT] (Forecast) host={metrics.host} "
                        f"predicted CPU={predicted_cpu:.2f} > {FORECAST_THRESHOLD}"
                    )
            except Exception as e:
                print(f"[ML] Forecast prediction failed: {e}")




@app.get("/metrics")
def get_metrics(
    host: Optional[str] = None,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    query = db.query(MetricsModel)
    if host:
        query = query.filter(MetricsModel.host == host)

    rows: List[MetricsModel] = (
        query.order_by(MetricsModel.timestamp.desc()).limit(limit).all()
    )

    result = []
    for r in rows:
        result.append(
            {
                "id": r.id,
                "timestamp": r.timestamp.isoformat(),
                "host": r.host,
                "cpu_percent": r.cpu_percent,
                "memory_percent": r.memory_percent,
                "disk_percent": r.disk_percent,
                "net_bytes_sent": r.net_bytes_sent,
                "net_bytes_recv": r.net_bytes_recv,
            }
        )

    return {"count": len(result), "metrics": result}


@app.get("/alerts")
def get_alerts(limit: int = 10, db: Session = Depends(get_db)):
    rows = (
        db.query(Alert)
        .order_by(Alert.timestamp.desc())
        .limit(limit)
        .all()
    )

    result = []
    for r in rows:
        result.append(
            {
                "id": r.id,
                "timestamp": r.timestamp.isoformat(),
                "host": r.host,
                "metric": r.metric,
                "value": r.value,
                "alert_type": r.alert_type,
                "severity": r.severity,
            }
        )

    return {"count": len(result), "alerts": result}
