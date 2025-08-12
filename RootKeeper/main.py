from fastapi import FastAPI
from models import NodeRecord, InputNodeRecords
from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

MAX_WORKERS = 10

# node identity table
nodes = {}

def get_timestamp():
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

def get_timedelta(t2, t1):
    t2_datatime_obj = datetime.strptime(t2, "%Y-%m-%dT%H:%M:%SZ")
    t1_datatime_obj = datetime.strptime(t1, "%Y-%m-%dT%H:%M:%SZ")

    diff_secs = (t2_datatime_obj - t1_datatime_obj).total_seconds()
    return diff_secs

# Background thread that pings all registered nodes
def check_node_health(key,val):
        try:
            print(f"""[PING] {key}""")
            url = f"""{val.get("url")}/health"""
            res = requests.get(url, timeout=1)
            timestamp = get_timestamp()

            # update last seen
            nodes[key]["last_seen"] = timestamp

            if nodes[key]["is_alive"] == False:
                print(f"[Node Online] {key}")

            nodes[key]["is_alive"] = True

            print(f"""[ALIVE] {timestamp} | {key}:{res.status_code}""")        
        except Exception as e:
            # print(e)
            pass

        # mark node as dead
        now = get_timestamp()
        delta = get_timedelta(now, nodes[key]["last_seen"])
        if delta > 10:
            print(f"[DEAD] {key}")
            nodes[key]["is_alive"] = False

def ping_nodes():
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(check_node_health, key, val) for key,val in list(nodes.items())]
        for _ in as_completed(futures):
            pass


@asynccontextmanager
async def lifespan(app:FastAPI):
    print("[SYS] Starting Background Tasks")
    # start background task
    scheduler = BackgroundScheduler()
    scheduler.add_job(ping_nodes, 'interval', seconds=5, max_instances=5)
    scheduler.start()

    try:
        yield
    finally:
        # kill background task
        scheduler.shutdown()

app = FastAPI(lifespan=lifespan)

@app.post("/register")
def register_node(req: InputNodeRecords):
    timestamp = get_timestamp()

    for node in req.nodes:
        nodes[node.name] = {
            "url": node.url,
            "joined_at": timestamp,
            "last_seen": timestamp,
            "is_alive": False
        }

    return nodes

@app.get("/cluster")
def get_cluster():
    return nodes