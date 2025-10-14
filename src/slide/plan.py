"""
Slide 计划生成模块
根据章节脚本决定每页 Slide 的布局和所需资源
"""
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class SlidePlan:
    """单页 Slide 计划"""
    
    def __init__(
        self,
        layout: str,
        title: str,
        content: Optional[str] = None,
        bullets: Optional[List[str]] = None,
        image_prompt: Optional[str] = None,
        chart_type: Optional[str] = None,
        chart_data: Optional[Dict] = None,
        table_headers: Optional[List[str]] = None,
        table_rows: Optional[List[List[str]]] = None,
    ):
        """
        Args:
            layout: 布局类型 (title_slide, text_bullets, left_image_right_text, 
                    image_slide, chart, table, content_slide)
            title: 页面标题
            content: 文本内容
            bullets: 要点列表
            image_prompt: 图片生成提示词
            chart_type: 图表类型 (bar, line, pie, scatter)
            chart_data: 图表数据
            table_headers: 表格表头
            table_rows: 表格行数据
        """
        self.layout = layout
        self.title = title
        self.content = content
        self.bullets = bullets or []
        self.image_prompt = image_prompt
        self.chart_type = chart_type
        self.chart_data = chart_data
        self.table_headers = table_headers
        self.table_rows = table_rows
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "layout": self.layout,
            "title": self.title,
            "content": self.content,
            "bullets": self.bullets,
            "image_prompt": self.image_prompt,
            "chart_type": self.chart_type,
            "chart_data": self.chart_data,
            "table_headers": self.table_headers,
            "table_rows": self.table_rows,
        }


def plan_slides_for_section(script: Dict[str, Any]) -> List[SlidePlan]:
    """
    根据章节脚本生成 Slide 计划
    
    Args:
        script: 章节脚本，包含 title/bullets/narration
    
    Returns:
        List[SlidePlan]: Slide 计划列表
    
    策略:
        - 标题页: title_slide (章节标题)
        - 要点页: text_bullets (如果有 bullets)
        - 内容页: content_slide (如果 narration 较长)
        - 图片页: left_image_right_text (根据关键词判断是否需要图片)
    """
    title = script.get("title") or "Section"
    bullets = script.get("bullets") or []
    narration = script.get("narration") or ""
    
    plans: List[SlidePlan] = []
    
    # 1. 标题页（每个章节的第一页）
    plans.append(SlidePlan(
        layout="title_slide",
        title=title,
        content=narration[:100] if narration else None,  # 简短摘要
    ))
    
    # 2. 要点页（如果有 bullets）
    if bullets and len(bullets) >= 2:
        plans.append(SlidePlan(
            layout="text_bullets",
            title=f"{title} - 要点",
            bullets=bullets[:5],  # 最多5条
        ))
    
    # 3. 判断是否需要图片页（基于关键词）
    # 如果标题或旁白中包含特定关键词，生成图片页
    image_keywords = [
        "architecture", "framework", "model", "system", "design",
        "结构", "架构", "模型", "系统", "设计", "流程", "方法"
    ]
    needs_image = any(kw in title.lower() or kw in narration.lower() for kw in image_keywords)
    
    if needs_image:
        # 生成图片提示词
        image_prompt = f"A technical diagram illustrating {title}"
        if "method" in title.lower() or "方法" in title:
            image_prompt = f"A flowchart or architecture diagram for {title}"
        elif "result" in title.lower() or "结果" in title:
            image_prompt = f"A visualization of experimental results for {title}"
        
        plans.append(SlidePlan(
            layout="left_image_right_text",
            title=f"{title} - 示意图",
            content=narration[:200] if narration else None,
            bullets=bullets[:3] if bullets else None,
            image_prompt=image_prompt,
        ))
    
    # 4. 内容页（如果旁白较长且没有图片页）
    if len(narration) > 150 and not needs_image:
        plans.append(SlidePlan(
            layout="content_slide",
            title=f"{title} - 详细说明",
            content=narration[:400],
        ))
    
    # 5. 特殊情况：如果是 Experiments 或 Results 章节，可能需要图表
    if "experiment" in title.lower() or "result" in title.lower() or "实验" in title or "结果" in title:
        # 简单示例数据（实际应从论文中提取）
        plans.append(SlidePlan(
            layout="chart",
            title=f"{title} - 性能对比",
            chart_type="bar",
            chart_data={
                "labels": ["Baseline", "Method A", "Method B", "Our Method"],
                "values": [0.75, 0.82, 0.85, 0.91],
                "ylabel": "Accuracy",
            },
        ))
    
    logger.info(f"为章节 '{title}' 生成了 {len(plans)} 页 Slide 计划")
    return plans


def plan_slides_for_paper(sections_scripts: List[Dict[str, Any]]) -> List[SlidePlan]:
    """
    为整篇论文生成 Slide 计划
    
    Args:
        sections_scripts: 所有章节的脚本列表
    
    Returns:
        List[SlidePlan]: 完整的 Slide 计划列表
    """
    all_plans: List[SlidePlan] = []
    
    for script in sections_scripts:
        section_plans = plan_slides_for_section(script)
        all_plans.extend(section_plans)
    
    logger.info(f"为整篇论文生成了 {len(all_plans)} 页 Slide 计划")
    return all_plans

