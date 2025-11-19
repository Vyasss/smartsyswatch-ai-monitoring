from kafka import KafkaConsumer
import json

KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"  # host listener from docker-compose
KAFKA_ALERTS_TOPIC = "alerts"


def send_notification(alert):
    ts = alert["timestamp"]
    host = alert["host"]
    metric = alert["metric"]
    value = alert["value"]
    alert_type = alert["alert_type"]
    severity = alert["severity"]

    print(
        f"[ALERT] {ts} | host={host} | metric={metric} | "
        f"value={value:.2f} | type={alert_type} | severity={severity}"
    )


def main():
    print(
        f"Connecting Kafka consumer to {KAFKA_BOOTSTRAP_SERVERS}, "
        f"topic={KAFKA_ALERTS_TOPIC}"
    )

    consumer = KafkaConsumer(
        KAFKA_ALERTS_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        auto_offset_reset="latest",   # read only new alerts
        enable_auto_commit=True,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        group_id="alert_notifier_group",
    )

    print("Waiting for alerts... (Ctrl+C to stop)\n")

    try:
        for msg in consumer:
            alert = msg.value
            send_notification(alert)
    except KeyboardInterrupt:
        print("Stopping consumer...")
    finally:
        consumer.close()


if __name__ == "__main__":
    main()
