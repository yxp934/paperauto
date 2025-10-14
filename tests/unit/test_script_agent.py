"""
Unit tests for Script Agent
"""
import sys
sys.path.insert(0, '/Users/yxp/Documents/ghpaperauto')

from agents.script_agent import ScriptAgent
from src.utils.llm_client import LLMClient


def test_script_agent():
    """Test Script Agent with real LLM"""
    print("\n=== Testing Script Agent ===")
    
    # Initialize LLM client
    llm_client = LLMClient()
    
    # Initialize Script Agent (without retriever for now)
    script_agent = ScriptAgent(llm_client, retriever=None)
    
    # Test section
    section = {
        'title': 'Introduction and Background',
        'summary': '本部分介绍Transformer模型的研究背景、问题陈述和研究意义。我们将从该领域的发展历程、现有方法的局限性以及本研究的创新点展开讨论。',
        'keywords': ['背景', '问题', '动机', 'Transformer']
    }
    
    # Test paper context
    paper_context = {
        'title': 'Attention Is All You Need',
        'abstract': 'The dominant sequence transduction models are based on complex recurrent or convolutional neural networks. We propose a new simple network architecture, the Transformer, based solely on attention mechanisms.',
        'arxiv_id': 'test.001'
    }
    
    # Generate script
    script = script_agent.generate_script(section, paper_context)
    
    # Validate result
    assert 'title' in script, "Script must have title"
    assert 'bullets' in script, "Script must have bullets"
    assert 'narration_parts' in script, "Script must have narration_parts"
    assert 'meta' in script, "Script must have meta"
    
    print(f"✓ Generated script for '{script['title']}'")
    
    # Validate bullets
    bullets = script['bullets']
    assert len(bullets) >= 3, f"Must have at least 3 bullets, got {len(bullets)}"
    assert len(bullets) <= 5, f"Must have at most 5 bullets, got {len(bullets)}"
    print(f"✓ Bullets: {len(bullets)} items")
    for i, bullet in enumerate(bullets):
        print(f"  {i+1}. {bullet}")
    
    # Validate narration parts
    parts = script['narration_parts']
    assert len(parts) == 2, f"Must have exactly 2 narration parts, got {len(parts)}"
    
    for i, part in enumerate(parts):
        part_len = len(part)
        assert part_len >= 600, f"Part {i+1} too short: {part_len} chars (minimum 600)"
        print(f"✓ Narration part {i+1}: {part_len} chars")
        print(f"  Preview: {part[:100]}...")
    
    # Validate Chinese ratio
    meta = script['meta']
    zh_ratio = meta.get('zh_ratio', 0.0)
    assert zh_ratio >= 0.7, f"Chinese ratio too low: {zh_ratio:.2f} (minimum 0.7)"
    print(f"✓ Chinese ratio: {zh_ratio:.2f}")
    
    # Token usage
    total_tokens = meta.get('total_tokens', 0)
    print(f"✓ Token usage: {total_tokens} tokens")
    print(f"✓ Total cost: ${script_agent.total_cost:.4f}")
    
    return True


if __name__ == '__main__':
    try:
        test_script_agent()
        print("\n✅ Script Agent test PASSED")
    except Exception as e:
        print(f"\n❌ Script Agent test FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

