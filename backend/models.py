from sqlalchemy import Column, Integer, String, Float, BigInteger, DateTime
from .database import Base


class Metrics(Base):
    __tablename__ = "metrics"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, index=True)
    host = Column(String, index=True)
    cpu_percent = Column(Float)
    memory_percent = Column(Float)
    disk_percent = Column(Float)
    net_bytes_sent = Column(BigInteger)
    net_bytes_recv = Column(BigInteger)


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, index=True)
    host = Column(String, index=True)
    metric = Column(String)       # e.g. "cpu_percent"
    value = Column(Float)
    alert_type = Column(String)   # e.g. "anomaly"
    severity = Column(String)     # e.g. "high"
