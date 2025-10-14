"""
智能论文解析器

负责解析各种格式的论文文件，提取结构化内容和数据。
支持LLM驱动的智能数据提取和表格图表解析。
"""

from typing import Dict, List, Optional, Any, Union
import logging
from pathlib import Path
import json
import re
import pandas as pd
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TableData:
    """表格数据结构"""
    title: str
    headers: List[str]
    rows: List[List[str]]
    caption: str = ""
    metadata: Dict[str, Any] = None


@dataclass
class ChartData:
    """图表数据结构（兼容测试期望的字段）"""
    chart_type: str
    title: str
    x_label: str = ""
    y_label: str = ""
    data_points: List[Dict[str, Any]] = None
    categories: List[str] = None
    values: List[Any] = None
    caption: str = ""
    metadata: Dict[str, Any] = None


class PaperDataParser:
    """智能论文数据解析器，支持LLM驱动的数据提取"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化解析器

        Args:
            config: 配置字典
        """
        # Merge provided config with defaults to ensure required keys exist
        defaults = self._get_default_config()
        self.config = {**defaults, **(config or {})}
        self.llm_client = self._initialize_llm_client()
        self.supported_formats = ['.pdf', '.txt', '.md', '.json']
        self.cache = {}  # 缓存解析结果

    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            'llm_model': 'gemini-1.5-flash',
            'max_text_length': 10000,
            'chunk_size': 2000,
            'temperature': 0.3,
            'cache_enabled': True,
            'extraction_confidence_threshold': 0.7,
            'table_detection_keywords': ['table', 'tab', '表格', '表'],
            'chart_detection_keywords': ['figure', 'fig', 'chart', 'graph', '图', '图表'],
            'metric_keywords': ['accuracy', 'precision', 'recall', 'f1', 'bleu', 'rouge', '准确率', '精确率', '召回率']
        }

    def _initialize_llm_client(self):
        """初始化LLM客户端"""
        try:
            from ..utils.llm_client import LLMClient
            from ..core.config import config

            if hasattr(config, 'llm_api_url') and hasattr(config, 'llm_api_key'):
                return LLMClient(config.llm_api_url, config.llm_api_key)
            else:
                logger.warning("LLM配置不完整，将使用基础解析方法")
                return None
        except Exception as e:
            logger.error(f"LLM客户端初始化失败: {e}")
            return None

    def parse_paper(self, paper_path: str) -> Dict[str, Any]:
        """
        解析论文文件

        Args:
            paper_path: 论文文件路径

        Returns:
            解析后的论文内容
        """
        try:
            path = Path(paper_path)
            if not path.exists():
                raise FileNotFoundError(f"论文文件不存在: {paper_path}")

            file_extension = path.suffix.lower()
            if file_extension not in self.supported_formats:
                raise ValueError(f"不支持的文件格式: {file_extension}")

            logger.info(f"开始解析论文: {paper_path} ({file_extension})")

            # 根据文件格式选择解析方法
            if file_extension == '.pdf':
                content = self._parse_pdf(paper_path)
            elif file_extension == '.txt':
                content = self._parse_txt(paper_path)
            elif file_extension == '.md':
                content = self._parse_markdown(paper_path)
            elif file_extension == '.json':
                content = self._parse_json(paper_path)
            else:
                content = self._get_fallback_content(paper_path)

            # 后处理内容
            processed_content = self._post_process_content(content, paper_path)

            logger.info(f"论文解析完成: {paper_path}")
            return processed_content

        except Exception as e:
            logger.error(f"论文解析失败: {paper_path}, 错误: {e}")
            return self._get_error_content(paper_path, str(e))

    def _parse_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """解析PDF文件"""
        # TODO: 实现PDF解析逻辑
        # 可以使用PyPDF2、pdfplumber等库
        return {
            'title': 'PDF论文标题',
            'abstract': 'PDF论文摘要',
            'sections': [
                {
                    'title': '引言',
                    'content': '这是PDF论文的引言部分内容...'
                },
                {
                    'title': '方法',
                    'content': '这是PDF论文的方法部分内容...'
                }
            ],
            'authors': ['作者1', '作者2'],
            'key_findings': ['发现1', '发现2'],
            'metadata': {
                'format': 'pdf',
                'pages': 10
            }
        }

    def _parse_txt(self, txt_path: str) -> Dict[str, Any]:
        """解析TXT文件"""
        try:
            with open(txt_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 简单的文本解析逻辑
            lines = content.split('\n')
            title = lines[0] if lines else "无标题"

            # 尝试提取摘要（通常在标题后的前几段）
            abstract = ""
            for i, line in enumerate(lines[1:10]):
                if line.strip() and not line.startswith('##') and not line.startswith('###'):
                    abstract += line.strip() + " "
                if len(abstract) > 200:
                    break

            # 解析章节
            sections = []
            current_section = None
            section_content = []

            for line in lines:
                line = line.strip()
                if line.startswith('##') or line.startswith('###'):
                    # 保存上一个章节
                    if current_section and section_content:
                        sections.append({
                            'title': current_section,
                            'content': '\n'.join(section_content)
                        })

                    # 开始新章节
                    current_section = line.lstrip('#').strip()
                    section_content = []
                elif line and current_section:
                    section_content.append(line)

            # 保存最后一个章节
            if current_section and section_content:
                sections.append({
                    'title': current_section,
                    'content': '\n'.join(section_content)
                })

            return {
                'title': title,
                'abstract': abstract.strip(),
                'sections': sections,
                'authors': [],  # TXT文件通常不包含作者信息
                'key_findings': self._extract_key_findings(content),
                'metadata': {
                    'format': 'txt',
                    'lines': len(lines)
                }
            }

        except Exception as e:
            logger.error(f"TXT文件解析失败: {e}")
            return self._get_fallback_content(txt_path)

    def _parse_markdown(self, md_path: str) -> Dict[str, Any]:
        """解析Markdown文件"""
        try:
            with open(md_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Markdown解析逻辑
            lines = content.split('\n')
            title = ""
            abstract = ""
            sections = []
            authors = []

            current_section = None
            section_content = []

            for line in lines:
                line = line.strip()

                # 提取标题
                if line.startswith('# ') and not title:
                    title = line.lstrip('# ').strip()

                # 提取作者信息（通常在标题后）
                elif line.startswith('作者:') or line.startswith('Authors:'):
                    author_line = line.split(':', 1)[1].strip()
                    authors = [author.strip() for author in author_line.split(',')]

                # 章节标题
                elif line.startswith('##'):
                    # 保存上一个章节
                    if current_section and section_content:
                        sections.append({
                            'title': current_section,
                            'content': '\n'.join(section_content)
                        })

                    # 开始新章节
                    current_section = line.lstrip('#').strip()
                    section_content = []

                # 内容行
                elif line and current_section:
                    section_content.append(line)

                # 摘要（在没有明确章节时）
                elif line and not current_section and not abstract:
                    abstract = line

            # 保存最后一个章节
            if current_section and section_content:
                sections.append({
                    'title': current_section,
                    'content': '\n'.join(section_content)
                })

            return {
                'title': title,
                'abstract': abstract,
                'sections': sections,
                'authors': authors,
                'key_findings': self._extract_key_findings(content),
                'metadata': {
                    'format': 'markdown',
                    'lines': len(lines)
                }
            }

        except Exception as e:
            logger.error(f"Markdown文件解析失败: {e}")
            return self._get_fallback_content(md_path)

    def _parse_json(self, json_path: str) -> Dict[str, Any]:
        """解析JSON文件"""
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 验证JSON结构
            if not isinstance(data, dict):
                raise ValueError("JSON文件根节点必须是对象")

            # 标准化字段
            result = {
                'title': data.get('title', data.get('标题', '无标题')),
                'abstract': data.get('abstract', data.get('摘要', '')),
                'sections': data.get('sections', data.get('sections', [])),
                'authors': data.get('authors', data.get('作者', [])),
                'key_findings': data.get('key_findings', data.get('关键发现', [])),
                'metadata': {
                    'format': 'json',
                    'original_keys': list(data.keys())
                }
            }

            # 如果sections是字符串列表，转换为标准格式
            if isinstance(result['sections'], list) and result['sections']:
                if isinstance(result['sections'][0], str):
                    result['sections'] = [
                        {'title': f'章节{i+1}', 'content': content}
                        for i, content in enumerate(result['sections'])
                    ]

            return result

        except Exception as e:
            logger.error(f"JSON文件解析失败: {e}")
            return self._get_fallback_content(json_path)

    def _extract_key_findings(self, content: str) -> List[str]:
        """从内容中提取关键发现"""
        # 简单的关键词提取逻辑
        keywords = ['发现', '结果', '结论', '贡献', '创新', 'improvement', 'result', 'conclusion', 'finding']
        findings = []

        sentences = content.split('。')
        for sentence in sentences:
            sentence = sentence.strip()
            if any(keyword in sentence for keyword in keywords) and len(sentence) > 10:
                findings.append(sentence)
                if len(findings) >= 5:  # 限制数量
                    break

        return findings

    def _post_process_content(self, content: Dict[str, Any], paper_path: str) -> Dict[str, Any]:
        """后处理解析内容"""
        # 添加文件路径信息
        if 'metadata' not in content:
            content['metadata'] = {}

        content['metadata']['file_path'] = paper_path
        content['metadata']['parsed_at'] = str(Path(paper_path).stat().st_mtime)

        # 确保必需字段存在
        content.setdefault('title', '未知标题')
        content.setdefault('abstract', '')
        content.setdefault('sections', [])
        content.setdefault('authors', [])
        content.setdefault('key_findings', [])

        # 如果没有章节，创建默认章节
        if not content['sections'] and content['abstract']:
            content['sections'] = [
                {
                    'title': '摘要',
                    'content': content['abstract']
                }
            ]

        return content

    def _get_fallback_content(self, paper_path: str) -> Dict[str, Any]:
        """获取回退内容"""
        path = Path(paper_path)
        return {
            'title': path.stem,
            'abstract': f'无法解析文件: {paper_path}',
            'sections': [
                {
                    'title': '解析失败',
                    'content': '文件格式不支持或解析过程中出现错误。'
                }
            ],
            'authors': [],
            'key_findings': [],
            'metadata': {
                'format': 'unknown',
                'file_path': paper_path,
                'error': 'parsing_failed'
            }
        }

    def _get_error_content(self, paper_path: str, error_msg: str) -> Dict[str, Any]:
        """获取错误内容"""
        return {
            'title': '解析错误',
            'abstract': f'论文解析失败: {error_msg}',
            'sections': [
                {
                    'title': '错误信息',
                    'content': f'文件: {paper_path}\n错误: {error_msg}'
                }
            ],
            'authors': [],
            'key_findings': [],
            'metadata': {
                'format': 'error',
                'file_path': paper_path,
                'error': error_msg
            }
        }

    # ========== 新增的智能数据提取方法 ==========

    def extract_data(self, paper_content: str, query: str) -> Dict[str, Any]:
        """
        智能数据提取

        Args:
            paper_content: 论文内容
            query: 查询内容

        Returns:
            Dict[str, Any]: 提取的数据
        """
        # 基本参数校验
        if not isinstance(paper_content, str) or not paper_content.strip():
            raise ValueError("paper_content is empty")
        if not isinstance(query, str) or not query.strip():
            return {'error': 'query is empty', 'data': None}
        try:
            # 检查缓存
            cache_key = f"{hash(paper_content[:500])}_{hash(query)}"
            if self.config.get('cache_enabled') and cache_key in self.cache:
                logger.info("使用缓存的数据提取结果")
                return self.cache[cache_key]

            # 使用LLM进行智能数据提取
            if self.llm_client:
                result = self._llm_extract_data(paper_content, query)
            else:
                # 回退到基础提取方法
                result = self._basic_extract_data(paper_content, query)

            # 缓存结果
            if self.config.get('cache_enabled'):
                self.cache[cache_key] = result

            return result

        except Exception as e:
            logger.error(f"数据提取失败: {e}")
            return {'error': str(e), 'data': None}

    def _llm_extract_data(self, paper_content: str, query: str) -> Dict[str, Any]:
        """
        使用LLM提取数据

        Args:
            paper_content: 论文内容
            query: 查询内容

        Returns:
            提取的数据
        """
        try:
            # 截断内容以避免超出限制
            content = paper_content[:self.config['max_text_length']]

            # 构建提示词
            prompt = self._build_extraction_prompt(query, content)

            messages = [
                {
                    "role": "system",
                    "content": "你是一个专业的学术论文数据提取专家。请从给定的论文内容中提取准确、结构化的数据。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]

            response = self.llm_client.chat_completion(
                messages,
                temperature=self.config['temperature'],
                max_tokens=2000
            )

            # 解析响应
            return self._parse_extraction_response(response, query)

        except Exception as e:
            logger.error(f"LLM数据提取失败: {e}")
            return self._basic_extract_data(paper_content, query)

    def _build_extraction_prompt(self, query: str, content: str) -> str:
        """
        构建数据提取提示词

        Args:
            query: 查询内容
            content: 论文内容

        Returns:
            提示词
        """
        # 分析查询类型
        extraction_type = self._analyze_query_type(query)

        prompts = {
            'table': f"""
请从以下论文内容中提取表格数据，返回JSON格式：

查询：{query}

论文内容：
{content}

请返回以下JSON格式的数据：
{{
    "type": "table",
    "title": "表格标题",
    "headers": ["列1", "列2", "列3"],
    "rows": [
        ["值1", "值2", "值3"],
        ["值4", "值5", "值6"]
    ],
    "caption": "表格说明",
    "confidence": 0.95
}}

要求：
1. 仔细识别表格的结构和数据
2. 确保数值的准确性
3. 包含表格的标题和说明
4. 评估提取的置信度（0-1）
5. 只返回JSON，不要其他文字
""",

            'chart': f"""
请从以下论文内容中提取图表数据，返回JSON格式：

查询：{query}

论文内容：
{content}

请返回以下JSON格式的数据：
{{
    "type": "chart",
    "title": "图表标题",
    "chart_type": "bar/line/pie/scatter/area/radar/histogram/box",
    "data": {{
        "categories": ["类别1", "类别2"],
        "values": [值1, 值2]
    }},
    "caption": "图表说明",
    "confidence": 0.95
}}

要求：
1. 识别图表类型和结构
2. 准确提取数据点
3. 包含图表的标题和说明
4. 评估提取的置信度（0-1）
5. 只返回JSON，不要其他文字
""",

            'metrics': f"""
请从以下论文内容中提取性能指标数据，返回JSON格式：

查询：{query}

论文内容：
{content}

请返回以下JSON格式的数据：
{{
    "type": "metrics",
    "models": ["模型1", "模型2"],
    "metrics": ["准确率", "精确率", "召回率", "F1分数"],
    "values": [
        [0.95, 0.93, 0.91, 0.94],
        [0.92, 0.89, 0.88, 0.90]
    ],
    "confidence": 0.95
}}

要求：
1. 识别所有相关的性能指标
2. 准确提取数值数据
3. 确保模型和指标的对应关系
4. 评估提取的置信度（0-1）
5. 只返回JSON，不要其他文字
""",

            'general': f"""
请从以下论文内容中提取相关数据，返回JSON格式：

查询：{query}

论文内容：
{content}

请返回以下JSON格式的数据：
{{
    "type": "general",
    "data": "提取的相关数据内容",
    "key_points": ["要点1", "要点2", "要点3"],
    "confidence": 0.90
}}

要求：
1. 仔细理解查询意图
2. 提取最相关的数据和信息
3. 总结关键要点
4. 评估提取的置信度（0-1）
5. 只返回JSON，不要其他文字
"""
        }

        return prompts.get(extraction_type, prompts['general'])

    def _analyze_query_type(self, query: str) -> str:
        """
        分析查询类型

        Args:
            query: 查询内容

        Returns:
            查询类型
        """
        query_lower = query.lower()

        # 表格相关
        if any(keyword in query_lower for keyword in self.config.get('table_detection_keywords', ['table', 'tab', '表格', '表'])):
            return 'table'

        # 图表相关
        if any(keyword in query_lower for keyword in self.config.get('chart_detection_keywords', ['figure', 'fig', 'chart', 'graph', '图', '图表'])):
            return 'chart'

        # 性能指标相关
        if any(keyword in query_lower for keyword in self.config.get('metric_keywords', ['accuracy', 'precision', 'recall', 'f1', 'bleu', 'rouge', '准确率', '精确率', '召回率'])):
            return 'metrics'

        return 'general'

    def _parse_extraction_response(self, response: str, query: str) -> Dict[str, Any]:
        """
        解析LLM提取响应

        Args:
            response: LLM响应
            query: 原始查询

        Returns:
            解析后的数据
        """
        try:
            # 尝试直接解析JSON
            import json
            result = json.loads(response)

            # 验证置信度
            confidence = result.get('confidence', 0.0)
            if confidence < self.config['extraction_confidence_threshold']:
                logger.warning(f"提取置信度较低: {confidence}")

            return result

        except json.JSONDecodeError:
            logger.warning("LLM响应不是有效JSON，尝试提取JSON片段")
            # 尝试提取JSON片段
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group())
                    return result
                except:
                    pass

            # 最终回退
            return {
                'type': 'general',
                'data': response,
                'confidence': 0.5,
                'error': 'JSON解析失败'
            }

    def _basic_extract_data(self, paper_content: str, query: str) -> Dict[str, Any]:
        """
        基础数据提取（回退方法）

        Args:
            paper_content: 论文内容
            query: 查询内容

        Returns:
            提取的数据
        """
        query_type = self._analyze_query_type(query)

        if query_type == 'table':
            return self._extract_tables_basic(paper_content)
        elif query_type == 'chart':
            return self._extract_figures_basic(paper_content)
        elif query_type == 'metrics':
            return self._extract_performance_basic(paper_content)
        else:
            return self._extract_general_basic(paper_content, query)

    def extract_table_data(self, paper_content: str, table_query: str = "提取所有表格") -> List[TableData]:
        """
        提取表格数据

        Args:
            paper_content: 论文内容
            table_query: 表格查询

        Returns:
            表格数据列表
        """
        try:
            result = self.extract_data(paper_content, table_query)

            if result.get('type') == 'table':
                table_data = TableData(
                    title=result.get('title', ''),
                    headers=result.get('headers', []),
                    rows=result.get('rows', []),
                    caption=result.get('caption', ''),
                    metadata={'confidence': result.get('confidence', 0.0)}
                )
                return [table_data]
            else:
                return []

        except Exception as e:
            logger.error(f"表格数据提取失败: {e}")
            return []

    def extract_chart_data(self, paper_content: str, chart_query: str = "提取所有图表") -> List[ChartData]:
        """
        提取图表数据

        Args:
            paper_content: 论文内容
            chart_query: 图表查询

        Returns:
            图表数据列表
        """
        try:
            result = self.extract_data(paper_content, chart_query)

            if result.get('type') == 'chart':
                chart_data = ChartData(
                    title=result.get('title', ''),
                    chart_type=result.get('chart_type', 'bar'),
                    data=result.get('data', {}),
                    caption=result.get('caption', ''),
                    metadata={'confidence': result.get('confidence', 0.0)}
                )
                return [chart_data]
            else:
                return []

        except Exception as e:
            logger.error(f"图表数据提取失败: {e}")
            return []

    def extract_metrics_data(self, paper_content: str) -> Dict[str, Any]:
        """
        提取性能指标数据

        Args:
            paper_content: 论文内容

        Returns:
            性能指标数据
        """
        try:
            result = self.extract_data(paper_content, "提取性能指标和准确率等数据")

            if result.get('type') == 'metrics':
                return {
                    'models': result.get('models', []),
                    'metrics': result.get('metrics', []),
                    'values': result.get('values', []),
                    'confidence': result.get('confidence', 0.0)
                }
            else:
                return {}

        except Exception as e:
            logger.error(f"性能指标提取失败: {e}")
            return {}

    def _extract_tables_basic(self, content: str) -> Dict[str, Any]:
        """基础表格提取"""
        # 简单的表格识别模式
        table_patterns = [
            r'Table\s+\d+[:\s]*([^\n]+)',
            r'表\s*\d+[:\s]*([^\n]+)'
        ]

        for pattern in table_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                return {
                    'type': 'table',
                    'title': matches[0],
                    'confidence': 0.6
                }

        return {'type': 'table', 'confidence': 0.3, 'data': None}

    def _extract_figures_basic(self, content: str) -> Dict[str, Any]:
        """基础图表提取"""
        # 简单的图表识别模式
        figure_patterns = [
            r'Figure\s+\d+[:\s]*([^\n]+)',
            r'图\s*\d+[:\s]*([^\n]+)'
        ]

        for pattern in figure_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                return {
                    'type': 'chart',
                    'title': matches[0],
                    'confidence': 0.6
                }

        return {'type': 'chart', 'confidence': 0.3, 'data': None}

    def _extract_performance_basic(self, content: str) -> Dict[str, Any]:
        """基础性能数据提取"""
        # 查找性能指标
        metric_pattern = r'(accuracy|precision|recall|f1[-\s]*score|准确率|精确率|召回率)[:\s]*([0-9.]+)'
        matches = re.findall(metric_pattern, content, re.IGNORECASE)

        if matches:
            metrics = [match[0] for match in matches]
            values = [float(match[1]) for match in matches]

            return {
                'type': 'metrics',
                'metrics': metrics,
                'values': values,
                'confidence': 0.7
            }

        return {'type': 'metrics', 'confidence': 0.3, 'data': None}

    def _extract_general_basic(self, content: str, query: str) -> Dict[str, Any]:
        """基础通用数据提取"""
        # 查找查询相关的句子
        sentences = content.split('。')
        relevant_sentences = []
        for sentence in sentences:
            if any(word in sentence.lower() for word in (query or '').lower().split()):
                relevant_sentences.append(sentence.strip())
        return {
            'type': 'general',
            'data': ' '.join(relevant_sentences[:5]),
            'confidence': 0.5
        }


    # ========== 测试期望的辅助格式化/校验方法 ==========
    def format_table_data(self, raw_data: Dict[str, Any]) -> TableData:
        title = raw_data.get('title', '')
        headers = raw_data.get('headers') or list(raw_data.keys())
        rows = raw_data.get('rows')
        if rows is None and isinstance(raw_data, dict):
            # 将键值对转为行
            rows = [[k, str(v)] for k, v in raw_data.items() if k not in ('title', 'headers', 'caption')]
        return TableData(title=title, headers=headers, rows=rows or [], caption=raw_data.get('caption', ''))

    def format_chart_data(self, raw_data: Dict[str, Any]) -> ChartData:
        return ChartData(
            chart_type=raw_data.get('chart_type', 'bar'),
            title=raw_data.get('title', ''),
            x_label=raw_data.get('x_label', ''),
            y_label=raw_data.get('y_label', ''),
            data_points=raw_data.get('data_points', []),
            categories=raw_data.get('categories'),
            values=raw_data.get('values'),
            caption=raw_data.get('caption', ''),
            metadata=raw_data.get('metadata')
        )

    def format_performance_data(self, perf: Dict[str, Any]) -> Dict[str, Any]:
        models = perf.get('models', [])
        metrics = perf.get('metrics', {})
        # 选择一个代表性指标用于柱状图（优先accuracy/f1）
        preferred = None
        for key in ['accuracy', 'acc', 'f1', 'f1_score']:
            if key in metrics:
                preferred = key
                break
        preferred = preferred or (list(metrics.keys())[0] if metrics else None)
        values = metrics.get(preferred, []) if preferred else []
        chart_data = {
            'chart_type': 'bar',
            'title': perf.get('dataset', '性能对比'),
            'categories': models,
            'values': values
        }
        # 生成表格
        headers = ['Metric'] + models
        rows = []
        for m, arr in metrics.items():
            row = [m] + [str(arr[i]) if i < len(arr) else 'N/A' for i in range(len(models))]
            rows.append(row)
        table = TableData(title=perf.get('dataset', '性能表'), headers=headers, rows=rows)
        return {'chart_data': chart_data, 'table_data': table.__dict__}

    def format_training_progress(self, data: Dict[str, Any]) -> Dict[str, Any]:
        # 返回折线图所需的数据结构
        series = []
        for name, s in (data.get('models') or {}).items():
            series.append({'name': name, 'x': s.get('epochs', []), 'y': s.get('accuracy', [])})
        return {'line_chart_data': {'chart_type': 'line', 'series': series}}

    def format_comparison_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        heatmap = {
            'chart_type': 'heatmap',
            'x_labels': data.get('tasks', []),
            'y_labels': data.get('models', []),
            'matrix': data.get('accuracy_matrix', [])
        }
        # 汇总每个模型的平均准确率作为柱状图
        matrix = data.get('accuracy_matrix', [])
        avgs = [sum(row)/len(row) if row else 0 for row in matrix]
        bar = {'chart_type': 'bar', 'categories': data.get('models', []), 'values': avgs}
        return {'heatmap_data': heatmap, 'bar_chart_data': bar}

    def validate_table_data(self, d: Dict[str, Any]) -> bool:
        headers = d.get('headers') or []
        rows = d.get('rows') or []
        if not headers or not rows:
            return False
        cols = len(headers)
        return all(isinstance(r, list) and len(r) == cols for r in rows)

    def validate_chart_data(self, d: Dict[str, Any]) -> bool:
        ctype = d.get('chart_type')
        if ctype == 'scatter':
            pts = d.get('data_points') or []
            return len(pts) >= 1 and all('x' in p and 'y' in p for p in pts)
        if ctype == 'bar':
            cats = d.get('categories') or []
            vals = d.get('values') or []
            return len(cats) >= 1 and len(cats) == len(vals)
        return False

    def detect_chart_type(self, description: str) -> str:
        s = (description or '').lower()
        if any(k in s for k in ['scatter', '散点']):
            return 'scatter'
        if any(k in s for k in ['bar', '柱']):
            return 'bar'
        if any(k in s for k in ['line', '折线']):
            return 'line'
        if any(k in s for k in ['pie', '饼']):
            return 'pie'
        return 'bar'

    def clean_data(self, d: Dict[str, Any]) -> Dict[str, Any]:
        def parse_num(v: Any):
            if v is None:
                return None
            s = str(v).strip()
            if s.upper() == 'N/A' or s == '':
                return None
            if s.endswith('%'):
                try:
                    return float(s[:-1])
                except:
                    return None
            try:
                f = float(s)
                # 若在0-1之间，当作比例，转为百分比
                return round(f*100, 1) if 0 <= f <= 1 else f
            except:
                return None
        out = dict(d)
        if 'values' in out and isinstance(out['values'], list):
            out['values'] = [parse_num(v) for v in out['values']]
        if 'labels' in out and isinstance(out['labels'], list):
            out['labels'] = [str(x).strip() for x in out['labels']]
        return out

    def extract_keywords(self, text: str, max_keywords: int = 10) -> List[str]:
        words = re.findall(r'[\u4e00-\u9fa5A-Za-z0-9]+', text or '')
        from collections import Counter
        freq = Counter(w for w in words if len(w) >= 2)
        return [w for w, _ in freq.most_common(max_keywords)]

    def extract_summary(self, text: str, max_length: int = 200) -> str:
        s = (text or '').strip().replace('\n', ' ')
        return s[:max_length]


