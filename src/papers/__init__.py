"""论文获取模块"""
from .models import Paper
from .fetch_papers import (
    get_recent_papers,
    get_daily_papers,
    get_paper_by_id,
    fetch_daily_papers,
    PaperFetcher,
)

__all__ = [
    'Paper',
    'get_recent_papers',
    'get_daily_papers',
    'get_paper_by_id',
    'fetch_daily_papers',
    'PaperFetcher',
]

