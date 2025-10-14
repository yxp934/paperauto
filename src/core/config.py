"""
配置管理模块
从环境变量和默认值加载配置
"""
import os
from pathlib import Path
from typing import Optional


class Config:
    """全局配置类"""
    
    def __init__(self):
        # API配置
        self.llm_api_url = os.getenv("LLM_API_URL", "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent")
        self.llm_api_key = os.getenv("LLM_API_KEY", "")
        self.llm_model = os.getenv("LLM_MODEL", "gemini-2.5-pro")
        
        self.image_api_url = os.getenv("IMAGE_API_URL", "https://api-inference.modelscope.cn/v1/images/generations")
        self.image_api_key = os.getenv("IMAGE_API_KEY", "")
        self.image_model = os.getenv("IMAGE_MODEL", "MusePublic/Qwen-image")
        
        self.tts_api_url = os.getenv("TTS_API_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions")
        self.tts_api_key = os.getenv("TTS_API_KEY", "")
        self.dashscope_api_key = os.getenv("DASHSCOPE_API_KEY", "")
        
        self.huggingface_api_key = os.getenv("HUGGINGFACE_API_KEY", "")
        
        # 目录配置
        self.output_dir = Path(os.getenv("OUTPUT_DIR", "./output"))
        self.temp_dir = Path(os.getenv("TEMP_DIR", "./temp"))
        self.cache_dir = self.temp_dir / "cache"
        
        # Slide系统配置
        self.slide_output_dir = self.output_dir / "slides"
        self.slide_temp_dir = self.temp_dir / "slides"
        self.slide_cache_dir = self.cache_dir / "slides"
        
        # 日志配置
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        
        # 流水线配置
        self.max_papers = int(os.getenv("MAX_PAPERS", "1"))
        self.use_slide_system = os.getenv("USE_SLIDE_SYSTEM", "true").lower() == "true"
        
        # Slide系统高级配置
        self.slide_max_workers = int(os.getenv("SLIDE_MAX_WORKERS", "4"))
        self.slide_parallel_enabled = os.getenv("SLIDE_PARALLEL_ENABLED", "true").lower() == "true"
        self.slide_cache_enabled = os.getenv("SLIDE_CACHE_ENABLED", "true").lower() == "true"
        self.slide_timeout = int(os.getenv("SLIDE_TIMEOUT", "3600"))
        self.slide_retry_attempts = int(os.getenv("SLIDE_RETRY_ATTEMPTS", "3"))
        self.slide_resolution = tuple(map(int, os.getenv("SLIDE_RESOLUTION", "1920,1080").split(",")))
        self.slide_format = os.getenv("SLIDE_FORMAT", "PNG")
        self.slide_quality = int(os.getenv("SLIDE_QUALITY", "95"))
        
        # Bilibili上传配置
        self.bilibili_enabled = os.getenv("BILIBILI_ENABLED", "false").lower() == "true"
        self.bilibili_debug_port = int(os.getenv("BILIBILI_DEBUG_PORT", "9222"))
        self.bilibili_default_category = os.getenv("BILIBILI_DEFAULT_CATEGORY", "科技")
        self.bilibili_default_tags = os.getenv("BILIBILI_DEFAULT_TAGS", "AI,论文解读,科技").split(",")
        
        # PPTX导出配置
        self.export_pptx_default = os.getenv("EXPORT_PPTX_DEFAULT", "false").lower() == "true"
    
    def ensure_directories(self):
        """确保所有必要的目录存在"""
        for directory in [
            self.output_dir,
            self.temp_dir,
            self.cache_dir,
            self.slide_output_dir,
            self.slide_temp_dir,
            self.slide_cache_dir,
            self.output_dir / "videos",
            self.temp_dir / "audio",
            self.temp_dir / "images",
            self.temp_dir / "video",
        ]:
            directory.mkdir(parents=True, exist_ok=True)


# 全局配置实例
config = Config()

