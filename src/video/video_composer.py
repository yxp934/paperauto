import os
import subprocess
from typing import List, Callable, Optional


class VideoComposer:
    """
    Compose a narrated video by:
    1) Building a video from slide images with per-slide durations
    2) Concatenating WAV segments into a single WAV
    3) Muxing the audio with the video
    """

    def __init__(self) -> None:
        self.tmp_dir = os.path.join("temp", "video")
        os.makedirs(self.tmp_dir, exist_ok=True)

    def compose(self, slide_paths: List[str], audio_wavs: List[str], durations: List[float], out_path: str, log: Optional[Callable[[str], None]] = None) -> bool:
        if not slide_paths or not audio_wavs:
            if log:
                log("[video] compose aborted: missing slides or audio")
            return False
        # 1) Build concat list for images with durations
        # 优化：增加最小时长到 2.0 秒，避免过短
        list_file = os.path.join(self.tmp_dir, "slides.txt")
        with open(list_file, "w") as f:
            for p, d in zip(slide_paths, durations):
                f.write(f"file '{os.path.abspath(p)}'\n")
                f.write(f"duration {max(10.0, float(d))}\n")  # 最小 10.0 秒，保证时长充足
            # repeat last frame
            f.write(f"file '{os.path.abspath(slide_paths[-1])}'\n")
        video_track = os.path.join(self.tmp_dir, "slides_video.mp4")
        # 优化：使用 libx264 编码器，CRF 18 高质量，preset veryfast
        cmd_video = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file,
            "-vf", "scale=1920:1080,format=yuv420p",
            "-c:v", "libx264", "-crf", "14", "-preset", "medium",
            "-pix_fmt", "yuv420p", "-r", "30",
            "-movflags", "+faststart",
            video_track,
        ]
        if log:
            log(f"[video] cmd: {' '.join(cmd_video)}")
        try:
            subprocess.run(cmd_video, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            if log:
                log(f"[video] ERROR slides->video ffmpeg failed: {e}")
            raise

        # 2) Concat audio wavs (must be same format)
        audio_list = os.path.join(self.tmp_dir, "audio.txt")
        with open(audio_list, "w") as f:
            for a in audio_wavs:
                f.write(f"file '{os.path.abspath(a)}'\n")
        audio_track = os.path.join(self.tmp_dir, "audio_all.wav")
        cmd_audio = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", audio_list, "-c", "copy", audio_track]
        if log:
            log(f"[video] cmd: {' '.join(cmd_audio)}")
        try:
            subprocess.run(cmd_audio, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            if log:
                log(f"[video] ERROR audio concat ffmpeg failed: {e}")
            raise

        # 3) Mux
        # 优化：移除 -shortest，改用精准时间对齐
        # 策略：如果音频较短，用 apad 填充静音；如果视频较短，用 tpad 延长最后一帧
        # 这里简化实现：不使用 -shortest，让 FFmpeg 自动对齐到较长的轨道
        final_cmd = [
            "ffmpeg", "-y",
            "-i", video_track,
            "-i", audio_track,
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "256k",
            # 移除 -shortest，让视频和音频都完整保留
            out_path
        ]
        if log:
            log(f"[video] cmd: {' '.join(final_cmd)}")
        try:
            subprocess.run(final_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            if log:
                log(f"[video] ERROR mux ffmpeg failed: {e}")
            raise
        return True


# ============================================================================
# 步骤8: 统一视频合成函数
# ============================================================================

def compose_video(
    slides: List[str],
    audios: List[str],
    durations: List[float],
    output_path: str,
    log: Optional[Callable[[str], None]] = None
) -> bool:
    """
    合成视频（优化版）

    Args:
        slides: Slide 图片路径列表
        audios: 音频文件路径列表
        durations: 每页 Slide 的展示时长列表
        output_path: 输出视频路径
        log: 日志回调函数

    Returns:
        bool: 是否成功

    优化点:
        - 最小 Slide 时长 2.0 秒
        - 使用 libx264 -crf 18 高质量编码
        - 移除 -shortest，避免截断
        - 1920x1080, 30fps, yuv420p, AAC 音频
    """
    composer = VideoComposer()
    return composer.compose(slides, audios, durations, output_path, log=log)

