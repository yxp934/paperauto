#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
讯飞 TTS WebSocket API 测试脚本
根据官方文档: https://www.xfyun.cn/doc/tts/online_tts/API.html
"""

import os
import sys
import json
import base64
import hmac
import hashlib
import time
from datetime import datetime
from urllib.parse import urlencode
from wsgiref.handlers import format_date_time
from time import mktime
import websocket
import wave

# 从环境变量读取配置
from dotenv import load_dotenv
load_dotenv()

# 讯飞 TTS 配置
WEBSOCKET_URL = os.getenv("XFYUN_WEBSOCKET_URL", "wss://tts-api.xfyun.cn/v2/tts")
API_KEY = os.getenv("XFYUN_API_KEY")
API_SECRET = os.getenv("XFYUN_API_SECRET")
APPID = os.getenv("XFYUN_APPID")

print("=" * 80)
print("讯飞 TTS WebSocket API 测试")
print("=" * 80)
print(f"WebSocket URL: {WEBSOCKET_URL}")
print(f"API Key: {API_KEY[:10]}..." if API_KEY else "API Key: None")
print(f"API Secret: {API_SECRET[:10]}..." if API_SECRET else "API Secret: None")
print(f"APPID: {APPID}")
print()

if not all([API_KEY, API_SECRET, APPID]):
    print("❌ 错误：缺少必要的配置参数！")
    print("请在 .env 文件中添加以下配置：")
    print("  XFYUN_APPID=你的APPID")
    print("  api_key=你的APIKey")
    print("  api_secret=你的APISecret")
    sys.exit(1)


class XfyunTTS:
    """讯飞 TTS WebSocket 客户端"""
    
    def __init__(self, appid, api_key, api_secret):
        self.appid = appid
        self.api_key = api_key
        self.api_secret = api_secret
        self.ws = None
        self.audio_data = []
        
    def create_url(self):
        """
        生成鉴权 URL
        根据官方文档的鉴权方法
        """
        # 解析 WebSocket URL
        url = WEBSOCKET_URL
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
                print(f"❌ 错误: code={code}, message={data.get('message')}")
                ws.close()
                return
            
            # 提取音频数据
            audio = data.get("data", {}).get("audio")
            status = data.get("data", {}).get("status")
            
            if audio:
                # base64 解码音频数据
                audio_bytes = base64.b64decode(audio)
                self.audio_data.append(audio_bytes)
                print(f"✅ 接收音频数据: {len(audio_bytes)} 字节, status={status}")
            
            # status=2 表示合成结束
            if status == 2:
                print("✅ 音频合成完成！")
                ws.close()
                
        except Exception as e:
            print(f"❌ 处理消息时出错: {e}")
            ws.close()
    
    def on_error(self, ws, error):
        """错误回调"""
        print(f"❌ WebSocket 错误: {error}")
    
    def on_close(self, ws, close_status_code, close_msg):
        """关闭连接回调"""
        print(f"🔌 WebSocket 连接已关闭")
        if close_status_code:
            print(f"   状态码: {close_status_code}")
        if close_msg:
            print(f"   消息: {close_msg}")
    
    def on_open(self, ws):
        """连接建立回调"""
        print("✅ WebSocket 连接已建立")
        
        # 发送合成请求
        def send_request():
            # 测试文本
            text = "这是一个讯飞语音合成测试，用于验证WebSocket API是否正常工作。"
            
            # 构建请求参数
            request_data = {
                "common": {
                    "app_id": self.appid
                },
                "business": {
                    "aue": "raw",  # 音频编码: raw (PCM)
                    "auf": "audio/L16;rate=16000",  # 音频采样率: 16k
                    "vcn": "xiaoyan",  # 发音人: 小燕（中文女声）
                    "speed": 50,  # 语速
                    "volume": 50,  # 音量
                    "pitch": 50,  # 音高
                    "tte": "UTF8"  # 文本编码
                },
                "data": {
                    "status": 2,  # 固定为2（一次性传输）
                    "text": base64.b64encode(text.encode('utf-8')).decode('utf-8')
                }
            }
            
            print(f"📤 发送合成请求:")
            print(f"   文本: {text}")
            print(f"   发音人: xiaoyan")
            print(f"   音频格式: PCM 16k")
            
            ws.send(json.dumps(request_data))
        
        send_request()
    
    def synthesize(self, text, output_file="test_xfyun_output.wav"):
        """
        合成语音
        
        Args:
            text: 要合成的文本
            output_file: 输出文件路径
        """
        # 重置音频数据
        self.audio_data = []
        
        # 创建鉴权 URL
        auth_url = self.create_url()
        print(f"🔗 鉴权 URL 已生成")
        print()
        
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
        print("🚀 开始连接 WebSocket...")
        self.ws.run_forever()
        
        # 保存音频文件
        if self.audio_data:
            print()
            print(f"💾 保存音频文件: {output_file}")
            
            # 合并所有音频数据
            audio_bytes = b''.join(self.audio_data)
            
            # 保存为 WAV 文件
            with wave.open(output_file, 'wb') as wf:
                wf.setnchannels(1)  # 单声道
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(16000)  # 16kHz
                wf.writeframes(audio_bytes)
            
            file_size = os.path.getsize(output_file)
            print(f"✅ 音频文件已保存: {file_size} 字节")
            print(f"   文件路径: {os.path.abspath(output_file)}")
            
            return output_file
        else:
            print("❌ 没有接收到音频数据")
            return None


def main():
    """主函数"""
    print("开始测试讯飞 TTS WebSocket API...")
    print()
    
    # 创建 TTS 客户端
    tts = XfyunTTS(
        appid=APPID,
        api_key=API_KEY,
        api_secret=API_SECRET
    )
    
    # 测试文本
    test_text = "这是一个讯飞语音合成测试，用于验证WebSocket API是否正常工作。"
    
    # 合成语音
    output_file = tts.synthesize(test_text)
    
    print()
    print("=" * 80)
    if output_file and os.path.exists(output_file):
        print("✅ 测试成功！")
        print(f"   音频文件: {output_file}")
        print(f"   文件大小: {os.path.getsize(output_file)} 字节")
    else:
        print("❌ 测试失败！")
    print("=" * 80)


if __name__ == "__main__":
    main()

