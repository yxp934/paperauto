import os
import re
import pytest

from src.utils.llm_client import LLMClient


def zh_ratio(s: str) -> float:
    ch = sum(1 for c in s if '\u4e00' <= c <= '\u9fff')
    latin = sum(1 for c in s if ('A' <= c <= 'Z') or ('a' <= c <= 'z'))
    return ch / max(1, ch + latin)


def test_expand_to_chinese_heuristic_meets_quality_when_no_keys(monkeypatch):
    # Ensure no API keys so the heuristic path is used
    monkeypatch.delenv("LLM_API_URL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    client = LLMClient()

    # English-dominant input with some symbols should be filtered/expanded
    content = """
    In this section, we introduce the approach and compare it with baselines.
    We discuss implementation details and experimental results.
    Code: https://github.com/user/repo. Dataset size: 10k.
    """.strip()

    out = client._expand_to_chinese(content, topic="Introduction", min_len=600)

    assert isinstance(out, str)
    assert len(out) >= 600
    assert zh_ratio(out) >= 0.9


def test_validate_and_repair_parts_ensures_length_and_zh_purity(monkeypatch):
    monkeypatch.delenv("LLM_API_URL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    client = LLMClient()

    parts = [
        "Short English part.",
        "Another short fragment with ASCII tokens and URLs: http://example.com"
    ]

    fixed = client._validate_and_repair_parts(parts, topic="Method", min_len=600)
    assert len(fixed) == 2
    assert all(len(p) >= 600 for p in fixed)
    assert zh_ratio("".join(fixed)) >= 0.9

