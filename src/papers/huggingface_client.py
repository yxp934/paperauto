"""
Minimal HuggingFace/ArXiv fetcher for recent papers.
To avoid extra dependencies, we use the public arXiv API directly.
If HUGGINGFACE integration is desired later, swap implementation accordingly.
"""
from __future__ import annotations
from typing import List, Optional
from datetime import datetime, timedelta
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
    # If no entries, fall back to seed ids to ensure we still process real papers
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

