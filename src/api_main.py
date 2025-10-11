from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List
import asyncio
import time

app = FastAPI(title="Video Generation Backend", version="0.2.0")

# CORS for local dev
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health():
    return {"status": "ok"}

# --- In-memory job store (stub for dev) ---
class Job(BaseModel):
    id: str
    status: str = "queued"
    created_at: float = time.time()

jobs: Dict[str, Job] = {}
job_logs: Dict[str, List[str]] = {}
log_queues: Dict[str, asyncio.Queue] = {}

@app.post("/api/jobs")
async def create_job() -> Dict[str, str]:
    job_id = str(int(time.time() * 1000))
    jobs[job_id] = Job(id=job_id, status="running", created_at=time.time())
    job_logs[job_id] = ["Job created", "Starting pipeline..."]
    log_queues[job_id] = asyncio.Queue()
    async def produce_logs(jid: str):
        for i in range(1, 6):
            msg = f"step {i}/5 completed"
            job_logs[jid].append(msg)
            await log_queues[jid].put(msg)
            await asyncio.sleep(0.5)
        jobs[jid].status = "completed"
        await log_queues[jid].put("__DONE__")
    asyncio.create_task(produce_logs(job_id))
    return {"job_id": job_id}

@app.get("/api/jobs")
async def list_jobs():
    return {"jobs": [j.model_dump() for j in jobs.values()]}

@app.get("/api/jobs/recent")
async def recent_jobs(limit: int = 10):
    ids = sorted(jobs.keys(), reverse=True)[:limit]
    return {"job_ids": ids, "jobs": ids}

@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        return {"error": "not_found"}
    return job.model_dump()

@app.get("/api/jobs/{job_id}/logs")
async def get_logs(job_id: str, limit: int = 50):
    logs = job_logs.get(job_id, [])
    return {"job_id": job_id, "logs": logs[-limit:]}

@app.websocket("/api/jobs/{job_id}/ws")
async def job_ws(websocket: WebSocket, job_id: str):
    await websocket.accept()
    queue = log_queues.get(job_id)
    try:
        for line in job_logs.get(job_id, []):
            await websocket.send_text(line)
        if queue is None:
            await websocket.send_text("no-live-logs")
            await websocket.close()
            return
        while True:
            msg = await queue.get()
            if msg == "__DONE__":
                await websocket.send_text("done")
                await websocket.close()
                break
            await websocket.send_text(msg)
    except WebSocketDisconnect:
        pass
