# AI 虚拟数字人项目 · 启动指南

## 技术栈

| 层级 | 技术 |
|------|------|
| **前端** | Vue 3 + Vite + Vue Router + Axios |
| **后端** | Python FastAPI + SQLAlchemy + PyMySQL |
| **数据库** | MySQL 8.0 (root:123456) |
| **Python 环境** | Conda 虚拟环境 (venv/) · Python 3.10 |

---

## 启动步骤（每次开发都需要）

### 1️⃣ 启动后端（打开 **终端 1**）

```powershell
cd G:\Virtual_presenter\backend
G:\Virtual_presenter\venv\python.exe -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**验证方式**：
- 看到 `Uvicorn running on http://0.0.0.0:8000` 即启动成功
- 浏览器打开 [http://127.0.0.1:8000](http://127.0.0.1:8000) → 应显示 `{"code":200,"msg":"✅ AI数字人后端运行正常"}`
- 自动 API 文档：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)（Swagger UI，可在线测试接口）

### 2️⃣ 启动前端（打开 **终端 2**，保持终端 1 不关闭）

```powershell
cd G:\Virtual_presenter\frontend
npm run dev
```

**验证方式**：
- 看到 `Local: http://localhost:5173/` 即启动成功
- 浏览器打开 [http://localhost:5173](http://localhost:5173) → 看到登录页面

### 3️⃣ 使用流程

```
打开 http://localhost:5173
  → 注册账号
  → 登录
  → 进入聊天页面
  → 输入消息，回车发送
```

---

## 项目目录结构（核心代码）

```
G:\Virtual_presenter\
├── backend/
│   ├── main.py            # FastAPI 主程序（路由 + 业务逻辑）
│   ├── database.py        # MySQL 数据库连接配置
│   ├── models.py          # 数据表模型（User, ChatRecord）
│   └── schemas.py         # 请求/响应数据结构
├── frontend/
│   └── src/
│       ├── main.js            # Vue 入口
│       ├── App.vue            # 根组件
│       ├── router/index.js    # 路由配置
│       ├── request.js         # Axios 请求配置 → 后端 127.0.0.1:8000
│       ├── views/
│       │   ├── Login.vue      # 登录页
│       │   ├── Register.vue   # 注册页
│       │   └── Chat.vue       # 聊天主页面
│       └── style.css          # 全局样式
├── venv/                  # Conda Python 虚拟环境（Python 3.10）
├── 软件需求分析.docx            # 需求规格说明书
└── AI虚拟数字人互动系统-可行性分析报告.doc  # 可行性分析报告
```

---

## 后端 API 一览

| 接口 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 健康检查 |
| `/register` | POST | 注册 `{username, password}` |
| `/login` | POST | 登录 `{username, password}` |
| `/chat` | POST | 聊天 `{user_uid, message}` |
| `/my_chat_history` | GET | 查聊天记录 `?user_uid=xxx` |

---

## 已知状态

| 功能 | 状态 |
|------|------|
| ✅ MySQL 数据库连接 | 正常 |
| ✅ 用户注册 / 登录 | 已实现 |
| ✅ 聊天消息收发 + 入库 | 已实现 |
| ❌ AI 大模型接入 | 未接入（当前回复为固定模板） |
| ❌ Live2D 数字人 | 未接入 |
| ❌ TTS 语音合成 | 未接入 |
