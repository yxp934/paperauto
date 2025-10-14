"""
Slide Agent - generates slide layouts and images
"""
import logging
from typing import Dict, List, Optional
from agents.base import BaseAgent
from tools.image_gen import ImageGenerator

logger = logging.getLogger(__name__)


class SlideAgent(BaseAgent):
    """Agent for generating slide layouts and images"""
    
    def __init__(self, llm_client):
        super().__init__("SlideAgent")
        self.llm_client = llm_client
        self.image_generator = ImageGenerator()
    
    def generate_slide_plan(self, script: Dict, paper_context: Dict, slide_index: int) -> Dict:
        """
        Generate slide layout plan and image
        
        Args:
            script: {title, bullets, narration_parts}
            paper_context: {title, abstract}
            slide_index: Index of this slide (for unique ID)
            
        Returns:
            {
                "title": str,
                "bullets": [str],
                "image_path": str,
                "image_prompt": str,
                "meta": {token counts}
            }
        """
        title = script.get('title', 'Slide')
        bullets = script.get('bullets', [])[:5]
        
        # Generate image prompt using LLM
        image_prompt_data = self._generate_image_prompt(title, bullets, paper_context)
        
        # Generate image
        slide_id = f"slide_{slide_index:02d}"
        image_path = self.image_generator.generate_image(
            prompt=image_prompt_data['prompt'],
            slide_id=slide_id,
            style=image_prompt_data.get('style', 'professional')
        )
        
        return {
            'title': title,
            'bullets': bullets,
            'image_path': image_path,
            'image_prompt': image_prompt_data['prompt'],
            'image_description': image_prompt_data.get('description', ''),
            'meta': image_prompt_data.get('meta', {})
        }
    
    def _generate_image_prompt(self, slide_title: str, slide_bullets: List[str], paper_context: Dict) -> Dict:
        """Generate image prompt using LLM"""
        # Load prompt template
        prompt_template = self.load_prompt("image_gen.yaml")
        
        try:
            # Build messages
            system_msg = {"role": "system", "content": prompt_template.get("system", "")}
            user_content = prompt_template.get("user", "").format(
                slide_title=slide_title,
                slide_bullets="\n".join([f"- {b}" for b in slide_bullets]),
                paper_title=paper_context.get('title', '')
            )
            user_msg = {"role": "user", "content": user_content}
            
            # Call LLM
            response, prompt_tokens, completion_tokens = self.call_llm(
                [system_msg, user_msg],
                temperature=0.5,
                max_tokens=1024
            )
            
            # Extract JSON
            data = self.extract_json(response)
            if data and 'prompt' in data:
                data['meta'] = {
                    'prompt_tokens': prompt_tokens,
                    'completion_tokens': completion_tokens,
                    'total_tokens': prompt_tokens + completion_tokens
                }
                return data
        
        except Exception as e:
            logger.warning(f"[SlideAgent] Image prompt generation failed: {e}")
        
        # Fallback: heuristic prompt
        return self._heuristic_image_prompt(slide_title, slide_bullets, paper_context)
    
    def _heuristic_image_prompt(self, slide_title: str, slide_bullets: List[str], paper_context: Dict) -> Dict:
        """Heuristic fallback for image prompt"""
        # Extract keywords from title and bullets
        keywords = []
        for text in [slide_title] + slide_bullets:
            words = text.split()
            keywords.extend([w for w in words if len(w) > 3])
        
        # Build prompt
        prompt = f"A professional diagram illustrating {slide_title}, showing {', '.join(keywords[:5])}, clean modern style, technical illustration"
        
        return {
            'prompt': prompt,
            'style': 'professional',
            'description': f'{slide_title}的示意图',
            'meta': {
                'prompt_tokens': 0,
                'completion_tokens': 0,
                'total_tokens': 0,
                'fallback': True
            }
        }

