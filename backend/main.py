import json
import json
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from database import engine, Base, get_db, SessionLocal
import models
import schemas
import llm_engine
import rag_retriever
import random

# 启动时自动创建全新规范数据表
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI数字人聊天系统")

# 全局跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"code": 200, "msg": "✅ AI数字人后端运行正常"}


# 注册接口：生成唯一8位UID + 严格大小写用户名
@app.post("/register")
def register(user: schemas.UserRequest, db=Depends(get_db)):
    all_users = db.query(models.User).all()

    # 原生Python严格区分大小写校验
    for u in all_users:
        if u.username == user.username:
            raise HTTPException(status_code=400, detail="该用户名已被注册")

    # 循环生成不重复的8位数字UID
    while True:
        random_num = random.randint(10000000, 99999999)
        new_uid = str(random_num)
        exist_uid = db.query(models.User).filter(models.User.uid == new_uid).first()
        if not exist_uid:
            break

    # 创建新用户
    new_user = models.User(
        uid = new_uid,
        username = user.username,
        password = user.password
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "code": 200,
        "msg": "注册成功",
        "uid": new_user.uid,
        "username": new_user.username
    }


# 登录接口：返回UID，全程UID做用户唯一标识
@app.post("/login")
def login(user: schemas.UserRequest, db=Depends(get_db)):
    all_users = db.query(models.User).all()
    target_user = None

    for u in all_users:
        if u.username == user.username:
            target_user = u
            break

    if not target_user:
        raise HTTPException(status_code=400, detail="用户名不存在，请检查大小写")
    if target_user.password != user.password:
        raise HTTPException(status_code=400, detail="密码错误")

    return {
        "code": 200,
        "msg": "登录成功",
        "uid": target_user.uid,
        "username": target_user.username
    }


# 启动时预加载 LLM 模型（避免首次请求等待）
@app.on_event("startup")
def startup():
    llm_engine.load_model()


# 私聊聊天接口（同步，等待完整回复后返回）
@app.post("/chat")
def chat(chat: schemas.ChatRequest, db=Depends(get_db)):
    current_user = db.query(models.User).filter(models.User.uid == chat.user_uid).first()
    if not current_user:
        raise HTTPException(status_code=400, detail="用户身份无效，请重新登录")

    ai_reply_text = llm_engine.generate(chat.message)

    new_record = models.ChatRecord(
        user_uid=chat.user_uid,
        user_content=chat.message,
        ai_reply=ai_reply_text,
        chat_type=0,
        room_id=0,
    )
    db.add(new_record)
    db.commit()
    db.refresh(new_record)

    return {
        "code": 200,
        "user_content": new_record.user_content,
        "ai_reply": new_record.ai_reply,
        "create_time": str(new_record.create_time),
    }


# SSE 流式聊天接口（打字机效果）
@app.get("/chat/stream")
def chat_stream(
    user_uid: str = Query(...),
    message: str = Query(...),
):
    # 校验用户
    db = SessionLocal()
    try:
        current_user = db.query(models.User).filter(models.User.uid == user_uid).first()
        if not current_user:
            raise HTTPException(status_code=400, detail="用户身份无效，请重新登录")
    finally:
        db.close()

    def event_stream():
        full_reply = ""
        try:
            for token in llm_engine.generate_stream(message):
                full_reply += token
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            return

        # 流式结束后写入数据库
        db_write = SessionLocal()
        try:
            record = models.ChatRecord(
                user_uid=user_uid,
                user_content=message,
                ai_reply=full_reply,
                chat_type=0,
                room_id=0,
            )
            db_write.add(record)
            db_write.commit()
            db_write.refresh(record)
            yield f"data: {json.dumps({'done': True, 'record_id': record.id}, ensure_ascii=False)}\n\n"
        finally:
            db_write.close()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# 获取当前用户专属私聊历史（UID精准隔离，支持分页）
@app.get("/my_chat_history")
def get_private_history(
    user_uid: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
):
    base_query = db.query(models.ChatRecord).filter(
        models.ChatRecord.user_uid == user_uid,
        models.ChatRecord.chat_type == 0,
    )
    total = base_query.count()

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
        "total_pages": (total + page_size - 1) // page_size,
    }


# ========== RAG 知识库管理 API ==========

class KnowledgeDoc(BaseModel):
    title: str
    content: str
    source: str = ""


@app.post("/kb/add")
def kb_add(doc: KnowledgeDoc):
    """添加/更新知识文档"""
    result = rag_retriever.add_knowledge(doc.title, doc.content, doc.source)
    return {"code": 200, "msg": "知识添加成功", "data": result}


@app.get("/kb/list")
def kb_list():
    """列出所有知识文档"""
    return {"code": 200, "data": rag_retriever.list_knowledge()}


@app.delete("/kb/{title}")
def kb_delete(title: str):
    """删除指定标题的知识文档"""
    count = rag_retriever.delete_knowledge(title)
    if count == 0:
        raise HTTPException(status_code=404, detail="未找到该知识文档")
    return {"code": 200, "msg": f"已删除 {count} 个分块"}


@app.get("/kb/search")
def kb_search(q: str = Query(...), top_k: int = Query(3, ge=1, le=10)):
    """搜索知识库"""
    results = rag_retriever.search_knowledge(q, top_k)
    return {"code": 200, "data": results}


# ========== RAG 增强聊天 ==========

class RAGChatRequest(BaseModel):
    user_uid: str
    message: str
    use_rag: bool = True


@app.post("/chat/rag")
def chat_rag(chat: RAGChatRequest, db=Depends(get_db)):
    """RAG 增强聊天（同步），检索知识库后注入 prompt 再生成回答"""
    current_user = db.query(models.User).filter(models.User.uid == chat.user_uid).first()
    if not current_user:
        raise HTTPException(status_code=400, detail="用户身份无效，请重新登录")

    # 检索相关知识
    contexts = []
    if chat.use_rag:
        contexts = rag_retriever.search_knowledge(chat.message, top_k=3)

    # 构建增强 prompt
    enhanced_prompt = rag_retriever.build_rag_prompt(chat.message, contexts)
    ai_reply_text = llm_engine.generate(enhanced_prompt)

    new_record = models.ChatRecord(
        user_uid=chat.user_uid,
        user_content=chat.message,
        ai_reply=ai_reply_text,
        chat_type=0,
        room_id=0,
    )
    db.add(new_record)
    db.commit()
    db.refresh(new_record)

    return {
        "code": 200,
        "user_content": new_record.user_content,
        "ai_reply": new_record.ai_reply,
        "create_time": str(new_record.create_time),
        "retrieved_docs": [{"title": c["metadata"]["title"], "content": c["content"][:100]}
                           for c in contexts],
    }


@app.get("/chat/rag/stream")
def chat_rag_stream(
    user_uid: str = Query(...),
    message: str = Query(...),
    use_rag: bool = Query(True),
):
    """RAG 增强流式聊天（SSE）"""
    db = SessionLocal()
    try:
        current_user = db.query(models.User).filter(models.User.uid == user_uid).first()
        if not current_user:
            raise HTTPException(status_code=400, detail="用户身份无效，请重新登录")
    finally:
        db.close()

    # 在生成器外部预先检索，避免重复检索
    contexts = []
    if use_rag:
        contexts = rag_retriever.search_knowledge(message, top_k=3)
    enhanced_prompt = rag_retriever.build_rag_prompt(message, contexts)

    def event_stream():
        full_reply = ""
        try:
            for token in llm_engine.generate_stream(enhanced_prompt):
                full_reply += token
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            return

        db_write = SessionLocal()
        try:
            record = models.ChatRecord(
                user_uid=user_uid,
                user_content=message,
                ai_reply=full_reply,
                chat_type=0,
                room_id=0,
            )
            db_write.add(record)
            db_write.commit()
            db_write.refresh(record)
            yield f"data: {json.dumps({'done': True, 'record_id': record.id}, ensure_ascii=False)}\n\n"
        finally:
            db_write.close()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )