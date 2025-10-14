#!/usr/bin/env python3
"""
CLI 测试脚本 - 完整视频生成管线
支持三种模式：demo, single, complete
"""
import argparse
import sys
import os
import time
import subprocess
import json
from pathlib import Path
from typing import Dict, List, Optional

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent))

# 优先加载 .env（无第三方依赖）
from src.utils.helpers import load_env_from_file
load_env_from_file()

from src.papers.fetch_papers import fetch_daily_papers, get_paper_by_id
from src.utils.llm_client import LLMClient
from src.slide.plan import plan_slides_for_section, SlidePlan
from src.video.tts_dashscope import generate_audio
from src.video.video_composer import compose_video

# 简化：使用 PIL 直接生成 Slide
from PIL import Image, ImageDraw, ImageFont




def _render_simple_slide(title: str, bullets: List[str]) -> Image.Image:
    """使用 PIL 渲染简单的文本 Slide"""
    img = Image.new("RGB", (1920, 1080), color=(30, 40, 60))
    draw = ImageDraw.Draw(img)

    try:
        title_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 80)
        text_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 50)
    except:
        title_font = ImageFont.load_default()
        text_font = ImageFont.load_default()

    # 绘制标题
    draw.text((100, 100), title[:50], fill=(255, 255, 255), font=title_font)

    # 绘制要点
    y = 300
    for bullet in bullets[:5]:
        text = f"• {bullet[:80]}"
        draw.text((150, y), text, fill=(220, 220, 220), font=text_font)
        y += 120

    return img

def log_step(step: int, total: int, message: str):
    """打印步骤日志"""
    print(f"\n{'='*80}")
    print(f"[步骤 {step}/{total}] {message}")
    print(f"{'='*80}")


def validate_video(video_path: str) -> Dict:
    """
    使用 ffprobe 验证视频元信息

    Returns:
        Dict: 包含 duration/width/height/fps/codec 等信息
    """
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,codec_name",
            "-show_entries", "format=duration",
            "-of", "json",
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        data = json.loads(result.stdout)

        stream = data.get("streams", [{}])[0]
        format_info = data.get("format", {})

        # 解析帧率（格式为 "30/1"）
        fps_str = stream.get("r_frame_rate", "30/1")
        fps_parts = fps_str.split("/")
        fps = float(fps_parts[0]) / float(fps_parts[1]) if len(fps_parts) == 2 else 30.0

        return {
            "duration": float(format_info.get("duration", 0)),
            "width": int(stream.get("width", 0)),
            "height": int(stream.get("height", 0)),
            "fps": fps,
            "codec": stream.get("codec_name", "unknown"),
        }
    except Exception as e:
        print(f"⚠️  ffprobe 验证失败: {e}")
        return {}


def run_demo_mode():
    """运行演示模式"""
    log_step(0, 8, "演示模式 - 使用模拟数据")

    # 模拟论文数据
    paper = {
        "title": "Attention Is All You Need",
        "abstract": "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks...",
        "authors": ["Ashish Vaswani", "Noam Shazeer"],
        "arxiv_id": "1706.03762",
    }

    # 步骤 2: LLM 分析
    log_step(2, 8, "LLM 内容分析")
    llm_client = LLMClient()
    sections = llm_client.analyze_paper_structure(paper)
    print(f"✓ 生成 {len(sections)} 个章节")

    # 步骤 3: 脚本生成
    log_step(3, 8, "章节脚本生成")
    scripts = []
    for section in sections[:3]:  # 仅处理前3个章节（演示）
        script = llm_client.generate_section_script(section, paper)
        scripts.append(script)
        print(f"  - {script['title']}: {len(script['narration'])}字")

    # 步骤 4: Slide 计划
    log_step(4, 8, "Slide 计划生成")
    all_plans: List[SlidePlan] = []
    for script in scripts:
        plans = plan_slides_for_section(script)
        all_plans.extend(plans)
    print(f"✓ 生成 {len(all_plans)} 页 Slide 计划")

    # 步骤 5-6: 资源生成与 Slide 渲染
    log_step(5, 8, "资源生成与 Slide 渲染")
    slide_paths = []
    slide_dir = Path("temp/slides")
    slide_dir.mkdir(parents=True, exist_ok=True)

    for i, plan in enumerate(all_plans):
        print(f"  渲染 Slide {i+1}/{len(all_plans)}: {plan.title}")

        # 简化：使用 PIL 生成简单文本 Slide
        slide_img = _render_simple_slide(plan.title, plan.bullets or [plan.content or ""])
        slide_path = str(slide_dir / f"demo_slide_{i+1:03d}.png")
        slide_img.save(slide_path, "PNG")
        slide_paths.append(slide_path)

    print(f"✓ 渲染完成 {len(slide_paths)} 页 Slide")

    # 步骤 7: TTS 生成
    log_step(7, 8, "TTS 音频生成")
    audio_paths = []
    durations = []

    for i, script in enumerate(scripts):
        print(f"  生成 TTS {i+1}/{len(scripts)}: {script['title']}")
        try:
            audio_path, duration = generate_audio(script["narration"])
            audio_paths.append(audio_path)
            durations.append(duration)
            print(f"    ✓ {duration:.2f}秒")
        except Exception as e:
            print(f"    ✗ TTS 生成失败: {e}")
            return False

    # 步骤 8: 视频合成
    log_step(8, 8, "视频合成")
    output_dir = Path("output/videos")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(output_dir / f"demo_{int(time.time())}.mp4")

    # 确保 slide_paths 和 durations 长度匹配
    if len(slide_paths) > len(durations):
        # 为多余的 slide 分配平均时长
        avg_duration = sum(durations) / len(durations) if durations else 3.0
        durations.extend([avg_duration] * (len(slide_paths) - len(durations)))
    elif len(durations) > len(slide_paths):
        durations = durations[:len(slide_paths)]

    success = compose_video(slide_paths, audio_paths, durations, output_path)

    if success:
        print(f"\n✓ 视频生成成功: {output_path}")

        # 验证视频
        info = validate_video(output_path)
        if info:
            print(f"\n视频元信息:")
            print(f"  时长: {info['duration']:.2f}秒")
            print(f"  分辨率: {info['width']}x{info['height']}")
            print(f"  帧率: {info['fps']:.2f} fps")
            print(f"  编码: {info['codec']}")

            # 验收标准
            if info['duration'] >= 30:
                print(f"  ✓ 时长符合要求 (≥30秒)")
            else:
                print(f"  ⚠️  时长过短 (<30秒)")

            if info['width'] == 1920 and info['height'] == 1080:
                print(f"  ✓ 分辨率符合要求 (1920x1080)")
            else:
                print(f"  ⚠️  分辨率不符合要求")

        return True
    else:
        print(f"\n✗ 视频生成失败")
        return False


def run_single_mode(paper_id: str):
    """运行单篇论文模式（等同 demo，但基于真实论文）"""
    log_step(0, 8, f"单篇论文模式 - {paper_id}")

    # 步骤 1: 获取论文
    log_step(1, 8, "论文获取")
    paper = get_paper_by_id(paper_id)
    if not paper:
        print(f"✗ 无法获取论文: {paper_id}")
        return False

    print(f"✓ 论文: {paper.title}")
    if getattr(paper, 'authors', None):
        print(f"  作者: {', '.join(paper.authors[:3])}")

    # 步骤 2: LLM 分析
    log_step(2, 8, "LLM 内容分析")
    llm_client = LLMClient()
    sections = llm_client.analyze_paper_structure({
        "title": paper.title,
        "abstract": getattr(paper, 'abstract', ''),
        "authors": getattr(paper, 'authors', []),
        "arxiv_id": getattr(paper, 'arxiv_id', paper_id),
    })
    print(f"✓ 生成 {len(sections)} 个章节")

    # 步骤 3: 脚本生成（限制前3个章节以控制耗时）
    log_step(3, 8, "章节脚本生成")
    scripts = []
    for section in sections[:3]:
        script = llm_client.generate_section_script(section, {
            "title": paper.title,
            "abstract": getattr(paper, 'abstract', ''),
        })
        scripts.append(script)
        print(f"  - {script['title']}: {len(script['narration'])}字")

    # 步骤 4: Slide 计划
    log_step(4, 8, "Slide 计划生成")
    all_plans: List[SlidePlan] = []
    for script in scripts:
        plans = plan_slides_for_section(script)
        all_plans.extend(plans)
    print(f"✓ 生成 {len(all_plans)} 页 Slide 计划")

    # 步骤 5-6: 渲染
    log_step(5, 8, "资源生成与 Slide 渲染")
    slide_paths = []
    slide_dir = Path("temp/slides")
    slide_dir.mkdir(parents=True, exist_ok=True)
    for i, plan in enumerate(all_plans):
        print(f"  渲染 Slide {i+1}/{len(all_plans)}: {plan.title}")
        slide_img = _render_simple_slide(plan.title, plan.bullets or [plan.content or ""])
        slide_path = str(slide_dir / f"single_{paper_id}_slide_{i+1:03d}.png")
        slide_img.save(slide_path, "PNG")
        slide_paths.append(slide_path)
    print(f"✓ 渲染完成 {len(slide_paths)} 页 Slide")

    # 步骤 7: TTS
    log_step(7, 8, "TTS 音频生成")
    audio_paths, durations = [], []
    for i, script in enumerate(scripts):
        print(f"  生成 TTS {i+1}/{len(scripts)}: {script['title']}")
        try:
            audio_path, duration = generate_audio(script["narration"])
            audio_paths.append(audio_path)
            durations.append(duration)
            print(f"    ✓ {duration:.2f}秒")
        except Exception as e:
            print(f"    ✗ TTS 生成失败: {e}")
            return False

    # 步骤 8: 合成
    log_step(8, 8, "视频合成")
    output_dir = Path("output/videos")
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_id = str(paper_id).replace('/', '_')
    output_path = str(output_dir / f"single_{safe_id}_{int(time.time())}.mp4")

    if len(slide_paths) > len(durations):
        avg = sum(durations) / len(durations)
        durations.extend([avg] * (len(slide_paths) - len(durations)))
    elif len(durations) > len(slide_paths):
        durations = durations[:len(slide_paths)]

    success = compose_video(slide_paths, audio_paths, durations, output_path)
    if success:
        print(f"\n✓ 视频生成成功: {output_path}")
        info = validate_video(output_path)
        if info:
            print(f"\n视频元信息:")
            print(f"  时长: {info['duration']:.2f}秒")
            print(f"  分辨率: {info['width']}x{info['height']}")
            print(f"  帧率: {info['fps']:.2f} fps")
            print(f"  编码: {info['codec']}")
        return True
    print("\n✗ 视频生成失败")
    return False


def run_complete_mode(max_papers: int):
    """运行完整模式"""
    log_step(0, 8, f"完整模式 - 最多 {max_papers} 篇论文")

    # 步骤 1: 获取论文
    log_step(1, 8, "论文获取")
    papers = fetch_daily_papers(max_results=max_papers)

    if not papers:
        print("✗ 未获取到论文")
        return False

    print(f"✓ 获取 {len(papers)} 篇论文:")
    for i, paper in enumerate(papers):
        print(f"  {i+1}. {paper.title}")

    # 为每篇论文生成视频
    all_ok = True
    for i, paper in enumerate(papers, start=1):
        print(f"\n--- 处理第 {i}/{len(papers)} 篇 ---")
        ok = run_single_mode(paper.arxiv_id)
        all_ok = all_ok and ok
    return all_ok


def main():
    parser = argparse.ArgumentParser(description="视频生成管线 CLI 测试")
    parser.add_argument("--mode", choices=["demo", "single", "complete"], default="demo",
                        help="运行模式")
    parser.add_argument("--paper-id", help="论文 ID (single 模式)")
    parser.add_argument("--max-papers", type=int, default=3, help="最大论文数 (complete 模式)")

    args = parser.parse_args()

    print(f"\n{'='*80}")
    print(f"视频生成管线 CLI 测试")
    print(f"模式: {args.mode}")
    print(f"{'='*80}\n")

    start_time = time.time()

    try:
        if args.mode == "demo":
            success = run_demo_mode()
        elif args.mode == "single":
            if not args.paper_id:
                print("✗ single 模式需要 --paper-id 参数")
                return 1
            success = run_single_mode(args.paper_id)
        elif args.mode == "complete":
            success = run_complete_mode(args.max_papers)
        else:
            print(f"✗ 未知模式: {args.mode}")
            return 1

        elapsed = time.time() - start_time
        print(f"\n{'='*80}")
        print(f"总耗时: {elapsed:.2f}秒")
        print(f"结果: {'✓ 成功' if success else '✗ 失败'}")
        print(f"{'='*80}\n")

        return 0 if success else 1

    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
        return 130
    except Exception as e:
        print(f"\n\n✗ 异常: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

