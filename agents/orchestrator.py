"""
Orchestrator Agent - analyzes paper structure and plans section generation
"""
import logging
from typing import Dict, List
from agents.base import BaseAgent

logger = logging.getLogger(__name__)


class OrchestratorAgent(BaseAgent):
    """Agent for paper structure analysis and task planning"""
    
    def __init__(self, llm_client):
        super().__init__("OrchestratorAgent")
        self.llm_client = llm_client
    
    def analyze_paper(self, paper: Dict, max_retries: int = 3) -> Dict:
        """
        Analyze paper and generate section plan
        
        Args:
            paper: {title, abstract, arxiv_id, authors}
            max_retries: Maximum retry attempts
            
        Returns:
            {
                "sections": [
                    {"title": str, "summary": str, "keywords": [str]}
                ],
                "meta": {token counts, etc}
            }
        """
        # Load prompt template
        prompt_template = self.load_prompt("orchestrator.yaml")
        
        # Try LLM generation with retries
        for attempt in range(max_retries):
            try:
                # Build messages
                system_msg = {"role": "system", "content": prompt_template.get("system", "")}
                user_content = prompt_template.get("user", "").format(
                    title=paper.get('title', ''),
                    abstract=paper.get('abstract', '')[:2000]
                )
                user_msg = {"role": "user", "content": user_content}
                
                # Call LLM
                response, prompt_tokens, completion_tokens = self.call_llm(
                    [system_msg, user_msg],
                    temperature=0.2,
                    max_tokens=4096
                )
                
                # Extract JSON
                data = self.extract_json(response)
                if not data or 'sections' not in data:
                    logger.warning(f"[OrchestratorAgent] Attempt {attempt+1}: Invalid response structure")
                    continue
                
                # Validate sections
                sections = self._validate_sections(data['sections'])
                if len(sections) >= 3:
                    result = {
                        'sections': sections,
                        'meta': {
                            'prompt_tokens': prompt_tokens,
                            'completion_tokens': completion_tokens,
                            'total_tokens': prompt_tokens + completion_tokens,
                            'attempt': attempt + 1
                        }
                    }
                    logger.info(f"[OrchestratorAgent] Generated {len(sections)} sections (attempt {attempt+1})")
                    return result
                
            except Exception as e:
                logger.error(f"[OrchestratorAgent] Attempt {attempt+1} failed: {e}")
        
        # Fallback: heuristic section generation
        logger.warning(f"[OrchestratorAgent] All LLM attempts failed, using heuristic fallback")
        return self._heuristic_fallback(paper)
    
    def _validate_sections(self, sections: List) -> List[Dict]:
        """Validate and clean section data"""
        validated = []
        for sec in sections:
            if not isinstance(sec, dict):
                continue
            
            title = str(sec.get('title', '')).strip()
            summary = str(sec.get('summary', '')).strip()
            keywords = sec.get('keywords', [])
            
            if not title:
                continue
            
            # Ensure keywords is a list
            if not isinstance(keywords, list):
                keywords = []
            keywords = [str(k).strip() for k in keywords if k][:5]
            
            # Ensure summary has minimum length
            if len(summary) < 50:
                summary = f"{title}的核心内容包括相关背景、主要方法、实验结果与分析。本部分将详细阐述该主题的关键要点与技术细节。"
            
            validated.append({
                'title': title,
                'summary': summary,
                'keywords': keywords
            })
        
        return validated
    
    def _heuristic_fallback(self, paper: Dict) -> Dict:
        """Heuristic fallback when LLM fails"""
        title = paper.get('title', 'Paper')
        abstract = paper.get('abstract', '')

        sections = [
            {
                'title': 'Introduction and Background',
                'summary': f"本部分介绍{title}的研究背景、问题陈述和研究意义。我们将从该领域的发展历程、现有方法的局限性以及本研究的创新点展开讨论。{abstract[:300]}",
                'keywords': ['背景', '问题', '动机']
            },
            {
                'title': 'Method and Approach',
                'summary': f"本部分详细阐述{title}的核心方法、技术路线和算法设计。我们将介绍模型架构、关键组件、训练策略以及与现有方法的对比分析。",
                'keywords': ['方法', '算法', '架构']
            },
            {
                'title': 'Experiments and Results',
                'summary': f"本部分展示{title}的实验设置、评估指标、实验结果与分析。我们将呈现在多个基准数据集上的性能表现，并进行消融实验与误差分析。",
                'keywords': ['实验', '结果', '评估']
            }
        ]
        
        return {
            'sections': sections,
            'meta': {
                'prompt_tokens': 0,
                'completion_tokens': 0,
                'total_tokens': 0,
                'attempt': 0,
                'fallback': True
            }
        }

