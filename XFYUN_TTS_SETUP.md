# 讯飞 TTS 配置指南

## 1. 获取讯飞 TTS 凭证

### 步骤 1：注册讯飞开放平台账号
1. 访问 [讯飞开放平台](https://www.xfyun.cn/)
2. 注册并登录账号

### 步骤 2：创建应用
1. 登录后，进入 [控制台](https://console.xfyun.cn/app/myapp)
2. 点击"创建新应用"
3. 填写应用信息（应用名称、应用类型等）
4. 创建成功后，会生成一个 **APPID**

### 步骤 3：开通语音合成服务
1. 在控制台中，找到你创建的应用
2. 点击"添加服务" → 选择"语音合成（流式版）"
3. 开通服务后，可以查看：
   - **APPID**: 应用的唯一标识
   - **APIKey**: API 密钥
   - **APISecret**: API 密钥

### 步骤 4：配置到 .env 文件
将获取到的凭证填写到 `.env` 文件中：

```bash
# TTS 讯飞 (XFyun)
XFYUN_WEBSOCKET_URL=wss://tts-api.xfyun.cn/v2/tts
XFYUN_API_KEY=你的APIKey（32位字符串）
XFYUN_API_SECRET=你的APISecret（32位字符串）
XFYUN_APPID=你的APPID（8位数字）
```

## 2. 测试配置

运行测试脚本验证配置是否正确：

```bash
python3 test_xfyun_tts.py
```

如果配置正确，会输出：
```
✅ WebSocket 连接已建立
✅ 接收音频数据: xxx 字节, status=1
✅ 音频合成完成！
✅ 音频文件已保存: xxx 字节
```

## 3. 常见问题

### Q1: 错误码 10313 - "your api_key does not belong to app_id"
**原因**: API_KEY 和 APPID 不匹配  
**解决**: 确保 API_KEY、API_SECRET 和 APPID 来自同一个应用

### Q2: 错误码 11200 - "auth no license"
**原因**: 没有权限或调用次数超限  
**解决**: 
- 检查是否已开通语音合成服务
- 检查是否使用了未授权的发音人
- 检查每日调用次数是否超限

### Q3: 错误码 401 - "HMAC signature does not match"
**原因**: 签名验证失败  
**解决**: 
- 检查 API_KEY 和 API_SECRET 是否正确
- 检查系统时间是否准确（允许误差 5 分钟）

## 4. 发音人列表

常用发音人（需在控制台开通）：

| 发音人 | 参数值 | 语言 | 性别 | 说明 |
|--------|--------|------|------|------|
| 小燕 | xiaoyan | 中文 | 女 | 标准女声 |
| 小宇 | xiaoyu | 中文 | 男 | 标准男声 |
| 小峰 | xiaofeng | 中文 | 男 | 磁性男声 |
| 小梅 | aisxmei | 中文 | 女 | 温柔女声 |
| 小莉 | aisxli | 中文 | 女 | 知性女声 |
| 小坤 | aisxkun | 中文 | 男 | 青年男声 |

更多发音人请访问：https://www.xfyun.cn/services/online_tts

## 5. 参考文档

- [讯飞 TTS WebAPI 文档](https://www.xfyun.cn/doc/tts/online_tts/API.html)
- [讯飞开放平台控制台](https://console.xfyun.cn/)
- [错误码查询](https://www.xfyun.cn/document/error-code)

