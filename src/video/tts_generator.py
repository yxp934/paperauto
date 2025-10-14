import os
import subprocess
import wave
from typing import List, Tuple, Callable, Optional


class TTSGenerator:
    """
    Simple TTS wrapper.
    - On macOS (darwin): uses `say` to synthesize AIFF then converts to WAV via ffmpeg
    - Otherwise: falls back to generating a short sine-tone audio via ffmpeg
    Returns list of (wav_path, duration_seconds)
    """

    def __init__(self, voice: str | None = None) -> None:
        self.tmp_dir = os.path.join("temp", "audio")
        os.makedirs(self.tmp_dir, exist_ok=True)
        self.voice = self._pick_voice(voice or os.environ.get("TTS_VOICE") or "Ting-Ting")

    def _pick_voice(self, preferred: str) -> str:
        if not self._has_say():
            return preferred
        # Check if preferred exists; otherwise fallback to common voices or first available
        if self._voice_available(preferred):
            return preferred
        for cand in ["Samantha", "Alex", "Victoria", "Ting-Ting", "Mei-Jia"]:
            if self._voice_available(cand):
                return cand
        # Fallback to first listed voice
        try:
            out = subprocess.check_output(["say", "-v", "?"], text=True, stderr=subprocess.DEVNULL)
            first = (out.splitlines()[0].split()[0]) if out.splitlines() else preferred
            return first or preferred
        except Exception:
            return preferred

    def _voice_available(self, name: str) -> bool:
        try:
            out = subprocess.check_output(["say", "-v", "?"], text=True, stderr=subprocess.DEVNULL)
            names = [ln.split()[0] for ln in out.splitlines() if ln.strip()]
            return name in names
        except Exception:
            return False

    def synthesize_segments(self, texts: List[str], log: Optional[Callable[[str], None]] = None) -> List[Tuple[str, float]]:
        results: List[Tuple[str, float]] = []
        use_say = self._has_say()
        if log:
            if use_say:
                log(f"[tts] using macOS say voice={self.voice}")
            else:
                log("[tts] using ffmpeg tone fallback")
        for idx, t in enumerate(texts, start=1):
            t = (t or "").strip() or "空白内容"
            wav_path = os.path.join(self.tmp_dir, f"seg_{idx:02d}.wav")
            try:
                if use_say:
                    aiff_path = os.path.join(self.tmp_dir, f"seg_{idx:02d}.aiff")
                    txt_path = os.path.join(self.tmp_dir, f"seg_{idx:02d}.txt")
                    with open(txt_path, "w", encoding="utf-8") as tf:
                        tf.write(t)
                    cmd_say = ["say", "-v", self.voice, "-o", aiff_path, "-f", txt_path]
                    if log:
                        log(f"[tts] cmd: {' '.join(cmd_say)}")
                    subprocess.run(cmd_say, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    cmd_conv = ["ffmpeg", "-y", "-i", aiff_path, "-ar", "22050", "-ac", "1", wav_path]
                    if log:
                        log(f"[tts] cmd: {' '.join(cmd_conv)}")
                    subprocess.run(cmd_conv, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    try:
                        os.remove(aiff_path)
                        os.remove(txt_path)
                    except Exception:
                        pass
                else:
                    duration = max(1.2, min(8.0, len(t) / 16.0))
                    cmd_tone = ["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency=800:duration={duration}", wav_path]
                    if log:
                        log(f"[tts] cmd: {' '.join(cmd_tone)}")
                    subprocess.run(cmd_tone, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                dur = self._wav_duration(wav_path)
                results.append((wav_path, dur))
                if log:
                    log(f"[tts] synthesized segment {idx}/{len(texts)}: {wav_path} (duration: {dur:.2f}s)")
            except subprocess.CalledProcessError as e:
                if log:
                    log(f"[tts] ERROR executing TTS command (segment {idx}): {e}")
                raise
        return results

    def _has_say(self) -> bool:
        return os.uname().sysname.lower() == "darwin" and self._which("say") is not None

    @staticmethod
    def _which(cmd: str) -> str | None:
        from shutil import which
        return which(cmd)

    @staticmethod
    def _wav_duration(path: str) -> float:
        try:
            with wave.open(path, "rb") as w:
                frames = w.getnframes()
                rate = w.getframerate()
                return frames / float(rate or 1)
        except Exception:
            return 0.0

