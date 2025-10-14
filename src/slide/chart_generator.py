"""
专业图表生成器

负责生成各种类型的高质量图表，支持8种图表类型和多种样式主题。
"""

from typing import Dict, List, Any, Optional, Union, Tuple
import logging
import io
from PIL import Image
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import matplotlib as mpl
from matplotlib import rcParams

logger = logging.getLogger(__name__)


class ChartGenerator:
    """专业图表生成器"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化图表生成器

        Args:
            config: 配置字典
        """
        default_cfg = self._get_default_config()
        self.config = {**default_cfg, **(config or {})}
        self._setup_matplotlib()

    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            # 基础配置
            'figure_size': (12, 8),
            'dpi': 150,
            'resolution': (1920, 1080),

            # 字体配置
            'font_size': 14,
            'title_font_size': 18,
            'label_font_size': 12,
            'legend_font_size': 11,
            'tick_font_size': 10,

            # 颜色主题 - 学术风格
            'color_palette': [
                '#2E86AB',  # 蓝色
                '#A23B72',  # 紫色
                '#F18F01',  # 橙色
                '#C73E1D',  # 红色
                '#4CAF50',  # 绿色
                '#FFC107',  # 黄色
                '#9C27B0',  # 紫罗兰
                '#607D8B',  # 蓝灰色
            ],
            'background_color': '#FFFFFF',
            'grid_color': '#E0E0E0',
            'text_color': '#212121',

            # 样式配置
            'style': 'academic',
            'grid': True,
            'tight_layout': True,
            'show_values': True,
            'show_legend': True,
            'title_padding': 20,
            'label_padding': 10,

            # 特定图表配置
            'bar_width': 0.8,
            'line_width': 2.5,
            'marker_size': 8,
            'alpha': 0.8,
            'edge_color': 'white',
            'edge_width': 1,

            # 中文支持
            'font_family': self._get_default_font_family()
        }

    def _get_default_font_family(self) -> str:
        """获取默认字体族"""
        font_families = [
            'SimHei',           # 中文黑体
            'Microsoft YaHei',  # 微软雅黑
            'PingFang SC',      # 苹方简体
            'Noto Sans CJK SC', # 思源黑体
            'Arial Unicode MS', # Arial Unicode
            'DejaVu Sans',      # DejaVu
            'sans-serif'        # 默认无衬线字体
        ]

        for font_family in font_families:
            try:
                # 测试字体是否可用
                rcParams['font.sans-serif'] = [font_family]
                plt.figure(figsize=(1, 1))
                plt.text(0.5, 0.5, "Test", fontfamily=font_family)
                plt.close()
                return font_family
            except:
                continue
        return 'sans-serif'

    def _setup_matplotlib(self) -> None:
        """专业matplotlib配置"""
        # 设置中文支持
        font_family = self.config.get('font_family', ['SimHei', 'Arial Unicode MS', 'Arial'])
        if isinstance(font_family, str):
            plt.rcParams['font.sans-serif'] = [font_family]
        else:
            plt.rcParams['font.sans-serif'] = font_family
        plt.rcParams['axes.unicode_minus'] = False

        # 设置高质量渲染
        plt.rcParams['figure.figsize'] = self.config.get('figure_size', (12, 8))
        plt.rcParams['figure.dpi'] = self.config.get('dpi', 100)
        plt.rcParams['savefig.dpi'] = self.config.get('dpi', 100)
        plt.rcParams['savefig.bbox'] = 'tight'
        plt.rcParams['savefig.pad_inches'] = 0.1

        # 字体配置
        plt.rcParams['font.size'] = self.config.get('font_size', 12)
        plt.rcParams['axes.titlesize'] = self.config.get('title_font_size', 16)
        plt.rcParams['axes.labelsize'] = self.config.get('label_font_size', 14)
        plt.rcParams['legend.fontsize'] = self.config.get('legend_font_size', 12)
        plt.rcParams['xtick.labelsize'] = self.config.get('tick_font_size', 10)
        plt.rcParams['ytick.labelsize'] = self.config.get('tick_font_size', 10)

        # 网格和边框
        plt.rcParams['axes.grid'] = self.config.get('grid', True)
        plt.rcParams['grid.color'] = self.config.get('grid_color', '#e0e0e0')
        plt.rcParams['grid.linewidth'] = 0.5
        plt.rcParams['axes.linewidth'] = 1.2

        # 颜色和背景
        plt.rcParams['figure.facecolor'] = self.config.get('background_color', 'white')
        plt.rcParams['axes.facecolor'] = self.config.get('background_color', 'white')
        plt.rcParams['text.color'] = self.config.get('text_color', '#333333')
        plt.rcParams['axes.labelcolor'] = self.config.get('text_color', '#333333')

        # 高质量渲染
        plt.rcParams['pdf.fonttype'] = 42
        plt.rcParams['ps.fonttype'] = 42

    def create_chart(self, chart_type: str, data: Dict[str, Any],
                      config_override: Optional[Dict[str, Any]] = None,
                      output_path: Optional[str] = None) -> Dict[str, Any]:
        """
        创建图表的便捷方法（支持单次调用覆盖配置），并在失败时抛出异常

        Args:
            chart_type: 图表类型
            data: 图表数据
            config_override: 单次调用的配置覆盖
            output_path: 输出路径

        Returns:
            生成结果（包含image与metadata）
        """
        # 允许部分原始数据的别名/格式进行兼容处理
        prepared = self._prepare_input_data(chart_type, data)
        # 暂时合并配置（浅拷贝）
        if config_override:
            original = self.config
            self.config = {**self.config, **config_override}
            try:
                result = self.generate_chart(chart_type, prepared, output_path)
            finally:
                self.config = original
        else:
            result = self.generate_chart(chart_type, prepared, output_path)

        if not result.get('success'):
            # 转为异常，便于上层测试用例使用pytest.raises捕获
            raise ValueError(result.get('error', '图表生成失败'))
        # 补充标准metadata字段
        if 'metadata' not in result:
            result['metadata'] = {
                'chart_type': chart_type,
                'figure_size': self.config.get('figure_size'),
                'dpi': self.config.get('dpi')
            }
        else:
            result['metadata'].setdefault('chart_type', chart_type)
        return result

    def _validate_data(self, chart_type: str, data: Dict[str, Any]) -> bool:
        """
        验证数据格式与一致性（字段存在与长度匹配等）

        Args:
            chart_type: 图表类型
            data: 数据字典

        Returns:
            是否有效
        """
        required_fields = self._get_required_fields(chart_type)
        for field in required_fields:
            if field not in data:
                logger.error(f"图表类型 {chart_type} 缺少必需字段: {field}")
                return False
        # 长度/一致性校验
        try:
            if chart_type == 'bar':
                cats, vals = data['categories'], data['values']
                if isinstance(vals, list) and vals and isinstance(vals[0], list):
                    if not all(len(series) == len(cats) for series in vals):
                        return False
                else:
                    if len(cats) != len(vals):
                        return False
            elif chart_type in ['line', 'scatter', 'area']:
                x, y = data['x_data'], data['y_data']
                if isinstance(y, list) and y and isinstance(y[0], list):
                    if not all(len(series) == len(x) for series in y):
                        return False
                else:
                    if len(x) != len(y):
                        return False
            elif chart_type == 'pie':
                if len(data['labels']) != len(data['sizes']):
                    return False
            elif chart_type == 'radar':
                cats, vals = data['categories'], data['values']
                if isinstance(vals, list) and vals and isinstance(vals[0], list):
                    if not all(len(series) == len(cats) for series in vals):
                        return False
                else:
                    if len(cats) != len(vals):
                        return False
            elif chart_type in ['histogram', 'box']:
                vals = data.get('values', [])
                if not vals:
                    return False
                if chart_type == 'box' and vals and not isinstance(vals[0], (list, tuple)):
                    return False
        except Exception:
            return False
        return True

    def _get_required_fields(self, chart_type: str) -> List[str]:
        """
        获取图表类型所需的字段

        Args:
            chart_type: 图表类型

        Returns:
            必需字段列表
        """
        field_map = {
            'bar': ['categories', 'values'],
            'line': ['x_data', 'y_data'],
            'pie': ['labels', 'sizes'],
            'scatter': ['x_data', 'y_data'],
            'area': ['x_data', 'y_data'],
            'radar': ['categories', 'values'],
            'histogram': ['values'],
            'box': ['values']
        }
        return field_map.get(chart_type, [])
    def _prepare_input_data(self, chart_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        规范化/兼容上层传入的数据结构：
        - scatter: 兼容 data_points -> x_data/y_data
        - box: 兼容 datasets -> values
        - line/bar: 兼容 series -> y_data/values 与 labels
        - radar: 单列表值包装为二维列表
        """
        prepared = dict(data) if isinstance(data, dict) else {}
        # scatter: 支持 {data_points: [{x, y, label?}, ...]}
        if chart_type == 'scatter' and 'x_data' not in prepared and 'y_data' not in prepared:
            pts = prepared.get('data_points')
            if isinstance(pts, list) and pts:
                prepared['x_data'] = [p.get('x') for p in pts]
                prepared['y_data'] = [p.get('y') for p in pts]
                labels = [p.get('label') for p in pts if 'label' in p]
                if labels:
                    prepared.setdefault('labels', labels)
        # box: datasets -> values
        if chart_type == 'box' and 'values' not in prepared and 'datasets' in prepared:
            prepared['values'] = prepared.get('datasets', [])
        # line/bar: series -> y_data/values
        if chart_type in ['line', 'bar'] and 'series' in prepared and 'y_data' not in prepared and 'values' not in prepared:
            series = prepared['series']
            labels = [s.get('name', f'系列{i+1}') for i, s in enumerate(series)]
            series_values = [s.get('data', []) for s in series]
            if chart_type == 'line':
                prepared['y_data'] = series_values
                prepared['labels'] = labels
            else:
                prepared['values'] = series_values
                prepared['labels'] = labels
        # radar: 一维 -> 二维
        if chart_type == 'radar' and 'values' in prepared and prepared['values'] and not isinstance(prepared['values'][0], (list, tuple)):
            prepared['values'] = [prepared['values']]
        return prepared


    def _enhance_data(self, chart_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        增强数据（自动计算缺失的字段）

        Args:
            chart_type: 图表类型
            data: 原始数据

        Returns:
            增强后的数据
        """
        enhanced_data = data.copy()

        # 自动生成颜色
        if 'colors' not in enhanced_data:
            num_series = self._get_series_count(chart_type, data)
            enhanced_data['colors'] = self.config['color_palette'][:num_series]

        # 自动设置默认值
        if 'title' not in enhanced_data:
            enhanced_data['title'] = f'{chart_type.title()} Chart'

        if 'alpha' not in enhanced_data:
            enhanced_data['alpha'] = self.config.get('alpha', 0.8)

        return enhanced_data

    def _get_series_count(self, chart_type: str, data: Dict[str, Any]) -> int:
        """
        获取数据系列数量

        Args:
            chart_type: 图表类型
            data: 数据字典

        Returns:
            系列数量
        """
        if chart_type in ['bar', 'line']:
            if 'values' in data:
                if isinstance(data['values'][0], list):
                    return len(data['values'])
                else:
                    return 1
        elif chart_type == 'pie':
            return len(data.get('labels', []))
        elif chart_type == 'radar':
            if 'values' in data:
                return len(data['values'])
        return 1

    def generate_chart(self, chart_type: str, data: Dict[str, Any],
                      output_path: Optional[str] = None) -> Dict[str, Any]:
        """
        生成专业图表

        Args:
            chart_type: 图表类型
            data: 图表数据
            output_path: 输出路径

        Returns:
            生成结果信息
        """
        try:
            # 预处理/兼容输入数据（支持 data_points 等变体）
            prepared = self._prepare_input_data(chart_type, data)

            # 验证图表类型
            if chart_type not in self._get_supported_chart_types():
                raise ValueError(f"不支持的图表类型: {chart_type}")

            # 验证数据格式
            if not self._validate_data(chart_type, prepared):
                raise ValueError(f"数据格式验证失败: {chart_type}")

            # 增强数据
            enhanced_data = self._enhance_data(chart_type, prepared)

            logger.info(f"开始生成{chart_type}图表")

            # 创建高质量图表
            fig, ax = plt.subplots(
                figsize=self.config['figure_size'],
                dpi=self.config['dpi'],
                facecolor=self.config['background_color']
            )

            # 根据图表类型绘制
            if chart_type == 'bar':
                self._draw_bar_chart(ax, enhanced_data)
            elif chart_type == 'line':
                self._draw_line_chart(ax, enhanced_data)
            elif chart_type == 'pie':
                self._draw_pie_chart(ax, enhanced_data)
            elif chart_type == 'scatter':
                self._draw_scatter_chart(ax, enhanced_data)
            elif chart_type == 'area':
                self._draw_area_chart(ax, enhanced_data)
            elif chart_type == 'radar':
                self._draw_radar_chart(ax, enhanced_data)
            elif chart_type == 'histogram':
                self._draw_histogram(ax, enhanced_data)
            elif chart_type == 'box':
                self._draw_box_plot(ax, enhanced_data)
            else:
                raise ValueError(f"图表类型 {chart_type} 的绘制逻辑尚未实现")

            # 设置标题和标签
            self._set_labels(ax, enhanced_data)

            # 添加图例
            if self.config['show_legend'] and 'labels' in enhanced_data:
                self._add_legend(ax, enhanced_data)

            # 应用样式
            self._apply_styling(ax, enhanced_data)

            # 转换为高质量PIL图片
            image = self._fig_to_image(fig)
            plt.close(fig)

            # 保存图片
            if output_path:
                image.save(output_path, 'PNG', quality=95, optimize=True)
                logger.info(f"高质量图表生成成功: {output_path}")

            return {
                'success': True,
                'image': image,
                'output_path': output_path,
                'chart_type': chart_type,
                'figure_size': self.config['figure_size'],
                'dpi': self.config['dpi']
            }

        except Exception as e:
            logger.error(f"图表生成失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'output_path': None
            }

    def _add_legend(self, ax, data: Dict[str, Any]) -> None:
        """
        添加图例（使用当前 Matplotlib 字体配置渲染标签）

        Args:
            ax: matplotlib轴对象
            data: 数据字典
        """
        if 'labels' in data and data['labels']:
            try:
                ax.legend(
                    data['labels'],
                    loc='best',
                    frameon=True,
                    fancybox=True,
                    shadow=True,
                    framealpha=0.9,
                    borderpad=1
                )
            except Exception as e:
                logger.warning(f"图例添加失败: {e}")

    def _apply_styling(self, ax, data: Dict[str, Any]) -> None:
        """
        应用样式

        Args:
            ax: matplotlib轴对象
            data: 数据字典
        """
        # 设置网格
        if self.config['grid'] and data.get('grid', True):
            ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.5)

        # 设置刻度样式
        ax.tick_params(axis='both', which='major', labelsize=self.config['tick_font_size'])

        # 设置边框
        for spine in ax.spines.values():
            spine.set_linewidth(1.2)
            spine.set_color(self.config['text_color'])

        # 紧凑布局
        if self.config['tight_layout']:
            plt.tight_layout(pad=2.0)

    def format_chart_data(self, raw_data: Any, chart_type: str) -> Dict[str, Any]:
        """
        格式化图表数据

        Args:
            raw_data: 原始数据
            chart_type: 图表类型

        Returns:
            格式化的数据
        """
        if chart_type == 'bar':
            return self._format_bar_data(raw_data)
        elif chart_type == 'line':
            return self._format_line_data(raw_data)
        elif chart_type == 'pie':
            return self._format_pie_data(raw_data)
        elif chart_type == 'scatter':
            return self._format_scatter_data(raw_data)
        else:
            # 通用格式化
            return raw_data if isinstance(raw_data, dict) else {'data': raw_data}

    def _format_bar_data(self, raw_data: Any) -> Dict[str, Any]:
        """格式化柱状图数据"""
        if isinstance(raw_data, dict):
            return {
                'categories': list(raw_data.keys()),
                'values': list(raw_data.values())
            }
        elif isinstance(raw_data, list) and len(raw_data) >= 2:
            return {
                'categories': raw_data[0],
                'values': raw_data[1]
            }
        else:
            raise ValueError("无法解析柱状图数据")

    def _format_line_data(self, raw_data: Any) -> Dict[str, Any]:
        """格式化折线图数据"""
        if isinstance(raw_data, dict) and 'x_data' in raw_data and 'y_data' in raw_data:
            return raw_data
        elif isinstance(raw_data, list) and len(raw_data) >= 2:
            return {
                'x_data': raw_data[0],
                'y_data': raw_data[1]
            }
        else:
            raise ValueError("无法解析折线图数据")

    def _format_pie_data(self, raw_data: Any) -> Dict[str, Any]:
        """格式化饼图数据"""
        if isinstance(raw_data, dict):
            return {
                'labels': list(raw_data.keys()),
                'sizes': list(raw_data.values())
            }
        elif isinstance(raw_data, list) and len(raw_data) >= 2:
            return {
                'labels': raw_data[0],
                'sizes': raw_data[1]
            }
        else:
            raise ValueError("无法解析饼图数据")

    def _format_scatter_data(self, raw_data: Any) -> Dict[str, Any]:
        """格式化散点图数据"""
        return self._format_line_data(raw_data)

    def _get_supported_chart_types(self) -> List[str]:
        """获取支持的图表类型"""
        return ['bar', 'line', 'pie', 'scatter', 'area', 'radar', 'histogram', 'box']

    def _draw_bar_chart(self, ax, data: Dict[str, Any]) -> None:
        """绘制柱状图"""
        categories = data.get('categories', [])
        values = data.get('values', [])
        colors = data.get('colors', self.config['color_palette'])

        # 处理多组数据
        if isinstance(values[0], list):
            # 多组柱状图
            x = np.arange(len(categories))
            width = 0.8 / len(values)

            for i, value_group in enumerate(values):
                ax.bar(x + i * width, value_group, width,
                      label=data.get('labels', [f'系列{i+1}'])[i],
                      color=colors[i % len(colors)])

            ax.set_xticks(x + width * (len(values) - 1) / 2)
            ax.set_xticklabels(categories)
            if data.get('labels'):
                ax.legend()
        else:
            # 单组柱状图
            bars = ax.bar(categories, values, color=colors[:len(categories)])

            # 添加数值标签
            for bar, value in zip(bars, values):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{value:.2f}', ha='center', va='bottom')

    def _draw_line_chart(self, ax, data: Dict[str, Any]) -> None:
        """绘制折线图"""
        x_data = data.get('x_data', [])
        y_data = data.get('y_data', [])
        colors = data.get('colors', self.config['color_palette'])

        if isinstance(y_data[0], list):
            # 多条折线
            for i, y_group in enumerate(y_data):
                ax.plot(x_data, y_group,
                       label=data.get('labels', [f'系列{i+1}'])[i],
                       color=colors[i % len(colors)],
                       marker='o', linewidth=2)

            if data.get('labels'):
                ax.legend()
        else:
            # 单条折线
            ax.plot(x_data, y_data, color=colors[0], marker='o', linewidth=2)

            # 添加数值标签
            for x, y in zip(x_data, y_data):
                ax.annotate(f'{y:.2f}', (x, y), textcoords="offset points",
                           xytext=(0,10), ha='center')

    def _draw_pie_chart(self, ax, data: Dict[str, Any]) -> None:
        """绘制饼图"""
        labels = data.get('labels', [])
        sizes = data.get('sizes', [])
        colors = data.get('colors', self.config['color_palette'])
        explode = data.get('explode', None)

        wedges, texts, autotexts = ax.pie(sizes, labels=labels, colors=colors[:len(labels)],
                                         autopct='%1.1f%%', startangle=90, explode=explode)

        # 美化文字
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')

        ax.axis('equal')  # 确保饼图是圆形

    def _draw_scatter_chart(self, ax, data: Dict[str, Any]) -> None:
        """绘制散点图"""
        x_data = data.get('x_data', [])
        y_data = data.get('y_data', [])
        colors = data.get('colors', self.config['color_palette'][0])
        sizes = data.get('sizes', 50)
        alpha = data.get('alpha', 0.7)

        ax.scatter(x_data, y_data, c=colors, s=sizes, alpha=alpha)

        # 添加趋势线（如果需要）
        if data.get('trend_line', False):
            z = np.polyfit(x_data, y_data, 1)
            p = np.poly1d(z)
            ax.plot(x_data, p(x_data), "--", color='red', alpha=0.8)

    def _draw_area_chart(self, ax, data: Dict[str, Any]) -> None:
        """绘制面积图"""
        x_data = data.get('x_data', [])
        y_data = data.get('y_data', [])
        colors = data.get('colors', self.config['color_palette'])

        if isinstance(y_data[0], list):
            # 多个面积图（堆叠）
            ax.stackplot(x_data, *y_data, labels=data.get('labels', []),
                        colors=colors, alpha=0.7)
            if data.get('labels'):
                ax.legend()
        else:
            # 单个面积图
            ax.fill_between(x_data, y_data, alpha=0.7, color=colors[0])
            ax.plot(x_data, y_data, color=colors[0], linewidth=2)

    def _draw_radar_chart(self, ax, data: Dict[str, Any]) -> None:
        """绘制雷达图"""
        categories = data.get('categories', [])
        values = data.get('values', [])
        labels = data.get('labels', ['系列1'])

        # 计算角度
        angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
        angles += angles[:1]  # 闭合图形

        ax = plt.subplot(111, projection='polar')

        # 绘制每个系列
        colors = self.config['color_palette']
        for i, value_group in enumerate(values):
            value_group += value_group[:1]  # 闭合图形
            ax.plot(angles, value_group, 'o-', linewidth=2,
                   label=labels[i], color=colors[i % len(colors)])
            ax.fill(angles, value_group, alpha=0.25, color=colors[i % len(colors)])

        # 设置标签
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(categories)
        ax.set_ylim(0, max(max(v) for v in values) * 1.1)

        if labels:
            ax.legend()

    def _draw_histogram(self, ax, data: Dict[str, Any]) -> None:
        """绘制直方图"""
        values = data.get('values', [])
        bins = data.get('bins', 20)
        color = data.get('color', self.config['color_palette'][0])
        alpha = data.get('alpha', 0.7)

        ax.hist(values, bins=bins, color=color, alpha=alpha, edgecolor='black')

        # 添加统计信息
        if data.get('show_stats', False):
            mean_val = np.mean(values)
            std_val = np.std(values)
            ax.axvline(mean_val, color='red', linestyle='--', linewidth=2, label=f'均值: {mean_val:.2f}')
            ax.axvline(mean_val + std_val, color='orange', linestyle='--', alpha=0.7, label=f'+1σ: {mean_val + std_val:.2f}')
            ax.axvline(mean_val - std_val, color='orange', linestyle='--', alpha=0.7, label=f'-1σ: {mean_val - std_val:.2f}')
            ax.legend()

    def _draw_box_plot(self, ax, data: Dict[str, Any]) -> None:
        """绘制箱线图"""
        values = data.get('values', [])
        labels = data.get('labels', [f'组{i+1}' for i in range(len(values))])

        box_plot = ax.boxplot(values, labels=labels, patch_artist=True)

        # 设置颜色
        colors = self.config['color_palette']
        for i, patch in enumerate(box_plot['boxes']):
            patch.set_facecolor(colors[i % len(colors)])
            patch.set_alpha(0.7)

    def _set_labels(self, ax, data: Dict[str, Any]) -> None:
        """设置标签和标题（ASCII降级）"""
        def _ascii(s: str) -> str:
            try:
                return s.encode('ascii', 'ignore').decode('ascii')
            except Exception:
                return ''.join(ch for ch in str(s) if ord(ch) < 128)

        if 'title' in data:
            ax.set_title(_ascii(str(data['title'])), fontweight='bold', pad=20)

        if 'x_label' in data:
            ax.set_xlabel(_ascii(str(data['x_label'])))

        if 'y_label' in data:
            ax.set_ylabel(_ascii(str(data['y_label'])))

        if 'xlim' in data:
            ax.set_xlim(data['xlim'])

        if 'ylim' in data:
            ax.set_ylim(data['ylim'])

        if 'grid' in data:
            ax.grid(data['grid'])

    def _fig_to_image(self, fig) -> Image.Image:
        """将matplotlib图形转换为PIL图片"""
        buffer = io.BytesIO()
        fig.savefig(buffer, format='png', bbox_inches='tight',
                   facecolor=self.config['background_color'], dpi=self.config['dpi'])
        buffer.seek(0)
        image = Image.open(buffer).convert('RGB')
        # resize to 1920x1080
        target = self.config.get('resolution', (1920, 1080))
        if image.size != target:
            image = image.resize(target, Image.LANCZOS)
        return image

    def create_performance_comparison(self, models_or_data, metrics: Optional[List[str]] = None,
                                   values: Optional[List[List[float]]] = None, title: str = "模型性能对比",
                                   chart_type: str = 'bar') -> Image.Image:
        """
        创建专业性能对比图表

        支持两种调用方式：
        - 显式参数(models, metrics, values)
        - 单个数据字典：{"models": [...], "accuracy": [...], ...}
        """
        # 兼容字典输入，如{"models": [...], "accuracy": [...], "speed": [...]} 等
        if isinstance(models_or_data, dict):
            d = models_or_data
            models = d.get('models', [])
            # 将除models/title外的键视为指标
            metric_keys = [k for k in d.keys() if k not in ['models', 'title']]
            metrics = metric_keys
            # 组装values为按指标的序列
            values = [d[k] for k in metric_keys]
            title = d.get('title', title)
            # 以柱状图展示多指标（每个指标为一组）
            data = {
                'categories': models,
                'values': values,
                'labels': metrics,
                'title': title,
                'x_label': '模型',
                'y_label': '数值'
            }
            result = self.generate_chart('bar', data)
            return result['image'] if result['success'] else self._create_error_image("性能对比图生成失败", result['error'])

        # 旧式参数路径
        models = models_or_data
        if chart_type == 'bar':
            data = {
                'categories': metrics,
                'values': [[values[i][j] for i in range(len(models))] for j in range(len(metrics))],
                'labels': models,
                'title': title,
                'x_label': '评估指标',
                'y_label': '性能分数'
            }
        elif chart_type == 'radar':
            data = {
                'categories': metrics,
                'values': [[values[i][j] for j in range(len(metrics))] for i in range(len(models))],
                'labels': models,
                'title': title
            }
        else:  # line
            data = {
                'x_data': metrics,
                'y_data': [[values[i][j] for j in range(len(metrics))] for i in range(len(models))],
                'labels': models,
                'title': title,
                'x_label': '评估指标',
                'y_label': '性能分数'
            }

        result = self.generate_chart(chart_type, data)
        return result['image'] if result['success'] else self._create_error_image("性能对比图生成失败", result['error'])

    def create_trend_chart(self, x_data_or_data: Union[Dict[str, Any], List[Union[str, int, float]]],
                         y_data: Optional[List[float]] = None, title: str = "趋势分析",
                         show_points: bool = True) -> Image.Image:
        """
        创建专业趋势图

        支持两种调用：
        - create_trend_chart({'dates': [...], 'values': [...], 'trend_line': True, 'title': '...'} )
        - create_trend_chart(x_data, y_data, title, show_points)
        """
        if isinstance(x_data_or_data, dict):
            d = x_data_or_data
            data = {
                'x_data': d.get('dates', d.get('x_data', [])),
                'y_data': d.get('values', d.get('y_data', [])),
                'title': d.get('title', title),
                'x_label': d.get('x_label', '时间'),
                'y_label': d.get('y_label', '数值'),
                'trend_line': d.get('trend_line', False)
            }
        else:
            data = {
                'x_data': x_data_or_data,
                'y_data': y_data or [],
                'title': title,
                'x_label': '时间/条件',
                'y_label': '数值',
                'show_points': show_points,
                'marker': 'o' if show_points else None
            }

        result = self.generate_chart('line', data)
        return result['image'] if result['success'] else self._create_error_image("趋势图生成失败", result['error'])

    def create_distribution_chart(self, values: List[float], title: str = "数据分布",
                                 bins: int = 30, show_stats: bool = True) -> Image.Image:
        """
        创建专业分布图

        Args:
            values: 数值列表
            title: 图表标题
            bins: 分箱数量
            show_stats: 是否显示统计信息

        Returns:
            图表图片
        """
        data = {
            'values': values,
            'title': title,
            'x_label': '数值区间',
            'y_label': '频次',
            'bins': bins,
            'show_stats': show_stats
        }

        result = self.generate_chart('histogram', data)

        if result['success']:
            return result['image']
        else:
            return self._create_error_image("分布图生成失败", result['error'])

    def create_correlation_chart(self, x_data: List[float], y_data: List[float],
                                title: str = "相关性分析", show_trend: bool = True) -> Image.Image:
        """
        创建相关性散点图

        Args:
            x_data: X轴数据
            y_data: Y轴数据
            title: 图表标题
            show_trend: 是否显示趋势线

        Returns:
            图表图片
        """
        data = {
            'x_data': x_data,
            'y_data': y_data,
            'title': title,
            'x_label': 'X变量',
            'y_label': 'Y变量',
            'trend_line': show_trend,
            'alpha': 0.7
        }

        result = self.generate_chart('scatter', data)

        if result['success']:
            return result['image']
        else:
            return self._create_error_image("相关性图生成失败", result['error'])

    def create_composition_chart(self, labels: List[str], sizes: List[float],
                                title: str = "构成分析", chart_type: str = 'pie') -> Image.Image:
        """
        创建构成图表

        Args:
            labels: 标签列表
            sizes: 数值列表
            title: 图表标题
            chart_type: 图表类型 ('pie', 'bar')

        Returns:
            图表图片
        """
        data = {
            'labels': labels,
            'sizes': sizes,
            'title': title
        }

        if chart_type == 'bar':
            data['categories'] = labels
            data['values'] = sizes
            del data['labels']
            del data['sizes']

        result = self.generate_chart(chart_type, data)

        if result['success']:
            return result['image']
        else:
            return self._create_error_image("构成图生成失败", result['error'])

    def create_ablation_study_chart(self, configs: List[str], performance: List[float],
                                  title: str = "消融实验结果") -> Image.Image:
        """
        创建消融实验图表

        Args:
            configs: 配置名称列表
            performance: 性能数值列表
            title: 图表标题

        Returns:
            图表图片
        """
        data = {
            'categories': configs,
            'values': performance,
            'title': title,
            'x_label': '配置',
            'y_label': '性能指标',
            'show_values': True
        }

        # 按性能排序
        sorted_data = sorted(zip(configs, performance), key=lambda x: x[1], reverse=True)
        data['categories'] = [x[0] for x in sorted_data]
        data['values'] = [x[1] for x in sorted_data]

        result = self.generate_chart('bar', data)

        if result['success']:
            return result['image']
        else:
            return self._create_error_image("消融实验图生成失败", result['error'])

    def create_multi_metric_comparison(self, model_data: Dict[str, Dict[str, float]],
                                     title: str = "多指标对比") -> Image.Image:
        """
        创建多指标对比图

        Args:
            model_data: 模型数据 {model_name: {metric: value}}
            title: 图表标题

        Returns:
            图表图片
        """
        # 获取所有指标
        all_metrics = set()
        for model_metrics in model_data.values():
            all_metrics.update(model_metrics.keys())

        # 准备数据
        models = list(model_data.keys())
        metrics = list(all_metrics)

        data = {
            'categories': metrics,
            'values': [[model_data[model].get(metric, 0) for metric in metrics] for model in models],
            'labels': models,
            'title': title,
            'x_label': '评估指标',
            'y_label': '性能分数'
        }

        result = self.generate_chart('bar', data)

        if result['success']:
            return result['image']
        else:
            return self._create_error_image("多指标对比图生成失败", result['error'])

    def create_time_series_chart(self, timestamps: List[str], values: List[float],
                                 title: str = "时间序列分析") -> Image.Image:
        """
        创建时间序列图表

        Args:
            timestamps: 时间戳列表
            values: 数值列表
            title: 图表标题

        Returns:
            图表图片
        """
        data = {
            'x_data': timestamps,
            'y_data': values,
            'title': title,
            'x_label': '时间',
            'y_label': '数值'
        }

        result = self.generate_chart('line', data)

        if result['success']:
            return result['image']
        else:
            return self._create_error_image("时间序列图生成失败", result['error'])

    def _create_error_image(self, title: str, error_msg: str) -> Image.Image:
        """创建专业错误提示图片"""
        image = Image.new('RGB', (500, 300), color=(255, 240, 240))

        from PIL import ImageDraw, ImageFont
        draw = ImageDraw.Draw(image)

        try:
            # 尝试使用系统字体
            font = ImageFont.truetype(self.config.get('font_family', 'Arial'), 18)
            title_font = ImageFont.truetype(self.config.get('font_family', 'Arial'), 24)
        except:
            font = ImageFont.load_default()
            title_font = ImageFont.load_default()

        # 绘制标题
        title_bbox = draw.textbbox((0, 0), title, font=title_font)
        title_width = title_bbox[2] - title_bbox[0]
        title_x = (500 - title_width) // 2
        draw.text((title_x, 50), title, font=title_font, fill=(180, 30, 30))

        # 绘制错误信息
        draw.text((50, 120), error_msg[:80], font=font, fill=(100, 50, 50))
        if len(error_msg) > 80:
            draw.text((50, 150), error_msg[80:160], font=font, fill=(100, 50, 50))

        # 绘制边框
        draw.rectangle([10, 10, 490, 290], outline=(200, 100, 100), width=2)

        return image