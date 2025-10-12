"""
Minimal AssetManager used by SlideRenderer.
Loads images from local path or URL, performs simple resizing, and caches results.
"""
from __future__ import annotations
from io import BytesIO
from pathlib import Path
from typing import Dict, Optional, Tuple
import functools

try:
    from PIL import Image  # type: ignore
except Exception:  # pragma: no cover
    Image = None  # type: ignore

try:
    import requests  # type: ignore
except Exception:  # pragma: no cover
    requests = None  # type: ignore


class AssetManager:
    def __init__(self, config: Optional[Dict] = None) -> None:
        self.config = config or {}
        self._cache: Dict[str, object] = {}

    def _open_image(self, src: str):
        if Image is None:
            return None
        # Local path
        p = Path(src)
        if p.exists():
            return Image.open(str(p)).convert("RGBA")
        # Remote URL
        if src.startswith("http://") or src.startswith("https://"):
            if requests is None:
                return None
            r = requests.get(src, timeout=10)
            r.raise_for_status()
            return Image.open(BytesIO(r.content)).convert("RGBA")
        return None

    def load_image(self, src: str, max_size: Tuple[int, int] = (800, 600)):
        key = f"{src}|{max_size[0]}x{max_size[1]}"
        if key in self._cache:
            return self._cache[key]
        img = self._open_image(src)
        if img is None:
            return None
        try:
            img.thumbnail(max_size, Image.LANCZOS)
        except Exception:
            pass
        self._cache[key] = img
        return img

    def clear_cache(self) -> None:
        self._cache.clear()

