from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Dict, List
import asyncio
import time
from pathlib import Path
import base64
import urllib.request

app = FastAPI(title="Video Generation Backend", version="0.3.0")

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

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
(OUTPUT_DIR / "slides").mkdir(parents=True, exist_ok=True)
(OUTPUT_DIR / "videos").mkdir(parents=True, exist_ok=True)

# Serve /static from OUTPUT_DIR
app.mount("/static", StaticFiles(directory=str(OUTPUT_DIR)), name="static")

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
latest_outputs: Dict[str, str | list[str] | None] = {}

SLIDE_PX = base64.b64decode(
    b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9eHEcS8AAAAASUVORK5CYII="
)  # 1x1 PNG

async def ensure_demo_assets():
    # slides
    slides = []
    for i in range(1, 7):
        p = OUTPUT_DIR / "slides" / f"slide_{i}.png"
        if not p.exists():
            p.write_bytes(SLIDE_PX)
        slides.append(str(Path("output") / "slides" / p.name))

    # subtitle
    subtitle = OUTPUT_DIR / "videos" / "sample.vtt"
    if not subtitle.exists():
        subtitle.write_text("""WEBVTT\n\n00:00.000 --> 00:02.000\nDemo subtitle line\n""")
    subtitle_rel = str(Path("output") / "videos" / subtitle.name)

    # video: try download a small mp4; fallback to empty if fails
    video = OUTPUT_DIR / "videos" / "sample.mp4"
    if not video.exists():
        try:
            url = "https://filesamples.com/samples/video/mp4/sample_640x360.mp4"
            urllib.request.urlretrieve(url, str(video))
        except Exception:
            # fallback to zero-byte placeholder (may not play) but keeps URL structure
            video.write_bytes(b"")
    video_rel = str(Path("output") / "videos" / video.name)

    return {"video": video_rel, "subtitle": subtitle_rel, "slides": slides, "pptx": None}

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
        jobs[jid].status = "succeeded"
        # create demo assets and set latest outputs
        out = await ensure_demo_assets()
        latest_outputs.clear()
        latest_outputs.update(out)
        await log_queues[jid].put("__DONE__")

    asyncio.create_task(produce_logs(job_id))
    return {"job_id": job_id}

@app.get("/api/jobs")
async def list_jobs():
    return {"jobs": [j.model_dump() for j in jobs.values()]}

@app.get("/api/jobs/recent")
async def recent_jobs(limit: int = 10):
    ids = sorted(jobs.keys(), reverse=True)[:limit]
    # return list of job objects for better compatibility
    return [jobs[i].model_dump() for i in ids if i in jobs]

@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="not_found")
    return job.model_dump()

@app.get("/api/jobs/{job_id}/logs")
async def get_logs(job_id: str, limit: int = 50):
    logs = job_logs.get(job_id, [])
    return {"job_id": job_id, "logs": logs[-limit:]}

@app.get("/api/outputs/latest")
async def outputs_latest():
    if not latest_outputs:
        raise HTTPException(status_code=404, detail="no_outputs")
    return latest_outputs

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
