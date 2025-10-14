"""
智能Slide生成系统主协调器

协调整个slide生成流程，集成LLM决策引擎、工具注册中心、内容生成器和渲染器。
支持并行处理、缓存机制和完整的错误处理。

使用示例：
    orchestrator = SlideOrchestrator()
    slide_paths = orchestrator.generate_slides_for_paper(
        paper_id="paper123",
        paper_data={"title": "...", "abstract": "..."},
        script_sections=[{"title": "...", "content": "..."}]
    )
"""

import logging
import time
import hashlib
import json
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from dataclasses import dataclass
import threading
from functools import lru_cache

from .tool_registry import ToolRegistry
from .slide_renderer import SlideRenderer
from .content_generator import ContentGenerator
from .providers.base import ContentProvider
from .providers.local_a2a import LocalA2AProvider
from .providers.external_http import ExternalHTTPProvider
from .providers.multiagent_local import MultiAgentLocalProvider
from .models import SlideDocument, SlidePage, SlideComponent
from .export.pptx_exporter import PPTXExporter
from .schema import validate_slide_document, SlideSchemaError

logger = logging.getLogger(__name__)


@dataclass
class SlideGenerationResult:
    """Slide生成结果"""
    section_index: int
    slide_path: Optional[str]
    success: bool
    error_message: Optional[str]
    generation_time: float
    layout_type: Optional[str]
    tool_calls: List[Dict[str, Any]]


@dataclass
class SectionData:
    """段落数据"""
    index: int
    title: str
    content: str
    duration: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class SlideOrchestrator:
    """Slide生成主协调器"""

    def __init__(self, llm_client=None, config: Optional[Dict[str, Any]] = None, runtime_options: Optional[Dict[str, Any]] = None):
        """
        初始化协调器

        Args:
            llm_client: LLM客户端实例（可选）
            config: 配置参数
        """
        self.llm_client = llm_client
        self.config = config or self._get_default_config()
        self.runtime_options = runtime_options or {}

        # 初始化核心组件
        self.tool_registry = ToolRegistry()
        self.slide_renderer = SlideRenderer(
            config=self.config.get('renderer', {})
        )
        self.content_generator = ContentGenerator(
            llm_client=self.llm_client,
            config=self.config.get('content_generator', {})
        )
        self._slide_provider: Optional[ContentProvider] = None
        self._select_content_provider()

        # 缓存和临时目录
        self.cache_dir = Path(self.config.get('cache_dir', 'temp/slide_cache'))
        self.output_dir = Path(self.config.get('output_dir', 'output/slides'))
        self.temp_dir = Path(self.config.get('temp_dir', 'temp/slides'))

        # 创建目录
        for directory in [self.cache_dir, self.output_dir, self.temp_dir]:
            directory.mkdir(parents=True, exist_ok=True)

        # 线程锁
        self._cache_lock = threading.Lock()
        self._stats_lock = threading.Lock()

        # 统计信息
        self._stats = {
            'total_slides_generated': 0,
            'total_generation_time': 0.0,
            'successful_slides': 0,
            'failed_slides': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }

    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            'max_workers': 4,
            'enable_parallel': True,
            'enable_caching': True,
            'cache_ttl': 3600,  # 缓存有效期（秒）
            'retry_attempts': 3,
            'retry_delay': 1.0,
            'cache_dir': 'temp/slide_cache',
            'output_dir': 'output/slides',
            'temp_dir': 'temp/slides',
            'renderer': {
                'resolution': (1920, 1080),
                'format': 'PNG',
                'quality': 95
            },
            'content_generator': {
                'table': {'font_size': 24},
                'chart': {'figure_size': (12, 8)}
            }
        }

    def generate_slides_for_paper(
        self,
        paper_id: str,
        paper_data: Dict[str, Any],
        script_sections: List[Dict[str, Any]]
    ) -> List[str]:
        """
        为整篇论文生成所有slide

        Args:
            paper_id: 论文ID
            paper_data: 论文完整数据（标题、摘要、全文等）
            script_sections: 脚本段落列表

        Returns:
            List[str]: slide图片路径列表（按顺序）
        """
        start_time = time.time()
        logger.info(f"开始为论文生成slides: {paper_id}, 段落数量: {len(script_sections)}")

        try:
            # 新流程：使用内容提供器（与 MultiAgentPPT 对齐的逐页 JSON）
            if self._use_provider_flow():
                logger.info("启用 Provider 流程 (逐页生成)")
                # 将 paper_id 放入上下文（供渲染/工具使用）
                paper_ctx = dict(paper_data)
                paper_ctx['paper_id'] = paper_id

                document: SlideDocument = self._slide_provider.build_slide_document(paper_ctx, script_sections)  # type: ignore[arg-type]
                try:
                    validate_slide_document(document)
                except SlideSchemaError as se:
                    logger.warning(f"SlideDocument 验证警告/错误：{se}")

                # 若 External Provider 提供了 PPTX 产物，优先保存
                try:
                    self._save_document_artifacts(document, paper_ctx)
                except Exception as e:
                    logger.warning(f"保存文档附件失败（可忽略）：{e}")

                # 渲染每页
                page_results: List[Tuple[int, Optional[str], bool, Optional[str]]] = []
                for page in sorted(document.pages, key=lambda p: p.page_number):
                    path, ok, err = self._render_page_with_qc(document, page, paper_ctx)
                    page_results.append((page.page_number, path, ok, err))

                # 汇总统计
                total_time = time.time() - start_time
                success_count = sum(1 for _, _, ok, _ in page_results if ok)
                self._update_stats(len(page_results), total_time, [
                    SlideGenerationResult(
                        section_index=pn,
                        slide_path=pth,
                        success=ok,
                        error_message=err,
                        generation_time=0.0,
                        layout_type=None,
                        tool_calls=[],
                    )
                    for pn, pth, ok, err in page_results
                ])
                slide_paths = [pth for _, pth, ok, _ in page_results if ok and pth]
                logger.info(f"Provider流程完成: {success_count}/{len(page_results)} 成功, 总耗时: {total_time:.2f}s")

                # 可选导出PPTX
                self._maybe_export_pptx(slide_paths, paper_id)

                return slide_paths

            sections = [
                SectionData(
                    index=i,
                    title=section.get('title', f'段落 {i+1}'),
                    content=section.get('content', ''),
                    duration=section.get('duration'),
                    metadata=section.get('metadata', {})
                )
                for i, section in enumerate(script_sections)
            ]

            # 生成slides
            if self.config.get('enable_parallel', True) and len(sections) > 1:
                slide_results = self._generate_slides_parallel(sections, paper_data)
            else:
                slide_results = self._generate_slides_sequential(sections, paper_data)

            # 排序并提取路径
            slide_results.sort(key=lambda x: x.section_index)
            slide_paths = [result.slide_path for result in slide_results if result.success]

            # 记录统计信息
            total_time = time.time() - start_time
            self._update_stats(len(slide_results), total_time, slide_results)

            logger.info(f"Slides生成完成: {len(slide_paths)}/{len(sections)} 成功, 总耗时: {total_time:.2f}s")

            # 可选导出PPTX
            self._maybe_export_pptx(slide_paths, paper_id)

            return slide_paths

        except Exception as e:
            logger.error(f"Slides生成失败: {e}")
            raise

    def _save_document_artifacts(self, document: SlideDocument, paper_ctx: Dict[str, Any]) -> None:
        """保存来自 Provider 的文档级附件，如 PPTX。

        支持的 meta 字段：
        - pptx_url: 远程 PPTX 下载链接
        - pptx_base64 / pptx_b64: base64 编码的 PPTX 内容
        """
        meta = getattr(document, 'meta', {}) or {}
        if not isinstance(meta, dict):
            return
        target_basename = f"{paper_ctx.get('paper_id', 'paper')}_slides.pptx"
        target_path = self.output_dir / target_basename

        # base64 优先
        b64 = meta.get('pptx_base64') or meta.get('pptx_b64')
        if isinstance(b64, str) and len(b64) > 100:
            import base64
            data = base64.b64decode(b64)
            with open(target_path, 'wb') as f:
                f.write(data)
            logger.info(f"已保存外部PPTX（base64）：{target_path}")
            return

        # URL 其次
        url = meta.get('pptx_url')
        if isinstance(url, str) and url.startswith('http'):
            try:
                import requests
                resp = requests.get(url, timeout=120)
                resp.raise_for_status()
                with open(target_path, 'wb') as f:
                    f.write(resp.content)
                logger.info(f"已下载外部PPTX：{target_path}")
            except Exception as e:
                logger.warning(f"下载外部PPTX失败：{e}")

    def _maybe_export_pptx(self, slide_paths: List[str], paper_id: str) -> None:
        try:
            if not slide_paths:
                return
            export_flag = bool((self.runtime_options or {}).get('export_pptx'))
            # 如果未显式指定，则参考全局配置默认
            from src.core.config import config as _global_config
            export_flag = export_flag or getattr(_global_config, 'export_pptx_default', False)
            if not export_flag:
                return
            exporter = PPTXExporter(width_px=self.config.get('renderer', {}).get('resolution', (1920, 1080))[0],
                                    height_px=self.config.get('renderer', {}).get('resolution', (1920, 1080))[1])
            out_path = str(self.output_dir / f"{paper_id}_slides.pptx")
            res = exporter.export(slide_paths, out_path)
            if res:
                logger.info(f"已导出PPTX: {res}")
        except Exception as e:
            logger.warning(f"导出PPTX失败（可忽略）: {e}")

    def _use_provider_flow(self) -> bool:
        provider = (self.runtime_options or {}).get('slide_provider', 'legacy')
        return provider in {'local_a2a', 'external_http', 'multiagent_local'} and self._slide_provider is not None

    def _select_content_provider(self) -> None:
        provider = (self.runtime_options or {}).get('slide_provider', 'legacy')
        if provider == 'local_a2a':
            self._slide_provider = LocalA2AProvider(self.llm_client, self.runtime_options)
            logger.info("内容提供器: LocalA2AProvider")
        elif provider == 'external_http':
            try:
                self._slide_provider = ExternalHTTPProvider(self.llm_client, self.runtime_options)
                if not getattr(self._slide_provider, 'base_url', ''):
                    logger.warning("ExternalHTTPProvider 未配置 base_url，回退为 legacy")
                    self._slide_provider = None
                else:
                    logger.info("内容提供器: ExternalHTTPProvider")
            except Exception as e:
                logger.warning(f"ExternalHTTPProvider 初始化失败，回退为 legacy: {e}")
                self._slide_provider = None
        elif provider == 'multiagent_local':
            # In-repo multi-agent provider using .env LLM config
            try:
                self._slide_provider = MultiAgentLocalProvider(self.llm_client, self.runtime_options)
                logger.info("内容提供器: MultiAgentLocalProvider")
            except Exception as e:
                logger.warning(f"MultiAgentLocalProvider 初始化失败，回退为 legacy: {e}")
                self._slide_provider = None
        else:
            self._slide_provider = None

    # -------------------- Provider 渲染路径 --------------------
    def _render_page_with_qc(self, document: SlideDocument, page: SlidePage, paper_ctx: Dict[str, Any]) -> Tuple[Optional[str], bool, Optional[str]]:
        """对单页执行QC与渲染，返回 (path, ok, error)"""
        # 缓存检查
        cached = self._get_cached_page(page, paper_ctx)
        if cached:
            self._increment_cache_hits()
            return cached, True, None
        self._increment_cache_misses()

        # 如果外部Provider提供了已渲染好的整页图片URL，则直接下载保存，跳过本地模板渲染
        try:
            rendered_url = None
            if isinstance(page.meta, dict):
                rendered_url = page.meta.get('rendered_image_url')
            if not rendered_url:
                # 查找 image 组件上标记了 slide_rendered 的 URL
                for comp in page.components:
                    if comp.type == 'image' and isinstance(comp.payload, dict):
                        if comp.payload.get('slide_rendered') and comp.payload.get('url'):
                            rendered_url = comp.payload.get('url')
                            break
            if rendered_url:
                output_path = self.output_dir / f"page_{page.page_number:03d}.png"
                # 使用 ImageGenerator 的下载能力
                from src.video.image_generator import ImageGenerator as _IG
                _ig = getattr(self, '_image_generator', None) or _IG()
                setattr(self, '_image_generator', _ig)
                img = _ig._download_image(rendered_url)
                if img is not None:
                    img = img.convert('RGB') if img.mode not in ('RGB', 'RGBA') else img
                    img.save(str(output_path), 'PNG', optimize=True)
                    final_path = str(output_path)
                    self._cache_page(page, paper_ctx, final_path)
                    logger.info(f"使用外部已渲染页面，已保存: {final_path}")
                    return final_path, True, None
                else:
                    logger.warning(f"下载外部已渲染页面失败，将回退为本地渲染: {rendered_url}")
        except Exception as e:
            logger.warning(f"处理外部已渲染页面时异常，回退本地渲染: {e}")

        max_retries = int((self.runtime_options or {}).get('slide_qc_retries', 3)) if (self.runtime_options or {}).get('enable_slide_qc') else 0
        last_err: Optional[str] = None
        for attempt in range(max_retries + 1):
            try:
                template_name, render_data = self._page_to_render_data(page, paper_ctx)
                output_path = self.output_dir / f"page_{page.page_number:03d}.png"
                result = self.slide_renderer.render_slide(
                    layout_type=template_name,
                    render_data=render_data,
                    output_path=str(output_path)
                )
                final_path = result.output_path or str(output_path)
                self._cache_page(page, paper_ctx, final_path)
                return final_path, True, None
            except Exception as e:  # pragma: no cover - robustness path
                last_err = str(e)
                logger.warning(f"渲染第{page.page_number}页失败(尝试{attempt+1}/{max_retries+1}): {e}")
                # 尝试简单修复：裁剪 bullets、追加占位图
                try:
                    self._repair_page_in_place(page)
                except Exception:
                    pass
                continue
        return None, False, last_err

    def _repair_page_in_place(self, page: SlidePage) -> None:
        # 限制 bullets 长度
        for comp in page.components:
            if comp.type == 'bullets':
                items = comp.payload.get('items') or []
                comp.payload['items'] = [str(x)[:120] for x in items[:5]]
        # 确保有标题
        if not any(c.type in {'title', 'subtitle'} for c in page.components):
            page.components.insert(0, SlideComponent('title', {'text': 'Overview'}))

    def _page_to_render_data(self, page: SlidePage, paper_ctx: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """将 SlidePage 转为模板名称与渲染数据。"""
        template_name = self._map_layout_to_template(page.layout)
        data: Dict[str, Any] = {}

        # 标题/副标题
        title = self._first_payload_text(page, {'title'}) or paper_ctx.get('title') or 'Untitled'
        data['title'] = title

        # bullets
        bullets_comp = self._first_component(page, 'bullets')
        if bullets_comp:
            items = bullets_comp.payload.get('items') or []
            data['bullets'] = [str(x) for x in items[:5]]

        # quote -> emphasis/description
        quote_text = self._first_payload_text(page, {'quote'})
        if quote_text:
            data['emphasis'] = quote_text

        # notes/description
        notes_text = self._first_payload_text(page, {'notes', 'caption'})
        if notes_text:
            data['description'] = notes_text[:600]

        # image
        image_comp = self._first_component(page, 'image')
        if image_comp:
            image_obj = self._resolve_image_payload(image_comp.payload, title)
            if image_obj is not None:
                data['image'] = image_obj
            caption = image_comp.payload.get('caption')
            if caption:
                data['caption'] = str(caption)[:200]

        # table
        table_comp = self._first_component(page, 'table')
        if table_comp:
            table_data = table_comp.payload.get('data')
            if table_data is not None:
                data['table'] = table_data

        # chart
        chart_comp = self._first_component(page, 'chart')
        if chart_comp:
            chart_payload = chart_comp.payload
            if isinstance(chart_payload, dict):
                # accept {'type':..., 'data':...} or {'data':...}
                if 'type' in chart_payload and 'data' in chart_payload:
                    data['chart'] = {'type': chart_payload['type'], 'data': chart_payload['data']}
                elif 'data' in chart_payload:
                    data['chart'] = {'type': chart_payload.get('type', 'bar'), 'data': chart_payload['data']}

        # Template-specific requirements
        if template_name == 'left_image_right_text':
            # Require a 'text' body: prefer description/notes, otherwise join bullets
            if 'description' in data and data['description']:
                data['text'] = data['description']
            else:
                bullets = data.get('bullets') or []
                if isinstance(bullets, list) and bullets:
                    data['text'] = ' \n'.join(str(b) for b in bullets)
                else:
                    # fallback minimal text
                    data['text'] = paper_ctx.get('abstract') or paper_ctx.get('title') or 'Overview'
            # Ensure an image exists; if not, create a placeholder image
            if 'image' not in data:
                # 如果有表格或图表，渲染器会将其转换为图片并作为image使用，这里不生成占位图
                if 'table' not in data and 'chart' not in data:
                    placeholder = self._resolve_image_payload({'prompt': 'minimal abstract tech illustration, soft gradients'}, title)
                    data['image'] = placeholder

        return template_name, data

    def _map_layout_to_template(self, layout: str) -> str:
        mapping = {
            'left_image_right_text': 'left_image_right_text',
            'title_with_image': 'content_slide',
            'two_column': 'two_column',
            'image_full_bleed': 'image_slide',
            'comparison': 'content_slide',
            'quote': 'quote',
            'timeline': 'timeline',
            # 兼容旧模板名
            'title_slide': 'title_slide',
            'text_bullets': 'text_bullets',
            'content_slide': 'content_slide',
            'image_slide': 'image_slide',
        }
        return mapping.get(layout, 'content_slide')

    def _first_component(self, page: SlidePage, comp_type: str) -> Optional[Dict[str, Any]]:
        for comp in page.components:
            if comp.type == comp_type:
                return comp
        return None

    def _first_payload_text(self, page: SlidePage, types: set) -> Optional[str]:
        for comp in page.components:
            if comp.type in types:
                val = comp.payload.get('text') or comp.payload.get('value')
                if isinstance(val, str) and val.strip():
                    return val.strip()
        return None

    def _resolve_image_payload(self, payload: Dict[str, Any], title: str):
        # 延迟导入，避免循环依赖
        from src.video.image_generator import ImageGenerator
        if not hasattr(self, '_image_generator'):
            self._image_generator = ImageGenerator()
        # 1) 直接URL
        url = payload.get('url') or payload.get('image_url')
        if isinstance(url, str) and url.startswith('http'):
            img = self._image_generator._download_image(url)
            if img is not None:
                return img
        # 2) base64/bytes handled by image_generator
        base64_data = payload.get('b64') or payload.get('image_base64')
        if isinstance(base64_data, str) and len(base64_data) > 100:
            # image_generator has a decoder but not public; fallback to prompt
            pass
        # 3) prompt 生成
        prompt = payload.get('prompt') or payload.get('description')
        if isinstance(prompt, str) and prompt.strip():
            return self._image_generator.generate_image_with_api(prompt)
        # 4) 占位
        return self._image_generator.generate_fallback_image("Image placeholder", title)

    # 缓存（按页粒度）
    def _page_cache_key(self, page: SlidePage, paper_ctx: Dict[str, Any]) -> str:
        content = json.dumps({
            'page_number': page.page_number,
            'layout': page.layout,
            'components': [
                {'type': c.type, 'payload': c.payload} for c in page.components
            ],
            'paper_title': paper_ctx.get('title', ''),
        }, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    def _get_cached_page(self, page: SlidePage, paper_ctx: Dict[str, Any]) -> Optional[str]:
        if not self.config.get('enable_caching', True):
            return None
        key = self._page_cache_key(page, paper_ctx)
        cache_file = self.cache_dir / f"{key}.png"
        if cache_file.exists():
            file_age = time.time() - cache_file.stat().st_mtime
            if file_age < self.config.get('cache_ttl', 3600):
                return str(cache_file)
        return None

    def _cache_page(self, page: SlidePage, paper_ctx: Dict[str, Any], slide_path: str) -> None:
        if not self.config.get('enable_caching', True):
            return
        try:
            from pathlib import Path as _P
            if not _P(slide_path).exists():
                return
            key = self._page_cache_key(page, paper_ctx)
            cache_file = self.cache_dir / f"{key}.png"
            import shutil
            shutil.copy2(slide_path, cache_file)
        except Exception as e:
            logger.debug(f"缓存写入失败: {e}")

    def generate_single_slide(
        self,
        section: Dict[str, Any],
        paper_context: Dict[str, Any],
        section_index: int
    ) -> str:
        """
        为单个段落生成slide

        流程:
        1. LLM分析段落，决定布局和所需工具
        2. 执行工具调用（生图、制表等）
        3. 收集所有资源
        4. 调用渲染器生成slide

        Args:
            section: 段落数据（标题、内容等）
            paper_context: 论文上下文
            section_index: 段落索引

        Returns:
            str: slide图片路径
        """
        start_time = time.time()

        try:
            # 检查缓存
            if self.config.get('enable_caching', True):
                cached_path = self._get_cached_slide(section, paper_context)
                if cached_path:
                    logger.info(f"使用缓存的slide: {cached_path}")
                    self._increment_cache_hits()
                    return cached_path
                self._increment_cache_misses()

            # 准备段落数据
            section_data = SectionData(
                index=section_index,
                title=section.get('title', f'段落 {section_index+1}'),
                content=section.get('content', ''),
                duration=section.get('duration'),
                metadata=section.get('metadata', {})
            )

            # 1. LLM分析段落，决定布局和所需工具
            decision_result = self._analyze_section_with_llm(section_data, paper_context)

            if not decision_result['success']:
                raise Exception(f"LLM分析失败: {decision_result.get('error', '未知错误')}")

            layout_type = decision_result['layout_type']
            tool_calls = decision_result.get('tool_calls', [])
            elements = decision_result.get('elements', {})

            logger.info(f"段落 {section_index+1} 分析完成: 布局={layout_type}, 工具调用数={len(tool_calls)}")

            # 2. 执行工具调用
            tool_results = {}
            if tool_calls:
                tool_results = self._execute_tools(tool_calls)
                logger.info(f"工具执行完成: 成功 {sum(1 for r in tool_results.values() if r.get('success', False))}/{len(tool_calls)}")

            # 3. 准备渲染数据
            render_data = self._prepare_render_data(section_data, layout_type, tool_results, elements)

            # 4. 生成slide
            slide_path = self._render_and_save_slide(render_data, layout_type, section_index)

            # 缓存结果
            if self.config.get('enable_caching', True):
                self._cache_slide(section, paper_context, slide_path)

            generation_time = time.time() - start_time
            logger.info(f"Slide {section_index+1} 生成完成: {slide_path}, 耗时: {generation_time:.2f}s")

            return slide_path

        except Exception as e:
            error_msg = f"Slide {section_index+1} 生成失败: {e}"
            logger.error(error_msg)
            raise Exception(error_msg)

    def _generate_slides_parallel(
        self,
        sections: List[SectionData],
        paper_data: Dict[str, Any]
    ) -> List[SlideGenerationResult]:
        """并行生成多个slides"""
        results = []

        with ThreadPoolExecutor(max_workers=self.config.get('max_workers', 4)) as executor:
            # 提交所有任务
            future_to_section = {
                executor.submit(
                    self._generate_single_slide_with_retry,
                    section,
                    paper_data
                ): section
                for section in sections
            }

            # 收集结果
            for future in as_completed(future_to_section):
                section = future_to_section[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"并行生成slide失败: 段落 {section.index}, 错误: {e}")
                    results.append(SlideGenerationResult(
                        section_index=section.index,
                        slide_path=None,
                        success=False,
                        error_message=str(e),
                        generation_time=0.0,
                        layout_type=None,
                        tool_calls=[]
                    ))

        return results

    def _generate_slides_sequential(
        self,
        sections: List[SectionData],
        paper_data: Dict[str, Any]
    ) -> List[SlideGenerationResult]:
        """顺序生成slides"""
        results = []

        for section in sections:
            try:
                result = self._generate_single_slide_with_retry(section, paper_data)
                results.append(result)
            except Exception as e:
                logger.error(f"顺序生成slide失败: 段落 {section.index}, 错误: {e}")
                results.append(SlideGenerationResult(
                    section_index=section.index,
                    slide_path=None,
                    success=False,
                    error_message=str(e),
                    generation_time=0.0,
                    layout_type=None,
                    tool_calls=[]
                ))

        return results

    def _generate_single_slide_with_retry(
        self,
        section: SectionData,
        paper_data: Dict[str, Any]
    ) -> SlideGenerationResult:
        """带重试机制的slide生成"""
        start_time = time.time()
        last_error = None

        for attempt in range(self.config.get('retry_attempts', 3)):
            try:
                slide_path = self.generate_single_slide(
                    section=section.__dict__,
                    paper_context=paper_data,
                    section_index=section.index
                )

                return SlideGenerationResult(
                    section_index=section.index,
                    slide_path=slide_path,
                    success=True,
                    error_message=None,
                    generation_time=time.time() - start_time,
                    layout_type=None,  # TODO: 从决策结果获取
                    tool_calls=[]
                )

            except Exception as e:
                last_error = e
                if attempt < self.config.get('retry_attempts', 3) - 1:
                    delay = self.config.get('retry_delay', 1.0) * (2 ** attempt)
                    logger.warning(f"Slide生成失败，{delay}s后重试: {e}")
                    time.sleep(delay)

        return SlideGenerationResult(
            section_index=section.index,
            slide_path=None,
            success=False,
            error_message=str(last_error),
            generation_time=time.time() - start_time,
            layout_type=None,
            tool_calls=[]
        )

    def _analyze_section_with_llm(
        self,
        section: SectionData,
        paper_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        使用LLM分析段落并做出决策

        Args:
            section: 段落数据
            paper_context: 论文上下文

        Returns:
            Dict[str, Any]: LLM决策结果
        """
        # 使用LLM智能选择最合适的布局类型和工具调用
        try:
            # 获取论文ID用于图片生成
            paper_id = paper_context.get('paper_id', 'unknown')

            prompt = f"""
请分析以下幻灯片段落内容，选择最合适的布局类型并决定是否需要调用工具生成资源。

段落标题：{section.title}
段落内容：{section.content[:800]}
关键词：{', '.join(section.metadata.get('keywords', []))}
要点：{', '.join(section.metadata.get('talking_points', []))}
图片提示词：{section.metadata.get('image_prompt', '')}

可用布局类型：
1. title_slide - 标题页（用于开场、结尾、章节分隔）
2. text_bullets - 文字要点列表（用于列举要点、步骤、特性）
3. content_slide - 图文混排（用于包含配图说明的内容）
4. image_slide - 全屏图片（用于展示图表、架构图、演示图）

可用工具：
1. image_generation - 生成技术配图
   参数：prompt（英文描述）, style（风格：technical_diagram/architecture/workflow/concept）, size（尺寸：wide/square/tall）

工具调用决策标准：
- 如果内容涉及技术架构、系统流程、算法原理 → 调用image_generation生成架构图
- 如果内容需要可视化概念、展示实验结果 → 调用image_generation生成示意图
- 如果仅是文字总结、要点列举 → 不调用工具

请返回JSON格式：
{{
  "layout_type": "选择的布局类型",
  "reasoning": "选择理由（简短）",
  "elements": {{
    "title": "幻灯片标题",
    "bullets": ["要点1", "要点2", "要点3"]  // 如果适用
  }},
  "tool_calls": [
    {{
      "tool": "image_generation",
      "params": {{
        "prompt": "Detailed English description for image generation",
        "style": "technical_diagram",
        "size": "wide",
        "paper_id": "{paper_id}",
        "section_title": "{section.title}"
      }}
    }}
  ]  // 如果不需要工具，返回空数组[]
}}
"""

            messages = [
                {"role": "system", "content": "你是专业的幻灯片设计AI，擅长根据内容选择最佳视觉呈现方式和调用合适的工具。"},
                {"role": "user", "content": prompt}
            ]

            response = self.llm_client.chat_completion(messages, temperature=0.3, max_tokens=8192)

            # 提取JSON
            from src.utils.llm_client import extract_json_from_response
            decision = extract_json_from_response(response)

            if not decision or 'layout_type' not in decision:
                raise ValueError("LLM未返回有效的layout_type")

            # 提取要点（如果需要）
            if decision['layout_type'] in ['text_bullets', 'content_slide']:
                if 'bullets' not in decision.get('elements', {}):
                    bullets = self.content_generator.extract_bullet_points(section.content)
                    decision['elements'] = decision.get('elements', {})
                    decision['elements']['bullets'] = bullets

            # 确保tool_calls存在
            if 'tool_calls' not in decision:
                decision['tool_calls'] = []

            decision['success'] = True
            tool_count = len(decision.get('tool_calls', []))
            logger.info(f"LLM布局决策: {decision['layout_type']}, 工具调用: {tool_count}个, 理由: {decision.get('reasoning', '')}")

            return decision

        except Exception as e:
            logger.warning(f"LLM布局决策失败，使用默认: {e}")
            # 回退：根据段落标题简单判断
            title_lower = section.title.lower()
            if any(kw in title_lower for kw in ['开场', '总结', 'intro', 'conclusion', 'summary']):
                layout = 'title_slide'
            else:
                layout = 'text_bullets'

            return {
                'success': True,
                'layout_type': layout,
                'elements': {
                    'title': section.title,
                    'bullets': self.content_generator.extract_bullet_points(section.content)
                },
                'tool_calls': [],
                'reasoning': f'回退方案：使用{layout}布局'
            }

    def _execute_tools(self, tool_calls: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        执行LLM决定的工具调用

        Args:
            tool_calls: 工具调用列表

        Returns:
            Dict[str, Any]: 工具执行结果
        """
        if not tool_calls:
            return {}

        try:
            # 使用工具注册中心执行工具
            results = {}
            for tool_call in tool_calls:
                tool_name = tool_call.get('tool')
                tool_params = tool_call.get('params', {})

                try:
                    result = self.tool_registry.execute_tool_sync(tool_name, tool_params)
                    results[f"tool_{tool_name}"] = {
                        'success': result.status.value == 'success',
                        'data': result.data,
                        'error': result.error_message
                    }
                except Exception as e:
                    logger.error(f"工具执行失败: {tool_name}, 错误: {e}")
                    results[f"tool_{tool_name}"] = {
                        'success': False,
                        'error': str(e)
                    }

            return results

        except Exception as e:
            logger.error(f"工具执行失败: {e}")
            return {}

    def _prepare_render_data(
        self,
        section: SectionData,
        layout_type: str,
        tool_results: Dict[str, Any],
        elements: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        准备渲染所需的所有数据

        Args:
            section: 段落数据
            layout_type: 布局类型
            tool_results: 工具执行结果
            elements: LLM提取的元素

        Returns:
            Dict[str, Any]: 渲染数据
        """
        render_data = {
            'title': elements.get('title', section.title),
            'layout_type': layout_type
        }

        # 根据布局类型准备特定数据
        if layout_type == 'title_slide':
            # 标题页：需要标题和副标题
            render_data['subtitle'] = section.content[:200] if len(section.content) > 200 else section.content
            render_data['description'] = elements.get('description', '')

        elif layout_type == 'text_bullets':
            # 文字要点：需要要点列表
            render_data['bullets'] = elements.get('bullets', [])
            if not render_data['bullets']:
                # 如果没有提供bullets，尝试从content提取
                render_data['bullets'] = [section.content[:100]] if section.content else []

        elif layout_type == 'content_slide':
            # 图文混排：需要描述和要点
            render_data['description'] = elements.get('description', section.content[:300])
            render_data['bullets'] = elements.get('bullets', [])

        elif layout_type == 'image_slide':
            # 图片页：需要描述和图片
            render_data['description'] = elements.get('description', section.content[:200])

        # 添加通用元素
        if 'bullets' in elements and 'bullets' not in render_data:
            render_data['bullets'] = elements['bullets']

        if 'description' in elements and 'description' not in render_data:
            render_data['description'] = elements['description']

        if 'emphasis' in elements:
            render_data['emphasis'] = elements['emphasis']

        # 处理工具结果（用于image_slide等）
        from PIL import Image as PILImage
        import os

        for tool_key, tool_result in tool_results.items():
            if tool_result.get('success'):
                if 'data' in tool_result:
                    data = tool_result['data']
                    if isinstance(data, dict):
                        # 根据工具类型处理数据，并加载图片为PIL Image对象
                        if 'image_path' in data:
                            image_path = data['image_path']
                            if os.path.exists(image_path):
                                try:
                                    render_data['image'] = PILImage.open(image_path)
                                    logger.info(f"成功加载图片: {image_path}")
                                except Exception as e:
                                    logger.warning(f"加载图片失败 {image_path}: {e}")
                                    render_data['image'] = image_path  # 回退到路径
                            else:
                                render_data['image'] = image_path  # 路径不存在，仍传递路径
                        elif 'table_image' in data:
                            table_path = data['table_image']
                            if os.path.exists(table_path):
                                try:
                                    render_data['table'] = PILImage.open(table_path)
                                except Exception as e:
                                    logger.warning(f"加载表格图片失败 {table_path}: {e}")
                                    render_data['table'] = table_path
                            else:
                                render_data['table'] = table_path
                        elif 'chart_image' in data:
                            chart_path = data['chart_image']
                            if os.path.exists(chart_path):
                                try:
                                    render_data['chart'] = PILImage.open(chart_path)
                                except Exception as e:
                                    logger.warning(f"加载图表图片失败 {chart_path}: {e}")
                                    render_data['chart'] = chart_path
                            else:
                                render_data['chart'] = chart_path
                        else:
                            # 直接将数据作为render_data的一部分
                            render_data.update(data)

        return render_data

    def _render_and_save_slide(
        self,
        render_data: Dict[str, Any],
        layout_type: str,
        section_index: int
    ) -> str:
        """
        渲染并保存slide

        Args:
            render_data: 渲染数据
            layout_type: 布局类型
            section_index: 段落索引

        Returns:
            str: slide图片路径
        """
        # 生成输出路径
        output_path = self.output_dir / f"slide_{section_index+1:03d}.png"

        # 渲染slide（返回RenderResult对象）
        render_result = self.slide_renderer.render_slide(
            layout_type=layout_type,
            render_data=render_data,
            output_path=str(output_path)
        )

        # 从RenderResult提取路径
        if hasattr(render_result, 'output_path') and render_result.output_path:
            return render_result.output_path

        # 如果是旧版直接返回字符串的情况
        return str(render_result) if render_result else str(output_path)

    def _get_cache_key(self, section: Dict[str, Any], paper_context: Dict[str, Any]) -> str:
        """生成缓存键"""
        content = json.dumps({
            'section': section,
            'paper_title': paper_context.get('title', ''),
            'paper_abstract': paper_context.get('abstract', '')
        }, sort_keys=True)

        return hashlib.md5(content.encode()).hexdigest()

    def _get_cached_slide(self, section: Dict[str, Any], paper_context: Dict[str, Any]) -> Optional[str]:
        """获取缓存的slide"""
        if not self.config.get('enable_caching', True):
            return None

        cache_key = self._get_cache_key(section, paper_context)
        cache_file = self.cache_dir / f"{cache_key}.png"

        if cache_file.exists():
            # 检查缓存是否过期
            file_age = time.time() - cache_file.stat().st_mtime
            if file_age < self.config.get('cache_ttl', 3600):
                return str(cache_file)

        return None

    def _cache_slide(self, section: Dict[str, Any], paper_context: Dict[str, Any], slide_path: str):
        """缓存slide"""
        if not self.config.get('enable_caching', True):
            return

        try:
            # 检查源文件是否存在
            from pathlib import Path
            if not Path(slide_path).exists():
                logger.debug(f"跳过缓存，源文件不存在: {slide_path}")
                return

            cache_key = self._get_cache_key(section, paper_context)
            cache_file = self.cache_dir / f"{cache_key}.png"

            import shutil
            shutil.copy2(slide_path, cache_file)
            logger.debug(f"Slide缓存成功: {slide_path} -> {cache_file}")

        except Exception as e:
            logger.warning(f"Slide缓存失败: {e}")

    def _update_stats(
        self,
        total_slides: int,
        total_time: float,
        results: List[SlideGenerationResult]
    ):
        """更新统计信息"""
        with self._stats_lock:
            self._stats['total_slides_generated'] += total_slides
            self._stats['total_generation_time'] += total_time
            self._stats['successful_slides'] += sum(1 for r in results if r.success)
            self._stats['failed_slides'] += sum(1 for r in results if not r.success)

    def _increment_cache_hits(self):
        """增加缓存命中次数"""
        with self._stats_lock:
            self._stats['cache_hits'] += 1

    def _increment_cache_misses(self):
        """增加缓存未命中次数"""
        with self._stats_lock:
            self._stats['cache_misses'] += 1

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._stats_lock:
            stats = self._stats.copy()

        # 计算平均时间
        if stats['total_slides_generated'] > 0:
            stats['average_generation_time'] = stats['total_generation_time'] / stats['total_slides_generated']
            stats['success_rate'] = stats['successful_slides'] / stats['total_slides_generated']
        else:
            stats['average_generation_time'] = 0.0
            stats['success_rate'] = 0.0

        # 计算缓存命中率
        total_cache_requests = stats['cache_hits'] + stats['cache_misses']
        if total_cache_requests > 0:
            stats['cache_hit_rate'] = stats['cache_hits'] / total_cache_requests
        else:
            stats['cache_hit_rate'] = 0.0

        return stats

    def clear_cache(self):
        """清理缓存"""
        try:
            for cache_file in self.cache_dir.glob("*.png"):
                cache_file.unlink()

            with self._stats_lock:
                self._stats['cache_hits'] = 0
                self._stats['cache_misses'] = 0

            logger.info("缓存清理完成")

        except Exception as e:
            logger.error(f"缓存清理失败: {e}")

    def cleanup_temp_files(self):
        """清理临时文件"""
        try:
            import shutil
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
                self.temp_dir.mkdir(parents=True, exist_ok=True)

            logger.info("临时文件清理完成")

        except Exception as e:
            logger.error(f"临时文件清理失败: {e}")