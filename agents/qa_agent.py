"""
QA Agent - quality assurance for scripts and slides
"""
import logging
from typing import Dict, List, Tuple
from collections import Counter
import re

logger = logging.getLogger(__name__)


class QAAgent:
    """Agent for quality assurance and consistency checks"""
    
    def __init__(self):
        self.name = "QAAgent"
    
    def check_scripts_quality(self, scripts: List[Dict]) -> Tuple[bool, List[str]]:
        """
        Check quality of all scripts
        
        Args:
            scripts: List of script dicts
            
        Returns:
            (passed, issues) where issues is list of problem descriptions
        """
        issues = []
        
        # Check each script
        for i, script in enumerate(scripts):
            # Check narration parts
            parts = script.get('narration_parts', [])
            if len(parts) < 2:
                issues.append(f"Script {i+1}: Less than 2 narration parts ({len(parts)})")
            
            for j, part in enumerate(parts):
                # Check length
                if len(part) < 600:
                    issues.append(f"Script {i+1}, part {j+1}: Too short ({len(part)} chars, minimum 600)")
                
                # Check Chinese ratio
                zh_ratio = self._chinese_ratio(part)
                if zh_ratio < 0.7:
                    issues.append(f"Script {i+1}, part {j+1}: Low Chinese ratio ({zh_ratio:.2f}, minimum 0.7)")
            
            # Check bullets
            bullets = script.get('bullets', [])
            if len(bullets) < 3:
                issues.append(f"Script {i+1}: Less than 3 bullets ({len(bullets)})")
            elif len(bullets) > 5:
                issues.append(f"Script {i+1}: More than 5 bullets ({len(bullets)})")
        
        # Check cross-section repetition
        repetition_rate = self._check_repetition(scripts)
        if repetition_rate > 0.1:
            issues.append(f"Cross-section repetition rate too high: {repetition_rate:.2%} (maximum 10%)")
        
        passed = len(issues) == 0
        return passed, issues
    
    def check_slides_quality(self, slides: List[Dict]) -> Tuple[bool, List[str]]:
        """
        Check quality of all slides
        
        Args:
            slides: List of slide plan dicts
            
        Returns:
            (passed, issues)
        """
        issues = []
        
        for i, slide in enumerate(slides):
            # Check bullets
            bullets = slide.get('bullets', [])
            if len(bullets) < 3:
                issues.append(f"Slide {i+1}: Less than 3 bullets ({len(bullets)})")
            elif len(bullets) > 5:
                issues.append(f"Slide {i+1}: More than 5 bullets ({len(bullets)})")
            
            # Check image
            image_path = slide.get('image_path')
            if not image_path:
                issues.append(f"Slide {i+1}: No image generated")
        
        passed = len(issues) == 0
        return passed, issues
    
    def _chinese_ratio(self, text: str) -> float:
        """Calculate Chinese character ratio"""
        if not text:
            return 0.0
        
        cjk = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        letters = sum(1 for c in text if c.isalpha())
        total = max(1, cjk + letters)
        return cjk / total
    
    def _check_repetition(self, scripts: List[Dict]) -> float:
        """
        Check cross-section repetition rate
        
        Returns:
            Repetition rate (0.0 to 1.0)
        """
        if len(scripts) < 2:
            return 0.0
        
        # Extract all sentences from all scripts
        all_sentences = []
        for script in scripts:
            parts = script.get('narration_parts', [])
            for part in parts:
                sentences = self._split_sentences(part)
                all_sentences.extend(sentences)
        
        if len(all_sentences) < 2:
            return 0.0
        
        # Count duplicates
        sentence_counts = Counter(all_sentences)
        duplicates = sum(count - 1 for count in sentence_counts.values() if count > 1)
        
        repetition_rate = duplicates / len(all_sentences)
        return repetition_rate
    
    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences"""
        # Split by Chinese and English sentence endings
        sentences = re.split(r'[。！？.!?]+', text)
        # Clean and filter
        sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]
        return sentences
    
    def generate_quality_report(self, scripts: List[Dict], slides: List[Dict]) -> Dict:
        """
        Generate comprehensive quality report
        
        Returns:
            {
                "scripts_passed": bool,
                "scripts_issues": [str],
                "slides_passed": bool,
                "slides_issues": [str],
                "overall_passed": bool,
                "stats": {various statistics}
            }
        """
        scripts_passed, scripts_issues = self.check_scripts_quality(scripts)
        slides_passed, slides_issues = self.check_slides_quality(slides)
        
        # Calculate statistics
        stats = {
            'num_scripts': len(scripts),
            'num_slides': len(slides),
            'total_narration_chars': sum(
                sum(len(p) for p in script.get('narration_parts', []))
                for script in scripts
            ),
            'avg_narration_chars': 0,
            'total_bullets': sum(len(script.get('bullets', [])) for script in scripts),
            'images_generated': sum(1 for slide in slides if slide.get('image_path')),
            'repetition_rate': self._check_repetition(scripts)
        }
        
        if len(scripts) > 0:
            stats['avg_narration_chars'] = stats['total_narration_chars'] // len(scripts)
        
        return {
            'scripts_passed': scripts_passed,
            'scripts_issues': scripts_issues,
            'slides_passed': slides_passed,
            'slides_issues': slides_issues,
            'overall_passed': scripts_passed and slides_passed,
            'stats': stats
        }

