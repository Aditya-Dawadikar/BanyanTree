import asyncio
from aiokafka import AIOKafkaProducer
from typing import Optional

class BanyanCoreLogger:
    def __init__(self, node_id: str, bootstrap_servers: str = "localhost:9093"):
        self.node_id = node_id
        self.bootstrap_servers = bootstrap_servers
        self.producer: Optional[AIOKafkaProducer] = None

    async def start_producer(self) -> None:
        """Initialize and start the Kafka producer"""
        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: v.encode('utf-8')  # Convert strings to bytes
        )
        await self.producer.start()

    async def stop_producer(self) -> None:
        """Stop the Kafka producer"""
        if self.producer is not None:
            await self.producer.stop()
            self.producer = None

    async def log(self, topic: str, msg: str) -> None:
        """Send a log message to Kafka"""
        if self.producer is None:
            raise RuntimeError("Producer is not started. Call start_producer() first.")

        try:
            print(msg)
            msg = f"[{self.node_id}] | {msg}" 
            await self.producer.send_and_wait(topic=topic, value=msg)
        except Exception as e:
            # You might want to add more specific exception handling here
            print(f"Failed to send log message: {e}")
            raise

    async def __aenter__(self):
        await self.start_producer()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop_producer()