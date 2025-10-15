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

# Import A2A workflow
try:
    from graph.workflow import A2AWorkflow
    from src.utils.llm_client import LLMClient
    a2a_available = True
except Exception:
    a2a_available = False


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


def _write_slide_with_image(title: str, bullets: list[str], image_path: str | None, out_path: Path, size=(1920,1080)):
    """Write slide with text and image"""
    img = Image.new('RGB', size, color=(30,40,60))
    draw = ImageDraw.Draw(img)

    # Load fonts
    ft = _load_font(56)
    fb = _load_font(36)

    # Title
    draw.text((60, 40), (title or "")[0:50], fill=(255,255,255), font=ft)

    # If image available, place it on the right side
    if image_path and Path(image_path).exists():
        try:
            gen_img = Image.open(image_path)
            # Resize to fit right half
            img_w, img_h = 800, 800
            gen_img = gen_img.resize((img_w, img_h), Image.Resampling.LANCZOS)
            # Paste on right side
            img.paste(gen_img, (1920 - img_w - 60, (1080 - img_h) // 2))
        except Exception as e:
            pass  # If image loading fails, just skip it

    # Bullets on left side
    y = 150
    max_bullet_width = 900 if image_path else 1700
    for b in (bullets or [])[:6]:
        bullet_text = f"• {str(b)[0:60]}"
        draw.text((80, y), bullet_text, fill=(220,220,220), font=fb)
        y += 80

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(out_path), 'PNG', optimize=True)


# --- Web-facing minimal pipeline for Generate page (structured logs) ---
from typing import Tuple
from src.papers.fetch_papers import get_daily_papers, get_recent_papers
from src.utils.llm_client import LLMClient
from src.video.tts_dashscope import generate_audio as ds_tts
from src.video.video_composer import compose_video


def _write_vtt(durations: list[float], texts: list[str], out: Path):
    def fmt(t: float) -> str:
        h = int(t // 3600); m = int((t % 3600) // 60); s = int(t % 60)
        return f"{h:02d}:{m:02d}:{s:02d}.000"
    cur = 0.0
    lines = ["WEBVTT", ""]
    for i, d in enumerate(durations, start=1):
        start = fmt(cur); end = fmt(cur + max(2.0, float(d)))
        text = (texts[i-1] if i-1 < len(texts) else "").strip() or f"Segment {i}"
        lines.append(f"{i}")
        lines.append(f"{start} --> {end}")
        # Allow multi-line by splitting on '。' and keeping short lines for readability
        parts = [p.strip() for p in text.replace('\r',' ').split('。') if p.strip()]
        if not parts:
            parts = [text]
        for j, p in enumerate(parts):
            if j < 3:
                lines.append(p)
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
            sections = fut.result(timeout=int(os.getenv('LLM_ANALYZE_TIMEOUT', '35')))
        except Exception:
            sections = _heuristic_sections_from_paper(paper)

    scripts = []
    def _gen_script(s):
        return llm.generate_section_script(s, {"title": paper_dict['title'], "abstract": paper_dict['abstract']})
    for s in sections[:3]:
        with _f.ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(_gen_script, s)
            try:
                scr = fut.result(timeout=int(os.getenv('LLM_SCRIPT_TIMEOUT', '35')))
                scripts.append(scr)
            except Exception as e:
                log_cb({"type":"log","message":f"[llm] WARN script gen timeout -> heuristic for {s.get('title')}"})
                # Robust heuristic: ensure 3-5 meaningful bullets and 200+ char narration
                sec_title = (s.get('title') or '').strip()
                sec_sum = (s.get('summary') or '').strip()
                abs_txt = (paper_dict.get('abstract') or '').strip()
                # split by sentence
                import re as _re
                bullets = [b.strip() for b in _re.split(r"[\u3002.!?]\s*", sec_sum) if b.strip()]
    # Enrich scripts if bullets too few
                if len(bullets) < 3 and abs_txt:
                    bullets += [b.strip() for b in _re.split(r"[\u3002.!?]\s*", abs_txt) if b.strip()][:5]
                # template supplement by section title
                templates = []
                if any(k in sec_title for k in ["方法","架构","Method"]):
                    templates = ["总体思路与流程","关键模块与算法","训练与推理细节","复杂度与局限性"]
                elif any(k in sec_title for k in ["实验","结果","Experiments","Results"]):
                    templates = ["数据集与设置","对比方法与指标","主要结果与可视化","消融与误差分析"]
                elif any(k in sec_title for k in ["概览","引言","背景","Overview","Introduction","Background"]):
                    templates = ["研究动机与问题","核心贡献","方法直观说明","潜在应用"]
                if len(bullets) < 3:
                    for t in templates:
                        if t not in bullets:
                            bullets.append(t)
                        if len(bullets) >= 5:
                            break
                bullets = bullets[:5]
                if not bullets:
                    bullets = ["要点提取失败：请参见摘要与标题"]
                # narration
                intro = f"本节围绕{sec_title or '该部分'}展开，"
                narr_body = (sec_sum or abs_txt or paper_dict.get('title') or '')
                narr = (intro + narr_body + "。要点包括：" + "；".join(bullets) + "。")
                if len(narr) < 220 and abs_txt:
                    narr = (narr + " " + abs_txt)[:480]
                scr = {"title": sec_title or 'Section', "bullets": bullets, "narration": narr}
                scripts.append(scr)

    import re as __re_enr
    for si, sc in enumerate(scripts):
        bl = [b.strip() for b in (sc.get('bullets') or []) if str(b).strip()]
        if len(bl) < 3:
            add_from_abs = [b.strip() for b in __re_enr.split(r"[\u3002.!?]\s*", paper_dict.get('abstract') or '') if b.strip()][:5]
            bl += [x for x in add_from_abs if x and x not in bl]
            # section-specific templates
            st = (sc.get('title') or '')
            tpl = []
            if any(k in st for k in ["方法","架构","Method"]):
                tpl = ["总体思路与流程","关键模块与算法","训练与推理细节","复杂度与局限性"]
            elif any(k in st for k in ["实验","结果","Experiments","Results"]):
                tpl = ["数据集与设置","对比方法与指标","主要结果与可视化","消融与误差分析"]
            elif any(k in st for k in ["概览","引言","背景","Overview","Introduction","Background"]):
                tpl = ["研究动机与问题","核心贡献","方法直观说明","潜在应用"]
            for t in tpl:
                if len(bl) >= 5: break
                if t not in bl:
                    bl.append(t)
            sc['bullets'] = bl[:5]
            # ensure narration rich
            if len((sc.get('narration') or '')) < 200:
                sc['narration'] = (f"本节围绕{st or '该部分'}展开，" + (paper_dict.get('abstract') or '') + "。要点包括：" + "；".join(sc['bullets']) + "。")[:600]
        # re-log after enrichment
        _bl2 = sc.get('bullets') or []
        log_cb({"type":"log","message":f"[llm] script enriched | title={sc.get('title')} | bullets={len(_bl2)} | narr_len={len(sc.get('narration') or '')}"})

        _bl = scr.get('bullets') or []
        log_cb({"type":"log","message":f"[llm] script obj | title={scr.get('title')} | bullets={len(_bl)} | narr_len={len(scr.get('narration') or '')} | bullet_head={(_bl[0][:24] if _bl else '')}"})
    log_cb({"type":"log","message":"[llm] script generated"})

    # Step 4-6: Render 6 slides using CJK font helper
    slide_paths: list[str] = []
    for i, sc in enumerate(scripts, start=1):
        # two slides per section: title-only and bullet points
        p1 = base_slides / f"{_sanitize(arxiv_id)}_{_now_ts()}_{i*2-1:02d}.png"
        p2 = base_slides / f"{_sanitize(arxiv_id)}_{_now_ts()}_{i*2:02d}.png"
        _bul = sc.get('bullets') or []
        log_cb({"type":"log","message":f"[slides] rendering {i*2-1}/6 | bullets={len(_bul)} | head={(_bul[0][:20] if _bul else '')}"});
        _write_text_slide(sc['title'], _bul, p1)
        log_cb({"type":"log","message":f"[slides] rendering {i*2}/6   | bullets={len(_bul)} | head={(_bul[1][:20] if len(_bul)>1 else (_bul[0][:20] if _bul else ''))}"});
        _write_text_slide(sc['title'], _bul, p2)
        slide_paths += [str(p1), str(p2)]

    # Step 7: TTS（为每个章节拆成两段，避免两页读同一段）
    log_cb({"type":"log","message":"[tts] generating speech"})
    audio_wavs: list[str] = []
    durations: list[float] = []
    subtitle_texts: list[str] = []
    total_segments = len(slide_paths)
    import re as _re
    def _split_narr(n: str) -> tuple[str, str]:
        if not n: return ("", "")
        parts = [s.strip() for s in _re.split(r"[。.!?]", n) if s.strip()]
        if len(parts) <= 1:
            L = len(n)//2 or len(n)
            return (n[:L], n[L:])
        mid = max(1, len(parts)//2)
        a = "。".join(parts[:mid]).strip()
        b = "。".join(parts[mid:]).strip()
        return (a, b)

    for idx, sc in enumerate(scripts, start=1):
        full = sc.get("narration") or ""
        # 构造两段旁白，若过短则补充要点
        a, b = _split_narr(full)
        # if LLM provided high-quality narration_parts, prefer them
        _np = sc.get("narration_parts") or []
        if isinstance(_np, list) and len(_np) >= 2:
            try:
                a, b = str(_np[0] or ""), str(_np[1] or "")
            except Exception:
                pass

        # quality metric for logs
        def __ch_ratio(t: str) -> float:
            ch = sum(1 for c in t if '\u4e00' <= c <= '\u9fff')
            letters = sum(1 for c in t if c.isalpha())
            denom = max(1, ch + letters)
            return ch/denom
        log_cb({"type":"log","message":f"[narr] quality | idx={idx} | lens={[len(a), len(b)]} | zh_ratio={[round(__ch_ratio(a),2), round(__ch_ratio(b),2)]}"})

        if len(a) < 60 and (sc.get("bullets") or []):
            a = (a + " " + "".join([str(x) for x in sc.get("bullets", [])[:2]])).strip()
        if len(b) < 60 and (sc.get("bullets") or []):
            b = (b + " " + "".join([str(x) for x in sc.get("bullets", [])[2:5]])).strip()
        # sanitize TTS text: strip control chars, ensure readable separators
        import re as __re
        a = __re.sub(r"[\x00-\x1F\x7F]", " ", a)
        b = __re.sub(r"[\x00-\x1F\x7F]", " ", b)
        log_cb({"type":"log","message":f"[tts] input | idx={idx} | a_len={len(a)} | b_len={len(b)} | a_head={(a[:30])} | b_head={(b[:30])}"})

        # record subtitle texts aligned with audio segments
        subtitle_texts.extend([a or full, b or full])

        mp3_1, dur1 = ds_tts(a or full)
        mp3_2, dur2 = ds_tts(b or full)
        base_idx = (idx - 1) * 2
        # convert mp3->wav mono 22.05k
        wav1 = str((Path("temp/audio") / f"seg_{base_idx+1:02d}.wav").resolve())
        wav2 = str((Path("temp/audio") / f"seg_{base_idx+2:02d}.wav").resolve())
        subprocess.run(["ffmpeg","-y","-i", mp3_1, "-ar","22050","-ac","1", wav1], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(["ffmpeg","-y","-i", mp3_2, "-ar","22050","-ac","1", wav2], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        audio_wavs.extend([wav1, wav2]); durations.extend([dur1, dur2])
        log_cb({"type":"log","message":f"[tts] to-wav done | {base_idx+1},{base_idx+2}"})
        log_cb({"type":"log","message":f"[tts] synthesized segment {base_idx+1}/{total_segments}"})
        log_cb({"type":"log","message":f"[tts] synthesized segment {base_idx+2}/{total_segments}"})

    # Step 8: Compose video
    vid_path = base_vid / f"{_sanitize(arxiv_id)}_{int(time.time())}.mp4"
    log_cb({"type":"log","message":"[video] composing with audio narration"})
    compose_video(slide_paths, audio_wavs, durations, str(vid_path), log=lambda m: log_cb({"type":"log","message":str(m)}))

    # Subtitles (WEBVTT)
    vtt_path = vid_path.with_suffix('.vtt')
    _write_vtt(durations, subtitle_texts, vtt_path)

    return {
        'video': str(vid_path),
        'subtitle': str(vtt_path),
        'slides': slide_paths,
        'pptx': None,
    }


def run_complete_a2a(max_papers: int, out_dir: Path, log_cb):
    """
    A2A multi-agent workflow version of complete pipeline
    """
    if not a2a_available:
        log_cb({"type":"log","message":"[A2A] workflow not available, falling back to standard pipeline"})
        return run_complete_for_web(max_papers, out_dir, log_cb)

    base_slides = out_dir / "slides"
    base_vid = out_dir / "videos"
    base_slides.mkdir(parents=True, exist_ok=True)
    base_vid.mkdir(parents=True, exist_ok=True)

    # Step 1: fetch papers
    log_cb({"type":"log","message":"[A2A] fetching papers"})
    from src.papers.fetch_papers import get_daily_papers, get_recent_papers
    papers = get_daily_papers(max_results=max_papers)
    if not papers:
        log_cb({"type":"log","message":"[A2A] HF daily empty, fallback to arXiv"})
        papers = get_recent_papers(max_results=max_papers)

    if not papers:
        raise Exception("no papers fetched")

    paper = papers[0]
    arxiv_id = getattr(paper, 'id', None) or getattr(paper, 'arxiv_id', None) or "unknown"

    paper_dict = {
        "title": getattr(paper, 'title', ''),
        "abstract": getattr(paper, 'description', '') or getattr(paper, 'abstract', ''),
        "authors": getattr(paper, 'authors', []),
        "arxiv_id": arxiv_id,
    }

    log_cb({"type":"paper","id": arxiv_id, "title": paper_dict['title'], "authors": paper_dict['authors'], "url": f"https://arxiv.org/abs/{arxiv_id}"})

    # Step 2: Run A2A workflow
    log_cb({"type":"log","message":"[A2A] initializing workflow"})
    llm = LLMClient(log_callback=log_cb)
    workflow = A2AWorkflow(llm, log_callback=log_cb)

    log_cb({"type":"status","status":"running","progress":0.1, "message":"[A2A] running multi-agent workflow"})
    result = workflow.run(paper_dict, max_qa_retries=1)

    scripts = result['scripts']
    slides_data = result['slides']
    meta = result['meta']

    log_cb({"type":"log","message":f"[A2A] workflow complete: {len(scripts)} scripts, {meta['total_tokens']} tokens, ${meta['total_cost']:.4f}"})
    # Emit structured token stats for frontend panel
    try:
        log_cb({
            "type": "token",
            "total": int(meta.get('total_tokens', 0)),
            "cost": float(meta.get('total_cost', 0.0)),
            "by_agent": {
                "orchestrator": int(meta.get('orchestrator_tokens', 0)),
                "script_agent": int(meta.get('script_agent_tokens', 0)),
                "slide_agent": int(meta.get('slide_agent_tokens', 0)),
            }
        })
    except Exception:
        pass

    # Step 3: Render slides with images
    log_cb({"type":"status","status":"running","progress":0.5, "message":"[A2A] rendering slides"})
    slide_paths = []
    for i, slide_data in enumerate(slides_data):
        slide_path = base_slides / f"{_sanitize(arxiv_id)}_{_now_ts()}_{i+1:02d}.png"
        _write_slide_with_image(
            title=slide_data['title'],
            bullets=slide_data['bullets'],
            image_path=slide_data.get('image_path'),
            out_path=slide_path
        )
        slide_paths.append(str(slide_path))
        log_cb({"type":"log","message":f"[A2A] rendered slide {i+1}/{len(slides_data)}"})

    # Step 4: TTS
    log_cb({"type":"status","status":"running","progress":0.7, "message":"[A2A] generating audio"})
    from src.video.tts_dashscope import generate_audio as ds_tts
    audio_wavs = []
    durations = []
    subtitle_texts = []

    for i, script in enumerate(scripts):
        parts = script.get('narration_parts', [])
        if len(parts) < 2:
            parts = [script.get('narration', ''), '']

        for j, part_text in enumerate(parts[:2]):
            if not part_text.strip():
                continue

            log_cb({"type":"log","message":f"[A2A] TTS {i+1}.{j+1}: {len(part_text)} chars"})
            mp3_path, dur = ds_tts(part_text)

            # Convert to WAV
            wav_path = Path(mp3_path).with_suffix('.wav')
            subprocess.run(['ffmpeg', '-y', '-i', mp3_path, '-ar', '44100', '-ac', '2', str(wav_path)], check=True, capture_output=True)

            audio_wavs.append(str(wav_path))
            durations.append(dur)
            subtitle_texts.append(part_text)

    # Step 5: Compose video
    log_cb({"type":"status","status":"running","progress":0.9, "message":"[A2A] composing video"})
    vid_path = base_vid / f"{_sanitize(arxiv_id)}_{_now_ts()}.mp4"

    from src.video.video_composer import compose_video
    compose_video([Path(p) for p in slide_paths], audio_wavs, durations, str(vid_path), log=lambda m: log_cb({"type":"log","message":str(m)}))

    # Step 6: Subtitles
    vtt_path = vid_path.with_suffix('.vtt')
    _write_vtt(durations, subtitle_texts, vtt_path)

    log_cb({"type":"log","message":f"[A2A] complete: {vid_path}"})

    return {
        'video': str(vid_path),
        'subtitle': str(vtt_path),
        'slides': slide_paths,
        'pptx': None,
        'meta': meta
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
                    logger({"type":"log","message":f"[mode] raw options = {opts}"})
                    maxp = int(req.max_papers or opts.get("max_papers") or 1)
                    # Check if A2A mode requested
                    use_a2a = opts.get("use_a2a", False) or opts.get("a2a", False)
                    logger({"type":"log","message":f"[mode] opts.use_a2a={opts.get('use_a2a')} a2a_available={a2a_available}"})
                    if use_a2a and a2a_available:
                        logger({"type":"log","message":"[mode] using A2A multi-agent workflow"})
                        return run_complete_a2a(max_papers=maxp, out_dir=OUTPUT_DIR, log_cb=logger)
                    else:
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


@app.post("/api/jobs/{job_id}/regenerate")
async def regenerate_job(job_id: str, scope: Optional[str] = None, index: Optional[int] = None) -> Dict[str, str]:
    """
    Regenerate content for a given job by starting a new job run.
    For now, this will start a new 'complete' job with A2A enabled.
    Returns the new job_id so the frontend can follow logs.
    Optional query params:
    - scope: e.g. 'script' | 'slide' | 'all' (reserved)
    - index: section/slide index (1-based)
    """
    req = JobCreate(mode="complete", options={"use_a2a": True})
    return await create_job(req)
