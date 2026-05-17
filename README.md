# AI Anchor — AI 虚拟数字人互动系统

> 基于 LLM + RAG + Live2D + TTS 的开源 AI 虚拟主播/数字人项目

[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-green)](https://www.python.org/)
[![Vue](https://img.shields.io/badge/vue-3.x-brightgreen)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/fastapi-0.100+-teal)](https://fastapi.tiangolo.com/)

## 项目愿景

用户打开网页 → 看到 Live2D 数字人形象 → 打字/语音输入 → 本地 LLM + RAG 知识库生成回答 → TTS 语音合成 → 数字人开口说话

## 当前进度

| 模块 | 状态 | 说明 |
|------|:----:|------|
| 用户注册/登录 | ✅ 已完成 | FastAPI + MySQL，8位UID标识 |
| 聊天消息收发 | ✅ 已完成 | 前端 Vue3 聊天界面 + 后端入库 |
| LLM 大模型接入 | 🔄 进行中 | 接入 Qwen3-8B，替换固定模板回复 |
| RAG 知识库检索 | 🔜 待开发 | ChromaDB + BGE Embedding |
| Live2D 数字人 | 🔜 待开发 | pixi-live2d-display 渲染 |
| TTS 语音合成 | 🔜 待开发 | CosyVoice-300M 语音合成 + 口型同步 |
| LoRA 微调 | 🔜 待开发 | 人设数据集 + QLoRA 微调 |
| 云部署 | 🔜 待开发 | Nginx + uvicorn + GPU 实例 |

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| **LLM** | Qwen3-8B (HuggingFace) | 中文最强 8B 模型，Apache 2.0 |
| **后端** | FastAPI + SQLAlchemy + PyMySQL | Python 异步 Web 框架 |
| **前端** | Vue 3 + Vite + Axios + Vue Router | 现代化前端 |
| **数据库** | MySQL 8.0 | 用户数据 + 聊天记录 |
| **向量库** | ChromaDB | RAG 知识检索 |
| **Embedding** | BGE-small-zh-v1.5 | 中文文本向量化 |
| **TTS** | CosyVoice-300M | 中文语音合成 |
| **Live2D** | pixi-live2d-display | 数字人渲染 |
| **微调** | PEFT + QLoRA | 参数高效微调 |

## 项目结构

```
ai_digital_human_project/
├── backend/                    # FastAPI 后端
│   ├── main.py                # API 入口（路由 + 业务逻辑）
│   ├── database.py            # MySQL 连接配置
│   ├── models.py              # 数据表 ORM 模型
│   ├── schemas.py             # Pydantic 请求/响应体
│   ├── llm_engine.py          # [新增] LangChain LLM 封装
│   ├── rag_retriever.py       # [新增] RAG 检索器
│   └── tts_engine.py          # [新增] TTS 语音合成
├── frontend/                   # Vue 3 前端
│   └── src/
│       ├── components/        # 组件（含 Live2DModel）
│       ├── views/             # 页面（Login, Register, Chat）
│       ├── router/            # 路由配置
│       └── request.js         # Axios 请求封装
├── models/                     # 模型权重（通过 HuggingFace 下载）
│   ├── llm/                   # Qwen3-8B (~16GB / ~6GB 4-bit)
│   ├── embedding/             # BGE-small-zh-v1.5 (~480MB)
│   └── tts/                   # CosyVoice-300M (~310MB)
├── database/                   # 数据库脚本
├── README.md                   # 项目文档
├── CHANGELOG.md                # 开发日志
└── .gitignore
```

## 快速启动

### 环境要求

- **OS**: Windows 11 / Linux
- **GPU**: NVIDIA RTX 4060 (8GB VRAM) 或更高
- **RAM**: 32GB+
- **Python**: 3.10+
- **Node.js**: 18+
- **MySQL**: 8.0

### 1. 下载模型

```bash
# 一键下载所有模型
python download_models.py

# 或分阶段下载
python download_models.py --llm       # Qwen3-8B (~16GB)
python download_models.py --embed     # BGE-small-zh-v1.5 (~184MB)
python download_models.py --tts       # CosyVoice-300M (~2.5GB)
```

| 模型 | 大小 | 路径 | 用途 |
|------|------|------|------|
| Qwen3-8B | 16GB | `models/llm/Qwen3-8B/` | 中英双语对话生成 |
| BGE-small-zh-v1.5 | 184MB | `models/embedding/bge-small-zh-v1.5/` | 中文文本向量化 (RAG) |
| CosyVoice-300M | 2.5GB | `models/tts/CosyVoice-300M/` | 中文语音合成 + 声音克隆 |

### 2. 启动后端

```powershell
cd backend
..\venv\python.exe -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

验证: 浏览器打开 http://127.0.0.1:8000 → 显示 `{"code":200,"msg":"✅ AI数字人后端运行正常"}`

### 3. 启动前端

```powershell
cd frontend
npm install
npm run dev
```

验证: 浏览器打开 http://localhost:5173

### 4. 数据库配置

确保 MySQL 8.0 运行中，创建数据库：

```sql
CREATE DATABASE IF NOT EXISTS ai_digital_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

默认连接: `root:123456@localhost:3306/ai_digital_db`（可在 `backend/database.py` 修改）

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 健康检查 |
| POST | `/register` | 用户注册 `{username, password}` |
| POST | `/login` | 用户登录 `{username, password}` |
| POST | `/chat` | 聊天 `{user_uid, message}` |
| GET | `/my_chat_history` | 聊天记录 `?user_uid=xxx` |

完整 API 文档: http://127.0.0.1:8000/docs (Swagger UI)

## 路线图

详见 [AI数字人项目-学习开发路线图.md](AI数字人项目-学习开发路线图.md)

- [x] 阶段零：环境摸底与准备
- [ ] 第一阶段：LLM + LangChain 接入（1-2周）
- [ ] 第二阶段：RAG 知识库检索（1-2周）
- [ ] 第三阶段：Live2D 卡通形象（1-2周）
- [ ] 第四阶段：TTS 语音 + 口型同步（1-2周）
- [ ] 第五阶段：LoRA 微调（2-3周）
- [ ] 第六阶段：云部署上线（1周）

## 硬件适配

本项目针对 **RTX 4060 (8GB VRAM)** 优化：

- Qwen3-8B 使用 4-bit 量化 (~6GB VRAM)
- Embedding 模型纯 CPU 运行
- TTS 模型纯 CPU 运行
- 剩余 ~2GB VRAM 作为推理缓冲

## 许可证

本项目代码采用 MIT 许可证。使用的开源模型分别遵循其各自的许可证：

- Qwen3-8B: Apache 2.0
- BGE-small-zh-v1.5: MIT
- CosyVoice-300M: Apache 2.0

## 作者

- GitHub: [@Jun-shisheng](https://github.com/Jun-shisheng)
