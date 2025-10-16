#!/usr/bin/env python3
"""
DashScope TTS 诊断测试脚本
测试不同的模型和音色组合
"""
import os
import sys
from pathlib import Path

# 加载 .env 文件
env_path = Path(".env")
if env_path.exists():
    print(f"✓ 加载 .env 文件: {env_path}")
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()
else:
    print(f"⚠ 未找到 .env 文件: {env_path}")

# 获取 API Key
api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("TTS_API_KEY")
if not api_key:
    print("❌ 错误：DASHSCOPE_API_KEY 未配置")
    sys.exit(1)

print(f"✓ API Key: {api_key[:10]}...{api_key[-4:]}")

# 测试文本
test_text = "这是一个测试语音合成的句子，用于验证DashScope TTS服务是否正常工作。"

# 测试不同的模型和音色组合
test_configs = [
    # 当前配置
    {"model": "cosyvoice-v2", "voice": "longxiaochun_v2", "name": "当前配置 (v2)"},
    # 备选配置
    {"model": "cosyvoice-v1", "voice": "longxiaochun", "name": "备选配置 (v1)"},
    {"model": "sambert-zhichu-v1", "voice": "zhichu", "name": "备选配置 (sambert)"},
]

print("\n" + "="*60)
print("开始测试 DashScope TTS API")
print("="*60)

try:
    import dashscope
    from dashscope.audio.tts_v2 import SpeechSynthesizer
    print("✓ dashscope SDK 已安装")
except ImportError as e:
    print(f"❌ 错误：dashscope SDK 未安装")
    print(f"   请运行: pip install dashscope")
    sys.exit(1)

# 设置 API Key
dashscope.api_key = api_key

for i, config in enumerate(test_configs, 1):
    print(f"\n{'='*60}")
    print(f"测试 {i}/{len(test_configs)}: {config['name']}")
    print(f"  模型: {config['model']}")
    print(f"  音色: {config['voice']}")
    print(f"{'='*60}")
    
    try:
        synthesizer = SpeechSynthesizer(model=config['model'], voice=config['voice'])
        print("  ✓ SpeechSynthesizer 初始化成功")
        
        print(f"  → 调用 TTS API...")
        audio_bytes = synthesizer.call(test_text)
        
        if audio_bytes:
            print(f"  ✓ 成功生成音频！")
            print(f"    音频大小: {len(audio_bytes)} 字节")
            
            # 保存测试音频
            output_path = f"test_tts_{config['model']}_{config['voice']}.mp3"
            with open(output_path, 'wb') as f:
                f.write(audio_bytes)
            print(f"    已保存到: {output_path}")
            
            print(f"\n  ✅ 配置可用！推荐使用此配置。")
            break
        else:
            print(f"  ❌ API 返回空音频")
            
    except Exception as e:
        error_msg = str(e)
        print(f"  ❌ 错误: {error_msg}")
        
        # 分析错误类型
        error_lower = error_msg.lower()
        if "arrearage" in error_lower or "account" in error_lower:
            print(f"     → 账户问题（欠费或权限不足）")
        elif "not found" in error_lower or "invalid" in error_lower:
            print(f"     → 模型或音色不存在")
        elif "rate" in error_lower or "429" in error_lower:
            print(f"     → API 限流")
        elif "ssl" in error_lower or "connection" in error_lower:
            print(f"     → 网络连接问题")
        else:
            print(f"     → 未知错误类型")

print("\n" + "="*60)
print("测试完成")
print("="*60)

