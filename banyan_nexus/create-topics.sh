#!/bin/bash

KAFKA_BROKER="kafka:9092"
TOPICS=("raft-logs" "store-logs")
RETENTION_MS="1800000"  # 30 minutes
PARTITIONS=3
REPLICATION_FACTOR=1

# Wait until Kafka is ready
echo "Waiting for Kafka at $KAFKA_BROKER..."
for i in {1..30}; do
  kafka-topics --list --bootstrap-server "$KAFKA_BROKER" &>/dev/null && break
  echo "Kafka not ready, retrying ($i/30)..."
  sleep 2
done

if [ $i -eq 30 ]; then
  echo "Kafka not reachable after 30 attempts. Exiting."
  exit 1
fi
echo "Kafka is ready."

# Ensure topics exist and have correct config
for TOPIC in "${TOPICS[@]}"; do
  echo "Checking topic: $TOPIC"
  if kafka-topics --list --bootstrap-server "$KAFKA_BROKER" | grep -qw "$TOPIC"; then
    echo "Topic '$TOPIC' exists. Updating retention.ms..."
    kafka-configs --alter --topic "$TOPIC" --bootstrap-server "$KAFKA_BROKER" \
      --add-config "retention.ms=$RETENTION_MS"
  else
    echo "Creating topic '$TOPIC'..."
    kafka-topics --create \
      --topic "$TOPIC" \
      --bootstrap-server "$KAFKA_BROKER" \
      --partitions "$PARTITIONS" \
      --replication-factor "$REPLICATION_FACTOR" \
      --config "retention.ms=$RETENTION_MS"
  fi
done

echo "Topic setup complete."
exit 0
