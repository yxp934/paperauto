"""
Facade for fetching papers using the minimal arXiv client.
This keeps the rest of the pipeline decoupled from the concrete provider.
"""
from __future__ import annotations
from typing import List, Optional

from .models import Paper
from .huggingface_client import (
    fetch_recent_papers as _recent,
    fetch_paper_by_id as _by_id,
    fetch_huggingface_daily_papers as _hf_daily,
)


def get_recent_papers(max_results: int = 1) -> List[Paper]:
    return _recent(max_results=max_results)


def get_daily_papers(date: Optional[str] = None, max_results: int = 5) -> List[Paper]:
    return _hf_daily(date=date, max_results=max_results)


def get_paper_by_id(arxiv_id: str) -> Optional[Paper]:
    return _by_id(arxiv_id)


# 统一函数名（用于步骤1）
def fetch_daily_papers(date: Optional[str] = None, max_results: int = 5) -> List[Paper]:
    """
    获取每日论文（HF Daily → arXiv 回退）

    策略：
    1. 尝试从 Hugging Face Daily Papers 获取
    2. 如果失败或返回空，回退到 arXiv API（cs.AI 最新论文）
    3. 如果仍失败，使用种子ID列表

    Args:
        date: 日期 YYYY-MM-DD（默认今天）
        max_results: 最大结果数

    Returns:
        List[Paper]: 论文列表（至少返回1篇，除非所有策略都失败）
    """
    # 策略1: HF Daily Papers
    papers = get_daily_papers(date=date, max_results=max_results)

    if papers and len(papers) > 0:
        return papers

    # 策略2: arXiv API 回退
    print(f"HF Daily Papers 未返回结果，回退到 arXiv API...")
    papers = get_recent_papers(max_results=max_results)

    if papers and len(papers) > 0:
        return papers

    # 策略3: 如果仍然失败，返回空列表（调用者可以决定如何处理）
    print(f"警告: 所有论文获取策略均失败")
    return []


class PaperFetcher:
    """论文获取器类（兼容旧版main.py）"""

    def fetch_daily_papers(self, date: Optional[str] = None, max_results: int = 5) -> List[Paper]:
        """获取每日论文"""
        return fetch_daily_papers(date=date, max_results=max_results)

    def get_recent_papers(self, max_results: int = 1) -> List[Paper]:
        """获取最近论文"""
        return get_recent_papers(max_results=max_results)

    def get_paper_by_id(self, arxiv_id: str) -> Optional[Paper]:
        """根据ID获取论文"""
        return get_paper_by_id(arxiv_id)

