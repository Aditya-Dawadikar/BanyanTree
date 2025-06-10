#!/bin/bash

# Define broker and topics
KAFKA_BROKER="kafka:9092"
TOPICS=("raft-logs" "store-logs")  # Correct bash array syntax

# Wait until Kafka is up
echo "Waiting for Kafka to be ready..."
while ! kafka-topics --list --bootstrap-server $KAFKA_BROKER &>/dev/null; do   
  sleep 2
done

echo "Kafka is up!"

# Create topics if they don't exist
for TOPIC in "${TOPICS[@]}"; do
  echo "Checking if topic '$TOPIC' exists..."
  if kafka-topics --list --bootstrap-server $KAFKA_BROKER | grep -qw "$TOPIC"; then
      echo "Topic '$TOPIC' already exists"
  else
      echo "Creating topic: $TOPIC"
      kafka-topics --create --topic $TOPIC --bootstrap-server $KAFKA_BROKER --partitions 3 --replication-factor 1
      echo "Topic $TOPIC created."
  fi
done