# 开发日志 (CHANGELOG)

## 2026-05-17 — 项目初始化 & 模型下载

### 已完成
- [x] 初始化 Git 仓库，连接 GitHub 远程仓库
- [x] 创建项目 README.md 和开发文档
- [x] 创建 `.gitignore`，排除 venv/node_modules/models

### 进行中
- [ ] 下载 Qwen3-8B 模型到 `models/llm/`
- [ ] 新建 `backend/llm_engine.py`，LangChain 封装模型调用
- [ ] 改造 `/chat` 接口，替换固定回复为真实 AI 生成

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
