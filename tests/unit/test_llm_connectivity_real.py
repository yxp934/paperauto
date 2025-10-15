import os
import pytest
from src.utils.llm_client import LLMClient

# Load .env manually to make keys available in test env
try:
    from pathlib import Path
    env_path = Path('.env')
    if env_path.exists():
        for line in env_path.read_text(encoding='utf-8', errors='ignore').splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            k = k.strip(); v = v.strip().strip('"').strip("'")
            if k and v and k not in os.environ:
                os.environ[k] = v
except Exception:
    pass

pytestmark = pytest.mark.timeout(60)


def _has_any_llm_key():
    return any([
        os.getenv("LLM_API_URL") and os.getenv("LLM_API_KEY"),
        os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
        os.getenv("OPENAI_API_KEY"),
    ])


def test_llm_chat_completion_returns_text_when_keys_present():
    if not _has_any_llm_key():
        pytest.skip("No LLM keys in env")
    client = LLMClient()
    txt = client.chat_completion([
        {"role":"system","content":"用中文回答，尽量简短。"},
        {"role":"user","content":"用两句话概述Transformer是什么。"}
    ], temperature=0.2, max_tokens=256)
    assert isinstance(txt, str) and len(txt.strip()) > 10


def test_generate_script_sections_produces_structured_sections():
    if not _has_any_llm_key():
        pytest.skip("No LLM keys in env")
    client = LLMClient()
    paper = {"title":"A Study on Transformers","abstract":"We investigate ...", "authors":["A","B"], "arxiv_id":"1234.5678"}
    sections = client.generate_script_sections(paper, n_sections=3)
    assert isinstance(sections, list) and len(sections) >= 1
    # no heuristic fallback allowed when keys exist: bullets should come from LLM JSON path
    assert any(len(s.get("bullets", [])) >= 3 for s in sections)

