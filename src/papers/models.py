"""
Minimal paper models used by the reconstructed pipeline.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Paper:
    arxiv_id: str
    title: str
    abstract: str
    authors: List[str]
    url: Optional[str] = None

