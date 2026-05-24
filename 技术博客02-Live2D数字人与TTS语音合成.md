# 技术博客 02 — Live2D 数字人与 TTS 语音合成

> 本文档供学习参考，详解 Live2D 渲染、语音合成、口型同步、SSE 流式推送的全链路实现。

---

## 目录

1. [整体架构](#1-整体架构)
2. [CosyVoice-300M TTS 引擎](#2-cosyvoice-300m-tts-引擎)
3. [句级流式流水线](#3-句级流式流水线)
4. [SSE 事件流设计](#4-sse-事件流设计)
5. [Live2D 前端渲染](#5-live2d-前端渲染)
6. [口型同步：Web Audio API 音量驱动](#6-口型同步web-audio-api-音量驱动)
7. [GPU 加速与性能数据](#7-gpu-加速与性能数据)
8. [灵魂引擎预留接口](#8-灵魂引擎预留接口)
9. [踩坑记录](#9-踩坑记录)
10. [下一步](#10-下一步)

---

## 1. 整体架构

```
用户浏览器（Vue3）
  │ 输入文字
  ▼
POST /chat  ──►  FastAPI 后端
                    │
                    ├─► Qwen3-8B (4-bit) LLM 流式生成
                    │     │ token by token
                    │     ▼
                    │   SSE Event: {"token": "大"}, {"token": "家"}, ...
                    │
                    ├─► 完整回复收集完毕 → 按句号/感叹号/问号切句
                    │     │
                    │     ├─► 句1 → CosyVoice-300M (GPU fp16) → WAV
                    │     ├─► 句2 → CosyVoice-300M (GPU fp16) → WAV
                    │     └─► 句3 → ...
                    │     │
                    │     ▼
                    │   SSE Event: {"audio": {"wav_url":"/audio/tts_xxx.wav", "duration":1.5}}
                    │
                    ▼
                  SSE Event: {"done": true, "record_id": 42}

浏览器端：
  │
  ├─► 收到 token → Chat.vue 逐字渲染（打字机效果）
  ├─► 收到 audio → 加入播放队列 → Live2DStage.playAudio()
  │     └─► Audio.play() + LipSync 驱动口型
  └─► 收到 done → 对话完成
```

---

## 2. CosyVoice-300M TTS 引擎

**模型文件** (`models/tts/CosyVoice-300M/`，2.1GB):

| 文件 | 大小 | 用途 |
|------|------|------|
| `llm.pt` | 1.2GB | 文本→语音 token 的自回归 LLM |
| `flow.pt` | 400MB | Flow Matching 声学特征生成 |
| `hift.pt` | 78MB | HiFi-GAN 声码器（特征→波形） |
| `campplus.onnx` | 27MB | 说话人特征提取 |
| `speech_tokenizer_v1.onnx` | 498MB | 语音离散化 tokenizer |

**推理流程**:

```
输入文本 "大家好！"
  → wetext 中文前端（文本正则化、分词）
  → LLM 自回归生成语音 token 序列（50 fps，每 token=20ms）
  → Flow Matching 将离散 token 转为 Mel 频谱
  → HiFi-GAN 将频谱转为 22kHz 波形
  → 输出 WAV 文件
```

**零样本声音克隆**：CosyVoice 支持 zero-shot voice cloning——给一段 3-10 秒的参考音频 + 对应文本，模型就能模仿该声音。当前用 CosyVoice 官方提供的示例女声 (`zero_shot_prompt.wav`)，后续替换参考音频就能自定义小安的声线。

**核心代码** (`backend/tts_engine.py`):

```python
from cosyvoice.cli.cosyvoice import CosyVoice
import torchaudio

engine = CosyVoice(model_dir, fp16=torch.cuda.is_available())

# 零样本推理
outputs = engine.inference_zero_shot(
    tts_text="大家好！我是小安~",
    prompt_text="希望你以后能够做的比我还好呦。",
    prompt_wav="path/to/reference.wav",
    stream=False,
)
audio = outputs[0]["tts_speech"]  # torch.Tensor, shape (1, N)
torchaudio.save("output.wav", audio, 22050)
```

**线程安全**：CosyVoice 内部不是线程安全的（模型参数在 GPU 上的共享状态）。使用 `ThreadPoolExecutor(max_workers=1)` 确保请求串行处理。

**文件级缓存**：相同文本的音频永久缓存，通过 SHA256 哈希避免重复合成：

```python
audio_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
wav_path = f"audio/tts_{audio_hash}.wav"
if wav_path.exists():
    return cached  # 跳过推理
```

---

## 3. 句级流式流水线

**设计动机**：如果等 LLM 生成完所有文本再开始 TTS，用户要等 `LLM时间 + 所有句子TTS时间` 才能听到第一句音频。句级流水线让 TTS 在 LLM 生成过程中就开始工作。

**实现**（非在线版，在线版见第 4 节讨论）:

```python
# 1. LLM 生成全文（SSE 流式推送文字给前端）
full_reply = ""
for chunk in llm_engine.generate_stream(message):
    full_reply += chunk
    yield token_event(chunk)

# 2. 按标点切句
sentences = tts_engine.split_sentences(full_reply)
# "大家好！今天我们来聊点有趣的~你喜欢什么？"
# → ["大家好！", "今天我们来聊点有趣的~", "你喜欢什么？"]

# 3. 异步提交所有句子到 TTS（GPU 串行执行）
futures = [(sent, tts_engine.synthesize_async(sent)) for sent in sentences]

# 4. 等待结果，逐个推送音频事件
for sent, future in futures:
    audio = future.result(timeout=60)
    yield audio_event(audio)
```

**句子分割正则**:

```python
SENTENCE_RE = re.compile(r'[。！？…\n]')

def split_sentences(text: str) -> list[str]:
    parts = re.split(r'(?<=[。！？~！？…\n])', text)
    return [p.strip() for p in parts if p.strip()]
```

使用正向后顾 `(?<=...)` 保留标点符号在句尾。

---

## 4. SSE 事件流设计

### 事件格式

```
data: {"token":"大"}
data: {"token":"家"}
data: {"token":"好"}
data: {"token":"！"}
data: {"audio":{"wav_url":"/audio/tts_d8b8d893.wav","duration":1.5,"text":"大家好！"}}
data: {"token":"今"}
data: {"token":"天"}
...
data: {"audio":{"wav_url":"/audio/tts_1234abcd.wav","duration":2.2,"text":"今天我们来..."}}
...
data: {"done":true,"record_id":42,"tts":true}
```

### 前端 SSE 解析

```javascript
es.onmessage = (event) => {
  const data = JSON.parse(event.data)
  if (data.token) {
    item.ai_reply += data.token          // 追加文字
    scrollToBottom()
  } else if (data.audio) {
    enqueueAudio(data.audio.wav_url)     // 音频入队
  } else if (data.done) {
    item._streaming = false              // 完成
  }
}
```

### 音频队列播放

前端维护一个播放队列，确保多句音频按顺序播放、不重叠：

```javascript
let audioQueue = []
let audioPlaying = false

function enqueueAudio(audioUrl, text) {
  audioQueue.push({ audioUrl, text })
  playAudioQueue()
}

async function playAudioQueue() {
  if (audioPlaying || audioQueue.length === 0) return
  audioPlaying = true
  while (audioQueue.length > 0) {
    const { audioUrl } = audioQueue.shift()
    await live2dRef.value.playAudio(BASE_URL + audioUrl)
  }
  audioPlaying = false
}
```

---

## 5. Live2D 前端渲染

### 技术选型

- **PIXI.js v7** — WebGL 2D 渲染引擎
- **pixi-live2d-display v0.4.0** — PIXI 的 Live2D 插件，支持 Cubism 2/3/4

> 为什么不用 PixiJS v8？pixi-live2d-display 最新版本 (v0.5.0-beta) 仍依赖 PixiJS v7，v8 不兼容。

### Live2DStage.vue 组件架构

```
Live2DStage.vue
├── <template>
│   ├── 模型未就绪 → 显示紫色圆形头像占位
│   └── 模型就绪 → PIXI Canvas（透明背景）
├── <script setup>
│   ├── Props: modelPath, expression, energy
│   ├── initLive2D() → 创建 PIXI.Application → 加载模型
│   ├── playAudio(url) → 播放音频 + 驱动口型
│   ├── setExpression(name) → 切换表情
│   └── Expose: playAudio, stopAudio, setExpression
└── <style>
    └── radial-gradient 暗色背景，Canvas 自适应
```

### 关键代码

**初始化 PIXI + Live2D**:

```javascript
const { Live2DModel } = await import('pixi-live2d-display')
const PIXI = await import('pixi.js')

const app = new PIXI.Application({
  width, height,
  backgroundAlpha: 0,        // 透明背景，CSS 负责底色
  antialias: true,
  resolution: window.devicePixelRatio,
  autoDensity: true,
})

const model = await Live2DModel.from('/live2d/shizuku.model.json')
model.anchor.set(0.5, 0.5)             // 锚点居中
model.x = width / 2                    // 水平居中
model.y = height * 0.55                // 略偏下
model.scale.set(scale * 0.9)           // 适配画布
app.stage.addChild(model)
```

**口型驱动（每一帧）**:

```javascript
app.ticker.add(() => {
  currentMouth += (targetMouth - currentMouth) * 0.2  // 指数平滑
  model.internalModel.coreModel.setParameterValueById(
    'PARAM_MOUTH_OPEN_Y',  // Cubism 2.1 参数名
    currentMouth
  )
})
```

平滑系数 0.2 使口型过渡自然，避免突变。

**Cubism 2.1 vs 3/4 参数名差异**:

| 参数 | Cubism 2.1 | Cubism 3/4 |
|------|-----------|-----------|
| 嘴张开 | `PARAM_MOUTH_OPEN_Y` | `ParamMouthOpenY` |
| 左眼 | `PARAM_EYE_L_OPEN` | `ParamEyeLOpen` |
| 右眼 | `PARAM_EYE_R_OPEN` | `ParamEyeROpen` |

组件在模型加载后自动探测正确的参数名。

---

## 6. 口型同步：Web Audio API 音量驱动

### 为什么用音量而不是音素？

CosyVoice 不直接输出音素时间戳。要做精确的音素级口型需要外加 MFA（Montreal Forced Aligner），引入额外 1-2GB 模型和数十秒对齐延迟。音量驱动是 80 分方案——不需要任何额外模型，延迟为零。

### LipSync 实现

```javascript
class LipSync {
  start(audio, onUpdate) {
    this.audioContext = new AudioContext()
    this.analyser = this.audioContext.createAnalyser()
    this.analyser.fftSize = 256                     // 频域精度
    this.analyser.smoothingTimeConstant = 0.3       // 时间平滑

    this.source = this.audioContext.createMediaElementSource(audio)
    this.source.connect(this.analyser)
    this.analyser.connect(this.audioContext.destination)  // 直通扬声器
  }

  _tick() {
    const data = new Uint8Array(this.analyser.frequencyBinCount)
    this.analyser.getByteFrequencyData(data)

    // RMS → 0~1
    let sum = 0
    for (let i = 0; i < data.length; i++) sum += data[i] * data[i]
    const rms = Math.sqrt(sum / data.length) / 255
    const value = Math.min(1, rms * 3.0)   // 放大 3x 让口型更明显

    this.onUpdate(value)                    // 回调驱动 Live2D
    requestAnimationFrame(() => this._tick())
  }
}
```

**参数说明**:
- `fftSize=256` → 128 个频率 bin，足够做音量估计
- `smoothingTimeConstant=0.3` → 平滑过渡，避免口型抖动
- `rms * 3.0` → 人声信号 RMS 通常较低（0.05-0.3），放大后口型更可见
- `Math.min(1, ...)` → 裁剪到 0-1 区间

### 音素方案（可选升级）

如果要做到真正的音素口型（"n"→闭口，"a"→大开口），方案是：

1. CosyVoice 生成音频时导出内部的对齐矩阵（需修改源码）
2. 或用 MFA (Montreal Forced Aligner) 离线做文本-音频对齐
3. 得到 `[{phoneme: "n", start: 0.0, end: 0.12}, {phoneme: "i", start: 0.12, end: 0.25}, ...]`
4. 前端根据当前播放时间插值对应的口型值

这是 Phase 4 的工作。

---

## 7. GPU 加速与性能数据

### 硬件环境

- GPU: NVIDIA RTX 4060 Laptop (8GB VRAM)
- CUDA: 12.8
- PyTorch: 2.11.0+cu128 (fp16)

### 性能对比

| 指标 | CPU (i7-13700H) | GPU (RTX 4060) |
|------|:---:|:---:|
| 模型加载 | ~60s | ~58s |
| RTF (实时率) | 8.5x | 2.7x |
| 3 秒音频合成时间 | ~25s | ~8s |

> RTF = 合成时间 / 音频时长。RTF < 1.0 表示比实时快。

### 为什么 GPU RTF 只有 2.7x 而不是 < 1.0？

1. **自回归生成**：CosyVoice 的 LLM 自回归生成语音 token（每次 forward 只出一个 token），3 秒音频 ≈ 150 个 token ≈ 150 次 GPU forward。每次 forward 都很快，但 150 次加起来就慢了。

2. **ONNX Runtime 是 CPU 版**：Campplus（说话人特征）和 speech_tokenizer 通过 ONNX 推理，当前 ONNX Runtime 没有 CUDA provider，额外增加 1-2 秒。

3. **HiFi-GAN 在 CPU 上**：部分后处理未 GPU 化。

### 优化方向

- 安装 `onnxruntime-gpu` → ONNX 模型上 GPU，估计省 1-2 秒
- TensorRT 加速 Flow decoder（`load_trt=True`）→ 估计省 30-40%
- 使用 CosyVoice2 模型（更小的 LLM，更快的推理）

---

## 8. 灵魂引擎预留接口

Phase 5 将实现"虚拟主播灵魂引擎"——情绪模型、记忆系统、生理节律。当前代码已预留接口桩 (`backend/soul_engine.py`)：

```python
def get_agent_state() -> dict:
    """返回当前内在状态"""
    return {
        "energy": 0.8,          # 精力 0-1
        "mood_valence": 0.6,    # PAD 愉悦度
        "mood_arousal": 0.5,    # PAD 唤醒度
        "mood_dominance": 0.7,  # PAD 支配度
        "expression": "happy",  # 映射到 Live2D 表情
    }

def on_message_sent(user_msg: str) -> None: ...
def on_reply_generated(reply: str) -> None: ...
```

前端 `Live2DStage.vue` 暴露 `expression` 和 `energy` props，后续接入灵魂引擎时无需改 API。

参考设计（20 子系统虚拟生命引擎）中，对虚拟主播最有价值的子系统：
1. **生理节律 + PAD 情绪** — 不同时段不同状态
2. **NarrativeSelf** — 主播有"过去"和人设故事
3. **CuriosityEngine** — 冷场时主动找话题
4. **动态回复延迟** — 模拟真人思考时间

---

## 9. 踩坑记录

### 9.1 CosyVoice 依赖链

CosyVoice 依赖 30+ 个包（wetext, omegaconf, hydra-core, diffusers, openai-whisper, x-transformers, gdown, librosa, pyworld, conformer...）。建议直接按其 `requirements.txt` 安装，但排除 Linux-only 的 `deepspeed` 和 `tensorrt-cu12`。

### 9.2 Python 3.13 + CUDA PyTorch

Python 3.13 on Windows 的 CUDA PyTorch 只有 cu128 索引有预编译包。CUDA 12.1 索引没有 cp313 wheel。解决：

```bash
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128
```

### 9.3 pixi-live2d-display 版本兼容

- v0.4.0 依赖 PixiJS v6/v7（非 v8）
- v0.5.0-beta 仍依赖 PixiJS v7（尽管 PixiJS v8 已出）
- 解决：安装 `pixi.js@^7.3.0`

### 9.4 Cubism 版本差异

- Cubism 2.1: `model.json` + `.moc` 文件，参数名大写加下划线
- Cubism 3/4: `model3.json` + `.moc3` 文件，参数名驼峰

pixi-live2d-display 支持所有版本，但参数名需要适配。

### 9.5 GPU 显存压力

同时加载 Qwen3-8B (4-bit, ~5GB) + CosyVoice-300M (fp16, ~2GB) ≈ 7GB。RTX 4060 8GB 刚好够用，但加上系统开销后非常紧张。如果 GPU 显存不足，可在 `.env` 设置 `TTS_ENABLED=false` 只禁用 TTS。

---

## 10. 下一步

| 优先级 | 任务 | 说明 |
|:---:|------|------|
| 🔧 | 端到端联调测试 | 启动前后端，验证 SSE → TTS → Live2D 全链路 |
| 📋 | 口型精确同步 | MFA 音素对齐替代音量驱动 |
| 📋 | 音频推流优化 | 在线句级流水线（边生成边 TTS） |
| 📋 | 声线自定义 | 录制小安专属参考音频替换默认女声 |
| 📋 | Phase 5 灵魂引擎 | 情绪/记忆/节律/好奇心引擎 |

---

*上一篇：[技术博客 01 — RAG 检索系统与安全架构](./技术博客01-RAG检索系统与安全架构.md)*
