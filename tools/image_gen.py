"""
Image generation tool using ModelScope/DALL-E/Stable Diffusion
"""
import os
import logging
import requests
from pathlib import Path
from typing import Optional, Dict
import time

logger = logging.getLogger(__name__)


class ImageGenerator:
    """Generate images for slides using various APIs"""

    def __init__(self):
        self.output_dir = Path("output/generated_images")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Check available API keys
        self.openai_key = os.getenv('OPENAI_API_KEY')
        self.dashscope_key = os.getenv('DASHSCOPE_API_KEY')

    def generate_image(self, prompt: str, slide_id: str, style: str = "professional") -> Optional[str]:
        """
        Generate image from prompt

        Args:
            prompt: Image generation prompt (English)
            slide_id: Unique identifier for the slide
            style: Image style (professional/academic/technical/illustration)

        Returns:
            Path to generated image file, or None if failed
        """
        # Try different providers in order
        providers = []

        if self.dashscope_key:
            providers.append(self._generate_with_dashscope)
        if self.openai_key:
            providers.append(self._generate_with_dalle)
            providers.append(self._generate_with_openai_rest)
        # ModelScope Image API if configured
        if os.getenv("IMAGE_API_URL") and os.getenv("IMAGE_API_KEY") and os.getenv("IMAGE_MODEL"):
            providers.append(self._generate_with_modelscope)

        # 禁止使用占位图作为回退；如果所有真实提供方均失败，则抛出异常
        # providers.append(self._generate_placeholder)

        last_err = None
        for provider in providers:
            try:
                image_path = provider(prompt, slide_id, style)
                if image_path and Path(image_path).exists():
                    logger.info(f"Generated image: {image_path}")
                    return image_path
            except Exception as e:
                last_err = e
                logger.warning(f"Image generation failed with {provider.__name__}: {e}")

        raise RuntimeError(f"All image providers failed for slide {slide_id}: {last_err}")

    def _generate_with_dashscope(self, prompt: str, slide_id: str, style: str) -> Optional[str]:
        """Generate image using DashScope (Alibaba Cloud)"""
        try:
            import dashscope
            from dashscope import ImageSynthesis

            dashscope.api_key = self.dashscope_key

            enhanced_prompt = self._enhance_prompt(prompt, style)
            last_err = None
            for attempt in range(4):
                try:
                    response = ImageSynthesis.call(
                        model='wanx-v1',
                        prompt=enhanced_prompt,
                        n=1,
                        size='1024*1024'
                    )
                    if response.status_code == 200 and response.output and response.output.results:
                        image_url = response.output.results[0].url
                        image_path = self.output_dir / f"{slide_id}_dashscope.png"
                        self._download_image(image_url, image_path)
                        return str(image_path)
                    raise RuntimeError(f"DashScope unexpected response: {getattr(response, 'status_code', '?')}")
                except Exception as e:
                    last_err = e
                    msg = str(e)
                    # Retry on network/5xx/empty
                    if attempt < 3:
                        wait_seconds = 2 ** (attempt + 1)
                        logger.warning(f"[ImageGen] DashScope API call failed (attempt {attempt+1}/4): {msg[:200]}, retrying in {wait_seconds}s...")
                        time.sleep(wait_seconds)
                    else:
                        logger.error(f"DashScope image generation failed (final): {msg}")
                        break
        except Exception as e:
            logger.error(f"DashScope image generation failed: {e}")

        return None

    def _generate_with_dalle(self, prompt: str, slide_id: str, style: str) -> Optional[str]:
        """Generate image using DALL-E (OpenAI SDK)"""
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.openai_key)
            enhanced_prompt = self._enhance_prompt(prompt, style)
            last_err = None
            for attempt in range(4):
                try:
                    response = client.images.generate(
                        model=os.getenv("OPENAI_IMAGE_MODEL", "dall-e-3"),
                        prompt=enhanced_prompt,
                        size=os.getenv("OPENAI_IMAGE_SIZE", "1024x1024"),
                        quality="standard",
                        n=1,
                    )
                    image_url = response.data[0].url
                    image_path = self.output_dir / f"{slide_id}_dalle.png"
                    self._download_image(image_url, image_path)
                    return str(image_path)
                except Exception as e:
                    last_err = e
                    if attempt < 3:
                        wait_seconds = 2 ** (attempt + 1)
                        logger.warning(f"[ImageGen] DALL-E API call failed (attempt {attempt+1}/4): {str(e)[:200]}, retrying in {wait_seconds}s...")
                        time.sleep(wait_seconds)
                    else:
                        logger.error(f"DALL-E image generation failed (final): {e}")
                        break
        except Exception as e:
            logger.error(f"DALL-E image generation failed: {e}")
        return None

    def _generate_with_openai_rest(self, prompt: str, slide_id: str, style: str) -> Optional[str]:
        """Generate image using OpenAI Images API via REST to avoid SDK dependency."""
        try:
            import json, urllib.request, urllib.error
            enhanced_prompt = self._enhance_prompt(prompt, style)
            base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com").rstrip('/')
            last_err = None
            for attempt in range(4):
                try:
                    req = urllib.request.Request(
                        url=f"{base}/v1/images/generations",
                        data=json.dumps({
                            "model": os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1"),
                            "prompt": enhanced_prompt,
                            "size": os.getenv("OPENAI_IMAGE_SIZE", "1024x1024"),
                            "n": 1
                        }).encode("utf-8"),
                        headers={
                            "Content-Type": "application/json",
                            "Authorization": f"Bearer {self.openai_key}",
                        },
                        method="POST",
                    )
                    with urllib.request.urlopen(req) as resp:
                        obj = json.loads(resp.read().decode("utf-8", errors="ignore"))
                    data = obj.get("data") or []
                    if isinstance(data, list) and data:
                        if data[0].get("url"):
                            image_url = data[0]["url"]
                            image_path = self.output_dir / f"{slide_id}_openai.png"
                            self._download_image(image_url, image_path)
                            return str(image_path)
                        if data[0].get("b64_json"):
                            import base64
                            image_path = self.output_dir / f"{slide_id}_openai.png"
                            with open(image_path, 'wb') as f:
                                f.write(base64.b64decode(data[0]["b64_json"]))
                            return str(image_path)
                    raise RuntimeError("OpenAI Images REST returned empty data")
                except urllib.error.HTTPError as e:
                    code = getattr(e, 'code', 0)
                    body = ""
                    try:
                        body = e.read().decode("utf-8", errors="ignore")
                    except Exception:
                        pass
                    if code in (400, 401, 403, 404):
                        logger.error(f"OpenAI Images REST failed {code}: {body[:300]}")
                        return None
                    if attempt < 3:
                        wait_seconds = 2 ** (attempt + 1)
                        logger.warning(f"[ImageGen] OpenAI Images REST call failed (attempt {attempt+1}/4): HTTP {code} {body[:160]}, retrying in {wait_seconds}s...")
                        time.sleep(wait_seconds)
                    else:
                        last_err = e
                        logger.error(f"OpenAI REST image generation failed (final {code}): {body[:300]}")
                        break
                except urllib.error.URLError as e:
                    last_err = e
                    if attempt < 3:
                        wait_seconds = 2 ** (attempt + 1)
                        logger.warning(f"[ImageGen] OpenAI Images REST call failed (attempt {attempt+1}/4): {str(e)[:200]}, retrying in {wait_seconds}s...")
                        time.sleep(wait_seconds)
                    else:
                        logger.error(f"OpenAI REST image generation failed (final): {e}")
                        break
                except Exception as e:
                    last_err = e
                    if attempt < 3:
                        wait_seconds = 2 ** (attempt + 1)
                        logger.warning(f"[ImageGen] OpenAI Images REST call failed (attempt {attempt+1}/4): {str(e)[:200]}, retrying in {wait_seconds}s...")
                        time.sleep(wait_seconds)
                    else:
                        logger.error(f"OpenAI REST image generation failed (final): {e}")
                        break
        except Exception as e:
            logger.error(f"OpenAI REST image generation failed: {e}")
        return None

    def _generate_with_modelscope(self, prompt: str, slide_id: str, style: str) -> Optional[str]:
        """Generate image using ModelScope Images API (async mode with polling)."""
        try:
            import json, requests, time
            api_url = os.getenv("IMAGE_API_URL") or "https://api-inference.modelscope.cn/v1/images/generations"
            api_key = os.getenv("IMAGE_API_KEY")
            model = os.getenv("IMAGE_MODEL") or "Qwen/Qwen-Image"
            if not (api_url and api_key and model):
                return None
            enhanced_prompt = self._enhance_prompt(prompt, style)
            base_url = api_url.split("/v1/")[0].rstrip('/') + '/'
            last_err = None
            for attempt in range(4):
                try:
                    headers = {
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "X-ModelScope-Async-Mode": "true",
                    }
                    submit = requests.post(
                        api_url,
                        headers=headers,
                        data=json.dumps({
                            "model": model,
                            "prompt": enhanced_prompt
                        }, ensure_ascii=False).encode('utf-8')
                    )
                    # Retryable on 429/5xx
                    if submit.status_code in (429, 500, 502, 503, 504):
                        raise RuntimeError(f"ModelScope submit HTTP {submit.status_code}: {submit.text[:160]}")
                    submit.raise_for_status()
                    task_id = submit.json().get("task_id")
                    if not task_id:
                        raise RuntimeError(f"ModelScope submit missing task_id: {submit.text[:200]}")
                    poll_headers = {
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "X-ModelScope-Task-Type": "image_generation",
                    }
                    image_url = None
                    for _ in range(18):
                        r = requests.get(f"{base_url}v1/tasks/{task_id}", headers=poll_headers)
                        if r.status_code in (429, 500, 502, 503, 504):
                            time.sleep(5)
                            continue
                        r.raise_for_status()
                        data = r.json()
                        status = data.get("task_status")
                        if status == "SUCCEED":
                            outs = data.get("output_images") or []
                            if outs:
                                image_url = outs[0]
                            break
                        if status == "FAILED":
                            raise RuntimeError(f"ModelScope task failed: {data}")
                        time.sleep(5)
                    if not image_url:
                        raise RuntimeError("ModelScope task did not succeed in time")
                    image_path = self.output_dir / f"{slide_id}_modelscope.jpg"
                    # Download with simple retry (reuse helper)
                    self._download_image(image_url, image_path)
                    return str(image_path)
                except Exception as e:
                    last_err = e
                    msg = str(e)
                    if attempt < 3:
                        wait_seconds = 2 ** (attempt + 1)
                        logger.warning(f"[ImageGen] ModelScope API call failed (attempt {attempt+1}/4): {msg[:200]}, retrying in {wait_seconds}s...")
                        time.sleep(wait_seconds)
                    else:
                        logger.error(f"ModelScope image generation failed (final): {msg}")
                        break
        except Exception as e:
            logger.error(f"ModelScope image generation failed: {e}")
        return None

    def _generate_placeholder(self, prompt: str, slide_id: str, style: str) -> str:
        """Generate a simple placeholder image using PIL"""
        try:
            from PIL import Image, ImageDraw, ImageFont

            # Create image
            img = Image.new('RGB', (1024, 1024), color=(240, 240, 245))
            draw = ImageDraw.Draw(img)

            # Add text
            try:
                font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 40)
            except:
                font = ImageFont.load_default()

            # Wrap text
            text = f"Image: {prompt[:100]}"
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            x = (1024 - text_width) // 2
            y = (1024 - text_height) // 2

            draw.text((x, y), text, fill=(100, 100, 120), font=font)

            # Save
            image_path = self.output_dir / f"{slide_id}_placeholder.png"
            img.save(image_path)

            logger.info(f"Generated placeholder image: {image_path}")
            return str(image_path)

        except Exception as e:
            logger.error(f"Placeholder generation failed: {e}")
            return None

    def _enhance_prompt(self, prompt: str, style: str) -> str:
        """Enhance prompt with style keywords"""
        style_keywords = {
            'professional': 'professional, clean, modern, business style',
            'academic': 'academic, scholarly, educational, diagram style',
            'technical': 'technical, engineering, blueprint, schematic style',
            'illustration': 'illustration, artistic, colorful, infographic style'
        }

        keywords = style_keywords.get(style, style_keywords['professional'])
        return f"{prompt}, {keywords}, high quality, detailed"

    def _download_image(self, url: str, save_path: Path):
        """Download image from URL with unified retries"""
        last_err = None
        for attempt in range(4):
            try:
                response = requests.get(url)
                # Retryable status codes
                if response.status_code in (429, 500, 502, 503, 504):
                    raise RuntimeError(f"HTTP {response.status_code}")
                response.raise_for_status()
                with open(save_path, 'wb') as f:
                    f.write(response.content)
                logger.info(f"Downloaded image to {save_path}")
                return
            except Exception as e:
                last_err = e
                if attempt < 3:
                    wait_seconds = 2 ** (attempt + 1)
                    logger.warning(f"[ImageGen] download failed (attempt {attempt+1}/4): {str(e)[:200]}, retrying in {wait_seconds}s...")
                    time.sleep(wait_seconds)
                else:
                    logger.error(f"Image download failed (final): {e}")
                    raise

