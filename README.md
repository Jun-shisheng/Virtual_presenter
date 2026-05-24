# Virtual_presenter — AI 虚拟数字人互动系统

> LLM + RAG + Live2D + TTS 全链路 AI 虚拟主播/数字人项目

[![Python](https://img.shields.io/badge/python-3.10+-green)](https://www.python.org/)
[![Vue](https://img.shields.io/badge/vue-3.x-brightgreen)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/fastapi-0.100+-teal)](https://fastapi.tiangolo.com/)
[![GPU](https://img.shields.io/badge/GPU-RTX_4060-orange)]()

## 项目愿景

打开网页 → 看到 Live2D 数字人 → 打字聊天 → 本地 LLM + RAG 知识库生成回答 → TTS 语音合成 → 数字人口型同步说话

## 当前进度

| 模块 | 状态 | 关键技术 |
|------|:----:|------|
| 用户注册/登录 | ✅ | bcrypt + JWT |
| LLM 对话 | ✅ | Qwen3-8B 4-bit + SSE 流式 |
| RAG 知识库 | ✅ | ChromaDB + BGE + Reranker 精排 |
| 安全加固 | ✅ | 关键词过滤 + System Prompt + 拒绝模板 |
| Live2D 数字人 | 🔧 | pixi-live2d-display（代码完成，待下载模型） |
| TTS 语音合成 | 🔧 | CosyVoice-300M GPU fp16（代码完成，RTF ~2.7x） |
| 灵魂引擎 | 📋 | 设计已完成，Phase 5 实现（情绪/记忆/节律） |
| LoRA 微调 | 📋 | PEFT + QLoRA 人设微调 |

## 技术栈

| 层级 | 技术 |
|------|------|
| LLM | Qwen3-8B (4-bit GPTQ) |
| 后端 | FastAPI + SQLAlchemy + Redis + PyMySQL |
| 前端 | Vue 3 + Vite + PIXI.js + pixi-live2d-display |
| 向量库 | ChromaDB + BGE-small-zh-v1.5 + BGE-Reranker |
| TTS | CosyVoice-300M (GPU fp16) |
| 安全 | bcrypt + JWT + 输入校验 + 内容过滤 |

## 项目结构

```
Virtual_presenter/
├── backend/
│   ├── main.py              FastAPI 入口 + 路由
│   ├── auth.py              JWT 鉴权
│   ├── config.py            统一配置管理
│   ├── database.py          MySQL 连接
│   ├── llm_engine.py        Qwen3-8B 4-bit 推理
│   ├── rag_retriever.py     ChromaDB + BGE + Reranker
│   ├── tts_engine.py        CosyVoice-300M 句级流式合成
│   ├── audio_cache.py       高频短语预生成缓存
│   ├── soul_engine.py       [stub] Phase 5 灵魂引擎
│   ├── models.py / schemas.py  ORM + 请求体
│   └── audio/               生成音频文件 (.gitignore)
├── frontend/src/
│   ├── views/Chat.vue       双栏聊天（Live2D + 对话）
│   ├── components/Live2DStage.vue  PIXI.js Live2D 渲染
│   ├── utils/lipSync.js     Web Audio 音量→口型
│   ├── router/ / request.js 路由 + Axios
│   └── assets/
├── models/                   模型权重 (.gitignore)
│   ├── llm/Qwen3-8B/         ~5GB (4-bit)
│   ├── embedding/bge-small-zh-v1.5/  184MB
│   ├── reranker/bge-reranker-base/   400MB
│   └── tts/CosyVoice-300M/  2.1GB
├── third_party/CosyVoice/    CosyVoice 推理代码
├── docs/
│   └── phase3-live2d-tts-design.md
└── requirements.txt
```

## 快速启动

### 环境要求

- **OS**: Windows 11 / Linux
- **GPU**: NVIDIA RTX 4060 (8GB VRAM) 或更高
- **RAM**: 32GB+
- **Python**: 3.10+
- **Node.js**: 18+
- **MySQL**: 8.0

### 1. 安装依赖

```bash
cd Virtual_presenter
uv venv
source .venv/Scripts/activate  # Windows
uv pip install -r requirements.txt

# CosyVoice 依赖
uv pip install hyperpyyaml modelscope onnxruntime onnx diffusers \
    openai-whisper soundfile librosa pyworld conformer inflect wetext \
    omegaconf hydra-core lightning networkx torchcodec \
    --index-url https://download.pytorch.org/whl/cu128

# 初始化 CosyVoice 子模块
cd third_party/CosyVoice
git submodule update --init --depth 1 third_party/Matcha-TTS
cd ../..

cd frontend && npm install && cd ..
```

### 2. 下载模型

```bash
python download_models.py
```

| 模型 | 大小 | 路径 | 用途 |
|------|------|------|------|
| Qwen3-8B (4-bit) | ~5GB | `models/llm/Qwen3-8B/` | 对话生成 |
| BGE-small-zh-v1.5 | 184MB | `models/embedding/bge-small-zh-v1.5/` | RAG Embedding |
| bge-reranker-base | 400MB | `models/reranker/bge-reranker-base/` | RAG 精排 (可选) |
| CosyVoice-300M | 2.1GB | `models/tts/CosyVoice-300M/` | 语音合成 |

### 3. 启动后端

```bash
cd backend
source ../.venv/Scripts/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

首次启动时 TTS 模型加载约 60 秒（GPU 编译 CUDA kernel）。之后保持在内存中。

### 4. 启动前端

```bash
cd frontend
npm run dev
```

浏览器打开 http://localhost:5173

### 5. 数据库

```sql
CREATE DATABASE IF NOT EXISTS ai_digital_db
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

默认连接 `root:123456@localhost:3306/ai_digital_db`，可通过环境变量 `DATABASE_URL` 覆盖。

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 健康检查 |
| POST | `/register` | 注册 `{username, password}` |
| POST | `/login` | 登录 → JWT token |
| POST | `/chat` | 同步聊天 |
| GET | `/chat/stream` | SSE 流式聊天 + TTS 音频 |
| GET | `/chat/rag` | RAG 增强同步聊天 |
| GET | `/chat/rag/stream` | RAG 增强 SSE 流式 + TTS |
| GET | `/my_chat_history` | 聊天历史分页 |
| POST | `/kb/add` | 添加知识文档 |
| GET | `/kb/search` | 知识库检索 |
| GET | `/audio/*` | 静态音频文件服务 |

完整 API 文档: http://127.0.0.1:8000/docs

## SSE 事件流格式

```
data: {"token": "大"}                              ← 逐字显示
data: {"token": "家"}
data: {"token": "好"}
data: {"token": "！"}
data: {"audio": {"wav_url":"/audio/tts_xxx.wav",
        "duration":1.5, "text":"大家好！"}}          ← 第一句音频就绪
data: {"token": "今"}
...
data: {"done": true, "record_id": 42}              ← 对话结束
```

## 硬件适配

针对 **RTX 4060 (8GB VRAM)** 优化：

| 模型 | 显存占用 | 备注 |
|------|------|------|
| Qwen3-8B (4-bit) | ~5GB | 常驻显存 |
| CosyVoice-300M (fp16) | ~2GB | 推理时加载 |
| BGE + Reranker | CPU | 不占显存 |
| **合计** | ~7GB | 4060 刚好够用 |

若显存不足，可设置 `TTS_ENABLED=false` 环境变量仅禁用 TTS。

## 路线图

- [x] Phase 1: LLM 接入 + 基础聊天
- [x] Phase 2: RAG 知识库 + 安全加固 + SSE 流式
- [x] Phase 3: Live2D 数字人 + TTS 语音合成（**当前**）
- [ ] Phase 4: 口型精确同步 (MFA) + 音频推流优化
- [ ] Phase 5: 灵魂引擎 — 情绪/记忆/生理节律
- [ ] Phase 6: LoRA 人设微调
- [ ] Phase 7: 云部署上线

## 许可证

本项目代码采用 MIT 许可证。使用的开源模型各自遵循其许可证：

- Qwen3-8B: Apache 2.0
- BGE-small-zh-v1.5: MIT
- CosyVoice-300M: Apache 2.0
- Live2D Cubism SDK: [Live2D 专有许可证](https://www.live2d.com/en/download/cubism-sdk/)
