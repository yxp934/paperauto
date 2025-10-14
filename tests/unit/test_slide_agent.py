"""
Unit tests for Slide Agent
"""
import sys
sys.path.insert(0, '/Users/yxp/Documents/ghpaperauto')

from pathlib import Path
from agents.slide_agent import SlideAgent
from src.utils.llm_client import LLMClient


def test_slide_agent():
    """Test Slide Agent with image generation"""
    print("\n=== Testing Slide Agent ===")
    
    # Initialize LLM client
    llm_client = LLMClient()
    
    # Initialize Slide Agent
    slide_agent = SlideAgent(llm_client)
    
    # Test script
    script = {
        'title': 'Transformer Architecture',
        'bullets': [
            'Self-attention mechanism',
            'Multi-head attention',
            'Position-wise feed-forward networks',
            'Positional encoding',
            'Layer normalization'
        ]
    }
    
    # Test paper context
    paper_context = {
        'title': 'Attention Is All You Need',
        'abstract': 'The Transformer model architecture based on attention mechanisms.'
    }
    
    # Generate slide plan
    slide_plan = slide_agent.generate_slide_plan(script, paper_context, slide_index=1)
    
    # Validate result
    assert 'title' in slide_plan, "Slide plan must have title"
    assert 'bullets' in slide_plan, "Slide plan must have bullets"
    assert 'image_path' in slide_plan, "Slide plan must have image_path"
    assert 'image_prompt' in slide_plan, "Slide plan must have image_prompt"
    assert 'meta' in slide_plan, "Slide plan must have meta"
    
    print(f"✓ Generated slide plan for '{slide_plan['title']}'")
    
    # Validate bullets
    bullets = slide_plan['bullets']
    assert len(bullets) >= 3, f"Must have at least 3 bullets, got {len(bullets)}"
    assert len(bullets) <= 5, f"Must have at most 5 bullets, got {len(bullets)}"
    print(f"✓ Bullets: {len(bullets)} items")
    for i, bullet in enumerate(bullets):
        print(f"  {i+1}. {bullet}")
    
    # Validate image
    image_path = slide_plan['image_path']
    assert image_path is not None, "Image path must not be None"
    assert Path(image_path).exists(), f"Image file must exist: {image_path}"
    
    file_size = Path(image_path).stat().st_size
    print(f"✓ Image generated: {image_path}")
    print(f"  File size: {file_size} bytes")
    print(f"  Prompt: {slide_plan['image_prompt'][:100]}...")
    
    # Token usage
    meta = slide_plan['meta']
    total_tokens = meta.get('total_tokens', 0)
    print(f"✓ Token usage: {total_tokens} tokens")
    print(f"✓ Total cost: ${slide_agent.total_cost:.4f}")
    
    return True


if __name__ == '__main__':
    try:
        test_slide_agent()
        print("\n✅ Slide Agent test PASSED")
    except Exception as e:
        print(f"\n❌ Slide Agent test FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

