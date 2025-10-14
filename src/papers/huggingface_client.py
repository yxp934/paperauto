"""
Minimal HuggingFace/ArXiv fetcher for recent papers.
To avoid extra dependencies, we use the public arXiv API directly.
If HUGGINGFACE integration is desired later, swap implementation accordingly.
"""
from __future__ import annotations
from typing import List, Optional
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from .models import Paper

# Use HTTPS to improve reachability in constrained networks
ARXIV_API = "https://export.arxiv.org/api/query"
# Fallback seed IDs (real papers) used only when category search yields zero
SEED_IDS: List[str] = [
    "2510.03215",  # Cache-to-Cache: Direct Semantic Communication Between LLMs
    "2510.08572",  # BLAZER: Bootstrapping LLM-based Manipulation Agents
]


def _parse_entry(entry: ET.Element) -> Optional[Paper]:
    try:
        ns = {"a": "http://www.w3.org/2005/Atom"}
        id_text = entry.findtext("a:id", namespaces=ns) or ""
        arxiv_id = id_text.rsplit("/", 1)[-1]
        title = (entry.findtext("a:title", namespaces=ns) or "").strip()
        abstract = (entry.findtext("a:summary", namespaces=ns) or "").strip()
        authors = [a.findtext("a:name", namespaces=ns) or "" for a in entry.findall("a:author", namespaces=ns)]
        link = None
        for l in entry.findall("a:link", namespaces=ns):
            if l.attrib.get("rel") == "alternate":
                link = l.attrib.get("href")
                break
        return Paper(arxiv_id=arxiv_id, title=title, abstract=abstract, authors=authors, url=link)
    except Exception:
        return None


def fetch_recent_papers(max_results: int = 1) -> List[Paper]:
    # Query recent submissions in cs.AI (adjust if needed)
    params = {
        "search_query": "cat:cs.AI",
        "sortBy": "lastUpdatedDate",
        "sortOrder": "descending",
        "start": 0,
        "max_results": max(1, int(max_results)),
    }
    url = f"{ARXIV_API}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "Paper2Video/0.1"})
    data: Optional[bytes] = None
    # Slightly longer timeout with a second attempt to be resilient
    for timeout in (10, 12):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
                break
        except Exception:
            data = None
            continue
    if not data:
        # As a last resort, try fetching known recent ids via id_list
        return _fetch_by_id_list(SEED_IDS, max_results=max_results)

    # Parse Atom XML
    try:
        root = ET.fromstring(data)
    except Exception:
        return _fetch_by_id_list(SEED_IDS, max_results=max_results)

    ns = {"a": "http://www.w3.org/2005/Atom"}
    papers: List[Paper] = []
    for entry in root.findall("a:entry", namespaces=ns):
        p = _parse_entry(entry)
        if p:
            papers.append(p)
    if papers:
        return papers[: max(1, int(max_results))]
    # If no entries, try arXiv RSS (real data) before any seed fallback
    rss = _fetch_arxiv_rss(max_results=max_results)
    if rss:
        return rss
    # As a last resort, use a tiny real id_list to keep the pipeline alive in constrained envs
    return _fetch_by_id_list(SEED_IDS, max_results=max_results)


def _fetch_by_id_list(ids: List[str], max_results: int = 1) -> List[Paper]:
    if not ids:
        return []
    params = {"id_list": ",".join(ids[:max(1, int(max_results))])}
    url = f"{ARXIV_API}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "Paper2Video/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read()
    except Exception:
        return []
    try:
        root = ET.fromstring(data)
    except Exception:
        return []
    ns = {"a": "http://www.w3.org/2005/Atom"}
    papers: List[Paper] = []
    for entry in root.findall("a:entry", namespaces=ns):
        p = _parse_entry(entry)
        if p:
            papers.append(p)
    return papers[: max(1, int(max_results))]


def fetch_paper_by_id(arxiv_id: str) -> Optional[Paper]:
    # Fetch specific id over HTTPS
    params = {"id_list": arxiv_id}
    url = f"{ARXIV_API}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "Paper2Video/0.1"})
    data: Optional[bytes] = None
    for timeout in (10, 12):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
                break
        except Exception:
            data = None
            continue
    if not data:
        return None
    try:
        root = ET.fromstring(data)
    except Exception:
        return None
    ns = {"a": "http://www.w3.org/2005/Atom"}
    entry = root.find("a:entry", namespaces=ns)
    if entry is None:
        return None
    return _parse_entry(entry)


# -------------------- Hugging Face daily papers --------------------
import re, json
from datetime import date as _date

HF_PAPERS_URL = "https://huggingface.co/papers"
HF_API_URL = "https://huggingface.co/api/daily_papers"


def fetch_huggingface_daily_papers(date: Optional[str] = None, max_results: int = 5) -> List[Paper]:
    """
    Fetch daily curated papers from Hugging Face.
    - date: YYYY-MM-DD (defaults to today, UTC)
    - returns: List[Paper]
    Strategy:
      1) Try JSON API: /api/papers?date=YYYY-MM-DD
      2) Fallback to HTML page: /papers?date=YYYY-MM-DD (best-effort scrape)
      3) On failure, return [] so callers can fallback to arXiv or seeds
    """
    if not date:
        date = _date.today().isoformat()
    # Try JSON API first
    params = urllib.parse.urlencode({"date": date})
    url_api = f"{HF_API_URL}?{params}"
    req = urllib.request.Request(url_api, headers={"User-Agent": "Paper2Video/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            buf = resp.read()
        try:
            payload = json.loads(buf.decode("utf-8", "ignore"))
        except Exception:
            payload = None
        if isinstance(payload, dict) and "papers" in payload:
            items = payload.get("papers") or []
            return _hf_items_to_papers(items, max_results=max_results)
        if isinstance(payload, list):
            return _hf_items_to_papers(payload, max_results=max_results)
    except Exception:
        pass

    # Fallback: HTML page scrape
    url_html = f"{HF_PAPERS_URL}?{params}"
    req2 = urllib.request.Request(url_html, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req2, timeout=12) as resp:
            html = resp.read().decode("utf-8", "ignore")
    except Exception:
        return []

    # Heuristic extraction: find arXiv IDs and surrounding titles/authors
    id_pat = re.compile(r"arxiv\.org/(?:abs|pdf)/([0-9]{4}\.[0-9]{4,5}(?:v\d+)?)", re.I)
    ids = []
    for m in id_pat.finditer(html):
        aid = m.group(1)
        if aid not in ids:
            ids.append(aid)
    papers: List[Paper] = []
    for aid in ids[: max(1, int(max_results))]:
        # Title: try to capture text around first occurrence
        idx = html.lower().find(aid.lower())
        title = aid
        authors: List[str] = []
        abstract = ""
        if idx != -1:
            window = html[max(0, idx-600): idx+600]
            # crude title capture
            t = re.search(r"<h[23][^>]*>([^<]{5,200})</h[23]>", window, re.I)
            if not t:
                t = re.search(r"class=\"[^\"]*(?:title|paper-title)[^\"]*\">([^<]{5,200})<", window, re.I)
            if t:
                title = re.sub(r"\s+", " ", t.group(1)).strip()
            a = re.search(r"(?:By|by)\s+([^<]{5,200})", window)
            if a:
                raw = a.group(1)
                authors = [s.strip() for s in re.split(r",| and ", raw) if s.strip()]
        papers.append(Paper(arxiv_id=aid, title=title, abstract=abstract, authors=authors, url=f"https://arxiv.org/abs/{aid}"))
    return papers


def _hf_items_to_papers(items, max_results: int = 5) -> List[Paper]:
    out: List[Paper] = []
    for it in items:
        # Try multiple field names since schema may change
        aid = (
            it.get("arxiv_id") or it.get("arxivId") or it.get("id") or ""
        )
        title = it.get("title") or it.get("paper_title") or it.get("name") or ""
        abstract = it.get("abstract") or it.get("summary") or ""
        authors = it.get("authors") or it.get("authors_list") or []
        if isinstance(authors, str):
            authors = [s.strip() for s in re.split(r",| and ", authors) if s.strip()]
        url = it.get("url") or it.get("arxiv_url") or (f"https://arxiv.org/abs/{aid}" if aid else None)
        if not aid and url:
            m = re.search(r"arxiv\.org/(?:abs|pdf)/([0-9]{4}\.[0-9]{4,5}(?:v\d+)?)", url)
            if m:
                aid = m.group(1)
        if not aid:
            continue
        out.append(Paper(arxiv_id=aid, title=title or aid, abstract=abstract or "", authors=authors, url=url))
        if len(out) >= max(1, int(max_results)):
            break
    return out


# --------------- arXiv RSS fallback (real data, no presets) ---------------
ARXIV_RSS_URLS = [
    "https://export.arxiv.org/rss/cs.AI",
    "https://export.arxiv.org/rss/cs.LG",
    "https://export.arxiv.org/rss/cs.CL",
]

def _fetch_arxiv_rss(max_results: int = 5) -> List[Paper]:
    for rss in ARXIV_RSS_URLS:
        try:
            req = urllib.request.Request(rss, headers={"User-Agent": "Paper2Video/0.1"})
            with urllib.request.urlopen(req, timeout=12) as resp:
                xml = resp.read()
            root = ET.fromstring(xml)
            # RSS feed namespaces can vary; search loosely
            items = root.findall('.//item')
            papers: List[Paper] = []
            for it in items:
                title_el = it.find('title')
                link_el = it.find('link')
                desc_el = it.find('description')
                title = title_el.text.strip() if title_el is not None and title_el.text else ''
                link = link_el.text.strip() if link_el is not None and link_el.text else ''
                abstract = ''
                if desc_el is not None and desc_el.text:
                    # Strip HTML tags
                    txt = re.sub(r'<[^>]+>', ' ', desc_el.text)
                    abstract = re.sub(r'\s+', ' ', txt).strip()
                aid = ''
                m = re.search(r'arxiv\.org/(?:abs|pdf)/([0-9]{4}\.[0-9]{4,5}(?:v\d+)?)', link)
                if m:
                    aid = m.group(1)
                if not aid:
                    continue
                papers.append(Paper(arxiv_id=aid, title=title or aid, abstract=abstract, authors=[], url=f"https://arxiv.org/abs/{aid}"))
                if len(papers) >= max(1, int(max_results)):
                    break
            if papers:
                return papers
        except Exception:
            continue
    return []

