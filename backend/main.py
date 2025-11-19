import json
import os
from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from kafka import KafkaProducer
from collections import defaultdict, deque
import numpy as np
import joblib

from .database import SessionLocal, engine, Base
from .models import Metrics as MetricsModel, Alert

# -------------------------------------------------------
# FastAPI: App + CORS
# -------------------------------------------------------

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create tables
Base.metadata.create_all(bind=engine)

# -------------------------------------------------------
# Load ML Models
# -------------------------------------------------------

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

FORECAST_WINDOW_SIZE = 5
FORECAST_THRESHOLD = 50.0  # predicted CPU above this => warning

# -------------------------------------------------------
# Kafka Producer
# -------------------------------------------------------

KAFKA_BOOTSTRAP_SERVERS = "kafka:29092"
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
        kafka_producer.flush()
    except Exception as e:
        print(f"[KAFKA] Failed to publish alert: {e}")




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




def build_iso_features(m: MetricsCreate):
    return [[m.cpu_percent, m.memory_percent, m.disk_percent]]


def get_recent_cpu_window(db: Session, host: str, window_size: int):
    rows = (
        db.query(MetricsModel)
        .filter(MetricsModel.host == host)
        .order_by(MetricsModel.timestamp.desc())
        .limit(window_size)
        .all()
    )

    if len(rows) < window_size:
        return None

    rows = rows[::-1]  # reverse to oldest first
    return [r.cpu_percent for r in rows]




MIN_REPORTABLE = 1.0
ROLLING_WINDOW = 10
Z_THRESH = 3.0
PERCENT_INCREASE = 1.5
PERSIST_COUNT = 2

_recent_values = defaultdict(lambda: deque(maxlen=ROLLING_WINDOW))
_persist_counts = defaultdict(int)



@app.get("/")
def root():
    return {
        "message": "System monitoring backend with DB + ML",
        "ml_anomaly_model_loaded": iso_forest_model is not None,
        "ml_forecast_model_loaded": forecast_model is not None,
    }


@app.post("/ingest")
def ingest_metrics(
    metrics: MetricsCreate,
    db: Session = Depends(get_db),
):
    ts = datetime.fromisoformat(metrics.timestamp)

    # 1) Store metric
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

    host = metrics.host
    value = metrics.cpu_percent
    metric_name = "cpu_percent"

    # -------------------------------------------------------
    # Realistic alerting logic starts now
    # -------------------------------------------------------

    # Ignore tiny CPU values (noise)
    if value < MIN_REPORTABLE:
        return {"status": "ok", "note": "Value too small to evaluate"}

    # Update rolling window
    _recent_values[host].append(value)
    vals = list(_recent_values[host])

    mean = float(np.mean(vals)) if len(vals) > 1 else None
    std = float(np.std(vals)) if len(vals) > 1 else None

    z_score = None
    pct_inc = None
    if mean and std and std > 0:
        z_score = (value - mean) / std
        pct_inc = value / mean if mean > 0 else None

    # ML anomaly detection
    ml_anom = False
    ml_score = None

    if iso_forest_model is not None:
        feats = build_iso_features(metrics)
        try:
            if hasattr(iso_forest_model, "decision_function"):
                ml_score = float(iso_forest_model.decision_function(feats))
                ml_anom = ml_score < -0.1
            else:
                ml_anom = iso_forest_model.predict(feats)[0] == -1
        except:
            ml_anom = False

    # Statistical deviation
    stat_flag = False
    if z_score is not None and z_score >= Z_THRESH:
        stat_flag = True
    if pct_inc is not None and pct_inc >= PERCENT_INCREASE:
        stat_flag = True

    candidate = ml_anom and stat_flag

    # Persistence check
    if candidate:
        _persist_counts[host] += 1
    else:
        _persist_counts[host] = 0

    # Fire alert only after persistence is met
    if _persist_counts[host] >= PERSIST_COUNT:
        # Severity scale by CPU %
        if value >= 80:
            severity = "CRITICAL"
        elif value >= 60:
            severity = "HIGH"
        elif value >= 40:
            severity = "MEDIUM"
        else:
            severity = "LOW"

        # Forecast influence
        forecast_pred = None
        if forecast_model is not None:
            window = get_recent_cpu_window(db, host, FORECAST_WINDOW_SIZE)
            if window is not None:
                try:
                    forecast_pred = float(forecast_model.predict([window])[0])
                    if forecast_pred >= 80:
                        severity = "CRITICAL"
                    elif forecast_pred >= 60 and severity != "CRITICAL":
                        severity = "HIGH"
                except:
                    forecast_pred = None

        # Create alert in DB
        alert = Alert(
            timestamp=ts,
            host=host,
            metric=metric_name,
            value=value,
            alert_type="ml_stat_combined",
            severity=severity,
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)

        # Publish to Kafka
        alert_event = {
            "id": alert.id,
            "timestamp": alert.timestamp.isoformat(),
            "host": alert.host,
            "metric": alert.metric,
            "value": float(alert.value),
            "severity": alert.severity,
            "ml_score": ml_score,
            "z_score": z_score,
            "pct_increase": pct_inc,
            "forecast_pred": forecast_pred,
        }
        publish_alert_to_kafka(alert_event)

        print(f"[ALERT] {host} val={value:.2f} sev={severity} ml={ml_score} z={z_score} pct={pct_inc}")
        _persist_counts[host] = 0

    return {"status": "ok"}


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
