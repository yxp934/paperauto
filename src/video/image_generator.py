import io
import os
import random
import json
import logging
import time
from typing import Optional
from urllib import request, error
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


class ImageGenerator:
    """
    Minimal image generator used by Orchestrator.
    - generate_image_with_api(prompt): try to call a remote API if configured; otherwise generate a placeholder
    - generate_fallback_image(text, title): solid background with text
    - _download_image(url): helper to fetch remote image
    - save_temp_image(img): save PIL image to a temp file and return path
    """

    def __init__(self) -> None:
        self.tmp_dir = os.path.join("temp", "images")
        os.makedirs(self.tmp_dir, exist_ok=True)

        # ModelScope API 配置
        self.image_api_url = os.getenv("IMAGE_API_URL", "https://api-inference.modelscope.cn/v1/images/generations")
        self.image_api_key = os.getenv("IMAGE_API_KEY", "")
        self.image_model = os.getenv("IMAGE_MODEL", "MusePublic/Qwen-image")

    def generate_image_with_api(self, prompt: str) -> Image.Image:
        """
        使用 ModelScope API 生成图片

        Args:
            prompt: 图片生成提示词

        Returns:
            PIL.Image: 生成的图片（失败时返回占位图）
        """
        if not self.image_api_key:
            logger.warning("IMAGE_API_KEY 未配置，使用占位图")
            return self.generate_fallback_image(prompt or "tech diagram", title="")

        try:
            # 调用 ModelScope API
            body = {
                "model": self.image_model,
                "prompt": prompt,
                "n": 1,
                "size": "1024x1024",  # ModelScope 支持的尺寸
            }

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.image_api_key}",
            }

            data = json.dumps(body).encode("utf-8")
            req = request.Request(
                self.image_api_url,
                data=data,
                headers=headers,
                method="POST"
            )

            logger.info(f"调用 ModelScope API 生成图片: {prompt[:50]}...")

            with request.urlopen(req, timeout=60) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")

            result = json.loads(raw)

            # 解析响应（ModelScope 返回格式: {"data": [{"url": "..."}]}）
            if "data" in result and len(result["data"]) > 0:
                image_url = result["data"][0].get("url")
                if image_url:
                    logger.info(f"图片生成成功，下载中...")
                    img = self._download_image(image_url)
                    if img:
                        # 调整尺寸为 1920x1080（适合 Slide）
                        img = img.resize((1920, 1080), Image.Resampling.LANCZOS)
                        logger.info(f"图片下载并调整尺寸成功")
                        return img

            logger.warning("ModelScope API 返回格式异常，使用占位图")
            return self.generate_fallback_image(prompt or "tech diagram", title="")

        except error.HTTPError as e:
            logger.error(f"ModelScope API 调用失败 (HTTP {e.code}): {e.reason}")
            return self.generate_fallback_image(prompt or "tech diagram", title="")
        except Exception as e:
            logger.error(f"图片生成异常: {e}")
            return self.generate_fallback_image(prompt or "tech diagram", title="")

    def generate_fallback_image(self, text: str, title: str, size=(1280, 720)) -> Image.Image:
        img = Image.new("RGB", size, color=self._rand_bg())
        d = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("Arial Unicode.ttf", 40)
        except Exception:
            font = ImageFont.load_default()
        snippet = (title or text or "").strip()[:60]
        d.text((40, 40), snippet, fill=(255, 255, 255), font=font)
        return img

    def _download_image(self, url: str) -> Optional[Image.Image]:
        try:
            with request.urlopen(url, timeout=20) as resp:
                data = resp.read()
            return Image.open(io.BytesIO(data))
        except Exception:
            return None

    def save_temp_image(self, img: Image.Image) -> str:
        path = os.path.join(self.tmp_dir, f"img_{random.randint(10_000, 99_999)}.png")
        img.save(path, "PNG", optimize=True)
        return path

    @staticmethod
    def _rand_bg():
        import random
        # dark gradient-ish color
        base = random.randint(20, 80)
        return (base, base + 20, base + 40)




# ============================================================================
# 步骤5: 统一资源生成函数
# ============================================================================

def generate_image(prompt: str) -> str:
    """
    生成图片并返回本地路径

    Args:
        prompt: 图片生成提示词

    Returns:
        str: 图片文件路径
    """
    generator = ImageGenerator()
    img = generator.generate_image_with_api(prompt)
    path = generator.save_temp_image(img)
    logger.info(f"图片已保存: {path}")
    return path


def generate_chart(chart_type: str, data: dict) -> str:
    """
    生成图表并返回本地路径

    Args:
        chart_type: 图表类型 (bar, line, pie, scatter)
        data: 图表数据，包含 labels/values/ylabel 等

    Returns:
        str: 图表文件路径
    """
    from src.slide.chart_generator import ChartGenerator

    generator = ChartGenerator()
    chart_img = generator.generate_chart(
        chart_type=chart_type,
        labels=data.get("labels", []),
        values=data.get("values", []),
        title=data.get("title", ""),
        ylabel=data.get("ylabel", "Value"),
    )

    # 保存图表
    tmp_dir = os.path.join("temp", "charts")
    os.makedirs(tmp_dir, exist_ok=True)
    path = os.path.join(tmp_dir, f"chart_{random.randint(10_000, 99_999)}.png")
    chart_img.save(path, "PNG")
    logger.info(f"图表已保存: {path}")
    return path


def generate_table(headers: list, rows: list) -> str:
    """
    生成表格并返回本地路径

    Args:
        headers: 表头列表
        rows: 行数据列表

    Returns:
        str: 表格图片文件路径
    """
    from src.slide.table_generator import TableGenerator

    generator = TableGenerator()
    table_img = generator.generate_table(headers=headers, rows=rows)

    # 保存表格
    tmp_dir = os.path.join("temp", "tables")
    os.makedirs(tmp_dir, exist_ok=True)
    path = os.path.join(tmp_dir, f"table_{random.randint(10_000, 99_999)}.png")
    table_img.save(path, "PNG")
    logger.info(f"表格已保存: {path}")
    return path

