"""
Unit tests for QA Agent
"""
import sys
sys.path.insert(0, '/Users/yxp/Documents/ghpaperauto')

from agents.qa_agent import QAAgent


def test_qa_agent():
    """Test QA Agent with sample data"""
    print("\n=== Testing QA Agent ===")
    
    # Initialize QA Agent
    qa_agent = QAAgent()
    
    # Test scripts (good quality)
    good_scripts = [
        {
            'title': 'Introduction',
            'bullets': ['Point 1', 'Point 2', 'Point 3'],
            'narration_parts': [
                '这是第一段旁白，内容详细且充实。' * 50,  # ~600 chars
                '这是第二段旁白，同样详细且充实。' * 50   # ~600 chars
            ]
        },
        {
            'title': 'Method',
            'bullets': ['Method 1', 'Method 2', 'Method 3', 'Method 4'],
            'narration_parts': [
                '方法部分的第一段旁白，描述核心算法。' * 50,
                '方法部分的第二段旁白，描述实现细节。' * 50
            ]
        },
        {
            'title': 'Results',
            'bullets': ['Result 1', 'Result 2', 'Result 3', 'Result 4', 'Result 5'],
            'narration_parts': [
                '结果部分的第一段旁白，展示实验数据。' * 50,
                '结果部分的第二段旁白，分析性能表现。' * 50
            ]
        }
    ]
    
    # Test slides (good quality)
    good_slides = [
        {
            'title': 'Introduction',
            'bullets': ['Point 1', 'Point 2', 'Point 3'],
            'image_path': 'output/generated_images/slide_01.png'
        },
        {
            'title': 'Method',
            'bullets': ['Method 1', 'Method 2', 'Method 3', 'Method 4'],
            'image_path': 'output/generated_images/slide_02.png'
        },
        {
            'title': 'Results',
            'bullets': ['Result 1', 'Result 2', 'Result 3'],
            'image_path': 'output/generated_images/slide_03.png'
        }
    ]
    
    # Check scripts quality
    scripts_passed, scripts_issues = qa_agent.check_scripts_quality(good_scripts)
    print(f"✓ Scripts quality check: {'PASSED' if scripts_passed else 'FAILED'}")
    if scripts_issues:
        for issue in scripts_issues:
            print(f"  - {issue}")
    else:
        print("  No issues found")
    
    # Check slides quality
    slides_passed, slides_issues = qa_agent.check_slides_quality(good_slides)
    print(f"✓ Slides quality check: {'PASSED' if slides_passed else 'FAILED'}")
    if slides_issues:
        for issue in slides_issues:
            print(f"  - {issue}")
    else:
        print("  No issues found")
    
    # Generate quality report
    report = qa_agent.generate_quality_report(good_scripts, good_slides)
    print(f"\n✓ Quality Report:")
    print(f"  Overall: {'PASSED' if report['overall_passed'] else 'FAILED'}")
    print(f"  Scripts: {report['stats']['num_scripts']}")
    print(f"  Slides: {report['stats']['num_slides']}")
    print(f"  Total narration: {report['stats']['total_narration_chars']} chars")
    print(f"  Avg narration: {report['stats']['avg_narration_chars']} chars")
    print(f"  Total bullets: {report['stats']['total_bullets']}")
    print(f"  Images generated: {report['stats']['images_generated']}")
    print(f"  Repetition rate: {report['stats']['repetition_rate']:.2%}")
    
    # Test with bad data
    print(f"\n=== Testing with bad data ===")
    bad_scripts = [
        {
            'title': 'Bad Script',
            'bullets': ['Only one'],  # Too few bullets
            'narration_parts': [
                'Too short',  # Too short
                'Also short'  # Too short
            ]
        }
    ]
    
    bad_passed, bad_issues = qa_agent.check_scripts_quality(bad_scripts)
    print(f"✓ Bad scripts detected: {len(bad_issues)} issues")
    for issue in bad_issues:
        print(f"  - {issue}")
    
    assert not bad_passed, "Bad scripts should not pass"
    assert len(bad_issues) >= 3, f"Should detect at least 3 issues, got {len(bad_issues)}"
    
    print(f"\n✓ QA Agent correctly identifies quality issues")
    
    return True


if __name__ == '__main__':
    try:
        test_qa_agent()
        print("\n✅ QA Agent test PASSED")
    except Exception as e:
        print(f"\n❌ QA Agent test FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

