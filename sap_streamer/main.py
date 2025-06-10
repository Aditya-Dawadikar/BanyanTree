import uvicorn
from fastapi import FastAPI
import asyncio
from aiokafka import AIOKafkaConsumer
from aiokafka.helpers import create_ssl_context
from aiokafka.structs import TopicPartition
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from typing import List

class BackgroundTaskManager:
    def __init__(self):
        self.tasks: List[asyncio.Task] = []
    
    def add_task(self, task: asyncio.Task):
        self.tasks.append(task)
    
    async def cancel_all(self):
        for task in self.tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass  # Expected for cancelled tasks

task_manager = BackgroundTaskManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("[STARTUP] Initializing background tasks...")
    task_manager.add_task(asyncio.create_task(consume_raft_logs()))
    # Add more tasks here as needed
    # task_manager.add_task(asyncio.create_task(other_background_task()))
    
    yield
    
    # Shutdown
    print("[SHUTDOWN] Stopping all background tasks...")
    await task_manager.cancel_all()
    print("[SHUTDOWN] All background tasks stopped")

app = FastAPI(lifespan=lifespan)

async def consume_raft_logs():
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
            timestamp = datetime.fromtimestamp(msg.timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')
            print(f"[TOPIC: {msg.topic}]({timestamp}) {msg.value.decode('utf-8')}")

    except asyncio.CancelledError:
        print("Kafka consumer received cancellation signal")
    except Exception as e:
        print(f"Error in Kafka consumer: {str(e)}")
    finally:
        print("Stopping Kafka consumer...")
        await consumer.stop()
        print("Kafka consumer stopped")


# Example additional background task
# async def other_background_task():
#     try:
#         while True:
#             print("Background task running...")
#             await asyncio.sleep(5)
#     except asyncio.CancelledError:
#         print("Background task cancelled")

if __name__=="__main__":
    uvicorn.run("main:app",
                host="0.0.0.0",
                port=3000,
                reload=True)
