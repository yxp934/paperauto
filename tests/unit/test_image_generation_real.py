import os
import pytest
from tools.image_gen import ImageGenerator

# Load .env manually
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

pytestmark = pytest.mark.timeout(90)

def test_image_generation_uses_real_provider_when_keys_present(tmp_path):
    has_provider = bool(os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY"))
    if not has_provider:
        pytest.skip("No image provider keys")
    gen = ImageGenerator()
    out = gen.generate_image(prompt="a clean technical diagram of an attention mechanism", slide_id="test_01", style="technical")
    assert out is not None
    assert not out.endswith("_placeholder.png"), "Should not fall back to placeholder when keys exist"

