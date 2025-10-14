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
# Lazy import real pipeline entry points to avoid optional modules at import time
run_demo_mode = None
run_complete_pipeline = None
process_single_paper = None
run_slides_only = None
try:
    from src.main import run_demo_mode as _rd, run_complete_pipeline as _rc, process_single_paper as _sp, run_slides_only as _rs
    run_demo_mode, run_complete_pipeline, process_single_paper, run_slides_only = _rd, _rc, _sp, _rs
except Exception:
    # optional; web mode uses run_complete_for_web
    pass


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
# Store latest paper metadata per job to replay over WS upon connection
job_paper: Dict[str, dict] = {}
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

# ---- CJK font helpers to ensure Chinese rendering ----
from PIL import Image, ImageDraw, ImageFont

def _find_cjk_font_path() -> str:
    candidates = []
    env_path = os.getenv("CJK_FONT_PATH")
    if env_path:
        candidates.append(env_path)
    candidates += [
        # macOS
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/Hiragino Sans GB W3.otf",
        "/System/Library/Fonts/Hiragino Sans GB W6.otf",
        # Linux
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSerifCJK-Regular.ttc",
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
        # Windows
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simsun.ttc",
        "C:/Windows/Fonts/simhei.ttf",
    ]
    for p in candidates:
        try:
            if p and os.path.exists(p):
                return p
        except Exception:
            continue
    return ""

def _load_font(size: int) -> ImageFont.FreeTypeFont:
    fp = _find_cjk_font_path()
    if fp:
        try:
            return ImageFont.truetype(fp, size)
        except Exception:
            pass
    try:
        return ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size)
    except Exception:
        return ImageFont.load_default()

def _write_text_slide(title: str, bullets: list[str], out: Path, size=(1920,1080)):
    img = Image.new('RGB', size, color=(30,40,60))
    draw = ImageDraw.Draw(img)
    ft = _load_font(64)
    fb = _load_font(40)
    draw.text((80, 80), (title or "")[0:50], fill=(255,255,255), font=ft)
    y = 200
    for b in (bullets or [])[:8]:
        draw.text((120, y), f"• {str(b)[0:70]}", fill=(220,220,220), font=fb)
        y += 90
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(out), 'PNG', optimize=True)

# --- Web-facing minimal pipeline for Generate page (structured logs) ---
from typing import Tuple
from src.papers.fetch_papers import get_daily_papers, get_recent_papers
from src.utils.llm_client import LLMClient
from src.video.tts_dashscope import generate_audio as ds_tts
from src.video.video_composer import compose_video


def _write_vtt(durations: list[float], out: Path):
    def fmt(t: float) -> str:
        h = int(t // 3600); m = int((t % 3600) // 60); s = int(t % 60)
        return f"{h:02d}:{m:02d}:{s:02d}.000"
    cur = 0.0
    lines = ["WEBVTT", ""]
    for i, d in enumerate(durations, start=1):
        start = fmt(cur); end = fmt(cur + max(2.0, float(d)))
        lines.append(f"{i}")
        lines.append(f"{start} --> {end}")
        lines.append(f"Segment {i}")
        lines.append("")
        cur += max(2.0, float(d))
    out.write_text("\n".join(lines), encoding="utf-8")


def run_complete_for_web(max_papers: int, out_dir: Path, log_cb):
    base_slides = out_dir / "slides"; base_vid = out_dir / "videos"
    base_slides.mkdir(parents=True, exist_ok=True); base_vid.mkdir(parents=True, exist_ok=True)

    # Step 1: fetch papers (HF -> arXiv fallback)
    log_cb({"type":"log","message":"fetching Hugging Face daily"})
    papers = get_daily_papers(max_results=max_papers)
    source = "huggingface daily" if papers else "arXiv (fallback)"
    if not papers:
        log_cb({"type":"log","message":"HF daily empty, fallback to arXiv"})
        papers = get_recent_papers(max_results=max_papers)
    log_cb({"type":"log","message":f"[papers] source: {source}"})

    if not papers:
        raise Exception("no papers fetched")

    # Only process first for web acceptance
    paper = papers[0]
    arxiv_id = getattr(paper, 'id', None) or getattr(paper, 'arxiv_id', None) or "unknown"
    log_cb({"type":"status","status":"running","progress":0.05, "message":f"[pipeline] complete: processing 1/1 {arxiv_id}"})
    log_cb({"type":"log","message":f"[pipeline] complete: processing 1/1 {arxiv_id}"})
    log_cb({"type":"paper","id": arxiv_id, "title": getattr(paper, 'title', ''), "authors": getattr(paper, 'authors', []), "url": f"https://arxiv.org/abs/{arxiv_id}"})

    # Step 2-3: LLM analysis + scripts (guarded by timeouts to avoid hanging)
    log_cb({"type":"log","message":"[llm] analyzing paper"})
    llm = LLMClient()
    import concurrent.futures as _f

    # Replay paper event later to ensure WS listeners capture it
    try:
        log_cb({"type":"paper","id": arxiv_id, "title": getattr(paper, 'title', ''), "authors": getattr(paper, 'authors', []), "url": f"https://arxiv.org/abs/{arxiv_id}"})
    except Exception:
        pass

    def _heuristic_sections_from_paper(p):
        abs_txt = getattr(p, 'description', '') or getattr(p, 'abstract', '') or ''
        title_txt = getattr(p, 'title', '') or 'Paper'
        # Very small heuristic 3 sections
        return [
            {"title": f"{title_txt} - 概览", "summary": abs_txt[:200], "keywords": []},
            {"title": "方法与架构", "summary": "方法核心思想与系统架构。", "keywords": []},
            {"title": "实验与结果", "summary": "实验设置与关键结果。", "keywords": []},
        ]

    paper_dict = {
        "title": getattr(paper, 'title', ''),
        "abstract": getattr(paper, 'description', '') or getattr(paper, 'abstract', ''),
        "authors": getattr(paper, 'authors', []),
        "arxiv_id": arxiv_id,
    }

    with _f.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(llm.analyze_paper_structure, paper_dict)
        try:
            sections = fut.result(timeout=int(os.getenv('LLM_ANALYZE_TIMEOUT', '12')))
        except Exception:
            sections = _heuristic_sections_from_paper(paper)

    scripts = []
    def _gen_script(s):
        return llm.generate_section_script(s, {"title": paper_dict['title'], "abstract": paper_dict['abstract']})
    for s in sections[:3]:
        with _f.ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(_gen_script, s)
            try:
                scripts.append(fut.result(timeout=int(os.getenv('LLM_SCRIPT_TIMEOUT', '12'))))
            except Exception:
                # Heuristic narration from summary
                scripts.append({
                    "title": s.get("title") or "内容",
                    "bullets": [],
                    "narration": (s.get("summary") or paper_dict['abstract'] or paper_dict['title'])[:220]
                })
    log_cb({"type":"log","message":"[llm] script generated"})

    # Step 4-6: Render 6 slides using CJK font helper
    slide_paths: list[str] = []
    for i, sc in enumerate(scripts, start=1):
        # two slides per section: title-only and bullet points
        p1 = base_slides / f"{_sanitize(arxiv_id)}_{_now_ts()}_{i*2-1:02d}.png"
        p2 = base_slides / f"{_sanitize(arxiv_id)}_{_now_ts()}_{i*2:02d}.png"
        log_cb({"type":"log","message":f"[slides] rendering {i*2-1}/6"}); _write_text_slide(sc['title'], sc.get('bullets') or [], p1)
        log_cb({"type":"log","message":f"[slides] rendering {i*2}/6"}); _write_text_slide(sc['title'], sc.get('bullets') or [], p2)
        slide_paths += [str(p1), str(p2)]

    # Step 7: TTS
    log_cb({"type":"log","message":"[tts] generating speech"})
    audio_wavs: list[str] = []
    durations: list[float] = []
    total_segments = len(slide_paths)
    for idx, sc in enumerate(scripts, start=1):
        mp3_path, dur = ds_tts(sc.get("narration") or "")
        base_idx = (idx - 1) * 2
        # generate two wavs for two slides per section
        wav1 = str((Path("temp/audio") / f"seg_{base_idx+1:02d}.wav").resolve())
        wav2 = str((Path("temp/audio") / f"seg_{base_idx+2:02d}.wav").resolve())
        # convert mp3->wav mono 22.05k
        subprocess.run(["ffmpeg","-y","-i", mp3_path, "-ar","22050","-ac","1", wav1], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # reuse same audio for second slide
        subprocess.run(["ffmpeg","-y","-i", mp3_path, "-ar","22050","-ac","1", wav2], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        audio_wavs.extend([wav1, wav2]); durations.extend([dur, dur])
        log_cb({"type":"log","message":f"[tts] synthesized segment {base_idx+1}/{total_segments}"})
        log_cb({"type":"log","message":f"[tts] synthesized segment {base_idx+2}/{total_segments}"})

    # Step 8: Compose video
    vid_path = base_vid / f"{_sanitize(arxiv_id)}_{int(time.time())}.mp4"
    log_cb({"type":"log","message":"[video] composing with audio narration"})
    compose_video(slide_paths, audio_wavs, durations, str(vid_path), log=lambda m: log_cb({"type":"log","message":str(m)}))

    # Subtitles (WEBVTT)
    vtt_path = vid_path.with_suffix('.vtt')
    _write_vtt(durations, vtt_path)

    return {
        'video': str(vid_path),
        'subtitle': str(vtt_path),
        'slides': slide_paths,
        'pptx': None,
    }

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
                    if msg.get('type') == 'paper':
                        try:
                            job_paper[jid] = {
                                'type': 'paper',
                                'id': msg.get('id'),
                                'title': msg.get('title'),
                                'authors': msg.get('authors'),
                                'url': msg.get('url'),
                            }
                        except Exception:
                            pass
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
                    # Use web-optimized pipeline with structured logs and CJK slides
                    return run_complete_for_web(max_papers=maxp, out_dir=OUTPUT_DIR, log_cb=logger)
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

@app.post("/api/jobs/{job_id}/replay-paper")
async def replay_paper(job_id: str):
    q = log_queues.get(job_id)
    if not q:
        raise HTTPException(status_code=404, detail="no_queue")
    data = job_paper.get(job_id)
    if not data:
        return {"ok": True, "sent": False}
    try:
        await q.put(dict(data))
        return {"ok": True, "sent": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
        # Replay latest paper metadata if present so tests can observe a paper event even if emitted pre-WS
        if job_id in job_paper:
            try:
                await websocket.send_text(json.dumps(job_paper[job_id]))
            except Exception:
                pass
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
