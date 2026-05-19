# AI虚拟主播技术博客 01：RAG 知识库检索系统与安全架构深度解析

## 摘要

本文详细介绍 AI 虚拟主播项目「小安」的 RAG 检索增强生成系统与后端安全架构。系统采用 ChromaDB 向量数据库 + BGE 中文 Embedding 模型实现知识库语义检索，通过 Qwen3-8B 4-bit 量化大模型生成对话回复。安全层面实现了 bcrypt 密码哈希、JWT 无状态令牌鉴权、三层安全防线（输入预检 → System Prompt → LLM 兜底）。全文涵盖余弦相似度检索原理、标点语义分块策略、相似度阈值过滤机制、SSE 流式生成与线程管理、FastAPI 工程化实践等核心技术细节，适合对 RAG 架构和后端安全感兴趣的开发者参考。

---

## 一、项目概述

### 1.1 系统架构

```
用户浏览器 (Vue3 + EventSource)
        |
    HTTP/SSE
        |
    FastAPI 后端 ─── ChromaDB 向量数据库
        |                |
    Qwen3-8B (4-bit)   BGE-small-zh-v1.5
        |              (Embedding 模型)
    MySQL (用户/聊天记录)
```

技术栈：Python 3.11 + FastAPI + SQLAlchemy + ChromaDB + Sentence-Transformers + Transformers + PyTorch + MySQL

### 1.2 项目路径与仓库

- 本地：`G:\Virtual_presenter`
- 远程：`https://github.com/Jun-shisheng/AI_anchor`
- 后端入口：`backend/main.py`
- RAG 模块：`backend/rag_retriever.py`
- LLM 引擎：`backend/llm_engine.py`
- 鉴权模块：`backend/auth.py`

---

## 二、RAG 知识库检索系统

### 2.1 向量数据库：ChromaDB

ChromaDB 是一个轻量级的开源向量数据库，专为 LLM 应用设计。我们使用持久化模式（PersistentClient），数据存储在 `database/chroma_db/` 目录。

**Collection 配置**：

```python
_collection = _chroma_client.get_or_create_collection(
    name="anchor_knowledge",
    metadata={"hnsw:space": "cosine"},
)
```

关键参数 `hnsw:space: cosine` 指定使用余弦距离作为向量相似度度量。

### 2.2 Embedding 模型：BGE-small-zh-v1.5

选择 BAAI 的 BGE（BAAI General Embedding）系列中文模型，原因：

| 模型 | 参数量 | 维度 | 大小 | 适用场景 |
|------|--------|------|------|----------|
| bge-large-zh-v1.5 | 326M | 1024 | 1.3GB | 高精度生产环境 |
| **bge-small-zh-v1.5** | 24M | 512 | 184MB | 轻量级、CPU 友好 |
| bge-m3 | 568M | 1024 | 2.3GB | 多语言 + 长文本 |

选择 small 版本的核心考量：CPU 推理延迟可控（< 100ms），内存占用低（~200MB），对虚拟主播场景的对话级文本完全够用。

**Embedding 归一化**：

```python
embeddings = model.encode(chunks, normalize_embeddings=True)
```

BGE 模型训练时使用对比学习 + 余弦相似度损失函数，推理时对输出做 L2 归一化（`||v|| = 1`），使向量落在单位球面上。此时余弦距离和欧氏距离满足数学等价关系：

$$\text{cosine\_distance} = \frac{\text{euclidean\_distance}^2}{2}$$

因此 ChromaDB 配置 `hnsw:space: cosine` 是最优选择。

### 2.3 余弦相似度 vs 欧氏距离

#### 余弦相似度

$$\text{cosine\_similarity}(A, B) = \frac{A \cdot B}{||A|| \times ||B||}$$

- 范围：[-1, 1]，1 = 完全同向，0 = 正交，-1 = 完全反向
- 只关注方向，忽略向量模长（长度）
- 适用于文本语义检索：两段话词语数量不同但语义相似时，方向一致

#### 欧氏距离

$$\text{euclidean\_distance}(A, B) = \sqrt{\sum_{i=1}^{n}(A_i - B_i)^2}$$

- 范围：[0, +∞)，0 = 完全相同
- 关注绝对距离，受向量模长影响
- 适用于图像像素差异、空间坐标等场景

#### 本项目为什么选余弦？

1. BGE 模型设计即用于余弦相似度检索
2. 文本语义：两个意思相近但长度不同的句子，方向一致但欧氏距离可能很大
3. ChromaDB natively supports cosine via HNSW index

### 2.4 相似度分数计算

ChromaDB 返回的是余弦**距离**，需要转换为相似度分数：

```python
score = 1.0 - distance  # 转换后范围 [-1, 1]
score = max(0.0, min(1.0, score))  # 裁剪到 [0, 1]
```

转换对照表：

| 余弦距离 | 相似度 score | 含义 |
|:---:|:---:|------|
| 0.0 | 1.0 | 完全相同 |
| 0.2 | 0.8 | 高度相关 |
| 0.5 | 0.5 | 中等相关（阈值边界） |
| 0.8 | 0.2 | 弱相关，应丢弃 |
| 1.0 | 0.0 | 无关 |
| 2.0 | -1.0 | 完全相反 |

系统中设置 `score >= 0.5` 作为保留阈值，低于此分数认为不相关，不注入 prompt。

### 2.5 文本分块策略

#### 2.5.1 为什么要精心设计分块？

文本分块质量直接决定 RAG 检索的命中率和回答质量。常见的两种极端：

- **分块太大**（> 1000 字）：embedding 向量稀释，无法精准定位具体信息
- **分块太小**（< 50 字）：语义碎片化，缺少上下文

#### 2.5.2 旧方案的问题

```python
# 旧方案：简单滑动窗口
for i in range(0, len(para), chunk_size - overlap):
    chunks.append(para[i:i + chunk_size])
# chunk_size=300, overlap=50 → 步进 250 字符
```

问题：在对话场景中频繁拦腰截断句子。例如：

> "今天我要给大家分享一个超级有趣的故事关于我最近在游戏里遇到的"

恰好卡在"遇到的"后面切断。"遇到的什么？"语义丢失，检索时 embedding 向量偏离预期方向。

#### 2.5.3 新方案：标点语义切分

```python
# 第一级：按主要标点切句
sentences = re.split(r'(?<=[。？！；\n])\s*', text)

# 短句合并到 min_chunk (80字)
# 长句按逗号/分号递归拆分
sub_parts = re.split(r'(?<=[，；、：])\s*', sent)

# 参数：max_chunk=512, min_chunk=80
```

两级切分策略：

```
原始文本
    │
    ▼
按 。？！；\n 切句 （第一级：句子边界）
    │
    ├── 长度 < max_chunk ──▶ 直接保留
    ├── 长度 < min_chunk ──▶ 合并到上一个 chunk
    ├── 长度 > max_chunk ──▶ 按 ，；、：拆分（第二级：短句边界）
    │                        │
    │                        ├── 仍超长 ──▶ 硬切（兜底）
    │                        └── 正常 ──▶ 保留
    └── 最后一段太短 ──▶ 合并到前一 chunk
```

关键参数：

| 参数 | 默认值 | 作用 |
|------|--------|------|
| `max_chunk` | 512 | 单个 chunk 最大字符数 |
| `min_chunk` | 80 | 最小合并字符数 |
| 不再需要 overlap | — | 句子边界天然连续，无需重叠 |

### 2.6 相似度阈值过滤

检索流程中引入阈值过滤，防止不相关内容污染模型输入：

```python
def search_knowledge(query, top_k=3, score_threshold=0.5):
    fetch_k = max(top_k * 2, 10)  # 多召回一些
    results = collection.query(query_embeddings=query_embedding, n_results=fetch_k)

    items = []
    for i, doc_id in enumerate(results["ids"][0]):
        score = 1.0 - results["distances"][0][i]
        if score < threshold:  # 低于阈值直接丢弃
            continue
        items.append({...})
        if len(items) >= top_k:
            break
    return items
```

设计要点：
- 召回数量 `fetch_k = max(top_k * 2, 10)` — 留出过滤余量
- 如果所有结果都被过滤 → 返回空列表 → `build_rag_prompt` 不触发 RAG 增强 → 走普通对话模式
- 避免"强行匹配"：没有相关知识就诚实地说不知道，防止模型编造

### 2.7 RAG Prompt 构建

```python
def build_rag_prompt(user_message, contexts):
    # 无相关知识 → 走普通对话
    if not contexts:
        return user_message

    knowledge_text = "\n".join(
        f"[参考{i+1}] {ctx['content']}" for i, ctx in enumerate(contexts)
    )

    return (
        f"{ANCHOR_PERSONA}\n{CONTENT_BLOCK}\n\n"
        f"## 参考知识（优先使用以下知识回答，不相关则忽略）\n"
        f"{knowledge_text}\n\n"
        f"## 观众提问\n{user_message}"
    )
```

Prompt 结构：

```
[角色设定] + [安全边界]
    ↓
[参考知识 1]  评分: 0.85  ← 最高相关性
[参考知识 2]  评分: 0.72
[参考知识 3]  评分: 0.61
    ↓
[观众提问]
```

关键设计："不相关则忽略" — 给模型一个退路，防止被低质量检索结果带偏。

---

## 三、安全架构

### 3.1 密码安全：bcrypt 哈希

#### 问题

原代码中密码以明文存储在 MySQL：

```python
# models.py (旧)
password = Column(String(20), nullable=False)

# main.py (旧) — 注册时直接写入明文
new_user = models.User(password=user.password)

# main.py (旧) — 登录时直接字符串比对
if target_user.password != user.password:
    raise HTTPException(...)
```

这意味着：
- 数据库泄露 = 所有用户密码泄露
- 内部人员可查看任意用户密码
- 即使日志中不小心输出也会暴露

#### 修复：bcrypt 自适应哈希

```python
import bcrypt

# 注册：哈希存储
hashed = bcrypt.hashpw(user.password.encode("utf-8"), bcrypt.gensalt())
new_user.password = hashed.decode("utf-8")  # 存储为 60 字符字符串

# 登录：哈希比对
if not bcrypt.checkpw(user.password.encode("utf-8"), target_user.password.encode("utf-8")):
    raise HTTPException(400, "密码错误")
```

bcrypt 的核心特性：
- **自带盐值**：`gensalt()` 每次生成随机 16 字节盐，两个相同密码的哈希值不同
- **自适应成本**：`gensalt(rounds=12)` 表示 2^12 次迭代，可随硬件升级调整
- **抗彩虹表**：128 位盐 + 184 位哈希 = 无法预计算
- **存储格式**：`$2b$12$...salt...hash...` — 60 字符，self-contained

DB 字段同时扩展为 `String(128)` 以兼容未来更强的哈希算法。

### 3.2 JWT 令牌鉴权

#### 问题

原接口仅校验 UID 是否存在于数据库：

```python
# 旧：任何人猜到一个 8 位 UID 就能冒充该用户
current_user = db.query(models.User).filter(models.User.uid == user_uid).first()
if not current_user:
    raise HTTPException(400, "用户身份无效")
```

UID 是 8 位纯数字，共 1 亿种可能。攻击者可以：
1. 遍历 UID 读取他人聊天历史
2. 伪造他人身份发送消息
3. 批量抓取所有用户的聊天数据

#### 修复：JWT 无状态令牌

```python
# auth.py — 登录时签发令牌
def create_token(uid: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=72)
    payload = {"sub": uid, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

# 后续请求校验
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security_scheme)):
    uid = verify_token(credentials.credentials)
    # 从 DB 获取用户对象
    ...

# SSE GET 接口无法设 Header，从 Query 参数传
def get_current_user_from_query(token: str | None = None):
    uid = verify_token(token)
    ...
```

JWT 方案的优势：
- **无状态**：服务端不需要存储 session，验证靠签名
- **防篡改**：任何修改都会导致签名不匹配
- **自然过期**：72 小时后自动失效，用户需重新登录
- **轻量**：Header + Payload + Signature 三部分，base64 编码后约 200 字节

令牌流程：
```
POST /login → 返回 access_token
     │
     ▼
后续请求 Header: Authorization: Bearer <token>
     │
     ▼
auth.get_current_user Depends 注入
     │
     ├── 签名无效 → 401 "令牌验证失败"
     ├── 已过期   → 401 "令牌已过期，请重新登录"
     └── 有效     → 返回 User 对象
```

### 3.3 三层安全防线

虚拟主播面向公众，必须防止越狱攻击（jailbreak prompting），如诱导讨论政治敏感事件。

```
第一层 — 关键词预检 (main.py 入口)
    用户输入 → 检查黑名单关键词 → 命中 → HTTP 400 "不适合在直播间讨论"
    │
    通过
    ▼
第二层 — System Prompt (rag_retriever.py / llm_engine.py)
    prompt 首行注入角色设定 + 话题白名单 + 拒绝模板
    角色设定："你是虚拟主播，只聊娱乐话题"
    拒绝模板："这个话题不适合在直播间讨论哦~我们聊点开心的吧！"
    │
    ▼
第三层 — LLM 兜底
    System Prompt 中的安全指令让模型本身拒绝越狱
    Qwen3-8B 已有 Anthropic/HuggingFace 的安全对齐训练
```

安全边界定义：

| 允许 (whitelist) | 禁止 (blacklist) |
|------|------|
| 直播互动、弹幕互动 | 政治敏感事件 |
| 游戏、电竞、攻略 | 色情、低俗内容 |
| 音乐、唱歌、乐器 | 暴力、恐怖主义 |
| 绘画、Cosplay、动漫 | 违法活动、黑客技术 |
| 日常闲聊、情感倾诉 | 诱导越狱（DAN/Jailbreak） |

---

## 四、LLM 引擎

### 4.1 模型加载：4-bit 量化 + 线程安全单例

```python
_model = None
_model_lock = threading.Lock()

def load_model():
    global _model, _tokenizer
    if _model is not None:     # 快速路径（已加载）
        return _model, _tokenizer

    with _model_lock:           # 未加载 → 争抢锁
        if _model is not None:  # double-check
            return _model, _tokenizer
        # 加载 16GB 模型...
```

使用 BitsAndBytes 4-bit 量化：

```python
quantization_config = BitsAndBytesConfig(
    load_in_4bit=True,          # 模型权重 4-bit
    bnb_4bit_compute_dtype=torch.float16,  # 计算时反量化到 fp16
    bnb_4bit_quant_type="nf4",  # Normal Float 4
)
```

对 Qwen3-8B（原始约 16GB）的影响：

| 方面 | FP16 | 4-bit NF4 |
|------|------|-----------|
| 显存占用 | ~16GB | ~5GB |
| 推理速度 | 基准 | 约 85% |
| 困惑度（Perplexity） | 基准 | +0.2%~0.5% |

对于对话场景，质量损失几乎不可感知。

### 4.2 SSE 流式生成与线程管理

```python
def generate_stream(prompt, max_new_tokens=512, temperature=0.7):
    model, tokenizer = load_model()
    # ... tokenization ...

    streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)

    thread = Thread(target=model.generate, kwargs=generation_kwargs, daemon=True)
    thread.start()

    try:
        for chunk in streamer:
            yield chunk          # 逐 token 推送给前端
    finally:
        thread.join(timeout=60)  # 等待线程结束或超时
        if thread.is_alive():
            print("[LLM] Stream generation timed out")
```

关键设计点：
- **`daemon=True`**：主进程退出时自动终止，不会残留 zombie thread
- **`thread.join(timeout=60)`**：在 `finally` 块中确保线程结束，防止 GPU 显存泄漏
- **客户端断连**：`for chunk in streamer` 抛出 GeneratorExit → `finally` 执行 → join 等待 → 线程安全终止

前端 SSE 消费（Vue3）：

```javascript
const eventSource = new EventSource(
  `/chat/stream?token=${token}&message=${encodeURIComponent(msg)}`
);
eventSource.onmessage = (e) => {
  const data = JSON.parse(e.data);
  if (data.done) { eventSource.close(); return; }
  reply.value += data.token;  // 打字机逐字追加
};
```

### 4.3 生成参数

```python
outputs = model.generate(
    **inputs,
    max_new_tokens=512,       # 最大生成长度（正常回复 50~200）
    temperature=0.7,          # 随机性（0=确定性，1=高随机）
    do_sample=True,           # 采样模式（非贪心）
    top_p=0.8,                # nucleus sampling
    pad_token_id=tokenizer.eos_token_id,
)
```

参数调优说明：
- `temperature=0.7`：对于虚拟主播，需要一定活泼度但不要胡说八道
- `top_p=0.8`：截断低概率尾巴，减少重复啰嗦
- `max_new_tokens=512`：预留可能的长回答（知识类），系统 prompt 中再限制"不超过 200 字"

---

## 五、数据库设计

### 5.1 表结构

**users 表**：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT PK | 内部主键 |
| uid | VARCHAR(8) UNIQUE INDEX | 对外 8 位唯一 UID |
| username | VARCHAR(20) | 严格区分大小写 |
| password | VARCHAR(128) | bcrypt 哈希（60 字符 + 余量） |
| create_time | DATETIME | 注册时间 |

**chat_records 表**：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT PK | 自增主键 |
| user_uid | VARCHAR(8) INDEX | 绑定用户 UID |
| user_content | TEXT | 用户消息 |
| ai_reply | TEXT | AI 回复 |
| chat_type | INT | 0=私聊 1=公聊（预留） |
| room_id | INT | 房间 ID（预留） |
| is_allow_train | INT | 是否允许用于训练 |
| create_time | DATETIME INDEX | 创建时间 |

### 5.2 索引策略

- `uid UNIQUE INDEX` → 登录后所有操作查 UID，高频查询必须走索引
- `user_uid INDEX` → 拉取用户聊天历史，WHERE user_uid = xxx 走索引
- `create_time INDEX` → `ORDER BY create_time DESC` 分页查询，无索引时全表扫描

### 5.3 查询优化

**注册查重**（从全表扫描改为精准查询）：

```python
# 旧：全表拉到内存再 Python for 循环
all_users = db.query(models.User).all()
for u in all_users:
    if u.username == user.username: ...

# 新：SQL 层精准过滤
existing = db.query(models.User).filter(models.User.username == user.username).first()
```

**流式接口连接管理**（从手动 try/finally 改为上下文管理器）：

```python
# 旧：手动管理
db = SessionLocal()
try:
    user = db.query(...).first()
finally:
    db.close()

# 新：上下文管理器，异常路径也保证关闭
with SessionLocal() as db:
    user = db.query(...).first()
```

### 5.4 UID 生成策略

```python
for _ in range(10):  # 最多重试 10 次
    candidate = str(random.randint(10000000, 99999999))
    if not db.query(...).first():  # 检查是否已存在
        new_uid = candidate
        break
if new_uid is None:
    raise HTTPException(500, "系统繁忙，请稍后重试")
```

- 8 位数字空间：1 亿种可能
- 碰撞概率：假设 100 万用户 → 碰撞率 < 1%
- 10 次重试：每次独立概率 1%，10 次连续碰撞概率 (0.01)^10 ≈ 0
- 设置上限避免极低概率下的无限循环

---

## 六、工程化实践

### 6.1 配置管理

从各文件散落的硬编码改为集中 `.env` + `config.py`：

```python
# config.py
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://...")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "anchor-secret-change-in-production")
MODEL_PATH = PROJECT_ROOT / "models" / "llm" / "Qwen3-8B"
EMBED_MODEL_PATH = PROJECT_ROOT / "models" / "embedding" / "bge-small-zh-v1.5"
CHROMA_DB_PATH = PROJECT_ROOT / "database" / "chroma_db"
CHUNK_MAX = int(os.getenv("CHUNK_MAX", "512"))
CHUNK_MIN = int(os.getenv("CHUNK_MIN", "80"))
RAG_SCORE_THRESHOLD = float(os.getenv("RAG_SCORE_THRESHOLD", "0.5"))
```

```ini
# .env
DATABASE_URL=mysql+pymysql://root:123456@localhost:3306/ai_digital_db
JWT_SECRET_KEY=change-me-to-a-random-string-in-production
ACCESS_TOKEN_EXPIRE_HOURS=72
CHUNK_MAX=512
CHUNK_MIN=80
RAG_SCORE_THRESHOLD=0.5
```

### 6.2 全局异常处理

```python
@app.exception_handler(500)
async def internal_error_handler(request, exc):
    logger.error(f"Internal error: {exc}", exc_info=True)
    return {"code": 500, "msg": "服务器内部错误，请稍后重试"}

@app.exception_handler(401)
async def auth_error_handler(request, exc):
    return {"code": 401, "msg": str(exc.detail)}
```

防止堆栈信息泄露到前端，同时保证用户看到友好的错误提示。

### 6.3 日志系统

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("anchor")

# 使用示例
logger.info(f"User registered: uid={new_user.uid}")
logger.error(f"Stream error: {e}", exc_info=True)
```

生产环境建议进一步配置 `RotatingFileHandler` 或接入 ELK/Loki。

### 6.4 输入校验

```python
class UserRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=20)
    password: str = Field(..., min_length=6, max_length=128)

class ChatRequest(BaseModel):
    user_uid: str = Field(..., min_length=8, max_length=8)
    message: str = Field(..., min_length=1, max_length=500)
```

- username 2~20：防止空字符串和超长用户名
- password 6~128：最小安全长度 + 哈希后不超 DB 字段
- message 1~500：弹幕级聊天长度，防止 LLM 过载

### 6.5 公共函数抽取

```python
def _save_chat_record(user_uid, message, reply):
    """chat_stream 和 chat_rag_stream 共用"""
    with SessionLocal() as db:
        record = models.ChatRecord(user_uid=user_uid, ...)
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

def _lookup_user(user_uid):
    """chat_stream 和 chat_rag_stream 共用"""
    with SessionLocal() as db:
        user = db.query(models.User).filter(...).first()
        if not user:
            raise HTTPException(400, "用户身份无效")
        return user
```

消除原代码中每处 7 行重复的 SessionLocal + try/finally 代码块。

---

## 七、API 接口文档

### 7.1 账号系统

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|:---:|------|
| POST | `/register` | 无 | 注册，返回 uid |
| POST | `/login` | 无 | 登录，返回 JWT access_token |

### 7.2 聊天

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|:---:|------|
| POST | `/chat` | Header Bearer | 同步聊天 |
| GET | `/chat/stream` | Query token | SSE 流式聊天 |
| GET | `/my_chat_history` | Query token | 分页聊天历史 |

### 7.3 RAG 知识库

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|:---:|------|
| POST | `/kb/add` | 无 | 添加知识文档 |
| GET | `/kb/list` | 无 | 列出知识文档 |
| DELETE | `/kb/{title}` | 无 | 删除知识文档 |
| GET | `/kb/search` | 无 | 搜索知识库 |

### 7.4 RAG 增强聊天

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|:---:|------|
| POST | `/chat/rag` | Header Bearer | RAG 同步聊天 |
| GET | `/chat/rag/stream` | Query token | RAG SSE 流式 |

---

## 八、已知局限与下一步

### 8.1 当前局限

| 项目 | 状态 | 说明 |
|------|:---:|------|
| Rerank 精排 | 🔜 | 召回 20 → reranker → 取 3，提升检索精确度 |
| Redis 缓存 | 🔜 | 高频问题缓存，减少重复 LLM 调用 |
| 同步接口阻塞 | 🔜 | `/chat`、`/chat/rag` LLM 生成期间阻塞线程 |
| Live2D 渲染 | 🔜 | 前端数字人显示 |
| TTS 语音 | 🔜 | CosyVoice-300M 文字转语音 |
| LoRA 微调 | 🔜 | 主播风格定制训练 |

### 8.2 模型清单

| 模型 | 路径 | 大小 | 用途 |
|------|------|------|------|
| Qwen3-8B (4-bit) | `models/llm/Qwen3-8B/` | ~5GB | 对话生成 |
| BGE-small-zh-v1.5 | `models/embedding/bge-small-zh-v1.5/` | 184MB | 向量 Embedding |
| CosyVoice-300M | `models/tts/CosyVoice-300M/` | 2.5GB | TTS（待接入） |

---

## 九、参考资料

- ChromaDB 文档：https://docs.trychroma.com/
- BGE 模型系列：https://huggingface.co/BAAI/bge-small-zh-v1.5
- Qwen3 模型：https://huggingface.co/Qwen/Qwen3-8B
- FastAPI 文档：https://fastapi.tiangolo.com/
- bcrypt 算法：https://en.wikipedia.org/wiki/Bcrypt
- JWT RFC 7519：https://datatracker.ietf.org/doc/html/rfc7519
