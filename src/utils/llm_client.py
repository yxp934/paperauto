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
        self.gemini_model = os.environ.get("GEMINI_MODEL") or os.environ.get("LLM_MODEL") or "gemini-2.5-flash"
        self.openai_key = os.environ.get("OPENAI_API_KEY")
        self.openai_model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        # HuggingFace Inference API (optional)
        self.hf_key = os.environ.get("HUGGINGFACE_API_KEY")
        self.hf_model = os.environ.get("HUGGINGFACE_MODEL", "Qwen/Qwen2.5-7B-Instruct")

    # --------------------------- Core chat ---------------------------
    def chat_completion(self, messages: List[Dict[str, str]], temperature: float = 0.3, max_tokens: int = 2048) -> str:
        # Try providers in order; if one returns empty due to error, cascade to the next
        if self.generic_url and self.generic_key:
            txt = self._chat_generic(messages, temperature, max_tokens)
            if txt:
                return txt
            logger.warning("LLMClient: Generic endpoint returned empty, trying Gemini/OpenAI")
        if self.gemini_key:
            txt = self._chat_gemini(messages, temperature, max_tokens)
            if txt:
                return txt
            logger.warning("LLMClient: Gemini returned empty, trying OpenAI")
        if self.openai_key:
            txt = self._chat_openai(messages, temperature, max_tokens)
            if txt:
                return txt
            logger.warning("LLMClient: OpenAI returned empty, trying HuggingFace Inference API")
        if self.hf_key:
            txt = self._chat_huggingface(messages, temperature, max_tokens)
            if txt:
                return txt
        logger.error("LLMClient: All LLM providers failed or returned empty response")
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
        # Do not override model if URL already includes full path
        # add key query if absent
        parsed = _up.urlparse(url)
        q = _up.parse_qs(parsed.query)
        if "key" not in q:
            q["key"] = [self.generic_key]
            new_query = _up.urlencode(q, doseq=True)
            url = _up.urlunparse(parsed._replace(query=new_query))
        data = json.dumps(body).encode("utf-8")
        _headers = {"Content-Type": "application/json"}
        if self.generic_key:
            _headers.setdefault("x-goog-api-key", self.generic_key)
        req = request.Request(url, data=data, headers=_headers, method="POST")
        try:
            with request.urlopen(req) as resp:
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
            body = ""
            try:
                body = e.read().decode("utf-8", errors="ignore")
            except Exception:
                pass
            code = getattr(e, 'code', 'HTTPError')
            logger.error(f"LLM API调用失败 (Generic) {code}: {body[:500]}")
            return ""
        except error.URLError as e:
            logger.error(f"LLM API调用异常 (Generic) URL: {getattr(e, 'reason', e)}")
            return ""
        except Exception as e:
            logger.error(f"LLM API调用异常 (Generic): {e}")
            return ""

    def _chat_gemini(self, messages: List[Dict[str, str]], temperature: float, max_tokens: int) -> str:
        """Use official Google Gemini SDK when available; fall back to REST if SDK is missing.
        No timeout is set anywhere per requirements.
        """
        # Merge messages into a single string
        sys_txt = "\n".join(m.get("content", "") for m in messages if m.get("role") == "system").strip()
        usr_txt = "\n\n".join(m.get("content", "") for m in messages if m.get("role") in {"user", "assistant"}).strip()
        if sys_txt:
            contents = f"[System instruction]\n{sys_txt}\n\n[User]\n{usr_txt}"
        else:
            contents = usr_txt
        api_key = self.gemini_key or self.generic_key
        model = self.gemini_model
        # Try SDK first
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            resp = client.models.generate_content(model=model, contents=contents)
            text = getattr(resp, 'text', '') or ''
            return text.strip()
        except ImportError:
            pass
        # Fallback to REST without overriding model in URL
        try:
            body = {
                "contents": [{"role": "user", "parts": [{"text": contents}]}],
                "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
            }
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            data = json.dumps(body).encode("utf-8")
            req = request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
            with request.urlopen(req) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
            obj = json.loads(raw)
            parts = []
            for cand in (obj.get("candidates") or []):
                content = (cand.get("content") or {})
                for part in (content.get("parts") or []):
                    if isinstance(part, dict) and part.get("text"):
                        parts.append(part["text"])
            return "\n".join(parts).strip()
        except Exception as e:
            logger.error(f"LLM API调用异常 (Gemini SDK/REST): {e}")
            return ""

    def _chat_openai(self, messages: List[Dict[str, str]], temperature: float, max_tokens: int) -> str:
        # Use the REST API to avoid extra deps
        base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com")
        url = f"{base.rstrip('/')}/v1/chat/completions"
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
            with request.urlopen(req) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
            obj = json.loads(raw)
            choices = obj.get("choices") or []
            if choices and choices[0].get("message", {}).get("content"):
                text = choices[0]["message"]["content"].strip()
                logger.info(f"LLM调用成功（OpenAI），返回 {len(text)} 字符")
                return text
            return ""
        except error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="ignore")
            except Exception:
                pass
            code = getattr(e, 'code', 'HTTPError')
            logger.error(f"LLM API调用失败 (OpenAI) {code}: {body[:500]}")
            return ""
        except error.URLError as e:
            logger.error(f"LLM API调用异常 (OpenAI) URL: {getattr(e, 'reason', e)}")
            return ""
        except Exception as e:
            logger.error(f"LLM API调用异常 (OpenAI): {e}")
            return ""

    def _chat_huggingface(self, messages: List[Dict[str, str]], temperature: float, max_tokens: int) -> str:
        """Call HuggingFace Inference API for text generation."""
        try:
            # Build a simple prompt from messages
            sys_txt = "\n".join(m.get("content", "") for m in messages if m.get("role") == "system").strip()
            usr_txt = "\n\n".join(m.get("content", "") for m in messages if m.get("role") in {"user", "assistant"}).strip()
            prompt = (sys_txt + "\n\n" + usr_txt).strip() if sys_txt else usr_txt
            import json
            from urllib import request as _rq
            url = f"https://api-inference.huggingface.co/models/{self.hf_model}"
            data = json.dumps({
                "inputs": prompt,
                "parameters": {"max_new_tokens": max_tokens, "temperature": temperature},
                "options": {"wait_for_model": True}
            }).encode("utf-8")
            req = _rq.Request(url, data=data, headers={
                "Authorization": f"Bearer {self.hf_key}",
                "Content-Type": "application/json",
            }, method="POST")
            with _rq.urlopen(req) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
            try:
                obj = json.loads(raw)
            except Exception:
                obj = None
            if isinstance(obj, list) and obj and isinstance(obj[0], dict) and obj[0].get('generated_text'):
                text = str(obj[0]['generated_text']).strip()
                logger.info(f"LLM调用成功（HuggingFace），返回 {len(text)} 字符")
                return text
            # some models return dict with 'generated_text'
            if isinstance(obj, dict) and obj.get('generated_text'):
                text = str(obj['generated_text']).strip()
                logger.info(f"LLM调用成功（HuggingFace），返回 {len(text)} 字符")
                return text
            logger.error(f"LLM API调用失败 (HF) unexpected response: {raw[:300]}")
            return ""
        except Exception as e:
            logger.error(f"LLM API调用异常 (HF): {e}")
            return ""
    # --------------------------- Quality Helpers ---------------------------
    @staticmethod
    def _is_chinese_dominant(text: str, threshold: float = 0.7) -> bool:
        if not text:
            return False
        cjk = sum(1 for ch in text if '\u4e00' <= ch <= '\u9fff')
        latin = sum(1 for ch in text if ('A' <= ch <= 'Z') or ('a' <= ch <= 'z'))
        total = max(1, cjk + latin)
        return (cjk / total) >= threshold

    @staticmethod
    def _dedup_sentences(text: str) -> str:
        if not text:
            return text
        # split by common sentence boundaries (Chinese + English)
        parts = re.split(r"[。.!?；;]\s*", text)
        seen, out = set(), []
        for p in parts:
            p = p.strip()
            if not p:
                continue
            k = p
            if k not in seen:
                seen.add(k)
                out.append(p)
        return "。".join(out)

    def _expand_to_chinese(self, content: str, topic: str, min_len: int = 600) -> str:
        """Ask LLM to rewrite/expand content into pure Chinese, >= min_len, avoid repetition.
        If LLM unavailable, heuristically elongate with Chinese templates.
        """
        if not content:
            content = ""
        # normalize topic display to Chinese if common section title
        t = (topic or "该部分").strip()
        tl = t.lower()
        if "introduction" in tl or "intro" in tl:
            t = "引言"
        elif "background" in tl:
            t = "背景"
        elif "method" in tl or "approach" in tl or "architecture" in tl:
            t = "方法"
        elif "experiment" in tl or "setup" in tl:
            t = "实验"
        elif "result" in tl or "analysis" in tl:
            t = "结果"
        elif "conclusion" in tl or "discussion" in tl:
            t = "结论"
        # Try LLM rewrite/expand
        try:
            sys = {"role":"system","content":"你是专业的中文写作助手，输出必须为纯中文，内容完整连贯、避免重复。"}
            user = {"role":"user","content":(
                "请将以下内容改写为纯中文长段落，并扩展为不少于"+str(min_len)+"字，避免中英文混杂、避免逐句重复；保留必要的专业术语的英文形式，但请用括号标注。例如 Transformer（Transformer）。\n"
                + f"主题：{t}\n"
                + "原始内容：\n" + content[:3000]
            )}
            txt = self.chat_completion([sys, user], temperature=0.2, max_tokens=4096)
            if txt:
                txt = self._dedup_sentences(txt)
                if self._is_chinese_dominant(txt, threshold=0.9) and len(txt) >= min_len:
                    return txt[:8000]
        except Exception:
            pass
        # If providers configured, do NOT heuristic-expand; return empty to force upstream failure
        if self.generic_key or self.gemini_key or self.openai_key or self.hf_key:
            logger.error("heuristic expansion forbidden with providers configured; returning empty")
            return ""
        # Heuristic expansion as last resort (no LLM)
        base = f"本部分围绕{t}进行详细讲解，从研究动机、关键概念、典型方法、实践细节与潜在问题等角度展开，力求清晰、连贯且可操作。"
        # Remove mostly-ASCII lines
        # 更严格地过滤含英文的句子：仅保留 ASCII 占比 < 20% 的行
        lines = []
        for ln in re.split(r"\n+", content):
            ln = ln.strip()
            if not ln:
                continue
            asc = sum(1 for c in ln if c.isascii())
            ratio = asc / max(1, len(ln))
            if ratio < 0.2:
                # 移除残留的纯英文/符号片段
                ln = re.sub(r"[A-Za-z0-9_/.:;+\-]{3,}", " ", ln)
                lines.append(ln)
        more = ("。".join([ln for ln in lines if ln.strip()]))
        if len(more) < min_len//2:
            more += "。" + "这一部分还将解释关键术语的直观含义、为何必要、与相关工作的差别、以及在真实任务中的使用注意事项。"
        if len(more) < min_len*0.9:
            more += "。" + "最后总结主要观点，并指出当前方法的局限与改进方向，以帮助读者建立完整的认知框架。"
        out = self._dedup_sentences(base + "。" + more)
        # Ensure minimum length without LLM by appending informative Chinese paragraphs
        filler_paras = [
            f"围绕{t}，进一步从问题场景、研究动机与应用价值展开叙述，结合典型实例说明其在真实任务中的意义与挑战。",
            f"在方法层面，我们总结常见技术路线的优缺点与适用条件，对关键步骤给出直观比喻，帮助建立可操作的思维框架。",
            f"同时对比相关工作，指出本主题与传统做法的差异与联系，强调设计取舍与潜在风险，避免生搬硬套。",
            f"在实践落地方面，总结评估指标、数据与实现细节、调参策略与诊断建议，形成面向工程的操作指引。",
            f"最后展望改进方向与开放问题，讨论与其它方向的交叉融合与应用前景，强化长期视角与系统性理解。"
        ]
        _i = 0
        while len(out) < min_len and _i < 50:
            out += "。" + filler_paras[_i % len(filler_paras)]
            _i += 1
        # Remove long Latin sequences to enforce Chinese purity
        out = re.sub(r"[A-Za-z]{2,}", "", out)
        return out[:8000]


    def _validate_and_repair_parts(self, parts: List[str], topic: str, min_len: int = 600) -> List[str]:
        fixed: List[str] = []
        for p in parts:
            p = (p or "").strip()
            p = re.sub(r"[\x00-\x1F\x7F]", " ", p)
            p = self._dedup_sentences(p)
            if not self._is_chinese_dominant(p, threshold=0.9) or len(p) < min_len:
                p = self._expand_to_chinese(p, topic, min_len=min_len)
            fixed.append(p)
        # Ensure distinctness between parts (reduce overlap)
        if len(fixed) == 2 and fixed[0] and fixed[1]:
            # if overlap too high, ask LLM to diversify the second part
            s1 = [s for s in fixed[0].split("。") if s.strip()]
            s2 = [s for s in fixed[1].split("。") if s.strip()]
            if s1 and s2:
                overlap_cnt = len(set(s1) & set(s2))
                overlap_ratio = overlap_cnt / max(1, min(len(s1), len(s2)))
                if overlap_ratio > 0.1:
                    try:
                        sys = {"role":"system","content":"请改写为纯中文，避免与第一段重复，保持主题一致。"}
                        user = {"role":"user","content":(
                            f"主题：{topic}\n第一段：\n{fixed[0][:1800]}\n第二段（需改写避免重复，保持≥{min_len}字）：\n{fixed[1][:2200]}"
                        )}
                        txt = self.chat_completion([sys, user], temperature=0.2, max_tokens=4096)
                        if txt and self._is_chinese_dominant(txt, threshold=0.9) and len(txt) >= min_len:
                            fixed[1] = self._dedup_sentences(txt)[:8000]
                    except Exception:
                        pass
        return fixed


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
            # No heuristic fallback allowed when providers configured
            if self.generic_key or self.gemini_key or self.openai_key or self.hf_key:
                raise RuntimeError("LLM providers configured but failed to produce structured sections; no heuristic fallback allowed")
            # If absolutely no providers, allow a minimal heuristic to keep pipeline usable offline
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
        为单个章节生成演讲脚本（严格中文、避免重复）

        Returns:
            Dict: 章节脚本，包含:
                - title: 章节标题
                - bullets: 要点列表（3-5条）
                - narration_parts: 两段纯中文旁白（每段≥600字，去重且不混杂英文）
                - narration: 合并后的全量旁白（便于兼容旧逻辑）
        """
        section_title = section.get("title") or "Section"
        section_summary = section.get("summary") or ""
        section_keywords = section.get("keywords") or []

        paper_title = paper_context.get("title") or "Untitled"
        paper_abstract = paper_context.get("abstract") or ""

        # 强化版 Prompt：要求输出 narration_parts 两段，各≥600字、纯中文、避免重复
        sys = {
            "role": "system",
            "content": (
                "你是一个专业的科技视频撰稿助手。\n"
                "必须满足：\n"
                "- 纯中文输出（可在括号中保留必要术语的英文原文，例如 Transformer（Transformer））\n"
                "- 针对当前章节定制内容，禁止整体复述摘要或在不同章节重复相同句子\n"
                "- narration_parts 输出两段，每段≥600字，口语化且逻辑完整，不截断\n"
            ),
        }
        user = {
            "role": "user",
            "content": (
                f"请为以下章节生成脚本：\n\n"
                f"论文标题: {paper_title}\n"
                f"论文摘要: {paper_abstract[:1500]}\n\n"
                f"章节标题: {section_title}\n"
                f"章节摘要: {section_summary}\n"
                f"关键词: {', '.join(section_keywords)}\n\n"
                "请输出JSON：\n"
                "{\n"
                '  "title": "章节标题",\n'
                '  "bullets": ["要点1", "要点2", "要点3"],\n'
                '  "narration_parts": ["第一段（≥600字）", "第二段（≥600字）"]\n'
                "}"
            ),
        }

        # 记录 Prompt 摘要
        try:
            logger.debug(
                "[llm] gen_script prompt | title=%s | section=%s | abs_len=%d | secsum_len=%d | kws=%s",
                paper_title[:80], section_title[:80], len(paper_abstract), len(section_summary), ",".join(section_keywords[:5])
            )
        except Exception:
            pass

        # 调用+重试（最多3次），直到质量满足
        data = None
        for attempt in range(3):
            text = self.chat_completion([sys, user], temperature=0.3 + 0.1*attempt, max_tokens=8192)
            if text is not None:
                logger.debug("[llm] gen_script raw_response(%d) (first 300): %s", attempt+1, str(text)[:300].replace("\n"," "))
            data = self.extract_json_from_response(text) if text else None
            logger.debug("[llm] gen_script parsed(%d)=%s", attempt+1, json.dumps(data, ensure_ascii=False)[:300] if data else "<none>")
            if data and isinstance(data.get("narration_parts"), list) and data.get("bullets"):
                # 质量校验
                parts = [str(x) for x in (data.get("narration_parts") or [])][:2]
                parts = self._validate_and_repair_parts(parts, section_title, min_len=600)
                bullets = [str(b) for b in (data.get("bullets") or [])][:5]
                if all(len(p) >= 600 for p in parts) and self._is_chinese_dominant("".join(parts), threshold=0.9):
                    script = {
                        "title": str(data.get("title") or section_title),
                        "bullets": bullets,
                        "narration_parts": parts,
                        "narration": "\n\n".join(parts),
                    }
                    logger.info(
                        "[llm] gen_script OK | title=%s | bullets=%d | narr_lens=%s",
                        script["title"][:60], len(script["bullets"]), str([len(x) for x in parts])
                    )
                    return script
            time.sleep(0.8 * (attempt + 1))

        # No heuristic fallback allowed when providers are configured
        if self.generic_key or self.gemini_key or self.openai_key or self.hf_key:
            raise RuntimeError("generate_section_script failed and fallback is not allowed; fix LLM connectivity/config")
        # If truly offline (no providers), keep a minimal heuristic to avoid total failure
        sent = [s.strip() for s in re.split(r'[。.!?]', section_summary) if s.strip()]
        bullets: list[str] = []
        for s in sent:
            if len(bullets) >= 5: break
            if len(s) >= 8 and s not in bullets:
                bullets.append(s)
        if len(bullets) < 3:
            bullets += ["问题与场景", "方法与实现", "实验与结论"]
            bullets = bullets[:5]
        base_content = (section_summary or "")
        p1 = self._expand_to_chinese(base_content, f"{section_title}-上半部分", min_len=600)
        p2 = self._expand_to_chinese(base_content, f"{section_title}-下半部分", min_len=600)
        parts = self._validate_and_repair_parts([p1, p2], section_title, min_len=600)
        script = {
            "title": section_title,
            "bullets": bullets[:5],
            "narration_parts": parts,
            "narration": "\n\n".join(parts),
        }
        logger.info("章节脚本（离线回退）生成完成: %s narr_lens=%s", script['title'], str([len(x) for x in parts]))
        return script

