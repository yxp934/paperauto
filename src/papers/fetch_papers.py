"""
Facade for fetching papers using the minimal arXiv client.
This keeps the rest of the pipeline decoupled from the concrete provider.
"""
from __future__ import annotations
from typing import List, Optional

from .models import Paper
from .huggingface_client import fetch_recent_papers as _recent, fetch_paper_by_id as _by_id


def get_recent_papers(max_results: int = 1) -> List[Paper]:
    return _recent(max_results=max_results)


def get_paper_by_id(arxiv_id: str) -> Optional[Paper]:
    return _by_id(arxiv_id)

