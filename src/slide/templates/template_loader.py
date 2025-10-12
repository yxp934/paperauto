"""
Minimal TemplateLoader and basic templates for SlideRenderer.
Provides a few simple layouts: text_bullets, title_only, centered_image, left_image_right_text, top_image_bottom_text.
"""
from __future__ import annotations
from typing import Dict, Optional, Any, List

try:
    from PIL import Image, ImageDraw, ImageFont  # type: ignore
except Exception:  # pragma: no cover
    Image = None  # type: ignore


class BaseTemplate:
    name = "base"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.resolution = tuple(self.config.get("resolution", (1920, 1080)))
        self.bg_color = self.config.get("bg_color", "#0b1020")
        self.fg_color = self.config.get("text_color", "#eaeef7")

    def render(self, data: Dict[str, Any]):
        if Image is None:
            return None
        img = Image.new("RGB", self.resolution, self.bg_color)
        d = ImageDraw.Draw(img)
        title = str(data.get("title", "Slide"))
        bullets = data.get("bullets") or []
        try:
            font_title = ImageFont.truetype("Arial Unicode.ttf", 64)
            font_bullet = ImageFont.truetype("Arial Unicode.ttf", 36)
        except Exception:
            font_title = ImageFont.load_default()
            font_bullet = ImageFont.load_default()
        d.text((80, 80), title[:160], fill=self.fg_color, font=font_title)
        y = 180
        for b in bullets[:10]:
            d.text((120, y), f"• {str(b)[:180]}", fill=self.fg_color, font=font_bullet)
            y += 56
        # If image provided, paste
        if data.get("image") is not None:
            try:
                im = data["image"].copy()
                im.thumbnail((900, 700))
                img.paste(im, (img.width - im.width - 80, img.height - im.height - 80))
            except Exception:
                pass
        return img


class TitleOnlyTemplate(BaseTemplate):
    name = "title_only"


class TextBulletsTemplate(BaseTemplate):
    name = "text_bullets"


class CenteredImageTemplate(BaseTemplate):
    name = "centered_image"

    def render(self, data: Dict[str, Any]):
        img = super().render({"title": data.get("title", ""), "bullets": []})
        if img and data.get("image") is not None:
            try:
                im = data["image"].copy()
                im.thumbnail((min(img.width, 1200), min(img.height, 800)))
                img.paste(im, ((img.width - im.width)//2, (img.height - im.height)//2))
            except Exception:
                pass
        return img


class LeftImageRightTextTemplate(BaseTemplate):
    name = "left_image_right_text"

    def render(self, data: Dict[str, Any]):
        if Image is None:
            return None
        img = Image.new("RGB", self.resolution, self.bg_color)
        d = ImageDraw.Draw(img)
        try:
            font_title = ImageFont.truetype("Arial Unicode.ttf", 60)
            font_bullet = ImageFont.truetype("Arial Unicode.ttf", 34)
        except Exception:
            font_title = ImageFont.load_default()
            font_bullet = ImageFont.load_default()
        # Image on left
        if data.get("image") is not None:
            im = data["image"].copy()
            im.thumbnail((img.width//2 - 120, img.height - 160))
            img.paste(im, (80, (img.height - im.height)//2))
        # Text on right
        x0 = img.width//2 + 40
        d.text((x0, 80), str(data.get("title", ""))[:160], fill=self.fg_color, font=font_title)
        y = 180
        for b in (data.get("bullets") or [])[:10]:
            d.text((x0+40, y), f"• {str(b)[:180]}", fill=self.fg_color, font=font_bullet)
            y += 52
        return img


class TopImageBottomTextTemplate(BaseTemplate):
    name = "top_image_bottom_text"

    def render(self, data: Dict[str, Any]):
        if Image is None:
            return None
        img = Image.new("RGB", self.resolution, self.bg_color)
        d = ImageDraw.Draw(img)
        try:
            font_title = ImageFont.truetype("Arial Unicode.ttf", 60)
            font_bullet = ImageFont.truetype("Arial Unicode.ttf", 34)
        except Exception:
            font_title = ImageFont.load_default()
            font_bullet = ImageFont.load_default()
        # Image on top
        yy = 80
        if data.get("image") is not None:
            im = data["image"].copy()
            im.thumbnail((img.width - 160, img.height//2))
            img.paste(im, ((img.width - im.width)//2, yy))
            yy += im.height + 40
        d.text((80, yy), str(data.get("title", ""))[:160], fill=self.fg_color, font=font_title)
        yy += 80
        for b in (data.get("bullets") or [])[:8]:
            d.text((120, yy), f"• {str(b)[:180]}", fill=self.fg_color, font=font_bullet)
            yy += 52
        return img


class TemplateLoader:
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}
        self._templates: Dict[str, BaseTemplate] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        for T in [TitleOnlyTemplate, TextBulletsTemplate, CenteredImageTemplate,
                  LeftImageRightTextTemplate, TopImageBottomTextTemplate]:
            t = T(config=self.config)
            self._templates[t.name] = t

    def load_template(self, name: str) -> BaseTemplate:
        return self._templates.get(name) or self._templates["text_bullets"]

    def get_available_templates(self) -> list[str]:
        return list(self._templates.keys())

    def preload_templates(self, template_names: list[str]) -> None:
        # Nothing to do in minimal loader
        return None

    def get_template_info(self, template_name: str) -> Optional[Dict[str, Any]]:
        if template_name not in self._templates:
            return None
        return {"name": template_name, "config": dict(self.config)}

