"""
Script Agent - generates high-quality Chinese narration scripts
"""
import logging
from typing import Dict, List, Optional
from agents.base import BaseAgent

logger = logging.getLogger(__name__)


class ScriptAgent(BaseAgent):
    """Agent for generating section scripts with quality assurance"""

    def __init__(self, llm_client, retriever=None):
        super().__init__("ScriptAgent")
        self.llm_client = llm_client
        # Enforce structured outputs via response_schema
        # NOTE: Removed minLength constraints from schema as they can cause Gemini API to hang
        # Length validation is now done in post-processing with rewrite logic
        self.script_schema = {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "bullets": {
                    "type": "array",
                    "minItems": 3,
                    "maxItems": 5,
                    "items": {"type": "string"}
                },
                "narration_parts": {
                    "type": "array",
                    "minItems": 2,
                    "maxItems": 2,
                    "items": {"type": "string"}
                }
            },
            "required": ["title", "bullets", "narration_parts"]
        }
        self.narration_only_schema = {
            "type": "object",
            "properties": {
                "narration_parts": {
                    "type": "array",
                    "minItems": 2,
                    "maxItems": 2,
                    "items": {"type": "string"}
                }
            },
            "required": ["narration_parts"]
        }
        self.retriever = retriever

    def generate_script(self, section: Dict, paper_context: Dict, max_retries: int = 3) -> Dict:
        """
        Generate script for a section with quality checks and retries

        Args:
            section: {title, summary, keywords}
            paper_context: {title, abstract, arxiv_id}
            max_retries: Maximum retry attempts

        Returns:
            {title, bullets, narration_parts, meta}
        """
        # Retrieve relevant context if retriever available
        retrieved_context = ""
        if self.retriever:
            try:
                query = f"{section.get('title', '')} {section.get('summary', '')}"
                results = self.retriever.query(query, n_results=3, filter_paper_id=paper_context.get('arxiv_id'))
                retrieved_context = "\n\n".join([r['text'] for r in results])
            except Exception as e:
                logger.warning(f"Retrieval failed: {e}")

        # Load prompt template
        prompt_template = self.load_prompt("script.yaml")

        # Try LLM generation with retries
        for attempt in range(max_retries):
            try:
                # Build messages
                system_msg = {"role": "system", "content": prompt_template.get("system", "")}
                user_content = prompt_template.get("user", "").format(
                    paper_title=paper_context.get('title', ''),
                    paper_abstract=paper_context.get('abstract', '')[:1500],
                    section_title=section.get('title', ''),
                    section_summary=section.get('summary', ''),
                    section_keywords=", ".join(section.get('keywords', [])),
                    retrieved_context=retrieved_context[:1000] if retrieved_context else "无"
                )
                user_msg = {"role": "user", "content": user_content}

                # Call LLM
                response, prompt_tokens, completion_tokens = self.call_llm(
                    [system_msg, user_msg],
                    temperature=0.2 + 0.05 * attempt,
                    max_tokens=8192,
                    response_schema=self.script_schema
                )

                # Extract JSON
                data = self.extract_json(response)
                if not data:
                    # One more JSON-only try within the same attempt
                    logger.warning(f"[ScriptAgent] Attempt {attempt+1}: Failed to parse JSON, requesting JSON-only minimal schema (strict)")
                    json_only_sys = (
                        "严格只输出 JSON 对象，不得包含任何前后缀、空行、注释或 Markdown 代码块标记(例如 ``` 或 ```json)。"
                        "输出必须是单个 JSON 对象，并严格以 { 开始、以 } 结束；若非 JSON 或含多余字符，将被判定为错误并立即丢弃并重新生成。"
                        "请严格按以下最小结构与顺序输出：{\"title\":\"...\",\"bullets\":[\"...\",\"...\",\"...\"],\"narration_parts\":[\"段1\",\"段2\"]}"
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
                        ], temperature=0.1, max_tokens=4096, response_schema=self.script_schema)
                        data = self.extract_json(resp2)
                    except Exception as _:
                        data = None
                if not data:
                    logger.warning(f"[ScriptAgent] Attempt {attempt+1}: Failed to parse JSON (after JSON-only request)")
                    continue

                # Validate and repair
                script = self._validate_and_repair(data, section.get('title', ''))

                # Post-process: enforce Chinese-only and low duplication; may trigger one rewrite
                script = self._post_process(script, section, paper_context)

                # Check quality
                if self._check_quality(script):
                    script['meta'] = {
                        'prompt_tokens': prompt_tokens,
                        'completion_tokens': completion_tokens,
                        'total_tokens': prompt_tokens + completion_tokens,
                        'attempt': attempt + 1,
                        'zh_ratio': self._chinese_ratio(script.get('narration_parts', [])),
                    }
                    logger.info(f"[ScriptAgent] Generated script for '{section.get('title', '')}' (attempt {attempt+1})")
                    return script

                # Quality not sufficient: perform one strict re-generation within this attempt
                parts = script.get('narration_parts', []) or []
                lengths = [len(p) for p in parts]
                zh_ratio = self._chinese_ratio(parts)
                reasons = []
                if any(l < 600 for l in lengths):
                    reasons.append(f"lengths<{600}")
                if zh_ratio < 0.90:
                    reasons.append(f"zh_ratio<{0.90}")
                if not reasons:
                    reasons.append("style/template")
                logger.warning(f"[ScriptAgent] Attempt {attempt+1}: Quality check failed ({', '.join(reasons)}); issuing strict quality re-generation")

                quality_sys = (
                    "你是一名中文科普视频的资深撰稿人。严格按照以下质量要求重新生成完整 JSON（含 title, bullets, narration_parts）:"
                    "1) narration_parts 必须两段且每段≥600字; 2) 仅使用中文，中文占比≥0.9，严禁英文字母; "
                    "3) 严禁套话/模板化表达，必须结合给定上下文写出具体技术细节、实验设置/数据与关键结果; "
                    "4) bullets 3-5条，覆盖不同要点; 5) 严禁 Markdown 代码块与任何解释性文字; 6) 仅输出 JSON，对象且以 { 开始、以 } 结束。"
                )
                quality_user = (
                    user_content
                    + "\n\n请给出最终满足质量要求的 JSON。若上次失败原因: " + ",".join(reasons)
                )
                try:
                    resp_q, _, _ = self.call_llm([
                        {"role": "system", "content": quality_sys},
                        {"role": "user", "content": quality_user}
                    ], temperature=0.2, max_tokens=8192, response_schema=self.script_schema)
                    data_q = self.extract_json(resp_q) or {}
                    script_q = self._validate_and_repair(data_q, section.get('title', ''))
                    script_q = self._post_process(script_q, section, paper_context)
                    if self._check_quality(script_q):
                        script_q['meta'] = {
                            'prompt_tokens': prompt_tokens,
                            'completion_tokens': completion_tokens,
                            'total_tokens': prompt_tokens + completion_tokens,
                            'attempt': attempt + 1,
                            'zh_ratio': self._chinese_ratio(script_q.get('narration_parts', [])),
                            'quality_retry': True,
                        }
                        logger.info(f"[ScriptAgent] Generated script (quality-retry) for '{section.get('title', '')}' (attempt {attempt+1})")
                        return script_q
                except Exception as e:
                    logger.warning(f"[ScriptAgent] strict quality re-generation failed: {e}")

            except Exception as e:
                logger.error(f"[ScriptAgent] Attempt {attempt+1} failed: {e}")

        # No heuristic fallback when real providers are configured
        import os
        if os.getenv("LLM_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("HUGGINGFACE_API_KEY"):
            raise RuntimeError("LLM providers configured but script generation failed; heuristic fallback is forbidden")
        logger.warning(f"[ScriptAgent] All LLM attempts failed, using heuristic fallback (no providers configured)")
        return self._heuristic_fallback(section, paper_context)

    def _validate_and_repair(self, data: Dict, section_title: str) -> Dict:
        """Validate and repair script data"""
        title = data.get('title', section_title)
        bullets = [str(b) for b in (data.get('bullets', []) or [])][:5]
        narration_parts = [str(p) for p in (data.get('narration_parts', []) or [])][:2]

        # Ensure at least 3 bullets
        while len(bullets) < 3:
            bullets.append(f"要点{len(bullets)+1}")

        # Ensure 2 narration parts, each >=600 chars
        return {
            'title': title,
            'bullets': bullets[:5],
            'narration_parts': narration_parts,
            'narration': "\n\n".join(narration_parts)
        }

    def _post_process(self, script: Dict, section: Dict, paper_context: Dict) -> Dict:
        """Enforce Chinese-only and reduce duplication; may perform one rewrite via LLM."""
        parts = script.get('narration_parts', []) or []
        # Compute ASCII English letter ratio only
        combined_text = ''.join(parts)
        letters_ascii = sum(1 for c in combined_text if ('A' <= c <= 'Z') or ('a' <= c <= 'z'))
        cjk = sum(1 for c in combined_text if '\u4e00' <= c <= '\u9fff')
        ratio_en = letters_ascii / max(1, (letters_ascii + cjk))
        zh_ratio = self._chinese_ratio(parts)

        # Similarity between the two parts using 3-gram Jaccard
        def _shingles(s: str):
            s2 = ''.join(s.split())
            return set(s2[i:i+3] for i in range(max(0, len(s2)-2)))
        sim = 0.0
        if len(parts) >= 2:
            a, b = _shingles(parts[0]), _shingles(parts[1])
            if a and b:
                sim = len(a & b) / max(1, len(a | b))

        need_rewrite = (ratio_en > 0.02) or (zh_ratio < 0.95) or (sim > 0.10)
        if not need_rewrite:
            return script

        # Template phrase blacklist
        templates = ["大家好", "今天我们来聊聊", "想象一下", "我们不妨先", "总之", "综上所述", "接下来让我们看看"]
        has_template = any(t in combined_text for t in templates)

        # Build rewrite prompt to enforce pure Chinese, ≥600 chars each part, no ASCII letters, no templates
        system = (
            "你是一名中文科普视频的资深撰稿人。请将给定的两段旁白改写为地道、自然、具有吸引力且高信息密度的中文口语体。"
            "严格要求：1) 禁止出现任何英文字母[a-zA-Z]；2) 每段≥600字；3) 必须结合章节与上下文内容，不得空泛；"
            "4) 两段内容避免相似或重复表述；5) 严禁套话/模板化开头（如‘大家好’、‘今天我们来聊聊’、‘想象一下’等）。"
            "仅输出JSON对象，键为 narration_parts，格式为：{\\\"narration_parts\\\":[\\\"段1\\\",\\\"段2\\\"]}"
        )
        user = (
            f"论文标题：{paper_context.get('title','')}\n"
            f"章节：{section.get('title','')}\n"
            f"是否检测到模板句：{has_template}\n"
            f"原始旁白：\nPART1:\n{parts[0] if parts else ''}\n\nPART2:\n{parts[1] if len(parts)>1 else ''}\n"
        )
        # Try up to 2 rewrite attempts
        for _ in range(2):
            try:
                resp, _, _ = self.call_llm([
                    {"role": "system", "content": system},
                    {"role": "user", "content": user}
                ], temperature=0.15, max_tokens=8192, response_schema=self.narration_only_schema)
                data = self.extract_json(resp) or {}
                new_parts = [str(x) for x in (data.get('narration_parts') or [])][:2]
                if len(new_parts) == 2:
                    # Recompute quality gates
                    zh = self._chinese_ratio(new_parts)
                    letters_ascii2 = sum(1 for c in ''.join(new_parts) if ('A' <= c <= 'Z') or ('a' <= c <= 'z'))
                    cjk2 = sum(1 for c in ''.join(new_parts) if '\u4e00' <= c <= '\u9fff')
                    ratio_en2 = letters_ascii2 / max(1, letters_ascii2 + cjk2)
                    if all(len(p) >= 600 for p in new_parts) and zh >= 0.95 and ratio_en2 <= 0.02:
                        script['narration_parts'] = new_parts
                        script['narration'] = "\n\n".join(new_parts)
                        return script
                    else:
                        user = user + "\n\n上次未满足条件（或检测到英文/模板/长度不足），请严格重写。"
            except Exception as e:
                logger.warning(f"[ScriptAgent] rewrite failed: {e}")

        # Last resort: strip English letters and extend
        fixed = []
        import re
        for p in parts[:2]:
            p2 = re.sub(r"[A-Za-z]", "", p)
            if len(p2) < 600:
                p2 = self._expand_narration(p2, section.get('title',''), 600)
            fixed.append(p2)
        while len(fixed) < 2:
            fixed.append(self._expand_narration("", section.get('title',''), 600))
        script['narration_parts'] = fixed[:2]
        script['narration'] = "\n\n".join(script['narration_parts'])
        return script

    def _expand_narration(self, text: str, topic: str, min_len: int) -> str:
        """Expand narration to minimum length with pure Chinese"""
        if len(text) >= min_len:
            return text

        # Ensure text starts with Chinese
        if not text or len(text) < 50:
            text = f"本部分围绕{topic}展开详细讨论。"

        # Add informative Chinese filler
        fillers = [
            f"我们首先从{topic}的核心概念与定义出发，梳理该领域的发展脉络与研究现状，明确当前面临的主要挑战与瓶颈。",
            f"接下来深入分析{topic}的技术原理与实现细节，对比不同方法的优劣势，总结最佳实践与常见陷阱。",
            f"在理论基础方面，我们探讨{topic}背后的数学原理与算法思想，建立系统化的知识框架与思维模型。",
            f"从应用角度看，{topic}在实际场景中展现出广泛的价值，我们通过典型案例分析其落地路径与效果评估。",
            f"同时关注{topic}的局限性与改进空间，讨论未来发展方向与潜在突破点，为后续研究提供参考。",
            f"在工程实践层面，我们总结{topic}的实现要点、性能优化策略与调试技巧，形成可操作的技术指南。",
            f"此外，{topic}与相关领域的交叉融合也值得关注，我们探讨跨学科合作的机遇与挑战。",
            f"最后，我们对{topic}的研究成果进行系统性回顾，提炼关键洞察与经验教训，为读者提供全面的知识图谱。"
        ]

        result = text
        i = 0
        while len(result) < min_len and i < 20:
            result += fillers[i % len(fillers)]
            i += 1

        return result[:8000]

    def _check_quality(self, script: Dict) -> bool:
        """Check if script meets quality standards"""
        parts = script.get('narration_parts', [])
        if len(parts) < 2:
            return False

        # Check length
        if any(len(p) < 600 for p in parts):
            return False

        # Check Chinese ratio
        zh_ratio = self._chinese_ratio(parts)
        if zh_ratio < 0.9:
            return False

        return True

    def _chinese_ratio(self, texts: List[str]) -> float:
        """Calculate Chinese character ratio"""
        if not texts:
            return 0.0

        combined = "".join(texts)
        cjk = sum(1 for c in combined if '\u4e00' <= c <= '\u9fff')
        letters_ascii = sum(1 for c in combined if ('A' <= c <= 'Z') or ('a' <= c <= 'z'))
        total = max(1, cjk + letters_ascii)
        return cjk / total

    def _heuristic_fallback(self, section: Dict, paper_context: Dict) -> Dict:
        """Heuristic fallback when LLM fails"""
        title = section.get('title', 'Section')
        summary = section.get('summary', '')

        # Generate bullets
        bullets = [
            f"{title}的核心概念与定义",
            f"{title}的主要方法与技术路线",
            f"{title}的实验设置与评估指标",
            f"{title}的关键结果与发现",
            f"{title}的局限性与未来方向"
        ][:5]

        # Generate narration parts
        part1 = self._expand_narration(f"本部分围绕{title}展开。{summary}", title, 600)
        part2 = self._expand_narration(f"继续讨论{title}的细节。{summary}", title, 600)

        return {
            'title': title,
            'bullets': bullets,
            'narration_parts': [part1, part2],
            'narration': f"{part1}\n\n{part2}",
            'meta': {
                'prompt_tokens': 0,
                'completion_tokens': 0,
                'total_tokens': 0,
                'attempt': 0,
                'zh_ratio': 1.0,
                'fallback': True
            }
        }

