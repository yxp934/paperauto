#!/usr/bin/env python3
"""
快速测试脚本 - 验证核心模块是否正常工作
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# 优先加载 .env（无第三方依赖）
from src.utils.helpers import load_env_from_file
load_env_from_file()

print("=" * 80)
print("快速测试 - 核心模块导入与基本功能")
print("=" * 80)

# 测试 1: 配置模块
print("\n[1/8] 测试配置模块...")
try:
    from src.core.config import config
    config.ensure_directories()
    print(f"  ✓ 配置加载成功")
    print(f"    - OUTPUT_DIR: {config.output_dir}")
    print(f"    - LLM_API_KEY: {'已配置' if config.llm_api_key else '未配置'}")
    print(f"    - DASHSCOPE_API_KEY: {'已配置' if config.dashscope_api_key else '未配置'}")
except Exception as e:
    print(f"  ✗ 失败: {e}")
    sys.exit(1)

# 测试 2: 论文获取
print("\n[2/8] 测试论文获取...")
try:
    from src.papers.fetch_papers import fetch_daily_papers
    papers = fetch_daily_papers(max_results=1)
    if papers:
        print(f"  ✓ 获取到 {len(papers)} 篇论文")
        print(f"    - 标题: {papers[0].title[:60]}...")
    else:
        print(f"  ⚠️  未获取到论文（可能是网络问题）")
except Exception as e:
    print(f"  ✗ 失败: {e}")

# 测试 3: LLM 客户端
print("\n[3/8] 测试 LLM 客户端...")
try:
    from src.utils.llm_client import LLMClient
    llm = LLMClient()
    
    # 测试论文结构分析
    test_paper = {
        "title": "Test Paper",
        "abstract": "This is a test abstract for testing purposes.",
        "authors": ["Test Author"],
        "arxiv_id": "0000.00000",
    }
    sections = llm.analyze_paper_structure(test_paper)
    print(f"  ✓ LLM 分析成功，生成 {len(sections)} 个章节")
    for i, sec in enumerate(sections[:3]):
        print(f"    - {sec['title']}")
except Exception as e:
    print(f"  ✗ 失败: {e}")

# 测试 4: Slide 计划
print("\n[4/8] 测试 Slide 计划生成...")
try:
    from src.slide.plan import plan_slides_for_section
    test_script = {
        "title": "Introduction",
        "bullets": ["Point 1", "Point 2", "Point 3"],
        "narration": "This is a test narration for the introduction section.",
    }
    plans = plan_slides_for_section(test_script)
    print(f"  ✓ 生成 {len(plans)} 页 Slide 计划")
    for i, plan in enumerate(plans):
        print(f"    - {plan.layout}: {plan.title}")
except Exception as e:
    print(f"  ✗ 失败: {e}")

# 测试 5: 图片生成（占位）
print("\n[5/8] 测试图片生成...")
try:
    from src.video.image_generator import ImageGenerator
    gen = ImageGenerator()
    img = gen.generate_fallback_image("Test Image", "Test Title")
    path = gen.save_temp_image(img)
    print(f"  ✓ 图片生成成功: {path}")
except Exception as e:
    print(f"  ✗ 失败: {e}")

# 测试 6: TTS（需要 API Key）
print("\n[6/8] 测试 TTS 音频生成...")
try:
    from src.video.tts_dashscope import generate_audio
    import os
    
    if os.getenv("DASHSCOPE_API_KEY"):
        audio_path, duration = generate_audio("这是一个测试音频。")
        print(f"  ✓ TTS 生成成功: {audio_path} ({duration:.2f}秒)")
    else:
        print(f"  ⚠️  DASHSCOPE_API_KEY 未配置，跳过 TTS 测试")
except Exception as e:
    print(f"  ⚠️  TTS 测试失败（可能是 API 问题）: {e}")

# 测试 7: 视频合成（需要 ffmpeg）
print("\n[7/8] 测试视频合成...")
try:
    import subprocess
    result = subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
    if result.returncode == 0:
        print(f"  ✓ FFmpeg 可用")
    else:
        print(f"  ✗ FFmpeg 不可用")
except Exception as e:
    print(f"  ✗ FFmpeg 检查失败: {e}")

# 测试 8: 主流水线入口
print("\n[8/8] 测试主流水线入口...")
try:
    from src.main import run_demo_mode, run_complete_pipeline, process_single_paper
    print(f"  ✓ 主流水线函数导入成功")
    print(f"    - run_demo_mode")
    print(f"    - run_complete_pipeline")
    print(f"    - process_single_paper")
except Exception as e:
    print(f"  ✗ 失败: {e}")

print("\n" + "=" * 80)
print("快速测试完成")
print("=" * 80)
print("\n提示: 运行完整测试请执行:")
print("  python test_pipeline_cli.py --mode demo")

