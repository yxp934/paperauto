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

ARXIV_API = "http://export.arxiv.org/api/query"


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
    query = urllib.parse.urlencode({
        "search_query": "cat:cs.AI",
        "sortBy": "lastUpdatedDate",
        "sortOrder": "descending",
        "start": 0,
        "max_results": max(1, int(max_results)),
    })
    url = f"{ARXIV_API}?{query}"
    req = urllib.request.Request(url, headers={"User-Agent": "Paper2Video/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = resp.read()
    except Exception:
        return []
    # Parse Atom XML
    root = ET.fromstring(data)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    papers: List[Paper] = []
    for entry in root.findall("a:entry", namespaces=ns):
        p = _parse_entry(entry)
        if p:
            papers.append(p)
    return papers


def fetch_paper_by_id(arxiv_id: str) -> Optional[Paper]:
    # Fetch specific id
    query = urllib.parse.urlencode({
        "id_list": arxiv_id,
    })
    url = f"{ARXIV_API}?{query}"
    req = urllib.request.Request(url, headers={"User-Agent": "Paper2Video/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = resp.read()
    except Exception:
        return None
    root = ET.fromstring(data)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    entry = root.find("a:entry", namespaces=ns)
    if entry is None:
        return None
    return _parse_entry(entry)

