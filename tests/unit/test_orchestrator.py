"""
Unit tests for Orchestrator Agent
"""
import sys
sys.path.insert(0, '/Users/yxp/Documents/ghpaperauto')

from agents.orchestrator import OrchestratorAgent
from src.utils.llm_client import LLMClient


def test_orchestrator_with_real_llm():
    """Test Orchestrator with real LLM"""
    print("\n=== Testing Orchestrator Agent ===")
    
    # Initialize LLM client
    llm_client = LLMClient()
    
    # Initialize Orchestrator
    orchestrator = OrchestratorAgent(llm_client)
    
    # Test paper
    paper = {
        'title': 'Attention Is All You Need',
        'abstract': 'The dominant sequence transduction models are based on complex recurrent or convolutional neural networks. We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely.',
        'arxiv_id': 'test.001'
    }
    
    # Analyze paper
    result = orchestrator.analyze_paper(paper)
    
    # Validate result
    assert 'sections' in result, "Result must contain 'sections'"
    assert 'meta' in result, "Result must contain 'meta'"
    assert len(result['sections']) >= 3, f"Must have at least 3 sections, got {len(result['sections'])}"
    
    print(f"✓ Generated {len(result['sections'])} sections")
    print(f"✓ Token usage: {result['meta']['total_tokens']} tokens")
    
    # Validate each section
    for i, sec in enumerate(result['sections']):
        assert 'title' in sec, f"Section {i} must have title"
        assert 'summary' in sec, f"Section {i} must have summary"
        assert 'keywords' in sec, f"Section {i} must have keywords"
        assert len(sec['summary']) >= 50, f"Section {i} summary too short: {len(sec['summary'])} chars"
        
        print(f"\nSection {i+1}: {sec['title']}")
        print(f"  Summary: {sec['summary'][:100]}...")
        print(f"  Keywords: {sec['keywords']}")
    
    print(f"\n✓ All sections validated")
    print(f"✓ Total cost: ${orchestrator.total_cost:.4f}")
    
    return True


if __name__ == '__main__':
    try:
        test_orchestrator_with_real_llm()
        print("\n✅ Orchestrator Agent test PASSED")
    except Exception as e:
        print(f"\n❌ Orchestrator Agent test FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

