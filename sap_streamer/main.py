import uvicorn
from fastapi import FastAPI
import asyncio
from contextlib import asynccontextmanager
from typing import List
from routes import get_cluster_router
from consumer import consume_logs

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
    task_manager.add_task(asyncio.create_task(consume_logs()))
    
    yield
    
    # Shutdown
    print("[SHUTDOWN] Stopping all background tasks...")
    await task_manager.cancel_all()
    print("[SHUTDOWN] All background tasks stopped")

app = FastAPI(lifespan=lifespan)

app.include_router(get_cluster_router(),
                   prefix="/cluster")

if __name__=="__main__":
    uvicorn.run("main:app",
                host="0.0.0.0",
                port=3000,
                reload=True)
