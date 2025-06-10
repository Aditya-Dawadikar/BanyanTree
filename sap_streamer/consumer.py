import asyncio
from aiokafka import AIOKafkaConsumer
from datetime import datetime
from elasticsearch import Elasticsearch


async def consume_logs(es: Elasticsearch):
    consumer = AIOKafkaConsumer(
        "raft-logs", "store-logs",
        bootstrap_servers="localhost:9093",
        group_id="sap_streamer_group",
        enable_auto_commit=True,
        auto_offset_reset="latest"  # or "earliest" if you want to start from the beginning
    )

    try:
        await consumer.start()
        print("[INFO] Kafka consumer started and awaiting messages...")

        async for msg in consumer:
            timestamp = datetime.fromtimestamp(msg.timestamp / 1000).isoformat() + "Z"
            print(f"[TOPIC: {msg.topic}]({timestamp}) {msg.value.decode('utf-8')}")

            log_entry = {
                "timestamp": timestamp,
                "topic": msg.topic,
                "message": msg.value.decode('utf-8')
            }

            index_name = msg.topic
            es.index(index=index_name, document=log_entry)

            print(f"[ES] Indexed log into {index_name}: {log_entry}")

    except asyncio.CancelledError:
        print("Kafka consumer received cancellation signal")
    except Exception as e:
        print(f"Error in Kafka consumer: {str(e)}")
    finally:
        print("Stopping Kafka consumer...")
        await consumer.stop()
        print("Kafka consumer stopped")
