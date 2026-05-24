# Phase 3: Live2D 数字人 + TTS 语音合成

状态: 开发中 | 2026-05-24

## 架构

```
用户输入 → Vue Chat.vue
  → SSE /chat/stream → LLM 流式生成文本
  → 句级分割（检测 。！？~ 等标点）
  → 每句立即送 TTS (CosyVoice-300M) → WAV + 音素时间戳
  → SSE 交错推送: token 事件（逐字显示）+ audio 事件（播放+口型）
  → 前端 Live2DStage.vue: PIXI.js + pixi-live2d-display 渲染
```

## 关键决策

### TTS 流水线: 句级流式
- LLM 生成时实时检测句子边界（。！？~ 等）
- 每检测到完整句子，立即异步送 TTS
- 第一句音频在 LLM 生成完后 0.3-0.5x 实时内就绪
- 高频回复（"欢迎来到直播间~"等）永久缓存

### Live2D 模型: 先免费后自定义
- 阶段 A: Cubism SDK 示例模型（Haru/Hiyori）跑通技术链路
- 阶段 B: 替换为自己定制/购买的 Live2D 模型

### 口型同步: 音素驱动
- CosyVoice 返回每个音素的 start/end + phoneme
- 前端 requestAnimationFrame 根据音频当前时间定位音素
- 元音开口度 1.0，辅音 0.3
- 无音素时自然闭合 + 呼吸/眨眼/idle motion 持续

## 后端变更

```
backend/
  tts_engine.py    ← CosyVoice-300M 加载 + 句级推理 + 音素提取
  audio_cache.py   ← 高频音频 SHA256 永久缓存
  audio/           ← 生成 WAV 文件（.gitignore）

修改:
  config.py        ← TTS 模型路径、缓存配置、句子边界正则
  main.py          ← SSE 流增加 audio 事件，句子分割，TTS 异步调用
```

## 前端变更

```
frontend/src/
  components/Live2DStage.vue  ← PIXI + Live2D 渲染
  utils/lipSync.js            ← 口型同步

修改:
  views/Chat.vue              ← 集成 Live2D，audio SSE 事件处理
  package.json                ← pixi.js, pixi-live2d-display
```

## 灵魂引擎预留接口

```python
# backend/soul_engine.py (stub, Phase 5)
def get_agent_state() -> dict:
    """返回 { energy, mood_valence, mood_arousal, mood_dominance, expression }"""
    return { "energy": 0.8, "mood_valence": 0.6, ... }

def on_message_sent(user_msg: str) -> None: ...
def on_reply_generated(reply: str) -> None: ...
```

前端 `Live2DStage.vue` 暴露 `expression` 和 `energy` props，后续灵魂引擎接入零改动。

## SSE 事件流格式

```
data: {"token": "大"}
data: {"token": "家"}
data: {"token": "好"}
data: {"token": "！"}
data: {"audio": "/audio/chat_xxx_seg_0.wav", "phonemes": [...], "text": "大家好！"}
data: {"token": "今"}
data: {"token": "天"}
...
data: {"audio": "/audio/chat_xxx_seg_1.wav", "phonemes": [...], "text": "今天我们来..."}
...
data: {"done": true, "record_id": 42}
```

## 模型

| 模型 | 路径 | 大小 |
|------|------|------|
| CosyVoice-300M | models/tts/CosyVoice-300M/ | 2.1GB |
