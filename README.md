\#  SmartSysWatch – AI Monitoring



A real-time \*\*AI-powered system monitoring platform\*\* that detects anomalies using Machine Learning and streams alerts through Kafka — similar to what Netflix, Uber \& Meta use in production.



---



\## Overview



SmartSysWatch continuously tracks:



\- CPU usage

\- RAM utilization

\- Disk usage

\- Network IO



A Machine Learning model (IsolationForest) analyzes incoming data and \*\*predicts\*\* anomalies and future usage trends.  

Alerts are published to \*\*Apache Kafka\*\* and consumed by a notifier service.



Perfect demonstration of \*\*MLOps + Distributed Systems + Real-Time AI\*\* skills.



---



\##  Key Features



| Feature | Description |

|--------|-------------|

| Real-time monitoring agent | Sends live system metrics every few seconds |

| ML anomaly detection | IsolationForest flags abnormal spikes |

| Forecasting model | Predicts high future load events |

| Kafka streaming | Distributed event-based alerting |

| Backend API | FastAPI for metric ingestion \& querying |

| Database storage | SQLite (can easily upgrade to PostgreSQL) |

| Docker-ready | Backend + Kafka via Docker Compose |

| Live visualization (coming next) | Grafana dashboards |



---



\## 🧩 Tech Stack



| Layer | Tools |

|------|-------|

| ML Engine | Scikit-Learn (IsolationForest, Forecasting) |

| Programming | Python |

| APIs | FastAPI |

| Streaming Data | Apache Kafka + Zookeeper |

| Storage | SQLite (default) |

| Deployment | Docker \& Docker Compose |

| Visualization \*(soon)\* | Grafana |



---



&nbsp;\*\*How to Run Locally



1️⃣ Start Kafka + Zookeeper



```bash

docker compose -f kafka-compose.yml up -d

2️⃣ Build \& run backend API

docker build -t monitoring-backend .

docker network create monitoring-net

docker run -p 8000:8000 --name monitoring-backend-container --network monitoring-n

3️⃣ Start alert notifier

python alert\_notifier.py



4️⃣ Start monitoring agent

python agent\_stage3\_client.py





Backend health check:



http://127.0.0.1:8000/





You should see:



{

&nbsp; "message": "System monitoring backend with DB + ML",

&nbsp; "ml\_anomaly\_model\_loaded": true,

&nbsp; "ml\_forecast\_model\_loaded": true

}



\*\*Author



Chetan — AI / ML Engineer

🔗 GitHub: https://github.com/

Vyasss

🔗 LinkedIn: https://linkedin.com/in/

linkedin.com/in/chetanvyas20







