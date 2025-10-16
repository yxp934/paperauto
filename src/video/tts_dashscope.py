"""
DashScope TTS 模块
使用阿里云 DashScope SDK 的 qwen3-tts-flash 模型生成语音
"""
import os
import logging
import random
import subprocess
import threading
from typing import Tuple, List
from pathlib import Path

_TTS_LOCK = threading.Lock()

logger = logging.getLogger(__name__)


def generate_audio(text: str, output_dir: str = "temp/audio") -> Tuple[str, float]:
    """
    使用 DashScope TTS 生成音频

    Args:
        text: 要转换的文本（中文）
        output_dir: 输出目录

    Returns:
        Tuple[str, float]: (音频文件路径, 时长秒数)

    Raises:
        Exception: 如果 TTS 生成失败
    """
    # 确保输出目录存在
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # 获取 API Key
    api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("TTS_API_KEY")
    if not api_key:
        raise Exception("DASHSCOPE_API_KEY 未配置，无法生成 TTS 音频")

    # 检查文本长度
    if not text or len(text.strip()) < 5:
        raise Exception(f"文本过短，无法生成 TTS: {text}")

    try:
        # 输出文件路径
        output_path = os.path.join(output_dir, f"tts_{random.randint(10_000, 99_999)}.mp3")
        logger.info(f"调用 DashScope TTS 生成音频: {text[:50]}... ({len(text)}字)")

        # 允许通过环境变量配置模型与音色（优先使用 v2 以提升质量）
        model = os.getenv("TTS_MODEL", os.getenv("DASHSCOPE_TTS_MODEL", "cosyvoice-v2"))
        voice = os.getenv("TTS_VOICE", os.getenv("DASHSCOPE_TTS_VOICE", "longxiaochun_v2"))

        # 使用 DashScope Python SDK（推荐）
        try:
            import dashscope  # type: ignore
            from dashscope.audio.tts_v2 import SpeechSynthesizer  # type: ignore
        except Exception as imp_err:
            raise Exception(f"未安装 dashscope SDK，请先安装: pip install dashscope; 原因: {imp_err}")

        # 设置 API Key（如果未通过环境变量被 SDK 自动读取）
        try:
            if not getattr(dashscope, 'api_key', None):
                dashscope.api_key = api_key
        except Exception:
            dashscope.api_key = api_key

        synthesizer = SpeechSynthesizer(model=model, voice=voice)
        audio_bytes = None
        last_err = None
        max_attempts = 4  # total attempts
        for attempt in range(max_attempts):
            try:
                # serialize all TTS calls to avoid concurrent-session errors
                with _TTS_LOCK:
                    audio_bytes = synthesizer.call(text)
                if audio_bytes:
                    break
                raise RuntimeError("DashScope TTS returned empty audio bytes")
            except Exception as e:
                last_err = e
                msg = str(e)
                lower = msg.lower()
                # Retryable conditions: concurrency, rate limit, SSL/EOF/network
                retryable = ("already started" in lower) or ("already_started" in lower) or ("too many requests" in lower) or ("429" in lower) or ("ssl" in lower) or ("eof" in lower) or ("connection" in lower) or ("timeout" in lower)
                if attempt < max_attempts - 1 and retryable:
                    wait_seconds = 2 ** (attempt + 1)  # 2, 4, 8
                    logger.warning(f"[TTS] DashScope API call failed (attempt {attempt+1}/{max_attempts}): {msg[:200]}, retrying in {wait_seconds}s...")
                    try:
                        # Re-instantiate to clear bad session
                        synthesizer = SpeechSynthesizer(model=model, voice=voice)
                    except Exception:
                        pass
                    try:
                        import time as _t; _t.sleep(wait_seconds)
                    except Exception:
                        pass
                else:
                    logger.error(f"DashScope TTS 调用失败 (final): {msg}")
                    break
        if not audio_bytes:
            raise Exception(f"DashScope TTS 返回空音频或失败: {last_err}")

        with open(output_path, 'wb') as f:
            f.write(audio_bytes)

        duration = _get_audio_duration(output_path)
        logger.info(f"TTS 音频生成成功: {output_path} ({duration:.2f}秒)")
        return output_path, duration

    except Exception as e:
        error_msg = str(e)
        logger.error(f"DashScope TTS 生成失败: {error_msg}")

        # Always fallback to local TTS when DashScope fails
        # (DashScope account is in arrearage status)
        logger.warning(f"DashScope TTS 不可用（{error_msg[:100]}），尝试使用本地 TTS 回退...")
        try:
            return _generate_audio_local_fallback(text, output_dir)
        except Exception as fallback_err:
            logger.error(f"本地 TTS 回退也失败: {fallback_err}")
            raise Exception(f"DashScope TTS 失败且本地 TTS 回退失败: {error_msg}")


def generate_audio_for_sections(
    sections_scripts: List[dict],
    output_dir: str = "temp/audio"
) -> List[Tuple[str, float]]:
    """
    为多个章节生成 TTS 音频

    Args:
        sections_scripts: 章节脚本列表，每个包含 narration 字段
        output_dir: 输出目录

    Returns:
        List[Tuple[str, float]]: [(音频路径, 时长), ...]
    """
    results = []

    for i, script in enumerate(sections_scripts):
        narration = script.get("narration") or ""

        if not narration or len(narration.strip()) < 5:
            logger.warning(f"章节 {i+1} 旁白为空或过短，跳过")
            continue

        try:
            audio_path, duration = generate_audio(narration, output_dir)
            results.append((audio_path, duration))
        except Exception as e:
            logger.error(f"章节 {i+1} TTS 生成失败: {e}")
            # 不中断整个流程，继续处理下一个章节
            continue

    logger.info(f"共生成 {len(results)}/{len(sections_scripts)} 个章节的 TTS 音频")
    return results


def _get_audio_duration(audio_path: str) -> float:
    """
    使用 ffprobe 获取音频时长

    Args:
        audio_path: 音频文件路径

    Returns:
        float: 时长（秒）
    """
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        duration = float(result.stdout.strip())
        return duration
    except Exception as e:
        logger.warning(f"无法获取音频时长，使用估算值: {e}")
        # 回退：按字符数估算（中文约 3 字/秒）
        # 这里假设音频文件对应的文本长度未知，返回默认值
        return 5.0


# ============================================================================
# 兼容旧版 TTSGenerator 接口
# ============================================================================

class DashScopeTTSGenerator:
    """DashScope TTS 生成器（兼容旧接口）"""

    def __init__(self):
        self.output_dir = "temp/audio"
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)

    def synthesize_segments(self, texts: List[str], log=None) -> List[Tuple[str, float]]:
        """
        批量生成 TTS 音频

        Args:
            texts: 文本列表
            log: 日志回调函数

        Returns:
            List[Tuple[str, float]]: [(音频路径, 时长), ...]
        """
        results = []

        for i, text in enumerate(texts):
            if log:
                log(f"生成 TTS 音频 {i+1}/{len(texts)}: {text[:30]}...")

            try:
                audio_path, duration = generate_audio(text, self.output_dir)
                results.append((audio_path, duration))
            except Exception as e:
                if log:
                    log(f"ERROR: TTS 生成失败: {e}")
                logger.error(f"TTS 生成失败: {e}")
                # 不使用回退，直接失败
                raise

        return results

    def generate_audio_for_paper(self, sections: List[dict], log=None) -> List[Tuple[str, float]]:
        """
        为论文章节生成 TTS 音频

        Args:
            sections: 章节列表，每个包含 narration 字段
            log: 日志回调函数

        Returns:
            List[Tuple[str, float]]: [(音频路径, 时长), ...]
        """
        texts = [s.get("narration") or "" for s in sections]
        texts = [t for t in texts if t.strip()]  # 过滤空文本

        if not texts:
            raise Exception("没有有效的旁白文本可生成 TTS")

        return self.synthesize_segments(texts, log=log)


def _generate_audio_local_fallback(text: str, output_dir: str = "temp/audio") -> Tuple[str, float]:
    """
    本地 TTS 回退方案（使用 macOS say 命令）

    Args:
        text: 要转换的文本
        output_dir: 输出目录

    Returns:
        Tuple[str, float]: (音频文件路径, 时长秒数)
    """
    import platform
    import wave

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # 检查是否为 macOS
    if platform.system() != "Darwin":
        raise Exception("本地 TTS 回退仅支持 macOS 系统")

    # 生成临时 AIFF 文件
    aiff_path = os.path.join(output_dir, f"tts_local_{random.randint(10_000, 99_999)}.aiff")
    mp3_path = Path(aiff_path).with_suffix('.mp3')

    logger.info(f"使用本地 TTS (say) 生成音频: {text[:50]}... ({len(text)}字)")

    try:
        # 使用 macOS say 命令生成 AIFF 音频
        # -v Tingting 是中文女声（注意：没有连字符）
        subprocess.run(
            ['say', '-v', 'Tingting', '-o', aiff_path, text],
            check=True,
            capture_output=True,
            timeout=60
        )

        # 转换 AIFF 到 MP3
        subprocess.run(
            ['ffmpeg', '-y', '-i', aiff_path, '-ar', '44100', '-ac', '2', '-b:a', '128k', str(mp3_path)],
            check=True,
            capture_output=True,
            timeout=60
        )

        # 删除临时 AIFF 文件
        try:
            os.remove(aiff_path)
        except Exception:
            pass

        # 获取音频时长
        duration = _get_audio_duration(str(mp3_path))
        logger.info(f"本地 TTS 音频生成成功: {mp3_path} ({duration:.2f}秒)")

        return str(mp3_path), duration

    except subprocess.TimeoutExpired:
        raise Exception("本地 TTS 生成超时")
    except subprocess.CalledProcessError as e:
        raise Exception(f"本地 TTS 命令执行失败: {e.stderr.decode() if e.stderr else str(e)}")
    except Exception as e:
        raise Exception(f"本地 TTS 生成失败: {e}")

