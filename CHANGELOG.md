# 开发日志 (CHANGELOG)

## 2026-05-17 — 项目初始化 & 模型下载

### 已完成
- [x] 初始化 Git 仓库，连接 GitHub 远程仓库 (`git@github.com:Jun-shisheng/Virtual_presenter.git`)
- [x] 首次代码推送（30 个文件，main 分支）
- [x] 创建项目 README.md（含技术栈、API 文档、硬件适配方案）
- [x] 创建 `.gitignore`，排除 venv/node_modules/models
- [x] 创建 `download_models.py` 统一模型下载脚本
- [x] 下载 BGE-small-zh-v1.5 Embedding 模型 (~184MB) → `models/embedding/`
- [x] 下载 CosyVoice-300M TTS 模型 → `models/tts/`

### 已完成（续）
- [x] 下载 Qwen3-8B 模型 (~16GB, 5 safetensors) → `models/llm/Qwen3-8B/`
- [x] 下载 BGE-small-zh-v1.5 Embedding (~184MB) → `models/embedding/bge-small-zh-v1.5/`
- [x] 下载 CosyVoice-300M TTS (~2.5GB) → `models/tts/CosyVoice-300M/`
- [x] 模型总大小: ~18GB，全部存放在项目 `models/` 目录

### 下一步
- [ ] 前端接入 SSE 流式聊天（EventSource 打字机效果）
- [ ] 聊天历史接口改为返回分页数据
- [ ] 第二阶段：RAG 知识库检索（ChromaDB + BGE Embedding）

---

## 2026-05-18 — Phase 1 收尾 & Phase 2 RAG 完成

### 已完成
- [x] 聊天历史接口改为分页返回（page/page_size/total）
- [x] 前端 SSE 流式聊天 — EventSource 逐 token 打字机效果
- [x] 前端新增 RAG 开关，一键切换增强模式
- [x] 新建 `backend/rag_retriever.py` — ChromaDB + BGE-small-zh-v1.5
- [x] 知识库管理 API: POST /kb/add, GET /kb/list, DELETE /kb/{title}, GET /kb/search
- [x] RAG 增强聊天: POST /chat/rag + GET /chat/rag/stream (SSE)
- [x] 安装依赖: chromadb, sentence-transformers

### API 汇总（新增 6 个）
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /kb/add | 添加知识文档 {title, content, source} |
| GET | /kb/list | 列出所有知识文档 |
| DELETE | /kb/{title} | 删除指定知识文档 |
| GET | /kb/search | 搜索知识库 ?q=xxx&top_k=3 |
| POST | /chat/rag | RAG 增强同步聊天 |
| GET | /chat/rag/stream | RAG 增强 SSE 流式聊天 |

### 下一步
- [ ] 准备知识库内容（虚拟主播人设、直播话术、粉丝问答）
- [ ] Phase 3: Live2D 数字人（pixi-live2d-display）
- [ ] Phase 4: TTS 语音合成（CosyVoice-300M）

---

## 2026-05-17 下午 — Phase 1: LLM 接入完成

### 已完成
- [x] 安装 bitsandbytes 4-bit 量化库 (v0.49.2, Windows 兼容)
- [x] 新建 `backend/llm_engine.py`，封装 Qwen3-8B 模型加载/生成
  - 4-bit NF4 量化加载（~6GB VRAM），适配 RTX 4060 8GB
  - `generate()` 同步生成 + `generate_stream()` 流式 token 输出
  - 虚拟主播人设 System Prompt（"小安"）
  - 关闭 Qwen3 思考模式（enable_thinking=False），加快响应
  - 首次调用自动加载，后续命中内存缓存
- [x] 改造 `POST /chat` 接口，替换固定回复为 `llm_engine.generate()` 真实 AI 生成
- [x] 新增 `GET /chat/stream` SSE 流式接口（token 级打字机效果）
- [x] 启动时预加载模型（`@app.on_event("startup")`），避免首次请求等待

### 技术决策
- **纯 HuggingFace transformers 方案**：不使用 Ollama，方便后续 QLoRA 微调
- **4-bit 量化**：NF4 量化 + float16 计算，VRAM 从 16GB 降至 ~6GB
- **双接口设计**：`POST /chat` 同步返回完整回复，`GET /chat/stream` SSE 流式推送（前端后续接入 EventSource 实现打字机效果）

---

## 2026-05-17 之前 — 基础脚手架搭建

### 已完成
- [x] FastAPI 后端框架搭建（`backend/main.py`）
- [x] MySQL 数据库连接 + ORM 模型（`backend/database.py`, `backend/models.py`）
- [x] 用户注册/登录接口（8位 UID 标识）
- [x] 聊天消息收发 + 历史记录入库
- [x] Vue3 前端搭建（Login / Register / Chat 三页面）
- [x] 前后端联调通过
- [x] Ollama 本地部署 Qwen:7B（用于测试，后续替换为纯代码调用）
- [x] 项目路线图规划（6 阶段）
