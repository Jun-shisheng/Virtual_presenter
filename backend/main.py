import json
import bcrypt
import hashlib
import logging
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from database import engine, Base, get_db, SessionLocal
import models
import schemas
import llm_engine
import rag_retriever
import auth
import random
import redis
from config import REDIS_URL, REDIS_CACHE_TTL

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("anchor")

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI数字人聊天系统")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========== 全局异常处理 ==========

@app.exception_handler(500)
async def internal_error_handler(request, exc):
    logger.error(f"Internal error: {exc}", exc_info=True)
    return {"code": 500, "msg": "服务器内部错误，请稍后重试"}


@app.exception_handler(401)
async def auth_error_handler(request, exc):
    return {"code": 401, "msg": str(exc.detail) if hasattr(exc, "detail") else "未授权"}


@app.get("/")
def home():
    return {"code": 200, "msg": "AI数字人后端运行正常"}


# ========== 账号系统 ==========

@app.post("/register")
def register(user: schemas.UserRequest, db=Depends(get_db)):
    # 精准查询替代全表扫描
    existing = db.query(models.User).filter(models.User.username == user.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="该用户名已被注册")

    # UID 生成，最多重试 10 次防死循环
    new_uid = None
    for _ in range(10):
        random_num = random.randint(10000000, 99999999)
        candidate = str(random_num)
        if not db.query(models.User).filter(models.User.uid == candidate).first():
            new_uid = candidate
            break
    if new_uid is None:
        raise HTTPException(status_code=500, detail="系统繁忙，请稍后重试")

    hashed = bcrypt.hashpw(user.password.encode("utf-8"), bcrypt.gensalt())

    new_user = models.User(
        uid=new_uid,
        username=user.username,
        password=hashed.decode("utf-8"),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    logger.info(f"User registered: uid={new_user.uid}, username={new_user.username}")
    return {
        "code": 200,
        "msg": "注册成功",
        "uid": new_user.uid,
        "username": new_user.username,
    }


@app.post("/login")
def login(user: schemas.UserRequest, db=Depends(get_db)):
    target_user = db.query(models.User).filter(models.User.username == user.username).first()
    if not target_user:
        raise HTTPException(status_code=400, detail="用户名不存在，请检查大小写")
    if not bcrypt.checkpw(user.password.encode("utf-8"), target_user.password.encode("utf-8")):
        raise HTTPException(status_code=400, detail="密码错误")

    token = auth.create_token(target_user.uid)
    logger.info(f"User login: uid={target_user.uid}")
    return {
        "code": 200,
        "msg": "登录成功",
        "uid": target_user.uid,
        "username": target_user.username,
        "access_token": token,
        "token_type": "bearer",
    }


# ========== 启动预加载 ==========

@app.on_event("startup")
def startup():
    llm_engine.load_model()


# ========== 公共函数 ==========

def _get_cache():
    """获取 Redis 连接，不可用时返回 None 降级"""
    try:
        r = redis.Redis.from_url(REDIS_URL, socket_connect_timeout=2, decode_responses=True)
        r.ping()
        return r
    except Exception:
        return None


def _cache_get(prompt: str) -> str | None:
    r = _get_cache()
    if r is None:
        return None
    key = "llm_cache:" + hashlib.sha256(prompt.encode()).hexdigest()[:16]
    return r.get(key)


def _cache_set(prompt: str, response: str):
    r = _get_cache()
    if r is None:
        return
    key = "llm_cache:" + hashlib.sha256(prompt.encode()).hexdigest()[:16]
    try:
        r.setex(key, REDIS_CACHE_TTL, response)
    except Exception:
        pass


def _save_chat_record(user_uid: str, message: str, reply: str):
    with SessionLocal() as db:
        record = models.ChatRecord(
            user_uid=user_uid,
            user_content=message,
            ai_reply=reply,
            chat_type=0,
            room_id=0,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record


def _lookup_user(user_uid: str):
    """抽取重复的 UID 校验逻辑"""
    with SessionLocal() as db:
        user = db.query(models.User).filter(models.User.uid == user_uid).first()
        if not user:
            raise HTTPException(status_code=400, detail="用户身份无效，请重新登录")
        return user


# ========== 关键词安全过滤 ==========

BLOCKED_KEYWORDS = [
    "习近平", "习主席", "中共", "六四", "法轮功", "台独", "藏独", "疆独",
    "性爱", "裸体", "色情", "杀人", "自杀", "毒品",
]

def _check_safety(text: str):
    """检查输入是否含敏感关键词"""
    lower = text.lower()
    for kw in BLOCKED_KEYWORDS:
        if kw.lower() in lower:
            raise HTTPException(status_code=400, detail="这个问题不适合在直播间讨论哦~")


# ========== 聊天接口 ==========

@app.post("/chat")
def chat(chat_req: schemas.ChatRequest, bg: BackgroundTasks, current_user=Depends(auth.get_current_user)):
    _check_safety(chat_req.message)

    # Redis 缓存命中则直接返回
    cached = _cache_get(chat_req.message)
    if cached:
        bg.add_task(_save_chat_record, current_user.uid, chat_req.message, cached)
        return {
            "code": 200,
            "user_content": chat_req.message,
            "ai_reply": cached,
            "create_time": str(datetime.now()),
            "cached": True,
        }

    ai_reply_text = llm_engine.generate(chat_req.message)
    bg.add_task(_save_chat_record, current_user.uid, chat_req.message, ai_reply_text)
    _cache_set(chat_req.message, ai_reply_text)

    return {
        "code": 200,
        "user_content": chat_req.message,
        "ai_reply": ai_reply_text,
        "create_time": str(datetime.now()),
    }


@app.get("/chat/stream")
def chat_stream(
    token: str = Query(...),
    message: str = Query(...),
):
    current_user = auth.get_current_user_from_query(token)
    _check_safety(message)

    def event_stream():
        full_reply = ""
        try:
            for chunk in llm_engine.generate_stream(message):
                full_reply += chunk
                yield f"data: {json.dumps({'token': chunk}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"Stream error: {e}", exc_info=True)
            yield f"data: {json.dumps({'error': '生成中断，请重试'})}\n\n"
            return

        try:
            record = _save_chat_record(current_user.uid, message, full_reply)
            yield f"data: {json.dumps({'done': True, 'record_id': record.id}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"Save record error: {e}", exc_info=True)
            yield f"data: {json.dumps({'done': True, 'error': '记录保存失败'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ========== 聊天历史 ==========

@app.get("/my_chat_history")
def get_private_history(
    token: str = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
):
    current_user = auth.get_current_user_from_query(token)

    base_query = db.query(models.ChatRecord).filter(
        models.ChatRecord.user_uid == current_user.uid,
        models.ChatRecord.chat_type == 0,
    )
    total = base_query.count()
    total_pages = max(1, (total + page_size - 1) // page_size) if total > 0 else 1

    records = (
        base_query
        .order_by(models.ChatRecord.create_time.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "code": 200,
        "data": records,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


# ========== RAG 知识库管理 ==========

class KnowledgeDoc(BaseModel):
    title: str
    content: str
    source: str = ""


@app.post("/kb/add")
def kb_add(doc: KnowledgeDoc):
    result = rag_retriever.add_knowledge(doc.title, doc.content, doc.source)
    return {"code": 200, "msg": "知识添加成功", "data": result}


@app.get("/kb/list")
def kb_list():
    return {"code": 200, "data": rag_retriever.list_knowledge()}


@app.delete("/kb/{title}")
def kb_delete(title: str):
    count = rag_retriever.delete_knowledge(title)
    if count == 0:
        raise HTTPException(status_code=404, detail="未找到该知识文档")
    return {"code": 200, "msg": f"已删除 {count} 个分块"}


@app.get("/kb/search")
def kb_search(q: str = Query(...), top_k: int = Query(3, ge=1, le=10)):
    results = rag_retriever.search_knowledge(q, top_k)
    return {"code": 200, "data": results}


# ========== RAG 增强聊天 ==========

class RAGChatRequest(BaseModel):
    user_uid: str = Field(..., min_length=8, max_length=8)
    message: str = Field(..., min_length=1, max_length=500)
    use_rag: bool = True


@app.post("/chat/rag")
def chat_rag(chat_req: RAGChatRequest, bg: BackgroundTasks, current_user=Depends(auth.get_current_user)):
    _check_safety(chat_req.message)

    # 构建 RAG prompt，用于缓存键（与缓存命中时一致）
    rag_prompt = _rag_chat_inner(chat_req.message, chat_req.use_rag)
    prompt_for_cache = rag_prompt if chat_req.use_rag else chat_req.message

    cached = _cache_get(prompt_for_cache)
    if cached:
        bg.add_task(_save_chat_record, current_user.uid, chat_req.message, cached)
        return {
            "code": 200,
            "user_content": chat_req.message,
            "ai_reply": cached,
            "create_time": str(datetime.now()),
            "cached": True,
        }

    ai_reply_text = llm_engine.generate(rag_prompt)
    bg.add_task(_save_chat_record, current_user.uid, chat_req.message, ai_reply_text)
    _cache_set(prompt_for_cache, ai_reply_text)

    return {
        "code": 200,
        "user_content": chat_req.message,
        "ai_reply": ai_reply_text,
        "create_time": str(datetime.now()),
    }


@app.get("/chat/rag/stream")
def chat_rag_stream(
    token: str = Query(...),
    message: str = Query(...),
    use_rag: bool = Query(True),
):
    current_user = auth.get_current_user_from_query(token)
    _check_safety(message)

    enhanced_prompt = _rag_chat_inner(message, use_rag)

    def event_stream():
        full_reply = ""
        try:
            for chunk in llm_engine.generate_stream(enhanced_prompt):
                full_reply += chunk
                yield f"data: {json.dumps({'token': chunk}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"RAG stream error: {e}", exc_info=True)
            yield f"data: {json.dumps({'error': '生成中断，请重试'})}\n\n"
            return

        try:
            record = _save_chat_record(current_user.uid, message, full_reply)
            yield f"data: {json.dumps({'done': True, 'record_id': record.id}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"Save record error: {e}", exc_info=True)
            yield f"data: {json.dumps({'done': True, 'error': '记录保存失败'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _rag_chat_inner(message: str, use_rag: bool) -> str:
    """RAG 内部逻辑：检索 + 空上下文兜底 + prompt 构建"""
    if use_rag:
        contexts = rag_retriever.search_knowledge(message, top_k=3)
        if contexts:
            return rag_retriever.build_rag_prompt(message, contexts)
        # 无相关知识 → 直接用普通 prompt，不做 RAG 增强
    return message
