"""
Reconstructed pipeline entry points.
- run_demo_mode()
- run_complete_pipeline(max_papers: int)
- process_single_paper(paper_id: str)
- run_slides_only(paper_id: str)

These functions generate meaningful slides using SlideRenderer and (optionally) ChartGenerator,
compose a slideshow video via ffmpeg (except slides-only), and write WebVTT subtitles.
They accept an optional log: Callable[[str], None] for progress streaming.
"""
from __future__ import annotations
from typing import Callable, Dict, List, Optional
from pathlib import Path
import time
import subprocess
from typing import Any

from src.slide.slide_renderer import SlideRenderer
# ChartGenerator is used internally by SlideRenderer when data['chart'] is a dict
# from src.slide.chart_generator import ChartGenerator
from src.papers.fetch_papers import get_recent_papers, get_paper_by_id

OUTPUT_DIR = Path("output")
SLIDES_DIR = OUTPUT_DIR / "slides"
VIDEOS_DIR = OUTPUT_DIR / "videos"
SLIDES_DIR.mkdir(parents=True, exist_ok=True)
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)


def _log(log, msg) -> None:
    try:
        if log:
            log(msg)
    except Exception:
        pass

def _progress(log, progress: float, stage: str, message: Optional[str] = None) -> None:
    try:
        if log:
            log({"type":"progress","progress": max(0.0,min(1.0, float(progress))), "stage": stage, **({"message": message} if message else {})})
    except Exception:
        pass

def _paper_event(log, arxiv_id: str, title: str, url: Optional[str] = None, authors: Optional[List[str]] = None) -> None:
    try:
        if log:
            payload = {"type":"paper","id": arxiv_id, "title": title}
            if url: payload["url"] = url
            if authors: payload["authors"] = authors
            log(payload)
    except Exception:
        pass


def _compose_video_ffmpeg(slides: List[Path], out_path: Path, per_sec: float = 3.0, log: Optional[Callable[[str], None]] = None) -> bool:
    try:
        lst = out_path.parent / f"list_{out_path.stem}.txt"
        with open(lst, "w") as f:
            for p in slides:
                ap = p.resolve().as_posix()
                f.write(f"file '{ap}'\n"); f.write(f"duration {per_sec}\n")
            if slides:
                f.write(f"file '{slides[-1].resolve().as_posix()}'\n")
        cmd = [
            "ffmpeg","-y","-f","concat","-safe","0","-i", str(lst),
            "-vf","scale=1920:1080,format=yuv420p","-pix_fmt","yuv420p",
            "-movflags","+faststart", str(out_path)
        ]
        _log(log, "[video] ffmpeg composing...")
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except Exception as e:
        _log(log, f"[video] ffmpeg failed: {e}")
        return False


def _write_vtt(slides: List[Path], vtt_path: Path, per_sec: float = 3.0, label: str = "Slide", log: Optional[Callable[[str], None]] = None) -> None:
    with open(vtt_path, "w") as f:
        f.write("WEBVTT\n\n")
        t0 = 0
        for i, _ in enumerate(slides, 1):
            t1 = t0 + int(per_sec)
            f.write(f"00:{t0:02d}.000 --> 00:{t1:02d}.000\n{label} {i}\n\n")
            t0 = t1
    _log(log, f"[subtitles] wrote {vtt_path.name}")


def _build_sections_from_paper(paper: Dict[str, Any]) -> List[Dict]:
    title = paper.get("title") or paper.get("paper_id") or "Paper"
    abstract = paper.get("abstract", "").split("\n")
    abs_bullets = [s.strip() for s in abstract if s.strip()][:3] or ["No abstract available."]
    sections: List[Dict] = [
        {"title": f"{title}: Overview", "bullets": abs_bullets[:3]},
        {"title": f"{title}: Background", "bullets": ["Context", "Problem", "Motivation"]},
        {"title": f"{title}: Method", "bullets": ["Model", "Training", "Loss"]},
        {"title": f"{title}: Experiments", "bullets": ["Datasets", "Baselines", "Metrics"]},
        {"title": f"{title}: Results", "bullets": ["Main Result", "Ablations", "Limitations"],
         "chart": {"type": "bar", "data": {"labels": ["A","B","C"], "values": [0.72, 0.81, 0.65], "title": "Accuracy"}}},
        {"title": f"{title}: Conclusion", "bullets": ["Summary", "Future Work", "Code"]},
    ]
    return sections


def _render_sections_to_slides(paper_id: str, sections: List[Dict], log: Optional[Callable[[str], None]] = None) -> List[Path]:
    renderer = SlideRenderer()
    paths: List[Path] = []
    total = max(1, len(sections))
    for idx, sec in enumerate(sections, 1):
        data = {"title": sec.get("title", ""), "bullets": sec.get("bullets", [])}
        chart = sec.get("chart")
        if chart:
            data["chart"] = chart
        layout = "left_image_right_text" if data.get("chart") else "text_bullets"
        out = SLIDES_DIR / f"{paper_id}_{int(time.time())}_{idx:02d}.png"
        _log(log, f"[slides] rendering {idx}/{len(sections)}")
        _progress(log, 0.1 + 0.6 * (idx/total), "slides", f"{idx}/{total}")
        res = renderer.render_slide(layout, data, str(out))
        if getattr(res, "success", False):
            paths.append(Path(res.output_path or str(out)))
        else:
            res2 = renderer.render_slide("title_only", {"title": data.get("title","")}, str(out))
            if getattr(res2, "success", False):
                paths.append(Path(res2.output_path or str(out)))
    return paths


def process_single_paper(paper_id: str, log: Optional[Callable[[str], None]] = None) -> Dict[str, object]:
    _log(log, f"[pipeline] single BEGIN: {paper_id}")
    try:
        _progress(log, 0.05, "fetch", f"{paper_id}")
        paper = get_paper_by_id(paper_id)
        if paper:
            _paper_event(log, paper.arxiv_id, paper.title, paper.url, paper.authors[:5] if paper.authors else None)
        pdata = {"paper_id": paper_id, "title": paper.title if paper else paper_id, "abstract": (paper.abstract if paper else "")}
        secs = _build_sections_from_paper(pdata)
        slides = _render_sections_to_slides(paper_id, secs, log=log)
        video_path = VIDEOS_DIR / f"{paper_id}_{int(time.time())}.mp4"
        vtt_path = VIDEOS_DIR / f"{paper_id}_{int(time.time())}.vtt"
        _progress(log, 0.75, "video", "compose")
        ok = _compose_video_ffmpeg(slides, video_path, per_sec=3.0, log=log)
        _progress(log, 0.9, "subtitles", "write")
        _write_vtt(slides, vtt_path, per_sec=3.0, label=paper_id, log=log)
        _log(log, f"[pipeline] single END: {paper_id}")
        return {
            "slides": [str(p) for p in slides],
            "video": str(video_path) if ok else None,
            "subtitle": str(vtt_path),
            "pptx": None,
        }
    except Exception as e:
        _log(log, f"[pipeline] single ERROR: {e}")
        raise


def run_slides_only(paper_id: str, log: Optional[Callable[[str], None]] = None) -> Dict[str, object]:
    _log(log, f"[pipeline] slides-only BEGIN: {paper_id}")
    try:
        paper = get_paper_by_id(paper_id)
        pdata = {"paper_id": paper_id, "title": paper.title if paper else paper_id, "abstract": (paper.abstract if paper else "")}
        secs = _build_sections_from_paper(pdata)
        slides = _render_sections_to_slides(paper_id, secs, log=log)
        _log(log, f"[pipeline] slides-only END: {paper_id}")
        return {"slides": [str(p) for p in slides], "video": None, "subtitle": None, "pptx": None}
    except Exception as e:
        _log(log, f"[pipeline] slides-only ERROR: {e}")
        raise


def run_demo_mode(log: Optional[Callable[[str], None]] = None) -> Dict[str, object]:
    _log(log, "[pipeline] demo BEGIN")
    try:
        res = process_single_paper("demo", log=log)
        _log(log, "[pipeline] demo END")
        return res
    except Exception as e:
        _log(log, f"[pipeline] demo ERROR: {e}")
        raise


def run_complete_pipeline(max_papers: int = 1, log: Optional[Callable[[str], None]] = None) -> Dict[str, object]:
    _log(log, f"[pipeline] complete BEGIN: max_papers={max_papers}")
    try:
        result: Dict[str, object] = {}
        _progress(log, 0.02, "papers", "fetching recent")
        papers = get_recent_papers(max_results=max(1, int(max_papers)))
        if not papers:
            _log(log, "[pipeline] complete: no papers fetched, falling back to demo")
            return run_demo_mode(log=log)
        total = len(papers)
        for i, p in enumerate(papers, 1):
            _paper_event(log, p.arxiv_id, p.title, p.url, p.authors[:5] if p.authors else None)
            _log(log, f"[pipeline] complete: processing {i}/{total} {p.arxiv_id} :: {p.title[:80]}")
            _progress(log, 0.05 + 0.05*(i/total), "papers", f"{i}/{total}")
            result = process_single_paper(p.arxiv_id, log=log)
        _progress(log, 0.99, "finalize")
        _log(log, "[pipeline] complete END")
        return result
    except Exception as e:
        _log(log, f"[pipeline] complete ERROR: {e}")
        raise

