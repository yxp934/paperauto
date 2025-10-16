"""
Orchestrator Agent - analyzes paper structure and plans section generation
"""
import logging
from typing import Dict, List
from agents.base import BaseAgent
from src.utils.llm_client import LLMClient

logger = logging.getLogger(__name__)


class OrchestratorAgent(BaseAgent):
    """Agent for paper structure analysis and task planning"""

    def __init__(self, llm_client=None, log_callback=None):
        super().__init__("OrchestratorAgent", agent_type="orchestrator")
        # Create own LLM client with orchestrator type for model selection
        self.llm_client = LLMClient(log_callback=log_callback, agent_type="orchestrator") if llm_client is None else llm_client
    
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
                
                # Define minimal response schema to enforce structure (Gemini-compatible)
                orchestrator_schema = {
                    "type": "object",
                    "properties": {
                        "sections": {
                            "type": "array",
                            "minItems": 3,
                            "maxItems": 6,
                            "items": {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string"},
                                    "summary": {"type": "string"},
                                    "keywords": {"type": "array", "items": {"type": "string"}}
                                },
                                "required": ["title", "summary", "keywords"]
                            }
                        }
                    },
                    "required": ["sections"]
                }

                # Call LLM
                response, prompt_tokens, completion_tokens = self.call_llm(
                    [system_msg, user_msg],
                    temperature=0.2,
                    max_tokens=4096,
                    response_schema=orchestrator_schema
                )

                # Extract JSON
                data = self.extract_json(response)
                if not data or 'sections' not in data:
                    logger.warning(f"[OrchestratorAgent] Attempt {attempt+1}: Invalid response structure, requesting JSON-only minimal schema (strict)")
                    # One more JSON-only try within the same attempt
                    json_only_sys = (
                        "严格只输出 JSON 对象，不得包含任何前后缀、空行、注释或 Markdown 代码块标记(例如 ``` 或 ```json)。"
                        "输出必须是单个 JSON 对象，并严格以 { 开始、以 } 结束；若非 JSON 或含多余字符，将被判定为错误并立即丢弃并重新生成。"
                        "只允许如下结构：{\"sections\":[{\"title\":\"...\",\"summary\":\"...\",\"keywords\":[\"...\",\"...\"]}]}"
                    )
                    json_only_user = (
                        user_content
                        + "\n\n仅输出严格 JSON 对象，禁止任何 ``` 或 ```json 代码块标记，不要任何解释性文字，"
                        + "直接以 { 开始、以 } 结束，并确保有效 JSON。"
                    )
                    try:
                        resp2, _, _ = self.call_llm([
                            {"role": "system", "content": json_only_sys},
                            {"role": "user", "content": json_only_user}
                        ], temperature=0.1, max_tokens=4096, response_schema=orchestrator_schema)
                        data = self.extract_json(resp2)
                    except Exception:
                        data = None
                    if not data or 'sections' not in data:
                        logger.warning(f"[OrchestratorAgent] Attempt {attempt+1}: Failed to parse JSON after JSON-only request")
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
        
        # Disable heuristic fallback per strict policy
        logger.error(f"[OrchestratorAgent] All LLM attempts failed; heuristic fallback is forbidden")
        raise RuntimeError("OrchestratorAgent failed to generate valid JSON sections without fallback")

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

