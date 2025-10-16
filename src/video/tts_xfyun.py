"""
讯飞 TTS 模块
使用讯飞开放平台的 WebSocket API 生成语音
文档: https://www.xfyun.cn/doc/tts/online_tts/API.html
"""
import os
import logging
import random
import json
import base64
import hmac
import hashlib
import wave
import threading
from datetime import datetime
from urllib.parse import urlencode
from wsgiref.handlers import format_date_time
from time import mktime
from typing import Tuple, List
from pathlib import Path
import websocket

_TTS_LOCK = threading.Lock()

logger = logging.getLogger(__name__)


class XfyunTTSClient:
    """讯飞 TTS WebSocket 客户端"""
    
    def __init__(self, appid: str, api_key: str, api_secret: str):
        """
        初始化讯飞 TTS 客户端
        
        Args:
            appid: 讯飞应用 ID
            api_key: API Key
            api_secret: API Secret
        """
        self.appid = appid
        self.api_key = api_key
        self.api_secret = api_secret
        self.ws = None
        self.audio_data = []
        self.error_msg = None
        
    def create_url(self) -> str:
        """
        生成鉴权 URL
        
        Returns:
            str: 带鉴权参数的 WebSocket URL
        """
        # WebSocket 配置
        url = os.getenv("XFYUN_WEBSOCKET_URL", "wss://tts-api.xfyun.cn/v2/tts")
        host = "tts-api.xfyun.cn"
        path = "/v2/tts"
        
        # 生成 RFC1123 格式的时间戳
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))
        
        # 拼接签名原始字符串
        signature_origin = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"
        
        # 使用 hmac-sha256 算法结合 apiSecret 对 signature_origin 签名
        signature_sha = hmac.new(
            self.api_secret.encode('utf-8'),
            signature_origin.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        
        # base64 编码
        signature = base64.b64encode(signature_sha).decode('utf-8')
        
        # 构建 authorization 原始字符串
        authorization_origin = (
            f'api_key="{self.api_key}", '
            f'algorithm="hmac-sha256", '
            f'headers="host date request-line", '
            f'signature="{signature}"'
        )
        
        # base64 编码 authorization
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode('utf-8')
        
        # 构建完整的 URL
        params = {
            "host": host,
            "date": date,
            "authorization": authorization
        }
        
        auth_url = f"{url}?{urlencode(params)}"
        return auth_url
    
    def on_message(self, ws, message):
        """接收消息回调"""
        try:
            data = json.loads(message)
            code = data.get("code")
            
            if code != 0:
                self.error_msg = f"code={code}, message={data.get('message')}"
                logger.error(f"讯飞 TTS 错误: {self.error_msg}")
                ws.close()
                return
            
            # 提取音频数据
            audio = data.get("data", {}).get("audio")
            status = data.get("data", {}).get("status")
            
            if audio:
                # base64 解码音频数据
                audio_bytes = base64.b64decode(audio)
                self.audio_data.append(audio_bytes)
                logger.debug(f"接收音频数据: {len(audio_bytes)} 字节, status={status}")
            
            # status=2 表示合成结束
            if status == 2:
                logger.info(f"讯飞 TTS 合成完成，共接收 {len(self.audio_data)} 个音频包")
                ws.close()
                
        except Exception as e:
            self.error_msg = f"处理消息时出错: {e}"
            logger.error(self.error_msg)
            ws.close()
    
    def on_error(self, ws, error):
        """错误回调"""
        self.error_msg = f"WebSocket 错误: {error}"
        logger.error(self.error_msg)
    
    def on_close(self, ws, close_status_code, close_msg):
        """关闭连接回调"""
        logger.debug(f"WebSocket 连接已关闭")
    
    def on_open(self, ws):
        """连接建立回调"""
        logger.debug("WebSocket 连接已建立")
        
        # 发送合成请求
        def send_request():
            try:
                # 构建请求参数
                request_data = {
                    "common": {
                        "app_id": self.appid
                    },
                    "business": {
                        "aue": "raw",  # 音频编码: raw (PCM)
                        "auf": "audio/L16;rate=16000",  # 音频采样率: 16k
                        "vcn": os.getenv("XFYUN_VOICE", "xiaoyan"),  # 发音人
                        "speed": int(os.getenv("XFYUN_SPEED", "50")),  # 语速
                        "volume": int(os.getenv("XFYUN_VOLUME", "50")),  # 音量
                        "pitch": int(os.getenv("XFYUN_PITCH", "50")),  # 音高
                        "tte": "UTF8"  # 文本编码
                    },
                    "data": {
                        "status": 2,  # 固定为2（一次性传输）
                        "text": base64.b64encode(self.text.encode('utf-8')).decode('utf-8')
                    }
                }
                
                logger.debug(f"发送合成请求: {self.text[:50]}...")
                ws.send(json.dumps(request_data))
                
            except Exception as e:
                self.error_msg = f"发送请求时出错: {e}"
                logger.error(self.error_msg)
                ws.close()
        
        send_request()
    
    def synthesize(self, text: str) -> bytes:
        """
        合成语音
        
        Args:
            text: 要合成的文本
            
        Returns:
            bytes: PCM 音频数据
            
        Raises:
            Exception: 如果合成失败
        """
        # 检查文本长度（讯飞限制 < 8000 字节）
        text_bytes = text.encode('utf-8')
        if len(text_bytes) > 8000:
            raise Exception(f"文本过长（{len(text_bytes)} 字节），超过讯飞 TTS 限制（8000 字节）")
        
        # 重置状态
        self.text = text
        self.audio_data = []
        self.error_msg = None
        
        # 创建鉴权 URL
        auth_url = self.create_url()
        
        # 创建 WebSocket 连接
        websocket.enableTrace(False)
        self.ws = websocket.WebSocketApp(
            auth_url,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
            on_open=self.on_open
        )
        
        # 运行 WebSocket
        self.ws.run_forever()
        
        # 检查是否有错误
        if self.error_msg:
            raise Exception(f"讯飞 TTS 合成失败: {self.error_msg}")
        
        # 检查是否有音频数据
        if not self.audio_data:
            raise Exception("讯飞 TTS 未返回音频数据")
        
        # 合并所有音频数据
        audio_bytes = b''.join(self.audio_data)
        return audio_bytes


def generate_audio(text: str, output_dir: str = "temp/audio") -> Tuple[str, float]:
    """
    使用讯飞 TTS 生成音频
    
    Args:
        text: 要转换的文本（中文）
        output_dir: 输出目录
        
    Returns:
        Tuple[str, float]: (音频文件路径, 时长秒数)
        
    Raises:
        Exception: 如果 TTS 生成失败
    """
    with _TTS_LOCK:
        # 确保输出目录存在
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # 获取讯飞配置
        appid = os.getenv("XFYUN_APPID")
        api_key = os.getenv("XFYUN_API_KEY")
        api_secret = os.getenv("XFYUN_API_SECRET")
        
        if not all([appid, api_key, api_secret]):
            raise Exception("讯飞 TTS 配置不完整，请检查 XFYUN_APPID、XFYUN_API_KEY、XFYUN_API_SECRET")
        
        # 检查文本长度
        if not text or len(text.strip()) < 5:
            raise Exception(f"文本过短，无法生成 TTS: {text}")
        
        logger.info(f"调用讯飞 TTS 生成音频: {text[:50]}... ({len(text)}字)")
        
        try:
            # 创建 TTS 客户端
            client = XfyunTTSClient(appid, api_key, api_secret)
            
            # 合成语音
            audio_bytes = client.synthesize(text)
            
            # 生成输出文件路径
            output_wav = os.path.join(output_dir, f"tts_xfyun_{random.randint(10_000, 99_999)}.wav")
            
            # 保存为 WAV 文件
            with wave.open(output_wav, 'wb') as wf:
                wf.setnchannels(1)  # 单声道
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(16000)  # 16kHz
                wf.writeframes(audio_bytes)
            
            # 计算时长（秒）
            duration = len(audio_bytes) / (16000 * 2)  # 16kHz, 16-bit
            
            logger.info(f"讯飞 TTS 生成成功: {output_wav} ({duration:.2f}秒, {len(audio_bytes)}字节)")
            
            return output_wav, duration
            
        except Exception as e:
            logger.error(f"讯飞 TTS 生成失败: {e}")
            raise

