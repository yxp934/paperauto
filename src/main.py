"""
主工作流程模块
自动化论文视频生成的完整流程
"""
import os
import sys
import traceback
from datetime import datetime
from typing import List, Dict, Optional
import re

# 添加src目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import config
from src.utils.logger import get_logger
from src.utils.helpers import save_json, clean_temp_files, ensure_dir
from src.papers.fetch_papers import PaperFetcher
from src.utils.llm_client import LLMClient
from src.video.image_generator import ImageGenerator
from src.video.tts_generator import TTSGenerator
from src.video.video_composer import VideoComposer
from src.slide.orchestrator import SlideOrchestrator

logger = get_logger("main")


class PaperVideoPipeline:
    """论文视频生成流水线"""

    def __init__(self, runtime_options: Optional[Dict] = None):
        logger.info("初始化论文视频生成流水线")

        # 记录运行期选项，后续阶段将用于控制内容提供器等功能
        self.runtime_options = runtime_options or {}

        # 确保目录存在
        config.ensure_directories()

        # 初始化各个组件
        self.paper_fetcher = PaperFetcher()
        self.llm_client = LLMClient(config.llm_api_url, config.llm_api_key)
        self.image_generator = ImageGenerator()
        self.tts_generator = TTSGenerator()
        self.video_composer = VideoComposer()

        # 初始化Slide生成器（如果启用）
        self.slide_orchestrator = None
        if config.use_slide_system:
            try:
                slide_config = {
                    'max_workers': config.slide_max_workers,
                    'enable_parallel': config.slide_parallel_enabled,
                    'enable_caching': config.slide_cache_enabled,
                    'cache_ttl': config.slide_timeout,
                    'retry_attempts': config.slide_retry_attempts,
                    'cache_dir': config.slide_cache_dir,
                    'output_dir': config.slide_output_dir,
                    'temp_dir': config.slide_temp_dir,
                    'renderer': {
                        'resolution': config.slide_resolution,
                        'format': config.slide_format,
                        'quality': config.slide_quality
                    }
                }
                self.slide_orchestrator = SlideOrchestrator(
                    llm_client=self.llm_client,
                    config=slide_config,
                    runtime_options=self.runtime_options,
                )
                logger.info("Slide系统初始化成功")
            except Exception as e:
                logger.warning(f"Slide系统初始化失败，将使用传统图片生成: {e}")
                self.slide_orchestrator = None
        else:
            logger.info("Slide系统已禁用，将使用传统图片生成")

    def run_complete_pipeline(self, max_papers: int = None) -> List[Dict]:
        """运行完整的流水线"""
        if max_papers is None:
            max_papers = config.max_papers

        logger.info(f"开始运行完整流水线，最大论文数: {max_papers}")

        results = []

        try:
            # 1. 获取热门论文
            logger.info("=" * 50)
            logger.info("步骤 1: 获取热门论文")
            logger.info("=" * 50)

            papers = self.paper_fetcher.fetch_daily_papers()
            papers = papers[:max_papers]

            if not papers:
                logger.error("没有获取到论文，终止流程")
                return results

            logger.info(f"成功获取 {len(papers)} 篇论文")

            # 2. 处理每篇论文
            for i, paper in enumerate(papers):
                try:
                    logger.info("=" * 50)
                    logger.info(f"步骤 2.{i+1}: 处理论文 {i+1}/{len(papers)} - {paper.title}")
                    logger.info("=" * 50)

                    result = self.process_single_paper(paper, i + 1)
                    if result:
                        results.append(result)
                        logger.info(f"论文 {paper.title} 处理成功")
                    else:
                        logger.error(f"论文 {paper.title} 处理失败")

                except Exception as e:
                    logger.error(f"处理论文 {paper.title} 时发生异常: {e}")
                    logger.error(traceback.format_exc())
                    continue

            # 3. 清理临时文件
            logger.info("=" * 50)
            logger.info("步骤 3: 清理临时文件")
            logger.info("=" * 50)

            clean_temp_files(config.temp_dir)

            # 4. 生成处理报告
            self._generate_report(results)

            logger.info(f"流水线完成，成功处理 {len(results)}/{len(papers)} 篇论文")
            return results

        except Exception as e:
            logger.error(f"流水线执行失败: {e}")
            logger.error(traceback.format_exc())
            return results

    def process_single_paper(self, paper, paper_index: int) -> Optional[Dict]:
        """处理单篇论文"""
        try:
            logger.info(f"开始处理论文: {paper.title}")

            # 创建论文专用目录
            safe_paper_id = paper.id.replace('/', '_').replace('\\', '_')
            paper_dir = os.path.join(config.temp_dir, f"paper_{paper_index:02d}")
            ensure_dir(paper_dir)

            # 1. 分析论文
            logger.info("1.1 分析论文内容...")
            analysis_result = self.llm_client.analyze_paper(
                paper.title, paper.description, paper.authors
            )
            paper.analysis_result = analysis_result

            # 2. 生成视频脚本
            logger.info("1.2 生成视频脚本...")
            script_data = self._generate_script_with_analysis(paper)
            if not script_data:
                logger.error("生成脚本失败")
                return None

            paper.video_script = script_data

            # 3. 生成图片/Sildes
            logger.info("1.3 生成视频图片...")
            image_assets = []

            # 决定使用slide系统还是传统图片生成
            use_slides = self.slide_orchestrator is not None and config.use_slide_system

            if use_slides:
                logger.info("使用智能slide生成系统...")
                try:
                    # 准备论文数据
                    paper_data = {
                        'title': paper.title,
                        'abstract': paper.description,
                        'authors': paper.authors,
                        'tags': getattr(paper, 'tags', []),
                        'analysis': analysis_result
                    }

                    # 生成slides
                    slide_paths = self.slide_orchestrator.generate_slides_for_paper(
                        paper_id=safe_paper_id,
                        paper_data=paper_data,
                        script_sections=script_data['sections']
                    )

                    if slide_paths:
                        # 将slide路径转换为image_assets格式
                        for i, slide_path in enumerate(slide_paths):
                            if os.path.exists(slide_path):
                                image_assets.append({
                                    'path': slide_path,
                                    'section_index': i,
                                    'variant_index': 0,
                                    'prompt': f'Slide for section {i+1}',
                                    'is_fallback': False,
                                    'is_slide': True,
                                    'is_cover': False
                                })
                        logger.info(f"成功生成 {len(image_assets)} 个slides")
                    else:
                        logger.warning("Slide生成失败，回退到传统图片生成")
                        use_slides = False

                except Exception as e:
                    logger.error(f"Slide生成过程中出现异常: {e}")
                    logger.warning("回退到传统图片生成")
                    use_slides = False

            # 如果slide系统未启用或失败，使用传统图片生成
            if not use_slides or not image_assets:
                logger.info("使用传统图片生成...")
                image_assets = self.image_generator.generate_images_for_paper(
                    safe_paper_id, script_data['sections']
                )

                if not image_assets:
                    logger.warning("生成图片失败，尝试创建默认图片")
                    # 创建默认图片
                    default_image_path = self._create_default_image(safe_paper_id)
                    if default_image_path:
                        image_assets = [{
                            'path': default_image_path,
                            'section_index': 0,
                            'variant_index': 0,
                            'prompt': 'Default image',
                            'is_fallback': True,
                            'is_cover': True
                        }]
                    else:
                        logger.error("无法创建默认图片")
                        return None

            # 生成封面图片（无论使用哪种方式都生成封面）
            cover_path = self.image_generator.generate_cover_image(
                paper.title, analysis_result.get('summary', '')
            )
            if cover_path:
                cover_asset = {
                    'path': cover_path,
                    'section_index': 0,
                    'variant_index': -1,
                    'prompt': 'Cover image',
                    'is_fallback': False,
                    'is_cover': True
                }
                image_assets.insert(0, cover_asset)

            # 4. 生成音频
            logger.info("1.4 生成语音音频...")
            audio_data = self.tts_generator.generate_audio_for_paper(
                safe_paper_id, script_data['sections']
            )

            if not audio_data:
                # 允许在无音频的情况下继续（例如测试或静默视频场景）
                logger.warning("没有生成任何音频数据，将尝试继续生成无音频视频")

            # 5. 合成视频
            logger.info("1.5 合成最终视频...")
            video_path = self.video_composer.create_video_from_assets(
                safe_paper_id, paper.title, image_assets, audio_data, script_data['sections']
            )

            if not video_path:
                logger.error("合成视频失败")
                return None

            # 6. 生成字幕
            logger.info("1.6 生成字幕文件...")
            subtitle_target_path = os.path.join(
                config.output_dir,
                f"{safe_paper_id}_{paper.safe_title}_subtitles.srt"
            )
            subtitle_path = self.video_composer.create_subtitle_file(
                audio_data, script_data['sections'], subtitle_target_path
            ) or subtitle_target_path

            # 7. 获取视频信息
            video_info = self.video_composer.get_video_info(video_path)

            # 构建结果
            result = {
                'paper': paper.to_dict(),
                'analysis': analysis_result,
                'script': script_data,
                'video_path': video_path,
                'subtitle_path': subtitle_path,
                'video_info': video_info,
                'timestamp': datetime.now().isoformat(),
                'status': 'success'
            }

            # 8. 上传到Bilibili (如果启用)
            if config.bilibili_enabled:
                logger.info("1.7 上传到Bilibili...")
                bilibili_result = self._upload_to_bilibili(
                    video_path,
                    image_assets,
                    paper,
                    analysis_result,
                    script_data
                )
                result['bilibili_upload'] = bilibili_result

            # 保存结果到文件
            result_file = os.path.join(
                config.output_dir,
                f"{safe_paper_id}_result.json"
            )
            save_json(result, result_file)

            logger.info(f"论文处理完成: {video_path}")
            return result

        except Exception as e:
            logger.error(f"处理论文时发生异常: {e}")
            logger.error(traceback.format_exc())
            return None

    def _generate_script_with_analysis(self, paper) -> Optional[Dict]:
        """基于论文分析生成脚本"""
        try:
            # 合并论文信息和分析结果
            # 将分析结果提升为顶层字段，避免下游取值缺失
            analysis = paper.analysis_result or {}
            script_data = {
                'title': paper.title,
                'tags': getattr(paper, 'tags', [])
            }
            # 合并分析内容（summary/key_points/technical_details/innovations/applications 等）
            if isinstance(analysis, dict):
                script_data.update(analysis)

            # 生成完整脚本
            full_script = self.llm_client.generate_video_script(script_data)
            if not full_script:
                return None

            # 分割脚本段落
            sections = self.llm_client.split_script_sections(full_script)

            # 生成并前置“吸引开场（Hook）”，避免与主脚本开场白冲突
            hook_text = None
            try:
                if isinstance(self.llm_client, LLMClient):
                    hook_data = self.llm_client.generate_video_hook(script_data)
                    if isinstance(hook_data, dict):
                        hook_text = (hook_data.get('hook') or '').strip()
            except Exception as hook_exc:
                logger.warning(f"生成视频Hook失败，跳过：{hook_exc}")

            if hook_text:
                hook_section = {
                    'title': '【吸引开场】（20秒）',
                    'content': hook_text,
                    'raw_content': hook_text,
                    'is_hook': True
                }
                sections = [hook_section] + sections

            # 为每个段落生成图片提示词
            for section in sections:
                if section.get('is_hook'):
                    # Hook 段落：不进行slide重写，直接生成图片提示
                    section['raw_content'] = section.get('content', '')
                    section['keywords'] = []
                    section['talking_points'] = []
                    section['background_prompt'] = 'Modern tech style, subtle tension, eye-catching composition'
                    section['image_prompt'] = self.llm_client.generate_image_prompts(
                        section.get('content', ''), section.get('title', '')
                    )
                else:
                    slide_plan = self.llm_client.generate_slide_prompt(
                        section.get('title', ''),
                        section.get('content', '')
                    )
                    # 保存原始中文内容到raw_content（用于TTS）
                    section['raw_content'] = section.get('content', '')

                    # 优先使用结构化的中文narration_cn；若回退为原始内容
                    final_narration = slide_plan.get('narration_cn') or section['raw_content']
                    if final_narration:
                        # 去除可能的舞台/时间提示（轻度清理，详尽清理在 TTS 阶段再做一次）
                        lines = [ln.strip() for ln in final_narration.split('\n') if ln.strip()]
                        lines = [ln for ln in lines if not re.match(r"^\s*(镜头|画面|配图|图示|字幕|旁白|BGM|转场|切换)[：:]", ln)]
                        cleaned = ' '.join(lines)
                        cleaned = re.sub(r"[（(]\s*\d+(?:\.\d+)?\s*(?:分钟|分|秒)(?:钟)?\s*[)）]", "", cleaned)
                        cleaned = re.sub(r"\(\s*\d+(?:\.\d+)?\s*(?:seconds?|minutes?|mins?|sec)\s*\)", "", cleaned, flags=re.IGNORECASE)
                        cleaned = re.sub(r"[（(][^）)]*(?:镜头|画面|配图|图示|字幕|旁白|BGM|转场|切换)[^）)]*[)）]", "", cleaned)
                        final_narration = cleaned.strip()

                    # content现在是精炼的中文解说词（用于显示和Slide）
                    section['content'] = final_narration
                    # 提取关键词和要点（用于Slide生成）
                    section['keywords'] = slide_plan.get('keywords', [])
                    section['talking_points'] = slide_plan.get('talking_points', [])
                    section['background_prompt'] = slide_plan.get('background_prompt')
                    section['image_prompt'] = slide_plan.get('image_prompt') or self.llm_client.generate_image_prompts(
                        section['content'], section.get('title', '')
                    )

            script_data['full_script'] = full_script
            script_data['sections'] = sections

            return script_data

        except Exception as e:
            logger.error(f"生成脚本失败: {e}")
            return None

    def _generate_report(self, results: List[Dict]):
        """生成处理报告"""
        try:
            logger.info("生成处理报告...")

            total_papers = len(results)
            successful_papers = len([r for r in results if r.get('status') == 'success'])
            failed_papers = total_papers - successful_papers

            # 计算总视频时长
            total_duration = sum(
                r.get('video_info', {}).get('duration', 0)
                for r in results if r.get('video_info')
            )

            report = {
                'timestamp': datetime.now().isoformat(),
                'summary': {
                    'total_papers': total_papers,
                    'successful_papers': successful_papers,
                    'failed_papers': failed_papers,
                    'success_rate': f"{(successful_papers / total_papers * 100):.1f}%" if total_papers > 0 else "0%",
                    'total_duration': total_duration,
                    'total_duration_formatted': self._format_duration(total_duration)
                },
                'papers': []
            }

            for result in results:
                paper_info = {
                    'title': result.get('paper', {}).get('title', 'Unknown'),
                    'status': result.get('status', 'unknown'),
                    'video_path': result.get('video_path', ''),
                    'video_info': result.get('video_info', {}),
                    'timestamp': result.get('timestamp', '')
                }
                report['papers'].append(paper_info)

            # 保存报告
            report_path = os.path.join(
                config.output_dir,
                f"pipeline_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            save_json(report, report_path)

            # 打印摘要
            logger.info("=" * 50)
            logger.info("流水线执行摘要:")
            logger.info(f"  总论文数: {total_papers}")
            logger.info(f"  成功处理: {successful_papers}")
            logger.info(f"  处理失败: {failed_papers}")
            logger.info(f"  成功率: {report['summary']['success_rate']}")
            logger.info(f"  总视频时长: {report['summary']['total_duration_formatted']}")
            logger.info(f"  报告文件: {report_path}")
            logger.info("=" * 50)

        except Exception as e:
            logger.error(f"生成报告失败: {e}")

    def _create_default_image(self, paper_id: str) -> Optional[str]:
        """创建默认图片"""
        try:
            from PIL import Image, ImageDraw, ImageFont
            import os

            # 创建图片
            width, height = 1920, 1080
            image = Image.new('RGB', (width, height), color='#1a1a2e')
            draw = ImageDraw.Draw(image)

            # 添加渐变背景
            for y in range(height):
                blue_value = int(26 + (40 * y / height))
                color = (blue_value, blue_value, blue_value + 35)
                draw.line([(0, y), (width, y)], fill=color)

            # 添加标题
            title = "AI Research Demo"
            try:
                font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 60)
            except:
                font = ImageFont.load_default()

            text_width = draw.textlength(title, font=font)
            x = (width - text_width) // 2
            y = height // 2 - 30
            draw.text((x, y), title, fill='white', font=font)

            # 保存图片
            temp_dir = os.path.join(config.temp_dir, "images")
            os.makedirs(temp_dir, exist_ok=True)

            image_path = os.path.join(temp_dir, f"{paper_id}_default.png")
            image.save(image_path, 'PNG', quality=95)

            logger.info(f"创建默认图片: {image_path}")
            return image_path

        except Exception as e:
            logger.error(f"创建默认图片失败: {e}")
            return None

    def _upload_to_bilibili(
        self,
        video_path: str,
        image_assets: list,
        paper,
        analysis_result: dict,
        script_data: dict
    ) -> dict:
        """上传视频到Bilibili

        Args:
            video_path: 视频文件路径
            image_assets: 图片资源列表
            paper: 论文对象
            analysis_result: 论文分析结果
            script_data: 视频脚本数据

        Returns:
            dict: 上传结果 {'status': 'success'/'failed', 'message': str}
        """
        try:
            from src.upload.bilibili_uploader import BilibiliUploader

            logger.info("开始Bilibili上传流程...")

            # 初始化上传器
            uploader = BilibiliUploader(debug_port=config.bilibili_debug_port)

            # 连接浏览器
            if not uploader.connect_browser():
                logger.error("无法连接到Chrome浏览器")
                logger.error(f"请先运行: google-chrome --remote-debugging-port={config.bilibili_debug_port}")
                logger.error("并在浏览器中登录Bilibili账号")
                return {
                    'status': 'failed',
                    'message': '无法连接到Chrome浏览器'
                }

            # 查找封面图片
            cover_path = None
            for asset in image_assets:
                if asset.get('is_cover'):
                    cover_path = asset.get('path')
                    break

            # 准备视频标题
            title = paper.title
            if len(title) > 80:
                title = title[:77] + "..."

            # 准备视频简介
            summary = analysis_result.get('summary', '')
            description = f"{summary}\n\n"
            description += f"论文来源: {paper.paper_url or 'Hugging Face'}\n"
            if paper.authors:
                description += f"作者: {', '.join(paper.authors[:3])}\n"

            # 限制简介长度
            if len(description) > 2000:
                description = description[:1997] + "..."

            # 准备标签
            tags = paper.tags if hasattr(paper, 'tags') and paper.tags else config.bilibili_default_tags
            if not tags:
                tags = ['AI', '论文解读', '科技']

            # 准备上传信息
            upload_info = {
                'video_path': video_path,
                'cover_path': cover_path,
                'title': title,
                'description': description,
                'category': config.bilibili_default_category,
                'tags': tags
            }

            logger.info(f"视频标题: {title}")
            logger.info(f"视频标签: {', '.join(tags)}")
            logger.info(f"视频分类: {config.bilibili_default_category}")

            # 执行上传
            upload_success = uploader.upload_video(upload_info)

            # 关闭连接
            uploader.close()

            if upload_success:
                logger.info("✓ Bilibili上传成功")
                return {
                    'status': 'success',
                    'message': '上传成功'
                }
            else:
                logger.error("✗ Bilibili上传失败")
                return {
                    'status': 'failed',
                    'message': '上传过程失败'
                }

        except Exception as e:
            logger.error(f"Bilibili上传异常: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'status': 'failed',
                'message': f'上传异常: {str(e)}'
            }

    def _format_duration(self, seconds: float) -> str:
        """格式化时长"""
        if seconds < 60:
            return f"{seconds:.1f}秒"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}分{secs}秒"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            return f"{hours}小时{minutes}分{secs}秒"

    def run_single_paper(self, paper_id: str) -> Optional[Dict]:
        """处理单篇论文（按ID）"""
        try:
            logger.info(f"开始处理指定论文: {paper_id}")

            # 获取论文详情
            paper = self.paper_fetcher.get_paper_by_id(paper_id)
            if not paper:
                logger.error(f"未找到论文: {paper_id}")
                return None

            return self.process_single_paper(paper, 1)

        except Exception as e:
            logger.error(f"处理指定论文失败: {e}")
            return None

    def run_demo_mode(self) -> Optional[Dict]:
        """运行演示模式（使用模拟数据）"""
        try:
            logger.info("开始运行演示模式")

            # 创建模拟论文数据
            from src.papers.models import Paper
            demo_paper = Paper(
                id="demo-paper-001",
                title="Demo: Advanced Neural Networks for AI Research",
                authors=["Demo Author", "AI Research Team"],
                description="This is a demonstration paper about advanced neural networks and their applications in artificial intelligence research. The paper explores novel architectures and training methodologies that push the boundaries of what's possible in machine learning. We introduce new techniques for optimization, regularization, and model scaling that enable training of larger and more capable neural networks.",
                paper_url="https://example.com/demo-paper",
                model_url="https://huggingface.co/demo/model",
                likes=999,
                downloads=5000,
                tags=["neural-networks", "deep-learning", "ai-research", "transformers"],
                language="en"
            )

            # 设置目录
            demo_dir = os.path.join(config.temp_dir, "demo")
            os.makedirs(demo_dir, exist_ok=True)

            # 处理论文
            result = self.process_single_paper(demo_paper, 1)

            if result:
                logger.info("演示模式执行成功")
                return result
            else:
                logger.error("演示模式执行失败")
                return None

        except Exception as e:
            logger.error(f"演示模式执行失败: {e}")
            logger.error(traceback.format_exc())
            return None


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='论文视频自动生成系统')
    parser.add_argument('--max-papers', type=int, default=1, help='最大处理论文数')
    parser.add_argument('--paper-id', type=str, help='处理指定ID的论文')
    parser.add_argument('--force-refresh', action='store_true', help='强制刷新缓存')
    parser.add_argument('--test-mode', action='store_true', help='测试模式（只处理1篇论文）')
    parser.add_argument('--demo-mode', action='store_true', help='演示模式（使用模拟数据）')
    parser.add_argument('--use-slides', action='store_true', help='强制使用Slide生成系统')
    parser.add_argument('--no-slides', action='store_true', help='禁用Slide生成系统，使用传统图片生成')
    parser.add_argument('--upload', action='store_true', help='强制启用自动上传到Bilibili')
    parser.add_argument('--no-upload', action='store_true', help='禁用自动上传，仅生成视频文件')
    parser.add_argument(
        '--slide-provider',
        type=str,
        choices=['legacy', 'local_a2a', 'external_http', 'multiagent_local'],
        default='legacy',
        help='选择Slide内容生成策略',
    )
    parser.add_argument(
        '--enable-slide-qc',
        action='store_true',
        help='启用Slide渲染前的质量检查',
    )
    parser.add_argument(
        '--slide-qc-retries',
        type=int,
        default=3,
        help='Slide质量检查失败后的最大重试次数',
    )
    parser.add_argument(
        '--max-parallel-research',
        type=int,
        default=4,
        help='多Agent内容生成模式下的最大并发Research Agent数量',
    )
    # External MultiAgentPPT provider options
    parser.add_argument(
        '--external-slide-api-base',
        type=str,
        help='MultiAgentPPT 兼容服务的 Base URL，例如 https://api.example.com',
    )
    parser.add_argument(
        '--external-slide-api-key',
        type=str,
        help='调用外部服务的 API Key（可选）',
    )
    parser.add_argument(
        '--external-timeout-seconds',
        type=int,
        default=120,
        help='外部服务调用超时时间（秒）',
    )
    parser.add_argument(
        '--external-request-headers',
        type=str,
        help='额外的HTTP请求头，JSON字符串，例如 {"X-Org": "demo"}',
    )
    parser.add_argument(
        '--mcp-enabled',
        action='store_true',
        help='启用本地多Agent流程中的 MCP 工具调用（如可用）',
    )
    parser.add_argument(
        '--search-api-url',
        type=str,
        help='MCP web search 工具的HTTP API地址（可选）',
    )
    parser.add_argument(
        '--search-api-key',
        type=str,
        help='MCP web search 工具的API Key（可选）',
    )
    parser.add_argument(
        '--plantuml-server-url',
        type=str,
        help='PlantUML 服务器URL（可选），例如 https://www.plantuml.com/plantuml',
    )
    parser.add_argument(
        '--export-pptx',
        action='store_true',
        help='在生成slides后导出为PPTX文件',
    )

    args = parser.parse_args()

    try:
        # 处理命令行参数对slide系统的影响
        if args.use_slides and args.no_slides:
            logger.error("不能同时指定 --use-slides 和 --no-slides")
            sys.exit(1)

        # 处理命令行参数对上传功能的影响
        if args.upload and args.no_upload:
            logger.error("不能同时指定 --upload 和 --no-upload")
            sys.exit(1)

        # 临时修改配置以响应命令行参数
        original_use_slide_system = config.use_slide_system
        original_bilibili_enabled = config.bilibili_enabled

        if args.use_slides:
            config.use_slide_system = True
            logger.info("命令行参数: 强制启用Slide系统")
        elif args.no_slides:
            config.use_slide_system = False
            logger.info("命令行参数: 禁用Slide系统")

        if args.upload:
            config.bilibili_enabled = True
            logger.info("命令行参数: 强制启用自动上传到Bilibili")
        elif args.no_upload:
            config.bilibili_enabled = False
            logger.info("命令行参数: 禁用自动上传，仅生成视频文件")

        # 初始化流水线
        runtime_options = {
            'slide_provider': args.slide_provider,
            'enable_slide_qc': args.enable_slide_qc,
            'slide_qc_retries': args.slide_qc_retries,
            'max_parallel_research': args.max_parallel_research,
        }

        # Inject external provider options if provided
        if args.external_slide_api_base:
            runtime_options['external_slide_api_base'] = args.external_slide_api_base
        if args.external_slide_api_key:
            runtime_options['external_slide_api_key'] = args.external_slide_api_key
        if args.external_timeout_seconds is not None:
            runtime_options['external_timeout_seconds'] = args.external_timeout_seconds
        if args.external_request_headers:
            try:
                import json as _json
                runtime_options['external_request_headers'] = _json.loads(args.external_request_headers)
            except Exception:
                logger.warning('external-request-headers 解析失败，需为JSON字符串，已忽略')

        if args.mcp_enabled:
            runtime_options['mcp_enabled'] = True
        if args.search_api_url:
            runtime_options['search_api_url'] = args.search_api_url
        if args.search_api_key:
            runtime_options['search_api_key'] = args.search_api_key
        if args.plantuml_server_url:
            runtime_options['plantuml_server_url'] = args.plantuml_server_url
        if args.export_pptx:
            runtime_options['export_pptx'] = True

        pipeline = PaperVideoPipeline(runtime_options=runtime_options)

        if args.demo_mode:
            # 运行演示模式
            logger.info("运行演示模式（使用模拟数据）")
            result = pipeline.run_demo_mode()
            if result:
                logger.info("演示模式执行成功")
                logger.info(f"视频文件: {result.get('video_path')}")
            else:
                logger.error("演示模式执行失败")
                sys.exit(1)
        elif args.paper_id:
            # 处理指定论文
            logger.info(f"处理指定论文: {args.paper_id}")
            result = pipeline.run_single_paper(args.paper_id)
            if result:
                logger.info("论文处理成功")
                logger.info(f"视频文件: {result.get('video_path')}")
            else:
                logger.error("论文处理失败")
                sys.exit(1)
        else:
            # 运行完整流水线
            max_papers = 1 if args.test_mode else args.max_papers
            logger.info(f"运行完整流水线，最大论文数: {max_papers}")
            results = pipeline.run_complete_pipeline(max_papers)

            if results:
                logger.info("流水线执行成功")
                for i, result in enumerate(results):
                    logger.info(f"  视频 {i+1}: {result.get('video_path', 'Unknown')}")
            else:
                logger.error("流水线执行失败")
                sys.exit(1)

    except KeyboardInterrupt:
        logger.info("用户中断执行")
        sys.exit(0)
    except Exception as e:
        logger.error(f"程序执行失败: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)
    finally:
        # 恢复原始配置
        if 'original_use_slide_system' in locals():
            config.use_slide_system = original_use_slide_system
        if 'original_bilibili_enabled' in locals():
            config.bilibili_enabled = original_bilibili_enabled



# ============================================================================
# 模块级函数入口（供 api_main.py 调用）
# ============================================================================

def run_demo_mode(log=None) -> Dict:
    """
    运行演示模式（使用模拟数据）

    Args:
        log: 日志回调函数

    Returns:
        Dict: 包含 video/subtitle/slides/pptx 路径的字典
    """
    try:
        pipeline = PaperVideoPipeline()
        result = pipeline.run_demo_mode()
        if result:
            return {
                'video': result.get('video_path'),
                'subtitle': result.get('subtitle_path'),
                'slides': [asset['path'] for asset in result.get('image_assets', []) if asset.get('is_slide')],
                'pptx': None,
            }
        return {}
    except Exception as e:
        if log:
            log(f"ERROR: {e}")
        raise


def run_complete_pipeline(max_papers: int = 1, log=None) -> Dict:
    """
    运行完整流水线

    Args:
        max_papers: 最大论文数
        log: 日志回调函数

    Returns:
        Dict: 包含 video/subtitle/slides/pptx 路径的字典
    """
    try:
        pipeline = PaperVideoPipeline()
        results = pipeline.run_complete_pipeline(max_papers=max_papers)
        if results and len(results) > 0:
            # 返回第一篇论文的结果
            result = results[0]
            return {
                'video': result.get('video_path'),
                'subtitle': result.get('subtitle_path'),
                'slides': [asset['path'] for asset in result.get('image_assets', []) if asset.get('is_slide')],
                'pptx': None,
            }
        return {}
    except Exception as e:
        if log:
            log(f"ERROR: {e}")
        raise


def process_single_paper(paper_id: str, log=None) -> Dict:
    """
    处理单篇论文

    Args:
        paper_id: 论文ID
        log: 日志回调函数

    Returns:
        Dict: 包含 video/subtitle/slides/pptx 路径的字典
    """
    try:
        pipeline = PaperVideoPipeline()
        result = pipeline.run_single_paper(paper_id)
        if result:
            return {
                'video': result.get('video_path'),
                'subtitle': result.get('subtitle_path'),
                'slides': [asset['path'] for asset in result.get('image_assets', []) if asset.get('is_slide')],
                'pptx': None,
            }
        return {}
    except Exception as e:
        if log:
            log(f"ERROR: {e}")
        raise


def run_slides_only(paper_id: str, log=None) -> Dict:
    """
    仅生成slides（不生成视频）

    Args:
        paper_id: 论文ID
        log: 日志回调函数

    Returns:
        Dict: 包含 slides 路径的字典
    """
    try:
        # 简化实现：调用 process_single_paper 但仅返回 slides
        result = process_single_paper(paper_id, log=log)
        return {
            'video': None,
            'subtitle': None,
            'slides': result.get('slides', []),
            'pptx': None,
        }
    except Exception as e:
        if log:
            log(f"ERROR: {e}")
        raise


if __name__ == "__main__":
    main()