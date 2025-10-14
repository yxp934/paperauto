"""Local provider emulating MultiAgentPPT style pipeline using existing LLM client."""
from __future__ import annotations

import concurrent.futures
from typing import Any, Dict, List, Optional

from src.utils.logger import get_logger
from ..models import SlideComponent, SlideDocument, SlidePage
from .base import ContentProvider


class LocalA2AProvider(ContentProvider):
    """Approximation of MultiAgentPPT's A2A + MCP + ADK pipeline for local use."""

    def __init__(self, llm_client, runtime_options: Optional[Dict[str, Any]] = None):
        self.llm_client = llm_client
        self.runtime_options = runtime_options or {}
        self.logger = get_logger("LocalA2AProvider")
        self.max_parallel_research = max(1, int(self.runtime_options.get("max_parallel_research", 4)))

    def build_slide_document(self, paper_data: Dict[str, Any], script_sections: Any) -> SlideDocument:  # type: ignore[override]
        self.logger.info("[A2A] 启动本地多Agent流水线")

        outline = self._generate_outline(paper_data, script_sections)
        topics = self._split_outline(outline)
        research_results = self._run_research_agents(topics)
        slide_pages = self._summarize_to_pages(research_results, paper_data)

        document = SlideDocument(
            title=paper_data.get("title", "Untitled"),
            topic=paper_data.get("topic") or paper_data.get("title", "Untitled Topic"),
            pages=slide_pages,
            meta={
                "outline": outline,
                "provider": "local_a2a",
                "analysis": paper_data.get("analysis", {}),
            },
        )
        self.logger.info("[A2A] 多Agent流水线完成，共生成 %d 页", len(document.pages))
        return document

    def _generate_outline(self, paper_data: Dict[str, Any], script_sections: Any) -> List[Dict[str, Any]]:
        self.logger.debug("[A2A] Outline Agent 生成大纲")
        outline = []
        for idx, section in enumerate(script_sections or [], start=1):
            if section.get("is_hook"):
                continue
            outline.append(
                {
                    "index": idx,
                    "title": section.get("title") or f"Section {idx}",
                    "summary": section.get("content") or section.get("raw_content", ""),
                    "source": section,
                }
            )
        if not outline:
            outline.append(
                {
                    "index": 1,
                    "title": paper_data.get("title", "Overview"),
                    "summary": paper_data.get("analysis", {}).get("summary", ""),
                    "source": {},
                }
            )
        return outline

    def _split_outline(self, outline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        self.logger.debug("[A2A] Split Outline Agent 拆分大纲")
        return outline  # Already granular per section

    def _run_research_agents(self, topics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        self.logger.info("[A2A] Research Agents 并发检索，共 %d 个主题", len(topics))
        if not topics:
            return []

        results: List[Dict[str, Any]] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_parallel_research) as executor:
            future_map = {
                executor.submit(self._research_topic, topic): topic["index"] for topic in topics
            }
            for future in concurrent.futures.as_completed(future_map):
                topic_index = future_map[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as exc:  # pragma: no cover - logged for diagnostics
                    self.logger.error("Research Agent for topic %s failed: %s", topic_index, exc)
        results.sort(key=lambda item: item.get("index", 0))
        return results

    def _research_topic(self, topic: Dict[str, Any]) -> Dict[str, Any]:
        section = topic.get("source") or {}
        title = topic.get("title", "")
        base_content = section.get("content") or section.get("raw_content") or topic.get("summary") or ""

        talking_points = section.get("talking_points") or []
        if not talking_points:
            talking_points = self._draft_talking_points(base_content)

        keywords = section.get("keywords") or []

        image_prompt = section.get("image_prompt")
        if not image_prompt:
            image_prompt = self.llm_client.generate_image_prompts(base_content, title)

        notes = section.get("raw_content") or base_content

        background_prompt = section.get("background_prompt")

        return {
            "index": topic.get("index", 0),
            "title": title,
            "talking_points": talking_points,
            "keywords": keywords,
            "image_prompt": image_prompt,
            "notes": notes,
            "background_prompt": background_prompt,
        }

    def _draft_talking_points(self, content: str) -> List[str]:
        # Support CN/EN punctuation; fall back to commas and newlines
        import re
        if not isinstance(content, str):
            return []
        # Split by sentence terminators
        parts = re.split(r"[。．\.?!！；;\n]+", content)
        points = [p.strip() for p in parts if p and p.strip()]
        if len(points) < 3:
            # Further split by commas and dashes to enrich bullets
            more = []
            for p in points:
                more.extend([x.strip() for x in re.split(r"[,，、\-]+", p) if x.strip()])
            points = (points + more)[:3]
        if not points and content:
            points = [content[:80]]
        return points[:3]

    def _summarize_to_pages(
        self,
        research_results: List[Dict[str, Any]],
        paper_data: Dict[str, Any],
    ) -> List[SlidePage]:
        self.logger.debug("[A2A] Summary Agent 汇总并进入 Loop PPT Agent")
        pages: List[SlidePage] = []
        for page_number, research in enumerate(research_results, start=1):
            layout = self._decide_layout(research)
            components = self._build_components(research, paper_data)
            background = self._build_background(research)
            pages.append(
                SlidePage(
                    page_number=page_number,
                    layout=layout,
                    components=components,
                    background=background,
                    meta={"keywords": research.get("keywords", [])},
                )
            )
        return pages

    def _decide_layout(self, research: Dict[str, Any]) -> str:
        has_image = bool(research.get("image_prompt"))
        bullets = research.get("talking_points") or []
        bullets_count = len(bullets)
        # Prefer text+image layouts to differentiate from legacy image-only style
        if has_image and bullets_count >= 2:
            return "left_image_right_text"
        if has_image and bullets_count == 1:
            return "title_with_image"
        if bullets_count >= 3:
            return "two_column"
        # As a last resort, use content slide to keep textual elements visible
        return "content_slide"

    def _build_components(
        self,
        research: Dict[str, Any],
        paper_data: Dict[str, Any],
    ) -> List[SlideComponent]:
        components: List[SlideComponent] = []

        components.append(
            SlideComponent("title", {"text": research.get("title") or paper_data.get("title", "")})
        )

        talking_points = research.get("talking_points") or []
        if talking_points:
            components.append(
                SlideComponent("bullets", {"items": talking_points})
            )

        keywords = research.get("keywords") or []
        if keywords:
            components.append(SlideComponent("caption", {"text": " / ".join(keywords)}))

        image_prompt = research.get("image_prompt")
        if image_prompt:
            components.append(
                SlideComponent(
                    "image",
                    {
                        "prompt": image_prompt,
                        "alt": research.get("title", ""),
                    },
                )
            )

        notes = research.get("notes")
        if notes:
            components.append(SlideComponent("notes", {"text": notes}))

        return components

    def _build_background(self, research: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        prompt = research.get("background_prompt")
        if not prompt:
            return None
        return {
            "prompt": prompt,
            "style": "cover",
        }
