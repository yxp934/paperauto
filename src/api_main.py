from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Dict, List, Optional
import asyncio
import time
from pathlib import Path
import base64
import urllib.request
import re
import subprocess
import os
from datetime import datetime

# Load .env early to ensure API keys present
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

app = FastAPI(title="Video Generation Backend", version="0.4.0")
# Real pipeline entry points (reconstructed)
from src.main import run_demo_mode, run_complete_pipeline, process_single_paper, run_slides_only


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

# --- In-memory job store ---
class Job(BaseModel):
    id: str
    status: str = "queued"
    created_at: float = time.time()
    mode: str | None = None
    paper_id: str | None = None

class JobCreate(BaseModel):
    mode: str
    paper_id: str | None = None
    options: dict | None = None
    max_papers: int | None = None

jobs: Dict[str, Job] = {}
job_logs: Dict[str, List[str]] = {}
log_queues: Dict[str, asyncio.Queue] = {}
latest_outputs: Dict[str, str | list[str] | None] = {}

# Utils
def _now_ts() -> str:
    return datetime.now().strftime('%Y%m%d_%H%M%S')

def _sanitize(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", s)[:80]

def _rel(path: Path) -> str:
    # Return path under output/ for /static
    try:
        return str(Path("output") / path.relative_to(OUTPUT_DIR))
    except Exception:
        return str(path)

async def _log(jid: str, message: str):
    job_logs.setdefault(jid, []).append(message)
    q = log_queues.get(jid)
    if q:
        await q.put(message)

def _write_text_slide(title: str, bullets: list[str], out: Path, size=(1920,1080)):
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new('RGB', size, color=(242,242,242))
    draw = ImageDraw.Draw(img)
    try:
        font_title = ImageFont.truetype('Arial Unicode.ttf', 64)
        font_bullet = ImageFont.truetype('Arial Unicode.ttf', 40)
    except Exception:
        font_title = ImageFont.load_default()
        font_bullet = ImageFont.load_default()
    draw.text((80, 80), title[:120], fill=(39,28,33), font=font_title)
    y = 180
    for b in bullets[:8]:
        draw.text((120, y), f"• {b[:140]}", fill=(39,28,33), font=font_bullet)
        y += 64
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(out), 'PNG', optimize=True)

def _compose_video_ffmpeg(slides: list[Path], out_path: Path, per_sec: float = 3.0) -> bool:
    try:
        # create list file
        lst = out_path.parent / f"list_{out_path.stem}.txt"
        with open(lst, 'w') as f:
            for p in slides:
                ap = p.resolve().as_posix()
                f.write(f"file '{ap}'\n")
                f.write(f"duration {per_sec}\n")
            # repeat last frame for proper duration
            if slides:
                ap = slides[-1].resolve().as_posix()
                f.write(f"file '{ap}'\n")
        cmd = [
            'ffmpeg','-y','-f','concat','-safe','0','-i', str(lst),
            '-vf','scale=1920:1080,format=yuv420p','-pix_fmt','yuv420p',
            '-movflags','+faststart', str(out_path)
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except Exception:
        return False

def _scan_latest_outputs() -> Dict[str, str | list[str] | None]:
    vids = [p for p in (OUTPUT_DIR/"videos").glob('*.mp4') if p.name != 'sample.mp4']
    subs = list((OUTPUT_DIR/"videos").glob('*.vtt')) + list((OUTPUT_DIR/"videos").glob('*.srt'))
    slides = list((OUTPUT_DIR/"slides").glob('*.png'))
    latest_video = max(vids, key=lambda p: p.stat().st_mtime, default=None)
    latest_sub = max(subs, key=lambda p: p.stat().st_mtime, default=None)
    # choose slides from last hour as latest set
    now = time.time()
    recent_slides = [p for p in slides if now - p.stat().st_mtime < 3600]
    recent_slides.sort(key=lambda p: p.stat().st_mtime)
    return {
        'video': _rel(latest_video) if latest_video else None,
        'subtitle': _rel(latest_sub) if latest_sub else None,
        'slides': [_rel(p) for p in recent_slides] if recent_slides else [],
        'pptx': None,
    }

@app.post("/api/jobs")
async def create_job(req: JobCreate) -> Dict[str, str]:
    job_id = str(int(time.time() * 1000))
    jobs[job_id] = Job(id=job_id, status="running", created_at=time.time(), mode=req.mode, paper_id=req.paper_id)
    job_logs[job_id] = ["Job created", f"Mode: {req.mode}"]
    log_queues[job_id] = asyncio.Queue()
    # Emit initial running status so UI can set progress bar to 0 right after queue creation
    try:
        log_queues[job_id].put_nowait({"type":"status","status":"running","progress":0})
    except Exception:
        pass


    async def run_pipeline(jid: str, req: JobCreate):
        try:
            await _log(jid, "Initializing...")
            loop = asyncio.get_event_loop()
            # Emit initial running status so UI can set progress bar to 0
            q0 = log_queues.get(jid)
            if q0 is not None:
                try:
                    q0.put_nowait({"type":"status","status":"running","progress":0})
                except Exception:
                    pass

            def logger(msg):
                # Accept both strings and dict structured events
                if isinstance(msg, dict):
                    # Store a compact textual representation for the log pane
                    summary = msg.get("message") or (
                        f"[{msg.get('type')}] {msg.get('stage') or ''} {msg.get('progress') if 'progress' in msg else ''}".strip()
                    )
                    job_logs.setdefault(jid, []).append(str(summary))
                else:
                    job_logs.setdefault(jid, []).append(str(msg))
                q = log_queues.get(jid)
                if q is not None:
                    try:
                        q.put_nowait(msg)
                    except Exception:
                        pass

            def task_call():
                if req.mode == "demo":
                    return run_demo_mode(log=logger)
                elif req.mode == "complete":
                    opts = req.options or {}
                    maxp = int(req.max_papers or opts.get("max_papers") or 1)
                    return run_complete_pipeline(max_papers=maxp, log=logger)
                elif req.mode == "single":
                    return process_single_paper(req.paper_id or "demo", log=logger)
                elif req.mode == "slides":
                    return run_slides_only(req.paper_id or "demo", log=logger)
                else:
                    return run_demo_mode(log=logger)

            res = await loop.run_in_executor(None, task_call)

            # Normalize/relativize outputs
            def _safe_rel(p: Optional[str]):
                if not p:
                    return None
                pp = Path(p)
                try:
                    return _rel(pp)
                except Exception:
                    return str(pp)

            out = {
                'video': _safe_rel(res.get('video')),
                'subtitle': _safe_rel(res.get('subtitle')),
                'slides': [ _safe_rel(s) for s in (res.get('slides') or []) ],
                'pptx': _safe_rel(res.get('pptx')),
            }
            latest_outputs.clear(); latest_outputs.update(out)
            jobs[jid].status = "succeeded"
            await _log(jid, "DONE")
            await log_queues[jid].put("__DONE__")
        except Exception as e:
            jobs[jid].status = "failed"
            await _log(jid, f"ERROR: {e}")
            await log_queues[jid].put("__DONE__")

    asyncio.create_task(run_pipeline(job_id, req))
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
        scanned = _scan_latest_outputs()
        if not scanned.get('slides') and not scanned.get('video'):
            raise HTTPException(status_code=404, detail="no_outputs")
        return scanned
    return latest_outputs

@app.websocket("/api/jobs/{job_id}/ws")
async def job_ws(websocket: WebSocket, job_id: str):
    await websocket.accept()
    queue = log_queues.get(job_id)
    try:
        import json
        for line in job_logs.get(job_id, []):
            await websocket.send_text(json.dumps({"type":"log","message": line}))
        if queue is None:
            await websocket.send_text(json.dumps({"type":"log","message":"no-live-logs"}))
            await websocket.close()
            return
        while True:
            msg = await queue.get()
            if msg == "__DONE__":
                await websocket.send_text(json.dumps({"type":"status","status":"done","progress":1}))
                await websocket.close()
                break
            elif isinstance(msg, dict):
                await websocket.send_text(json.dumps(msg))
            else:
                await websocket.send_text(json.dumps({"type":"log","message": str(msg)}))
    except WebSocketDisconnect:
        pass
