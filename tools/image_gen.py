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
        
        # Fallback: use placeholder
        providers.append(self._generate_placeholder)
        
        for provider in providers:
            try:
                image_path = provider(prompt, slide_id, style)
                if image_path and Path(image_path).exists():
                    logger.info(f"Generated image: {image_path}")
                    return image_path
            except Exception as e:
                logger.warning(f"Image generation failed with {provider.__name__}: {e}")
        
        return None
    
    def _generate_with_dashscope(self, prompt: str, slide_id: str, style: str) -> Optional[str]:
        """Generate image using DashScope (Alibaba Cloud)"""
        try:
            import dashscope
            from dashscope import ImageSynthesis
            
            dashscope.api_key = self.dashscope_key
            
            # Enhance prompt with style
            enhanced_prompt = self._enhance_prompt(prompt, style)
            
            # Call API
            response = ImageSynthesis.call(
                model='wanx-v1',
                prompt=enhanced_prompt,
                n=1,
                size='1024*1024'
            )
            
            if response.status_code == 200 and response.output and response.output.results:
                image_url = response.output.results[0].url
                
                # Download image
                image_path = self.output_dir / f"{slide_id}_dashscope.png"
                self._download_image(image_url, image_path)
                
                return str(image_path)
        
        except Exception as e:
            logger.error(f"DashScope image generation failed: {e}")
        
        return None
    
    def _generate_with_dalle(self, prompt: str, slide_id: str, style: str) -> Optional[str]:
        """Generate image using DALL-E (OpenAI)"""
        try:
            from openai import OpenAI
            
            client = OpenAI(api_key=self.openai_key)
            
            # Enhance prompt with style
            enhanced_prompt = self._enhance_prompt(prompt, style)
            
            # Call API (DALL-E 3)
            response = client.images.generate(
                model="dall-e-3",
                prompt=enhanced_prompt,
                size="1024x1024",
                quality="standard",
                n=1,
            )
            
            image_url = response.data[0].url
            
            # Download image
            image_path = self.output_dir / f"{slide_id}_dalle.png"
            self._download_image(image_url, image_path)
            
            return str(image_path)
        
        except Exception as e:
            logger.error(f"DALL-E image generation failed: {e}")
        
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
        """Download image from URL"""
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        with open(save_path, 'wb') as f:
            f.write(response.content)
        
        logger.info(f"Downloaded image to {save_path}")

