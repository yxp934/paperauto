"""
Integration test for A2A Workflow
"""
import sys
sys.path.insert(0, '/Users/yxp/Documents/ghpaperauto')

from graph.workflow import A2AWorkflow
from src.utils.llm_client import LLMClient


def test_workflow():
    """Test complete A2A workflow"""
    print("\n=== Testing A2A Workflow ===")
    
    # Initialize LLM client
    llm_client = LLMClient()
    
    # Log callback
    def log_callback(msg):
        agent = msg.get('agent', 'unknown')
        message = msg.get('message', '')
        print(f"[{agent}] {message}")
    
    # Initialize workflow
    workflow = A2AWorkflow(llm_client, log_callback=log_callback)
    
    # Test paper
    paper = {
        'title': 'Attention Is All You Need',
        'abstract': 'The dominant sequence transduction models are based on complex recurrent or convolutional neural networks in an encoder-decoder configuration. The best performing models also connect the encoder and decoder through an attention mechanism. We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely.',
        'arxiv_id': 'test.transformer',
        'authors': ['Vaswani et al.']
    }
    
    # Run workflow
    result = workflow.run(paper, max_qa_retries=1)
    
    # Validate result
    assert 'sections' in result, "Result must contain sections"
    assert 'scripts' in result, "Result must contain scripts"
    assert 'slides' in result, "Result must contain slides"
    assert 'qa_report' in result, "Result must contain qa_report"
    assert 'meta' in result, "Result must contain meta"
    
    sections = result['sections']
    scripts = result['scripts']
    slides = result['slides']
    qa_report = result['qa_report']
    meta = result['meta']
    
    print(f"\n=== Workflow Results ===")
    print(f"Sections: {len(sections)}")
    print(f"Scripts: {len(scripts)}")
    print(f"Slides: {len(slides)}")
    
    # Validate sections
    assert len(sections) >= 3, f"Must have at least 3 sections, got {len(sections)}"
    for i, section in enumerate(sections):
        print(f"\nSection {i+1}: {section['title']}")
        print(f"  Summary: {section['summary'][:80]}...")
        print(f"  Keywords: {section['keywords']}")
    
    # Validate scripts
    assert len(scripts) == len(sections), f"Scripts count ({len(scripts)}) must match sections count ({len(sections)})"
    for i, script in enumerate(scripts):
        parts = script.get('narration_parts', [])
        print(f"\nScript {i+1}: {script['title']}")
        print(f"  Bullets: {len(script.get('bullets', []))}")
        print(f"  Narration parts: {len(parts)}")
        for j, part in enumerate(parts):
            print(f"    Part {j+1}: {len(part)} chars")
    
    # Validate slides
    assert len(slides) == len(scripts), f"Slides count ({len(slides)}) must match scripts count ({len(scripts)})"
    for i, slide in enumerate(slides):
        print(f"\nSlide {i+1}: {slide['title']}")
        print(f"  Bullets: {len(slide.get('bullets', []))}")
        print(f"  Image: {slide.get('image_path', 'N/A')}")
    
    # Validate QA report
    print(f"\n=== QA Report ===")
    print(f"Overall: {'PASSED' if qa_report['overall_passed'] else 'FAILED'}")
    print(f"Scripts passed: {qa_report['scripts_passed']}")
    print(f"Slides passed: {qa_report['slides_passed']}")
    print(f"Stats:")
    for key, value in qa_report['stats'].items():
        print(f"  {key}: {value}")
    
    if qa_report['scripts_issues']:
        print(f"\nScripts issues:")
        for issue in qa_report['scripts_issues']:
            print(f"  - {issue}")
    
    if qa_report['slides_issues']:
        print(f"\nSlides issues:")
        for issue in qa_report['slides_issues']:
            print(f"  - {issue}")
    
    # Validate meta
    print(f"\n=== Token Usage ===")
    print(f"Total tokens: {meta['total_tokens']}")
    print(f"  Orchestrator: {meta['orchestrator_tokens']}")
    print(f"  Script Agent: {meta['script_agent_tokens']}")
    print(f"  Slide Agent: {meta['slide_agent_tokens']}")
    print(f"Total cost: ${meta['total_cost']:.4f}")
    
    print(f"\n✅ Workflow integration test PASSED")
    return True


if __name__ == '__main__':
    try:
        test_workflow()
    except Exception as e:
        print(f"\n❌ Workflow integration test FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

