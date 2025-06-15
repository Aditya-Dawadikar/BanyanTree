import os
import asyncio
from aiokafka import AIOKafkaConsumer
from datetime import datetime
from elasticsearch import Elasticsearch
from aiokafka.errors import GroupCoordinatorNotAvailableError
import logging
import traceback

logger = logging.getLogger("my_app")
logger.setLevel(logging.DEBUG)

async def wait_for_kafka(consumer):
    for i in range(10):  # Retry 10 times
        try:
            await consumer.start()
            print("[INFO] Kafka consumer started", flush=True)
            return
        except GroupCoordinatorNotAvailableError:
            print("[WARN] Kafka not ready yet, retrying...", flush=True)
            await asyncio.sleep(5)
    raise RuntimeError("Kafka not ready after multiple attempts", flush=True)

async def consume_logs(es: Elasticsearch):

    BOOSTRAP_SERVER = os.getenv("KAFKA_BOOTSTRAP_SERVERS","localhost:9093")

    logger.info(f"BOOTSTRAP_SERVER: {BOOSTRAP_SERVER}")

    consumer = AIOKafkaConsumer(
        "raft-logs", "store-logs",
        bootstrap_servers=BOOSTRAP_SERVER,
        group_id="sap_streamer_group",
        enable_auto_commit=True,
        auto_offset_reset="latest"  # or "earliest" if you want to start from the beginning
    )

    try:
        # await consumer.start()
        await wait_for_kafka(consumer)
        print("[INFO] Kafka consumer started and awaiting messages...", flush=True)

        async for msg in consumer:
            timestamp = datetime.fromtimestamp(msg.timestamp / 1000).isoformat() + "Z"
            print(f"[TOPIC: {msg.topic}]({timestamp}) {msg.value.decode('utf-8')}", flush=True)

            log_entry = {
                "timestamp": timestamp,
                "topic": msg.topic,
                "message": msg.value.decode('utf-8')
            }

            index_name = msg.topic
            es.index(index=index_name, document=log_entry)

            print(f"[ES] Indexed log into {index_name}: {log_entry}", flush=True)

    except asyncio.CancelledError:
        print("Kafka consumer received cancellation signal", flush=True)
    except Exception as e:
        print(f"Error in Kafka consumer: {str(e)}", flush=True)
        traceback.print_exc()
    finally:
        print("Stopping Kafka consumer...", flush=True)
        await consumer.stop()
        print("Kafka consumer stopped", flush=True)
