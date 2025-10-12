"""
Slide渲染器

负责加载布局模板并将内容渲染成最终的slide图片。
支持多种布局模板、主题样式和输出格式。

使用示例：
    renderer = SlideRenderer()
    slide_path = renderer.render_slide(
        layout_type="left_image_right_text",
        render_data={
            "title": "研究方法",
            "bullets": ["要点1", "要点2"],
            "image": "/tmp/image.png"
        },
        output_path="/tmp/slide.png"
    )
"""

import logging
import asyncio
import time
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path
from abc import ABC, abstractmethod
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from enum import Enum

from PIL import Image, ImageDraw, ImageFont
import numpy as np

logger = logging.getLogger(__name__)


class RenderFormat(Enum):
    """渲染输出格式"""
    PNG = "PNG"
    JPEG = "JPEG"
    WEBP = "WEBP"


@dataclass
class RenderRequest:
    """渲染请求数据类"""
    layout_type: str
    render_data: Dict[str, Any]
    output_path: Optional[str] = None
    format: RenderFormat = RenderFormat.PNG
    config: Optional[Dict[str, Any]] = None


@dataclass
class RenderResult:
    """渲染结果数据类"""
    success: bool
    output_path: Optional[str] = None
    error_message: Optional[str] = None
    render_time: float = 0.0
    template_used: Optional[str] = None

    def __fspath__(self):
        """支持PathLike协议，允许RenderResult直接用作文件路径"""
        if self.output_path is None:
            raise ValueError("RenderResult的output_path为None，无法转换为路径")
        return str(self.output_path)


class SlideRenderer:
    """Slide渲染引擎"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, config: Optional[Dict[str, Any]] = None):
        """单例模式实现"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化渲染器

        Args:
            config: 渲染配置
        """
        if hasattr(self, '_initialized'):
            return

        self.config = config or self._get_default_config()

        # 初始化各个管理器
        from .utils.font_manager import FontManager
        from .utils.asset_manager import AssetManager
        from .templates.template_loader import TemplateLoader

        self.font_manager = FontManager(self.config.get('fonts', {}))
        self.asset_manager = AssetManager(self.config.get('assets', {}))
        self.template_loader = TemplateLoader(self.config.get('templates', {}))

        # 确保输出目录存在
        self.output_dir = Path(self.config.get('output_dir', 'output/slides'))
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 渲染缓存
        self._render_cache = {}
        self._cache_lock = threading.Lock()

        # 性能统计
        self._stats = {
            'total_renders': 0,
            'successful_renders': 0,
            'failed_renders': 0,
            'total_render_time': 0.0,
            'cache_hits': 0
        }

        # 线程池用于并行渲染
        self._executor = ThreadPoolExecutor(
            max_workers=self.config.get('max_workers', 4)
        )

        self._initialized = True

    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            'resolution': (1920, 1080),
            'margin': 80,
            'safe_zone': 120,
            'bg_color': '#1a1a2e',
            'text_color': '#ffffff',
            'accent_color': '#0f3460',
            'output_dir': 'output/slides',
            'format': 'PNG',
            'quality': 95,
            'max_workers': 4,
            'enable_cache': True,
            'cache_size': 100,
            'enable_async': True,
            'performance_monitoring': True
        }

    def render_slide(
        self,
        layout_type: str,
        render_data: Dict[str, Any],
        output_path: Optional[str] = None,
        format: Optional[RenderFormat] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> RenderResult:
        """
        渲染单个slide

        Args:
            layout_type: 布局模板类型
            render_data: 渲染数据（标题、要点、图片等）
            output_path: 输出路径，如果为None则自动生成
            format: 输出格式
            config: 额外的渲染配置

        Returns:
            RenderResult: 渲染结果
        """
        start_time = time.time()
        self._stats['total_renders'] += 1

        try:
            # 验证输入数据
            if not self._validate_render_data(render_data):
                return RenderResult(
                    success=False,
                    error_message="渲染数据验证失败",
                    render_time=time.time() - start_time
                )

            # 检查缓存
            cache_key = self._generate_cache_key(layout_type, render_data, format, config)
            if self.config.get('enable_cache', True):
                cached_result = self._get_from_cache(cache_key)
                if cached_result:
                    self._stats['cache_hits'] += 1
                    return RenderResult(
                        success=True,
                        output_path=cached_result,
                        render_time=time.time() - start_time,
                        template_used=layout_type
                    )

            logger.info(f"开始渲染slide: {layout_type}")

            # 加载模板
            template = self.template_loader.load_template(layout_type)
            if template is None:
                raise ValueError(f"无法加载模板: {layout_type}")

            # 合并配置
            render_config = {**self.config, **(config or {})}

            # 文本按原文渲染（依赖 FontManager 选择可覆盖中文的字体），不再做 ASCII 降级
            # 如需强制英文，可在CLI或配置层设置 fonts.english_only=true 再触发降级
            if render_config.get('fonts', {}).get('english_only'):
                render_data = self._sanitize_text_fields(render_data)

            # 准备资源
            assets = self._prepare_assets(render_data, render_config)

            # 如果没有提供 image，但提供了 chart/table，则使用处理后的图像作为image
            if 'image' not in render_data:
                if 'processed_chart' in assets and assets['processed_chart'] is not None:
                    render_data = {**render_data, 'image': assets['processed_chart']}
                elif 'processed_table' in assets and assets['processed_table'] is not None:
                    render_data = {**render_data, 'image': assets['processed_table']}

            # 渲染slide
            slide_image = template.render({**render_data, **assets})

            # 应用主题
            if 'theme' in render_config:
                slide_image = self._apply_theme(slide_image, render_config['theme'])

            # 生成输出路径
            if output_path is None:
                output_path = self._generate_output_path(format or RenderFormat.PNG)

            # 保存slide
            self._save_slide(slide_image, output_path, format or RenderFormat.PNG, render_config)

            # 缓存结果
            if self.config.get('enable_cache', True):
                self._add_to_cache(cache_key, output_path)

            render_time = time.time() - start_time
            self._stats['successful_renders'] += 1
            self._stats['total_render_time'] += render_time

            logger.info(f"Slide渲染完成: {output_path}, 耗时: {render_time:.2f}s")

            return RenderResult(
                success=True,
                output_path=output_path,
                render_time=render_time,
                template_used=layout_type
            )

        except Exception as e:
            self._stats['failed_renders'] += 1
            render_time = time.time() - start_time
            logger.error(f"Slide渲染失败: {e}")
            return RenderResult(
                success=False,
                error_message=str(e),
                render_time=render_time
            )

    def render_slides_batch(
        self,
        render_requests: List[RenderRequest]
    ) -> List[RenderResult]:
        """
        批量渲染slides

        Args:
            render_requests: 渲染请求列表

        Returns:
            List[RenderResult]: 渲染结果列表
        """
        if not render_requests:
            return []

        logger.info(f"开始批量渲染 {len(render_requests)} 个slides")

        # 使用线程池并行渲染
        futures = []
        for request in render_requests:
            future = self._executor.submit(
                self.render_slide,
                request.layout_type,
                request.render_data,
                request.output_path,
                request.format,
                request.config
            )
            futures.append(future)

        # 收集结果
        results = []
        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                logger.error(f"批量渲染中的任务失败: {e}")
                results.append(RenderResult(
                    success=False,
                    error_message=str(e)
                ))

        successful_count = sum(1 for r in results if r.success)
        logger.info(f"批量渲染完成: {successful_count}/{len(render_requests)} 成功")

        return results

    async def render_slides_async(
        self,
        render_requests: List[RenderRequest]
    ) -> List[RenderResult]:
        """
        异步批量渲染slides

        Args:
            render_requests: 渲染请求列表

        Returns:
            List[RenderResult]: 渲染结果列表
        """
        if not self.config.get('enable_async', True):
            # 如果禁用异步，回退到同步方法
            return self.render_slides_batch(render_requests)

        logger.info(f"开始异步批量渲染 {len(render_requests)} 个slides")

        # 创建异步任务
        tasks = []
        loop = asyncio.get_event_loop()
        for request in render_requests:
            task = loop.run_in_executor(
                self._executor,
                self.render_slide,
                request.layout_type,
                request.render_data,
                request.output_path,
                request.format,
                request.config
            )
            tasks.append(task)

        # 等待所有任务完成
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理结果
        processed_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"异步渲染任务失败: {result}")
                processed_results.append(RenderResult(
                    success=False,
                    error_message=str(result)
                ))
            else:
                processed_results.append(result)

        successful_count = sum(1 for r in processed_results if r.success)
        logger.info(f"异步批量渲染完成: {successful_count}/{len(render_requests)} 成功")

        return processed_results

    def get_available_templates(self) -> List[str]:
        """获取所有可用的模板列表"""
        return self.template_loader.get_available_templates()

    def preload_templates(self, template_names: List[str]) -> None:
        """预加载指定的模板"""
        logger.info(f"开始预加载模板: {template_names}")
        self.template_loader.preload_templates(template_names)
        logger.info("模板预加载完成")

    def get_template_info(self, template_name: str) -> Optional[Dict[str, Any]]:
        """获取模板信息"""
        return self.template_loader.get_template_info(template_name)

    def _validate_render_data(self, render_data: Dict[str, Any]) -> bool:
        """验证渲染数据"""
        if not isinstance(render_data, dict):
            logger.error("渲染数据必须是字典类型")
            return False

        if not render_data.get('title'):
            logger.error("渲染数据必须包含标题")
            return False

        return True

    def _generate_cache_key(self, layout_type: str, render_data: Dict[str, Any],
                          format: Optional[RenderFormat] = None,
                          config: Optional[Dict[str, Any]] = None) -> str:
        """生成缓存键"""
        import hashlib
        import json

        # 创建包含所有相关参数的字典
        cache_data = {
            'layout_type': layout_type,
            'render_data': render_data,
            'format': format.value if format else None,
            'config_hash': hashlib.md5(
                json.dumps(config or {}, sort_keys=True).encode()
            ).hexdigest()[:8]
        }

        # 生成哈希
        cache_str = json.dumps(cache_data, sort_keys=True, default=str)
        return hashlib.md5(cache_str.encode()).hexdigest()

    def _get_from_cache(self, cache_key: str) -> Optional[str]:
        """从缓存获取结果"""
        with self._cache_lock:
            cached_item = self._render_cache.get(cache_key)
            if cached_item:
                # 检查文件是否仍然存在
                if os.path.exists(cached_item):
                    return cached_item
                else:
                    # 文件不存在，从缓存中删除
                    del self._render_cache[cache_key]
        return None

    def _add_to_cache(self, cache_key: str, output_path: str) -> None:
        """添加结果到缓存"""
        with self._cache_lock:
            # 检查缓存大小限制
            if len(self._render_cache) >= self.config.get('cache_size', 100):
                # 删除最旧的缓存项
                oldest_key = next(iter(self._render_cache))
                del self._render_cache[oldest_key]

            self._render_cache[cache_key] = output_path

    def _prepare_assets(self, render_data: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        """准备所有渲染资源（图片缩放、表格预处理等）"""
        assets = {}

        try:
            # 处理图片
            if 'image' in render_data:
                assets['processed_image'] = self.asset_manager.load_image(
                    render_data['image'],
                    max_size=config.get('max_image_size', (800, 600))
                )

            # 处理表格
            if 'table' in render_data:
                assets['processed_table'] = self._process_table(render_data['table'])

            # 处理图表
            if 'chart' in render_data:
                assets['processed_chart'] = self._process_chart(render_data['chart'])

            # 处理背景图片
            if 'background_image' in render_data:
                assets['processed_background'] = self.asset_manager.load_image(
                    render_data['background_image'],
                    max_size=config.get('resolution', (1920, 1080))
                )

        except Exception as e:
            logger.warning(f"资源准备过程中出现警告: {e}")

        return assets

    def _process_table(self, table_data: Any) -> Optional[Image.Image]:
        """处理表格数据"""
        try:
            from .table_generator import TableGenerator
            # Use TableGenerator defaults; renderer config may not include table keys
            generator = TableGenerator()
            # 支持传入 DataFrame / dict / list[list]
            result = generator.generate_table(table_data)
            if isinstance(result, dict) and result.get('success'):
                return result.get('image')
            return None
        except Exception as e:
            logger.error(f"表格处理失败: {e}")
            return None

    def _process_chart(self, chart_data: Any) -> Optional[Image.Image]:
        """处理图表数据"""
        try:
            # 若已是PIL.Image则直接返回
            from PIL import Image as _Image
            if isinstance(chart_data, _Image.Image):
                return chart_data

            from .chart_generator import ChartGenerator
            # Use ChartGenerator defaults; renderer config may not include chart keys
            generator = ChartGenerator()
            # 期望 chart_data 形如 {"type": "bar", "data": {...}}
            if isinstance(chart_data, dict) and 'type' in chart_data and 'data' in chart_data:
                result = generator.generate_chart(chart_data['type'], chart_data['data'])
                if isinstance(result, dict) and result.get('success'):
                    return result.get('image')
            return None
        except Exception as e:
            logger.error(f"图表处理失败: {e}")
            return None

    def _apply_theme(self, slide: Image.Image, theme: Dict[str, Any]) -> Image.Image:
        """

        """
        # TODO: 
        return slide


    def _sanitize_text_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Optional: ASCII-only fallback when english_only=true is set in fonts config."""
        def _to_ascii(s: str) -> str:
            try:
                return s.encode('ascii', 'ignore').decode('ascii')
            except Exception:
                return ''.join(ch for ch in str(s) if ord(ch) < 128)
        sanitized = dict(data)
        for key in ['title', 'subtitle', 'description', 'emphasis', 'caption']:
            if key in sanitized and isinstance(sanitized[key], str):
                sanitized[key] = _to_ascii(sanitized[key])
        if isinstance(sanitized.get('bullets'), list):
            sanitized['bullets'] = [_to_ascii(x) for x in sanitized['bullets']]
        return sanitized

    def _generate_output_path(self, format: RenderFormat = RenderFormat.PNG) -> str:
        """生成输出路径"""
        timestamp = int(time.time())
        extension = format.value.lower()
        filename = f"slide_{timestamp}.{extension}"
        return str(self.output_dir / filename)

    def _save_slide(self, slide: Image.Image, output_path: str,
                   format: RenderFormat, config: Dict[str, Any]) -> None:
        """保存slide图片"""
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # 保存参数
        save_params = {
            'format': format.value,
            'quality': config.get('quality', 95)
        }

        # 针对不同格式的特殊处理
        if format == RenderFormat.JPEG:
            # JPEG不支持透明度，转换为RGB
            if slide.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', slide.size, config.get('bg_color', '#ffffff'))
                if slide.mode == 'P':
                    slide = slide.convert('RGBA')
                background.paste(slide, mask=slide.split()[-1] if slide.mode == 'RGBA' else None)
                slide = background

        elif format == RenderFormat.PNG:
            # PNG的压缩设置
            save_params['optimize'] = True
            save_params['compress_level'] = config.get('compress_level', 6)

        slide.save(output_path, **save_params)

    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计信息"""
        stats = self._stats.copy()
        if stats['total_renders'] > 0:
            stats['average_render_time'] = stats['total_render_time'] / stats['total_renders']
            stats['success_rate'] = stats['successful_renders'] / stats['total_renders']
            stats['cache_hit_rate'] = stats['cache_hits'] / stats['total_renders']
        else:
            stats['average_render_time'] = 0.0
            stats['success_rate'] = 0.0
            stats['cache_hit_rate'] = 0.0

        return stats

    def clear_cache(self) -> None:
        """清理所有缓存"""
        with self._cache_lock:
            self._render_cache.clear()

        # 清理各个管理器的缓存
        self.asset_manager.clear_cache()
        self.font_manager.clear_cache()

    def shutdown(self) -> None:
        """关闭渲染器，清理资源"""
        logger.info("正在关闭Slide渲染器...")

        # 关闭线程池
        if hasattr(self, '_executor'):
            self._executor.shutdown(wait=True)

        # 清理缓存
        self.clear_cache()

        logger.info("Slide渲染器已关闭")

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.shutdown()
        return False


# 时间模块导入
import time