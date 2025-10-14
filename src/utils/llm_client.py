import os
import json
import time
import logging
import re
from typing import Any, Dict, List, Optional
from urllib import request, error

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Minimal LLM client with Gemini (preferred) and OpenAI compatibility.
    - chat_completion(messages): returns raw text response
    - extract_json_from_response(text): best-effort JSON extractor
    - generate_script_sections(paper): structured 6-section script for slides and TTS
    """

    def __init__(self) -> None:
        # Generic env-driven endpoint (preferred)
        self.generic_url = os.environ.get("LLM_API_URL")
        self.generic_key = os.environ.get("LLM_API_KEY")
        self.generic_model = os.environ.get("LLM_MODEL")
        # Specific providers as fallback
        # 优先顺序：GEMINI_API_KEY / GOOGLE_API_KEY / LLM_API_KEY（兼容现有 .env 配置）
        self.gemini_key = (
            os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
            or os.environ.get("LLM_API_KEY")
        )
        self.gemini_model = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
        self.openai_key = os.environ.get("OPENAI_API_KEY")
        self.openai_model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    # --------------------------- Core chat ---------------------------
    def chat_completion(self, messages: List[Dict[str, str]], temperature: float = 0.3, max_tokens: int = 2048) -> str:
        # 1) Generic env-configured endpoint (supports Gemini-compatible generateContent)
        if self.generic_url and self.generic_key:
            return self._chat_generic(messages, temperature, max_tokens)
        # 2) Gemini explicit fallback
        if self.gemini_key:
            return self._chat_gemini(messages, temperature, max_tokens)
        # 3) OpenAI explicit fallback
        if self.openai_key:
            return self._chat_openai(messages, temperature, max_tokens)
        logger.warning("LLMClient: No API key configured; falling back to heuristic content.")
        return ""

    def _chat_generic(self, messages: List[Dict[str, str]], temperature: float, max_tokens: int) -> str:
        """Generic Gemini-compatible endpoint using LLM_API_URL/LLM_API_KEY/LLM_MODEL.
        If URL already contains a 'key=' query, do not append.
        """
        # Merge messages to a single user text similar to _chat_gemini
        sys_txt = "\n".join(m.get("content", "") for m in messages if m.get("role") == "system").strip()
        usr_txt = "\n\n".join(m.get("content", "") for m in messages if m.get("role") in {"user", "assistant"}).strip()
        if sys_txt:
            usr_txt = f"[System instruction]\n{sys_txt}\n\n[User]\n{usr_txt}"
        body = {
            "contents": [{"role": "user", "parts": [{"text": usr_txt}]}],
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
        }
        # Prefer model from env if provided and URL is a template without model
        import urllib.parse as _up
        url = self.generic_url or ""
        if self.generic_model and "models/" in url:
            # try to replace the model segment between 'models/' and ':'
            try:
                prefix, rest = url.split("models/", 1)
                _, suffix = rest.split(":", 1)
                url = f"{prefix}models/{self.generic_model}:{suffix}"
            except Exception:
                pass
        # add key query if absent
        parsed = _up.urlparse(url)
        q = _up.parse_qs(parsed.query)
        if "key" not in q:
            q["key"] = [self.generic_key]
            new_query = _up.urlencode(q, doseq=True)
            url = _up.urlunparse(parsed._replace(query=new_query))
        data = json.dumps(body).encode("utf-8")
        req = request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with request.urlopen(req, timeout=int(os.getenv('LLM_TIMEOUT', '15'))) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
            obj = json.loads(raw)
            parts = []
            for cand in (obj.get("candidates") or []):
                content = (cand.get("content") or {})
                for part in (content.get("parts") or []):
                    if isinstance(part, dict) and part.get("text"):
                        parts.append(part["text"])
            text = "\n".join(parts).strip()
            logger.info(f"LLM调用成功（Generic/Gemini兼容），返回 {len(text)} 字符")
            return text
        except error.HTTPError as e:
            logger.error(f"LLM API调用失败 (Generic): {e}")
            return ""
        except Exception as e:
            logger.error(f"LLM API调用异常 (Generic): {e}")
            return ""

    def _chat_gemini(self, messages: List[Dict[str, str]], temperature: float, max_tokens: int) -> str:
        # Merge messages into a single user prompt (Gemini content parts)
        sys_txt = "\n".join(m["content"] for m in messages if m.get("role") == "system").strip()
        usr_txt = "\n\n".join(m["content"] for m in messages if m.get("role") in {"user", "assistant"}).strip()
        if sys_txt:
            usr_txt = f"[System instruction]\n{sys_txt}\n\n[User]\n{usr_txt}"
        body = {
            "contents": [{"role": "user", "parts": [{"text": usr_txt}]}],
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
        }
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_model}:generateContent?key={self.gemini_key}"
        data = json.dumps(body).encode("utf-8")
        req = request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with request.urlopen(req, timeout=int(os.getenv('LLM_TIMEOUT', '15'))) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
            obj = json.loads(raw)
            # Extract text from candidates
            parts = []
            for cand in (obj.get("candidates") or []):
                content = (cand.get("content") or {})
                for part in (content.get("parts") or []):
                    if isinstance(part, dict) and part.get("text"):
                        parts.append(part["text"])
            text = "\n".join(parts).strip()
            logger.info(f"LLM调用成功（Gemini），返回 {len(text)} 字符")
            return text
        except error.HTTPError as e:
            logger.error(f"LLM API调用失败 (Gemini): {e}")
            return ""
        except Exception as e:
            logger.error(f"LLM API调用异常 (Gemini): {e}")
            return ""

    def _chat_openai(self, messages: List[Dict[str, str]], temperature: float, max_tokens: int) -> str:
        # Use the REST API to avoid extra deps
        url = "https://api.openai.com/v1/chat/completions"
        body = {"model": self.openai_model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        data = json.dumps(body).encode("utf-8")
        req = request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.openai_key}",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=int(os.getenv('LLM_TIMEOUT', '15'))) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
            obj = json.loads(raw)
            choices = obj.get("choices") or []
            if choices and choices[0].get("message", {}).get("content"):
                text = choices[0]["message"]["content"].strip()
                logger.info(f"LLM调用成功（OpenAI），返回 {len(text)} 字符")
                return text
            return ""
        except error.HTTPError as e:
            logger.error(f"LLM API调用失败 (OpenAI): {e}")
            return ""
        except Exception as e:
            logger.error(f"LLM API调用异常 (OpenAI): {e}")
            return ""

    # --------------------------- Helpers ---------------------------
    @staticmethod
    def extract_json_from_response(text: str) -> Optional[Dict[str, Any]]:
        """Extract first JSON object from free-form LLM text.
        Handles fenced code blocks and plain braces.
        """
        if not text:
            return None
        # fenced
        m = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass
        # first balanced braces heuristic
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            snippet = text[start : end + 1]
            try:
                return json.loads(snippet)
            except Exception:
                pass
        return None

    # --------------------------- Script generation ---------------------------
    def generate_script_sections(self, paper: Dict[str, Any], n_sections: int = 6) -> List[Dict[str, Any]]:
        """
        Ask LLM to produce a structured script with sections for slides and narration.
        Fallback to a heuristic if no API is available.
        Returns: [{title, content, bullets, narration}]
        """
        title = paper.get("title") or "Untitled"
        abstract = paper.get("abstract") or ""
        authors = ", ".join(paper.get("authors") or [])
        arxiv_id = paper.get("paper_id") or paper.get("arxiv_id") or ""

        sys = {
            "role": "system",
            "content": (
                "你是一个专业的科技视频撰稿助手。请输出结构化的JSON，包含精炼的中文讲解内容。"
            ),
        }
        user = {
            "role": "user",
            "content": (
                f"请基于以下论文信息生成{n_sections}段脚本，每段包含: title, content(200-400字), bullets(3-5条), narration(用于配音，中文，180-300字)。\n"
                f"论文标题: {title}\n作者: {authors}\nArXiv: {arxiv_id}\n摘要: {abstract[:1200]}\n"
                "严格输出JSON格式：{\n  \"sections\": [ { \"title\": ..., \"content\": ..., \"bullets\": [..], \"narration\": ... }, ... ]\n}"
            ),
        }
        text = self.chat_completion([sys, user], temperature=0.4, max_tokens=4096)
        data = self.extract_json_from_response(text) if text else None
        sections: List[Dict[str, Any]] = []
        if data and isinstance(data.get("sections"), list):
            for s in data["sections"][:n_sections]:
                sections.append(
                    {
                        "title": str(s.get("title") or "内容"),
                        "content": str(s.get("content") or abstract[:300]),
                        "bullets": [str(b) for b in (s.get("bullets") or [])][:5],
                        "narration": str(s.get("narration") or s.get("content") or abstract[:200]),
                    }
                )
        if not sections:
            # Heuristic fallback
            lines = [x.strip() for x in re.split(r"[\n。.!?]", abstract) if x.strip()]
            bullets = lines[:4] or ["暂无摘要"]
            sections = [
                {"title": f"{title} - 概览", "content": abstract[:400], "bullets": bullets[:4], "narration": (abstract[:240] or title)},
                {"title": "背景与动机", "content": "研究背景、问题与动机。", "bullets": bullets[:3], "narration": "本文旨在..."},
                {"title": "方法与架构", "content": "方法核心思想与系统架构。", "bullets": bullets[:3], "narration": "我们的方法..."},
                {"title": "实验与结果", "content": "实验设置与关键结果。", "bullets": bullets[:3], "narration": "实验表明..."},
                {"title": "应用与局限", "content": "潜在应用与局限讨论。", "bullets": bullets[:3], "narration": "在实践中..."},
                {"title": "总结与展望", "content": "总结贡献并展望未来。", "bullets": bullets[:3], "narration": "总之..."},
            ]
        return sections


    # --------------------------- 步骤2: 论文结构分析 ---------------------------
    def analyze_paper_structure(self, paper: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        分析论文结构，生成5-7个结构化章节

        Args:
            paper: 论文信息字典，包含 title/abstract/authors/arxiv_id

        Returns:
            List[Dict]: 章节列表，每个章节包含:
                - title: 章节标题
                - summary: 章节摘要（100-200字）
                - keywords: 关键词列表（3-5个）

        标准章节结构:
            1. Introduction (引言)
            2. Background (背景)
            3. Method (方法)
            4. Experiments (实验)
            5. Results (结果)
            6. Conclusion (结论)
        """
        title = paper.get("title") or "Untitled"
        abstract = paper.get("abstract") or ""
        authors = ", ".join(paper.get("authors") or [])
        arxiv_id = paper.get("paper_id") or paper.get("arxiv_id") or ""

        sys = {
            "role": "system",
            "content": (
                "你是一个专业的学术论文分析助手。请分析论文并生成结构化的章节划分。"
                "输出严格的JSON格式，包含5-7个章节，每个章节包含title、summary、keywords。"
            ),
        }
        user = {
            "role": "user",
            "content": (
                f"请分析以下论文并生成5-7个章节的结构化划分：\n\n"
                f"论文标题: {title}\n"
                f"作者: {authors}\n"
                f"ArXiv ID: {arxiv_id}\n"
                f"摘要: {abstract[:1500]}\n\n"
                "请按照以下标准学术结构生成章节：\n"
                "1. Introduction (引言) - 研究背景、问题陈述、研究意义\n"
                "2. Background (背景) - 相关工作、理论基础\n"
                "3. Method (方法) - 核心方法、技术路线、算法设计\n"
                "4. Experiments (实验) - 实验设置、数据集、评估指标\n"
                "5. Results (结果) - 实验结果、性能对比、分析讨论\n"
                "6. Conclusion (结论) - 总结贡献、局限性、未来工作\n\n"
                "输出JSON格式：\n"
                "{\n"
                '  "sections": [\n'
                '    {\n'
                '      "title": "Introduction",\n'
                '      "summary": "本章节介绍...",\n'
                '      "keywords": ["关键词1", "关键词2", "关键词3"]\n'
                '    },\n'
                '    ...\n'
                '  ]\n'
                "}"
            ),
        }

        text = self.chat_completion([sys, user], temperature=0.3, max_tokens=3072)
        data = self.extract_json_from_response(text) if text else None

        sections: List[Dict[str, Any]] = []
        if data and isinstance(data.get("sections"), list):
            for s in data["sections"][:7]:  # 最多7个章节
                sections.append({
                    "title": str(s.get("title") or "Section"),
                    "summary": str(s.get("summary") or ""),
                    "keywords": [str(k) for k in (s.get("keywords") or [])][:5],
                })

        # 如果LLM失败，使用标准6章节模板
        if not sections or len(sections) < 5:
            logger.info("LLM章节分析空响应，使用标准模板")
            # 从摘要中提取关键词（简单分词）
            words = re.findall(r'\b[a-zA-Z]{4,}\b', abstract.lower())
            common_keywords = list(dict.fromkeys(words[:15]))  # 去重并取前15个

            sections = [
                {
                    "title": "Introduction",
                    "summary": f"本文介绍了{title}的研究背景、问题陈述和研究意义。",
                    "keywords": common_keywords[:3] or ["research", "paper", "study"],
                },
                {
                    "title": "Background",
                    "summary": "本章节回顾相关工作和理论基础。",
                    "keywords": common_keywords[3:6] or ["background", "related work", "theory"],
                },
                {
                    "title": "Method",
                    "summary": "本章节详细描述核心方法、技术路线和算法设计。",
                    "keywords": common_keywords[6:9] or ["method", "algorithm", "approach"],
                },
                {
                    "title": "Experiments",
                    "summary": "本章节介绍实验设置、数据集和评估指标。",
                    "keywords": common_keywords[9:12] or ["experiment", "dataset", "evaluation"],
                },
                {
                    "title": "Results",
                    "summary": "本章节展示实验结果、性能对比和分析讨论。",
                    "keywords": common_keywords[12:15] or ["results", "performance", "analysis"],
                },
                {
                    "title": "Conclusion",
                    "summary": "本章节总结主要贡献、讨论局限性并展望未来工作。",
                    "keywords": ["conclusion", "contribution", "future work"],
                },
            ]

        logger.info(f"论文结构分析完成，生成 {len(sections)} 个章节")
        return sections

    # --------------------------- 步骤3: 章节脚本生成 ---------------------------
    def generate_section_script(self, section: Dict[str, Any], paper_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        为单个章节生成演讲脚本

        Args:
            section: 章节信息，包含 title/summary/keywords
            paper_context: 论文上下文，包含 title/abstract/authors/arxiv_id

        Returns:
            Dict: 章节脚本，包含:
                - title: 章节标题
                - bullets: 要点列表（3-5条）
                - narration: 完整旁白文本（中文，200-400字）
        """
        section_title = section.get("title") or "Section"
        section_summary = section.get("summary") or ""
        section_keywords = section.get("keywords") or []

        paper_title = paper_context.get("title") or "Untitled"
        paper_abstract = paper_context.get("abstract") or ""

        sys = {
            "role": "system",
            "content": (
                "你是一个专业的科技视频撰稿助手。请为学术论文的章节生成演讲脚本。"
                "脚本应包含：标题、3-5条要点、200-400字的完整中文旁白。"
                "旁白应口语化、易懂，适合视频配音。"
            ),
        }
        user = {
            "role": "user",
            "content": (
                f"请为以下章节生成演讲脚本：\n\n"
                f"论文标题: {paper_title}\n"
                f"论文摘要: {paper_abstract[:800]}\n\n"
                f"章节标题: {section_title}\n"
                f"章节摘要: {section_summary}\n"
                f"关键词: {', '.join(section_keywords)}\n\n"
                "请生成：\n"
                "1. 3-5条要点（每条20-40字）\n"
                "2. 完整的中文旁白（200-400字，口语化，适合视频配音）\n\n"
                "输出JSON格式：\n"
                "{\n"
                '  "title": "章节标题",\n'
                '  "bullets": ["要点1", "要点2", "要点3"],\n'
                '  "narration": "大家好，今天我们来介绍...（完整旁白）"\n'
                "}"
            ),
        }

        text = self.chat_completion([sys, user], temperature=0.4, max_tokens=2048)
        data = self.extract_json_from_response(text) if text else None

        if data and data.get("narration"):
            script = {
                "title": str(data.get("title") or section_title),
                "bullets": [str(b) for b in (data.get("bullets") or [])][:5],
                "narration": str(data.get("narration") or ""),
            }
        else:
            # 回退：基于章节摘要生成简单脚本
            logger.info(f"LLM脚本生成空响应，使用启发式脚本: {section_title}")

            # 从摘要生成要点（按句子分割）
            sentences = [s.strip() for s in re.split(r'[。.!?]', section_summary) if s.strip()]
            bullets = sentences[:4] if sentences else [section_summary[:50] or "暂无内容"]

            # 生成简单旁白
            narration = f"接下来我们介绍{section_title}部分。{section_summary[:200]}"
            if len(narration) < 100:
                narration += f"这一部分主要讨论{', '.join(section_keywords[:3])}等关键内容。"

            script = {
                "title": section_title,
                "bullets": bullets[:5],
                "narration": narration[:400],  # 限制最大长度
            }

        # 确保旁白至少有一定长度（避免过短）
        if len(script["narration"]) < 80:
            script["narration"] += f"本章节重点关注{section_title}的核心内容和关键发现。"

        logger.info(f"章节脚本生成完成: {script['title']} ({len(script['narration'])}字)")
        return script

