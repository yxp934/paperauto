"""
Minimal FontManager used by SlideRenderer.
Provides basic font loading with sensible fallbacks and a tiny cache.
"""
from __future__ import annotations
from pathlib import Path
from typing import Dict, Optional, Tuple

try:
    from PIL import ImageFont  # type: ignore
except Exception:  # pragma: no cover
    ImageFont = None  # type: ignore


class FontManager:
    def __init__(self, config: Optional[Dict] = None) -> None:
        self.config = config or {}
        self._cache: Dict[Tuple[str, int], object] = {}

    def get_font(self, family: str = "Arial Unicode.ttf", size: int = 32):
        if ImageFont is None:
            return None
        key = (family, size)
        if key in self._cache:
            return self._cache[key]
        # Try load truetype; fallback to default
        font = None
        try:
            # If absolute path provided
            p = Path(family)
            if p.exists():
                font = ImageFont.truetype(str(p), size)
            else:
                # Let PIL search system font path by family string
                font = ImageFont.truetype(family, size)
        except Exception:
            try:
                font = ImageFont.load_default()
            except Exception:
                font = None
        self._cache[key] = font
        return font

    def clear_cache(self) -> None:
        self._cache.clear()

