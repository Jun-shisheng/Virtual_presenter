# 开发日志 (CHANGELOG)

## 2026-05-17 — 项目初始化 & 模型下载

### 已完成
- [x] 初始化 Git 仓库，连接 GitHub 远程仓库 (`git@github.com:Jun-shisheng/AI_anchor.git`)
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
- [ ] 新建 `backend/llm_engine.py`，用 transformers 加载 Qwen3-8B
- [ ] 改造 `/chat` 接口，替换固定回复为真实 AI 生成
- [ ] 实现 SSE 流式响应（打字机效果）

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
