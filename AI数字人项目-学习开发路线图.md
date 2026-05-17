# AI 虚拟数字人项目 · 完整学习与开发路线图

**本机配置**：RTX 4060 (8GB) + 32GB RAM + Win11  
**已有模型**：`qwen:7b`（Ollama 已安装）  
**当前进度**：Vue3 前端 + FastAPI 后端 + MySQL 数据库 基本打通

---

## 项目最终形态

```
用户打开网页
  → 看到 Live2D 卡通形象在画面中
  → 打字或语音输入
  → 本地 Qwen 7B 模型 + RAG 知识库检索 → 生成回答
  → TTS 语音合成 → Live2D 口型同步
  → 数字人开口说话、做动作
  → 部署在云服务器 7×24h 运行
```

---

## 阶段零：环境摸底与准备（1-2 天）

### 确认已有成果
- [ ] 启动项目确认前后端正常：`start_project.bat`
- [ ] 确认 MySQL 中已有 `ai_digital_db` 库，users / chat_records 表
- [ ] 确认 Ollama 能用：终端运行 `ollama run qwen:7b` 测试对话

### 环境准备
- [ ] 安装 LangChain：`pip install langchain langchain-community langchain-ollama`
- [ ] 安装 ChromaDB（向量数据库）：`pip install chromadb`
- [ ] 安装 Embedding 模型：`pip install sentence-transformers`
- [ ] 确认 CUDA 可用：`python -c "import torch; print(torch.cuda.is_available())"`
- [ ] Git 初始化项目，方便版本管理

### 了解的关键概念
```
LangChain 核心概念：
  Model I/O   → 调用模型（LLM / ChatModel）
  Retrieval   → 检索（文档加载 → 分割 → 向量化 → 存储 → 检索）
  Chain       → 链式调用
  Agent       → 智能体

RAG 核心概念：
  Embedding   → 文本向量化
  Vector DB   → 向量数据库
  Retriever   → 检索器
  Chunking    → 文档分块

Transformer 核心概念（后续深入）：
  Tokenizer   → 分词器
  Attention   → 注意力机制
  Embedding   → 嵌入层
  Fine-tune   → 微调（LoRA）
```

---

## 第一阶段：LLM 接入 + LangChain 基础（1-2 周）

### 目标
把当前后端 `main.py` 里的假回复替换成真正的 AI 模型回复。

### 实现步骤

```
backend/
  ├── main.py               # FastAPI 入口（改造 chat 接口）
  ├── llm_engine.py          # [新增] LangChain 模型封装
  ├── rag_retriever.py       # [新增] RAG 检索器（第一阶段先留空）
  ├── database.py
  ├── models.py
  └── schemas.py
```

#### Step 1: Ollama 调用验证
```python
# 终端测试
ollama run qwen:7b "你好，介绍一下你自己"
```

#### Step 2: LangChain 接入 Qwen
```python
# llm_engine.py
from langchain_ollama import ChatOllama

llm = ChatOllama(
    model="qwen:7b",
    temperature=0.7,
    num_predict=2048,
)
```

#### Step 3: 改造 `/chat` 接口
原来的假回复 → 调用 LangChain + Qwen 生成真实回复

#### Step 4: 添加系统提示词（System Prompt）
给数字人设定人设（语气、知识范围、行为规则）

#### Step 5: 流式响应（SSE）
让 AI 回复一个字一个字显示出来，体验感提升明显

### 产出
- [ ] `llm_engine.py` 封装 LangChain 调用
- [ ] `/chat` 接口返回真实 AI 回复
- [ ] 流式输出（打字机效果）
- [ ] 前端聊天体验优化

### 学习要点
```
- Ollama 的工作原理
- LangChain 的 ChatModel 抽象
- System Prompt 设计
- SSE（Server-Sent Events）流式传输
- 模型参数（temperature, top_p, max_tokens）的含义
```

---

## 第二阶段：RAG 知识库检索（1-2 周）

### 目标
让数字人能根据你提供的文档内容回答问题，而不是只靠模型自身的知识。

### 实现步骤

```
backend/
  ├── knowledge/             # [新增] 存放知识文档（txt/pdf/md）
  ├── llm_engine.py
  ├── rag_retriever.py       # [实现] 文档加载 → 分割 → 向量化 → 检索
  ├── vector_store/          # [新增] ChromaDB 持久化目录
  └── main.py
```

#### Step 1: 文档准备
- 放几份你的学习笔记、技术文档进去
- LangChain 的 `DocumentLoader` 支持 txt/pdf/md

#### Step 2: 文档分块（Text Splitting）
```python
from langchain.text_splitter import RecursiveCharacterTextSplitter
# 按段落/句子切分，每块 500 字符，重叠 50
```

#### Step 3: 向量化 + 存入 ChromaDB
```python
from langchain_community.embeddings import HuggingFaceEmbeddings
# 用 bge-small-zh-v1.5 或 text2vec-base-chinese（几百MB，本地运行）
```

#### Step 4: 检索增强生成
```
用户提问 → 向量检索 TOP-K 相关文档片段 → 
拼接成 Prompt（"根据以下资料回答问题：..."）→ 
送入 Qwen 生成回答
```

#### Step 5: 管理后台：上传/管理知识文档
- 前端加一个"知识库管理"页面
- 后端加文档上传 → 自动分块 → 向量化 → 入库的流程

### 产出
- [ ] RAG 检索流程跑通
- [ ] 知识文档上传与管理
- [ ] 数字人能根据知识库回答问题
- [ ] 理解 Embedding + 向量检索原理

### 学习要点
```
- Embedding 模型的作用与选型
- 向量数据库（ChromaDB / FAISS）
- 文档分块策略（chunk size / overlap）
- 检索策略（相似度搜索 / MMR / 重排序）
- RAG 的优缺点：知识可控 vs. 检索质量依赖分块
```

---

## 第三阶段：Live2D 卡通形象集成（1-2 周）

### 目标
从纯文字聊天 → 页面左侧有一个 Live2D 数字人形象，说话时有表情动作。

### 获取 Live2D 模型的途径

| 方式 | 难度 | 说明 |
|------|------|------|
| **① 用现成免费模型** | ⭐ | B站 VUP 社区/GitHub 有大量免费 Live2D 模型，直接下载 .model3.json |
| **② AI 生成 + 绑骨** | ⭐⭐⭐ | SD/MJ 生成立绘 → Live2D Cubism Editor 绑骨（有免费版） |
| **③ VRM 3D 模型** | ⭐ | VRoid Hub 海量免费角色，Three.js + @pixiv/three-vrm 渲染 |
| **④ 付费定制** | 💰 | 淘宝/B站 找画师约稿（约 300-2000 元） |

**推荐起步方式**：先用 ① 现成免费模型跑通技术流程，后续再考虑定制。

### 实现步骤

```
frontend/
  └── src/
      ├── components/
      │   └── Live2DModel.vue   # [新增] Live2D 渲染组件
      ├── views/
      │   └── Chat.vue          # [改造] 加入 Live2D 区域
      └── assets/live2d/        # [新增] 放模型资源文件
```

#### Step 1: 前端引入 Live2D 渲染
```bash
npm install pixi-live2d-display pixi.js
```

#### Step 2: 封装 Live2DModel 组件
- 加载 .model3.json 模型文件
- 基础动作：待机呼吸、眨眼、头发飘动

#### Step 3: 改造 Chat.vue 布局
```
┌─────────────────────────────────┐
│  ┌──────────┐  ┌─────────────┐ │
│  │ Live2D   │  │ 聊天记录     │ │
│  │ 数字人    │  │             │ │
│  │          │  │             │ │
│  └──────────┘  ├─────────────┤ │
│                │ 输入框+发送  │ │
│                └─────────────┘ │
└─────────────────────────────────┘
```

#### Step 4: 基础交互
- 点击数字人 → 播放随机动作/语音
- 说话时嘴巴张合动画
- 空闲时随机眨眼、换姿势

### 产出
- [ ] Live2D 模型在网页中正常渲染
- [ ] 聊天时数字人有对应动作反应
- [ ] 空闲时有待机动画

### 学习要点
```
- Live2D Cubism SDK 渲染原理
- 模型动作触发（Motion）
- 表情参数控制（Expression）
- 口型同步基础（LipSync）
```

---

## 第四阶段：TTS 语音合成 + 口型同步（1-2 周）

### 目标
AI 回复文本 → 合成语音 → 数字人开口说话 → 口型同步。

### TTS 模型选型

| 模型 | 大小 | 中文效果 | 说明 |
|------|------|---------|------|
| **ChatTTS** | ~1.5GB | ⭐⭐⭐⭐⭐ | 目前中文效果最好的开源 TTS，情感丰富 |
| **CosyVoice** | ~2GB | ⭐⭐⭐⭐⭐ | 阿里出品，支持声音克隆 |
| **Edge TTS** | 在线API | ⭐⭐⭐⭐ | 无需本地部署，但需要网络 |

### 实现步骤

```
backend/
  ├── tts_engine.py           # [新增] TTS 语音合成
  ├── audio_cache/            # [新增] 音频缓存目录
  └── main.py                 # [改造] 新增 TTS 接口
```

#### Step 1: 部署 TTS 模型
```bash
# ChatTTS 方案
pip install ChatTTS
# 下载模型后封装成 TTS 接口
```

#### Step 2: 后端 TTS 接口
```
POST /tts
  { "text": "你好，我是你的数字人助手", "voice_id": "default" }
→ 返回音频文件 / 音频流
```

#### Step 3: 前端音频播放
- 收到 TTS 音频 → 浏览器播放
- 同时驱动 Live2D 口型同步

#### Step 4: 口型同步实现
两种方式：
- **简版**：根据音频音量控制嘴巴张合幅度
- **精版**：用 Viseme（音素对应口型）精确驱动

### 产出
- [ ] TTS 合成接口跑通
- [ ] 前端播放 + Live2D 口型同步
- [ ] 可切换不同音色

---

## 第五阶段：微调 Fine-tuning（2-3 周）

### 目标
让 Qwen 7B 更符合"你的数字人"的人设和说话风格。

### LoRA 微调流程

```
准备数据集（500-2000 条对话）
  → 加载 base model（Qwen 7B）
  → 添加 LoRA adapter（rank=8~16）
  → 训练（约 2-4 小时）
  → 保存 adapter 权重（几十 MB）
  → 推理时 base model + adapter 合并加载
```

### 数据集格式
```json
{
  "instruction": "你是谁",
  "output": "我是你的专属AI数字人助手，有什么可以帮你的吗？"
}
```

### 工具链
```
- transformers              # HuggingFace 模型加载
- peft（Parameter-Efficient Fine-Tuning）  # LoRA 实现
- bitsandbytes              # 量化（QLoRA，省显存）
- datasets                  # 数据集处理
- trl（Transformer Reinforcement Learning）  # SFTTrainer
```

### 产出
- [ ] 准备好微调数据集（你的人设对话）
- [ ] LoRA 微调脚本跑通
- [ ] 微调后的模型在数字人中生效
- [ ] 理解 LoRA / QLoRA 原理

### 需要深入理解的知识
```
- Transformer 结构（Attention / FFN / LayerNorm）
- 参数高效微调（Adapter / Prefix Tuning / LoRA）
- 量化原理（FP16 / INT8 / INT4）
- 数据集质量的影响
- 过拟合与泛化
```

---

## 第六阶段：云部署上线（1 周）

### 架构方案

```
                 用户浏览器
                     │
              Nginx（反向代理 + HTTPS）
              ┌──────┴──────┐
              │              │
        前端静态文件      FastAPI 后端
        (Nginx托管)      (uvicorn + systemd)
                              │
                    ┌─────────┼─────────┐
                    │         │         │
                 MySQL     ChromaDB   Ollama
                                     (模型推理)
```

### 云服务器选择

| 平台 | GPU 实例 | 价格 | 适合 |
|------|---------|------|------|
| **AutoDL** | RTX 4090 / 4090D | ~2 元/小时 | 性价比最高，按量计费 |
| **腾讯云** | GN10Xp (T4) | ~8 元/小时 | 稳定，有国内合规 |
| **阿里云** | ECS + P4 | ~10 元/小时 | 生态好 |
| **自己电脑** | - | 免费 | 开发调试，不适合 7×24 |

### 部署步骤
- [ ] 后端打包：requirements.txt + uvicorn 服务化
- [ ] 前端打包：`npm run build` → dist 目录给 Nginx
- [ ] Nginx 配置反代 + HTTPS（Let's Encrypt）
- [ ] MySQL 迁移到云数据库或容器化
- [ ] Ollama 在 GPU 实例上运行
- [ ] 域名绑定 + DNS 解析
- [ ] 监控 + 日志 + 自动重启

---

## 总时间线预估

```
第 1-2 周   Phase 1: LLM + LangChain 接入（替换假回复）
第 3-4 周   Phase 2: RAG 知识库检索
第 3-4 周   Phase 3: Live2D 形象（可与 Phase 2 并行）
第 5-6 周   Phase 4: TTS 语音 + 口型同步
第 7-9 周   Phase 5: LoRA 微调
第 10 周    Phase 6: 云部署上线
```

**总计：约 2-3 个月**（业余时间）

---

## 推荐的学习资源

### LangChain / RAG
- LangChain 官方文档 + Cookbook
- 吴恩达《LangChain for LLM Application Development》免费课

### 模型 / 微调
- HuggingFace NLP Course（huggingface.co/learn）
- 《PEFT》文档（LoRA 微调最佳实践）
- 李沐《动手学深度学习》Transformer 章节

### Live2D / 前端
- pixi-live2d-display GitHub 仓库（有示例）
- Cubism Web SDK 官方示例
- VRoid Hub（免费 3D 模型）

---

## 附录：关键命令速查

```bash
# 启动 Ollama 模型
ollama run qwen:7b

# Python 依赖安装
pip install langchain langchain-community langchain-ollama chromadb sentence-transformers

# 查看 GPU 状态
nvidia-smi

# 启动开发环境
# 双击 start_project.bat

# 前端构建（部署用）
cd frontend && npm run build
```
